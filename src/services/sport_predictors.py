"""
G-03, G-04, G-05: 스포츠별 예측 모듈
- 야구 승1패 예측 (KBO, MLB 등)
- 농구 승5패 예측 (KBL, NBA 등)
- 기록식 예측 (코너킥, 카드 수 등)
"""

from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import math


class SportType(Enum):
    BASEBALL = "baseball"
    BASKETBALL = "basketball"
    SOCCER = "soccer"


@dataclass
class BaseballPrediction:
    """야구 승1패 예측 결과"""
    home_win_prob: float
    away_win_prob: float
    recommended: str  # "home" or "away"
    confidence: float
    run_line: float  # 핸디캡
    over_under_line: float
    over_prob: float
    under_prob: float
    expected_home_runs: float
    expected_away_runs: float
    factors: Dict[str, float]
    reasoning: str


@dataclass
class BasketballPrediction:
    """농구 승5패 예측 결과"""
    home_win_prob: float
    away_win_prob: float
    recommended: str
    confidence: float
    spread: float  # 핸디캡
    spread_home_prob: float
    spread_away_prob: float
    total_line: float
    over_prob: float
    under_prob: float
    expected_home_score: float
    expected_away_score: float
    quarter_predictions: List[Dict[str, float]]
    factors: Dict[str, float]
    reasoning: str


@dataclass
class RecordPrediction:
    """기록식 예측 결과"""
    record_type: str  # "corners", "cards", "goals", etc.
    line: float
    over_prob: float
    under_prob: float
    recommended: str  # "over" or "under"
    confidence: float
    expected_value: float
    factors: Dict[str, float]
    reasoning: str


