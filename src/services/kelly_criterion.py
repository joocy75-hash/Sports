# src/services/kelly_criterion.py

from dataclasses import dataclass


@dataclass
class KellyRecommendation:
    recommended_stake: float
    kelly_percentage: float
    expected_value: float
    expected_roi: float
    risk_level: str
    max_loss: float
    full_kelly_stake: float
    fractional_kelly_stake: float


class KellyCriterion:
    def __init__(self, kelly_fraction=0.25, max_bet_pct=0.05, min_edge=0.0):
        self.kelly_fraction = kelly_fraction
        self.max_bet_pct = max_bet_pct
        self.min_edge = min_edge

    def calculate_stake(
        self, win_prob: float, odds: float, bankroll: float
    ) -> KellyRecommendation:
        """
        Kelly Criterion을 사용하여 최적의 베팅 금액을 계산합니다.

        Formula: f* = (bp - q) / b
        where:
            f* = fraction of bankroll to wager
            b = net odds (decimal odds - 1)
            p = probability of winning
            q = probability of losing (1 - p)
        """
        if odds <= 1:
            return self._empty_recommendation()

        b = odds - 1
        p = win_prob
        q = 1 - p

        # Kelly Fraction (f*)
        f_star = (b * p - q) / b

        # Edge calculation (Expected Value per $1 bet)
        # EV = (Prob * (Odds - 1)) - (1 - Prob)
        ev = (p * b) - q

        if f_star <= 0 or ev <= self.min_edge:
            return self._empty_recommendation()

        # Apply fractional Kelly (e.g., Quarter Kelly)
        fractional_f = f_star * self.kelly_fraction

        # Apply max bet cap
        final_f = min(fractional_f, self.max_bet_pct)

        stake = bankroll * final_f

        # Risk Level Assessment
        risk = "Low"
        if final_f > 0.03:
            risk = "High"
        elif final_f > 0.015:
            risk = "Medium"

        return KellyRecommendation(
            recommended_stake=round(stake, 2),
            kelly_percentage=round(final_f * 100, 2),
            expected_value=round(stake * ev, 2),
            expected_roi=round(ev * 100, 2),
            risk_level=risk,
            max_loss=round(stake, 2),
            full_kelly_stake=round(bankroll * f_star, 2),
            fractional_kelly_stake=round(bankroll * fractional_f, 2),
        )

    def _empty_recommendation(self):
        return KellyRecommendation(0, 0, 0, 0, "None", 0, 0, 0)
