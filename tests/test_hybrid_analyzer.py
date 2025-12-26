#!/usr/bin/env python3
"""
HybridAnalyzer 통합 테스트
LLM AI + LightGBM ML + 통계 모델 통합 테스트
"""

import asyncio
import sys
import logging
from datetime import datetime

# 프로젝트 경로 추가
sys.path.insert(0, "/Users/mr.joo/Desktop/스포츠분석")

from src.services.hybrid_analyzer import (
    HybridAnalyzer,
    get_hybrid_analyzer,
    HybridResult,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_hybrid_analyzer_init():
    """HybridAnalyzer 초기화 테스트"""
    print("\n" + "=" * 60)
    print("📋 테스트 1: HybridAnalyzer 초기화")
    print("=" * 60)

    try:
        analyzer = HybridAnalyzer()
        print("✅ HybridAnalyzer 초기화 성공")

        # 컴포넌트 확인
        status = analyzer.get_status()
        print(
            f"   - AI Orchestrator: {'✅ 활성' if status['ai_orchestrator'] else '❌ 비활성'}"
        )
        print(
            f"   - ML Predictor: {'✅ 활성' if status['ml_predictor'] else '❌ 비활성'}"
        )
        print(
            f"   - Ensemble Model: {'✅ 활성' if status['ensemble_model'] else '❌ 비활성'}"
        )

        return True
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_hybrid_analyzer_singleton():
    """싱글톤 패턴 테스트"""
    print("\n" + "=" * 60)
    print("📋 테스트 2: 싱글톤 패턴 검증")
    print("=" * 60)

    try:
        # 싱글톤 리셋
        import src.services.hybrid_analyzer as ha_module

        ha_module._hybrid_analyzer = None

        analyzer1 = get_hybrid_analyzer()
        analyzer2 = get_hybrid_analyzer()

        if analyzer1 is analyzer2:
            print("✅ 싱글톤 패턴 정상 작동")
            return True
        else:
            print("❌ 싱글톤 패턴 실패 - 다른 인스턴스 반환됨")
            return False
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False


async def test_hybrid_analysis():
    """통합 분석 테스트"""
    print("\n" + "=" * 60)
    print("📋 테스트 3: 하이브리드 분석 실행")
    print("=" * 60)

    try:
        analyzer = get_hybrid_analyzer()

        # 테스트 데이터
        match_context = {
            "match_id": 12345,
            "home_team": "멤피스그리즐리스",
            "away_team": "워싱턴위저즈",
            "sport_type": "basketball",
            "league": "NBA",
            "match_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "odds": {"home": 1.40, "draw": 15.0, "away": 2.80},
        }

        team_stats = {
            "home": {
                "team_name": "멤피스그리즐리스",
                "wins": 18,
                "losses": 10,
                "avg_gf": 112.5,
                "avg_ga": 108.2,
                "home_record": "10-4",
                "form": "WWLWW",
            },
            "away": {
                "team_name": "워싱턴위저즈",
                "wins": 6,
                "losses": 22,
                "avg_gf": 105.8,
                "avg_ga": 118.4,
                "away_record": "2-12",
                "form": "LLLWL",
            },
        }

        h2h_data = {
            "home_wins": 4,
            "away_wins": 1,
            "draws": 0,
            "home_goals": 115,
            "away_goals": 107,
        }

        print(
            f"   분석 경기: {match_context['home_team']} vs {match_context['away_team']}"
        )
        print(f"   종목: {match_context['sport_type']}")

        # 분석 실행 (시간 측정)
        start_time = datetime.now()
        result = await analyzer.analyze(
            match_context=match_context, team_stats=team_stats, h2h_data=h2h_data
        )
        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n   ⏱️ 분석 소요 시간: {elapsed:.2f}초")
        print(f"\n📊 분석 결과:")
        print(f"   - 홈 승률: {result.home_prob:.1%}")
        print(f"   - 무승부: {result.draw_prob:.1%}")
        print(f"   - 원정 승률: {result.away_prob:.1%}")
        print(f"   - 신뢰도: {result.overall_confidence:.1%}")
        print(f"   - 합의도: {result.consensus_score:.1%}")
        print(f"   - 최종 추천: {result.predicted_outcome_kr}")

        print(f"\n📈 모델별 상태:")
        print(
            f"   - LLM AI: {'✅ 사용됨' if result.llm_prediction.get('available') else '❌ 미사용'}"
        )
        print(
            f"   - ML: {'✅ 사용됨' if result.ml_prediction.get('available') else '❌ 미사용'}"
        )
        print(
            f"   - 통계: {'✅ 사용됨' if result.statistical_prediction.get('available') else '❌ 미사용'}"
        )

        return True

    except Exception as e:
        print(f"❌ 분석 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_statistical_only():
    """통계 모델 분석 테스트"""
    print("\n" + "=" * 60)
    print("📋 테스트 4: 통계 모델 분석 테스트")
    print("=" * 60)

    try:
        analyzer = get_hybrid_analyzer()

        # 축구 테스트 데이터
        match_context = {
            "match_id": 67890,
            "home_team": "Chelsea",
            "away_team": "Arsenal",
            "sport_type": "soccer",
            "league": "Premier League",
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        team_stats = {
            "home": {
                "team_name": "Chelsea",
                "wins": 10,
                "draws": 5,
                "losses": 3,
                "avg_gf": 1.56,
                "avg_ga": 0.83,
                "elo": 1650,
                "form": "WDWWL",
            },
            "away": {
                "team_name": "Arsenal",
                "wins": 12,
                "draws": 4,
                "losses": 2,
                "avg_gf": 1.78,
                "avg_ga": 0.67,
                "elo": 1720,
                "form": "WWWWW",
            },
        }

        h2h_data = {
            "home_wins": 3,
            "away_wins": 5,
            "draws": 2,
            "home_goals": 12,
            "away_goals": 15,
        }

        print(
            f"   분석 경기: {match_context['home_team']} vs {match_context['away_team']}"
        )

        # 분석 실행
        result = await analyzer.analyze(
            match_context=match_context, team_stats=team_stats, h2h_data=h2h_data
        )

        print(f"\n📊 분석 결과:")
        print(f"   - 홈 승률: {result.home_prob:.1%}")
        print(f"   - 무승부: {result.draw_prob:.1%}")
        print(f"   - 원정 승률: {result.away_prob:.1%}")
        print(f"   - 신뢰도: {result.overall_confidence:.1%}")
        print(f"   - 예측: {result.predicted_outcome_kr}")

        return True

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "=" * 70)
    print("🔬 HybridAnalyzer 통합 테스트 시작")
    print("=" * 70)
    print(f"   시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # 동기 테스트
    results["초기화 테스트"] = test_hybrid_analyzer_init()
    results["싱글톤 테스트"] = test_hybrid_analyzer_singleton()

    # 비동기 테스트
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results["하이브리드 분석"] = loop.run_until_complete(test_hybrid_analysis())
    results["통계 모델 분석"] = loop.run_until_complete(test_statistical_only())
    loop.close()

    # 결과 요약
    print("\n" + "=" * 70)
    print("📊 테스트 결과 요약")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    failed = len(results) - passed

    for test_name, result in results.items():
        status = "✅ 통과" if result else "❌ 실패"
        print(f"   {status}: {test_name}")

    print(f"\n   총 테스트: {len(results)}")
    print(f"   통과: {passed}")
    print(f"   실패: {failed}")

    if failed == 0:
        print("\n🎉 모든 테스트 통과!")
        return True
    else:
        print(f"\n⚠️  {failed}개의 테스트가 실패했습니다.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
