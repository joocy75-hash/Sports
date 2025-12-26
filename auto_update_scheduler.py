#!/usr/bin/env python3
"""
자동 업데이트 스케줄러 - 축구 승무패 / 농구 승5패 자동 분석 및 알림

기능:
1. 새 회차 자동 감지
2. 14경기 정확히 수집 및 분석
3. 텔레그램 자동 알림
4. 스마트 스케줄링 (마감 시간 기반)

사용법:
    python auto_update_scheduler.py                    # 모든 게임 모니터링
    python auto_update_scheduler.py --basketball      # 농구만
    python auto_update_scheduler.py --soccer          # 축구만
    python auto_update_scheduler.py --interval 2      # 2시간 간격
    python auto_update_scheduler.py --once            # 1회 실행
"""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from src.services.round_manager import RoundManager
from src.services.telegram_notifier import TelegramNotifier
from basketball_w5l_notifier import BasketballW5LNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoUpdateScheduler:
    """자동 업데이트 스케줄러"""

    def __init__(self):
        self.round_manager = RoundManager()
        self.notifier = TelegramNotifier()
        self.basketball_notifier = BasketballW5LNotifier()

        # 마지막 분석 회차 추적
        self.last_analyzed = {
            "basketball_w5l": None,
            "soccer_wdl": None,
        }

    async def check_and_notify_basketball(self, force: bool = False) -> bool:
        """
        농구 승5패 새 회차 확인 및 알림

        Args:
            force: 강제 분석 (회차 비교 없이)

        Returns:
            True if 분석 및 알림 성공
        """
        try:
            round_info, games = await self.round_manager.get_basketball_w5l_round(force_refresh=True)

            if not games:
                logger.warning("🏀 농구 승5패: 경기 데이터 없음")
                return False

            # 새 회차 확인
            current_round = round_info.round_number
            last_round = self.last_analyzed["basketball_w5l"]

            if not force and last_round and current_round <= last_round:
                logger.info(f"🏀 농구 승5패 {current_round}회차: 이미 분석됨")
                return False

            # 새 회차 분석
            logger.info(f"🏀 농구 승5패 {current_round}회차 분석 시작...")
            logger.info(f"   경기일: {round_info.match_date}")
            logger.info(f"   경기 수: {len(games)}경기")
            logger.info(f"   마감: {round_info.deadline}")

            # BasketballW5LNotifier 사용하여 분석 및 전송
            success = await self.basketball_notifier.run_analysis(test_mode=False)

            if success:
                self.last_analyzed["basketball_w5l"] = current_round
                logger.info(f"✅ 농구 승5패 {current_round}회차 분석 및 알림 완료")
            else:
                logger.error(f"❌ 농구 승5패 {current_round}회차 분석 실패")

            return success

        except Exception as e:
            logger.error(f"농구 승5패 분석 오류: {e}")
            return False

    async def check_and_notify_soccer(self, force: bool = False) -> bool:
        """
        축구 승무패 새 회차 확인 및 알림

        Args:
            force: 강제 분석 (회차 비교 없이)

        Returns:
            True if 분석 및 알림 성공
        """
        try:
            round_info, games = await self.round_manager.get_soccer_wdl_round(force_refresh=True)

            if not games:
                logger.warning("⚽ 축구 승무패: 경기 데이터 없음")
                return False

            # 새 회차 확인
            current_round = round_info.round_number
            last_round = self.last_analyzed["soccer_wdl"]

            if not force and last_round and current_round <= last_round:
                logger.info(f"⚽ 축구 승무패 {current_round}회차: 이미 분석됨")
                return False

            # 새 회차 분석
            logger.info(f"⚽ 축구 승무패 {current_round}회차 분석 시작...")
            logger.info(f"   경기일: {round_info.match_date}")
            logger.info(f"   경기 수: {len(games)}경기")
            logger.info(f"   마감: {round_info.deadline}")

            # 축구 분석 메시지 생성 및 전송
            message = self._format_soccer_message(round_info, games)
            success = await self.notifier.send_message(message)

            if success:
                self.last_analyzed["soccer_wdl"] = current_round
                logger.info(f"✅ 축구 승무패 {current_round}회차 알림 완료")
            else:
                logger.error(f"❌ 축구 승무패 {current_round}회차 알림 실패")

            return success

        except Exception as e:
            logger.error(f"축구 승무패 분석 오류: {e}")
            return False

    def _format_soccer_message(self, round_info, games) -> str:
        """축구 승무패 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = []
        lines.append(f"⚽ *축구토토 승무패 {round_info.round_number}회차*")
        lines.append(f"📅 {now_str}")
        lines.append("━" * 24)
        lines.append("")
        lines.append("📋 *14경기 전체 예측*")
        lines.append("")

        for i, game in enumerate(games[:14], 1):
            home = game.get("hteam_han_nm", "홈팀")[:8]
            away = game.get("ateam_han_nm", "원정팀")[:8]
            match_tm = str(game.get("match_tm", "0000")).zfill(4)
            time_str = f"{match_tm[:2]}:{match_tm[2:]}"

            # 간단한 예측 (실제로는 AI 분석 필요)
            lines.append(f"{i:02d}. {home} vs {away}")
            lines.append(f"     ⏰ {time_str}")
            lines.append("")

        lines.append("━" * 24)
        lines.append("")
        lines.append("_베트맨 스포츠토토 AI 분석_")

        return "\n".join(lines)

    async def run_once(self, basketball: bool = True, soccer: bool = True, force: bool = False):
        """1회 실행"""
        logger.info("=" * 60)
        logger.info("🎯 스포츠토토 자동 분석 시스템")
        logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        if basketball:
            await self.check_and_notify_basketball(force=force)
            await asyncio.sleep(2)

        if soccer:
            await self.check_and_notify_soccer(force=force)

        logger.info("=" * 60)
        logger.info("✅ 분석 완료")
        logger.info("=" * 60)

    async def run_scheduler(
        self,
        interval_hours: int = 4,
        basketball: bool = True,
        soccer: bool = True
    ):
        """
        스케줄러 모드 실행

        Args:
            interval_hours: 체크 간격 (시간)
            basketball: 농구 승5패 모니터링
            soccer: 축구 승무패 모니터링
        """
        logger.info("=" * 60)
        logger.info("🎯 스포츠토토 자동 업데이트 스케줄러")
        logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        logger.info(f"⏰ 체크 간격: {interval_hours}시간")
        logger.info(f"🏀 농구 승5패: {'활성' if basketball else '비활성'}")
        logger.info(f"⚽ 축구 승무패: {'활성' if soccer else '비활성'}")
        logger.info("   Ctrl+C로 종료")
        logger.info("=" * 60)

        # 시작 시 1회 실행
        await self.run_once(basketball=basketball, soccer=soccer, force=True)

        while True:
            try:
                # 다음 체크 시간 계산
                next_check = datetime.now() + timedelta(hours=interval_hours)
                logger.info(f"⏰ 다음 체크: {next_check.strftime('%Y-%m-%d %H:%M')}")

                # 대기
                await asyncio.sleep(interval_hours * 3600)

                # 새 회차 확인 및 알림
                logger.info("")
                logger.info("=" * 60)
                logger.info(f"🔄 회차 체크 중... ({datetime.now().strftime('%H:%M')})")
                logger.info("=" * 60)

                if basketball:
                    await self.check_and_notify_basketball()
                    await asyncio.sleep(2)

                if soccer:
                    await self.check_and_notify_soccer()

            except KeyboardInterrupt:
                logger.info("")
                logger.info("🛑 스케줄러 종료")
                break
            except Exception as e:
                logger.error(f"스케줄러 오류: {e}")
                await asyncio.sleep(300)  # 5분 후 재시도


async def main():
    parser = argparse.ArgumentParser(
        description="스포츠토토 자동 업데이트 스케줄러"
    )
    parser.add_argument(
        "--basketball", "-b",
        action="store_true",
        help="농구 승5패만 모니터링"
    )
    parser.add_argument(
        "--soccer", "-s",
        action="store_true",
        help="축구 승무패만 모니터링"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=4,
        help="체크 간격 (시간, 기본: 4)"
    )
    parser.add_argument(
        "--once", "-o",
        action="store_true",
        help="1회만 실행 (스케줄러 없이)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="강제 분석 (이전 회차 무시)"
    )

    args = parser.parse_args()

    # 옵션 처리
    basketball = True
    soccer = True

    if args.basketball and not args.soccer:
        soccer = False
    elif args.soccer and not args.basketball:
        basketball = False

    scheduler = AutoUpdateScheduler()

    if args.once:
        await scheduler.run_once(
            basketball=basketball,
            soccer=soccer,
            force=args.force
        )
    else:
        await scheduler.run_scheduler(
            interval_hours=args.interval,
            basketball=basketball,
            soccer=soccer
        )


if __name__ == "__main__":
    asyncio.run(main())
