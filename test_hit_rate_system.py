#!/usr/bin/env python3
"""
적중률 추적 시스템 통합 테스트

테스트 항목:
1. 팀명 정규화 (team_name_normalizer)
2. 예측 저장/로드 (prediction_tracker)
3. 결과 수집 (result_collector)
4. 리포트 생성 (hit_rate_reporter)
5. 텔레그램 포맷팅
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

from src.services.team_name_normalizer import team_normalizer
from src.services.prediction_tracker import prediction_tracker
from src.services.hit_rate_reporter import hit_rate_reporter, HitRateReport


def test_team_normalizer():
    """1. 팀명 정규화 테스트"""
    print("=" * 60)
    print("1. 팀명 정규화 테스트")
    print("=" * 60)

    test_cases = [
        ("레스터C", "레스터시티"),
        ("맨체스U", "맨체스터유나이티드"),
        ("노팅엄포", "노팅엄포리스트"),
        ("울산모비스", "울산현대모비스피버스"),
        ("미네소타", "미네소타팀버울브스"),
        ("A빌라", "아스톤빌라"),
        ("크리스탈P", "크리스탈팰리스"),
    ]

    passed = 0
    for betman, api in test_cases:
        result = team_normalizer.match_team(betman, api)
        status = "✅" if result.confidence >= 0.6 else "❌"
        if result.confidence >= 0.6:
            passed += 1
        print(f"  {status} {betman:15} ↔ {api:20} → {result.method} ({result.confidence:.2f})")

    print(f"\n  결과: {passed}/{len(test_cases)} 통과")
    return passed == len(test_cases)


def test_prediction_tracker():
    """2. 예측 저장/로드 테스트"""
    print("\n" + "=" * 60)
    print("2. 예측 저장/로드 테스트")
    print("=" * 60)

    # 테스트 데이터
    test_round_info = {
        "round_number": 999,
        "deadline": (datetime.now() + timedelta(days=1)).isoformat(),
        "match_date": "2025-12-27",
    }

    test_predictions = [
        {
            "game_number": 1,
            "home_team": "레스터C",
            "away_team": "왓포드",
            "match_date": "2025-12-27",
            "match_time": "21:00",
            "predicted": "1",
            "confidence": 0.65,
            "multi_selections": [],
        },
        {
            "game_number": 2,
            "home_team": "노리치C",
            "away_team": "찰턴",
            "match_date": "2025-12-27",
            "match_time": "21:00",
            "predicted": "1",
            "confidence": 0.55,
            "multi_selections": ["1", "X"],
        },
    ]

    # 저장
    success = prediction_tracker.save_prediction(
        round_info=test_round_info,
        predictions=test_predictions,
        multi_games=[2],
        game_type="soccer_wdl"
    )

    if success:
        print(f"  ✅ 예측 저장: .state/predictions/soccer_wdl/round_999.json")
    else:
        print("  ❌ 예측 저장 실패")
        return False

    # 로드
    loaded = prediction_tracker.get_prediction(999, "soccer_wdl")
    if loaded and len(loaded.predictions) == 2:
        print(f"  ✅ 예측 로드: {loaded.round_number}회차, {len(loaded.predictions)}경기")
    else:
        print("  ❌ 예측 로드 실패")
        return False

    return True


def test_result_simulation():
    """3. 결과 수집 테스트 (모의 데이터)"""
    print("\n" + "=" * 60)
    print("3. 결과 수집 테스트 (모의 데이터)")
    print("=" * 60)

    # 모의 결과 데이터 생성
    from src.services.result_collector import RESULTS_DIR

    mock_result = {
        "round_number": 999,
        "game_type": "soccer_wdl",
        "predicted_at": datetime.now().isoformat(),
        "collected_at": datetime.now().isoformat(),
        "results": [
            {
                "game_number": 1,
                "home_team": "레스터C",
                "away_team": "왓포드",
                "match_date": "2025-12-27",
                "match_time": "21:00",
                "predicted": "1",
                "predicted_multi": [],
                "confidence": 0.65,
                "actual": "1",
                "score_home": 2,
                "score_away": 1,
                "is_correct": True,
                "is_multi_correct": False,
            },
            {
                "game_number": 2,
                "home_team": "노리치C",
                "away_team": "찰턴",
                "match_date": "2025-12-27",
                "match_time": "21:00",
                "predicted": "1",
                "predicted_multi": ["1", "X"],
                "confidence": 0.55,
                "actual": "X",
                "score_home": 1,
                "score_away": 1,
                "is_correct": False,
                "is_multi_correct": True,
            },
        ],
        "summary": {
            "total_games": 2,
            "correct_predictions": 1,
            "hit_rate": 0.5,
            "single_hit": False,
            "multi_combinations_hit": 1,
        }
    }

    # 저장
    result_file = RESULTS_DIR / "soccer_wdl_999.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(mock_result, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 결과 저장: .state/results/soccer_wdl_999.json")

    # 로드
    loaded = prediction_tracker.get_result(999, "soccer_wdl")
    if loaded:
        print(f"  ✅ 결과 로드: {loaded['round_number']}회차, {len(loaded['results'])}경기")
        print(f"  ✅ 적중률: {loaded['summary']['hit_rate'] * 100:.1f}%")
    else:
        print("  ❌ 결과 로드 실패")
        return False

    return True


def test_hit_rate_reporter():
    """4. 적중률 리포트 생성 테스트"""
    print("\n" + "=" * 60)
    print("4. 적중률 리포트 생성 테스트")
    print("=" * 60)

    report = hit_rate_reporter.generate_report(999, "soccer_wdl")

    if report:
        print(f"  ✅ 리포트 생성: {report.round_number}회차")
        print(f"     - 적중률: {report.hit_rate * 100:.1f}%")
        print(f"     - 경기 수: {report.total_games}")
        print(f"     - 적중: {report.correct_predictions}")
        return True
    else:
        print("  ❌ 리포트 생성 실패")
        return False


def test_telegram_format():
    """5. 텔레그램 메시지 포맷팅 테스트"""
    print("\n" + "=" * 60)
    print("5. 텔레그램 메시지 포맷팅 테스트")
    print("=" * 60)

    # 모의 리포트 생성
    from src.services.prediction_tracker import CumulativeStats

    mock_stats = CumulativeStats(
        game_type="soccer_wdl",
        total_rounds=10,
        completed_rounds=10,
        avg_hit_rate=0.7,
        best_hit_rate=0.857,
        best_round=152,
        worst_hit_rate=0.5,
        worst_round=148,
        single_hits=2,
        multi_hit_rate=0.75,
        recent_5_avg=0.72,
        recent_10_avg=0.7,
    )

    mock_report = HitRateReport(
        round_number=999,
        game_type="soccer_wdl",
        generated_at=datetime.now().isoformat(),
        total_games=14,
        correct_predictions=10,
        hit_rate=0.714,
        single_hit=False,
        multi_games_count=4,
        multi_correct_count=3,
        multi_combinations_hit=4,
        game_results=[
            {
                "game_number": 1,
                "home_team": "레스터C",
                "away_team": "왓포드",
                "predicted": "1",
                "predicted_multi": [],
                "actual": "1",
                "score_home": 2,
                "score_away": 1,
                "is_correct": True,
                "is_multi_correct": False,
            },
            {
                "game_number": 2,
                "home_team": "노리치C",
                "away_team": "찰턴",
                "predicted": "1",
                "predicted_multi": ["1", "X"],
                "actual": "X",
                "score_home": 1,
                "score_away": 1,
                "is_correct": False,
                "is_multi_correct": True,
            },
        ],
        cumulative_stats=mock_stats,
    )

    message = hit_rate_reporter.format_telegram_message(mock_report)

    if message and len(message) > 100:
        print("  ✅ 메시지 생성 성공")
        print("\n" + "-" * 40)
        print(message)
        print("-" * 40)
        return True
    else:
        print("  ❌ 메시지 생성 실패")
        return False


def cleanup():
    """테스트 데이터 정리"""
    print("\n" + "=" * 60)
    print("테스트 데이터 정리")
    print("=" * 60)

    from src.services.result_collector import PREDICTIONS_DIR, RESULTS_DIR

    # 테스트 파일 삭제
    pred_file = PREDICTIONS_DIR / "soccer_wdl" / "round_999.json"
    result_file = RESULTS_DIR / "soccer_wdl_999.json"

    if pred_file.exists():
        pred_file.unlink()
        print(f"  🗑️ 삭제: .state/predictions/soccer_wdl/round_999.json")

    if result_file.exists():
        result_file.unlink()
        print(f"  🗑️ 삭제: .state/results/soccer_wdl_999.json")


def main():
    """메인 테스트 실행"""
    print("🧪 적중률 추적 시스템 통합 테스트")
    print("=" * 60)

    results = {
        "팀명 정규화": test_team_normalizer(),
        "예측 저장/로드": test_prediction_tracker(),
        "결과 수집": test_result_simulation(),
        "리포트 생성": test_hit_rate_reporter(),
        "텔레그램 포맷": test_telegram_format(),
    }

    # 정리
    cleanup()

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)

    passed = 0
    for name, result in results.items():
        status = "✅" if result else "❌"
        if result:
            passed += 1
        print(f"  {status} {name}")

    print(f"\n  결과: {passed}/{len(results)} 통과")

    if passed == len(results):
        print("\n  🎉 모든 테스트 통과!")
        return 0
    else:
        print("\n  ⚠️ 일부 테스트 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
