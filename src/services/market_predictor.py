"""
G-01/G-02: 핸디캡/언더오버 예측 모듈
축구 핸디캡과 언더/오버 마켓 예측을 수행합니다.
"""

import math
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class HandicapSide(Enum):
    HOME = "home"
    AWAY = "away"


class OverUnderSide(Enum):
    OVER = "over"
    UNDER = "under"


@dataclass
class HandicapPrediction:
    """핸디캡 예측 결과"""
    handicap_line: float  # 예: -1.5, +0.5
    home_cover_prob: float  # 홈팀이 핸디캡 커버할 확률
    away_cover_prob: float
    recommended_side: HandicapSide
    confidence: float
    value_rating: float  # 기대가치 평가 (0-100)
    reasoning: str


@dataclass
class OverUnderPrediction:
    """언더/오버 예측 결과"""
    line: float  # 예: 2.5, 3.0
    over_prob: float
    under_prob: float
    recommended_side: OverUnderSide
    confidence: float
    value_rating: float
    expected_total_goals: float
    reasoning: str


@dataclass
class MarketPrediction:
    """종합 마켓 예측"""
    handicap: HandicapPrediction
    over_under: OverUnderPrediction
    btts_yes_prob: float  # Both Teams To Score
    btts_no_prob: float
    btts_recommendation: str
    clean_sheet_home_prob: float
    clean_sheet_away_prob: float


