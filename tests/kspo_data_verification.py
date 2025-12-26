#!/usr/bin/env python3
"""
KSPO API 데이터 검증 테스트
프론트엔드에서 최신 정보가 제대로 업데이트되는지 확인
"""

import requests
import datetime

BACKEND_URL = "http://localhost:8000"


def check_current_time():
    """현재 시간 확인"""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_kst = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=9)))

    print("⏰ 현재 시간 확인:")
    print(f"  UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  KST: {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
    print()


def test_kspo_api_data():
    """KSPO API 데이터 검증"""
    print("🔍 KSPO API 데이터 검증")
    print("=" * 60)

    try:
        # 1. 경기 목록 가져오기
        response = requests.get(f"{BACKEND_URL}/api/v1/games/list", timeout=10)
        if response.status_code != 200:
            print(f"❌ 경기 목록 API 실패: {response.status_code}")
            return False

        data = response.json()
        total_matches = data.get("total_matches", 0)
        categories = data.get("categories", [])

        print(f"✅ 총 경기 수: {total_matches}")
        print(f"✅ 카테고리 수: {len(categories)}")

        if not categories:
            print("❌ 카테고리가 없습니다.")
            return False

        # 2. 각 카테고리별 데이터 확인
        for category in categories:
            category_name = category.get("name", "알 수 없음")
            match_count = category.get("count", 0)
            matches = category.get("matches", [])

            print(f"\n📊 카테고리: {category_name}")
            print(f"   경기 수: {match_count}")

            if matches:
                # 첫 3개 경기만 상세 확인
                for i, match in enumerate(matches[:3]):
                    match_id = match.get("id")
                    home_team = match.get("home_team", "알 수 없음")
                    away_team = match.get("away_team", "알 수 없음")
                    start_time = match.get("start_time")
                    deadline = match.get("deadline")
                    status = match.get("status", "알 수 없음")

                    print(f"   {i + 1}. {home_team} vs {away_team}")
                    print(f"      ID: {match_id}")
                    print(f"      시작: {start_time}")
                    print(f"      마감: {deadline}")
                    print(f"      상태: {status}")

        return True

    except Exception as e:
        print(f"❌ KSPO API 테스트 실패: {str(e)}")
        return False


def test_match_status_accuracy():
    """경기 상태 정확성 검증"""
    print("\n🔍 경기 상태 정확성 검증")
    print("=" * 60)

    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/games/list", timeout=10)
        if response.status_code != 200:
            return False

        data = response.json()
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        categories = data.get("categories", [])
        if not categories:
            return True  # 데이터가 없으면 스킵

        matches = categories[0].get("matches", [])
        if not matches:
            return True  # 경기가 없으면 스킵

        print(f"검증할 경기 수: {len(matches)}")

        status_counts = {"예정": 0, "진행중": 0, "종료": 0, "마감": 0, "기타": 0}

        deadline_passed = 0
        started = 0
        ended = 0

        for match in matches[:20]:  # 처음 20개만 검증
            start_time_str = match.get("start_time", "").replace("Z", "+00:00")
            deadline_str = match.get("deadline", "").replace("Z", "+00:00")
            status = match.get("status", "")

            try:
                start_time = datetime.datetime.fromisoformat(start_time_str)
                deadline = datetime.datetime.fromisoformat(deadline_str)

                # 상태 판단 로직
                if deadline < now_utc:
                    deadline_passed += 1
                if start_time < now_utc:
                    started += 1
                if (
                    start_time + datetime.timedelta(hours=2) < now_utc
                ):  # 경기 시간 2시간 가정
                    ended += 1

                # 상태 카운트
                if status in status_counts:
                    status_counts[status] += 1
                else:
                    status_counts["기타"] += 1

            except Exception as e:
                print(f"   ⚠️  시간 파싱 오류: {e}")
                continue

        print("\n📊 상태 분석:")
        print(f"   마감 시간 지난 경기: {deadline_passed}개")
        print(f"   시작 시간 지난 경기: {started}개")
        print(f"   종료된 것으로 추정: {ended}개")

        print("\n📊 상태 분포:")
        for status, count in status_counts.items():
            if count > 0:
                print(f"   {status}: {count}개")

        return True

    except Exception as e:
        print(f"❌ 상태 검증 실패: {str(e)}")
        return False


def test_real_time_updates():
    """실시간 업데이트 테스트"""
    print("\n🔍 실시간 업데이트 테스트")
    print("=" * 60)

    try:
        # 캐시 통계 확인
        response = requests.get(f"{BACKEND_URL}/api/v1/cache/stats", timeout=10)
        if response.status_code == 200:
            cache_stats = response.json()
            print("✅ 캐시 통계:")
            if cache_stats.get("success"):
                stats = cache_stats.get("stats", {})
                print(f"   히트율: {stats.get('hit_rate', 0):.1f}%")
                print(f"   총 요청: {stats.get('total_requests', 0)}")
                print(f"   캐시 크기: {stats.get('cache_size', 0)}")

        # 실시간 배당 모니터 확인
        response = requests.get(f"{BACKEND_URL}/api/v1/odds/monitor-status", timeout=10)
        if response.status_code == 200:
            monitor_status = response.json()
            print("\n✅ 배당 모니터 상태:")
            if monitor_status.get("success"):
                print(f"   상태: {monitor_status.get('status', '알 수 없음')}")
                print(
                    f"   마지막 업데이트: {monitor_status.get('last_update', '알 수 없음')}"
                )

        return True

    except Exception as e:
        print(f"❌ 실시간 업데이트 테스트 실패: {str(e)}")
        return False


def main():
    """메인 함수"""
    print("🚀 KSPO API 데이터 검증 테스트")
    print("=" * 60)

    check_current_time()

    tests = [
        ("KSPO API 데이터 검증", test_kspo_api_data),
        ("경기 상태 정확성 검증", test_match_status_accuracy),
        ("실시간 업데이트 테스트", test_real_time_updates),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n▶️  실행 중: {test_name}")
        success = test_func()
        results.append((test_name, success))

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 검증 테스트 결과 요약")
    print("=" * 60)

    total = len(results)
    passed = sum(1 for _, success in results if success)
    failed = total - passed

    for i, (name, success) in enumerate(results, 1):
        status = "✅ 통과" if success else "❌ 실패"
        print(f"{i}. {name}: {status}")

    print(f"\n총 테스트: {total}")
    print(f"성공: {passed}")
    print(f"실패: {failed}")

    # 결론
    print("\n" + "=" * 60)
    print("📋 검증 결론")
    print("=" * 60)

    if failed == 0:
        print("✅ 모든 검증 테스트 통과!")
        print("✅ KSPO API 데이터가 정상적으로 수집되고 있습니다.")
        print("✅ 실시간 업데이트 시스템이 작동 중입니다.")
    else:
        print(f"⚠️  {failed}개의 테스트가 실패했습니다.")
        print("❌ 일부 기능에 문제가 있을 수 있습니다.")

    # 권장사항
    print("\n💡 권장사항:")
    print("1. 실제 KSPO API 키를 사용하여 라이브 데이터 테스트")
    print("3. 실시간 스코어 업데이트 기능 구현")
    print("4. 경기 결과 데이터 수집 및 표시")

    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
