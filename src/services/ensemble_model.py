"""
A-02: 앙상블 ML 모델
여러 예측 모델을 결합하여 더 정확한 예측을 제공합니다.
- 포아송 분포 모델
- ELO 레이팅 모델
- 폼 기반 모델
- 상대전적 기반 모델
"""

import math
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio


class PredictionOutcome(Enum):
    HOME = "home"
    DRAW = "draw"
    AWAY = "away"


@dataclass
class ModelPrediction:
    """개별 모델 예측 결과"""
    model_name: str
    home_prob: float
    draw_prob: float
    away_prob: float
    confidence: float
    weight: float = 1.0


@dataclass
class EnsemblePrediction:
    """앙상블 예측 결과"""
    home_prob: float
    draw_prob: float
    away_prob: float
    predicted_outcome: PredictionOutcome
    confidence: float
    expected_home_goals: float
    expected_away_goals: float
    model_predictions: List[ModelPrediction]
    agreement_score: float  # 모델 간 일치도 (0-1)


class PoissonModel:
    """포아송 분포 기반 예측 모델"""

    def __init__(self):
        self.name = "Poisson"
        self.weight = 0.30  # 30% 가중치

    def predict(
        self,
        home_avg_goals: float,
        away_avg_goals: float,
        home_avg_conceded: float,
        away_avg_conceded: float,
        league_avg_goals: float = 2.5
    ) -> ModelPrediction:
        """포아송 분포로 경기 결과 예측"""
        # 예상 골 수 계산
        home_attack = home_avg_goals / league_avg_goals
        away_attack = away_avg_goals / league_avg_goals
        home_defense = home_avg_conceded / league_avg_goals
        away_defense = away_avg_conceded / league_avg_goals

        # 홈 이점 (약 10% 추가)
        home_advantage = 1.1

        expected_home = (home_attack * away_defense * league_avg_goals / 2) * home_advantage
        expected_away = away_attack * home_defense * league_avg_goals / 2

        # 각 스코어라인 확률 계산 (0-5골)
        home_win_prob = 0
        draw_prob = 0
        away_win_prob = 0

        for h in range(6):
            for a in range(6):
                prob = self._poisson_prob(h, expected_home) * self._poisson_prob(a, expected_away)
                if h > a:
                    home_win_prob += prob
                elif h == a:
                    draw_prob += prob
                else:
                    away_win_prob += prob

        # 정규화
        total = home_win_prob + draw_prob + away_win_prob
        if total > 0:
            home_win_prob /= total
            draw_prob /= total
            away_win_prob /= total

        # 신뢰도: 예상 골 수의 분산이 작을수록 높음
        variance = abs(expected_home - expected_away)
        confidence = min(90, 50 + variance * 10)

        return ModelPrediction(
            model_name=self.name,
            home_prob=round(home_win_prob * 100, 2),
            draw_prob=round(draw_prob * 100, 2),
            away_prob=round(away_win_prob * 100, 2),
            confidence=confidence,
            weight=self.weight
        )

    def _poisson_prob(self, k: int, lambda_: float) -> float:
        """포아송 확률 계산"""
        if lambda_ <= 0:
            return 1.0 if k == 0 else 0.0
        return (lambda_ ** k) * math.exp(-lambda_) / math.factorial(k)


