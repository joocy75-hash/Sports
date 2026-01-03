"""
팀 통계 서비스 테스트

실시간 팀 통계 수집 및 캐싱 테스트
"""

import asyncio
import logging
from dotenv import load_dotenv

# .env 파일 로드 (필수!)
load_dotenv()

from src.services.team_stats_service import get_team_stats_service

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_team_stats():
    """팀 통계 서비스 테스트"""

    stats_service = get_team_stats_service()

    print("=" * 80)
    print("팀 통계 서비스 테스트")
    print("=" * 80)

    # 테스트 1: 축구 팀 통계
    print("\n[테스트 1] 축구 팀 통계 조회 (맨체스터 유나이티드)")
    print("-" * 80)

    soccer_stats = await stats_service.get_team_stats(
        team_name="맨체스U",
        league="프리미어리그",
        sport_type="soccer",
        is_home=True
    )

    print(f"팀명: {soccer_stats.team_name}")
    print(f"리그: {soccer_stats.league}")
    print(f"공격 레이팅: {soccer_stats.attack_rating:.1f}")
    print(f"수비 레이팅: {soccer_stats.defense_rating:.1f}")
    print(f"최근 폼: {soccer_stats.recent_form:.1f}")
    print(f"승률: {soccer_stats.win_rate:.2%}")
    print(f"평균 득점: {soccer_stats.avg_goals_scored:.2f}")
    print(f"평균 실점: {soccer_stats.avg_goals_conceded:.2f}")
    print(f"홈 어드밴티지: {soccer_stats.home_advantage:.1f}")
    print(f"데이터 소스: {soccer_stats.source}")
    print(f"마지막 업데이트: {soccer_stats.last_updated}")

    # 테스트 2: 농구 팀 통계
    print("\n[테스트 2] 농구 팀 통계 조회 (보스턴 셀틱스)")
    print("-" * 80)

    basketball_stats = await stats_service.get_team_stats(
        team_name="보스턴",
        league="NBA",
        sport_type="basketball",
        is_home=True
    )

    print(f"팀명: {basketball_stats.team_name}")
    print(f"리그: {basketball_stats.league}")
    print(f"공격 레이팅: {basketball_stats.attack_rating:.1f}")
    print(f"수비 레이팅: {basketball_stats.defense_rating:.1f}")
    print(f"최근 폼: {basketball_stats.recent_form:.1f}")
    print(f"승률: {basketball_stats.win_rate:.2%}")
    print(f"평균 득점: {basketball_stats.avg_points_scored:.1f}")
    print(f"평균 실점: {basketball_stats.avg_points_conceded:.1f}")
    print(f"홈 어드밴티지: {basketball_stats.home_advantage:.1f}")
    print(f"데이터 소스: {basketball_stats.source}")
    print(f"마지막 업데이트: {basketball_stats.last_updated}")

    # 테스트 3: 캐시 히트 테스트
    print("\n[테스트 3] 캐시 히트 테스트 (동일 팀 재조회)")
    print("-" * 80)

    # 같은 팀 다시 조회 (캐시에서 가져올 것)
    soccer_stats_cached = await stats_service.get_team_stats(
        team_name="맨체스U",
        league="프리미어리그",
        sport_type="soccer",
        is_home=True
    )

    print(f"데이터 소스: {soccer_stats_cached.source}")
    print(f"캐시에서 조회됨: {soccer_stats_cached.last_updated == soccer_stats.last_updated}")

    # 테스트 4: 캐시 통계
    print("\n[테스트 4] 캐시 통계")
    print("-" * 80)

    cache_stats = stats_service.get_cache_stats()
    print(f"총 요청 수: {cache_stats['total_requests']}")
    print(f"메모리 캐시 히트: {cache_stats['memory_hits']}")
    print(f"파일 캐시 히트: {cache_stats['file_hits']}")
    print(f"API 호출: {cache_stats['api_calls']}")
    print(f"기본값 사용: {cache_stats['fallback_uses']}")
    print(f"캐시 적중률: {cache_stats['cache_hit_rate']:.1%}")
    print(f"메모리 캐시 크기: {cache_stats['cache_size']}개")

    # 테스트 5: 14경기 시뮬레이션 (성능 테스트)
    print("\n[테스트 5] 14경기 시뮬레이션 (성능 테스트)")
    print("-" * 80)

    import time
    test_teams = [
        ("맨체스U", "프리미어리그", "soccer"),
        ("리버풀", "프리미어리그", "soccer"),
        ("첼시", "프리미어리그", "soccer"),
        ("아스널", "프리미어리그", "soccer"),
        ("토트넘", "프리미어리그", "soccer"),
        ("맨체스C", "프리미어리그", "soccer"),
        ("뉴캐슬", "프리미어리그", "soccer"),
        ("보스턴", "NBA", "basketball"),
        ("뉴욕닉스", "NBA", "basketball"),
        ("LA레이커스", "NBA", "basketball"),
        ("골든스테이트", "NBA", "basketball"),
        ("시카고", "NBA", "basketball"),
        ("마이애미", "NBA", "basketball"),
        ("댈러스", "NBA", "basketball"),
    ]

    start_time = time.time()

    for team_name, league, sport_type in test_teams:
        stats = await stats_service.get_team_stats(
            team_name=team_name,
            league=league,
            sport_type=sport_type,
            is_home=True
        )
        print(f"  {team_name:15s} | {sport_type:10s} | 소스: {stats.source:15s} | 공격: {stats.attack_rating:5.1f}")

    elapsed_time = time.time() - start_time
    print(f"\n총 소요 시간: {elapsed_time:.2f}초")
    print(f"경기당 평균: {elapsed_time / 14:.3f}초")

    # 최종 캐시 통계
    final_cache_stats = stats_service.get_cache_stats()
    print(f"\n최종 캐시 적중률: {final_cache_stats['cache_hit_rate']:.1%}")
    print(f"총 API 호출: {final_cache_stats['api_calls']}회")

    # 리소스 정리
    await stats_service.close()

    print("\n" + "=" * 80)
    print("테스트 완료")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_team_stats())
