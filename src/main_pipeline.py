"""
메인 파이프라인 - AI 기반 배당 산출 시스템

전체 워크플로우를 통합하여 14경기 일괄 분석을 수행합니다.

워크플로우:
1. 데이터 수집 (KSPO API + Perplexity)
2. 특징 추출
3. AI 앙상블 분석
4. 배당률 산출
5. Value Bet 탐지
6. 조합 최적화
7. 결과 출력
"""

import asyncio
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 데이터 수집
from src.services.kspo_api_client import KSPOApiClient

# 전처리
from src.preprocessing import FeatureEngineer, WeightCalculator
from src.preprocessing.feature_engineer import SportType, MatchFeatures

# AI 분석 - HybridAnalyzer (LLM + ML + 통계 통합)
from src.services.hybrid_analyzer import HybridAnalyzer, get_hybrid_analyzer

# 배당 산출
from src.odds_calculation import OddsCalculator, ValueDetector, MarginAdjuster
from src.odds_calculation.value_detector import ValueBet

# 조합 최적화
from src.analysis import CombinationOptimizer, Combination

# 신규 모듈 - 이변 감지, 복수 마킹, 텔레그램, 마킹 생성기
from src.services.upset_detector import UpsetDetector
from src.services.multi_marking_optimizer import MultiMarkingOptimizer
from src.services.telegram_notifier import TelegramNotifier
from src.services.marking_generator import MarkingGenerator

logger = logging.getLogger(__name__)


@dataclass
class MatchAnalysisResult:
    """경기 분석 결과"""

    match_id: str
    home_team: str
    away_team: str
    league: str
    match_time: str

    # AI 분석 결과
    predictions: Dict  # 개별 AI 예측
    synthesized: Dict  # 합성 예측
    confidence: float
    consensus: float

    # 배당률
    our_odds: Dict
    official_odds: Dict

    # Value Bets
    value_bets: List[Dict]

    # 특징
    features: Dict
    key_factors: List[str]


@dataclass
class RoundAnalysisResult:
    """회차 전체 분석 결과"""

    round_id: str
    sport_type: str
    matches: List[MatchAnalysisResult]
    combinations: List[Dict]
    summary: Dict
    generated_at: str


