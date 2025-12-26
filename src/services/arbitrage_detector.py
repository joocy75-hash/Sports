# src/services/arbitrage_detector.py

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class ArbitrageOpportunity:
    match_id: int
    home_team: str
    away_team: str
    profit_margin: float
    guaranteed_profit: float
    total_stake: float
    stakes: Dict[
        str, Dict
    ]  # {'home': {'bookmaker': '...', 'odds': ..., 'amount': ...}, ...}


class ArbitrageDetector:
    def __init__(self, min_profit_margin=0.0):
        self.min_profit_margin = min_profit_margin

    async def find_all_arbitrage_opportunities(
        self, matches: List[dict]
    ) -> List[ArbitrageOpportunity]:
        opportunities = []
        for match in matches:
            opp = self._check_match_arbitrage(match)
            if opp and opp.profit_margin >= self.min_profit_margin:
                opportunities.append(opp)
        return opportunities

    def _check_match_arbitrage(self, match: dict) -> Optional[ArbitrageOpportunity]:
        # 북메이커 데이터가 없으면 스킵
        if "bookmakers" not in match or not match["bookmakers"]:
            return None

        # 각 결과별 최고 배당 찾기
        best_odds = {
            "home": {"odds": 0, "bookmaker": None},
            "draw": {"odds": 0, "bookmaker": None},
            "away": {"odds": 0, "bookmaker": None},
        }

        has_draw = False

        for bm in match["bookmakers"]:
            # Home
            if bm.get("home_odds", 0) > best_odds["home"]["odds"]:
                best_odds["home"] = {"odds": bm["home_odds"], "bookmaker": bm["name"]}

            # Away
            if bm.get("away_odds", 0) > best_odds["away"]["odds"]:
                best_odds["away"] = {"odds": bm["away_odds"], "bookmaker": bm["name"]}

            # Draw (있을 경우)
            if bm.get("draw_odds"):
                has_draw = True
                if bm["draw_odds"] > best_odds["draw"]["odds"]:
                    best_odds["draw"] = {
                        "odds": bm["draw_odds"],
                        "bookmaker": bm["name"],
                    }

        # 유효성 검사
        if best_odds["home"]["odds"] == 0 or best_odds["away"]["odds"] == 0:
            return None
        if has_draw and best_odds["draw"]["odds"] == 0:
            return None

        # Implied Probability 계산
        implied_prob = (1 / best_odds["home"]["odds"]) + (1 / best_odds["away"]["odds"])
        if has_draw:
            implied_prob += 1 / best_odds["draw"]["odds"]

        # Arbitrage 조건: 총 확률 < 1
        if implied_prob < 1.0:
            profit_margin = (1 - implied_prob) / implied_prob * 100

            # 스테이크 계산 (총 $100 기준)
            total_stake = 100.0
            stakes = {}

            # Individual Stake = (Total Stake * Implied Prob of Outcome) / Total Implied Prob
            # Or simpler: Stake = (Total Investment) / (Odds * Sum of Inverse Odds)
            # Let's use: Stake = (Total Stake / Implied Prob) / Odds

            # Arbitrage Payout = Total Stake / Implied Prob
            payout = total_stake / implied_prob
            guaranteed_profit = payout - total_stake

            stakes["home"] = {
                "bookmaker": best_odds["home"]["bookmaker"],
                "odds": best_odds["home"]["odds"],
                "amount": round(payout / best_odds["home"]["odds"], 2),
            }
            stakes["away"] = {
                "bookmaker": best_odds["away"]["bookmaker"],
                "odds": best_odds["away"]["odds"],
                "amount": round(payout / best_odds["away"]["odds"], 2),
            }
            if has_draw:
                stakes["draw"] = {
                    "bookmaker": best_odds["draw"]["bookmaker"],
                    "odds": best_odds["draw"]["odds"],
                    "amount": round(payout / best_odds["draw"]["odds"], 2),
                }

            return ArbitrageOpportunity(
                match_id=match.get("id"),
                home_team=match.get("home_team"),
                away_team=match.get("away_team"),
                profit_margin=round(profit_margin, 2),
                guaranteed_profit=round(guaranteed_profit, 2),
                total_stake=total_stake,
                stakes=stakes,
            )

        return None
