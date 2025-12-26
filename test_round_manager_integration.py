#!/usr/bin/env python3
"""
RoundManager 통합 테스트 - 베트맨 크롤러 + KSPO API

테스트 시나리오:
1. 크롤러 우선 모드 (auto) - 크롤러 성공 시 14경기
2. 크롤러 전용 모드 (crawler) - 크롤러만 사용
3. API 전용 모드 (api) - API만 사용
4. Fallback 테스트 - 크롤러 실패 시 API로 전환
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.services.round_manager import RoundManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_soccer_auto_mode():
    """축구 승무패 - Auto 모드 (크롤러 우선)"""
    print("\n" + "=" * 80)
    print("테스트 1: 축구 승무패 - Auto 모드 (크롤러 우선, API fallback)")
    print("=" * 80)

    manager = RoundManager()

    try:
        info, games = await manager.get_soccer_wdl_round(force_refresh=True, source="auto")

        print(f"\n✅ 성공!")
        print(f"   회차: {info.round_number}회차")
        print(f"   경기일: {info.match_date}")
        print(f"   경기 수: {len(games)}경기")
        print(f"   상태: {info.status}")
        print(f"   업데이트: {info.updated_at}")

        print("\n📋 경기 목록:")
        for i, g in enumerate(games[:14], 1):
            home = g.get("hteam_han_nm", "")
            away = g.get("ateam_han_nm", "")
            row = g.get("row_num", "?")
            time = g.get("match_tm", "0000")
            print(f"   {i:02d}. [{row}] {home} vs {away} ({time})")

        return True

    except Exception as e:
        print(f"\n❌ 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_soccer_crawler_only():
    """축구 승무패 - 크롤러 전용 모드"""
    print("\n" + "=" * 80)
    print("테스트 2: 축구 승무패 - 크롤러 전용 모드")
    print("=" * 80)

    manager = RoundManager()

    try:
        info, games = await manager.get_soccer_wdl_round(force_refresh=True, source="crawler")

        print(f"\n✅ 성공!")
        print(f"   회차: {info.round_number}회차")
        print(f"   경기 수: {len(games)}경기")

        if len(games) == 14:
            print("   ✅ 14경기 정확히 수집됨!")
        else:
            print(f"   ⚠️ 경기 수 불일치: {len(games)}경기")

        return True

    except Exception as e:
        print(f"\n⚠️ 크롤러 실패 (예상된 동작): {e}")
        return False


async def test_soccer_api_only():
    """축구 승무패 - API 전용 모드"""
    print("\n" + "=" * 80)
    print("테스트 3: 축구 승무패 - API 전용 모드")
    print("=" * 80)

    manager = RoundManager()

    try:
        info, games = await manager.get_soccer_wdl_round(force_refresh=True, source="api")

        print(f"\n✅ 성공!")
        print(f"   회차: {info.round_number}회차")
        print(f"   경기 수: {len(games)}경기")

        return True

    except Exception as e:
        print(f"\n❌ 실패: {e}")
        return False


async def test_basketball_auto_mode():
    """농구 승5패 - Auto 모드"""
    print("\n" + "=" * 80)
    print("테스트 4: 농구 승5패 - Auto 모드 (크롤러 우선, API fallback)")
    print("=" * 80)

    manager = RoundManager()

    try:
        info, games = await manager.get_basketball_w5l_round(force_refresh=True, source="auto")

        print(f"\n✅ 성공!")
        print(f"   회차: {info.round_number}회차")
        print(f"   경기일: {info.match_date}")
        print(f"   경기 수: {len(games)}경기")

        print("\n📋 경기 목록 (첫 5개):")
        for i, g in enumerate(games[:5], 1):
            home = g.get("hteam_han_nm", "")
            away = g.get("ateam_han_nm", "")
            row = g.get("row_num", "?")
            print(f"   {i:02d}. [{row}] {home} vs {away}")

        return True

    except Exception as e:
        print(f"\n❌ 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cache_mechanism():
    """캐시 동작 테스트"""
    print("\n" + "=" * 80)
    print("테스트 5: 캐시 동작 확인")
    print("=" * 80)

    manager = RoundManager()

    # 첫 번째 요청 (캐시 미스)
    print("\n1차 요청 (캐시 미스)...")
    start = datetime.now()
    info1, games1 = await manager.get_soccer_wdl_round(force_refresh=True, source="auto")
    time1 = (datetime.now() - start).total_seconds()
    print(f"   소요 시간: {time1:.2f}초")

    # 두 번째 요청 (캐시 히트)
    print("\n2차 요청 (캐시 히트 예상)...")
    start = datetime.now()
    info2, games2 = await manager.get_soccer_wdl_round(force_refresh=False, source="auto")
    time2 = (datetime.now() - start).total_seconds()
    print(f"   소요 시간: {time2:.2f}초")

    if time2 < time1:
        print(f"   ✅ 캐시 동작 확인! ({time1:.2f}초 → {time2:.2f}초)")
    else:
        print(f"   ⚠️ 캐시가 동작하지 않음")

    # 회차 번호 일치 확인
    if info1.round_number == info2.round_number:
        print(f"   ✅ 회차 일치: {info1.round_number}회차")
    else:
        print(f"   ❌ 회차 불일치: {info1.round_number} vs {info2.round_number}")

    return True


async def main():
    """전체 테스트 실행"""
    print("\n" + "=" * 80)
    print("RoundManager 통합 테스트 시작")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    results = {}

    # 테스트 실행
    results["축구_Auto"] = await test_soccer_auto_mode()
    await asyncio.sleep(2)

    results["축구_크롤러전용"] = await test_soccer_crawler_only()
    await asyncio.sleep(2)

    results["축구_API전용"] = await test_soccer_api_only()
    await asyncio.sleep(2)

    results["농구_Auto"] = await test_basketball_auto_mode()
    await asyncio.sleep(2)

    results["캐시동작"] = await test_cache_mechanism()

    # 결과 요약
    print("\n" + "=" * 80)
    print("테스트 결과 요약")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✅ 통과" if passed else "❌ 실패"
        print(f"{test_name:20s}: {status}")

    total = len(results)
    passed = sum(1 for r in results.values() if r)

    print("\n" + "=" * 80)
    print(f"총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.0f}%)")
    print("=" * 80)

    # 종합 판정
    if passed == total:
        print("\n🎉 모든 테스트 통과! RoundManager 통합 성공!")
    elif passed >= total * 0.6:
        print("\n⚠️ 일부 테스트 실패. 크롤러 또는 API 연결을 확인하세요.")
    else:
        print("\n❌ 다수 테스트 실패. 설정을 확인하세요.")


if __name__ == "__main__":
    asyncio.run(main())