class OddsPipeline:
    """
    AI 기반 배당 산출 파이프라인

    KSPO API에서 경기 데이터를 가져와 AI 앙상블 분석 후
    자체 배당률을 산출하고 Value Bet을 탐지합니다.
    """

    def __init__(
        self,
        sport_type: SportType = SportType.SOCCER,
        margin: float = 0.05,
        use_perplexity: bool = True,
    ):
        """
        Args:
            sport_type: 스포츠 종류
            margin: 배당률 마진
            use_perplexity: Perplexity 뉴스 수집 사용 여부
        """
        self.sport_type = sport_type
        self.use_perplexity = use_perplexity

        # 컴포넌트 초기화
        self.kspo_client = KSPOApiClient()
        self.feature_engineer = FeatureEngineer(sport_type)
        self.weight_calculator = WeightCalculator(sport_type)
        self.odds_calculator = OddsCalculator(margin=margin)
        self.value_detector = ValueDetector()
        self.margin_adjuster = MarginAdjuster(target_margin=margin)
        self.combo_optimizer = CombinationOptimizer()

        # 하이브리드 분석기 초기화 (LLM + ML + 통계 통합)
        self.hybrid_analyzer = get_hybrid_analyzer()

        # 신규 모듈 초기화
        self.upset_detector = UpsetDetector()
        self.multi_optimizer = MultiMarkingOptimizer()
        self.telegram_notifier = TelegramNotifier()
        self.marking_generator = MarkingGenerator()

        # 모델 상태 로깅
        model_status = self.hybrid_analyzer.get_model_status()
        logger.info(f"🤖 HybridAnalyzer 초기화 완료")
        logger.info(
            f"   LLM AI: {'✅' if model_status['llm_ai']['available'] else '❌'} ({model_status['llm_ai']['weight']:.0%})"
        )
        logger.info(
            f"   LightGBM: {'✅' if model_status['ml']['available'] else '❌'} ({model_status['ml']['weight']:.0%})"
        )
        logger.info(
            f"   통계앙상블: {'✅' if model_status['statistical']['available'] else '❌'} ({model_status['statistical']['weight']:.0%})"
        )

        logger.info(
            f"OddsPipeline 초기화 완료 (sport={sport_type.value}, margin={margin})"
        )

    def get_model_status(self) -> Dict:
        """모델 상태 조회"""
        return self.hybrid_analyzer.get_model_status()

    async def analyze_round(
        self,
        round_id: Optional[str] = None,
        matches_data: Optional[List[Dict]] = None,
        official_odds: Optional[Dict[str, Dict]] = None,
    ) -> RoundAnalysisResult:
        """
        회차 전체 분석

        Args:
            round_id: 회차 ID (없으면 오늘 경기)
            matches_data: 직접 제공할 경기 데이터 (테스트용)
            official_odds: 공식 배당률 (match_id -> odds)

        Returns:
            RoundAnalysisResult
        """
        logger.info(f"🔍 회차 분석 시작: {round_id or '오늘 경기'}")

        # 1. 데이터 수집
        logger.info("  📊 1단계: 데이터 수집")
        if matches_data is None:
            matches_data = await self._collect_matches(round_id)

        if not matches_data:
            logger.warning("경기 데이터가 없습니다")
            return self._create_empty_result(round_id)

        logger.info(f"     {len(matches_data)}개 경기 수집 완료")

        # 분석 결과 저장
        match_results = []

        for i, match in enumerate(matches_data, 1):
            match_id = match.get("match_id", f"match_{i}")
            home_team = match.get("home_team", {}).get("name", "홈팀")
            away_team = match.get("away_team", {}).get("name", "원정팀")

            logger.info(
                f"  ⚽ 경기 {i}/{len(matches_data)}: {home_team} vs {away_team}"
            )

            try:
                # 2. 특징 추출
                features = self.feature_engineer.extract_features(match)

                # 3. 하이브리드 분석 (LLM + ML + 통계)
                hybrid_result = await self.hybrid_analyzer.analyze(
                    match_context={
                        "match_id": match_id,
                        "home_team": home_team,
                        "away_team": away_team,
                        "league": match.get("league", ""),
                        "sport_type": self.sport_type.value,
                        "h2h_summary": f"홈 {features.h2h_home_wins}승, 무 {features.h2h_draws}, 원정 {features.h2h_away_wins}승",
                        "additional_context": self.feature_engineer.to_ai_prompt_context(
                            features
                        ),
                    },
                    team_stats={
                        "home": {
                            "avg_gf": features.home_team.avg_goals_scored,
                            "avg_ga": features.home_team.avg_goals_conceded,
                            "form": features.home_team.recent_form,
                            "elo": 1500 + (10 - features.home_team.league_rank) * 50,
                        },
                        "away": {
                            "avg_gf": features.away_team.avg_goals_scored,
                            "avg_ga": features.away_team.avg_goals_conceded,
                            "form": features.away_team.recent_form,
                            "elo": 1500 + (10 - features.away_team.league_rank) * 50,
                        },
                    },
                    h2h_data={
                        "home_wins": features.h2h_home_wins,
                        "away_wins": features.h2h_away_wins,
                        "draws": features.h2h_draws,
                        "home_goals": features.h2h_home_goals,
                        "away_goals": features.h2h_away_goals,
                    },
                )

                # 4. 결과 추출
                synthesized = {
                    "home_win_prob": hybrid_result.home_prob,
                    "draw_prob": hybrid_result.draw_prob,
                    "away_win_prob": hybrid_result.away_prob,
                }
                confidence = hybrid_result.overall_confidence
                consensus = hybrid_result.consensus_score

                # 5. 배당률 산출
                our_odds = self.odds_calculator.probability_to_odds(
                    {
                        "home_win": synthesized.get("home_win_prob", 0.33),
                        "draw": synthesized.get("draw_prob", 0.33),
                        "away_win": synthesized.get("away_win_prob", 0.33),
                    }
                )

                # 6. Value Bet 탐지
                match_official = (
                    official_odds.get(match_id, {}) if official_odds else {}
                )
                value_bets = []

                if match_official:
                    value_bets_raw = self.value_detector.find_value_bets(
                        {**our_odds, "confidence": confidence}, match_official, match_id
                    )
                    value_bets = [vb.to_dict() for vb in value_bets_raw]

                # 결과 저장
                match_results.append(
                    MatchAnalysisResult(
                        match_id=match_id,
                        home_team=home_team,
                        away_team=away_team,
                        league=match.get("league", ""),
                        match_time=match.get("match_time", ""),
                        predictions=hybrid_result.to_dict(),
                        synthesized=synthesized,
                        confidence=confidence,
                        consensus=consensus,
                        our_odds=our_odds,
                        official_odds=match_official,
                        value_bets=value_bets,
                        features=features.feature_vector,
                        key_factors=features.key_factors,
                    )
                )

            except Exception as e:
                logger.error(f"     ❌ 분석 오류: {e}")
                continue

        # 7. 이변 감지
        logger.info("  ⚠️  7단계: 이변 감지")
        upset_matches = []
        for r in match_results:
            upset_analysis = self.upset_detector.detect_upsets(
                ai_prediction=r.synthesized,
                official_odds=r.official_odds,
                confidence=r.confidence
            )
            if upset_analysis['is_upset_candidate']:
                upset_matches.append({
                    'match_id': r.match_id,
                    'home_team': r.home_team,
                    'away_team': r.away_team,
                    'ai_prediction': r.synthesized,
                    'official_odds': r.official_odds,
                    'confidence': r.confidence,
                    **upset_analysis
                })
        logger.info(f"     {len(upset_matches)}개 이변 후보 발견")

        # 8. 복수 마킹 최적화
        logger.info("  🎲 8단계: 복수 마킹 최적화")
        marking_results = []
        for r in match_results:
            marking = self.multi_optimizer.optimize_marking({
                'id': r.match_id,
                'home_team': r.home_team,
                'away_team': r.away_team,
                'ai_prediction': r.synthesized,
                'confidence': r.confidence,
                'official_odds': r.official_odds,
                'individual_predictions': r.predictions.get('individual_predictions', [])
            })
            marking_results.append({
                'match_id': r.match_id,
                'home_team': r.home_team,
                'away_team': r.away_team,
                **marking
            })

        multi_marking_count = sum(1 for m in marking_results if m['marking_type'] != 'single')
        logger.info(f"     {multi_marking_count}개 경기 복수 마킹 권장")

        # 9. 최종 마킹 생성
        logger.info("  📋 9단계: 최종 마킹 생성")
        final_markings = self.marking_generator.generate({
            'round_id': round_id or 'today',
            'matches': [
                {
                    'id': r.match_id,
                    'home_team': r.home_team,
                    'away_team': r.away_team,
                    'ai_prediction': r.synthesized,
                    'confidence': r.confidence,
                    'individual_predictions': r.predictions.get('individual_predictions', []),
                    'official_odds': r.official_odds
                }
                for r in match_results
            ],
            'upsets': upset_matches,
            'markings': marking_results
        })

        # 10. 텔레그램 알림 전송
        logger.info("  📱 10단계: 텔레그램 알림")
        try:
            if self.telegram_notifier.enabled:
                # 기본 메시지 전송 (특수 문자 이스케이프)
                message = f"🎯 프로토 {round_id or 'today'}회차 분석 완료\n"
                message += f"총 {len(final_markings['final_markings'])}경기 분석\n"
                message += f"이변 후보: {len(upset_matches)}경기\n"
                message += f"복수 마킹: {final_markings['summary'].get('double_count', 0) + final_markings['summary'].get('triple_count', 0)}경기\n"
                # Markdown 특수 문자 이스케이프
                message = message.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
                await self.telegram_notifier.send_message(message, parse_mode=None)  # 포맷 해제
                logger.info("     텔레그램 알림 전송 완료")
            else:
                logger.info("     텔레그램 비활성화 (알림 전송 생략)")
        except Exception as e:
            logger.warning(f"     텔레그램 알림 실패: {e}")

        # 11. 조합 최적화
        logger.info("  🔄 11단계: 조합 최적화")
        combos_input = [
            {
                "match_id": r.match_id,
                "home_team": r.home_team,
                "away_team": r.away_team,
                "synthesized_prediction": r.synthesized,
                "confidence": r.confidence,
                "our_odds": r.our_odds,
                "value_bets": r.value_bets,
            }
            for r in match_results
        ]
        combinations = self.combo_optimizer.generate_combinations(combos_input)

        # 12. 요약 생성
        summary = self._generate_summary(match_results, combinations)
        summary['upset_count'] = len(upset_matches)
        summary['multi_marking_count'] = multi_marking_count
        summary['final_markings'] = final_markings

        logger.info("✅ 분석 완료!")

        return RoundAnalysisResult(
            round_id=round_id or "today",
            sport_type=self.sport_type.value,
            matches=match_results,
            combinations=[c.to_dict() for c in combinations],
            summary=summary,
            generated_at=datetime.now().isoformat(),
        )

    async def _collect_matches(self, round_id: Optional[str]) -> List[Dict]:
        """경기 데이터 수집"""
        try:
            if self.sport_type == SportType.SOCCER:
                matches = await asyncio.to_thread(self.kspo_client.get_toto_matches)
            else:
                matches = await asyncio.to_thread(self.kspo_client.get_proto_matches)

            return matches or []
        except Exception as e:
            logger.error(f"경기 데이터 수집 실패: {e}")
            return []

    async def _analyze_with_ensemble(self, features: MatchFeatures) -> List[tuple]:
        """AI 앙상블 분석"""

        if not self.analyzers:
            return []

        # MatchContext 생성
        context = MatchContext(
            match_id=features.match_id,
            home_team=features.home_team.team_name,
            away_team=features.away_team.team_name,
            league=features.league_name,
            sport_type=self.sport_type,
            home_stats={
                "form": features.home_team.recent_form,
                "goals_scored": features.home_team.avg_goals_scored,
                "goals_conceded": features.home_team.avg_goals_conceded,
                "rank": features.home_team.league_rank,
            },
            away_stats={
                "form": features.away_team.recent_form,
                "goals_scored": features.away_team.avg_goals_scored,
                "goals_conceded": features.away_team.avg_goals_conceded,
                "rank": features.away_team.league_rank,
            },
            h2h_summary=f"홈팀 {features.h2h_home_wins}승, 무 {features.h2h_draws}, 원정 {features.h2h_away_wins}승",
            additional_context=self.feature_engineer.to_ai_prompt_context(features),
        )

        # 병렬 분석
        tasks = [analyzer.analyze_match(context) for analyzer in self.analyzers]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 성공한 결과만 반환
        valid_results = []
        for analyzer, result in zip(self.analyzers, results):
            if isinstance(result, Exception):
                logger.warning(f"  {analyzer.provider_name} 분석 실패: {result}")
            else:
                valid_results.append((analyzer, result))

        return valid_results

    def _synthesize_predictions(self, ai_results: List[tuple]) -> tuple:
        """AI 예측 합성"""

        if not ai_results:
            return (
                {"home_win_prob": 0.33, "draw_prob": 0.34, "away_win_prob": 0.33},
                0.5,
                0.5,
            )

        # 확률 수집
        home_probs = []
        draw_probs = []
        away_probs = []
        confidences = []

        for analyzer, opinion in ai_results:
            probs = opinion.probabilities or {}
            home_probs.append(probs.get("home", 0.33))
            draw_probs.append(probs.get("draw", 0.33))
            away_probs.append(probs.get("away", 0.33))
            confidences.append(
                opinion.confidence / 100
                if opinion.confidence > 1
                else opinion.confidence
            )

        # 신뢰도 가중 평균
        total_conf = sum(confidences) or 1
        weights = [c / total_conf for c in confidences]

        home_win = sum(p * w for p, w in zip(home_probs, weights))
        draw = sum(p * w for p, w in zip(draw_probs, weights))
        away_win = sum(p * w for p, w in zip(away_probs, weights))

        # 정규화
        total = home_win + draw + away_win
        if total > 0:
            home_win /= total
            draw /= total
            away_win /= total

        # 평균 신뢰도 및 합의도
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        # 합의도: 표준편차 기반
        import statistics

        if len(home_probs) >= 2:
            std = statistics.stdev(home_probs)
            consensus = max(0, 1 - std * 2)
        else:
            consensus = 0.5

        return (
            {
                "home_win_prob": round(home_win, 4),
                "draw_prob": round(draw, 4),
                "away_win_prob": round(away_win, 4),
            },
            round(avg_confidence, 4),
            round(consensus, 4),
        )

    def _generate_summary(
        self, matches: List[MatchAnalysisResult], combinations: List[Combination]
    ) -> Dict:
        """분석 요약 생성"""

        if not matches:
            return {"status": "no_matches"}

        high_conf = [m for m in matches if m.confidence >= 0.80]
        value_bet_count = sum(len(m.value_bets) for m in matches)
        avg_consensus = sum(m.consensus for m in matches) / len(matches)

        best_combo = combinations[0] if combinations else None

        return {
            "total_matches": len(matches),
            "high_confidence_matches": len(high_conf),
            "value_bets_found": value_bet_count,
            "avg_consensus": round(avg_consensus, 2),
            "best_combination": best_combo.name if best_combo else None,
            "expected_roi": best_combo.metrics.expected_roi if best_combo else 0,
            "recommendation": self._get_recommendation(matches, combinations),
        }

    def _get_recommendation(
        self, matches: List[MatchAnalysisResult], combinations: List[Combination]
    ) -> str:
        """추천 메시지"""

        if not combinations:
            return "분석 결과가 충분하지 않습니다."

        best = combinations[0]
        roi = best.metrics.expected_roi

        if roi > 0.30:
            return f"🔥 강력 추천! 예상 ROI {roi:.1%} ({best.name})"
        elif roi > 0.10:
            return f"👍 좋은 기회. 예상 ROI {roi:.1%} ({best.name})"
        elif roi > 0:
            return f"📊 보통 기회. 예상 ROI {roi:.1%} ({best.name})"
        else:
            return "⚠️ 이번 회차는 관망을 권장합니다."

    def _create_empty_result(self, round_id: Optional[str]) -> RoundAnalysisResult:
        """빈 결과 생성"""
        return RoundAnalysisResult(
            round_id=round_id or "unknown",
            sport_type=self.sport_type.value,
            matches=[],
            combinations=[],
            summary={"status": "no_data"},
            generated_at=datetime.now().isoformat(),
        )

    def generate_report(self, result: RoundAnalysisResult) -> str:
        """분석 리포트 생성"""

        report = f"""# 📊 토토 분석 리포트

**회차**: {result.round_id}
**종목**: {result.sport_type}
**생성 시각**: {result.generated_at}

---

## 📈 요약

- 총 경기 수: {result.summary.get("total_matches", 0)}
- 고신뢰도 경기: {result.summary.get("high_confidence_matches", 0)}
- Value Bet 발견: {result.summary.get("value_bets_found", 0)}
- 평균 AI 합의도: {result.summary.get("avg_consensus", 0):.1%}

**추천**: {result.summary.get("recommendation", "N/A")}

---

## 🏆 추천 조합

"""
        # 조합 추가
        combo_report = (
            self.combo_optimizer.format_combination_report(
                [
                    Combination(**c) if isinstance(c, dict) else c
                    for c in result.combinations[:3]
                ]
            )
            if result.combinations
            else "생성된 조합이 없습니다.\n"
        )

        report += combo_report

        # 경기별 요약
        report += "\n## 📋 경기별 분석 요약\n\n"
        report += "| 경기 | 예측 | 신뢰도 | 합의도 |\n"
        report += "|------|------|--------|--------|\n"

        for m in result.matches:
            synth = m.synthesized
            best_outcome = max(
                [
                    ("홈승", synth.get("home_win_prob", 0)),
                    ("무", synth.get("draw_prob", 0)),
                    ("원정승", synth.get("away_win_prob", 0)),
                ],
                key=lambda x: x[1],
            )
            report += f"| {m.home_team} vs {m.away_team} | "
            report += f"{best_outcome[0]} ({best_outcome[1]:.0%}) | "
            report += f"{m.confidence:.0%} | {m.consensus:.0%} |\n"

        return report


# 편의 함수
async def quick_analyze(sport: str = "soccer") -> Dict:
    """빠른 분석 (오늘 경기)"""
    sport_type = SportType.SOCCER if sport == "soccer" else SportType.BASKETBALL
    pipeline = OddsPipeline(sport_type=sport_type)
    result = await pipeline.analyze_round()
    return (
        asdict(result) if hasattr(result, "__dataclass_fields__") else result.__dict__
    )


# 실행
if __name__ == "__main__":
    import sys

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    async def main():
        # 파이프라인 실행
        pipeline = OddsPipeline(sport_type=SportType.SOCCER)
        result = await pipeline.analyze_round()

        # 리포트 출력
        report = pipeline.generate_report(result)
        print(report)

        # JSON 저장
        output_path = (
            f"results/analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        os.makedirs("results", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2, default=str)

        print(f"\n📁 결과 저장: {output_path}")

    asyncio.run(main())
