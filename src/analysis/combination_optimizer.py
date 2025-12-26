"""
CombinationOptimizer - 조합 최적화기

14경기 중 최적의 베팅 조합을 생성합니다.
다양한 전략 (고신뢰도, 고가치, 균형, 안전, 공격적)을 지원합니다.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging
import numpy as np
from itertools import combinations

logger = logging.getLogger(__name__)


class CombinationStrategy(Enum):
    """조합 전략"""

    HIGH_CONFIDENCE = "high_confidence"  # 고신뢰도
    HIGH_VALUE = "high_value"  # 고가치
    BALANCED = "balanced"  # 균형
    SAFE = "safe"  # 안전
    AGGRESSIVE = "aggressive"  # 공격적


@dataclass
class Selection:
    """개별 선택"""

    match_id: str
    home_team: str
    away_team: str
    outcome: str  # 'home_win', 'draw', 'away_win'
    outcome_str: str  # '홈승', '무', '원정승'
    probability: float  # 예측 확률
    confidence: float  # AI 신뢰도
    odds: float  # 배당률
    value: Optional[float] = None  # 가치 (있는 경우)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CombinationMetrics:
    """조합 지표"""

    expected_roi: float  # 기대 ROI
    win_probability: float  # 승리 확률 (모든 경기 적중)
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    num_matches: int  # 선택된 경기 수
    avg_confidence: float  # 평균 신뢰도
    avg_odds: float  # 평균 배당률

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Combination:
    """베팅 조합"""

    name: str
    strategy: CombinationStrategy
    strategy_desc: str
    selections: List[Selection]
    total_odds: float
    metrics: CombinationMetrics
    stake_suggestion: float = 0.02  # 권장 배팅 비율 (기본 2%)

    def to_dict(self) -> Dict:
        result = {
            "name": self.name,
            "strategy": self.strategy.value,
            "strategy_desc": self.strategy_desc,
            "selections": [s.to_dict() for s in self.selections],
            "total_odds": self.total_odds,
            "metrics": self.metrics.to_dict(),
            "stake_suggestion": self.stake_suggestion,
        }
        return result


class CombinationOptimizer:
    """
    조합 최적화기

    14경기 분석 결과를 바탕으로 최적의 베팅 조합을 생성합니다.
    """

    def __init__(
        self,
        max_combinations: int = 5,
        min_confidence: float = 0.60,
        min_value: float = 0.05,
    ):
        """
        Args:
            max_combinations: 최대 조합 수
            min_confidence: 최소 신뢰도
            min_value: 최소 가치 (Value Bet 기준)
        """
        self.max_combinations = max_combinations
        self.min_confidence = min_confidence
        self.min_value = min_value

    def generate_combinations(self, match_analyses: List[Dict]) -> List[Combination]:
        """
        최적 조합 생성

        Args:
            match_analyses: AI 분석 결과 리스트
                각 항목: {
                    'match_id': str,
                    'home_team': str,
                    'away_team': str,
                    'synthesized_prediction': {
                        'home_win_prob': float,
                        'draw_prob': float,
                        'away_win_prob': float
                    },
                    'confidence': float,
                    'our_odds': {
                        'home_win_odds': float,
                        'draw_odds': float,
                        'away_win_odds': float
                    },
                    'value_bets': List[Dict]  # optional
                }

        Returns:
            조합 리스트 (예상 ROI 순)
        """
        combinations = []

        # 1. 고신뢰도 조합
        high_conf = self._build_high_confidence_combo(match_analyses)
        if high_conf:
            combinations.append(high_conf)

        # 2. 고가치 조합
        high_value = self._build_high_value_combo(match_analyses)
        if high_value:
            combinations.append(high_value)

        # 3. 균형 조합
        balanced = self._build_balanced_combo(match_analyses)
        if balanced:
            combinations.append(balanced)

        # 4. 안전 조합
        safe = self._build_safe_combo(match_analyses)
        if safe:
            combinations.append(safe)

        # 5. 공격적 조합
        aggressive = self._build_aggressive_combo(match_analyses)
        if aggressive:
            combinations.append(aggressive)

        # 예상 ROI 순 정렬
        combinations.sort(key=lambda x: x.metrics.expected_roi, reverse=True)

        return combinations[: self.max_combinations]

    def _build_high_confidence_combo(
        self, analyses: List[Dict]
    ) -> Optional[Combination]:
        """고신뢰도 조합: 신뢰도 80% 이상 경기만 선택"""

        selections = []

        for match in analyses:
            confidence = match.get("confidence", 0)

            if confidence < 0.80:
                continue

            # 가장 확률 높은 결과 선택
            prediction = match.get("synthesized_prediction", {})
            best_outcome, best_prob = self._get_best_outcome(prediction)

            if not best_outcome:
                continue

            odds = match.get("our_odds", {}).get(f"{best_outcome}_odds", 0)
            if odds <= 0:
                odds = match.get("official_odds", {}).get(best_outcome, 1.5)

            selections.append(
                Selection(
                    match_id=match.get("match_id", ""),
                    home_team=match.get("home_team", ""),
                    away_team=match.get("away_team", ""),
                    outcome=best_outcome,
                    outcome_str=self._outcome_to_korean(best_outcome),
                    probability=best_prob,
                    confidence=confidence,
                    odds=odds,
                )
            )

        if not selections:
            return None

        return self._create_combination(
            name="🎯 고신뢰도 조합",
            strategy=CombinationStrategy.HIGH_CONFIDENCE,
            strategy_desc="신뢰도 80% 이상 경기만 선택",
            selections=selections,
        )

    def _build_high_value_combo(self, analyses: List[Dict]) -> Optional[Combination]:
        """고가치 조합: Value 10% 이상 경기만 선택"""

        selections = []

        for match in analyses:
            value_bets = match.get("value_bets", [])

            if not value_bets:
                continue

            # 가장 높은 Value 선택
            best_value_bet = max(value_bets, key=lambda x: x.get("value", 0))
            value = best_value_bet.get("value", 0)

            if value < 0.10:
                continue

            outcome = best_value_bet.get("outcome", "")
            confidence = best_value_bet.get("confidence", 0.5)
            odds = best_value_bet.get("official_odds", 0)

            prediction = match.get("synthesized_prediction", {})
            prob = prediction.get(f"{outcome}_prob", 0.33)

            selections.append(
                Selection(
                    match_id=match.get("match_id", ""),
                    home_team=match.get("home_team", ""),
                    away_team=match.get("away_team", ""),
                    outcome=outcome,
                    outcome_str=self._outcome_to_korean(outcome),
                    probability=prob,
                    confidence=confidence,
                    odds=odds,
                    value=value,
                )
            )

        if not selections:
            return None

        # 가치순 정렬
        selections.sort(key=lambda x: x.value or 0, reverse=True)

        return self._create_combination(
            name="💰 고가치 조합",
            strategy=CombinationStrategy.HIGH_VALUE,
            strategy_desc="Value Bet 10% 이상 선택",
            selections=selections,
        )

    def _build_balanced_combo(self, analyses: List[Dict]) -> Optional[Combination]:
        """균형 조합: 신뢰도와 Value 균형"""

        selections = []

        for match in analyses:
            confidence = match.get("confidence", 0)

            if confidence < 0.65:
                continue

            prediction = match.get("synthesized_prediction", {})
            best_outcome, best_prob = self._get_best_outcome(prediction)

            if not best_outcome or best_prob < 0.40:
                continue

            # 균형 점수: 신뢰도 * 확률
            balance_score = confidence * best_prob

            if balance_score < 0.40:
                continue

            odds = match.get("our_odds", {}).get(f"{best_outcome}_odds", 0)
            if odds <= 0:
                odds = match.get("official_odds", {}).get(best_outcome, 1.5)

            selections.append(
                Selection(
                    match_id=match.get("match_id", ""),
                    home_team=match.get("home_team", ""),
                    away_team=match.get("away_team", ""),
                    outcome=best_outcome,
                    outcome_str=self._outcome_to_korean(best_outcome),
                    probability=best_prob,
                    confidence=confidence,
                    odds=odds,
                )
            )

        if not selections:
            return None

        # 균형 점수순 정렬
        selections.sort(key=lambda x: x.confidence * x.probability, reverse=True)

        # 상위 7개만 선택
        selections = selections[:7]

        return self._create_combination(
            name="⚖️ 균형 조합",
            strategy=CombinationStrategy.BALANCED,
            strategy_desc="신뢰도와 확률 균형 (상위 7경기)",
            selections=selections,
        )

    def _build_safe_combo(self, analyses: List[Dict]) -> Optional[Combination]:
        """안전 조합: 낮은 배당, 높은 확률"""

        selections = []

        for match in analyses:
            prediction = match.get("synthesized_prediction", {})
            best_outcome, best_prob = self._get_best_outcome(prediction)

            if not best_outcome or best_prob < 0.55:
                continue

            odds = match.get("our_odds", {}).get(f"{best_outcome}_odds", 0)
            if odds <= 0:
                odds = match.get("official_odds", {}).get(best_outcome, 1.5)

            # 안전: 배당률 2.5 이하만
            if odds > 2.5:
                continue

            confidence = match.get("confidence", 0.5)

            if confidence < 0.70:
                continue

            selections.append(
                Selection(
                    match_id=match.get("match_id", ""),
                    home_team=match.get("home_team", ""),
                    away_team=match.get("away_team", ""),
                    outcome=best_outcome,
                    outcome_str=self._outcome_to_korean(best_outcome),
                    probability=best_prob,
                    confidence=confidence,
                    odds=odds,
                )
            )

        if not selections:
            return None

        # 확률순 정렬
        selections.sort(key=lambda x: x.probability, reverse=True)

        # 상위 5개만 선택
        selections = selections[:5]

        return self._create_combination(
            name="🛡️ 안전 조합",
            strategy=CombinationStrategy.SAFE,
            strategy_desc="높은 확률, 낮은 배당 (상위 5경기)",
            selections=selections,
        )

    def _build_aggressive_combo(self, analyses: List[Dict]) -> Optional[Combination]:
        """공격적 조합: 높은 배당, 중간 신뢰도"""

        selections = []

        for match in analyses:
            prediction = match.get("synthesized_prediction", {})

            # 이변 가능성 탐색 (두 번째 높은 확률)
            outcomes = [
                ("home_win", prediction.get("home_win_prob", 0)),
                ("draw", prediction.get("draw_prob", 0)),
                ("away_win", prediction.get("away_win_prob", 0)),
            ]
            outcomes.sort(key=lambda x: x[1], reverse=True)

            # 두 번째 높은 확률이 25% 이상이면 이변 가능성
            if len(outcomes) >= 2 and outcomes[1][1] >= 0.25:
                chosen_outcome = outcomes[1][0]
                chosen_prob = outcomes[1][1]
            else:
                # 첫 번째 선택하되 배당이 높은 경우만
                chosen_outcome = outcomes[0][0]
                chosen_prob = outcomes[0][1]

            odds = match.get("our_odds", {}).get(f"{chosen_outcome}_odds", 0)
            if odds <= 0:
                odds = match.get("official_odds", {}).get(chosen_outcome, 2.0)

            # 공격적: 배당률 2.0 이상
            if odds < 2.0:
                continue

            confidence = match.get("confidence", 0.5)

            if confidence < 0.55:
                continue

            selections.append(
                Selection(
                    match_id=match.get("match_id", ""),
                    home_team=match.get("home_team", ""),
                    away_team=match.get("away_team", ""),
                    outcome=chosen_outcome,
                    outcome_str=self._outcome_to_korean(chosen_outcome),
                    probability=chosen_prob,
                    confidence=confidence,
                    odds=odds,
                )
            )

        if not selections:
            return None

        # 배당순 정렬
        selections.sort(key=lambda x: x.odds, reverse=True)

        # 상위 4개만 선택
        selections = selections[:4]

        return self._create_combination(
            name="🔥 공격적 조합",
            strategy=CombinationStrategy.AGGRESSIVE,
            strategy_desc="높은 배당, 이변 가능성 (상위 4경기)",
            selections=selections,
        )

    def _create_combination(
        self,
        name: str,
        strategy: CombinationStrategy,
        strategy_desc: str,
        selections: List[Selection],
    ) -> Combination:
        """조합 객체 생성"""

        total_odds = self._calculate_total_odds(selections)
        metrics = self._calculate_metrics(selections, total_odds)
        stake = self._suggest_stake(metrics)

        return Combination(
            name=name,
            strategy=strategy,
            strategy_desc=strategy_desc,
            selections=selections,
            total_odds=total_odds,
            metrics=metrics,
            stake_suggestion=stake,
        )

    def _get_best_outcome(self, prediction: Dict) -> Tuple[Optional[str], float]:
        """가장 확률 높은 결과 반환"""

        outcomes = [
            ("home_win", prediction.get("home_win_prob", 0)),
            ("draw", prediction.get("draw_prob", 0)),
            ("away_win", prediction.get("away_win_prob", 0)),
        ]

        best = max(outcomes, key=lambda x: x[1])

        if best[1] <= 0:
            return None, 0

        return best[0], best[1]

    def _outcome_to_korean(self, outcome: str) -> str:
        """결과를 한국어로 변환"""
        mapping = {"home_win": "홈승", "draw": "무", "away_win": "원정승"}
        return mapping.get(outcome, outcome)

    def _calculate_total_odds(self, selections: List[Selection]) -> float:
        """총 배당률 계산"""
        if not selections:
            return 0

        total = 1.0
        for sel in selections:
            total *= sel.odds

        return round(total, 2)

    def _calculate_metrics(
        self, selections: List[Selection], total_odds: float
    ) -> CombinationMetrics:
        """조합 지표 계산"""

        if not selections:
            return CombinationMetrics(
                expected_roi=0,
                win_probability=0,
                risk_level="N/A",
                num_matches=0,
                avg_confidence=0,
                avg_odds=0,
            )

        # 승리 확률 (모든 경기 적중)
        win_prob = 1.0
        for sel in selections:
            win_prob *= sel.probability

        # 예상 ROI
        expected_roi = (total_odds * win_prob) - 1

        # 평균 신뢰도
        avg_conf = sum(s.confidence for s in selections) / len(selections)

        # 평균 배당률
        avg_odds = sum(s.odds for s in selections) / len(selections)

        # 리스크 레벨
        if avg_conf >= 0.80 and win_prob >= 0.15:
            risk_level = "LOW"
        elif avg_conf >= 0.70 and win_prob >= 0.05:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        return CombinationMetrics(
            expected_roi=round(expected_roi, 4),
            win_probability=round(win_prob, 4),
            risk_level=risk_level,
            num_matches=len(selections),
            avg_confidence=round(avg_conf, 4),
            avg_odds=round(avg_odds, 2),
        )

    def _suggest_stake(self, metrics: CombinationMetrics) -> float:
        """권장 배팅 비율 계산"""

        # 기본: 2%
        stake = 0.02

        # ROI와 리스크에 따라 조정
        if metrics.expected_roi > 0.50 and metrics.risk_level == "LOW":
            stake = 0.04
        elif metrics.expected_roi > 0.20 and metrics.risk_level != "HIGH":
            stake = 0.03
        elif metrics.risk_level == "HIGH" or metrics.expected_roi < 0:
            stake = 0.01

        return stake

    def format_combination_report(self, combinations: List[Combination]) -> str:
        """조합 리포트 생성"""

        if not combinations:
            return "생성된 조합이 없습니다."

        report = "# 🎲 베팅 조합 리포트\n\n"

        for i, combo in enumerate(combinations, 1):
            report += f"## {i}. {combo.name}\n\n"
            report += f"**전략**: {combo.strategy_desc}\n\n"

            # 선택된 경기 테이블
            report += "| 경기 | 예측 | 확률 | 신뢰도 | 배당 |\n"
            report += "|------|------|------|--------|------|\n"

            for sel in combo.selections:
                match_str = f"{sel.home_team} vs {sel.away_team}"
                report += f"| {match_str} | {sel.outcome_str} | "
                report += f"{sel.probability:.1%} | {sel.confidence:.1%} | "
                report += f"{sel.odds:.2f} |\n"

            report += "\n"

            # 지표
            m = combo.metrics
            report += f"- **총 배당률**: {combo.total_odds:.2f}\n"
            report += f"- **승리 확률**: {m.win_probability:.1%}\n"
            report += f"- **예상 ROI**: {m.expected_roi:.1%}\n"
            report += f"- **리스크**: {m.risk_level}\n"
            report += f"- **권장 배팅**: 자금의 {combo.stake_suggestion:.0%}\n"
            report += "\n---\n\n"

        return report
