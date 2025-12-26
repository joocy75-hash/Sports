from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.orm import aliased

from src.db.models import League, Match, OddsHistory, PredictionLog, Team
from src.db.session import get_session


async def fetch_fixtures(limit: int = 50) -> List[dict]:
    now = datetime.utcnow()
    window_end = now + timedelta(days=2)
    home_team = aliased(Team)
    away_team = aliased(Team)
    stmt = (
        select(Match, League, home_team, away_team)
        .join(League, Match.league_id == League.id)
        .join(home_team, Match.home_team_id == home_team.id)
        .join(away_team, Match.away_team_id == away_team.id)
        .where(Match.start_time >= now, Match.start_time <= window_end)
        .order_by(Match.start_time)
        .limit(limit)
    )
    async with get_session() as session:
        rows = (await session.execute(stmt)).all()
    fixtures: List[dict] = []
    for match, league, home, away in rows:
        fixtures.append(
            {
                "id": match.id,
                "league": league.name,
                "home": home.name,
                "away": away.name,
                "start": match.start_time.isoformat(),
                "lineupEta": "Confirmed" if match.lineup_confirmed_at else "Pending",
                "sport": match.sport,
                "odds": {
                    "home": match.odds_home,
                    "draw": match.odds_draw,
                    "away": match.odds_away,
                },
                "sharp": {
                    "flag": match.sharp_detected,
                    "direction": match.sharp_direction,
                },
                "oddsDelta": await get_odds_delta(match.id),
            }
        )
    return fixtures


async def fetch_picks(limit: int = 5) -> List[dict]:
    home_team = aliased(Team)
    away_team = aliased(Team)
    stmt = (
        select(PredictionLog, Match, League, home_team, away_team)
        .join(Match, PredictionLog.match_id == Match.id)
        .join(League, Match.league_id == League.id)
        .join(home_team, Match.home_team_id == home_team.id)
        .join(away_team, Match.away_team_id == away_team.id)
        .order_by(PredictionLog.created_at.desc())
        .limit(limit * 3)
    )
    async with get_session() as session:
        rows = (await session.execute(stmt)).all()
    picks: List[dict] = []
    seen_matches = set()
    for log, match, league, home, away in rows:
        if match.id in seen_matches:
            continue
        best_label, best_value = best_value_label(log)
        if best_value is None or best_value <= 0:
            continue
        seen_matches.add(match.id)
        picks.append(
            {
                "id": log.id,
                "league": league.name,
                "match": f"{home.name} vs {away.name}",
                "edge": best_value,
                "prob": prob_for_label(log, best_label),
                "odds": odds_for_label(match, best_label),
                "market": "1X2",
            }
        )
    picks.sort(key=lambda x: x["edge"], reverse=True)
    return picks[:limit]


async def fetch_match_detail(match_id: int) -> Optional[dict]:
    async with get_session() as session:
        home_team = aliased(Team)
        away_team = aliased(Team)
        row = await session.execute(
            select(Match, League, home_team, away_team)
            .join(League, Match.league_id == League.id)
            .join(home_team, Match.home_team_id == home_team.id)
            .join(away_team, Match.away_team_id == away_team.id)
            .where(Match.id == match_id)
        )
        result = row.first()
        if not result:
            return None
        match, league, home, away = result

        odds_history = (
            (
                await session.execute(
                    select(OddsHistory)
                    .where(OddsHistory.match_id == match_id)
                    .order_by(desc(OddsHistory.captured_at))
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
        predictions = (
            (
                await session.execute(
                    select(PredictionLog)
                    .where(PredictionLog.match_id == match_id)
                    .order_by(desc(PredictionLog.created_at))
                )
            )
            .scalars()
            .all()
        )

    return {
        "id": match.id,
        "league": league.name,
        "sport": match.sport,
        "start": match.start_time.isoformat(),
        "home": home.name,
        "away": away.name,
        "score": {"home": match.score_home, "away": match.score_away},
        "odds": {
            "home": match.odds_home,
            "draw": match.odds_draw,
            "away": match.odds_away,
        },
        "sharp": {"flag": match.sharp_detected, "direction": match.sharp_direction},
        "recommendation": match.recommendation,
        "stake_pct": match.recommended_stake_pct,
        "predictions": [
            {
                "created_at": p.created_at.isoformat(),
                "prob": {"home": p.prob_home, "draw": p.prob_draw, "away": p.prob_away},
                "value": {
                    "home": p.value_home,
                    "draw": p.value_draw,
                    "away": p.value_away,
                },
                "expected_score": {
                    "home": p.expected_score_home,
                    "away": p.expected_score_away,
                },
                "meta": p.meta,
            }
            for p in predictions
        ],
        "odds_history": [
            {
                "captured_at": o.captured_at.isoformat(),
                "odds": {"home": o.odds_home, "draw": o.odds_draw, "away": o.odds_away},
                "bookmaker": o.bookmaker,
                "market": o.market,
            }
            for o in odds_history
        ],
    }


async def get_odds_delta(match_id: int) -> dict:
    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    select(OddsHistory)
                    .where(OddsHistory.match_id == match_id)
                    .order_by(desc(OddsHistory.captured_at))
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
    if len(rows) < 2:
        return {"home": 0, "draw": 0, "away": 0}
    latest, prev = rows[0], rows[1]

    def delta(cur: Optional[float], prv: Optional[float]) -> float:
        if cur and prv and prv > 0:
            return round((cur - prv) / prv, 4)
        return 0.0

    return {
        "home": delta(latest.odds_home, prev.odds_home),
        "draw": delta(latest.odds_draw, prev.odds_draw),
        "away": delta(latest.odds_away, prev.odds_away),
    }


def prob_for_label(log: PredictionLog, label: Optional[str]) -> float:
    if label == "home":
        return log.prob_home
    if label == "draw":
        return log.prob_draw
    if label == "away":
        return log.prob_away
    return 0.0


def odds_for_label(match: Match, label: Optional[str]) -> float:
    if label == "home":
        return match.odds_home or 0.0
    if label == "draw":
        return match.odds_draw or 0.0
    if label == "away":
        return match.odds_away or 0.0
    return 0.0


def best_value_label(log: PredictionLog) -> Tuple[Optional[str], Optional[float]]:
    best_label: Optional[str] = None
    best_value: Optional[float] = None
    for label, val in [
        ("home", log.value_home),
        ("draw", log.value_draw),
        ("away", log.value_away),
    ]:
        if val is None:
            continue
        if best_value is None or val > best_value:
            best_value = val
            best_label = label
    return best_label, best_value


def fallback_data():
    fixtures = [
        {
            "id": "1",
            "league": "EPL",
            "home": "Man City",
            "away": "Arsenal",
            "start": datetime.utcnow().isoformat(),
        },
        {
            "id": "2",
            "league": "La Liga",
            "home": "Real Madrid",
            "away": "Atleti",
            "start": datetime.utcnow().isoformat(),
        },
    ]
    picks = [
        {
            "id": "p1",
            "league": "EPL",
            "match": "Spurs vs Newcastle",
            "edge": 0.12,
            "prob": 0.67,
            "odds": 1.78,
            "market": "1X2",
        },
        {
            "id": "p2",
            "league": "NBA",
            "match": "Lakers @ Warriors",
            "edge": 0.09,
            "prob": 0.61,
            "odds": 1.92,
            "market": "Spread",
        },
    ]
    return fixtures, picks
