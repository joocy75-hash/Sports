#!/usr/bin/env python3
"""프로토 비용 최적화 기능 테스트"""

from datetime import datetime, timedelta, timezone
from src.services.proto_cost_optimizer import (
    ProtoSchedule,
    CostOptimizer,
    AnalysisMode
)


def test_proto_schedule():
    """프로토 일정 테스트"""
    print("=" * 70)
    print("🗓️  프로토 일정 테스트")
    print("=" * 70)

    # 다음 추첨일 확인
    next_승무패 = ProtoSchedule.get_next_draw_date("승무패")
    next_승5패 = ProtoSchedule.get_next_draw_date("승5패")

    print(f"다음 승무패 추첨일: {next_승무패.strftime('%Y-%m-%d %A %H:%M')}")
    print(f"다음 승5패 추첨일: {next_승5패.strftime('%Y-%m-%d %A %H:%M')}")

    # 남은 일수
    days_승무패 = ProtoSchedule.days_until_draw("승무패")
    days_승5패 = ProtoSchedule.days_until_draw("승5패")

    print(f"\n승무패 추첨까지: {days_승무패}일")
    print(f"승5패 추첨까지: {days_승5패}일")

    # 분석 여부
    should_승무패 = ProtoSchedule.should_analyze_now("승무패")
    should_승5패 = ProtoSchedule.should_analyze_now("승5패")

    print(f"\n승무패 분석 수행: {'✅ YES' if should_승무패 else '❌ NO'}")
    print(f"승5패 분석 수행: {'✅ YES' if should_승5패 else '❌ NO'}")
    print("=" * 70)
    print()


def test_cost_optimizer():
    """비용 최적화 테스트"""
    print("=" * 70)
    print("💰 비용 최적화 테스트")
    print("=" * 70)

    optimizer = CostOptimizer()

    # 시나리오 1: 추첨일 3일 전
    print("\n📅 시나리오 1: 추첨일 3일 전")
    mode = optimizer.get_recommended_mode("2024_001", "승무패")
    print(f"권장 모드: {mode.value}")

    # 시나리오 2: 강제 전체 분석
    print("\n📅 시나리오 2: 강제 전체 분석")
    mode = optimizer.get_recommended_mode("2024_001", "승무패", force_full=True)
    print(f"권장 모드: {mode.value}")

    # 시나리오 3: 캐시 테스트
    print("\n📅 시나리오 3: 캐시 테스트")
    test_result = {"analysis": "test data", "cost": 2.5}
    optimizer.cache_result("2024_001", test_result)
    print("✅ 결과 캐싱 완료")

    mode = optimizer.get_recommended_mode("2024_001", "승무패")
    print(f"권장 모드: {mode.value}")

    cached = optimizer.get_cached_result("2024_001")
    print(f"캐시 조회: {'✅ FOUND' if cached else '❌ NOT FOUND'}")

    print("=" * 70)
    print()


def test_cost_estimation():
    """비용 추정 테스트"""
    print("=" * 70)
    print("💵 비용 추정 테스트")
    print("=" * 70)

    optimizer = CostOptimizer()

    # 모드별 비용 추정
    modes = [AnalysisMode.FULL, AnalysisMode.QUICK, AnalysisMode.CACHED]

    for mode in modes:
        cost = optimizer.estimate_cost(mode, num_matches=14)
        print(f"\n{mode.value.upper()} 모드:")
        print(f"  총 비용: ${cost['total']:.4f}")
        print(f"  절감률: {cost['savings']}")
        if cost['breakdown']:
            print(f"  모델별:")
            for model, price in cost['breakdown'].items():
                print(f"    - {model}: ${price:.4f}")

    print("=" * 70)
    print()


def test_model_config():
    """모델 설정 테스트"""
    print("=" * 70)
    print("🤖 모델 설정 테스트")
    print("=" * 70)

    optimizer = CostOptimizer()

    modes = [AnalysisMode.FULL, AnalysisMode.QUICK, AnalysisMode.CACHED]

    for mode in modes:
        config = optimizer.get_model_config(mode)
        print(f"\n{mode.value.upper()} 모드 설정:")
        print(f"  Primary: {config.get('primary')}")
        print(f"  Secondary: {config.get('secondary')}")
        print(f"  Tertiary: {config.get('tertiary')}")
        print(f"  Iterations: {config.get('iterations')}")

        if config['consensus_weight']:
            print(f"  Consensus Weights:")
            for model, weight in config['consensus_weight'].items():
                print(f"    - {model}: {weight:.1%}")

    print("=" * 70)
    print()


def test_cache_cleanup():
    """캐시 정리 테스트"""
    print("=" * 70)
    print("🧹 캐시 정리 테스트")
    print("=" * 70)

    optimizer = CostOptimizer()

    # 여러 결과 캐싱
    for i in range(5):
        optimizer.cache_result(f"2024_{i:03d}", {"test": f"data_{i}"})

    print(f"캐시 항목 수: {len(optimizer.analysis_cache)}")

    # 오래된 캐시 정리 (0시간 = 모두 삭제)
    optimizer.clear_old_cache(max_age_hours=0)

    print(f"정리 후 캐시 항목 수: {len(optimizer.analysis_cache)}")

    print("=" * 70)
    print()


def test_monthly_cost_projection():
    """월간 비용 예측"""
    print("=" * 70)
    print("📊 월간 비용 예측")
    print("=" * 70)

    optimizer = CostOptimizer()

    # 승무패: 주 1회 = 월 4회
    승무패_최적화_없음 = 4 * 2.5  # 매일 분석
    승무패_최적화_적용 = 4 * (0.5 + 2.5)  # Quick 1회 + Full 1회

    print("\n승무패 (주 1회):")
    print(f"  최적화 없음: ${승무패_최적화_없음:.2f}/월")
    print(f"  최적화 적용: ${승무패_최적화_적용:.2f}/월")
    print(f"  절감액: ${승무패_최적화_없음 - 승무패_최적화_적용:.2f} ({(승무패_최적화_없음 - 승무패_최적화_적용) / 승무패_최적화_없음 * 100:.0f}%)")

    # 승5패: 주 2회 = 월 8회
    승5패_최적화_없음 = 8 * 2.5
    승5패_최적화_적용 = 8 * (0.5 + 2.5) / 2  # 평균

    print("\n승5패 (주 2회):")
    print(f"  최적화 없음: ${승5패_최적화_없음:.2f}/월")
    print(f"  최적화 적용: ${승5패_최적화_적용:.2f}/월")
    print(f"  절감액: ${승5패_최적화_없음 - 승5패_최적화_적용:.2f} ({(승5패_최적화_없음 - 승5패_최적화_적용) / 승5패_최적화_없음 * 100:.0f}%)")

    print("=" * 70)
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🛡️  프로토 비용 최적화 통합 테스트")
    print("=" * 70 + "\n")

    test_proto_schedule()
    test_cost_optimizer()
    test_cost_estimation()
    test_model_config()
    test_cache_cleanup()
    test_monthly_cost_projection()

    print("=" * 70)
    print("✅ 모든 테스트 완료!")
    print("=" * 70)
