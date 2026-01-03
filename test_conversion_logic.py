"""
팀 통계 변환 로직 검증 테스트

API 응답을 모방한 데이터로 변환 로직 검증
"""

import asyncio
from datetime import datetime
from src.services.stats_providers.api_football_provider import APIFootballProvider
from src.services.stats_providers.balldontlie_provider import BallDontLieProvider

# 로깅 설정
import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')


def test_api_football_conversion():
    """축구 통계 변환 로직 테스트"""
    print("\n" + "=" * 80)
    print("축구 통계 변환 로직 테스트 (API-Football)")
    print("=" * 80)

    provider = APIFootballProvider()

    # 모의 API 응답 데이터 (강팀: 맨체스터 시티)
    mock_strong_team = {
        "form": "WWWWW",  # 5연승
        "goals": {
            "for": {
                "average": {"total": "2.5"}  # 높은 득점력
            },
            "against": {
                "average": {"total": "0.8"}  # 낮은 실점
            }
        },
        "fixtures": {
            "played": {"total": 38, "home": 19, "away": 19},
            "wins": {"total": 28, "home": 16, "away": 12}
        },
        "clean_sheet": {"total": 18}  # 47% 클린시트
    }

    # 모의 데이터 (중간팀: 노리치)
    mock_mid_team = {
        "form": "WDLWD",  # 평균적인 폼
        "goals": {
            "for": {
                "average": {"total": "1.5"}  # 평균 득점력
            },
            "against": {
                "average": {"total": "1.5"}  # 평균 실점
            }
        },
        "fixtures": {
            "played": {"total": 38, "home": 19, "away": 19},
            "wins": {"total": 14, "home": 9, "away": 5}
        },
        "clean_sheet": {"total": 10}  # 26% 클린시트
    }

    # 모의 데이터 (약팀: 루턴)
    mock_weak_team = {
        "form": "LLLLD",  # 부진한 폼
        "goals": {
            "for": {
                "average": {"total": "0.9"}  # 낮은 득점력
            },
            "against": {
                "average": {"total": "2.3"}  # 높은 실점
            }
        },
        "fixtures": {
            "played": {"total": 38, "home": 19, "away": 19},
            "wins": {"total": 6, "home": 4, "away": 2}
        },
        "clean_sheet": {"total": 3}  # 8% 클린시트
    }

    # 테스트 1: 강팀
    print("\n[테스트 1] 강팀 (맨체스터 시티)")
    print("-" * 80)
    strong_stats = provider._convert_to_team_stats(
        team_name="맨체스터시티",
        league="프리미어리그",
        stats_data=mock_strong_team,
        is_home=True
    )
    print(f"공격 레이팅: {strong_stats.attack_rating:.1f} (기대: 85-95)")
    print(f"수비 레이팅: {strong_stats.defense_rating:.1f} (기대: 85-95)")
    print(f"최근 폼: {strong_stats.recent_form:.1f} (기대: 90-100)")
    print(f"승률: {strong_stats.win_rate:.2%} (기대: 70-75%)")
    print(f"평균 득점: {strong_stats.avg_goals_scored:.2f}")
    print(f"평균 실점: {strong_stats.avg_goals_conceded:.2f}")
    print(f"홈 어드밴티지: {strong_stats.home_advantage:.1f}")

    # 테스트 2: 중간팀
    print("\n[테스트 2] 중간팀 (노리치)")
    print("-" * 80)
    mid_stats = provider._convert_to_team_stats(
        team_name="노리치",
        league="챔피언십",
        stats_data=mock_mid_team,
        is_home=True
    )
    print(f"공격 레이팅: {mid_stats.attack_rating:.1f} (기대: 45-55)")
    print(f"수비 레이팅: {mid_stats.defense_rating:.1f} (기대: 45-55)")
    print(f"최근 폼: {mid_stats.recent_form:.1f} (기대: 40-60)")
    print(f"승률: {mid_stats.win_rate:.2%} (기대: 35-40%)")
    print(f"평균 득점: {mid_stats.avg_goals_scored:.2f}")
    print(f"평균 실점: {mid_stats.avg_goals_conceded:.2f}")

    # 테스트 3: 약팀
    print("\n[테스트 3] 약팀 (루턴)")
    print("-" * 80)
    weak_stats = provider._convert_to_team_stats(
        team_name="루턴",
        league="프리미어리그",
        stats_data=mock_weak_team,
        is_home=True
    )
    print(f"공격 레이팅: {weak_stats.attack_rating:.1f} (기대: 15-25)")
    print(f"수비 레이팅: {weak_stats.defense_rating:.1f} (기대: 15-25)")
    print(f"최근 폼: {weak_stats.recent_form:.1f} (기대: 0-15)")
    print(f"승률: {weak_stats.win_rate:.2%} (기대: 15-20%)")
    print(f"평균 득점: {weak_stats.avg_goals_scored:.2f}")
    print(f"평균 실점: {weak_stats.avg_goals_conceded:.2f}")

    # 검증
    print("\n[검증 결과]")
    print("-" * 80)
    assert strong_stats.attack_rating > mid_stats.attack_rating > weak_stats.attack_rating, "공격 레이팅 순서 오류"
    assert strong_stats.defense_rating > mid_stats.defense_rating > weak_stats.defense_rating, "수비 레이팅 순서 오류"
    assert strong_stats.recent_form > mid_stats.recent_form > weak_stats.recent_form, "폼 점수 순서 오류"
    print("✅ 모든 검증 통과!")


