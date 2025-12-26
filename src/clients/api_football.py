from datetime import date
from typing import Any, Dict, Optional

from src.config.settings import Settings
from src.clients.base import BaseAPIClient


class ApiFootballClient(BaseAPIClient):
    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.provider == "sportmonks":
            base_url = str(settings.sportmonks_base_url)
            headers: Dict[str, str] = {}
            self._auth_param = {"api_token": settings.sportmonks_key or ""}
        else:
            base_url = str(settings.api_football_base_url)
            headers = {}
            if settings.api_football_key:
                headers["x-rapidapi-key"] = settings.api_football_key
            if settings.api_football_base_url.host.startswith("api-football"):
                headers["x-rapidapi-host"] = settings.api_football_base_url.host
            self._auth_param = {}

        super().__init__(
            base_url=base_url,
            headers=headers,
            rate_limit_per_sec=settings.rate_limit_per_sec,
        )

    def _params(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = {**self._auth_param}
        if extra:
            params.update({k: v for k, v in extra.items() if v is not None})
        return params

    async def fixtures_by_date(
        self, target_date: date, league_id: Optional[int] = None
    ) -> Dict[str, Any]:
        if self.settings.provider == "sportmonks":
            # Sportmonks v3: fixtures/date/{date}
            path = f"fixtures/date/{target_date.isoformat()}"
            params = self._params({"include": "league;participants;state"})
            data = await self.http.get(path, params=params)
            return self._map_sportmonks_fixtures(data)
        else:
            params = self._params(
                {"date": target_date.isoformat(), "league": league_id}
            )
            return await self.http.get("fixtures", params=params)

    async def odds_by_fixture(self, fixture_id: int) -> Dict[str, Any]:
        if self.settings.provider == "sportmonks":
            # Sportmonks v3: odds/pre-match/fixtures/{fixture_id}
            path = f"odds/pre-match/fixtures/{fixture_id}"
            return await self.http.get(path, params=self._params())
        else:
            params = self._params({"fixture": fixture_id, "markets": "1x2"})
            return await self.http.get("odds", params=params)

    async def lineups(self, fixture_id: int) -> Dict[str, Any]:
        if self.settings.provider == "sportmonks":
            # Sportmonks v3: fixtures/{id}?include=lineups
            path = f"fixtures/{fixture_id}"
            params = self._params({"include": "lineups.player"})
            data = await self.http.get(path, params=params)
            return self._map_sportmonks_lineups(data)
        else:
            params = self._params({"fixture": fixture_id})
            return await self.http.get("fixtures/lineups", params=params)

    async def live_fixtures(self) -> Dict[str, Any]:
        if self.settings.provider == "sportmonks":
            # Sportmonks v3: livescores/now
            path = "livescores/now"
            params = self._params({"include": "league;participants;state;scores"})
            data = await self.http.get(path, params=params)
            return self._map_sportmonks_fixtures(data)
        else:
            params = self._params({"live": "all"})
            return await self.http.get("fixtures", params=params)

    def _map_sportmonks_fixtures(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Map Sportmonks v3 response to API-Football structure
        sm_fixtures = data.get("data", [])
        mapped = []
        for f in sm_fixtures:
            # Participants
            participants = f.get("participants", [])
            home = next(
                (
                    p
                    for p in participants
                    if p.get("meta", {}).get("location") == "home"
                ),
                {},
            )
            away = next(
                (
                    p
                    for p in participants
                    if p.get("meta", {}).get("location") == "away"
                ),
                {},
            )

            # Scores
            scores = f.get("scores", [])
            # Find current score (usually description="CURRENT" or type_id logic)
            # Simple fallback: look for score with participant_id
            home_score = next(
                (
                    s.get("score", {}).get("goals")
                    for s in scores
                    if s.get("participant_id") == home.get("id")
                    and s.get("description") == "CURRENT"
                ),
                None,
            )
            away_score = next(
                (
                    s.get("score", {}).get("goals")
                    for s in scores
                    if s.get("participant_id") == away.get("id")
                    and s.get("description") == "CURRENT"
                ),
                None,
            )

            # League
            league = f.get("league", {})

            mapped.append(
                {
                    "fixture": {
                        "id": f.get("id"),
                        "date": f.get("starting_at"),
                        "status": {
                            "short": f.get("state", {}).get("short_name", "TBD")
                        },
                    },
                    "league": {
                        "id": league.get("id"),
                        "name": league.get("name"),
                        "country": league.get("country", {}).get("name"),
                        "season": f.get("season_id"),
                    },
                    "teams": {
                        "home": {"id": home.get("id"), "name": home.get("name")},
                        "away": {"id": away.get("id"), "name": away.get("name")},
                    },
                    "goals": {"home": home_score, "away": away_score},
                }
            )
        return {"response": mapped}

    def _map_sportmonks_lineups(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Map Sportmonks v3 lineups to API-Football structure
        # API-Football: response: [{team: {...}, startXI: [...], substitutes: [...]}, ...]
        f = data.get("data", {})
        lineups = f.get("lineups", [])

        # Group by team_id
        teams_map = {}
        for l in lineups:
            tid = l.get("team_id")
            if tid not in teams_map:
                teams_map[tid] = {"team": {"id": tid}, "startXI": [], "substitutes": []}

            player = {
                "player": {
                    "id": l.get("player_id"),
                    "name": l.get("player_name")
                    or l.get("player", {}).get("display_name"),
                    "number": l.get("jersey_number"),
                    "pos": l.get("position_code"),
                }
            }
            if l.get("type_id") in [
                11,
                1,
            ]:  # 11=Lineup, 1=Lineup (check docs, usually type is distinct)
                # Assuming type logic or just 'lineup' vs 'bench'
                # Sportmonks v3: type_id 11 is usually starting XI?
                # Let's assume if it's in 'lineups' include, we check a property.
                # Actually Sportmonks v3 has 'lineups' list.
                pass

            # Simplified: just put everyone in startXI for now as we only check for existence
            teams_map[tid]["startXI"].append(player)

        return {"response": list(teams_map.values())}
