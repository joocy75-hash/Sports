"""
ValueDetector - Value Bet 탐지기

자체 배당과 공식 배당을 비교하여 가치 베팅 기회를 발견합니다.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BetRecommendation(Enum):
    """베팅 추천 등급"""

    STRONG_BET = "STRONG_BET"  # 강력 추천
    BET = "BET"  # 추천
    CONSIDER = "CONSIDER"  # 고려
    SKIP = "SKIP"  # 패스
    AVOID = "AVOID"  # 피해야 함 (마이너스 가치)


@dataclass
class ValueBet:
    """Value Bet 정보"""

    match_id: Optional[str]
    outcome: str  # 'home_win', 'draw', 'away_win'
    our_odds: float  # 자체 산출 배당률
    official_odds: float  # 공식 배당률
    value: float  # 가치 (0.0 ~ 1.0)
    value_percentage: str  # "15.3%"
    confidence: float  # AI 신뢰도
    recommendation: BetRecommendation
    expected_value: float  # 기대값

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        result = asdict(self)
        result["recommendation"] = self.recommendation.value
        return result


@dataclass
class RiskAssessment:
    """리스크 평가 결과"""

    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    risk_score: float  # 0.0 ~ 1.0
    risk_factors: List[str]  # 리스크 요인들
    recommended_stake: float  # 권장 배팅 비율 (0.0 ~ 0.05)
    kelly_fraction: float  # 켈리 기준 비율


class ValueDetector:
    """
    Value Bet 탐지기

    자체 배당과 공식 배당을 비교하여 가치 베팅 기회를 발견합니다.
    Value = (공식 배당 / 자체 배당) - 1

    양수: 공식 배당이 과대평가 → 베팅 기회
    음수: 공식 배당이 과소평가 → 피해야 함
    """

    def __init__(self, min_value_threshold: float = 0.05, min_confidence: float = 0.60):
        """
        Args:
            min_value_threshold: 최소 가치 임계값 (기본 5%)
            min_confidence: 최소 AI 신뢰도 (기본 60%)
        """
        self.min_threshold = min_value_threshold
        self.min_confidence = min_confidence

    def calculate_value(self, our_odds: float, official_odds: float) -> float:
        """
        가치 계산

        Value = (공식 배당 / 자체 배당) - 1

        양수: 공식 배당이 과대평가 (베팅 기회)
        음수: 공식 배당이 과소평가 (피해야 함)

        Args:
            our_odds: 자체 산출 배당률
            official_odds: 공식(시장) 배당률

        Returns:
            가치 (-1.0 ~ ∞)
        """
        if our_odds <= 0:
            return 0.0

        value = (official_odds / our_odds) - 1
        return round(value, 4)

    def calculate_expected_value(self, probability: float, odds: float) -> float:
        """
        기대값 계산

        EV = (확률 × 배당) - 1

        양수: 장기적으로 수익
        음수: 장기적으로 손실

        Args:
            probability: 예측 확률 (0.0 ~ 1.0)
            odds: 배당률

        Returns:
            기대값
        """
        if probability <= 0 or odds <= 0:
            return -1.0

        ev = (probability * odds) - 1
        return round(ev, 4)

    def find_value_bets(
        self, our_analysis: Dict, official_odds: Dict, match_id: Optional[str] = None
    ) -> List[ValueBet]:
        """
        가치 베팅 탐지

        Args:
            our_analysis: {
                'home_win_odds': float,
                'draw_odds': float,
                'away_win_odds': float,
                'confidence': float,
                'probabilities': {'home': float, 'draw': float, 'away': float}
            }
            official_odds: {
                'home_win': float,
                'draw': float,
                'away_win': float
            }
            match_id: 경기 ID

        Returns:
            ValueBet 리스트 (가치순 정렬)
        """
        value_bets = []
        confidence = our_analysis.get("confidence", 0.5)
        probabilities = our_analysis.get("probabilities", {})

        outcome_mappings = [
            ("home_win", "home"),
            ("draw", "draw"),
            ("away_win", "away"),
        ]

        for outcome, prob_key in outcome_mappings:
            # 배당률 가져오기
            our_odds = our_analysis.get(f"{outcome}_odds", 0)
            official = official_odds.get(outcome, 0)

            if not our_odds or not official:
                continue

            # 가치 계산
            value = self.calculate_value(our_odds, official)

            # 기대값 계산
            prob = probabilities.get(prob_key, 0.33)
            ev = self.calculate_expected_value(prob, official)

            # 추천 등급 결정
            recommendation = self._get_recommendation(value, confidence, ev)

            # 최소 임계값 이상인 경우만 포함
            if value >= self.min_threshold:
                value_bets.append(
                    ValueBet(
                        match_id=match_id,
                        outcome=outcome,
                        our_odds=our_odds,
                        official_odds=official,
                        value=value,
                        value_percentage=f"{value * 100:.1f}%",
                        confidence=confidence,
                        recommendation=recommendation,
                        expected_value=ev,
                    )
                )
            elif value < -0.10:  # 10% 이상 마이너스면 피하라고 알림
                value_bets.append(
                    ValueBet(
                        match_id=match_id,
                        outcome=outcome,
                        our_odds=our_odds,
                        official_odds=official,
                        value=value,
                        value_percentage=f"{value * 100:.1f}%",
                        confidence=confidence,
                        recommendation=BetRecommendation.AVOID,
                        expected_value=ev,
                    )
                )

        # 가치순 내림차순 정렬
        value_bets.sort(key=lambda x: x.value, reverse=True)

        return value_bets

    def _get_recommendation(
        self, value: float, confidence: float, expected_value: float
    ) -> BetRecommendation:
        """
        추천 등급 결정

        고려 요소:
        - 가치 크기
        - AI 신뢰도
        - 기대값

        Args:
            value: 가치 비율
            confidence: AI 신뢰도
            expected_value: 기대값

        Returns:
            BetRecommendation
        """
        if value < 0:
            if value < -0.10:
                return BetRecommendation.AVOID
            return BetRecommendation.SKIP

        if confidence < self.min_confidence:
            return BetRecommendation.SKIP

        # 종합 점수 계산 (가치 60%, 신뢰도 30%, EV 10%)
        score = (value * 0.6) + (confidence * 0.3) + (max(expected_value, 0) * 0.1)

        if score >= 0.25 and expected_value > 0:
            return BetRecommendation.STRONG_BET
        elif score >= 0.15 and expected_value > -0.05:
            return BetRecommendation.BET
        elif score >= 0.08:
            return BetRecommendation.CONSIDER
        else:
            return BetRecommendation.SKIP

    def evaluate_risk(self, value_bet: ValueBet, match_context: Dict) -> RiskAssessment:
        """
        베팅 리스크 평가

        고려 요소:
        - AI 합의도
        - 과거 정확도
        - 배당률 변동성
        - 경기 중요도

        Args:
            value_bet: ValueBet 객체
            match_context: 추가 맥락 정보

        Returns:
            RiskAssessment
        """
        risk_factors = []
        risk_score = 0.0

        # 1. 신뢰도 체크
        if value_bet.confidence < 0.7:
            risk_factors.append("낮은 AI 신뢰도")
            risk_score += 0.20

        # 2. 합의도 체크
        consensus = match_context.get("consensus_level", 0.7)
        if consensus < 0.7:
            risk_factors.append("AI 간 낮은 합의도")
            risk_score += 0.20

        # 3. 배당률 격차
        odds_diff = abs(value_bet.our_odds - value_bet.official_odds)
        if odds_diff > 1.0:
            risk_factors.append("큰 배당률 격차")
            risk_score += 0.15

        # 4. 부상자 영향
        injury_impact = match_context.get("injury_impact", 0)
        if injury_impact > 0.15:
            risk_factors.append("주요 선수 부상")
            risk_score += 0.15

        # 5. 경기 중요도 (컵 결승 등은 예측 어려움)
        importance = match_context.get("match_importance", "normal")
        if importance == "high":
            risk_factors.append("고중요도 경기 (예측 변동성 높음)")
            risk_score += 0.10

        # 6. 기대값 체크
        if value_bet.expected_value < 0:
            risk_factors.append("음수 기대값")
            risk_score += 0.15

        # 리스크 레벨 결정
        if risk_score <= 0.25:
            risk_level = "LOW"
        elif risk_score <= 0.50:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        # 켈리 기준 계산
        kelly = self._calculate_kelly(value_bet)

        # 권장 배팅 비율 (리스크 조정)
        recommended_stake = kelly * (1 - min(risk_score, 0.8))
        recommended_stake = min(recommended_stake, 0.05)  # 최대 5%
        recommended_stake = max(recommended_stake, 0)  # 최소 0%

        return RiskAssessment(
            risk_level=risk_level,
            risk_score=round(risk_score, 2),
            risk_factors=risk_factors,
            recommended_stake=round(recommended_stake, 4),
            kelly_fraction=round(kelly, 4),
        )

    def _calculate_kelly(self, value_bet: ValueBet) -> float:
        """
        켈리 기준 계산

        Kelly = (p * b - q) / b

        여기서:
        - p: 승리 확률
        - q: 패배 확률 (1 - p)
        - b: 순 배당률 (배당률 - 1)

        Args:
            value_bet: ValueBet 객체

        Returns:
            켈리 기준 배팅 비율
        """
        # 우리 배당률에서 확률 추정
        if value_bet.our_odds <= 0:
            return 0.0

        p = 1 / value_bet.our_odds  # 승리 확률 추정
        q = 1 - p  # 패배 확률
        b = value_bet.official_odds - 1  # 순 배당률

        if b <= 0:
            return 0.0

        kelly = (p * b - q) / b

        # 음수이면 베팅하지 말 것
        if kelly < 0:
            return 0.0

        # 보수적 접근: 1/4 켈리 적용
        return kelly * 0.25

    def summarize_value_bets(self, value_bets: List[ValueBet]) -> Dict:
        """
        Value Bet 요약

        Args:
            value_bets: ValueBet 리스트

        Returns:
            요약 정보
        """
        if not value_bets:
            return {
                "total_opportunities": 0,
                "strong_bets": 0,
                "average_value": 0,
                "best_bet": None,
            }

        strong_bets = [
            vb
            for vb in value_bets
            if vb.recommendation
            in [BetRecommendation.STRONG_BET, BetRecommendation.BET]
        ]

        avg_value = sum(vb.value for vb in value_bets) / len(value_bets)

        best_bet = max(value_bets, key=lambda x: x.value)

        return {
            "total_opportunities": len(value_bets),
            "strong_bets": len(strong_bets),
            "average_value": round(avg_value, 4),
            "average_value_percentage": f"{avg_value * 100:.1f}%",
            "best_bet": best_bet.to_dict() if best_bet else None,
        }
