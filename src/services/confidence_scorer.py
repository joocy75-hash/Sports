"""
AI 예측 신뢰도 스코어 시스템

평가 요소:
1. 모델 일치도 (40%) - 여러 모델 예측의 합의 수준
2. 데이터 품질 (20%) - 결측치, 데이터 신선도
3. 확률 분포 명확성 (20%) - 예측 확률이 뚜렷한가
4. 폼/모멘텀 일관성 (20%) - 최근 폼이 명확한가
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceResult:
    """신뢰도 계산 결과"""

    total_score: int  # 0-100
    model_agreement: float  # 모델 일치도 점수
    data_quality: float  # 데이터 품질 점수
    probability_clarity: float  # 확률 명확성 점수
    form_consistency: float  # 폼 일관성 점수
    confidence_level: str  # "높음", "중간", "낮음"
    recommendation_strength: str  # "강력 추천", "추천", "보류", "회피"


class ConfidenceScorer:
    """
    AI 예측 신뢰도 점수 계산기

    스포츠토토 배팅에서 각 예측의 신뢰도를 0-100으로 산출
    """

    # 가중치 설정
    WEIGHT_MODEL_AGREEMENT = 0.40
    WEIGHT_DATA_QUALITY = 0.20
    WEIGHT_PROBABILITY_CLARITY = 0.20
    WEIGHT_FORM_CONSISTENCY = 0.20

    def __init__(self):
        self.models_used: List[str] = []

    def calculate(
        self,
        prediction: Dict,
        home_stats: Optional[Dict] = None,
        away_stats: Optional[Dict] = None,
        model_predictions: Optional[List[Dict]] = None,
        recent_form: Optional[Dict] = None,
    ) -> ConfidenceResult:
        """
        종합 신뢰도 점수 계산

        Args:
            prediction: 최종 예측 결과 {'home': 0.45, 'draw': 0.30, 'away': 0.25}
            home_stats: 홈팀 통계 데이터
            away_stats: 원정팀 통계 데이터
            model_predictions: 각 모델별 예측 [{'home': 0.45, 'draw': 0.30, 'away': 0.25}, ...]
            recent_form: 최근 폼 데이터 {'home_form': 'WWDWL', 'away_form': 'LDLWW'}

        Returns:
            ConfidenceResult: 신뢰도 계산 결과
        """
        # 1. 모델 일치도 점수 (40%)
        model_agreement = self._calculate_model_agreement(prediction, model_predictions)

        # 2. 데이터 품질 점수 (20%)
        data_quality = self._calculate_data_quality(home_stats, away_stats)

        # 3. 확률 분포 명확성 (20%)
        probability_clarity = self._calculate_probability_clarity(prediction)

        # 4. 폼 일관성 (20%)
        form_consistency = self._calculate_form_consistency(recent_form)

        # 종합 점수 계산
        total_score = int(
            model_agreement * self.WEIGHT_MODEL_AGREEMENT * 100
            + data_quality * self.WEIGHT_DATA_QUALITY * 100
            + probability_clarity * self.WEIGHT_PROBABILITY_CLARITY * 100
            + form_consistency * self.WEIGHT_FORM_CONSISTENCY * 100
        )

        # 신뢰도 레벨 결정
        confidence_level = self._determine_confidence_level(total_score)
        recommendation_strength = self._determine_recommendation_strength(
            total_score, prediction
        )

        return ConfidenceResult(
            total_score=min(100, max(0, total_score)),
            model_agreement=round(model_agreement * 100, 1),
            data_quality=round(data_quality * 100, 1),
            probability_clarity=round(probability_clarity * 100, 1),
            form_consistency=round(form_consistency * 100, 1),
            confidence_level=confidence_level,
            recommendation_strength=recommendation_strength,
        )

    def _calculate_model_agreement(
        self, prediction: Dict, model_predictions: Optional[List[Dict]]
    ) -> float:
        """
        모델 일치도 계산

        여러 모델이 같은 결과를 예측하면 일치도 높음
        모델이 없으면 예측 확률의 명확성으로 대체
        """
        if not model_predictions or len(model_predictions) < 2:
            # 단일 모델: 예측 확률의 최대값을 기반으로 계산
            if prediction:
                probs = prediction.get("probabilities", prediction)
                max_prob = max(
                    probs.get("home", 0), probs.get("draw", 0), probs.get("away", 0)
                )
                # 최대 확률이 높을수록 일치도 높음 (40% ~ 80% -> 0.5 ~ 1.0)
                return min(1.0, max(0.5, (max_prob - 0.33) * 2.5))
            return 0.5

        # 다중 모델: 예측 결과의 표준편차로 일치도 계산
        home_probs = [p.get("home", 0.33) for p in model_predictions]
        draw_probs = [p.get("draw", 0.33) for p in model_predictions]
        away_probs = [p.get("away", 0.33) for p in model_predictions]

        # 표준편차가 낮을수록 일치도 높음
        avg_std = np.mean([np.std(home_probs), np.std(draw_probs), np.std(away_probs)])

        # std 0 -> 1.0, std 0.2 -> 0.0
        agreement = max(0, 1 - avg_std * 5)
        return agreement

    def _calculate_data_quality(
        self, home_stats: Optional[Dict], away_stats: Optional[Dict]
    ) -> float:
        """
        데이터 품질 점수 계산

        - 통계 데이터 존재 여부
        - 필수 필드 완성도
        """
        if not home_stats and not away_stats:
            return 0.3  # 데이터 없음: 기본값

        quality_score = 0.0

        # 필수 필드 체크
        required_fields = ["goals_scored_avg", "goals_conceded_avg", "momentum"]
        optional_fields = ["xg", "xga", "recent_form", "home_record", "away_record"]

        for stats in [home_stats, away_stats]:
            if not stats:
                continue

            # 필수 필드 (60%)
            for field in required_fields:
                if stats.get(field) is not None:
                    quality_score += 0.1

            # 선택 필드 (40%)
            for field in optional_fields:
                if stats.get(field) is not None:
                    quality_score += 0.04

        return min(1.0, quality_score)

    def _calculate_probability_clarity(self, prediction: Dict) -> float:
        """
        확률 분포 명확성 계산

        - 한 결과가 압도적으로 높으면 명확함
        - 3개 결과가 비슷하면 불명확
        """
        if not prediction:
            return 0.5

        probs = prediction.get("probabilities", prediction)

        p_home = probs.get("home", 0.33)
        p_draw = probs.get("draw", 0.33)
        p_away = probs.get("away", 0.33)

        # 최대 확률
        max_prob = max(p_home, p_draw, p_away)

        # 2위와의 격차
        sorted_probs = sorted([p_home, p_draw, p_away], reverse=True)
        gap = sorted_probs[0] - sorted_probs[1]

        # 명확성 점수: 최대 확률 및 격차 기반
        # 최대 확률 50%+, 격차 15%+ -> 높은 명확성
        clarity = 0.0

        if max_prob >= 0.60:
            clarity += 0.5
        elif max_prob >= 0.45:
            clarity += 0.3
        else:
            clarity += 0.1

        if gap >= 0.20:
            clarity += 0.5
        elif gap >= 0.10:
            clarity += 0.3
        else:
            clarity += 0.1

        return min(1.0, clarity)

    def _calculate_form_consistency(self, recent_form: Optional[Dict]) -> float:
        """
        최근 폼 일관성 계산

        - 최근 경기 결과가 일관되면 높음
        - WWWWW -> 일관성 높음
        - WLDWL -> 일관성 낮음
        """
        if not recent_form:
            return 0.5  # 데이터 없음: 중간값

        home_form = recent_form.get("home_form", "")
        away_form = recent_form.get("away_form", "")

        def calculate_form_score(form: str) -> float:
            if not form or len(form) < 3:
                return 0.5

            # W=승, D=무, L=패 카운트
            wins = form.count("W")
            draws = form.count("D")
            losses = form.count("L")

            total = len(form)

            # 일관성: 가장 많은 결과의 비율
            max_count = max(wins, draws, losses)
            consistency = max_count / total

            # 최근 경기 가중치 (최근 결과가 더 중요)
            recent_weight = 0.0
            if len(form) >= 3:
                recent_3 = form[:3]  # 가장 최근 3경기
                recent_wins = recent_3.count("W")
                recent_losses = recent_3.count("L")

                if recent_wins >= 2 or recent_losses >= 2:
                    recent_weight = 0.2

            return min(1.0, consistency + recent_weight)

        home_score = calculate_form_score(home_form)
        away_score = calculate_form_score(away_form)

        return (home_score + away_score) / 2

    def _determine_confidence_level(self, total_score: int) -> str:
        """신뢰도 레벨 결정"""
        if total_score >= 75:
            return "높음"
        elif total_score >= 50:
            return "중간"
        else:
            return "낮음"

    def _determine_recommendation_strength(
        self, total_score: int, prediction: Dict
    ) -> str:
        """추천 강도 결정"""
        probs = prediction.get("probabilities", prediction)
        max_prob = max(probs.get("home", 0), probs.get("draw", 0), probs.get("away", 0))

        if total_score >= 75 and max_prob >= 0.55:
            return "강력 추천"
        elif total_score >= 60 and max_prob >= 0.45:
            return "추천"
        elif total_score >= 45:
            return "보류"
        else:
            return "회피"


class MarkingRecommender:
    """
    토토 마킹 추천기

    신뢰도와 확률을 기반으로 단통/복수/지우개 마킹 추천
    """

    def __init__(self, confidence_scorer: Optional[ConfidenceScorer] = None):
        self.scorer = confidence_scorer or ConfidenceScorer()

    def recommend_marking(self, prediction: Dict, confidence: ConfidenceResult) -> Dict:
        """
        단일 경기 마킹 추천

        Returns:
            {
                'type': 'single' | 'double' | 'triple',
                'marks': ['H'] or ['H', 'D'] or ['H', 'D', 'A'],
                'icon': '🔒' | '🛡️' | '💣',
                'reason': str
            }
        """
        probs = prediction.get("probabilities", prediction)
        p_home = probs.get("home", 0.33)
        p_draw = probs.get("draw", 0.33)
        p_away = probs.get("away", 0.33)

        score = confidence.total_score

        # 확률 순위
        prob_ranking = sorted(
            [("H", p_home), ("D", p_draw), ("A", p_away)],
            key=lambda x: x[1],
            reverse=True,
        )

        top_choice, top_prob = prob_ranking[0]
        second_choice, second_prob = prob_ranking[1]

        # 1. 단통 조건: 신뢰도 70%+ AND 최대 확률 55%+
        if score >= 70 and top_prob >= 0.55:
            return {
                "type": "single",
                "marks": [top_choice],
                "icon": "🔒",
                "reason": f"신뢰도 {score}%, 확률 {top_prob * 100:.0f}% (단통)",
            }

        # 2. 복수 마킹 조건: 신뢰도 50%+ AND 상위 2개 합 75%+
        if score >= 50 and (top_prob + second_prob >= 0.75):
            return {
                "type": "double",
                "marks": [top_choice, second_choice],
                "icon": "🛡️",
                "reason": f"상위 2개 합 {(top_prob + second_prob) * 100:.0f}% (복수)",
            }

        # 3. 지우개 (Triple)
        return {
            "type": "triple",
            "marks": ["H", "D", "A"],
            "icon": "💣",
            "reason": f"불확실 (신뢰도 {score}%, 최대 확률 {top_prob * 100:.0f}%)",
        }


def get_marking_strategy_for_matches(matches: List[Dict], budget: int = 100000) -> Dict:
    """
    14경기 전체에 대한 마킹 전략 수립

    Args:
        matches: 경기별 예측 리스트
        budget: 예산 (원)

    Returns:
        {
            'strategy': [...],
            'total_combinations': int,
            'total_cost': int,
            'expected_roi': float
        }
    """
    scorer = ConfidenceScorer()
    recommender = MarkingRecommender(scorer)

    strategy = []
    combinations = 1

    for match in matches:
        prediction = match.get("prediction", {})
        confidence = scorer.calculate(
            prediction,
            home_stats=match.get("home_stats"),
            away_stats=match.get("away_stats"),
            recent_form=match.get("recent_form"),
        )

        marking = recommender.recommend_marking(prediction, confidence)

        strategy.append(
            {
                "match_id": match.get("match_id"),
                "home": match.get("home_team"),
                "away": match.get("away_team"),
                "marking": marking,
                "confidence": confidence.total_score,
            }
        )

        # 조합 수 계산
        combinations *= len(marking["marks"])

    total_cost = combinations * 1000  # 1조합당 1000원

    # 예산 초과 시 조정 필요 알림
    budget_ok = total_cost <= budget

    return {
        "strategy": strategy,
        "total_combinations": combinations,
        "total_cost": total_cost,
        "budget_ok": budget_ok,
        "budget": budget,
        "message": "예산 내"
        if budget_ok
        else f"예산 초과! {total_cost - budget}원 초과",
    }