class EloModel:
    """ELO 레이팅 기반 예측 모델"""

    def __init__(self):
        self.name = "ELO Rating"
        self.weight = 0.25  # 25% 가중치
        self.k_factor = 32
        self.home_advantage = 100  # ELO 홈 이점

    def predict(
        self,
        home_elo: float,
        away_elo: float,
        home_form_elo: float = 0,
        away_form_elo: float = 0
    ) -> ModelPrediction:
        """ELO 레이팅으로 승률 예측"""
        # 폼 반영 ELO
        effective_home = home_elo + home_form_elo + self.home_advantage
        effective_away = away_elo + away_form_elo

        # 기대 승률 계산
        elo_diff = effective_home - effective_away
        home_expected = 1 / (1 + 10 ** (-elo_diff / 400))
        away_expected = 1 - home_expected

        # 무승부 확률 추정 (ELO 차이가 작을수록 높음)
        draw_base = 0.25  # 기본 무승부 확률
        elo_factor = max(0, 1 - abs(elo_diff) / 400) * 0.15
        draw_prob = draw_base + elo_factor

        # 조정된 승패 확률
        remaining = 1 - draw_prob
        home_prob = home_expected * remaining
        away_prob = away_expected * remaining

        # 신뢰도: ELO 차이가 클수록 높음
        confidence = min(90, 50 + abs(elo_diff) / 10)

        return ModelPrediction(
            model_name=self.name,
            home_prob=round(home_prob * 100, 2),
            draw_prob=round(draw_prob * 100, 2),
            away_prob=round(away_prob * 100, 2),
            confidence=confidence,
            weight=self.weight
        )


class FormModel:
    """최근 폼 기반 예측 모델"""

    def __init__(self):
        self.name = "Recent Form"
        self.weight = 0.25  # 25% 가중치

    def predict(
        self,
        home_form: str,  # "WWDLW" 형태
        away_form: str,
        home_home_form: str = "",  # 홈에서의 폼
        away_away_form: str = ""   # 원정에서의 폼
    ) -> ModelPrediction:
        """최근 폼으로 예측"""
        home_points = self._form_to_points(home_form)
        away_points = self._form_to_points(away_form)

        # 장소별 폼 반영 (있으면)
        if home_home_form:
            home_points = home_points * 0.6 + self._form_to_points(home_home_form) * 0.4
        if away_away_form:
            away_points = away_points * 0.6 + self._form_to_points(away_away_form) * 0.4

        # 홈 이점 추가
        home_points *= 1.1

        total = home_points + away_points
        if total == 0:
            home_prob = away_prob = 0.35
            draw_prob = 0.30
        else:
            home_ratio = home_points / total
            away_ratio = away_points / total

            # 무승부 확률 (비슷할수록 높음)
            similarity = 1 - abs(home_ratio - away_ratio)
            draw_prob = 0.2 + similarity * 0.15

            remaining = 1 - draw_prob
            home_prob = home_ratio * remaining
            away_prob = away_ratio * remaining

        # 신뢰도: 폼 차이가 클수록 높음
        confidence = min(85, 45 + abs(home_points - away_points) * 5)

        return ModelPrediction(
            model_name=self.name,
            home_prob=round(home_prob * 100, 2),
            draw_prob=round(draw_prob * 100, 2),
            away_prob=round(away_prob * 100, 2),
            confidence=confidence,
            weight=self.weight
        )

    def _form_to_points(self, form: str) -> float:
        """폼 문자열을 점수로 변환 (최근 경기에 더 높은 가중치)"""
        if not form:
            return 5  # 기본값

        weights = [1.5, 1.3, 1.1, 0.9, 0.7][:len(form)]
        points = 0
        total_weight = 0

        for i, result in enumerate(form):
            w = weights[i] if i < len(weights) else 0.5
            if result.upper() == 'W':
                points += 3 * w
            elif result.upper() == 'D':
                points += 1 * w
            total_weight += w

        return points / total_weight if total_weight else 5


class H2HModel:
    """상대전적 기반 예측 모델"""

    def __init__(self):
        self.name = "Head-to-Head"
        self.weight = 0.20  # 20% 가중치

    def predict(
        self,
        home_wins: int,
        away_wins: int,
        draws: int,
        home_goals: int,
        away_goals: int,
        recent_trend: str = "stable"  # "home_improving", "away_improving", "stable"
    ) -> ModelPrediction:
        """상대전적으로 예측"""
        total = home_wins + away_wins + draws
        if total == 0:
            return ModelPrediction(
                model_name=self.name,
                home_prob=40.0,
                draw_prob=25.0,
                away_prob=35.0,
                confidence=30,
                weight=self.weight
            )

        # 기본 확률
        home_prob = home_wins / total
        away_prob = away_wins / total
        draw_prob = draws / total

        # 트렌드 반영
        trend_adj = 0.05
        if recent_trend == "home_improving":
            home_prob += trend_adj
            away_prob -= trend_adj
        elif recent_trend == "away_improving":
            away_prob += trend_adj
            home_prob -= trend_adj

        # 홈 이점 (상대전적에서도 홈에서 더 유리)
        home_prob *= 1.05
        away_prob *= 0.95

        # 정규화
        total_prob = home_prob + draw_prob + away_prob
        home_prob /= total_prob
        draw_prob /= total_prob
        away_prob /= total_prob

        # 신뢰도: 경기 수가 많을수록 높음
        confidence = min(80, 30 + total * 5)

        return ModelPrediction(
            model_name=self.name,
            home_prob=round(home_prob * 100, 2),
            draw_prob=round(draw_prob * 100, 2),
            away_prob=round(away_prob * 100, 2),
            confidence=confidence,
            weight=self.weight
        )


