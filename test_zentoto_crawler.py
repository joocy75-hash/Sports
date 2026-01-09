#!/usr/bin/env python3
"""
젠토토 크롤러 테스트 스크립트

테스트 항목:
1. 축구 승무패 14경기 크롤링
2. 농구 승5패 14경기 크롤링
3. 다음 회차 미리 확보
4. RoundManager 통합 테스트 (젠토토 → 베트맨 → API)
"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)


async def test_zentoto_crawler():
    """젠토토 크롤러 단독 테스트"""
    from src.services.zentoto_crawler import ZentotoCrawler

    print("=" * 70)
    print("🎯 젠토토 크롤러 테스트")
    print("=" * 70)

    async with ZentotoCrawler(headless=True) as crawler:
        # 1. 축구 승무패
        print("\n[1] 축구 승무패 크롤링")
        print("-" * 50)
        try:
            info, games = await crawler.get_soccer_wdl_games(force_refresh=True)
            print(f"  ✅ 회차: {info.year}년 {info.round_number}회차")
            print(f"  ✅ 상태: {info.status}")
            print(f"  ✅ 경기 수: {len(games)}경기")

            if len(games) == 14:
                print(f"  ✅ 14경기 수집 성공!")
            else:
                print(f"  ⚠️ 경기 수 불일치: {len(games)}/14")

            print("\n  경기 목록:")
            for g in games[:5]:  # 처음 5경기만 출력
                print(f"    {g.game_number:02d}. {g.home_team} vs {g.away_team}")
            if len(games) > 5:
                print(f"    ... (총 {len(games)}경기)")

        except Exception as e:
            print(f"  ❌ 오류: {e}")

        # 2. 농구 승5패
        print("\n[2] 농구 승5패 크롤링")
        print("-" * 50)
        try:
            info, games = await crawler.get_basketball_w5l_games(force_refresh=True)
            print(f"  ✅ 회차: {info.year}년 {info.round_number}회차")
            print(f"  ✅ 상태: {info.status}")
            print(f"  ✅ 경기 수: {len(games)}경기")

            if len(games) == 14:
                print(f"  ✅ 14경기 수집 성공!")
            else:
                print(f"  ⚠️ 경기 수 불일치: {len(games)}/14")

            print("\n  경기 목록:")
            for g in games[:5]:
                print(f"    {g.game_number:02d}. {g.home_team} vs {g.away_team}")
            if len(games) > 5:
                print(f"    ... (총 {len(games)}경기)")

        except Exception as e:
            print(f"  ❌ 오류: {e}")

        # 3. 다음 회차 미리 확보
        print("\n[3] 다음 회차 미리 확보 (축구)")
        print("-" * 50)
        try:
            result = await crawler.get_next_round_games("soccer_wdl")
            if result:
                info, games = result
                print(f"  ✅ 다음 회차 발견: {info.year}년 {info.round_number}회차")
                print(f"  ✅ 경기 수: {len(games)}경기")
            else:
                print("  ℹ️ 다음 회차가 아직 등록되지 않음")
        except Exception as e:
            print(f"  ❌ 오류: {e}")


async def test_round_manager_integration():
    """RoundManager 통합 테스트 (젠토토 우선)"""
    from src.services.round_manager import RoundManager

    print("\n")
    print("=" * 70)
    print("🔄 RoundManager 통합 테스트 (젠토토 → 베트맨 → API)")
    print("=" * 70)

    manager = RoundManager()

    # 1. 축구 승무패 (auto 모드)
    print("\n[1] 축구 승무패 - auto 모드")
    print("-" * 50)
    try:
        info, games = await manager.get_soccer_wdl_round(force_refresh=True)
        source = games[0].get("source", "unknown") if games else "unknown"
        print(f"  ✅ 회차: {info.round_number}회차")
        print(f"  ✅ 경기 수: {len(games)}경기")
        print(f"  ✅ 데이터 소스: {source}")

        if len(games) >= 14:
            print("  ✅ 14경기 수집 성공!")

    except Exception as e:
        print(f"  ❌ 오류: {e}")

    # 2. 농구 승5패 (auto 모드)
    print("\n[2] 농구 승5패 - auto 모드")
    print("-" * 50)
    try:
        info, games = await manager.get_basketball_w5l_round(force_refresh=True)
        source = games[0].get("source", "unknown") if games else "unknown"
        print(f"  ✅ 회차: {info.round_number}회차")
        print(f"  ✅ 경기 수: {len(games)}경기")
        print(f"  ✅ 데이터 소스: {source}")

        if len(games) >= 14:
            print("  ✅ 14경기 수집 성공!")

    except Exception as e:
        print(f"  ❌ 오류: {e}")

    # 3. 다음 회차 미리 확보
    print("\n[3] 다음 회차 미리 확보")
    print("-" * 50)
    try:
        result = await manager.check_and_prefetch("soccer_wdl")

        if result["current"]:
            info, _ = result["current"]
            print(f"  ✅ 현재 회차: {info.round_number}회차")

        if result["next"]:
            info, games = result["next"]
            print(f"  ✅ 다음 회차: {info.round_number}회차 ({len(games)}경기)")
        else:
            print("  ℹ️ 다음 회차 아직 미등록")

    except Exception as e:
        print(f"  ❌ 오류: {e}")


async def test_source_comparison():
    """데이터 소스 비교 테스트"""
    from src.services.round_manager import RoundManager

    print("\n")
    print("=" * 70)
    print("📊 데이터 소스 비교 (젠토토 vs 베트맨 vs API)")
    print("=" * 70)

    manager = RoundManager()

    sources = ["zentoto", "crawler", "api"]
    results = {}

    for source in sources:
        print(f"\n[{source.upper()}] 축구 승무패")
        print("-" * 50)
        try:
            info, games = await manager.get_soccer_wdl_round(force_refresh=True, source=source)
            results[source] = {
                "round": info.round_number,
                "games": len(games),
                "status": "success"
            }
            print(f"  ✅ 회차: {info.round_number}회차")
            print(f"  ✅ 경기 수: {len(games)}경기")

            # 처음 3경기 출력
            for g in games[:3]:
                home = g.get("hteam_han_nm", "")
                away = g.get("ateam_han_nm", "")
                print(f"    - {home} vs {away}")

        except Exception as e:
            results[source] = {"status": "failed", "error": str(e)}
            print(f"  ❌ 실패: {e}")

    # 결과 비교
    print("\n" + "=" * 70)
    print("📋 결과 요약")
    print("=" * 70)
    print(f"{'소스':<12} {'상태':<10} {'회차':<10} {'경기 수':<10}")
    print("-" * 50)
    for source, result in results.items():
        if result["status"] == "success":
            print(f"{source:<12} ✅ 성공     {result['round']:<10} {result['games']}경기")
        else:
            print(f"{source:<12} ❌ 실패     -          -")


async def main():
    """메인 테스트 실행"""
    import argparse

    parser = argparse.ArgumentParser(description="젠토토 크롤러 테스트")
    parser.add_argument("--zentoto", action="store_true", help="젠토토 크롤러만 테스트")
    parser.add_argument("--integration", action="store_true", help="RoundManager 통합 테스트")
    parser.add_argument("--compare", action="store_true", help="데이터 소스 비교")
    parser.add_argument("--all", action="store_true", help="모든 테스트 실행")

    args = parser.parse_args()

    # 기본: 모든 테스트
    if not any([args.zentoto, args.integration, args.compare]):
        args.all = True

    if args.all or args.zentoto:
        await test_zentoto_crawler()

    if args.all or args.integration:
        await test_round_manager_integration()

    if args.all or args.compare:
        await test_source_comparison()

    print("\n")
    print("=" * 70)
    print("✅ 테스트 완료!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
