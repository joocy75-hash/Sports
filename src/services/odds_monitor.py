"""
실시간 배당 변동 모니터링 서비스
주기적으로 배당 변화를 감지하고 WebSocket으로 브로드캐스트합니다.
"""

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.db.models import Match
from src.services.websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)


class OddsMonitor:
    """
    배당 변동 모니터링 서비스

    Features:
    - 주기적인 배당 데이터 폴링
    - 변동 감지 및 WebSocket 브로드캐스트
    - Redis Pub/Sub을 통한 멀티 서버 지원
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        poll_interval: int = 30
    ):
        """
        Args:
            session_factory: SQLAlchemy 세션 팩토리
            poll_interval: 폴링 간격 (초)
        """
        self.session_factory = session_factory
        self.poll_interval = poll_interval
        self.is_running = False
        self.task: Optional[asyncio.Task] = None

        # 이전 배당 저장 (match_id -> odds dict)
        self.previous_odds: Dict[str, Dict[str, float]] = {}

    async def start(self) -> None:
        """모니터링 시작"""
        if self.is_running:
            logger.warning("Odds monitor is already running")
            return

        self.is_running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info(f"✅ Odds monitor started (poll interval: {self.poll_interval}s)")

    async def stop(self) -> None:
        """모니터링 중지"""
        if not self.is_running:
            return

        self.is_running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("🛑 Odds monitor stopped")

    async def _monitor_loop(self) -> None:
        """모니터링 루프"""
        logger.info("🎧 Odds monitoring loop started")

        while self.is_running:
            try:
                await self._check_odds_changes()
            except Exception as e:
                logger.error(f"Error in odds monitoring loop: {e}", exc_info=True)

            # 다음 폴링까지 대기
            await asyncio.sleep(self.poll_interval)

    async def _check_odds_changes(self) -> None:
        """배당 변동 체크"""
        async with self.session_factory() as session:
            try:
                # 오늘 & 내일 경기의 배당 조회
                stmt = (
                    select(Match)
                    .options(
                        joinedload(Match.home_team),
                        joinedload(Match.away_team),
                        joinedload(Match.league)
                    )
                    .where(
                        Match.odds_home.isnot(None),
                        Match.odds_draw.isnot(None),
                        Match.odds_away.isnot(None)
                    )
                    .limit(50)  # 최근 50경기만
                )

                result = await session.execute(stmt)
                matches = result.unique().scalars().all()

                # 각 경기의 배당 변동 확인
                for match in matches:
                    await self._process_match_odds(match)

            except Exception as e:
                logger.error(f"Error checking odds changes: {e}", exc_info=True)

    async def _process_match_odds(self, match: Match) -> None:
        """
        경기 배당 처리 및 변동 감지

        Args:
            match: Match 모델 인스턴스
        """
        match_id = str(match.id)
        current_odds = {
            "home": float(match.odds_home or 0),
            "draw": float(match.odds_draw or 0),
            "away": float(match.odds_away or 0)
        }

        # 이전 배당과 비교
        previous = self.previous_odds.get(match_id)

        if previous:
            # 변동 계산
            change = {
                "home": current_odds["home"] - previous["home"],
                "draw": current_odds["draw"] - previous["draw"],
                "away": current_odds["away"] - previous["away"]
            }

            # 변동이 있으면 브로드캐스트
            threshold = 0.01  # 1% 이상 변동만 알림
            has_change = any(abs(c) >= threshold for c in change.values())

            if has_change:
                await self._broadcast_odds_update(match, current_odds, change)

        # 현재 배당 저장
        self.previous_odds[match_id] = current_odds

    async def _broadcast_odds_update(
        self,
        match: Match,
        odds: Dict[str, float],
        change: Dict[str, float]
    ) -> None:
        """
        배당 변동 브로드캐스트

        Args:
            match: Match 모델 인스턴스
            odds: 현재 배당
            change: 변동량
        """
        message = {
            "type": "odds_update",
            "data": {
                "match_id": str(match.id),
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown",
                "league": match.league.name if match.league else "Unknown",
                "match_time": match.start_time.isoformat() if match.start_time else None,
                "odds": odds,
                "change": change
            }
        }

        # WebSocket 브로드캐스트
        await ws_manager.broadcast("odds", message)

        # Redis로도 발행 (다른 서버 인스턴스에 전파)
        await ws_manager.publish_to_redis("odds", message)

        logger.info(
            f"📊 Odds update: {match.home_team.name if match.home_team else 'Unknown'} vs "
            f"{match.away_team.name if match.away_team else 'Unknown'} "
            f"(H: {change['home']:+.2f}, D: {change['draw']:+.2f}, A: {change['away']:+.2f})"
        )

    async def trigger_manual_update(self, match_id: int) -> bool:
        """
        특정 경기의 배당 업데이트를 수동으로 트리거

        Args:
            match_id: 경기 ID

        Returns:
            bool: 성공 여부
        """
        async with self.session_factory() as session:
            try:
                stmt = (
                    select(Match)
                    .options(
                        joinedload(Match.home_team),
                        joinedload(Match.away_team),
                        joinedload(Match.league)
                    )
                    .where(Match.id == match_id)
                )

                result = await session.execute(stmt)
                match = result.unique().scalar_one_or_none()

                if not match:
                    logger.warning(f"Match not found: {match_id}")
                    return False

                await self._process_match_odds(match)
                logger.info(f"✅ Manual odds update triggered for match {match_id}")
                return True

            except Exception as e:
                logger.error(f"Error in manual update: {e}", exc_info=True)
                return False


# 전역 인스턴스 (unified_server.py에서 초기화됨)
_odds_monitor: Optional[OddsMonitor] = None


def initialize_odds_monitor(
    session_factory: async_sessionmaker[AsyncSession],
    poll_interval: int = 30
) -> OddsMonitor:
    """
    Odds Monitor 초기화

    Args:
        session_factory: SQLAlchemy 세션 팩토리
        poll_interval: 폴링 간격 (초)

    Returns:
        OddsMonitor: 초기화된 모니터 인스턴스
    """
    global _odds_monitor
    _odds_monitor = OddsMonitor(session_factory, poll_interval)
    return _odds_monitor


def get_odds_monitor() -> Optional[OddsMonitor]:
    """
    Odds Monitor 인스턴스 가져오기

    Returns:
        OddsMonitor | None: 모니터 인스턴스
    """
    return _odds_monitor
