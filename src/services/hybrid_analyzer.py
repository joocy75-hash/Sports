"""
HybridAnalyzer - 모든 분석 모델 통합

LLM AI (5개) + LightGBM + 통계 앙상블 (4개)를 결합하여
가장 정확한 예측을 생성합니다.

가중치:
- LLM AI 앙상블: 50%
- LightGBM ML: 25%
- 통계 앙상블: 25%
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ModelPrediction:
    """개별 모델 예측"""

    model_name: str
    model_type: str  # 'llm', 'ml', 'statistical'
    home_prob: float
    draw_prob: float
    away_prob: float
    confidence: float
    weight: float
    reasoning: str = ""


@dataclass
class HybridResult:
    """하이브리드 분석 결과"""

    # 최종 확률
    home_prob: float
    draw_prob: float
    away_prob: float

    # 예측
    predicted_outcome: str  # 'home_win', 'draw', 'away_win'
    predicted_outcome_kr: str  # '홈승', '무', '원정승'

    # 신뢰도
    overall_confidence: float
    consensus_score: float  # 모델 간 합의도

    # 개별 모델 결과
    llm_prediction: Dict
    ml_prediction: Dict
    statistical_prediction: Dict
    all_models: List[ModelPrediction]

    # 메타데이터
    analyzed_at: str
    analysis_time_ms: int

    def to_dict(self) -> Dict:
        result = asdict(self)
        result["all_models"] = [asdict(m) for m in self.all_models]
        return result


class HybridAnalyzer:
    """
    하이브리드 분석기

    3가지 분석 계층을 통합:
    1. LLM AI 분석 (GPT, Claude, Gemini, Kimi, DeepSeek)
    2. LightGBM ML 모델
    3. 통계 앙상블 (Poisson, ELO, Form, H2H)
    """

    # 가중치 설정
    WEIGHT_LLM = 0.50  # LLM AI 50%
    WEIGHT_ML = 0.25  # LightGBM 25%
    WEIGHT_STAT = 0.25  # 통계 앙상블 25%

    def __init__(self):
        """분석기 초기화"""
        self.llm_available = False
        self.ml_available = False
        self.stat_available = False

        # LLM AI 오케스트레이터
        try:
            from src.services.ai_orchestrator import AIOrchestrator

            self.ai_orchestrator = AIOrchestrator()
            self.llm_available = len(self.ai_orchestrator.get_active_analyzers()) > 0
            logger.info(
                f"✅ LLM AI 로드: {len(self.ai_orchestrator.get_active_analyzers())}개 활성"
            )
        except Exception as e:
            logger.warning(f"❌ LLM AI 로드 실패: {e}")
            self.ai_orchestrator = None

        # LightGBM ML 모델
        try:
            from src.ml.model import MatchPredictorML

            self.ml_model = MatchPredictorML()
            self.ml_model.load_model()
            if self.ml_model.model:
                self.ml_available = True
                logger.info("✅ LightGBM ML 모델 로드 완료")
            else:
                logger.warning("⚠️ LightGBM 모델 파일 없음")
        except Exception as e:
            logger.warning(f"❌ LightGBM 로드 실패: {e}")
            self.ml_model = None

        # 통계 앙상블
        try:
            from src.services.ensemble_model import EnsembleModel

            self.ensemble_model = EnsembleModel()
            self.stat_available = True
            logger.info("✅ 통계 앙상블 로드 (Poisson, ELO, Form, H2H)")
        except Exception as e:
            logger.warning(f"❌ 통계 앙상블 로드 실패: {e}")
            self.ensemble_model = None

        # 고급 통계 예측기
        try:
            from src.services.predictor import AdvancedStatisticalPredictor

            self.stat_predictor = AdvancedStatisticalPredictor()
        except Exception as e:
            logger.warning(f"⚠️ 고급 통계 예측기 로드 실패: {e}")
            self.stat_predictor = None

        # 가중치 동적 조정
        self._adjust_weights()

        logger.info(f"📊 HybridAnalyzer 초기화 완료")
        logger.info(
            f"   가중치: LLM={self.WEIGHT_LLM:.0%}, ML={self.WEIGHT_ML:.0%}, STAT={self.WEIGHT_STAT:.0%}"
        )

    def _adjust_weights(self):
        """사용 가능한 모델에 따라 가중치 동적 조정"""
        total_available = 0

        if self.llm_available:
            total_available += self.WEIGHT_LLM
        if self.ml_available:
            total_available += self.WEIGHT_ML
        if self.stat_available:
            total_available += self.WEIGHT_STAT

        if total_available == 0:
            logger.error("사용 가능한 모델이 없습니다!")
            return

        # 재정규화
        if not self.llm_available:
            self.WEIGHT_LLM = 0
        if not self.ml_available:
            self.WEIGHT_ML = 0
        if not self.stat_available:
            self.WEIGHT_STAT = 0

        # 합이 1이 되도록 조정
        total = self.WEIGHT_LLM + self.WEIGHT_ML + self.WEIGHT_STAT
        if total > 0:
            self.WEIGHT_LLM /= total
            self.WEIGHT_ML /= total
            self.WEIGHT_STAT /= total

    async def analyze(
        self,
        match_context: Dict,
        team_stats: Optional[Dict] = None,
        h2h_data: Optional[Dict] = None,
    ) -> HybridResult:
        """
        하이브리드 분석 실행

        Args:
            match_context: 경기 정보
                - match_id: str
                - home_team: str
                - away_team: str
                - league: str
                - match_time: str (optional)

            team_stats: 팀 통계 (optional)
                - home: {avg_gf, avg_ga, avg_sf, avg_sa, form, ...}
                - away: {avg_gf, avg_ga, avg_sf, avg_sa, form, ...}

            h2h_data: 상대 전적 (optional)
                - home_wins: int
                - away_wins: int
                - draws: int

        Returns:
            HybridResult
        """
        start_time = datetime.now()
        all_predictions: List[ModelPrediction] = []

        # 기본 통계 준비
        home_stats = team_stats.get("home", {}) if team_stats else {}
        away_stats = team_stats.get("away", {}) if team_stats else {}

        # 1. LLM AI 분석 (비동기)
        llm_result = await self._analyze_with_llm(match_context, home_stats, away_stats)
        if llm_result:
            all_predictions.append(llm_result)

        # 2. LightGBM ML 분석
        ml_result = self._analyze_with_ml(match_context, home_stats, away_stats)
        if ml_result:
            all_predictions.append(ml_result)

        # 3. 통계 앙상블 분석
        stat_results = self._analyze_with_statistical(home_stats, away_stats, h2h_data)
        all_predictions.extend(stat_results)

        # 4. 결과 합성
        final_result = self._synthesize_predictions(all_predictions)

        # 5. 메타데이터 추가
        end_time = datetime.now()
        analysis_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # 개별 모델 결과 정리
        llm_pred = {
            "available": llm_result is not None,
            "prediction": asdict(llm_result) if llm_result else None,
        }

        ml_pred = {
            "available": ml_result is not None,
            "prediction": asdict(ml_result) if ml_result else None,
        }

        stat_pred = {
            "available": len(stat_results) > 0,
            "predictions": [asdict(r) for r in stat_results],
        }

        return HybridResult(
            home_prob=final_result["home"],
            draw_prob=final_result["draw"],
            away_prob=final_result["away"],
            predicted_outcome=final_result["outcome"],
            predicted_outcome_kr=final_result["outcome_kr"],
            overall_confidence=final_result["confidence"],
            consensus_score=final_result["consensus"],
            llm_prediction=llm_pred,
            ml_prediction=ml_pred,
            statistical_prediction=stat_pred,
            all_models=all_predictions,
            analyzed_at=datetime.now().isoformat(),
            analysis_time_ms=analysis_time_ms,
        )

    async def _analyze_with_llm(
        self, match_context: Dict, home_stats: Dict, away_stats: Dict
    ) -> Optional[ModelPrediction]:
        """LLM AI 분석"""

        if not self.llm_available or not self.ai_orchestrator:
            return None

        try:
            # MatchContext 생성
            from src.services.ai.models import (
                MatchContext,
                SportType as AIModelSportType,
            )

            # sport_type 변환
            sport_str = match_context.get("sport_type", "soccer")
            if sport_str in ["basketball", "농구"]:
                sport_enum = AIModelSportType.BASKETBALL
            else:
                sport_enum = AIModelSportType.SOCCER

            context = MatchContext(
                match_id=match_context.get("match_id", 0)
                if isinstance(match_context.get("match_id"), int)
                else 0,
                home_team=match_context.get("home_team", ""),
                away_team=match_context.get("away_team", ""),
                league=match_context.get("league", ""),
                start_time=match_context.get(
                    "match_time", match_context.get("start_time", "")
                ),
                sport_type=sport_enum,
                home_stats=home_stats or None,
                away_stats=away_stats or None,
            )

            # AI 오케스트레이터 호출
            result = await self.ai_orchestrator.analyze_match(context)

            if result and result.consensus:
                probs = result.consensus.probabilities or {}
                return ModelPrediction(
                    model_name="LLM AI Ensemble",
                    model_type="llm",
                    home_prob=probs.get("home", 0.33),
                    draw_prob=probs.get("draw", 0.33),
                    away_prob=probs.get("away", 0.33),
                    confidence=result.consensus.confidence / 100
                    if result.consensus.confidence > 1
                    else result.consensus.confidence,
                    weight=self.WEIGHT_LLM,
                    reasoning=result.consensus.recommendation or "",
                )

        except Exception as e:
            logger.error(f"LLM 분석 오류: {e}")

        return None

    def _analyze_with_ml(
        self, match_context: Dict, home_stats: Dict, away_stats: Dict
    ) -> Optional[ModelPrediction]:
        """LightGBM ML 분석"""

        if not self.ml_available or not self.ml_model:
            return None

        try:
            probs = self.ml_model.predict_proba(
                home_stats={
                    "avg_gf": home_stats.get(
                        "avg_gf", home_stats.get("goals_scored_avg", 1.5)
                    ),
                    "avg_ga": home_stats.get(
                        "avg_ga", home_stats.get("goals_conceded_avg", 1.0)
                    ),
                    "avg_sf": home_stats.get("avg_sf", 12),
                    "avg_sa": home_stats.get("avg_sa", 10),
                },
                away_stats={
                    "avg_gf": away_stats.get(
                        "avg_gf", away_stats.get("goals_scored_avg", 1.2)
                    ),
                    "avg_ga": away_stats.get(
                        "avg_ga", away_stats.get("goals_conceded_avg", 1.5)
                    ),
                    "avg_sf": away_stats.get("avg_sf", 10),
                    "avg_sa": away_stats.get("avg_sa", 12),
                },
                league_name=match_context.get("league", "Unknown"),
            )

            if probs:
                return ModelPrediction(
                    model_name="LightGBM",
                    model_type="ml",
                    home_prob=probs.get("home", 0.33),
                    draw_prob=probs.get("draw", 0.33),
                    away_prob=probs.get("away", 0.33),
                    confidence=0.75,  # ML 모델 기본 신뢰도
                    weight=self.WEIGHT_ML,
                    reasoning="LightGBM 머신러닝 예측",
                )

        except Exception as e:
            logger.error(f"ML 분석 오류: {e}")

        return None

    def _analyze_with_statistical(
        self, home_stats: Dict, away_stats: Dict, h2h_data: Optional[Dict]
    ) -> List[ModelPrediction]:
        """통계 앙상블 분석"""

        results = []

        if not self.stat_available or not self.ensemble_model:
            return results

        try:
            # 앙상블 모델 호출
            ensemble_pred = self.ensemble_model.predict(
                home_avg_goals=home_stats.get(
                    "avg_gf", home_stats.get("goals_scored_avg", 1.5)
                ),
                away_avg_goals=away_stats.get(
                    "avg_gf", away_stats.get("goals_scored_avg", 1.2)
                ),
                home_avg_conceded=home_stats.get(
                    "avg_ga", home_stats.get("goals_conceded_avg", 1.0)
                ),
                away_avg_conceded=away_stats.get(
                    "avg_ga", away_stats.get("goals_conceded_avg", 1.5)
                ),
                home_elo=home_stats.get("elo", 1500),
                away_elo=away_stats.get("elo", 1500),
                home_form=home_stats.get("form", ""),
                away_form=away_stats.get("form", ""),
                h2h_home_wins=h2h_data.get("home_wins", 0) if h2h_data else 0,
                h2h_away_wins=h2h_data.get("away_wins", 0) if h2h_data else 0,
                h2h_draws=h2h_data.get("draws", 0) if h2h_data else 0,
                h2h_home_goals=h2h_data.get("home_goals", 0) if h2h_data else 0,
                h2h_away_goals=h2h_data.get("away_goals", 0) if h2h_data else 0,
            )

            if ensemble_pred:
                # 전체 앙상블 결과
                results.append(
                    ModelPrediction(
                        model_name="Statistical Ensemble",
                        model_type="statistical",
                        home_prob=ensemble_pred.home_prob,
                        draw_prob=ensemble_pred.draw_prob,
                        away_prob=ensemble_pred.away_prob,
                        confidence=ensemble_pred.confidence,
                        weight=self.WEIGHT_STAT,
                        reasoning=f"합의도: {ensemble_pred.agreement_score:.0%}",
                    )
                )

                # 개별 모델 결과도 추가 (가중치 0 - 참조용)
                for mp in ensemble_pred.model_predictions:
                    results.append(
                        ModelPrediction(
                            model_name=mp.model_name,
                            model_type="statistical_sub",
                            home_prob=mp.home_prob,
                            draw_prob=mp.draw_prob,
                            away_prob=mp.away_prob,
                            confidence=mp.confidence,
                            weight=0,  # 참조용이므로 가중치 0
                            reasoning="",
                        )
                    )

        except Exception as e:
            logger.error(f"통계 분석 오류: {e}")

        # 고급 통계 예측기 사용
        if self.stat_predictor and home_stats and away_stats:
            try:
                stat_result = self.stat_predictor.predict_score_probabilities(
                    home_stats={
                        "goals_scored_avg": home_stats.get("avg_gf", 1.5),
                        "goals_conceded_avg": home_stats.get("avg_ga", 1.0),
                        "momentum": home_stats.get("momentum", 1.0),
                    },
                    away_stats={
                        "goals_scored_avg": away_stats.get("avg_gf", 1.2),
                        "goals_conceded_avg": away_stats.get("avg_ga", 1.5),
                        "momentum": away_stats.get("momentum", 1.0),
                    },
                )

                if stat_result:
                    probs = stat_result.get("probabilities", {})
                    results.append(
                        ModelPrediction(
                            model_name="Poisson Distribution",
                            model_type="statistical_sub",
                            home_prob=probs.get("home", 0.33),
                            draw_prob=probs.get("draw", 0.33),
                            away_prob=probs.get("away", 0.33),
                            confidence=0.70,
                            weight=0,  # 이미 앙상블에 포함되어 있으므로
                            reasoning=f"예상 스코어: {stat_result.get('expected_score', {})}",
                        )
                    )
            except Exception as e:
                logger.warning(f"고급 통계 예측 오류: {e}")

        return results

    def _synthesize_predictions(self, predictions: List[ModelPrediction]) -> Dict:
        """모든 예측 합성"""

        if not predictions:
            return {
                "home": 0.33,
                "draw": 0.34,
                "away": 0.33,
                "outcome": "draw",
                "outcome_kr": "무",
                "confidence": 0.5,
                "consensus": 0.5,
            }

        # 가중치가 있는 예측만 필터
        weighted_predictions = [p for p in predictions if p.weight > 0]

        if not weighted_predictions:
            weighted_predictions = predictions[:3]  # 상위 3개 사용
            for p in weighted_predictions:
                p.weight = 1.0 / len(weighted_predictions)

        # 가중 평균 계산
        total_weight = sum(p.weight for p in weighted_predictions)

        home_prob = (
            sum(p.home_prob * p.weight for p in weighted_predictions) / total_weight
        )
        draw_prob = (
            sum(p.draw_prob * p.weight for p in weighted_predictions) / total_weight
        )
        away_prob = (
            sum(p.away_prob * p.weight for p in weighted_predictions) / total_weight
        )

        # 정규화
        total = home_prob + draw_prob + away_prob
        if total > 0:
            home_prob /= total
            draw_prob /= total
            away_prob /= total

        # 예측 결과
        probs = {"home": home_prob, "draw": draw_prob, "away": away_prob}
        outcome = max(probs, key=probs.get)
        outcome_map = {
            "home": ("home_win", "홈승"),
            "draw": ("draw", "무"),
            "away": ("away_win", "원정승"),
        }

        # 신뢰도: 가중 평균 (0~1 범위로 제한)
        confidence = (
            sum(p.confidence * p.weight for p in weighted_predictions) / total_weight
        )
        # 신뢰도가 1보다 큰 경우 (예: 퍼센트로 주어진 경우) 정규화
        if confidence > 1:
            confidence = confidence / 100
        confidence = max(0, min(1, confidence))  # 0~1 범위로 클램핑

        # 합의도: 표준편차 기반
        import statistics

        if len(weighted_predictions) >= 2:
            home_probs = [p.home_prob for p in weighted_predictions]
            std = statistics.stdev(home_probs)
            consensus = max(0, 1 - std * 3)
        else:
            consensus = 0.7

        return {
            "home": round(home_prob, 4),
            "draw": round(draw_prob, 4),
            "away": round(away_prob, 4),
            "outcome": outcome_map[outcome][0],
            "outcome_kr": outcome_map[outcome][1],
            "confidence": round(confidence, 4),
            "consensus": round(consensus, 4),
        }

    async def analyze_batch(
        self,
        matches: List[Dict],
        team_stats_map: Optional[Dict[str, Dict]] = None,
        h2h_map: Optional[Dict[str, Dict]] = None,
        max_concurrent: int = 5,
    ) -> List[HybridResult]:
        """여러 경기 일괄 분석"""

        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(match: Dict) -> HybridResult:
            async with semaphore:
                match_id = match.get("match_id", "")
                team_stats = (
                    team_stats_map.get(match_id, {}) if team_stats_map else None
                )
                h2h = h2h_map.get(match_id, {}) if h2h_map else None
                return await self.analyze(match, team_stats, h2h)

        results = await asyncio.gather(
            *[analyze_with_limit(m) for m in matches], return_exceptions=True
        )

        # 예외 처리
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"경기 {i + 1} 분석 오류: {result}")
                continue
            valid_results.append(result)

        return valid_results

    def get_model_status(self) -> Dict:
        """모델 상태 확인"""
        return {
            "llm_ai": {
                "available": self.llm_available,
                "weight": self.WEIGHT_LLM,
                "models": self.ai_orchestrator.get_active_analyzers()
                if self.ai_orchestrator
                else [],
            },
            "ml": {
                "available": self.ml_available,
                "weight": self.WEIGHT_ML,
                "model": "LightGBM" if self.ml_available else None,
            },
            "statistical": {
                "available": self.stat_available,
                "weight": self.WEIGHT_STAT,
                "models": ["Poisson", "ELO", "Form", "H2H"]
                if self.stat_available
                else [],
            },
        }

    def get_status(self) -> Dict:
        """모델 상태 간단 요약 (호환성용)"""
        return {
            "ai_orchestrator": self.llm_available,
            "ml_predictor": self.ml_available,
            "ensemble_model": self.stat_available,
        }


# 싱글톤 인스턴스
_hybrid_analyzer: Optional[HybridAnalyzer] = None


def get_hybrid_analyzer() -> HybridAnalyzer:
    """싱글톤 HybridAnalyzer 반환"""
    global _hybrid_analyzer
    if _hybrid_analyzer is None:
        _hybrid_analyzer = HybridAnalyzer()
    return _hybrid_analyzer


# 테스트
if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)

    async def test():
        analyzer = HybridAnalyzer()

        # 모델 상태 확인
        status = analyzer.get_model_status()
        print("\n📊 모델 상태:")
        print(
            f"  LLM AI: {status['llm_ai']['available']} ({status['llm_ai']['weight']:.0%})"
        )
        print(f"  ML: {status['ml']['available']} ({status['ml']['weight']:.0%})")
        print(
            f"  통계: {status['statistical']['available']} ({status['statistical']['weight']:.0%})"
        )

        # 테스트 분석
        result = await analyzer.analyze(
            match_context={
                "match_id": "test_001",
                "home_team": "Manchester United",
                "away_team": "Liverpool",
                "league": "Premier League",
            },
            team_stats={
                "home": {"avg_gf": 1.8, "avg_ga": 1.0, "form": "WWDLW"},
                "away": {"avg_gf": 2.2, "avg_ga": 0.8, "form": "WWWWW"},
            },
            h2h_data={"home_wins": 3, "away_wins": 5, "draws": 2},
        )

        print(f"\n🎯 분석 결과:")
        print(f"  홈승: {result.home_prob:.1%}")
        print(f"  무: {result.draw_prob:.1%}")
        print(f"  원정승: {result.away_prob:.1%}")
        print(f"  예측: {result.predicted_outcome_kr}")
        print(f"  신뢰도: {result.overall_confidence:.1%}")
        print(f"  합의도: {result.consensus_score:.1%}")
        print(f"  분석 시간: {result.analysis_time_ms}ms")

    asyncio.run(test())
