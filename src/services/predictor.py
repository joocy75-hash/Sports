from typing import Tuple, Optional
import numpy as np
from scipy.stats import poisson


class AdvancedStatisticalPredictor:
    """
    Advanced Statistical Predictor using Poisson Distribution with adjustments.
    Factors in:
    - Home Advantage
    - Recent Form (Momentum)
    - League Averages (Attack/Defense Strength)
    """

    def __init__(self, league_avg_home_goals=1.5, league_avg_away_goals=1.2):
        self.league_avg_home_goals = league_avg_home_goals
        self.league_avg_away_goals = league_avg_away_goals

    def calculate_team_strength(
        self, avg_goals_scored: float, avg_goals_conceded: float, is_home: bool
    ) -> Tuple[float, float]:
        """
        Calculate Attack and Defense ratings relative to league average.
        Returns (Attack Strength, Defense Strength)
        """
        if is_home:
            att_strength = (
                avg_goals_scored / self.league_avg_home_goals
                if self.league_avg_home_goals > 0
                else 1.0
            )
            def_strength = (
                avg_goals_conceded / self.league_avg_away_goals
                if self.league_avg_away_goals > 0
                else 1.0
            )
        else:
            att_strength = (
                avg_goals_scored / self.league_avg_away_goals
                if self.league_avg_away_goals > 0
                else 1.0
            )
            def_strength = (
                avg_goals_conceded / self.league_avg_home_goals
                if self.league_avg_home_goals > 0
                else 1.0
            )

        return round(att_strength, 3), round(def_strength, 3)

    def predict_score_probabilities(self, home_stats: dict, away_stats: dict) -> dict:
        """
        Predict match outcome probabilities.

        stats dict should contain:
        - 'goals_scored_avg': float
        - 'goals_conceded_avg': float
        - 'momentum': float (0.5 - 1.5, default 1.0)
        """

        # 1. Calculate Strengths
        home_att, home_def = self.calculate_team_strength(
            home_stats.get("goals_scored_avg", 1.5),
            home_stats.get("goals_conceded_avg", 1.0),
            is_home=True,
        )

        away_att, away_def = self.calculate_team_strength(
            away_stats.get("goals_scored_avg", 1.2),
            away_stats.get("goals_conceded_avg", 1.5),
            is_home=False,
        )

        # 2. Apply Momentum (Form)
        home_momentum = home_stats.get("momentum", 1.0)
        away_momentum = away_stats.get("momentum", 1.0)

        # Momentum boosts attack and slightly improves defense (lowers conceded)
        home_att *= home_momentum
        away_att *= away_momentum

        # 3. Calculate Expected Goals (Lambda)
        # Home Goals = Home Att * Away Def * League Avg Home Goals
        home_xg = home_att * away_def * self.league_avg_home_goals

        # Away Goals = Away Att * Home Def * League Avg Away Goals
        away_xg = away_att * home_def * self.league_avg_away_goals

        # 4. Poisson Convolution
        max_goals = 10
        prob_home = 0.0
        prob_draw = 0.0
        prob_away = 0.0

        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                p = poisson.pmf(h, home_xg) * poisson.pmf(a, away_xg)
                if h > a:
                    prob_home += p
                elif h == a:
                    prob_draw += p
                else:
                    prob_away += p

        # Normalize (0으로 나누기 방지)
        total = prob_home + prob_draw + prob_away

        if total == 0 or np.isnan(total):
            # 기본값 반환
            return {
                "probabilities": {
                    "home": 0.33,
                    "draw": 0.34,
                    "away": 0.33,
                },
                "expected_score": {
                    "home": round(home_xg, 2),
                    "away": round(away_xg, 2),
                },
            }

        return {
            "probabilities": {
                "home": prob_home / total,
                "draw": prob_draw / total,
                "away": prob_away / total,
            },
            "expected_score": {"home": round(home_xg, 2), "away": round(away_xg, 2)},
        }

    def predict_basketball_win5_probabilities(
        self, home_stats: dict, away_stats: dict
    ) -> dict:
        """
        농구 승5패 확률 계산 (6점차 이상 승/5점차 이내/6점차 이상 패)
        """
        # 농구는 평균 득점이 높으므로 xG를 80~100 사이로 가정 (데이터가 없을 경우)
        home_xg = home_stats.get("goals_scored_avg", 85.0) * home_stats.get(
            "momentum", 1.0
        )
        away_xg = away_stats.get("goals_scored_avg", 82.0) * away_stats.get(
            "momentum", 1.0
        )

        # 정규분포 근사 (득점-실점 차이)
        # 농구 점수차의 표준편차는 보통 10~12 정도
        diff_mean = home_xg - away_xg
        diff_std = 12.0

        from scipy.stats import norm

        # 승 (Home > Away + 5) -> diff > 5.5
        prob_home = 1 - norm.cdf(5.5, loc=diff_mean, scale=diff_std)
        # 패 (Away > Home + 5) -> diff < -5.5
        prob_away = norm.cdf(-5.5, loc=diff_mean, scale=diff_std)
        # 5 (차이 <= 5)
        prob_5 = 1 - prob_home - prob_away

        return {
            "probabilities": {
                "home": prob_home,
                "draw": prob_5,
                "away": prob_away,
            },
            "expected_score": {"home": round(home_xg, 1), "away": round(away_xg, 1)},
        }

    def predict_baseball_win1_probabilities(
        self, home_stats: dict, away_stats: dict
    ) -> dict:
        """
        야구 승1패 확률 계산 (2점차 이상 승/1점차 이내/2점차 이상 패)
        """
        home_xg = home_stats.get("goals_scored_avg", 4.5) * home_stats.get(
            "momentum", 1.0
        )
        away_xg = away_stats.get("goals_scored_avg", 4.2) * away_stats.get(
            "momentum", 1.0
        )

        # 야구는 득점이 낮으므로 포아송 분포 사용 가능
        max_goals = 20
        prob_home = 0.0
        prob_1 = 0.0
        prob_away = 0.0

        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                p = poisson.pmf(h, home_xg) * poisson.pmf(a, away_xg)
                if h - a >= 2:
                    prob_home += p
                elif abs(h - a) <= 1:
                    prob_1 += p
                elif a - h >= 2:
                    prob_away += p

        total = prob_home + prob_1 + prob_away
        return {
            "probabilities": {
                "home": prob_home / total,
                "draw": prob_1 / total,
                "away": prob_away / total,
            },
            "expected_score": {"home": round(home_xg, 1), "away": round(away_xg, 1)},
        }


# Legacy support wrapper
def probabilities_from_xg(xg_home: float, xg_away: float) -> Tuple[float, float, float]:
    predictor = AdvancedStatisticalPredictor()
    # Reverse engineer to use the new class logic if needed, or just keep simple implementation
    # For now, keeping the simple one for backward compatibility if imported directly
    max_goals = 10
    prob_home = 0.0
    prob_draw = 0.0
    prob_away = 0.0

    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson.pmf(h, xg_home) * poisson.pmf(a, xg_away)
            if h > a:
                prob_home += p
            elif h == a:
                prob_draw += p
            else:
                prob_away += p
    total = prob_home + prob_draw + prob_away
    return prob_home / total, prob_draw / total, prob_away / total