class MarketPredictor:
    """핸디캡/언더오버 예측기"""

    def __init__(self):
        self.poisson_cache: Dict[str, List[List[float]]] = {}

    def predict_handicap(
        self,
        expected_home_goals: float,
        expected_away_goals: float,
        handicap_line: float = -0.5,
        home_odds: Optional[float] = None,
        away_odds: Optional[float] = None
    ) -> HandicapPrediction:
        """핸디캡 예측"""
        # 점수 확률 매트릭스 계산
        prob_matrix = self._calculate_score_matrix(expected_home_goals, expected_away_goals)

        # 핸디캡 커버 확률 계산
        home_cover = 0.0
        away_cover = 0.0

        for h in range(7):
            for a in range(7):
                prob = prob_matrix[h][a]
                adjusted_home = h + handicap_line

                if adjusted_home > a:
                    home_cover += prob
                elif adjusted_home < a:
                    away_cover += prob
                # 푸시(무효)는 무시

        # 정규화
        total = home_cover + away_cover
        if total > 0:
            home_cover = home_cover / total * 100
            away_cover = away_cover / total * 100

        # 추천 결정
        if home_cover > away_cover + 5:
            recommended = HandicapSide.HOME
            confidence = min(90, 50 + (home_cover - 50) * 0.8)
        elif away_cover > home_cover + 5:
            recommended = HandicapSide.AWAY
            confidence = min(90, 50 + (away_cover - 50) * 0.8)
        else:
            recommended = HandicapSide.HOME if home_cover >= away_cover else HandicapSide.AWAY
            confidence = 45

        # 기대가치 계산
        value_rating = 50
        if home_odds and away_odds:
            implied_home = 100 / home_odds
            implied_away = 100 / away_odds
            if recommended == HandicapSide.HOME:
                edge = home_cover - implied_home
            else:
                edge = away_cover - implied_away
            value_rating = min(100, max(0, 50 + edge))

        # 추론 생성
        goal_diff = expected_home_goals - expected_away_goals
        if handicap_line < 0:
            reasoning = f"홈팀이 {abs(handicap_line)}골 핸디캡을 극복할 확률 {home_cover:.1f}%"
        else:
            reasoning = f"원정팀이 {handicap_line}골 핸디캡을 극복할 확률 {away_cover:.1f}%"

        return HandicapPrediction(
            handicap_line=handicap_line,
            home_cover_prob=round(home_cover, 2),
            away_cover_prob=round(away_cover, 2),
            recommended_side=recommended,
            confidence=round(confidence, 1),
            value_rating=round(value_rating, 1),
            reasoning=reasoning
        )

    def predict_over_under(
        self,
        expected_home_goals: float,
        expected_away_goals: float,
        line: float = 2.5,
        over_odds: Optional[float] = None,
        under_odds: Optional[float] = None
    ) -> OverUnderPrediction:
        """언더/오버 예측"""
        expected_total = expected_home_goals + expected_away_goals

        # 점수 확률 매트릭스
        prob_matrix = self._calculate_score_matrix(expected_home_goals, expected_away_goals)

        # 오버/언더 확률 계산
        over_prob = 0.0
        under_prob = 0.0

        for h in range(7):
            for a in range(7):
                prob = prob_matrix[h][a]
                total = h + a

                if total > line:
                    over_prob += prob
                elif total < line:
                    under_prob += prob
                # 정확히 line과 같으면 푸시

        # 정규화
        total_prob = over_prob + under_prob
        if total_prob > 0:
            over_prob = over_prob / total_prob * 100
            under_prob = under_prob / total_prob * 100

        # 추천 결정
        if over_prob > under_prob + 5:
            recommended = OverUnderSide.OVER
            confidence = min(90, 50 + (over_prob - 50) * 0.8)
        elif under_prob > over_prob + 5:
            recommended = OverUnderSide.UNDER
            confidence = min(90, 50 + (under_prob - 50) * 0.8)
        else:
            recommended = OverUnderSide.OVER if expected_total > line else OverUnderSide.UNDER
            confidence = 45

        # 기대가치 계산
        value_rating = 50
        if over_odds and under_odds:
            implied_over = 100 / over_odds
            implied_under = 100 / under_odds
            if recommended == OverUnderSide.OVER:
                edge = over_prob - implied_over
            else:
                edge = under_prob - implied_under
            value_rating = min(100, max(0, 50 + edge))

        # 추론 생성
        if expected_total > line:
            reasoning = f"예상 총 골 {expected_total:.2f}골로 오버 {line} 유력"
        else:
            reasoning = f"예상 총 골 {expected_total:.2f}골로 언더 {line} 유력"

        return OverUnderPrediction(
            line=line,
            over_prob=round(over_prob, 2),
            under_prob=round(under_prob, 2),
            recommended_side=recommended,
            confidence=round(confidence, 1),
            value_rating=round(value_rating, 1),
            expected_total_goals=round(expected_total, 2),
            reasoning=reasoning
        )

    def predict_btts(
        self,
        expected_home_goals: float,
        expected_away_goals: float
    ) -> Tuple[float, float]:
        """양팀 득점(BTTS) 예측"""
        prob_matrix = self._calculate_score_matrix(expected_home_goals, expected_away_goals)

        btts_yes = 0.0
        btts_no = 0.0

        for h in range(7):
            for a in range(7):
                prob = prob_matrix[h][a]
                if h > 0 and a > 0:
                    btts_yes += prob
                else:
                    btts_no += prob

        total = btts_yes + btts_no
        if total > 0:
            btts_yes = btts_yes / total * 100
            btts_no = btts_no / total * 100

        return round(btts_yes, 2), round(btts_no, 2)

    def predict_clean_sheet(
        self,
        expected_home_goals: float,
        expected_away_goals: float
    ) -> Tuple[float, float]:
        """클린시트 확률 예측"""
        # 포아송 분포로 0골 확률 계산
        home_clean = math.exp(-expected_away_goals) * 100
        away_clean = math.exp(-expected_home_goals) * 100

        return round(home_clean, 2), round(away_clean, 2)

    def predict_all_markets(
        self,
        expected_home_goals: float,
        expected_away_goals: float,
        handicap_line: float = -0.5,
        over_under_line: float = 2.5,
        odds: Optional[Dict[str, float]] = None
    ) -> MarketPrediction:
        """모든 마켓 종합 예측"""
        odds = odds or {}

        handicap = self.predict_handicap(
            expected_home_goals,
            expected_away_goals,
            handicap_line,
            odds.get("handicap_home"),
            odds.get("handicap_away")
        )

        over_under = self.predict_over_under(
            expected_home_goals,
            expected_away_goals,
            over_under_line,
            odds.get("over"),
            odds.get("under")
        )

        btts_yes, btts_no = self.predict_btts(expected_home_goals, expected_away_goals)
        btts_recommendation = "Yes" if btts_yes > 55 else ("No" if btts_no > 55 else "Pass")

        clean_home, clean_away = self.predict_clean_sheet(expected_home_goals, expected_away_goals)

        return MarketPrediction(
            handicap=handicap,
            over_under=over_under,
            btts_yes_prob=btts_yes,
            btts_no_prob=btts_no,
            btts_recommendation=btts_recommendation,
            clean_sheet_home_prob=clean_home,
            clean_sheet_away_prob=clean_away
        )

    def _calculate_score_matrix(
        self,
        expected_home: float,
        expected_away: float,
        max_goals: int = 7
    ) -> List[List[float]]:
        """점수 확률 매트릭스 계산"""
        cache_key = f"{expected_home:.2f}_{expected_away:.2f}"
        if cache_key in self.poisson_cache:
            return self.poisson_cache[cache_key]

        matrix = []
        for h in range(max_goals):
            row = []
            for a in range(max_goals):
                prob = self._poisson_prob(h, expected_home) * self._poisson_prob(a, expected_away)
                row.append(prob)
            matrix.append(row)

        self.poisson_cache[cache_key] = matrix
        return matrix

    def _poisson_prob(self, k: int, lambda_: float) -> float:
        """포아송 확률 계산"""
        if lambda_ <= 0:
            return 1.0 if k == 0 else 0.0
        return (lambda_ ** k) * math.exp(-lambda_) / math.factorial(k)

    def get_best_handicap_line(
        self,
        expected_home_goals: float,
        expected_away_goals: float,
        available_lines: List[float] = None
    ) -> HandicapPrediction:
        """가장 유리한 핸디캡 라인 찾기"""
        if available_lines is None:
            available_lines = [-2.5, -2.0, -1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5, 2.0, 2.5]

        best_prediction = None
        best_edge = 0

        for line in available_lines:
            pred = self.predict_handicap(expected_home_goals, expected_away_goals, line)
            edge = max(pred.home_cover_prob, pred.away_cover_prob) - 50

            if edge > best_edge:
                best_edge = edge
                best_prediction = pred

        return best_prediction or self.predict_handicap(expected_home_goals, expected_away_goals, -0.5)

    def get_best_over_under_line(
        self,
        expected_home_goals: float,
        expected_away_goals: float,
        available_lines: List[float] = None
    ) -> OverUnderPrediction:
        """가장 유리한 오버/언더 라인 찾기"""
        if available_lines is None:
            available_lines = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]

        best_prediction = None
        best_edge = 0

        for line in available_lines:
            pred = self.predict_over_under(expected_home_goals, expected_away_goals, line)
            edge = max(pred.over_prob, pred.under_prob) - 50

            if edge > best_edge:
                best_edge = edge
                best_prediction = pred

        return best_prediction or self.predict_over_under(expected_home_goals, expected_away_goals, 2.5)

    def to_dict(self, prediction: MarketPrediction) -> Dict[str, Any]:
        """예측 결과를 딕셔너리로 변환"""
        return {
            "handicap": {
                "line": prediction.handicap.handicap_line,
                "home_cover_prob": prediction.handicap.home_cover_prob,
                "away_cover_prob": prediction.handicap.away_cover_prob,
                "recommended": prediction.handicap.recommended_side.value,
                "confidence": prediction.handicap.confidence,
                "value_rating": prediction.handicap.value_rating,
                "reasoning": prediction.handicap.reasoning
            },
            "over_under": {
                "line": prediction.over_under.line,
                "over_prob": prediction.over_under.over_prob,
                "under_prob": prediction.over_under.under_prob,
                "recommended": prediction.over_under.recommended_side.value,
                "confidence": prediction.over_under.confidence,
                "value_rating": prediction.over_under.value_rating,
                "expected_total": prediction.over_under.expected_total_goals,
                "reasoning": prediction.over_under.reasoning
            },
            "btts": {
                "yes_prob": prediction.btts_yes_prob,
                "no_prob": prediction.btts_no_prob,
                "recommendation": prediction.btts_recommendation
            },
            "clean_sheet": {
                "home_prob": prediction.clean_sheet_home_prob,
                "away_prob": prediction.clean_sheet_away_prob
            }
        }