class EnsembleModel:
    """앙상블 예측 모델"""

    def __init__(self):
        self.poisson = PoissonModel()
        self.elo = EloModel()
        self.form = FormModel()
        self.h2h = H2HModel()

    def predict(
        self,
        # Poisson 파라미터
        home_avg_goals: float = 1.5,
        away_avg_goals: float = 1.3,
        home_avg_conceded: float = 1.0,
        away_avg_conceded: float = 1.2,
        # ELO 파라미터
        home_elo: float = 1500,
        away_elo: float = 1500,
        home_form_elo: float = 0,
        away_form_elo: float = 0,
        # Form 파라미터
        home_form: str = "",
        away_form: str = "",
        home_home_form: str = "",
        away_away_form: str = "",
        # H2H 파라미터
        h2h_home_wins: int = 0,
        h2h_away_wins: int = 0,
        h2h_draws: int = 0,
        h2h_home_goals: int = 0,
        h2h_away_goals: int = 0,
        h2h_trend: str = "stable",
        # 모델 가중치 커스텀
        model_weights: Optional[Dict[str, float]] = None
    ) -> EnsemblePrediction:
        """앙상블 예측 수행"""
        predictions = []

        # 각 모델 예측
        poisson_pred = self.poisson.predict(
            home_avg_goals, away_avg_goals,
            home_avg_conceded, away_avg_conceded
        )
        predictions.append(poisson_pred)

        elo_pred = self.elo.predict(
            home_elo, away_elo,
            home_form_elo, away_form_elo
        )
        predictions.append(elo_pred)

        if home_form or away_form:
            form_pred = self.form.predict(
                home_form, away_form,
                home_home_form, away_away_form
            )
            predictions.append(form_pred)

        if h2h_home_wins + h2h_away_wins + h2h_draws > 0:
            h2h_pred = self.h2h.predict(
                h2h_home_wins, h2h_away_wins, h2h_draws,
                h2h_home_goals, h2h_away_goals, h2h_trend
            )
            predictions.append(h2h_pred)

        # 가중치 적용
        if model_weights:
            for pred in predictions:
                if pred.model_name in model_weights:
                    pred.weight = model_weights[pred.model_name]

        # 가중 평균 계산
        total_weight = sum(p.weight * p.confidence for p in predictions)
        if total_weight == 0:
            total_weight = 1

        home_prob = sum(p.home_prob * p.weight * p.confidence for p in predictions) / total_weight
        draw_prob = sum(p.draw_prob * p.weight * p.confidence for p in predictions) / total_weight
        away_prob = sum(p.away_prob * p.weight * p.confidence for p in predictions) / total_weight

        # 정규화
        prob_sum = home_prob + draw_prob + away_prob
        home_prob = home_prob / prob_sum * 100
        draw_prob = draw_prob / prob_sum * 100
        away_prob = away_prob / prob_sum * 100

        # 예측 결과
        if home_prob > draw_prob and home_prob > away_prob:
            outcome = PredictionOutcome.HOME
        elif away_prob > home_prob and away_prob > draw_prob:
            outcome = PredictionOutcome.AWAY
        else:
            outcome = PredictionOutcome.DRAW

        # 모델 간 일치도
        agreement = self._calculate_agreement(predictions)

        # 최종 신뢰도
        avg_confidence = sum(p.confidence for p in predictions) / len(predictions)
        final_confidence = avg_confidence * (0.7 + 0.3 * agreement)

        # 예상 골 수
        expected_home = home_avg_goals * (1 + (home_elo - 1500) / 1000)
        expected_away = away_avg_goals * (1 + (away_elo - 1500) / 1000)

        return EnsemblePrediction(
            home_prob=round(home_prob, 2),
            draw_prob=round(draw_prob, 2),
            away_prob=round(away_prob, 2),
            predicted_outcome=outcome,
            confidence=round(final_confidence, 1),
            expected_home_goals=round(expected_home, 2),
            expected_away_goals=round(expected_away, 2),
            model_predictions=predictions,
            agreement_score=round(agreement, 2)
        )

    def _calculate_agreement(self, predictions: List[ModelPrediction]) -> float:
        """모델 간 일치도 계산"""
        if len(predictions) < 2:
            return 1.0

        # 각 모델의 예측 결과
        outcomes = []
        for p in predictions:
            if p.home_prob > p.draw_prob and p.home_prob > p.away_prob:
                outcomes.append("home")
            elif p.away_prob > p.home_prob and p.away_prob > p.draw_prob:
                outcomes.append("away")
            else:
                outcomes.append("draw")

        # 가장 많은 예측과의 일치율
        from collections import Counter
        counts = Counter(outcomes)
        most_common = counts.most_common(1)[0][1]
        return most_common / len(predictions)

    def to_dict(self, prediction: EnsemblePrediction) -> Dict[str, Any]:
        """예측 결과를 딕셔너리로 변환"""
        return {
            "home_prob": prediction.home_prob,
            "draw_prob": prediction.draw_prob,
            "away_prob": prediction.away_prob,
            "predicted_outcome": prediction.predicted_outcome.value,
            "confidence": prediction.confidence,
            "expected_home_goals": prediction.expected_home_goals,
            "expected_away_goals": prediction.expected_away_goals,
            "agreement_score": prediction.agreement_score,
            "model_predictions": [
                {
                    "model": p.model_name,
                    "home": p.home_prob,
                    "draw": p.draw_prob,
                    "away": p.away_prob,
                    "confidence": p.confidence,
                    "weight": p.weight
                }
                for p in prediction.model_predictions
            ]
        }


