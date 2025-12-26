"""
OddsCalculator - AI 예측 확률을 배당률로 변환

확률을 배당률로 변환하고, 오버라운드(마진)를 계산합니다.
"""

from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OddsResult:
    """배당률 계산 결과"""

    home_win_odds: float
    draw_odds: Optional[float]  # 축구만 해당
    away_win_odds: float
    overround: float  # 총 마진
    margin_percentage: float  # 마진 비율


class OddsCalculator:
    """
    확률 → 배당률 변환기

    AI가 예측한 확률을 시장 배당률로 변환합니다.
    마진을 적용하여 실제 베팅에 사용할 수 있는 배당률을 생성합니다.
    """

    def __init__(self, margin: float = 0.05):
        """
        Args:
            margin: 북메이커 마진 (기본 5%)
        """
        self.margin = margin

    def probability_to_odds(
        self, probabilities: Dict[str, float], apply_margin: bool = True
    ) -> Dict[str, float]:
        """
        확률 → 배당률 변환

        공식: 배당률 = 1 / (확률 × (1 + 마진))

        Args:
            probabilities: {
                'home_win': 0.45,
                'draw': 0.25,      # 축구만 (농구는 None 또는 0)
                'away_win': 0.30
            }
            apply_margin: 마진 적용 여부

        Returns:
            {
                'home_win_odds': 2.20,
                'draw_odds': 4.00,
                'away_win_odds': 3.33
            }
        """
        odds = {}
        margin_factor = (1 + self.margin) if apply_margin else 1.0

        for outcome, prob in probabilities.items():
            if prob is None or prob <= 0:
                odds[f"{outcome}_odds"] = None
                continue

            # 마진 적용
            adjusted_prob = prob * margin_factor

            # 배당률이 1.01 미만이 되지 않도록 보정
            if adjusted_prob >= 1.0:
                adjusted_prob = 0.99

            # 배당률 계산
            odds_value = round(1 / adjusted_prob, 2)

            # 최소 배당률 1.01 보장
            odds[f"{outcome}_odds"] = max(odds_value, 1.01)

        return odds

    def calculate_fair_odds(self, probabilities: Dict[str, float]) -> Dict[str, float]:
        """
        마진 없는 공정 배당률 계산

        Args:
            probabilities: 예측 확률 딕셔너리

        Returns:
            마진 없는 공정 배당률
        """
        return self.probability_to_odds(probabilities, apply_margin=False)

    def calculate_implied_probability(self, odds: float) -> float:
        """
        배당률 → 내재 확률 계산

        공식: 확률 = 1 / 배당률

        Args:
            odds: 배당률

        Returns:
            내재 확률 (0.0 ~ 1.0)
        """
        if odds <= 0:
            return 0.0
        return round(1 / odds, 4)

    def calculate_overround(self, odds_dict: Dict[str, float]) -> float:
        """
        오버라운드(북메이커 마진) 계산

        오버라운드 = 각 결과의 내재 확률 합계

        Returns:
            오버라운드 비율 (1.0 = 마진 없음, 1.05 = 5% 마진)
        """
        implied_probs = []

        for key, odds in odds_dict.items():
            if odds is not None and odds > 0:
                implied_probs.append(self.calculate_implied_probability(odds))

        if not implied_probs:
            return 0.0

        return round(sum(implied_probs), 4)

    def calculate_margin_percentage(self, odds_dict: Dict[str, float]) -> float:
        """
        마진 비율 계산 (%)

        Returns:
            마진 비율 (예: 0.05 = 5%)
        """
        overround = self.calculate_overround(odds_dict)
        if overround <= 0:
            return 0.0
        return round(overround - 1.0, 4)

    def remove_margin(self, odds_dict: Dict[str, float]) -> Dict[str, float]:
        """
        배당률에서 마진 제거하여 순수 확률 추정

        Args:
            odds_dict: 마진이 포함된 배당률

        Returns:
            마진 제거된 순수 확률
        """
        # 내재 확률 계산
        implied = {}
        for key, odds in odds_dict.items():
            if odds is not None and odds > 0:
                implied[key] = 1 / odds

        if not implied:
            return {}

        # 총합 계산 (오버라운드)
        total = sum(implied.values())

        # 정규화 (합 = 1.0)
        normalized = {key: round(prob / total, 4) for key, prob in implied.items()}

        return normalized

    def calculate_full_odds(self, probabilities: Dict[str, float]) -> OddsResult:
        """
        완전한 배당률 결과 계산

        Args:
            probabilities: {
                'home_win': float,
                'draw': float (optional),
                'away_win': float
            }

        Returns:
            OddsResult: 배당률, 오버라운드, 마진 정보
        """
        odds = self.probability_to_odds(probabilities, apply_margin=True)

        return OddsResult(
            home_win_odds=odds.get("home_win_odds", 0),
            draw_odds=odds.get("draw_odds"),
            away_win_odds=odds.get("away_win_odds", 0),
            overround=self.calculate_overround(odds),
            margin_percentage=self.calculate_margin_percentage(odds),
        )

    def compare_odds(
        self, our_odds: Dict[str, float], official_odds: Dict[str, float]
    ) -> Dict[str, Dict[str, float]]:
        """
        자체 배당과 공식 배당 비교

        Args:
            our_odds: 자체 산출 배당률
            official_odds: 공식(시장) 배당률

        Returns:
            각 결과별 비교 정보
        """
        comparison = {}

        outcomes = ["home_win", "draw", "away_win"]

        for outcome in outcomes:
            our_key = f"{outcome}_odds"

            our_value = our_odds.get(our_key, 0)
            official_value = official_odds.get(outcome, 0)

            if our_value and official_value:
                # 차이 계산
                diff = round(official_value - our_value, 2)
                diff_percentage = round((diff / our_value) * 100, 2) if our_value else 0

                comparison[outcome] = {
                    "our_odds": our_value,
                    "official_odds": official_value,
                    "difference": diff,
                    "difference_percentage": diff_percentage,
                    "is_value": official_value
                    > our_value,  # 공식 배당이 더 높으면 가치
                }

        return comparison


# 편의 함수
def prob_to_decimal_odds(probability: float, margin: float = 0.05) -> float:
    """
    단일 확률을 배당률로 변환

    Args:
        probability: 확률 (0.0 ~ 1.0)
        margin: 마진 (기본 5%)

    Returns:
        배당률
    """
    if probability <= 0:
        return 999.99

    adjusted = probability * (1 + margin)
    if adjusted >= 1.0:
        adjusted = 0.99

    return round(1 / adjusted, 2)


def decimal_odds_to_prob(odds: float) -> float:
    """
    배당률을 확률로 변환

    Args:
        odds: 배당률

    Returns:
        내재 확률
    """
    if odds <= 0:
        return 0.0
    return round(1 / odds, 4)
