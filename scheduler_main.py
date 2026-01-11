#!/usr/bin/env python3
"""
프로토 14경기 자동 스케줄러 메인 프로그램

핵심 기능:
1. 6시간마다 새 회차 체크 및 예측 생성
2. 매일 06:00 결과 수집 및 리포트 전송
3. 매주 월요일 09:00 주간 요약
4. 매일 21:00 일일 상태 리포트

사용법:
    python scheduler_main.py                    # 스케줄러 시작 (데몬 모드)
    python scheduler_main.py --test-jobs        # 모든 작업 즉시 테스트
    python scheduler_main.py --run-now check    # 특정 작업 즉시 실행
    python scheduler_main.py --status           # 상태 확인
"""

import asyncio
import argparse
import signal
import sys
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from src.services.scheduler_service import scheduler_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scheduler.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class SchedulerDaemon:
    """스케줄러 데몬"""

    def __init__(self):
        self.scheduler = scheduler_service
        self.running = False

    def signal_handler(self, signum, frame):
        """시그널 핸들러 (Ctrl+C)"""
        logger.info("\n⚠️ 종료 시그널 감지...")
        self.stop()
        sys.exit(0)

    async def start_async(self):
        """스케줄러 시작 (async)"""
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        logger.info("\n" + "=" * 60)
        logger.info("🚀 프로토 14경기 자동 스케줄러")
        logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        logger.info("")

        # 스케줄러 시작 (이미 asyncio 이벤트 루프 실행 중)
        self.scheduler.start()
        self.running = True

        # 시작 알림
        try:
            await self._send_start_notification()
        except Exception as e:
            logger.error(f"시작 알림 전송 실패: {e}")

        # 메인 루프 대기 (스케줄러가 계속 실행되도록)
        try:
            while self.running:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            await self.stop_async()

    async def stop_async(self):
        """스케줄러 종료 (async)"""
        if self.running:
            self.scheduler.stop()
            self.running = False

            # 종료 알림
            try:
                await self._send_stop_notification()
            except Exception as e:
                logger.error(f"종료 알림 전송 실패: {e}")
    
    def stop(self):
        """스케줄러 종료 (동기)"""
        if self.running:
            self.scheduler.stop()
            self.running = False

    async def _send_start_notification(self):
        """시작 알림"""
        message = (
            f"🚀 *스케줄러 시작*\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"📋 *등록된 작업:*\n"
            f"• 새 회차 체크: 6시간마다\n"
            f"• 결과 수집: 매일 06:00\n"
            f"• 주간 요약: 월요일 09:00\n"
            f"• 일일 상태: 매일 21:00\n\n"
            f"✅ 시스템 가동 중"
        )

        try:
            from src.services.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier()
            await notifier.send_message(message)
        except Exception as e:
            logger.error(f"시작 알림 전송 실패: {e}")

    async def _send_stop_notification(self):
        """종료 알림"""
        message = (
            f"⏹️ *스케줄러 종료*\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"시스템이 정상적으로 종료되었습니다."
        )

        try:
            from src.services.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier()
            await notifier.send_message(message)
        except Exception as e:
            logger.error(f"종료 알림 전송 실패: {e}")


async def test_all_jobs():
    """모든 작업 즉시 테스트"""
    print("\n" + "=" * 60)
    print("🧪 모든 스케줄 작업 테스트")
    print("=" * 60)
    print()

    jobs = [
        ("check_new_rounds", "새 회차 체크 및 분석"),
        ("collect_results", "결과 수집 및 리포트"),
        ("weekly_summary", "주간 요약 리포트"),
        ("daily_stats", "일일 상태 리포트"),
    ]

    for job_id, job_name in jobs:
        print(f"\n▶️ {job_name} 실행 중...")
        print("-" * 40)

        try:
            await scheduler_service.run_now(job_id)
            print(f"✅ {job_name} 완료!")
        except Exception as e:
            print(f"❌ {job_name} 실패: {e}")
            import traceback
            traceback.print_exc()

        print()
        await asyncio.sleep(2)

    print("=" * 60)
    print("✅ 모든 작업 테스트 완료!")
    print("=" * 60)


async def run_specific_job(job_id: str):
    """특정 작업 즉시 실행"""
    job_names = {
        "check": "새 회차 체크 및 분석",
        "results": "결과 수집 및 리포트",
        "weekly": "주간 요약 리포트",
        "daily": "일일 상태 리포트",
    }

    full_job_ids = {
        "check": "check_new_rounds",
        "results": "collect_results",
        "weekly": "weekly_summary",
        "daily": "daily_stats",
    }

    if job_id not in full_job_ids:
        print(f"❌ 유효하지 않은 작업: {job_id}")
        print(f"\n사용 가능한 작업:")
        for key, name in job_names.items():
            print(f"  - {key}: {name}")
        return

    job_name = job_names[job_id]
    full_id = full_job_ids[job_id]

    print(f"\n▶️ {job_name} 실행 중...")
    print("-" * 40)

    try:
        await scheduler_service.run_now(full_id)
        print(f"✅ {job_name} 완료!")
    except Exception as e:
        print(f"❌ {job_name} 실패: {e}")
        import traceback
        traceback.print_exc()


def show_status():
    """스케줄러 상태 출력"""
    print("\n" + "=" * 60)
    print("📊 스케줄러 상태")
    print("=" * 60)
    print()

    status = scheduler_service.get_status()

    print(f"상태: {'🟢 실행 중' if status['running'] else '🔴 중지됨'}")
    print()

    print("📋 등록된 작업:")
    for job in status['jobs']:
        next_run = job['next_run']
        if next_run:
            next_run_str = datetime.fromisoformat(next_run).strftime('%Y-%m-%d %H:%M:%S')
        else:
            next_run_str = "없음"

        print(f"  • {job['name']}")
        print(f"    다음 실행: {next_run_str}")

    print()
    print("📊 마지막 처리:")
    last = status['last_processed']
    print(f"  • 축구: {last.get('soccer_wdl', 0)}회차")
    print(f"  • 농구: {last.get('basketball_w5l', 0)}회차")

    if last.get('last_result_check'):
        check_time = datetime.fromisoformat(last['last_result_check']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  • 마지막 결과 수집: {check_time}")

    print()
    print("=" * 60)


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="프로토 14경기 자동 스케줄러"
    )
    parser.add_argument("--test-jobs", action="store_true", help="모든 작업 즉시 테스트")
    parser.add_argument("--run-now", type=str, help="특정 작업 즉시 실행 (check|results|weekly|daily)")
    parser.add_argument("--status", action="store_true", help="스케줄러 상태 확인")

    args = parser.parse_args()

    # 상태 확인
    if args.status:
        show_status()
        return

    # 특정 작업 실행
    if args.run_now:
        await run_specific_job(args.run_now)
        return

    # 모든 작업 테스트
    if args.test_jobs:
        await test_all_jobs()
        return

    # 데몬 모드 (기본) - AsyncIOScheduler는 asyncio 이벤트 루프 필요
    daemon = SchedulerDaemon()
    await daemon.start_async()


if __name__ == "__main__":
    asyncio.run(main())