# 싱글톤 인스턴스
_model: Optional[EnsembleModel] = None


def get_ensemble_model() -> EnsembleModel:
    """싱글톤 모델 반환"""
    global _model
    if _model is None:
        _model = EnsembleModel()
    return _model


# 테스트
if __name__ == "__main__":
    model = EnsembleModel()

    # Liverpool vs Manchester United 예시
    prediction = model.predict(
        # 포아송
        home_avg_goals=2.1,
        away_avg_goals=1.4,
        home_avg_conceded=0.8,
        away_avg_conceded=1.2,
        # ELO
        home_elo=1850,
        away_elo=1720,
        home_form_elo=30,
        away_form_elo=-10,
        # 폼
        home_form="WWDWW",
        away_form="WLDWD",
        # H2H
        h2h_home_wins=5,
        h2h_away_wins=3,
        h2h_draws=2,
        h2h_home_goals=15,
        h2h_away_goals=10,
        h2h_trend="home_improving"
    )

    print("\n[앙상블 예측 결과]")
    print(f"  홈승: {prediction.home_prob}%")
    print(f"  무승부: {prediction.draw_prob}%")
    print(f"  원정승: {prediction.away_prob}%")
    print(f"  예측: {prediction.predicted_outcome.value}")
    print(f"  신뢰도: {prediction.confidence}%")
    print(f"  모델 일치도: {prediction.agreement_score}")

    print("\n[개별 모델 예측]")
    for mp in prediction.model_predictions:
        print(f"  {mp.model_name}: 홈 {mp.home_prob}%, 무 {mp.draw_prob}%, 원 {mp.away_prob}% (신뢰도 {mp.confidence}%)")