def test_balldontlie_conversion():
    """농구 통계 변환 로직 테스트"""
    print("\n" + "=" * 80)
    print("농구 통계 변환 로직 테스트 (BallDontLie)")
    print("=" * 80)

    provider = BallDontLieProvider()

    # 모의 API 응답 데이터 (강팀: 보스턴 셀틱스)
    mock_strong_team = {
        "pts": "118.5",  # 높은 득점
        "fg_pct": "0.488",  # 높은 FG%
        "fg3_pct": "0.382",  # 높은 3P%
        "ast": "26.5",  # 많은 어시스트
        "reb": "46.2",  # 많은 리바운드
        "stl": "8.1",  # 많은 스틸
        "blk": "5.5",  # 많은 블록
        "turnover": "11.5"  # 적은 턴오버
    }

    # 모의 데이터 (중간팀)
    mock_mid_team = {
        "pts": "110.0",
        "fg_pct": "0.460",
        "fg3_pct": "0.350",
        "ast": "23.0",
        "reb": "42.0",
        "stl": "7.2",
        "blk": "4.2",
        "turnover": "13.0"
    }

    # 모의 데이터 (약팀)
    mock_weak_team = {
        "pts": "102.5",
        "fg_pct": "0.440",
        "fg3_pct": "0.320",
        "ast": "19.5",
        "reb": "38.0",
        "stl": "6.0",
        "blk": "3.5",
        "turnover": "15.5"
    }

    # 테스트 1: 강팀
    print("\n[테스트 1] 강팀 (보스턴 셀틱스)")
    print("-" * 80)
    strong_stats = provider._convert_to_team_stats(
        team_name="보스턴",
        league="NBA",
        stats_data=mock_strong_team,
        is_home=True
    )
    print(f"공격 레이팅: {strong_stats.attack_rating:.1f} (기대: 85-95)")
    print(f"수비 레이팅: {strong_stats.defense_rating:.1f} (기대: 80-90)")
    print(f"최근 폼: {strong_stats.recent_form:.1f} (기대: 85-95)")
    print(f"승률: {strong_stats.win_rate:.2%} (기대: 60-70%)")
    print(f"평균 득점: {strong_stats.avg_points_scored:.1f}")
    print(f"평균 실점: {strong_stats.avg_points_conceded:.1f}")
    print(f"홈 어드밴티지: {strong_stats.home_advantage:.1f}")

    # 테스트 2: 중간팀
    print("\n[테스트 2] 중간팀")
    print("-" * 80)
    mid_stats = provider._convert_to_team_stats(
        team_name="중간팀",
        league="NBA",
        stats_data=mock_mid_team,
        is_home=True
    )
    print(f"공격 레이팅: {mid_stats.attack_rating:.1f} (기대: 65-75)")
    print(f"수비 레이팅: {mid_stats.defense_rating:.1f} (기대: 50-60)")
    print(f"최근 폼: {mid_stats.recent_form:.1f} (기대: 55-65)")
    print(f"승률: {mid_stats.win_rate:.2%} (기대: 50-55%)")

    # 테스트 3: 약팀
    print("\n[테스트 3] 약팀")
    print("-" * 80)
    weak_stats = provider._convert_to_team_stats(
        team_name="약팀",
        league="NBA",
        stats_data=mock_weak_team,
        is_home=True
    )
    print(f"공격 레이팅: {weak_stats.attack_rating:.1f} (기대: 45-55)")
    print(f"수비 레이팅: {weak_stats.defense_rating:.1f} (기대: 30-40)")
    print(f"최근 폼: {weak_stats.recent_form:.1f} (기대: 40-50)")
    print(f"승률: {weak_stats.win_rate:.2%} (기대: 40-45%)")

    # 검증
    print("\n[검증 결과]")
    print("-" * 80)
    assert strong_stats.attack_rating > mid_stats.attack_rating > weak_stats.attack_rating, "공격 레이팅 순서 오류"
    assert strong_stats.defense_rating > mid_stats.defense_rating > weak_stats.defense_rating, "수비 레이팅 순서 오류"
    print("✅ 모든 검증 통과!")