class BaseballPredictor:
    """
    G-03: 야구 승1패 예측기
    - 선발 투수 분석
    - 타선 상성
    - 홈/원정 성적
    - 최근 폼
    """

    def __init__(self):
        self.home_advantage = 0.54  # 야구 홈 승률 평균

    def predict(
        self,
        home_team: str,
        away_team: str,
        # 선발 투수 정보
        home_pitcher_era: float = 4.00,
        away_pitcher_era: float = 4.00,
        home_pitcher_whip: float = 1.30,
        away_pitcher_whip: float = 1.30,
        home_pitcher_k9: float = 8.0,
        away_pitcher_k9: float = 8.0,
        # 팀 타격 정보
        home_team_ops: float = 0.750,
        away_team_ops: float = 0.750,
        home_team_avg: float = 0.260,
        away_team_avg: float = 0.260,
        # 최근 성적
        home_last10: str = "5-5",  # "W-L"
        away_last10: str = "5-5",
        # 상대 전적
        h2h_home_wins: int = 5,
        h2h_away_wins: int = 5,
        # 배당률 (옵션)
        home_odds: Optional[float] = None,
        away_odds: Optional[float] = None
    ) -> BaseballPrediction:
        """야구 경기 예측"""
        factors = {}

        # 1. 선발 투수 분석 (40% 가중치)
        era_diff = away_pitcher_era - home_pitcher_era
        whip_diff = away_pitcher_whip - home_pitcher_whip
        k9_diff = home_pitcher_k9 - away_pitcher_k9

        pitcher_score = (era_diff * 3 + whip_diff * 2 + k9_diff * 0.5) / 5.5
        factors["pitcher"] = min(1, max(-1, pitcher_score / 2))

        # 2. 타선 분석 (30% 가중치)
        ops_diff = home_team_ops - away_team_ops
        avg_diff = home_team_avg - away_team_avg

        batting_score = ops_diff * 2 + avg_diff * 5
        factors["batting"] = min(1, max(-1, batting_score))

        # 3. 최근 폼 (15% 가중치)
        home_wins, home_losses = map(int, home_last10.split("-"))
        away_wins, away_losses = map(int, away_last10.split("-"))

        home_form = home_wins / 10
        away_form = away_wins / 10
        form_diff = home_form - away_form
        factors["form"] = form_diff

        # 4. 상대전적 (10% 가중치)
        total_h2h = h2h_home_wins + h2h_away_wins
        if total_h2h > 0:
            h2h_factor = (h2h_home_wins - h2h_away_wins) / total_h2h
        else:
            h2h_factor = 0
        factors["h2h"] = h2h_factor

        # 5. 홈 이점 (5% 가중치)
        factors["home_advantage"] = 0.08  # 야구 홈 이점 약 4%

        # 종합 점수 계산
        weights = {
            "pitcher": 0.40,
            "batting": 0.30,
            "form": 0.15,
            "h2h": 0.10,
            "home_advantage": 0.05
        }

        total_score = sum(factors[k] * weights[k] for k in weights)

        # 확률 변환
        home_prob = 0.5 + total_score * 0.3  # -30% ~ +30% 조정
        home_prob = min(0.75, max(0.25, home_prob))
        away_prob = 1 - home_prob

        # 예상 득점
        league_avg_runs = 4.5
        home_run_factor = 1 + factors["batting"] * 0.2 - factors["pitcher"] * 0.1
        away_run_factor = 1 - factors["batting"] * 0.2 + factors["pitcher"] * 0.1

        expected_home = league_avg_runs * home_run_factor
        expected_away = league_avg_runs * away_run_factor

        # 오버/언더
        total_runs = expected_home + expected_away
        over_under_line = round(total_runs * 2) / 2  # 0.5 단위로 반올림

        over_prob = 0.5 + (total_runs - over_under_line) * 0.15
        over_prob = min(0.70, max(0.30, over_prob))
        under_prob = 1 - over_prob

        # 런라인 (핸디캡)
        run_diff = expected_home - expected_away
        run_line = -1.5 if run_diff > 0.5 else (1.5 if run_diff < -0.5 else 0)

        # 추천 및 신뢰도
        recommended = "home" if home_prob > away_prob else "away"
        confidence = abs(home_prob - 0.5) * 2 * 100

        # 추론
        reasoning = self._generate_reasoning(factors, home_team, away_team)

        return BaseballPrediction(
            home_win_prob=round(home_prob * 100, 2),
            away_win_prob=round(away_prob * 100, 2),
            recommended=recommended,
            confidence=round(confidence, 1),
            run_line=run_line,
            over_under_line=over_under_line,
            over_prob=round(over_prob * 100, 2),
            under_prob=round(under_prob * 100, 2),
            expected_home_runs=round(expected_home, 2),
            expected_away_runs=round(expected_away, 2),
            factors={k: round(v, 3) for k, v in factors.items()},
            reasoning=reasoning
        )

    def _generate_reasoning(
        self,
        factors: Dict[str, float],
        home_team: str,
        away_team: str
    ) -> str:
        """추론 생성"""
        reasons = []

        if abs(factors["pitcher"]) > 0.2:
            better = home_team if factors["pitcher"] > 0 else away_team
            reasons.append(f"{better} 선발 투수 우위")

        if abs(factors["batting"]) > 0.1:
            better = home_team if factors["batting"] > 0 else away_team
            reasons.append(f"{better} 타선 우세")

        if abs(factors["form"]) > 0.2:
            better = home_team if factors["form"] > 0 else away_team
            reasons.append(f"{better} 최근 폼 좋음")

        if not reasons:
            reasons.append("양 팀 전력 균형")

        return ", ".join(reasons)


