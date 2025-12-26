import asyncio
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, desc

from src.agents.base import BaseAgent
from src.clients.api_football import ApiFootballClient
from src.clients.football_data import FootballDataClient
from src.clients.the_odds_api import TheOddsApiClient
from src.clients.the_sports_db import TheSportsDBClient
from src.core.logging import get_logger
from src.db.models import League, Match, OddsHistory, Team
from src.db.session import get_session

logger = get_logger(__name__)


class DataCollectorAgent(BaseAgent):
    def __init__(self, settings):
        super().__init__(settings=settings)
        self.api_client = ApiFootballClient(settings)
        self.fd_client = FootballDataClient(settings)
        self.odds_client = TheOddsApiClient(settings)
        self.tsdb_client = TheSportsDBClient(settings)

    async def run(self) -> None:
        self.logger.info(
            "DataCollectorAgent is idle. Call fetch_and_store(date) explicitly."
        )
        while True:
            await asyncio.sleep(3600)

    async def fetch_and_store(
        self, target_date: date, leagues: Optional[List[int]] = None
    ) -> None:
        await self._fetch_football(target_date, leagues)
        await self._fetch_odds(target_date)
        # Enrich team info periodically
        asyncio.create_task(self.enrich_team_info())

    async def fetch_odds(self, target_date: date) -> None:
        """Public wrapper for odds fetching."""
        await self._fetch_odds(target_date)

    async def fetch_lineups(self) -> None:
        """Poll lineups for matches starting soon (next 3h)."""
        now = datetime.utcnow()
        window_end = now + timedelta(hours=3)

        async with get_session() as session:
            # Find matches in window, not started, no confirmed lineup
            stmt = select(Match).where(
                Match.start_time >= now,
                Match.start_time <= window_end,
                Match.lineup_confirmed_at.is_(None),
            )
            matches = (await session.scalars(stmt)).all()

            if not matches:
                return

            self.logger.info(f"Checking lineups for {len(matches)} matches")
            for match in matches:
                try:
                    # Use api-football client
                    lineups_data = await self.api_client.lineups(match.id)
                    response = lineups_data.get("response", [])
                    if response:
                        # We have lineups!
                        # response is a list of 2 teams usually
                        match.lineup_home = next(
                            (
                                t
                                for t in response
                                if t.get("team", {}).get("id") == match.home_team_id
                            ),
                            None,
                        )
                        match.lineup_away = next(
                            (
                                t
                                for t in response
                                if t.get("team", {}).get("id") == match.away_team_id
                            ),
                            None,
                        )
                        match.lineup_confirmed_at = datetime.utcnow()
                        self.logger.info(f"Lineups confirmed for match {match.id}")
                except Exception as exc:
                    self.logger.error(
                        f"Failed to fetch lineups for match {match.id}: {exc}"
                    )

            await session.commit()

    async def fetch_live_data(self) -> None:
        """Fetch live scores and update ongoing matches."""
        try:
            # Primary: API-Football
            data = await self.api_client.live_fixtures()
            fixtures = data.get("response", [])

            # Secondary: TheSportsDB (Backup) if primary empty
            if not fixtures:
                try:
                    tsdb_data = await self.tsdb_client.get_live_scores(sport="Soccer")
                    # Convert TSDB format to internal format if needed
                    # For now, just logging as we need mapping logic
                    if tsdb_data and tsdb_data.get("events"):
                        self.logger.info(
                            f"Fetched {len(tsdb_data['events'])} live events from TheSportsDB"
                        )
                except Exception as e:
                    self.logger.warning(f"TSDB live fetch failed: {e}")

            if not fixtures:
                return

            async with get_session() as session:
                for fixture in fixtures:
                    fixture_info = fixture.get("fixture", {})
                    goals = fixture.get("goals", {})
                    fixture_id = fixture_info.get("id")

                    if not fixture_id:
                        continue

                    match = await session.scalar(
                        select(Match).where(Match.id == fixture_id)
                    )
                    if match:
                        match.status = fixture_info.get("status", {}).get(
                            "short", match.status
                        )
                        match.score_home = goals.get("home")
                        match.score_away = goals.get("away")
                        # We could also update elapsed time if we had a column for it
                await session.commit()
                self.logger.info(f"Updated live data for {len(fixtures)} matches")
        except Exception as exc:
            self.logger.error(f"Failed to fetch live data: {exc}")

    async def enrich_team_info(self) -> None:
        """Fetch additional team details from TheSportsDB."""
        async with get_session() as session:
            # Get teams with missing logo or stadium
            # Assuming we might add these columns later, for now just fetch
            teams = (await session.scalars(select(Team).limit(10))).all()

            for team in teams:
                if not team.name:
                    continue

                details = await self.tsdb_client.search_team(team.name)
                if details:
                    # Here we would update the team model if it had logo/stadium columns
                    # team.logo_url = details.get("strTeamBadge")
                    # team.stadium = details.get("strStadium")
                    self.logger.info(f"Enriched info for {team.name}")

            await session.commit()

    async def _fetch_football(
        self, target_date: date, leagues: Optional[List[int]]
    ) -> None:
        # Top 5 Leagues IDs (API-Football):
        # 39: Premier League, 140: La Liga, 78: Bundesliga, 135: Serie A, 61: Ligue 1
        # 2: UEFA Champions League, 3: UEFA Europa League
        # 292: K League 1
        top5_ids = [39, 140, 78, 135, 61, 2, 3, 292]

        # If leagues provided, filter them to only include top 5. If None, use all top 5.
        if leagues:
            league_ids = [lid for lid in leagues if lid in top5_ids]
        else:
            league_ids = top5_ids

        tasks = [self._process_league(target_date, lid) for lid in league_ids]
        for task in tasks:
            await task

        # football-data.org fallback (Optional, can be removed if not needed for these specific leagues)
        # fd_data = await self.fd_client.matches_by_date(target_date)
        # ... (Keeping it commented out or removed to strictly follow "only these leagues")

    async def _fetch_odds(self, target_date: date) -> None:
        if not self.settings.the_odds_api_key:
            return

        # Requested Sports: Top 5 Football, NBA, MLB
        sport_keys = [
            "soccer_epl",  # Premier League
            "soccer_spain_la_liga",  # La Liga
            "soccer_germany_bundesliga",  # Bundesliga
            "soccer_italy_serie_a",  # Serie A
            "soccer_france_ligue_one",  # Ligue 1
            "basketball_nba",  # NBA
            "baseball_mlb",  # MLB
        ]

        for key in sport_keys:
            try:
                # Fetch H2H, Spreads (Handicap), Totals (Over/Under)
                odds_resp = await self.odds_client.odds(
                    sport_key=key,
                    date_filter=target_date.isoformat(),
                    regions="us,uk,eu,au",
                    markets="h2h,spreads,totals",
                )
                await self._store_odds(key, odds_resp)
            except Exception:  # noqa: BLE001
                self.logger.exception("Odds fetch failed for %s", key)

    async def _process_league(
        self, target_date: date, league_id: Optional[int]
    ) -> None:
        data = await self.api_client.fixtures_by_date(
            target_date=target_date, league_id=league_id
        )
        fixtures = data.get("response", [])
        if not fixtures:
            self.logger.warning(
                "No fixtures returned for %s league=%s", target_date, league_id
            )
            return
        async with get_session() as session:
            for fixture in fixtures:
                try:
                    await self._upsert_fixture(session, fixture)
                except Exception as exc:  # noqa: BLE001
                    self.logger.exception(
                        "Failed to persist fixture %s: %s", fixture, exc
                    )
            await session.commit()

    async def _upsert_fixture(self, session, fixture: dict) -> None:
        fixture_info = fixture.get("fixture", {})
        league_info = fixture.get("league", {})
        teams_info = fixture.get("teams", {})

        fixture_id = fixture_info.get("id")
        if not fixture_id:
            self.logger.warning("Skipping fixture without id: %s", fixture)
            return

        start_iso = fixture_info.get("date")
        start_time = (
            datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            if start_iso
            else None
        )
        season = league_info.get("season") or datetime.utcnow().year

        home_team = teams_info.get("home", {})
        away_team = teams_info.get("away", {})

        # Upsert league
        league_id = league_info.get("id")
        if league_id:
            league = await session.scalar(select(League).where(League.id == league_id))
            if not league:
                session.add(
                    League(
                        id=league_id,
                        name=league_info.get("name", "Unknown League"),
                        country=league_info.get("country"),
                        sport="football",
                    )
                )

        # Upsert teams
        for team_data in (home_team, away_team):
            tid = team_data.get("id")
            if tid:
                team = await session.scalar(select(Team).where(Team.id == tid))
                if not team:
                    session.add(
                        Team(
                            id=tid,
                            name=team_data.get("name", "Unknown Team"),
                            league_id=league_id,
                            sport="football",
                        )
                    )

        existing_match = await session.scalar(
            select(Match).where(Match.id == fixture_id)
        )
        if existing_match:
            existing_match.start_time = start_time or existing_match.start_time
            existing_match.status = fixture_info.get("status", {}).get(
                "short", existing_match.status
            )
            existing_match.home_team_id = home_team.get(
                "id", existing_match.home_team_id
            )
            existing_match.away_team_id = away_team.get(
                "id", existing_match.away_team_id
            )
            existing_match.league_id = league_id or existing_match.league_id
            existing_match.season = season
            existing_match.sport = "football"
            return

        match = Match(
            id=fixture_id,
            league_id=league_id or 0,
            season=season,
            start_time=start_time or datetime.utcnow(),
            status=fixture_info.get("status", {}).get("short", "TBD"),
            home_team_id=home_team.get("id"),
            away_team_id=away_team.get("id"),
            sport="football",
        )
        odds = fixture.get("odds")
        if odds:
            match.odds_home = odds.get("home")
            match.odds_draw = odds.get("draw")
            match.odds_away = odds.get("away")
            match.raw_odds = odds
        session.add(match)

    async def _upsert_fd_fixture(self, match: dict) -> None:
        # football-data.org match payload
        match_id = match.get("id")
        if not match_id:
            return
        league = match.get("competition", {})
        season = match.get("season", {}).get("startDate", "2024")[:4]
        utc_date = match.get("utcDate")
        start_time = (
            datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
            if utc_date
            else datetime.utcnow()
        )
        home_team = match.get("homeTeam", {})
        away_team = match.get("awayTeam", {})
        league_id = league.get("id")
        async with get_session() as session:
            if league_id:
                existing_league = await session.scalar(
                    select(League).where(League.id == league_id)
                )
                if not existing_league:
                    session.add(
                        League(
                            id=league_id,
                            name=league.get("name", "Unknown League"),
                            country=league.get("area", {}).get("name"),
                            sport="football",
                        )
                    )
            for team_data in (home_team, away_team):
                tid = team_data.get("id")
                if tid:
                    team = await session.scalar(select(Team).where(Team.id == tid))
                    if not team:
                        session.add(
                            Team(
                                id=tid,
                                name=team_data.get("name", "Unknown Team"),
                                league_id=league_id,
                                sport="football",
                            )
                        )
            existing_match = await session.scalar(
                select(Match).where(Match.id == match_id)
            )
            if not existing_match:
                session.add(
                    Match(
                        id=match_id,
                        league_id=league_id or 0,
                        season=int(season),
                        start_time=start_time,
                        status=match.get("status", "TBD"),
                        home_team_id=home_team.get("id"),
                        away_team_id=away_team.get("id"),
                        sport="football",
                    )
                )
            await session.commit()

    async def _store_odds(self, sport_key: str, odds_resp: dict) -> None:
        events = (
            odds_resp if isinstance(odds_resp, list) else odds_resp.get("data") or []
        )
        if not events:
            return
        async with get_session() as session:
            for ev in events:
                match_id = ev.get("id") or ev.get("id")
                if not match_id:
                    continue
                # The Odds API uses bookies list; find Pinnacle if present
                bookmakers = ev.get("bookmakers", [])
                pinnacle = next(
                    (
                        b
                        for b in bookmakers
                        if b.get("title", "").lower().startswith("pinnacle")
                    ),
                    None,
                )
                if not pinnacle:
                    continue
                markets = pinnacle.get("markets", [])
                h2h = next(
                    (m for m in markets if m.get("key") in {"h2h", "h2h_lay"}), None
                )
                if not h2h:
                    continue
                outcomes = h2h.get("outcomes", [])
                if len(outcomes) < 2:
                    continue
                odds_home = odds_draw = odds_away = None
                for o in outcomes:
                    name = o.get("name", "").lower()
                    if name in {"home", "team1"}:
                        odds_home = o.get("price")
                    elif name in {"away", "team2"}:
                        odds_away = o.get("price")
                    elif name == "draw":
                        odds_draw = o.get("price")
                last = await session.scalar(
                    select(OddsHistory)
                    .where(OddsHistory.match_id == match_id)
                    .order_by(desc(OddsHistory.captured_at))
                )
                session.add(
                    OddsHistory(
                        match_id=match_id,
                        bookmaker="pinnacle",
                        odds_home=odds_home,
                        odds_draw=odds_draw,
                        odds_away=odds_away,
                        payload=pinnacle,
                    )
                )
                match = await session.scalar(select(Match).where(Match.id == match_id))
                if match:
                    match.odds_home = odds_home
                    match.odds_draw = odds_draw
                    match.odds_away = odds_away
                    match.raw_odds = pinnacle

                    # crude sharp detection: >5% drop from last price
                    def drop(prev, cur):
                        if prev and cur and prev > 0:
                            return (prev - cur) / prev
                        return 0

                    drops = {
                        "home": drop(last.odds_home, odds_home) if last else 0,
                        "draw": drop(last.odds_draw, odds_draw) if last else 0,
                        "away": drop(last.odds_away, odds_away) if last else 0,
                    }
                    best_side = max(drops, key=drops.get)
                    if drops[best_side] >= 0.05:
                        match.sharp_detected = True
                        match.sharp_direction = best_side
            await session.commit()
