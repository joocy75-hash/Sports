"""
스케줄러 서비스 - 자동 분석 및 결과 수집 스케줄링

핵심 기능:
1. 6시간마다 새 회차 체크 및 예측 생성
2. 매일 결과 수집 및 리포트 전송
3. 주간/월간 요약 리포트
4. 상태 모니터링
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.services.round_manager import RoundManager
from src.services.telegram_notifier import TelegramNotifier
from src.services.prediction_tracker import prediction_tracker
from src.services.result_collector import result_collector
from src.services.hit_rate_reporter import hit_rate_reporter

logger = logging.getLogger(__name__)


class SchedulerService:
    """자동 스케줄러 서비스"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone='Asia/Seoul')
        self.round_manager = RoundManager()
        self.notifier = TelegramNotifier()

        # 상태 저장
        self.state_file = Path(__file__).parent.parent.parent / ".state" / "scheduler_state.json"
        self.last_processed = {
            "soccer_wdl": 0,
            "basketball_w5l": 0,
            "last_result_check": None,
        }

    # ==================== 스케줄 작업 정의 ====================

    async def check_new_rounds_and_analyze(self):
        """
        새 회차 체크 및 자동 분석

        스케줄: 6시간마다
        """
        logger.info("\n" + "=" * 60)
        logger.info("🔄 새 회차 체크 시작")
        logger.info(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        try:
            # 축구 승무패 체크
            await self._check_and_analyze_game_type("soccer_wdl")

            # 농구 승5패 체크
            await self._check_and_analyze_game_type("basketball_w5l")

        except Exception as e:
            logger.error(f"❌ 새 회차 체크 실패: {e}")
            import traceback
            traceback.print_exc()

            # 에러 알림
            error_msg = (
                f"⚠️ *스케줄러 오류*\n\n"
                f"작업: 새 회차 체크\n"
                f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"오류: {str(e)[:100]}"
            )
            await self.notifier.send_message(error_msg)

    async def _check_and_analyze_game_type(self, game_type: str):
        """특정 게임 타입 체크 및 분석"""
        game_name = "⚽ 축구 승무패" if game_type == "soccer_wdl" else "🏀 농구 승5패"

        try:
            # 새 회차 체크
            new_round = await self.round_manager.check_new_round(game_type)

            if not new_round:
                logger.info(f"{game_name}: 새 회차 없음")
                return

            # 이미 처리한 회차인지 확인
            if new_round <= self.last_processed.get(game_type, 0):
                logger.info(f"{game_name}: {new_round}회차 이미 처리됨")
                return

            logger.info(f"\n🆕 {game_name} 새 회차 감지: {new_round}회차")

            # 분석 실행 (auto_sports_notifier 대신 직접 구현)
            from auto_sports_notifier import AutoSportsNotifier

            notifier = AutoSportsNotifier()

            if game_type == "soccer_wdl":
                success = await notifier.analyze_soccer(test_mode=False)
            else:
                success = await notifier.analyze_basketball(test_mode=False)

            if success:
                self.last_processed[game_type] = new_round
                logger.info(f"✅ {game_name} {new_round}회차 분석 완료!")
            else:
                logger.error(f"❌ {game_name} {new_round}회차 분석 실패")

        except Exception as e:
            logger.error(f"❌ {game_name} 체크 실패: {e}")

    async def collect_results_and_report(self):
        """
        미수집 결과 수집 및 리포트 전송

        스케줄: 매일 06:00
        """
        logger.info("\n" + "=" * 60)
        logger.info("📊 결과 수집 및 리포트 전송 시작")
        logger.info(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        try:
            # 축구 승무패
            await self._collect_results_for_game_type("soccer_wdl")

            # 농구 승5패
            await self._collect_results_for_game_type("basketball_w5l")

            # 마지막 체크 시간 업데이트
            self.last_processed["last_result_check"] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"❌ 결과 수집 실패: {e}")
            import traceback
            traceback.print_exc()

            # 에러 알림
            error_msg = (
                f"⚠️ *스케줄러 오류*\n\n"
                f"작업: 결과 수집\n"
                f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"오류: {str(e)[:100]}"
            )
            await self.notifier.send_message(error_msg)

    async def _collect_results_for_game_type(self, game_type: str):
        """특정 게임 타입 결과 수집"""
        game_name = "⚽ 축구 승무패" if game_type == "soccer_wdl" else "🏀 농구 승5패"

        try:
            # 미수집 회차 찾기
            pending = await result_collector.check_pending_rounds(game_type)

            if not pending:
                logger.info(f"{game_name}: 미수집 회차 없음")
                return

            logger.info(f"\n📋 {game_name} 미수집 회차 {len(pending)}개: {pending[:5]}")

            # 각 회차 처리
            for round_num in pending[:5]:  # 최대 5개씩만 처리
                try:
                    logger.info(f"\n🔄 {round_num}회차 결과 수집 중...")

                    # 결과 수집
                    round_result = await result_collector.collect_round_results(
                        round_num, game_type
                    )

                    if not round_result:
                        logger.warning(f"⚠️ {round_num}회차 결과 없음 (아직 경기 종료 전)")
                        continue

                    # 리포트 생성
                    report = hit_rate_reporter.generate_report(round_num, game_type)

                    if not report:
                        logger.warning(f"⚠️ {round_num}회차 리포트 생성 실패")
                        continue

                    # 텔레그램 전송
                    message = hit_rate_reporter.format_telegram_message(report)
                    success = await self.notifier.send_message(message)

                    if success:
                        logger.info(f"✅ {round_num}회차 리포트 전송 완료!")
                    else:
                        logger.error(f"❌ {round_num}회차 텔레그램 전송 실패")

                    # API 호출 간격
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"❌ {round_num}회차 처리 실패: {e}")
                    await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"❌ {game_name} 결과 수집 실패: {e}")

    async def send_weekly_summary(self):
        """
        주간 요약 리포트 전송

        스케줄: 매주 월요일 09:00
        """
        logger.info("\n" + "=" * 60)
        logger.info("📈 주간 요약 리포트 생성")
        logger.info(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        try:
            # 축구 승무패 통계
            soccer_stats = prediction_tracker.get_cumulative_stats("soccer_wdl")

            # 농구 승5패 통계
            basketball_stats = prediction_tracker.get_cumulative_stats("basketball_w5l")

            # 메시지 생성
            lines = [
                "📊 *주간 요약 리포트*",
                f"📅 {datetime.now().strftime('%Y년 %주차')}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━",
            ]

            if soccer_stats:
                lines.extend([
                    "",
                    "⚽ *축구 승무패*",
                    f"• 평균 적중률: {soccer_stats.avg_hit_rate * 100:.1f}%",
                    f"• 최근 5회차: {soccer_stats.recent_5_avg * 100:.1f}%",
                    f"• 전체 적중: {soccer_stats.single_hits}회",
                ])

            if basketball_stats:
                lines.extend([
                    "",
                    "🏀 *농구 승5패*",
                    f"• 평균 적중률: {basketball_stats.avg_hit_rate * 100:.1f}%",
                    f"• 최근 5회차: {basketball_stats.recent_5_avg * 100:.1f}%",
                    f"• 전체 적중: {basketball_stats.single_hits}회",
                ])

            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━",
                "_프로토 AI 분석 시스템_"
            ])

            message = "\n".join(lines)
            await self.notifier.send_message(message)

            logger.info("✅ 주간 요약 리포트 전송 완료!")

        except Exception as e:
            logger.error(f"❌ 주간 요약 실패: {e}")
            import traceback
            traceback.print_exc()

    async def send_daily_stats(self):
        """
        일일 상태 리포트 전송

        스케줄: 매일 21:00
        """
        logger.info("\n" + "=" * 60)
        logger.info("📊 일일 상태 리포트")
        logger.info(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        try:
            # 오늘 처리한 작업 확인
            all_soccer = prediction_tracker.get_all_rounds("soccer_wdl")
            all_basketball = prediction_tracker.get_all_rounds("basketball_w5l")

            message = (
                f"📊 *일일 상태 리포트*\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
                f"⚽ 축구: {len(all_soccer)}회차 예측\n"
                f"🏀 농구: {len(all_basketball)}회차 예측\n\n"
                f"✅ 시스템 정상 가동 중"
            )

            await self.notifier.send_message(message)
            logger.info("✅ 일일 상태 리포트 전송 완료!")

        except Exception as e:
            logger.error(f"❌ 일일 상태 리포트 실패: {e}")

    # ==================== 스케줄 설정 ====================

    def setup_schedules(self):
        """모든 스케줄 작업 설정"""
        logger.info("⚙️ 스케줄 설정 중...")

        # 1. 새 회차 체크 및 분석 (6시간마다)
        self.scheduler.add_job(
            self.check_new_rounds_and_analyze,
            trigger=IntervalTrigger(hours=6),
            id='check_new_rounds',
            name='새 회차 체크 및 분석',
            replace_existing=True,
            max_instances=1,
        )
        logger.info("  ✅ 새 회차 체크: 6시간마다")

        # 2. 결과 수집 및 리포트 (매일 06:00)
        self.scheduler.add_job(
            self.collect_results_and_report,
            trigger=CronTrigger(hour=6, minute=0, timezone='Asia/Seoul'),
            id='collect_results',
            name='결과 수집 및 리포트',
            replace_existing=True,
            max_instances=1,
        )
        logger.info("  ✅ 결과 수집: 매일 06:00")

        # 3. 주간 요약 (매주 월요일 09:00)
        self.scheduler.add_job(
            self.send_weekly_summary,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0, timezone='Asia/Seoul'),
            id='weekly_summary',
            name='주간 요약 리포트',
            replace_existing=True,
            max_instances=1,
        )
        logger.info("  ✅ 주간 요약: 매주 월요일 09:00")

        # 4. 일일 상태 리포트 (매일 21:00)
        self.scheduler.add_job(
            self.send_daily_stats,
            trigger=CronTrigger(hour=21, minute=0, timezone='Asia/Seoul'),
            id='daily_stats',
            name='일일 상태 리포트',
            replace_existing=True,
            max_instances=1,
        )
        logger.info("  ✅ 일일 상태: 매일 21:00")

        logger.info("✅ 스케줄 설정 완료!")

    # ==================== 제어 메서드 ====================

    def start(self):
        """스케줄러 시작"""
        logger.info("\n" + "=" * 60)
        logger.info("🚀 스케줄러 시작")
        logger.info("=" * 60)

        self.setup_schedules()
        self.scheduler.start()

        logger.info("\n📋 등록된 작업:")
        for job in self.scheduler.get_jobs():
            logger.info(f"  - {job.name}: {job.trigger}")

        logger.info("\n✅ 스케줄러 가동 중...")
        logger.info("   (Ctrl+C로 종료)")

    def stop(self):
        """스케줄러 종료"""
        logger.info("⏹️ 스케줄러 종료 중...")
        self.scheduler.shutdown()
        logger.info("✅ 스케줄러 종료 완료")

    async def run_now(self, job_id: str):
        """특정 작업 즉시 실행"""
        job = self.scheduler.get_job(job_id)

        if not job:
            logger.error(f"❌ 작업 없음: {job_id}")
            return

        logger.info(f"▶️ 즉시 실행: {job.name}")
        await job.func()

    def get_status(self) -> Dict[str, Any]:
        """스케줄러 상태 반환"""
        jobs = self.scheduler.get_jobs()

        return {
            "running": self.scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in jobs
            ],
            "last_processed": self.last_processed,
        }


# 전역 인스턴스
scheduler_service = SchedulerService()