class BasketballPredictor:
    """
    G-04: 농구 승5패 예측기
    - 공격/수비 효율
    - 페이스 (100 포제션당 득점)
    - 최근 폼
    - 홈/원정 성적
    """

    def __init__(self):
        self.home_advantage = 0.60  # 농구 홈 승률 평균

    def predict(
        self,
        home_team: str,
        away_team: str,
        # 공격/수비 효율 (100 포제션당)
        home_off_rating: float = 110.0,
        away_off_rating: float = 110.0,
        home_def_rating: float = 110.0,
        away_def_rating: float = 110.0,
        # 페이스 (포제션 수)
        home_pace: float = 100.0,
        away_pace: float = 100.0,
        # 최근 성적
        home_last10: str = "5-5",
        away_last10: str = "5-5",
        # 상대 전적
        h2h_home_wins: int = 2,
        h2h_away_wins: int = 2,
        # 배당률
        spread: float = 0.0,
        total_line: float = 210.0
    ) -> BasketballPrediction:
        """농구 경기 예측"""
        factors = {}

        # 1. 공격력 분석 (30%)
        off_diff = home_off_rating - away_off_rating
        factors["offense"] = min(1, max(-1, off_diff / 10))

        # 2. 수비력 분석 (30%) - 낮을수록 좋음
        def_diff = away_def_rating - home_def_rating
        factors["defense"] = min(1, max(-1, def_diff / 10))

        # 3. 최근 폼 (20%)
        home_wins = int(home_last10.split("-")[0])
        away_wins = int(away_last10.split("-")[0])
        form_diff = (home_wins - away_wins) / 10
        factors["form"] = form_diff

        # 4. 홈 이점 (15%)
        factors["home_advantage"] = 0.2  # 농구 홈 이점 큼

        # 5. 상대전적 (5%)
        total_h2h = h2h_home_wins + h2h_away_wins
        if total_h2h > 0:
            factors["h2h"] = (h2h_home_wins - h2h_away_wins) / total_h2h * 0.5
        else:
            factors["h2h"] = 0

        # 종합 점수
        weights = {"offense": 0.30, "defense": 0.30, "form": 0.20,
                   "home_advantage": 0.15, "h2h": 0.05}
        total_score = sum(factors[k] * weights[k] for k in weights)

        # 확률 변환
        home_prob = 0.5 + total_score * 0.4
        home_prob = min(0.80, max(0.20, home_prob))
        away_prob = 1 - home_prob

        # 예상 점수 계산
        avg_pace = (home_pace + away_pace) / 2
        possessions = avg_pace * 2  # 양 팀 포제션

        expected_home = (home_off_rating + (110 - away_def_rating)) / 200 * possessions
        expected_away = (away_off_rating + (110 - home_def_rating)) / 200 * possessions

        # 홈 이점 추가
        expected_home *= 1.03
        expected_away *= 0.97

        # 스프레드 예측
        point_diff = expected_home - expected_away
        spread_home_prob = 0.5 + (point_diff + spread) * 0.03
        spread_home_prob = min(0.75, max(0.25, spread_home_prob))

        # 오버/언더
        total_score = expected_home + expected_away
        over_prob = 0.5 + (total_score - total_line) * 0.025
        over_prob = min(0.70, max(0.30, over_prob))

        # 쿼터별 예측 (대략적)
        quarter_home = expected_home / 4
        quarter_away = expected_away / 4
        quarter_predictions = [
            {"quarter": i + 1, "home": round(quarter_home, 1), "away": round(quarter_away, 1)}
            for i in range(4)
        ]

        # 추천 및 신뢰도
        recommended = "home" if home_prob > away_prob else "away"
        confidence = abs(home_prob - 0.5) * 2 * 100

        reasoning = self._generate_reasoning(factors, home_team, away_team)

        return BasketballPrediction(
            home_win_prob=round(home_prob * 100, 2),
            away_win_prob=round(away_prob * 100, 2),
            recommended=recommended,
            confidence=round(confidence, 1),
            spread=spread,
            spread_home_prob=round(spread_home_prob * 100, 2),
            spread_away_prob=round((1 - spread_home_prob) * 100, 2),
            total_line=total_line,
            over_prob=round(over_prob * 100, 2),
            under_prob=round((1 - over_prob) * 100, 2),
            expected_home_score=round(expected_home, 1),
            expected_away_score=round(expected_away, 1),
            quarter_predictions=quarter_predictions,
            factors={k: round(v, 3) for k, v in factors.items()},
            reasoning=reasoning
        )

    def _generate_reasoning(
        self,
        factors: Dict[str, float],
        home_team: str,
        away_team: str
    ) -> str:
        """추론 생성"""
        reasons = []

        if abs(factors["offense"]) > 0.1:
            better = home_team if factors["offense"] > 0 else away_team
            reasons.append(f"{better} 공격력 우세")

        if abs(factors["defense"]) > 0.1:
            better = home_team if factors["defense"] > 0 else away_team
            reasons.append(f"{better} 수비력 우세")

        if factors["home_advantage"] > 0.1:
            reasons.append(f"{home_team} 홈 어드밴티지")

        return ", ".join(reasons) if reasons else "균형 잡힌 경기 예상"


