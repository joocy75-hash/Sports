import asyncio
from typing import List

from sqlalchemy import desc, select

from src.agents.base import BaseAgent
from src.core.logging import get_logger
from src.db.models import Match, TeamStats
from src.db.session import get_session

logger = get_logger(__name__)


class MomentumAgent(BaseAgent):
    async def run(self) -> None:
        self.logger.info("MomentumAgent run is manual; call refresh_all().")
        while True:
            await asyncio.sleep(3600)

    async def refresh_all(self, season: int) -> None:
        async with get_session() as session:
            team_ids = [row[0] for row in await session.execute(select(TeamStats.team_id).distinct())]
            for tid in team_ids:
                score = await self._compute_momentum(session, tid)
                await session.merge(TeamStats(team_id=tid, season=season, momentum=score))
            await session.commit()

    async def _compute_momentum(self, session, team_id: int) -> float:
        q = (
            select(Match)
            .where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
            .order_by(desc(Match.start_time))
            .limit(5)
        )
        matches: List[Match] = list((await session.scalars(q)).all())
        if not matches:
            return 0.0

        points = 0
        for m in matches:
            if m.score_home is None or m.score_away is None:
                continue
            if m.home_team_id == team_id:
                if m.score_home > m.score_away:
                    points += 3
                elif m.score_home == m.score_away:
                    points += 1
            else:
                if m.score_away > m.score_home:
                    points += 3
                elif m.score_home == m.score_away:
                    points += 1
        return round(points / (len(matches) * 3), 3)