# 싱글톤 인스턴스
_predictor: Optional[MarketPredictor] = None


def get_market_predictor() -> MarketPredictor:
    """싱글톤 예측기 반환"""
    global _predictor
    if _predictor is None:
        _predictor = MarketPredictor()
    return _predictor


# 테스트
if __name__ == "__main__":
    predictor = MarketPredictor()

    # Liverpool vs Manchester United 예시
    home_xg = 2.1
    away_xg = 1.2

    print("\n[마켓 예측 결과]")
    print(f"예상 골: 홈 {home_xg}, 원정 {away_xg}")

    # 핸디캡
    handicap = predictor.predict_handicap(home_xg, away_xg, -1.5)
    print(f"\n핸디캡 -1.5:")
    print(f"  홈 커버: {handicap.home_cover_prob}%")
    print(f"  원정 커버: {handicap.away_cover_prob}%")
    print(f"  추천: {handicap.recommended_side.value} (신뢰도 {handicap.confidence}%)")

    # 오버/언더
    over_under = predictor.predict_over_under(home_xg, away_xg, 2.5)
    print(f"\n오버/언더 2.5:")
    print(f"  오버: {over_under.over_prob}%")
    print(f"  언더: {over_under.under_prob}%")
    print(f"  추천: {over_under.recommended_side.value} (신뢰도 {over_under.confidence}%)")

    # BTTS
    btts_yes, btts_no = predictor.predict_btts(home_xg, away_xg)
    print(f"\nBTTS:")
    print(f"  Yes: {btts_yes}%")
    print(f"  No: {btts_no}%")

    # 전체 마켓
    all_markets = predictor.predict_all_markets(home_xg, away_xg)
    print(f"\n클린시트:")
    print(f"  홈: {all_markets.clean_sheet_home_prob}%")
    print(f"  원정: {all_markets.clean_sheet_away_prob}%")
