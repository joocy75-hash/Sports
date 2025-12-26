import asyncio
from typing import Iterable, Optional

from redis.asyncio import Redis
from sqlalchemy import select

from src.agents.base import BaseAgent
from src.clients.api_football import ApiFootballClient
from src.core.logging import get_logger
from src.db.models import Match
from src.db.session import get_session

logger = get_logger(__name__)


class LineupAgent(BaseAgent):
    def __init__(self, settings, redis_client: Optional[Redis] = None, poll_interval: int = 600):
        super().__init__(settings=settings, redis_client=redis_client)
        self.client = ApiFootballClient(settings)
        self.poll_interval = poll_interval
        self._fixtures: set[int] = set()

    def watch_fixtures(self, fixture_ids: Iterable[int]) -> None:
        self._fixtures.update(fixture_ids)

    async def run(self) -> None:
        if not self._fixtures:
            self.logger.info("LineupAgent idle; use watch_fixtures([...]) before start()")
        while True:
            await self._poll_all()
            await asyncio.sleep(self.poll_interval)

    async def _poll_all(self) -> None:
        for fid in list(self._fixtures):
            try:
                await self._poll_fixture(fid)
            except Exception:  # noqa: BLE001
                self.logger.exception("Lineup poll failed for fixture %s", fid)

    async def _poll_fixture(self, fixture_id: int) -> None:
        data = await self.client.lineups(fixture_id)
        lineups = data.get("response", [])
        if not lineups:
            return
        async with get_session() as session:
            match = await session.scalar(select(Match).where(Match.id == fixture_id))
            if not match:
                self.logger.warning("Received lineup for unknown match %s", fixture_id)
                return
            for lineup in lineups:
                team = lineup.get("team", {})
                if team.get("id") == match.home_team_id:
                    match.lineup_home = lineup
                elif team.get("id") == match.away_team_id:
                    match.lineup_away = lineup
            await session.commit()
        if self.redis:
            await self.redis.publish("lineup_ready", str(fixture_id))
        self.logger.info("Lineups updated for fixture %s", fixture_id)