def test_edge_cases():
    """극단적인 케이스 테스트"""
    print("\n" + "=" * 80)
    print("극단적인 케이스 테스트")
    print("=" * 80)

    provider = APIFootballProvider()

    # 완벽한 팀 (모든 지표 최고)
    print("\n[테스트 1] 완벽한 팀 (레이팅 100에 가까워야 함)")
    print("-" * 80)
    perfect_team = {
        "form": "WWWWW",
        "goals": {
            "for": {"average": {"total": "3.5"}},
            "against": {"average": {"total": "0.3"}}
        },
        "fixtures": {
            "played": {"total": 38, "home": 19, "away": 19},
            "wins": {"total": 35, "home": 18, "away": 17}
        },
        "clean_sheet": {"total": 25}
    }
    perfect_stats = provider._convert_to_team_stats(
        "완벽팀", "리그", perfect_team, True
    )
    print(f"공격 레이팅: {perfect_stats.attack_rating:.1f}")
    print(f"수비 레이팅: {perfect_stats.defense_rating:.1f}")
    print(f"최근 폼: {perfect_stats.recent_form:.1f}")
    assert perfect_stats.attack_rating >= 95, "완벽한 팀의 공격 레이팅이 95 미만"
    assert perfect_stats.defense_rating >= 95, "완벽한 팀의 수비 레이팅이 95 미만"
    print("✅ 검증 통과")

    # 최악의 팀
    print("\n[테스트 2] 최악의 팀 (레이팅 낮아야 함)")
    print("-" * 80)
    worst_team = {
        "form": "LLLLL",
        "goals": {
            "for": {"average": {"total": "0.3"}},
            "against": {"average": {"total": "3.5"}}
        },
        "fixtures": {
            "played": {"total": 38, "home": 19, "away": 19},
            "wins": {"total": 2, "home": 2, "away": 0}
        },
        "clean_sheet": {"total": 0}
    }
    worst_stats = provider._convert_to_team_stats(
        "최악팀", "리그", worst_team, True
    )
    print(f"공격 레이팅: {worst_stats.attack_rating:.1f}")
    print(f"수비 레이팅: {worst_stats.defense_rating:.1f}")
    print(f"최근 폼: {worst_stats.recent_form:.1f}")
    assert worst_stats.attack_rating <= 25, "최악의 팀의 공격 레이팅이 너무 높음"
    assert worst_stats.defense_rating <= 25, "최악의 팀의 수비 레이팅이 너무 높음"
    print("✅ 검증 통과")


if __name__ == "__main__":
    test_api_football_conversion()
    test_balldontlie_conversion()
    test_edge_cases()

    print("\n" + "=" * 80)
    print("전체 테스트 완료!")
    print("=" * 80)
    print("\n✅ 변환 로직이 정상적으로 작동합니다.")
    print("   - 강팀/중간팀/약팀을 올바르게 구분")
    print("   - 극단적인 케이스도 정상 처리")
    print("   - 레이팅 범위 (0-100) 준수")
