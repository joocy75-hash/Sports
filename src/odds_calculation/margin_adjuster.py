"""
MarginAdjuster - 마진 조정기

배당률의 마진을 조정하여 목표 마진을 달성하거나, 마진을 제거합니다.
"""

from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MarginAnalysis:
    """마진 분석 결과"""

    original_overround: float  # 원래 오버라운드
    target_overround: float  # 목표 오버라운드
    adjustment_factor: float  # 조정 계수
    fair_probabilities: Dict[str, float]  # 공정 확률
    adjusted_probabilities: Dict[str, float]  # 조정된 확률


class MarginAdjuster:
    """
    마진 조정기

    배당률의 마진을 조정하여 목표 마진을 달성하거나,
    공정한(마진 없는) 확률을 추정합니다.
    """

    def __init__(self, target_margin: float = 0.05):
        """
        Args:
            target_margin: 목표 마진 (기본 5%)
        """
        self.target_margin = target_margin

    def adjust_to_target_margin(
        self, probabilities: Dict[str, float]
    ) -> Dict[str, float]:
        """
        확률을 조정하여 목표 마진 달성

        Args:
            probabilities: {
                'home_win': 0.45,
                'draw': 0.25,
                'away_win': 0.30
            }

        Returns:
            마진이 적용된 조정 확률
        """
        # 현재 총합 (1.0이어야 정상)
        total = sum(probabilities.values())

        if total <= 0:
            return probabilities

        # 목표 총합 (1 + 마진)
        target_total = 1 + self.target_margin

        # 비례 조정
        adjusted = {
            key: round((value / total) * target_total, 4)
            for key, value in probabilities.items()
        }

        return adjusted

    def remove_margin(self, odds_dict: Dict[str, float]) -> Dict[str, float]:
        """
        배당률에서 마진 제거 (순수 확률 추정)

        여러 방법 중 "비례 방법" 사용:
        각 확률을 총합으로 나눠 정규화

        Args:
            odds_dict: {
                'home_win': 2.0,
                'draw': 3.5,
                'away_win': 3.0
            }

        Returns:
            마진 제거된 순수 확률
        """
        # 내재 확률 계산
        implied = {}
        for key, odds in odds_dict.items():
            if odds is not None and odds > 0:
                implied[key] = 1 / odds
            else:
                implied[key] = 0

        # 총합 계산 (오버라운드)
        total = sum(implied.values())

        if total <= 0:
            return {}

        # 정규화 (합 = 1.0)
        normalized = {key: round(value / total, 4) for key, value in implied.items()}

        return normalized

    def remove_margin_power_method(
        self, odds_dict: Dict[str, float], power: float = 0.5
    ) -> Dict[str, float]:
        """
        Power Method로 마진 제거

        Shin의 방법보다 간단하지만 효과적인 방법.
        확률을 power 값으로 거듭제곱한 후 정규화.

        Args:
            odds_dict: 배당률 딕셔너리
            power: 거듭제곱 계수 (기본 0.5)

        Returns:
            조정된 확률
        """
        # 내재 확률 계산
        implied = {}
        for key, odds in odds_dict.items():
            if odds is not None and odds > 0:
                implied[key] = (1 / odds) ** power
            else:
                implied[key] = 0

        # 정규화
        total = sum(implied.values())

        if total <= 0:
            return {}

        return {key: round(value / total, 4) for key, value in implied.items()}

    def calculate_overround(self, odds_dict: Dict[str, float]) -> float:
        """
        오버라운드 계산

        Args:
            odds_dict: 배당률 딕셔너리

        Returns:
            오버라운드 (100% = 1.0)
        """
        implied_sum = 0

        for odds in odds_dict.values():
            if odds is not None and odds > 0:
                implied_sum += 1 / odds

        return round(implied_sum, 4)

    def analyze_margin(self, odds_dict: Dict[str, float]) -> MarginAnalysis:
        """
        마진 분석

        Args:
            odds_dict: 배당률 딕셔너리

        Returns:
            MarginAnalysis 객체
        """
        original_overround = self.calculate_overround(odds_dict)
        target_overround = 1 + self.target_margin

        # 조정 계수
        adjustment_factor = (
            target_overround / original_overround if original_overround > 0 else 1.0
        )

        # 공정 확률 (마진 제거)
        fair_probs = self.remove_margin(odds_dict)

        # 목표 마진 적용된 확률
        adjusted_probs = self.adjust_to_target_margin(fair_probs)

        return MarginAnalysis(
            original_overround=original_overround,
            target_overround=target_overround,
            adjustment_factor=round(adjustment_factor, 4),
            fair_probabilities=fair_probs,
            adjusted_probabilities=adjusted_probs,
        )

    def compare_margins(
        self, our_odds: Dict[str, float], official_odds: Dict[str, float]
    ) -> Dict[str, float]:
        """
        자체 배당과 공식 배당의 마진 비교

        Args:
            our_odds: 자체 배당률
            official_odds: 공식 배당률

        Returns:
            마진 비교 정보
        """
        our_overround = self.calculate_overround(our_odds)
        official_overround = self.calculate_overround(official_odds)

        return {
            "our_overround": our_overround,
            "our_margin_pct": round((our_overround - 1) * 100, 2),
            "official_overround": official_overround,
            "official_margin_pct": round((official_overround - 1) * 100, 2),
            "margin_difference": round((official_overround - our_overround) * 100, 2),
        }

    def equalize_odds(
        self, odds_dict: Dict[str, float], target_overround: Optional[float] = None
    ) -> Dict[str, float]:
        """
        배당률을 목표 오버라운드에 맞게 조정

        Args:
            odds_dict: 원래 배당률
            target_overround: 목표 오버라운드 (기본: 1 + target_margin)

        Returns:
            조정된 배당률
        """
        if target_overround is None:
            target_overround = 1 + self.target_margin

        # 현재 오버라운드
        current_overround = self.calculate_overround(odds_dict)

        if current_overround <= 0:
            return odds_dict

        # 조정 비율
        adjustment = current_overround / target_overround

        # 배당률 조정
        adjusted_odds = {}
        for key, odds in odds_dict.items():
            if odds is not None and odds > 0:
                adjusted_odds[key] = round(odds * adjustment, 2)
            else:
                adjusted_odds[key] = odds

        return adjusted_odds

    def get_true_probabilities(
        self, odds_dict: Dict[str, float], method: str = "proportional"
    ) -> Dict[str, float]:
        """
        배당률에서 진정한 확률 추정

        Args:
            odds_dict: 배당률 딕셔너리
            method: 'proportional', 'power', 'shin'

        Returns:
            추정 확률
        """
        if method == "proportional":
            return self.remove_margin(odds_dict)
        elif method == "power":
            return self.remove_margin_power_method(odds_dict)
        else:
            # 기본값
            return self.remove_margin(odds_dict)


# 편의 함수
def remove_vig(odds_dict: Dict[str, float]) -> Dict[str, float]:
    """배당률에서 vig(마진) 제거"""
    adjuster = MarginAdjuster()
    return adjuster.remove_margin(odds_dict)


def calculate_vig(odds_dict: Dict[str, float]) -> float:
    """vig(마진) 비율 계산"""
    adjuster = MarginAdjuster()
    overround = adjuster.calculate_overround(odds_dict)
    return round((overround - 1) * 100, 2)  # 퍼센트로 반환
