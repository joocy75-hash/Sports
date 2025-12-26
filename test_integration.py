#!/usr/bin/env python3
"""
프로토 14경기 AI 분석 시스템 - 통합 테스트

이 스크립트는 전체 파이프라인을 Mock 데이터로 테스트합니다.
실제 API 호출을 최소화하고 시스템 통합과 데이터 흐름 검증에 집중합니다.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_match_data(match_id: int) -> Dict:
    """Mock 경기 데이터 생성"""

    teams = [
        ("맨체스터 시티", "첼시", 1.65, 3.80, 5.20, 0.55, 0.25, 0.20),
        ("리버풀", "아스날", 2.10, 3.40, 3.60, 0.42, 0.28, 0.30),
        ("바르셀로나", "레알 마드리드", 2.35, 3.20, 3.10, 0.38, 0.30, 0.32),
        ("바이에른 뮌헨", "도르트문트", 1.75, 3.60, 4.80, 0.52, 0.26, 0.22),
        ("파리 생제르맹", "마르세유", 1.55, 4.00, 6.00, 0.60, 0.23, 0.17),
        ("유벤투스", "인터 밀란", 2.50, 3.10, 3.00, 0.36, 0.31, 0.33),
        ("울버햄튼", "맨체스터 유나이티드", 4.20, 3.50, 1.90, 0.22, 0.27, 0.51),
        ("레스터 시티", "토트넘", 3.80, 3.40, 2.05, 0.24, 0.28, 0.48),
        ("AC 밀란", "나폴리", 2.80, 3.20, 2.65, 0.33, 0.30, 0.37),
        ("아틀레티코", "세비야", 1.95, 3.30, 4.00, 0.46, 0.29, 0.25),
        ("첼시", "레스터", 1.70, 3.70, 5.00, 0.54, 0.25, 0.21),
        ("리옹", "모나코", 2.40, 3.15, 3.20, 0.37, 0.30, 0.33),
        ("발렌시아", "빌바오", 2.60, 3.10, 2.90, 0.35, 0.31, 0.34),
        ("베르더 브레멘", "프랑크푸르트", 3.50, 3.30, 2.20, 0.26, 0.29, 0.45),
    ]

    if match_id > len(teams):
        match_id = 1

    home, away, h_odd, d_odd, a_odd, h_prob, d_prob, a_prob = teams[match_id - 1]

    return {
        "match_id": f"match_{match_id}",
        "home_team": {"name": home},
        "away_team": {"name": away},
        "league": "프리미어 리그" if match_id <= 8 else "라리가",
        "match_time": f"2025-12-24 {19 + (match_id % 5)}:00:00",
        "official_odds": {
            "home_win": h_odd,
            "draw": d_odd,
            "away_win": a_odd
        },
        # Mock 팀 통계
        "home_stats": {
            "league_rank": 3,
            "recent_form": "WWDWW",  # 최근 5경기
            "avg_goals_scored": 2.1,
            "avg_goals_conceded": 0.9,
            "home_record": {"wins": 8, "draws": 3, "losses": 1},
        },
        "away_stats": {
            "league_rank": 5,
            "recent_form": "WDLWW",
            "avg_goals_scored": 1.8,
            "avg_goals_conceded": 1.2,
            "away_record": {"wins": 6, "draws": 4, "losses": 2},
        },
        # Mock H2H
        "h2h": {
            "total_matches": 10,
            "home_wins": 4,
            "draws": 3,
            "away_wins": 3,
            "home_goals": 15,
            "away_goals": 12,
        },
        # AI 예측 (Mock)
        "ai_prediction": {
            "home_win_prob": h_prob,
            "draw_prob": d_prob,
            "away_win_prob": a_prob,
        },
        "confidence": 0.75 + (match_id % 3) * 0.08,
    }


def create_mock_round_data(num_matches: int = 14) -> List[Dict]:
    """Mock 회차 데이터 생성 (14경기)"""
    return [create_mock_match_data(i) for i in range(1, num_matches + 1)]


async def test_individual_modules():
    """개별 모듈 테스트"""

    logger.info("=" * 80)
    logger.info("🧪 개별 모듈 테스트 시작")
    logger.info("=" * 80)

    results = {
        "upset_detector": False,
        "multi_marking_optimizer": False,
        "marking_generator": False,
        "telegram_notifier": False,
    }

    # 1. 이변 감지 시스템 테스트
    logger.info("\n📌 1. 이변 감지 시스템 테스트")
    try:
        from src.services.upset_detector import UpsetDetector

        detector = UpsetDetector()
        test_match = create_mock_match_data(7)  # 울버햄튼 vs 맨유

        upset_result = detector.detect_upsets(
            ai_prediction=test_match["ai_prediction"],
            official_odds=test_match["official_odds"],
            confidence=test_match["confidence"]
        )

        logger.info(f"   ✅ 이변 감지 성공")
        logger.info(f"      - 이변 후보: {upset_result['is_upset_candidate']}")
        logger.info(f"      - 괴리도: {upset_result['divergence']:.2%}")
        logger.info(f"      - 리스크: {upset_result['risk_level']}")

        results["upset_detector"] = True

    except Exception as e:
        logger.error(f"   ❌ 이변 감지 실패: {e}")

    # 2. 복수 마킹 최적화 테스트
    logger.info("\n📌 2. 복수 마킹 최적화 테스트")
    try:
        from src.services.multi_marking_optimizer import MultiMarkingOptimizer

        optimizer = MultiMarkingOptimizer()
        test_match = create_mock_match_data(2)  # 리버풀 vs 아스날

        marking_result = optimizer.optimize_marking({
            'id': test_match['match_id'],
            'home_team': test_match['home_team']['name'],
            'away_team': test_match['away_team']['name'],
            'ai_prediction': test_match['ai_prediction'],
            'confidence': test_match['confidence'],
            'official_odds': test_match['official_odds'],
            'individual_predictions': []
        })

        logger.info(f"   ✅ 복수 마킹 최적화 성공")
        logger.info(f"      - 마킹 타입: {marking_result['marking_type']}")
        logger.info(f"      - 마킹 결과: {marking_result['marked_outcomes']}")
        logger.info(f"      - 예상 적중률: {marking_result['expected_hit_rate']:.2%}")

        results["multi_marking_optimizer"] = True

    except Exception as e:
        logger.error(f"   ❌ 복수 마킹 최적화 실패: {e}")

    # 3. 최종 마킹 생성기 테스트
    logger.info("\n📌 3. 최종 마킹 생성기 테스트")
    try:
        from src.services.marking_generator import MarkingGenerator

        generator = MarkingGenerator()
        mock_matches = create_mock_round_data(3)  # 3경기만 테스트

        # Mock 마킹 결과
        mock_markings = [
            {
                'match_id': m['match_id'],
                'home_team': m['home_team']['name'],
                'away_team': m['away_team']['name'],
                'marking_type': 'single',
                'marked_outcomes': ['home'],
                'expected_hit_rate': 0.55,
                'expected_value': 0.91,
                'reasoning': '고신뢰도 단식'
            }
            for m in mock_matches
        ]

        final_result = generator.generate({
            'round_id': 'TEST_123',
            'matches': [
                {
                    'id': m['match_id'],
                    'home_team': m['home_team']['name'],
                    'away_team': m['away_team']['name'],
                    'ai_prediction': m['ai_prediction'],
                    'confidence': m['confidence'],
                    'individual_predictions': [],
                    'official_odds': m['official_odds']
                }
                for m in mock_matches
            ],
            'upsets': [],
            'markings': mock_markings
        })

        logger.info(f"   ✅ 최종 마킹 생성 성공")
        logger.info(f"      - 회차: {final_result['round_id']}")
        logger.info(f"      - 경기 수: {len(final_result['final_markings'])}")
        logger.info(f"      - 평균 신뢰도: {final_result['summary']['avg_confidence']:.0f}%")

        results["marking_generator"] = True

    except Exception as e:
        logger.error(f"   ❌ 최종 마킹 생성 실패: {e}")

    # 4. 텔레그램 알림 테스트 (모듈만 확인)
    logger.info("\n📌 4. 텔레그램 알림 모듈 테스트")
    try:
        from src.services.telegram_notifier import TelegramNotifier

        notifier = TelegramNotifier()
        logger.info(f"   ✅ 텔레그램 모듈 로드 성공")
        logger.info(f"      - Bot Token 설정: {'✅' if notifier.bot_token else '❌'}")
        logger.info(f"      - Chat ID 설정: {'✅' if notifier.chat_id else '❌'}")

        results["telegram_notifier"] = True

    except Exception as e:
        logger.error(f"   ❌ 텔레그램 모듈 로드 실패: {e}")

    return results


async def test_integrated_pipeline():
    """통합 파이프라인 테스트"""

    logger.info("\n" + "=" * 80)
    logger.info("🔗 통합 파이프라인 테스트 시작")
    logger.info("=" * 80)

    try:
        from src.main_pipeline import OddsPipeline
        from src.preprocessing.feature_engineer import SportType

        # Mock 데이터 생성
        mock_matches = create_mock_round_data(14)

        # 공식 배당 추출
        official_odds = {
            m['match_id']: m['official_odds']
            for m in mock_matches
        }

        logger.info(f"\n📊 Mock 데이터 준비 완료")
        logger.info(f"   - 경기 수: {len(mock_matches)}")
        logger.info(f"   - 공식 배당: {len(official_odds)}개")

        # 파이프라인 초기화
        logger.info(f"\n🔧 파이프라인 초기화 중...")
        pipeline = OddsPipeline(
            sport_type=SportType.SOCCER,
            margin=0.05,
            use_perplexity=False  # 테스트에서는 비활성화
        )

        # 모델 상태 확인
        model_status = pipeline.get_model_status()
        logger.info(f"\n🤖 AI 모델 상태:")
        logger.info(f"   - LLM AI: {'✅' if model_status['llm_ai']['available'] else '❌'}")
        logger.info(f"   - ML 모델: {'✅' if model_status['ml']['available'] else '❌'}")
        logger.info(f"   - 통계 모델: {'✅' if model_status['statistical']['available'] else '❌'}")

        # 전체 파이프라인 실행
        logger.info(f"\n🚀 전체 파이프라인 실행 중...")
        logger.info(f"   (실제 AI 분석 대신 Mock 데이터 사용)")

        result = await pipeline.analyze_round(
            round_id="TEST_123",
            matches_data=mock_matches,
            official_odds=official_odds
        )

        # 결과 검증
        logger.info(f"\n✅ 파이프라인 실행 완료!")
        logger.info(f"\n📋 결과 요약:")
        logger.info(f"   - 회차 ID: {result.round_id}")
        logger.info(f"   - 분석 경기 수: {len(result.matches)}")
        logger.info(f"   - 고신뢰도 경기: {result.summary.get('high_confidence_matches', 0)}")
        logger.info(f"   - Value Bet 발견: {result.summary.get('value_bets_found', 0)}")
        logger.info(f"   - 평균 AI 합의도: {result.summary.get('avg_consensus', 0):.1%}")
        logger.info(f"   - 이변 후보: {result.summary.get('upset_count', 0)}경기")
        logger.info(f"   - 복수 마킹: {result.summary.get('multi_marking_count', 0)}경기")

        # 최종 마킹 확인
        final_markings = result.summary.get('final_markings', {})
        if final_markings:
            logger.info(f"\n📝 최종 마킹 통계:")
            summary = final_markings.get('summary', {})
            logger.info(f"   - 단식: {summary.get('single_count', 0)}경기")
            logger.info(f"   - 2개 복수: {summary.get('double_count', 0)}경기")
            logger.info(f"   - 3개 복수: {summary.get('triple_count', 0)}경기")

        # 추천 조합
        if result.combinations:
            logger.info(f"\n🏆 추천 조합 (상위 3개):")
            for i, combo in enumerate(result.combinations[:3], 1):
                logger.info(f"   {i}. {combo.get('name', 'Unknown')}")
                logger.info(f"      - 예상 ROI: {combo.get('metrics', {}).get('expected_roi', 0):.1%}")

        return True, result

    except Exception as e:
        logger.error(f"\n❌ 통합 파이프라인 테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, None


async def generate_test_report(
    individual_results: Dict[str, bool],
    pipeline_success: bool,
    pipeline_result
):
    """테스트 결과 리포트 생성"""

    logger.info("\n" + "=" * 80)
    logger.info("📊 테스트 결과 리포트")
    logger.info("=" * 80)

    # 개별 모듈 결과
    logger.info("\n✅ 개별 모듈 테스트 결과:")
    for module, success in individual_results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"   - {module}: {status}")

    # 통합 파이프라인 결과
    logger.info(f"\n✅ 통합 파이프라인 테스트:")
    logger.info(f"   - 상태: {'✅ PASS' if pipeline_success else '❌ FAIL'}")

    # 전체 통과율
    individual_pass = sum(individual_results.values())
    individual_total = len(individual_results)
    overall_pass_rate = (individual_pass + (1 if pipeline_success else 0)) / (individual_total + 1)

    logger.info(f"\n📈 전체 통과율:")
    logger.info(f"   - 개별 모듈: {individual_pass}/{individual_total} ({individual_pass/individual_total:.0%})")
    logger.info(f"   - 전체: {overall_pass_rate:.0%}")

    # JSON 리포트 생성
    report = {
        "test_date": datetime.now().isoformat(),
        "test_type": "integration_test",
        "individual_modules": individual_results,
        "integrated_pipeline": {
            "success": pipeline_success,
            "result_summary": None
        },
        "overall_pass_rate": overall_pass_rate,
    }

    if pipeline_success and pipeline_result:
        report["integrated_pipeline"]["result_summary"] = {
            "round_id": pipeline_result.round_id,
            "total_matches": len(pipeline_result.matches),
            "summary": pipeline_result.summary,
        }

    # 파일 저장
    report_path = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"\n💾 리포트 저장: {report_path}")

    return report


async def main():
    """메인 테스트 실행"""

    logger.info("🚀 프로토 14경기 AI 분석 시스템 - 통합 테스트 시작")
    logger.info(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 개별 모듈 테스트
    individual_results = await test_individual_modules()

    # 2. 통합 파이프라인 테스트
    pipeline_success, pipeline_result = await test_integrated_pipeline()

    # 3. 테스트 리포트 생성
    await generate_test_report(individual_results, pipeline_success, pipeline_result)

    logger.info("\n" + "=" * 80)
    logger.info("✅ 모든 테스트 완료!")
    logger.info(f"⏰ 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