class RecordPredictor:
    """
    G-05: 기록식 예측기
    - 코너킥 수
    - 카드 수
    - 득점 (정확한 스코어)
    - 기타 기록
    """

    def __init__(self):
        self.league_averages = {
            "corners": {
                "premier_league": 10.5,
                "la_liga": 9.8,
                "bundesliga": 10.2,
                "serie_a": 10.0,
                "default": 10.0
            },
            "cards": {
                "premier_league": 3.2,
                "la_liga": 4.5,
                "bundesliga": 3.8,
                "serie_a": 4.2,
                "default": 3.8
            }
        }

    def predict_corners(
        self,
        home_team: str,
        away_team: str,
        home_corners_for: float = 5.5,
        home_corners_against: float = 4.5,
        away_corners_for: float = 5.0,
        away_corners_against: float = 5.0,
        league: str = "default",
        line: float = 10.5
    ) -> RecordPrediction:
        """코너킥 예측"""
        # 예상 코너킥 수 계산
        home_corners = (home_corners_for + away_corners_against) / 2
        away_corners = (away_corners_for + home_corners_against) / 2

        total_expected = home_corners + away_corners

        # 리그 평균 조정
        league_avg = self.league_averages["corners"].get(league, 10.0)
        adjusted_total = (total_expected + league_avg) / 2

        # 확률 계산 (포아송 기반)
        over_prob = self._poisson_over_prob(adjusted_total, line)

        factors = {
            "home_corners_avg": home_corners,
            "away_corners_avg": away_corners,
            "league_avg": league_avg,
            "expected_total": adjusted_total
        }

        recommended = "over" if over_prob > 0.55 else "under"
        confidence = abs(over_prob - 0.5) * 200

        reasoning = f"예상 코너킥 {adjusted_total:.1f}개 (라인 {line})"

        return RecordPrediction(
            record_type="corners",
            line=line,
            over_prob=round(over_prob * 100, 2),
            under_prob=round((1 - over_prob) * 100, 2),
            recommended=recommended,
            confidence=round(confidence, 1),
            expected_value=round(adjusted_total, 2),
            factors=factors,
            reasoning=reasoning
        )

    def predict_cards(
        self,
        home_team: str,
        away_team: str,
        home_cards_for: float = 1.8,
        home_cards_against: float = 1.6,
        away_cards_for: float = 2.0,
        away_cards_against: float = 1.8,
        league: str = "default",
        line: float = 4.5,
        referee_avg_cards: Optional[float] = None
    ) -> RecordPrediction:
        """카드 수 예측"""
        # 팀별 예상 카드
        home_cards = (home_cards_for + away_cards_against) / 2
        away_cards = (away_cards_for + home_cards_against) / 2

        total_expected = home_cards + away_cards

        # 심판 스타일 반영
        if referee_avg_cards:
            league_avg = self.league_averages["cards"].get(league, 3.8)
            referee_factor = referee_avg_cards / league_avg
            total_expected *= referee_factor

        # 확률 계산
        over_prob = self._poisson_over_prob(total_expected, line)

        factors = {
            "home_cards_avg": home_cards,
            "away_cards_avg": away_cards,
            "expected_total": total_expected,
            "referee_factor": referee_avg_cards or "N/A"
        }

        recommended = "over" if over_prob > 0.55 else "under"
        confidence = abs(over_prob - 0.5) * 200

        reasoning = f"예상 카드 {total_expected:.1f}장 (라인 {line})"

        return RecordPrediction(
            record_type="cards",
            line=line,
            over_prob=round(over_prob * 100, 2),
            under_prob=round((1 - over_prob) * 100, 2),
            recommended=recommended,
            confidence=round(confidence, 1),
            expected_value=round(total_expected, 2),
            factors=factors,
            reasoning=reasoning
        )

    def predict_exact_score(
        self,
        expected_home_goals: float,
        expected_away_goals: float,
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """정확한 스코어 예측"""
        scores = []

        for h in range(6):
            for a in range(6):
                prob = self._poisson_prob(h, expected_home_goals) * \
                       self._poisson_prob(a, expected_away_goals)
                scores.append({
                    "score": f"{h}-{a}",
                    "home_goals": h,
                    "away_goals": a,
                    "probability": round(prob * 100, 2)
                })

        # 확률순 정렬
        scores.sort(key=lambda x: x["probability"], reverse=True)
        return scores[:top_n]

    def _poisson_prob(self, k: int, lambda_: float) -> float:
        """포아송 확률"""
        if lambda_ <= 0:
            return 1.0 if k == 0 else 0.0
        return (lambda_ ** k) * math.exp(-lambda_) / math.factorial(k)

    def _poisson_over_prob(self, expected: float, line: float) -> float:
        """포아송 분포로 오버 확률 계산"""
        under_prob = sum(
            self._poisson_prob(k, expected)
            for k in range(int(line) + 1)
        )
        return 1 - under_prob


# 싱글톤 인스턴스
_baseball: Optional[BaseballPredictor] = None
_basketball: Optional[BasketballPredictor] = None
_record: Optional[RecordPredictor] = None


def get_baseball_predictor() -> BaseballPredictor:
    global _baseball
    if _baseball is None:
        _baseball = BaseballPredictor()
    return _baseball


def get_basketball_predictor() -> BasketballPredictor:
    global _basketball
    if _basketball is None:
        _basketball = BasketballPredictor()
    return _basketball


def get_record_predictor() -> RecordPredictor:
    global _record
    if _record is None:
        _record = RecordPredictor()
    return _record


# 테스트
if __name__ == "__main__":
    print("\n[야구 예측 테스트]")
    baseball = get_baseball_predictor()
    result = baseball.predict(
        home_team="LG 트윈스",
        away_team="삼성 라이온즈",
        home_pitcher_era=3.50,
        away_pitcher_era=4.20,
        home_team_ops=0.780,
        away_team_ops=0.720,
        home_last10="7-3",
        away_last10="4-6"
    )
    print(f"  {result.home_win_prob}% vs {result.away_win_prob}%")
    print(f"  추천: {result.recommended} (신뢰도 {result.confidence}%)")
    print(f"  오버/언더 {result.over_under_line}: {result.over_prob}%/{result.under_prob}%")

    print("\n[농구 예측 테스트]")
    basketball = get_basketball_predictor()
    result = basketball.predict(
        home_team="서울 SK",
        away_team="부산 KT",
        home_off_rating=112.5,
        away_off_rating=108.3,
        home_def_rating=107.2,
        away_def_rating=110.5,
        home_last10="8-2",
        away_last10="5-5"
    )
    print(f"  {result.home_win_prob}% vs {result.away_win_prob}%")
    print(f"  예상 점수: {result.expected_home_score} - {result.expected_away_score}")
    print(f"  오버/언더 {result.total_line}: {result.over_prob}%/{result.under_prob}%")

    print("\n[기록식 예측 테스트 - 코너킥]")
    record = get_record_predictor()
    corners = record.predict_corners(
        home_team="리버풀",
        away_team="맨체스터 시티",
        home_corners_for=6.2,
        home_corners_against=4.8,
        away_corners_for=6.5,
        away_corners_against=4.2,
        line=11.5
    )
    print(f"  오버 {corners.line}: {corners.over_prob}%")
    print(f"  예상 코너킥: {corners.expected_value}개")

    print("\n[정확한 스코어 예측]")
    scores = record.predict_exact_score(1.8, 1.2)
    for s in scores:
        print(f"  {s['score']}: {s['probability']}%")
