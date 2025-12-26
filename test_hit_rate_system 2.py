#!/usr/bin/env python3
"""
적중률 추적 시스템 통합 테스트

테스트 항목:
1. 팀명 정규화 테스트
2. 예측 저장/로드 테스트
3. 결과 수집 테스트 (모의 데이터)
4. 적중률 리포트 생성 테스트
5. 텔레그램 메시지 포맷팅 테스트
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

# 테스트 데이터
TEST_ROUND_NUMBER = 999
TEST_GAME_TYPE = "soccer_wdl"


def test_team_name_normalizer():
    """1. 팀명 정규화 테스트"""
    print("=" * 60)
    print("1. 팀명 정규화 테스트")
    print("=" * 60)

    from src.services.team_name_normalizer import team_normalizer

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
    for betman, kspo in test_cases:
        result = team_normalizer.match_team(betman, kspo)
        status = "✅" if result.confidence >= 0.6 else "❌"
        if result.confidence >= 0.6:
            passed += 1
        print(f"  {status} {betman:15} ↔ {kspo:25} → {result.match_type} ({result.confidence:.2f})")

    print(f"\n  결과: {passed}/{len(test_cases)} 통과")
    return passed == len(test_cases)


def test_prediction_tracker():
    """2. 예측 저장/로드 테스트"""
    print("\n" + "=" * 60)
    print("2. 예측 저장/로드 테스트")
    print("=" * 60)

    from src.services.prediction_tracker import prediction_tracker, GamePredictionRecord, RoundPredictionRecord

    # 테스트 예측 데이터 생성
    predictions = [
        {
            "game_number": 1,
            "home_team": "레스터C",
            "away_team": "왓포드",
            "match_date": "2025-12-27",
            "match_time": "22:00",
            "prob_home": 0.55,
            "prob_draw": 0.25,
            "prob_away": 0.20,
            "recommended": "1",
            "confidence": 0.75,
            "is_multi": False,
            "multi_selections": [],
        },
        {
            "game_number": 2,
            "home_team": "노리치C",
            "away_team": "찰턴",
            "match_date": "2025-12-27",
            "match_time": "22:00",
            "prob_home": 0.40,
            "prob_draw": 0.35,
            "prob_away": 0.25,
            "recommended": "1",
            "confidence": 0.55,
            "is_multi": True,
            "multi_selections": ["1", "X"],
        },
    ]

    # 가상 RoundInfo
    class MockRoundInfo:
        def __init__(self):
            self.round_number = TEST_ROUND_NUMBER
            self.game_type = TEST_GAME_TYPE
            self.match_date = "2025-12-27"
            self.deadline = datetime(2025, 12, 27, 20, 0)

    round_info = MockRoundInfo()

    try:
        # 저장
        file_path = prediction_tracker.save_prediction(
            round_info=round_info,
            predictions=predictions,
            multi_games=[2]
        )
        print(f"  ✅ 예측 저장: {file_path}")

        # 로드
        loaded = prediction_tracker.get_prediction(TEST_ROUND_NUMBER, TEST_GAME_TYPE)
        if loaded:
            print(f"  ✅ 예측 로드: {loaded.round_number}회차, {len(loaded.predictions)}경기")
            return True
        else:
            print("  ❌ 예측 로드 실패")
            return False
    except Exception as e:
        print(f"  ❌ 에러: {e}")
        return False


def test_result_collector():
    """3. 결과 수집 테스트 (모의 데이터)"""
    print("\n" + "=" * 60)
    print("3. 결과 수집 테스트 (모의 데이터)")
    print("=" * 60)

    from src.services.result_collector import ResultCollector, GameResult, RoundResult

    # 모의 결과 데이터 생성
    game_results = [
        GameResult(
            game_number=1,
            home_team="레스터C",
            away_team="왓포드",
            match_date="2025-12-27",
            match_time="22:00",
            predicted="1",
            confidence=0.75,
            actual="1",
            score_home=2,
            score_away=1,
            match_end_val="승",
            is_correct=True,
        ),
        GameResult(
            game_number=2,
            home_team="노리치C",
            away_team="찰턴",
            match_date="2025-12-27",
            match_time="22:00",
            predicted="1",
            predicted_multi=["1", "X"],
            confidence=0.55,
            actual="X",
            score_home=1,
            score_away=1,
            match_end_val="무",
            is_correct=False,
            is_multi_correct=True,
        ),
    ]

    round_result = RoundResult(
        round_number=TEST_ROUND_NUMBER,
        game_type=TEST_GAME_TYPE,
        predicted_at=datetime.now().isoformat(),
        collected_at=datetime.now().isoformat(),
        results=game_results,
        total_games=2,
        correct_predictions=1,
        hit_rate=0.5,
        single_hit=False,
        multi_combinations_hit=1,
    )

    # 저장
    result_dir = Path(".state/results")
    result_dir.mkdir(parents=True, exist_ok=True)
    result_file = result_dir / f"{TEST_GAME_TYPE}_{TEST_ROUND_NUMBER}.json"

    try:
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(round_result.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"  ✅ 결과 저장: {result_file}")

        # 로드
        with open(result_file, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        print(f"  ✅ 결과 로드: {loaded['round_number']}회차, {len(loaded['results'])}경기")
        print(f"  ✅ 적중률: {loaded['summary']['hit_rate'] * 100:.1f}%")
        return True
    except Exception as e:
        print(f"  ❌ 에러: {e}")
        return False


def test_hit_rate_reporter():
    """4. 적중률 리포트 생성 테스트"""
    print("\n" + "=" * 60)
    print("4. 적중률 리포트 생성 테스트")
    print("=" * 60)

    from src.services.hit_rate_reporter import hit_rate_reporter

    try:
        report = hit_rate_reporter.generate_report(TEST_ROUND_NUMBER, TEST_GAME_TYPE)
        if report:
            print(f"  ✅ 리포트 생성: {report.round_number}회차")
            print(f"     - 적중률: {report.hit_rate * 100:.1f}%")
            print(f"     - 경기 수: {report.total_games}")
            print(f"     - 적중: {report.correct_predictions}")
            return True
        else:
            print("  ⚠️ 리포트 없음 (결과 데이터 없음)")
            return True  # 결과가 없는 경우도 정상
    except Exception as e:
        print(f"  ❌ 에러: {e}")
        return False


def test_telegram_format():
    """5. 텔레그램 메시지 포맷팅 테스트"""
    print("\n" + "=" * 60)
    print("5. 텔레그램 메시지 포맷팅 테스트")
    print("=" * 60)

    from src.services.hit_rate_reporter import hit_rate_reporter, HitRateReport
    from src.services.prediction_tracker import CumulativeStats

    # 테스트 리포트 생성
    test_report = HitRateReport(
        round_number=TEST_ROUND_NUMBER,
        game_type=TEST_GAME_TYPE,
        collected_at=datetime.now().isoformat(),
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
                "actual": "1",
                "score_home": 2,
                "score_away": 1,
                "is_correct": True,
                "predicted_multi": None,
                "is_multi_correct": False,
            },
            {
                "game_number": 2,
                "home_team": "노리치C",
                "away_team": "찰턴",
                "predicted": "1",
                "actual": "X",
                "score_home": 1,
                "score_away": 1,
                "is_correct": False,
                "predicted_multi": ["1", "X"],
                "is_multi_correct": True,
            },
        ],
        cumulative_stats=CumulativeStats(
            game_type=TEST_GAME_TYPE,
            total_rounds=10,
            total_games=140,
            total_correct=98,
            avg_hit_rate=0.70,
            best_round=152,
            best_hit_rate=0.857,
            worst_round=148,
            worst_hit_rate=0.50,
            multi_hit_rate=0.75,
            recent_5_avg=0.72,
            recent_10_avg=0.70,
        ),
    )

    try:
        message = hit_rate_reporter.format_telegram_message(test_report)
        print("  ✅ 메시지 생성 성공")
        print()
        print("-" * 40)
        print(message[:500] + "..." if len(message) > 500 else message)
        print("-" * 40)
        return True
    except Exception as e:
        print(f"  ❌ 에러: {e}")
        return False


def cleanup_test_data():
    """테스트 데이터 정리"""
    print("\n" + "=" * 60)
    print("테스트 데이터 정리")
    print("=" * 60)

    files_to_remove = [
        Path(f".state/predictions/{TEST_GAME_TYPE}/round_{TEST_ROUND_NUMBER}.json"),
        Path(f".state/results/{TEST_GAME_TYPE}_{TEST_ROUND_NUMBER}.json"),
    ]

    for file in files_to_remove:
        if file.exists():
            file.unlink()
            print(f"  🗑️ 삭제: {file}")


def main():
    """메인 테스트 실행"""
    print()
    print("🧪 적중률 추적 시스템 통합 테스트")
    print("=" * 60)

    results = {
        "팀명 정규화": test_team_name_normalizer(),
        "예측 저장/로드": test_prediction_tracker(),
        "결과 수집": test_result_collector(),
        "리포트 생성": test_hit_rate_reporter(),
        "텔레그램 포맷": test_telegram_format(),
    }

    # 테스트 데이터 정리
    cleanup_test_data()

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")

    print()
    print(f"  결과: {passed}/{total} 통과")

    if passed == total:
        print("\n  🎉 모든 테스트 통과!")
    else:
        print("\n  ⚠️ 일부 테스트 실패")


if __name__ == "__main__":
    main()
