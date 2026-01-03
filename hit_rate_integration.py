#!/usr/bin/env python3
"""
적중률 추적 통합 스크립트

핵심 기능:
1. 미수집 회차 자동 검색
2. 경기 결과 자동 수집
3. 적중률 리포트 생성
4. 텔레그램 자동 전송

사용법:
    python hit_rate_integration.py                  # 전체 (축구+농구)
    python hit_rate_integration.py --soccer         # 축구만
    python hit_rate_integration.py --basketball     # 농구만
    python hit_rate_integration.py --test           # 테스트 모드 (전송 안함)
    python hit_rate_integration.py --round 152      # 특정 회차
"""

import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List

from dotenv import load_dotenv
load_dotenv()

from src.services.result_collector import result_collector
from src.services.hit_rate_reporter import hit_rate_reporter
from src.services.prediction_tracker import prediction_tracker
from src.services.telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HitRateIntegration:
    """적중률 추적 통합 시스템"""

    def __init__(self):
        self.notifier = TelegramNotifier()

    async def collect_pending_results(
        self,
        game_type: str = "soccer_wdl",
        test_mode: bool = False
    ) -> Dict[int, bool]:
        """
        미수집 회차 결과 수집 및 리포트 전송

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"
            test_mode: 텔레그램 전송 여부

        Returns:
            Dict[round_num, success]
        """
        game_name = "축구 승무패" if game_type == "soccer_wdl" else "농구 승5패"
        logger.info(f"{'⚽' if game_type == 'soccer_wdl' else '🏀'} {game_name} 미수집 회차 검색 중...")

        # 미수집 회차 찾기
        pending_rounds = await result_collector.check_pending_rounds(game_type)

        if not pending_rounds:
            logger.info(f"✅ 미수집 회차 없음")
            return {}

        logger.info(f"📋 미수집 회차 {len(pending_rounds)}개: {pending_rounds[:10]}")

        # 각 회차 결과 수집
        results = {}
        for round_num in pending_rounds:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 {round_num}회차 결과 수집 중...")
            logger.info(f"{'='*60}")

            try:
                # 결과 수집
                round_result = await result_collector.collect_round_results(
                    round_num, game_type
                )

                if not round_result:
                    logger.warning(f"⚠️ {round_num}회차 결과 수집 실패 (데이터 없음)")
                    results[round_num] = False
                    await asyncio.sleep(1)
                    continue

                # 리포트 생성
                report = hit_rate_reporter.generate_report(round_num, game_type)

                if not report:
                    logger.warning(f"⚠️ {round_num}회차 리포트 생성 실패")
                    results[round_num] = False
                    await asyncio.sleep(1)
                    continue

                # 텔레그램 전송
                message = hit_rate_reporter.format_telegram_message(report)

                if test_mode:
                    print("\n" + "=" * 60)
                    print("📱 테스트 모드 - 전송하지 않음")
                    print("=" * 60)
                    print(message)
                    print("=" * 60)
                    results[round_num] = True
                else:
                    success = await self.notifier.send_message(message)
                    results[round_num] = success

                    if success:
                        logger.info(f"✅ {round_num}회차 리포트 전송 완료!")
                    else:
                        logger.error(f"❌ {round_num}회차 텔레그램 전송 실패")

                # API 호출 간격
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"❌ {round_num}회차 처리 실패: {e}")
                import traceback
                traceback.print_exc()
                results[round_num] = False
                await asyncio.sleep(2)

        return results

    async def collect_specific_round(
        self,
        round_number: int,
        game_type: str = "soccer_wdl",
        test_mode: bool = False
    ) -> bool:
        """
        특정 회차 결과 수집 및 리포트 전송

        Args:
            round_number: 회차 번호
            game_type: "soccer_wdl" | "basketball_w5l"
            test_mode: 텔레그램 전송 여부

        Returns:
            bool: 성공 여부
        """
        game_name = "축구 승무패" if game_type == "soccer_wdl" else "농구 승5패"
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 {game_name} {round_number}회차 결과 수집")
        logger.info(f"{'='*60}")

        try:
            # 결과 수집
            round_result = await result_collector.collect_round_results(
                round_number, game_type
            )

            if not round_result:
                logger.warning(f"⚠️ {round_number}회차 결과 없음")
                return False

            # 리포트 생성
            report = hit_rate_reporter.generate_report(round_number, game_type)

            if not report:
                logger.warning(f"⚠️ {round_number}회차 리포트 생성 실패")
                return False

            # 요약 출력
            logger.info(f"\n📊 적중률: {report.hit_rate * 100:.1f}% ({report.correct_predictions}/{report.total_games})")
            if report.single_hit:
                logger.info(f"🎉 전체 적중!")

            # 텔레그램 전송
            message = hit_rate_reporter.format_telegram_message(report)

            if test_mode:
                print("\n" + "=" * 60)
                print("📱 테스트 모드 - 전송하지 않음")
                print("=" * 60)
                print(message)
                print("=" * 60)
                return True

            success = await self.notifier.send_message(message)

            if success:
                logger.info(f"✅ {round_number}회차 리포트 전송 완료!")
            else:
                logger.error(f"❌ 텔레그램 전송 실패")

            return success

        except Exception as e:
            logger.error(f"❌ {round_number}회차 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def show_cumulative_stats(
        self,
        game_type: str = "soccer_wdl",
        send_to_telegram: bool = False
    ):
        """
        누적 통계 출력 및 전송

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"
            send_to_telegram: 텔레그램 전송 여부
        """
        stats = prediction_tracker.get_cumulative_stats(game_type)

        if not stats:
            logger.warning(f"누적 통계 없음 ({game_type})")
            return

        # 콘솔 출력
        game_name = "축구 승무패" if game_type == "soccer_wdl" else "농구 승5패"
        print("\n" + "=" * 60)
        print(f"📊 {game_name} 누적 통계")
        print("=" * 60)
        print(f"총 회차: {stats.total_rounds} (완료: {stats.completed_rounds})")
        print(f"평균 적중률: {stats.avg_hit_rate * 100:.1f}%")
        print(f"최고: {stats.best_hit_rate * 100:.1f}% ({stats.best_round}회차)")
        print(f"최저: {stats.worst_hit_rate * 100:.1f}% ({stats.worst_round}회차)")
        print(f"전체 적중: {stats.single_hits}회")
        print(f"\n최근 트렌드:")
        print(f"  - 5회차 평균: {stats.recent_5_avg * 100:.1f}%")
        print(f"  - 10회차 평균: {stats.recent_10_avg * 100:.1f}%")
        print("=" * 60)

        # 텔레그램 전송
        if send_to_telegram:
            message = hit_rate_reporter.format_cumulative_summary(stats)
            success = await self.notifier.send_message(message)

            if success:
                logger.info("✅ 누적 통계 전송 완료!")
            else:
                logger.error("❌ 텔레그램 전송 실패")


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="적중률 추적 통합 시스템"
    )
    parser.add_argument("--soccer", action="store_true", help="축구 승무패만")
    parser.add_argument("--basketball", action="store_true", help="농구 승5패만")
    parser.add_argument("--test", action="store_true", help="테스트 모드 (전송 안함)")
    parser.add_argument("--round", type=int, help="특정 회차 번호")
    parser.add_argument("--stats", action="store_true", help="누적 통계만 출력")

    args = parser.parse_args()

    print("=" * 60)
    print("🎯 적중률 추적 통합 시스템")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    integration = HitRateIntegration()

    try:
        # 누적 통계 출력
        if args.stats:
            if args.soccer or not args.basketball:
                await integration.show_cumulative_stats("soccer_wdl")

            if args.basketball or not args.soccer:
                await integration.show_cumulative_stats("basketball_w5l")

            return

        # 특정 회차 수집
        if args.round:
            if args.soccer or not args.basketball:
                await integration.collect_specific_round(
                    args.round, "soccer_wdl", args.test
                )
                await asyncio.sleep(2)

            if args.basketball or not args.soccer:
                await integration.collect_specific_round(
                    args.round, "basketball_w5l", args.test
                )

            return

        # 미수집 회차 전체 수집
        if args.soccer:
            results = await integration.collect_pending_results("soccer_wdl", args.test)
            print(f"\n⚽ 축구 승무패 처리 결과:")
            print(f"  성공: {sum(results.values())}회차")
            print(f"  실패: {len(results) - sum(results.values())}회차")

        elif args.basketball:
            results = await integration.collect_pending_results("basketball_w5l", args.test)
            print(f"\n🏀 농구 승5패 처리 결과:")
            print(f"  성공: {sum(results.values())}회차")
            print(f"  실패: {len(results) - sum(results.values())}회차")

        else:
            # 전체 (축구 + 농구)
            print("⚽ 축구 승무패 처리 중...")
            soccer_results = await integration.collect_pending_results("soccer_wdl", args.test)

            await asyncio.sleep(3)

            print("\n🏀 농구 승5패 처리 중...")
            basketball_results = await integration.collect_pending_results("basketball_w5l", args.test)

            print(f"\n{'='*60}")
            print("📊 전체 처리 결과:")
            print(f"{'='*60}")
            print(f"⚽ 축구: 성공 {sum(soccer_results.values())}, 실패 {len(soccer_results) - sum(soccer_results.values())}")
            print(f"🏀 농구: 성공 {sum(basketball_results.values())}, 실패 {len(basketball_results) - sum(basketball_results.values())}")
            print(f"{'='*60}")

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    print("✅ 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
