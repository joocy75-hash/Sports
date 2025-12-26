# src/services/live_betting_engine.py

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class LiveAnalysisResult:
    match_id: int
    momentum: str  # "home", "away", "neutral"
    live_value_bets: List[dict]
    timing_score: int  # 0-100 (betting timing quality)


class LiveBettingEngine:
    def __init__(self):
        pass

    async def analyze_live_match(
        self,
        match_id: int,
        current_score: tuple,
        minute: int,
        live_stats: dict,
        live_odds: dict,
    ) -> LiveAnalysisResult:
        """
        실시간 경기 분석 및 베팅 기회 포착
        """
        home_score, away_score = current_score

        # 1. 모멘텀 분석
        momentum = self._calculate_momentum(live_stats)

        # 2. Value Bet 탐색
        value_bets = []
        timing_score = 50

        # 전략 A: 강팀이 지고 있을 때 (Favorite Losing)
        # 예: 홈팀이 강팀인데 0-1로 지고 있고, 공격 지표가 압도적일 때
        if self._is_favorite_losing(live_odds, home_score, away_score):
            if momentum == "home" and minute < 80:
                value_bets.append(
                    {
                        "market": "Home Win",
                        "odds": live_odds.get("home_odds", 0),
                        "edge": 15.0,  # 추정치
                        "reason": "Favorite losing but dominating play",
                    }
                )
                timing_score = 80

        # 전략 B: 후반전 무승부 & 루즈한 경기 (Draw Scalping)
        if home_score == away_score and minute > 75:
            if momentum == "neutral":
                value_bets.append(
                    {
                        "market": "Draw",
                        "odds": live_odds.get("draw_odds", 0),
                        "edge": 10.0,
                        "reason": "Late game stalemate",
                    }
                )
                timing_score = 75

        return LiveAnalysisResult(
            match_id=match_id,
            momentum=momentum,
            live_value_bets=value_bets,
            timing_score=timing_score,
        )

    def _calculate_momentum(self, stats: dict) -> str:
        """
        최근 경기 흐름(Momentum) 계산
        """
        if not stats:
            return "neutral"

        # 간단한 로직: 최근 10분 공격 지표 비교
        # 실제로는 Dangerous Attacks, Shots on Target 등을 사용
        home_attacks = stats.get("home_dangerous_attacks", 0)
        away_attacks = stats.get("away_dangerous_attacks", 0)

        diff = home_attacks - away_attacks

        if diff > 5:
            return "home"
        elif diff < -5:
            return "away"
        else:
            return "neutral"

    def _is_favorite_losing(self, odds: dict, home_score: int, away_score: int) -> bool:
        """강팀이 지고 있는지 확인"""
        # 시작 배당 기준 (여기서는 현재 배당으로 근사하거나 별도 저장된 프리매치 배당 필요)
        # 임시로 현재 배당이 높더라도 스코어 감안하여 판단 로직 필요
        # 여기서는 단순화: 홈이 지고 있는데 홈 배당이 2.5 이하면 '추격 중'으로 간주

        if home_score < away_score:
            if (
                odds.get("home_odds", 100) < 3.0
            ):  # 지고 있는데도 배당이 낮으면 원래 강팀
                return True
        return False
