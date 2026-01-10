"""
강화된 이변 감지 시스템 (v4.0.0)

핵심 목적:
프로토 14경기는 ALL or NOTHING! 13경기 맞추고 1경기 틀리면 전액 손실.
따라서 "확률 높은 경기"보다 "이변 가능한 경기"를 정확히 식별하는 것이 핵심.

이변 신호 카테고리:
1. 확률/신뢰도 기반 (기존)
   - 확률 분포가 애매함
   - AI 신뢰도가 낮음
   - AI 간 의견 불일치

2. 폼 기반 (신규)
   - 상위팀 연패 중
   - 하위팀 연승 중
   - 홈/원정 성적 반전

3. 상대전적 기반 (신규)
   - 배당과 반대되는 상대전적
   - 언더독이 최근 우세

4. 상황 기반 (신규)
   - 주요 선수 부상
   - 강등권 생존 경기
   - 우승 확정/탈락 팀

사용 예시:
    from src.services.data.enhanced_upset_detector import EnhancedUpsetDetector

    detector = EnhancedUpsetDetector()

    # 단일 경기 이변 분석
    upset_analysis = detector.analyze_upset_potential(
        home_team="Arsenal",
        away_team="Liverpool",
        home_stats={"league_position": 1, ...},
        away_stats={"league_position": 5, ...},
        home_form={"winning_streak": 0, "losing_streak": 2, ...},
        away_form={"winning_streak": 4, ...},
        h2h={"home_wins": 2, "away_wins": 5, ...},
        home_injuries={"total": 3, "key_players": ["Saka"]},
        away_injuries={"total": 0},
        odds={"home": 1.85, "draw": 3.60, "away": 4.20},
        ai_confidence=0.65,
        ai_agreement=0.55,
    )

    print(f"이변 점수: {upset_analysis['upset_score']}")
    print(f"이변 위험: {upset_analysis['upset_risk']}")
    print(f"복수 베팅 권장: {upset_analysis['multi_bet_recommended']}")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# 이변 감지 상수
# =============================================================================

class UpsetSignalWeights:
    """이변 신호별 가중치

    총점 100점 만점 기준
    - 50점 이상: 높은 이변 가능성 (반드시 복수 베팅)
    - 30-49점: 중간 이변 가능성 (복수 베팅 권장)
    - 30점 미만: 낮은 이변 가능성 (단일 베팅 가능)
    """

    # ========== 확률/신뢰도 기반 (최대 40점) ==========
    # 확률 분포 애매함 (1위-2위 차이)
    PROB_GAP_VERY_SMALL = (0.10, 15)  # 10% 미만 차이 → 15점
    PROB_GAP_SMALL = (0.15, 12)       # 15% 미만 차이 → 12점
    PROB_GAP_MEDIUM = (0.20, 8)       # 20% 미만 차이 → 8점
    PROB_GAP_LARGE = (0.25, 4)        # 25% 미만 차이 → 4점

    # AI 신뢰도 낮음
    CONFIDENCE_VERY_LOW = (0.40, 12)   # 40% 미만 → 12점
    CONFIDENCE_LOW = (0.50, 8)         # 50% 미만 → 8점
    CONFIDENCE_MEDIUM = (0.60, 4)      # 60% 미만 → 4점

    # AI 불일치
    AI_DISAGREEMENT_HIGH = (0.50, 13)   # 50% 미만 일치 → 13점
    AI_DISAGREEMENT_MEDIUM = (0.60, 8)  # 60% 미만 일치 → 8점
    AI_DISAGREEMENT_LOW = (0.70, 4)     # 70% 미만 일치 → 4점

    # ========== 폼 기반 (최대 25점) ==========
    # 강팀 연패
    FAVORITE_LOSING_STREAK_3 = 10  # 배당 우세팀 3연패 → 10점
    FAVORITE_LOSING_STREAK_2 = 6   # 배당 우세팀 2연패 → 6점

    # 약팀 연승
    UNDERDOG_WINNING_STREAK_3 = 10  # 배당 열세팀 3연승 → 10점
    UNDERDOG_WINNING_STREAK_2 = 6   # 배당 열세팀 2연승 → 6점

    # 홈/원정 성적 역전
    HOME_AWAY_REVERSAL = 8  # 홈 성적 < 원정 성적 (비정상) → 8점

    # ========== 상대전적 기반 (최대 15점) ==========
    # 배당과 반대되는 상대전적
    H2H_OPPOSITE_TO_ODDS = 12  # 배당 열세팀이 상대전적 우세 → 12점
    H2H_EVEN = 5               # 상대전적 균형 → 5점

    # ========== 상황 기반 (최대 20점) ==========
    # 주요 선수 부상
    KEY_PLAYER_INJURY = 8       # 주전 공격수/GK 부상 → 8점
    MULTIPLE_INJURIES = 5       # 3명 이상 부상 → 5점

    # 시즌 상황
    RELEGATION_BATTLE = 7       # 강등권 생존 경기 → 7점
    NOTHING_TO_PLAY = 5         # 시즌 목표 달성/포기 팀 → 5점

    # 더비/라이벌
    DERBY_MATCH = 6             # 더비/라이벌전 → 6점


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class UpsetSignal:
    """개별 이변 신호"""
    category: str          # "probability", "form", "h2h", "situation"
    signal_name: str       # "favorite_losing_streak"
    score: float           # 점수
    description: str       # "맨시티 3연패 중"
    importance: str = "medium"  # "high", "medium", "low"


@dataclass
class UpsetAnalysis:
    """경기 이변 분석 결과"""
    home_team: str
    away_team: str

    # 이변 점수
    upset_score: float     # 총점 (0-100)
    upset_risk: str        # "high", "medium", "low"

    # 복수 베팅 권장
    multi_bet_recommended: bool
    multi_bet_selections: List[str]  # ["1", "X"] 또는 ["승", "5"]

    # 이변 신호 상세
    signals: List[UpsetSignal] = field(default_factory=list)

    # 요약
    summary: str = ""
    key_upset_factors: List[str] = field(default_factory=list)

    # 메타데이터
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "upset_score": self.upset_score,
            "upset_risk": self.upset_risk,
            "multi_bet_recommended": self.multi_bet_recommended,
            "multi_bet_selections": self.multi_bet_selections,
            "signals": [
                {
                    "category": s.category,
                    "signal_name": s.signal_name,
                    "score": s.score,
                    "description": s.description,
                    "importance": s.importance,
                }
                for s in self.signals
            ],
            "summary": self.summary,
            "key_upset_factors": self.key_upset_factors,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


# =============================================================================
# EnhancedUpsetDetector 클래스
# =============================================================================

class EnhancedUpsetDetector:
    """강화된 이변 감지기

    기존 확률/신뢰도 기반 감지에 더해:
    - 폼 기반 이변 신호
    - 상대전적 기반 이변 신호
    - 상황 기반 이변 신호
    """

    # 복수 베팅 임계값
    MULTI_BET_THRESHOLD_HIGH = 50    # 50점 이상: 반드시 복수
    MULTI_BET_THRESHOLD_MEDIUM = 30  # 30점 이상: 복수 권장

    def __init__(self):
        """초기화"""
        self.weights = UpsetSignalWeights()
        logger.info("EnhancedUpsetDetector 초기화 완료")

    def analyze_upset_potential(
        self,
        home_team: str,
        away_team: str,
        # AI 분석 결과
        ai_probs: Optional[Dict[str, float]] = None,  # {"home": 0.45, "draw": 0.28, "away": 0.27}
        ai_confidence: float = 0.5,
        ai_agreement: float = 0.5,
        # 실시간 데이터
        home_stats: Optional[Dict] = None,
        away_stats: Optional[Dict] = None,
        home_form: Optional[Dict] = None,
        away_form: Optional[Dict] = None,
        h2h: Optional[Dict] = None,
        home_injuries: Optional[Dict] = None,
        away_injuries: Optional[Dict] = None,
        odds: Optional[Dict[str, float]] = None,  # {"home": 1.85, "draw": 3.60, "away": 4.20}
        # 옵션
        sport_type: str = "soccer",
    ) -> UpsetAnalysis:
        """이변 가능성 분석

        Args:
            home_team: 홈팀명
            away_team: 원정팀명
            ai_probs: AI 예측 확률
            ai_confidence: AI 신뢰도 (0-1)
            ai_agreement: AI 일치도 (0-1)
            home_stats: 홈팀 시즌 통계
            away_stats: 원정팀 시즌 통계
            home_form: 홈팀 최근 폼
            away_form: 원정팀 최근 폼
            h2h: 상대전적
            home_injuries: 홈팀 부상자
            away_injuries: 원정팀 부상자
            odds: 배당률
            sport_type: "soccer" or "basketball"

        Returns:
            UpsetAnalysis 객체
        """
        signals: List[UpsetSignal] = []

        # 배당 우세팀 판단
        favorite = self._determine_favorite(odds)

        # 1. 확률/신뢰도 기반 신호
        prob_signals = self._analyze_probability_signals(
            ai_probs, ai_confidence, ai_agreement
        )
        signals.extend(prob_signals)

        # 2. 폼 기반 신호
        form_signals = self._analyze_form_signals(
            home_form, away_form, favorite, home_team, away_team
        )
        signals.extend(form_signals)

        # 3. 상대전적 기반 신호
        h2h_signals = self._analyze_h2h_signals(
            h2h, favorite, home_team, away_team, odds
        )
        signals.extend(h2h_signals)

        # 4. 상황 기반 신호
        situation_signals = self._analyze_situation_signals(
            home_stats, away_stats, home_injuries, away_injuries,
            home_team, away_team, favorite
        )
        signals.extend(situation_signals)

        # 총점 계산
        upset_score = sum(s.score for s in signals)
        upset_score = min(100, upset_score)  # 최대 100점

        # 이변 위험도 판정
        if upset_score >= self.MULTI_BET_THRESHOLD_HIGH:
            upset_risk = "high"
            multi_bet_recommended = True
        elif upset_score >= self.MULTI_BET_THRESHOLD_MEDIUM:
            upset_risk = "medium"
            multi_bet_recommended = True
        else:
            upset_risk = "low"
            multi_bet_recommended = False

        # 복수 베팅 선택지 결정
        multi_selections = self._determine_multi_selections(
            ai_probs, odds, sport_type, upset_risk
        )

        # 핵심 이변 요인 추출
        key_factors = [
            s.description for s in signals
            if s.importance == "high" or s.score >= 8
        ][:3]  # 상위 3개

        # 요약 생성
        summary = self._generate_summary(
            home_team, away_team, upset_score, upset_risk, signals
        )

        return UpsetAnalysis(
            home_team=home_team,
            away_team=away_team,
            upset_score=upset_score,
            upset_risk=upset_risk,
            multi_bet_recommended=multi_bet_recommended,
            multi_bet_selections=multi_selections,
            signals=signals,
            summary=summary,
            key_upset_factors=key_factors,
        )

    def _determine_favorite(self, odds: Optional[Dict]) -> str:
        """배당 기준 우세팀 판단

        Returns:
            "home", "away", or "even"
        """
        if not odds:
            return "even"

        home_odds = odds.get("home", 2.0)
        away_odds = odds.get("away", 2.0)

        if home_odds < away_odds * 0.8:  # 홈 배당이 20% 이상 낮으면
            return "home"
        elif away_odds < home_odds * 0.8:
            return "away"
        else:
            return "even"

    def _analyze_probability_signals(
        self,
        ai_probs: Optional[Dict],
        ai_confidence: float,
        ai_agreement: float,
    ) -> List[UpsetSignal]:
        """확률/신뢰도 기반 이변 신호"""
        signals = []

        # 확률 분포 애매함
        if ai_probs:
            probs = sorted(ai_probs.values(), reverse=True)
            if len(probs) >= 2:
                prob_gap = probs[0] - probs[1]

                if prob_gap < 0.10:
                    signals.append(UpsetSignal(
                        category="probability",
                        signal_name="prob_gap_very_small",
                        score=15,
                        description=f"확률 분포 매우 애매 (차이 {prob_gap:.1%})",
                        importance="high"
                    ))
                elif prob_gap < 0.15:
                    signals.append(UpsetSignal(
                        category="probability",
                        signal_name="prob_gap_small",
                        score=12,
                        description=f"확률 분포 애매 (차이 {prob_gap:.1%})",
                        importance="high"
                    ))
                elif prob_gap < 0.20:
                    signals.append(UpsetSignal(
                        category="probability",
                        signal_name="prob_gap_medium",
                        score=8,
                        description=f"확률 분포 보통 (차이 {prob_gap:.1%})",
                        importance="medium"
                    ))

        # AI 신뢰도 낮음
        if ai_confidence < 0.40:
            signals.append(UpsetSignal(
                category="probability",
                signal_name="low_confidence",
                score=12,
                description=f"AI 신뢰도 매우 낮음 ({ai_confidence:.0%})",
                importance="high"
            ))
        elif ai_confidence < 0.50:
            signals.append(UpsetSignal(
                category="probability",
                signal_name="low_confidence",
                score=8,
                description=f"AI 신뢰도 낮음 ({ai_confidence:.0%})",
                importance="medium"
            ))

        # AI 불일치
        if ai_agreement > 0:
            if ai_agreement < 0.50:
                signals.append(UpsetSignal(
                    category="probability",
                    signal_name="ai_disagreement",
                    score=13,
                    description=f"AI 의견 크게 불일치 ({ai_agreement:.0%})",
                    importance="high"
                ))
            elif ai_agreement < 0.60:
                signals.append(UpsetSignal(
                    category="probability",
                    signal_name="ai_disagreement",
                    score=8,
                    description=f"AI 의견 불일치 ({ai_agreement:.0%})",
                    importance="medium"
                ))

        return signals

    def _analyze_form_signals(
        self,
        home_form: Optional[Dict],
        away_form: Optional[Dict],
        favorite: str,
        home_team: str,
        away_team: str,
    ) -> List[UpsetSignal]:
        """폼 기반 이변 신호"""
        signals = []

        if not home_form and not away_form:
            return signals

        # 홈팀 폼 분석
        home_losing = home_form.get("losing_streak", 0) if home_form else 0
        home_winning = home_form.get("winning_streak", 0) if home_form else 0

        # 원정팀 폼 분석
        away_losing = away_form.get("losing_streak", 0) if away_form else 0
        away_winning = away_form.get("winning_streak", 0) if away_form else 0

        # 배당 우세팀이 연패 중
        if favorite == "home" and home_losing >= 3:
            signals.append(UpsetSignal(
                category="form",
                signal_name="favorite_losing_streak",
                score=10,
                description=f"⚠️ 배당 우세 {home_team} {home_losing}연패 중!",
                importance="high"
            ))
        elif favorite == "home" and home_losing >= 2:
            signals.append(UpsetSignal(
                category="form",
                signal_name="favorite_losing_streak",
                score=6,
                description=f"배당 우세 {home_team} {home_losing}연패 중",
                importance="medium"
            ))

        if favorite == "away" and away_losing >= 3:
            signals.append(UpsetSignal(
                category="form",
                signal_name="favorite_losing_streak",
                score=10,
                description=f"⚠️ 배당 우세 {away_team} {away_losing}연패 중!",
                importance="high"
            ))
        elif favorite == "away" and away_losing >= 2:
            signals.append(UpsetSignal(
                category="form",
                signal_name="favorite_losing_streak",
                score=6,
                description=f"배당 우세 {away_team} {away_losing}연패 중",
                importance="medium"
            ))

        # 배당 열세팀이 연승 중
        if favorite == "home" and away_winning >= 3:
            signals.append(UpsetSignal(
                category="form",
                signal_name="underdog_winning_streak",
                score=10,
                description=f"🔥 배당 열세 {away_team} {away_winning}연승 중!",
                importance="high"
            ))
        elif favorite == "home" and away_winning >= 2:
            signals.append(UpsetSignal(
                category="form",
                signal_name="underdog_winning_streak",
                score=6,
                description=f"배당 열세 {away_team} {away_winning}연승 중",
                importance="medium"
            ))

        if favorite == "away" and home_winning >= 3:
            signals.append(UpsetSignal(
                category="form",
                signal_name="underdog_winning_streak",
                score=10,
                description=f"🔥 배당 열세 {home_team} {home_winning}연승 중!",
                importance="high"
            ))
        elif favorite == "away" and home_winning >= 2:
            signals.append(UpsetSignal(
                category="form",
                signal_name="underdog_winning_streak",
                score=6,
                description=f"배당 열세 {home_team} {home_winning}연승 중",
                importance="medium"
            ))

        return signals

    def _analyze_h2h_signals(
        self,
        h2h: Optional[Dict],
        favorite: str,
        home_team: str,
        away_team: str,
        odds: Optional[Dict],
    ) -> List[UpsetSignal]:
        """상대전적 기반 이변 신호"""
        signals = []

        if not h2h:
            return signals

        home_wins = h2h.get("home_wins", 0)
        away_wins = h2h.get("away_wins", 0)
        total = h2h.get("total_matches", 0)

        if total < 3:  # 데이터 부족
            return signals

        # 배당과 반대되는 상대전적
        if favorite == "home" and away_wins > home_wins:
            signals.append(UpsetSignal(
                category="h2h",
                signal_name="h2h_opposite_odds",
                score=12,
                description=f"⚡ 상대전적: {away_team}이 우세 ({away_wins}승 vs {home_wins}승) - 배당과 반대!",
                importance="high"
            ))
        elif favorite == "away" and home_wins > away_wins:
            signals.append(UpsetSignal(
                category="h2h",
                signal_name="h2h_opposite_odds",
                score=12,
                description=f"⚡ 상대전적: {home_team}이 우세 ({home_wins}승 vs {away_wins}승) - 배당과 반대!",
                importance="high"
            ))
        elif abs(home_wins - away_wins) <= 1 and total >= 5:
            # 상대전적 균형
            signals.append(UpsetSignal(
                category="h2h",
                signal_name="h2h_even",
                score=5,
                description=f"상대전적 균형 ({home_wins}승 vs {away_wins}승)",
                importance="low"
            ))

        return signals

    def _analyze_situation_signals(
        self,
        home_stats: Optional[Dict],
        away_stats: Optional[Dict],
        home_injuries: Optional[Dict],
        away_injuries: Optional[Dict],
        home_team: str,
        away_team: str,
        favorite: str,
    ) -> List[UpsetSignal]:
        """상황 기반 이변 신호"""
        signals = []

        # 부상자 분석
        if home_injuries:
            injury_count = len(home_injuries.get("players", []))
            key_injured = home_injuries.get("key_players_injured", [])

            if key_injured:
                signals.append(UpsetSignal(
                    category="situation",
                    signal_name="key_injury",
                    score=8,
                    description=f"🔴 {home_team} 주전 부상: {', '.join(key_injured[:2])}",
                    importance="high"
                ))
            elif injury_count >= 3:
                signals.append(UpsetSignal(
                    category="situation",
                    signal_name="multiple_injuries",
                    score=5,
                    description=f"{home_team} {injury_count}명 부상",
                    importance="medium"
                ))

        if away_injuries:
            injury_count = len(away_injuries.get("players", []))
            key_injured = away_injuries.get("key_players_injured", [])

            if key_injured:
                signals.append(UpsetSignal(
                    category="situation",
                    signal_name="key_injury",
                    score=8,
                    description=f"🔴 {away_team} 주전 부상: {', '.join(key_injured[:2])}",
                    importance="high"
                ))
            elif injury_count >= 3:
                signals.append(UpsetSignal(
                    category="situation",
                    signal_name="multiple_injuries",
                    score=5,
                    description=f"{away_team} {injury_count}명 부상",
                    importance="medium"
                ))

        # 리그 순위 기반 상황
        if home_stats and away_stats:
            home_pos = home_stats.get("league_position", 10)
            away_pos = away_stats.get("league_position", 10)

            # 강등권 팀 (하위 3팀)
            if home_pos >= 18 or away_pos >= 18:
                relegation_team = home_team if home_pos >= 18 else away_team
                signals.append(UpsetSignal(
                    category="situation",
                    signal_name="relegation_battle",
                    score=7,
                    description=f"⚡ {relegation_team} 강등권 생존 경기!",
                    importance="high"
                ))

            # 순위 역전 가능성 (하위팀이 배당 우세)
            if favorite == "home" and home_pos > away_pos + 5:
                signals.append(UpsetSignal(
                    category="situation",
                    signal_name="position_vs_odds",
                    score=6,
                    description=f"순위 vs 배당 불일치 ({home_team} {home_pos}위 vs {away_team} {away_pos}위)",
                    importance="medium"
                ))
            elif favorite == "away" and away_pos > home_pos + 5:
                signals.append(UpsetSignal(
                    category="situation",
                    signal_name="position_vs_odds",
                    score=6,
                    description=f"순위 vs 배당 불일치 ({home_team} {home_pos}위 vs {away_team} {away_pos}위)",
                    importance="medium"
                ))

        return signals

    def _determine_multi_selections(
        self,
        ai_probs: Optional[Dict],
        odds: Optional[Dict],
        sport_type: str,
        upset_risk: str,
    ) -> List[str]:
        """복수 베팅 선택지 결정"""
        if not ai_probs:
            return ["1", "X"] if sport_type == "soccer" else ["승", "5"]

        # 확률 정렬
        if sport_type == "soccer":
            prob_map = {"1": ai_probs.get("home", 0), "X": ai_probs.get("draw", 0), "2": ai_probs.get("away", 0)}
        else:
            prob_map = {"승": ai_probs.get("home", 0), "5": ai_probs.get("draw", 0), "패": ai_probs.get("away", 0)}

        sorted_options = sorted(prob_map.items(), key=lambda x: x[1], reverse=True)

        # 상위 2개 선택
        return [sorted_options[0][0], sorted_options[1][0]]

    def _generate_summary(
        self,
        home_team: str,
        away_team: str,
        upset_score: float,
        upset_risk: str,
        signals: List[UpsetSignal],
    ) -> str:
        """이변 분석 요약 생성"""
        if upset_risk == "high":
            risk_emoji = "🚨"
            risk_text = "높음"
        elif upset_risk == "medium":
            risk_emoji = "⚠️"
            risk_text = "중간"
        else:
            risk_emoji = "✅"
            risk_text = "낮음"

        high_importance = [s for s in signals if s.importance == "high"]

        lines = [
            f"{risk_emoji} 이변 위험도: {risk_text} ({upset_score:.0f}점)",
            f"감지된 신호: {len(signals)}개",
        ]

        if high_importance:
            lines.append("핵심 신호:")
            for s in high_importance[:3]:
                lines.append(f"  • {s.description}")

        return "\n".join(lines)

    def analyze_all_matches(
        self,
        matches: List[Dict],
        sport_type: str = "soccer",
    ) -> List[UpsetAnalysis]:
        """14경기 전체 이변 분석

        Args:
            matches: 경기 정보 리스트
            sport_type: "soccer" or "basketball"

        Returns:
            UpsetAnalysis 리스트 (이변 점수 내림차순 정렬)
        """
        analyses = []

        for match in matches:
            analysis = self.analyze_upset_potential(
                home_team=match.get("home_team", ""),
                away_team=match.get("away_team", ""),
                ai_probs=match.get("ai_probs"),
                ai_confidence=match.get("ai_confidence", 0.5),
                ai_agreement=match.get("ai_agreement", 0.5),
                home_stats=match.get("home_stats"),
                away_stats=match.get("away_stats"),
                home_form=match.get("home_form"),
                away_form=match.get("away_form"),
                h2h=match.get("h2h"),
                home_injuries=match.get("home_injuries"),
                away_injuries=match.get("away_injuries"),
                odds=match.get("odds"),
                sport_type=sport_type,
            )
            analyses.append(analysis)

        # 이변 점수 내림차순 정렬
        analyses.sort(key=lambda x: x.upset_score, reverse=True)

        return analyses

    def select_multi_bet_games(
        self,
        analyses: List[UpsetAnalysis],
        max_multi: int = 4,
    ) -> List[UpsetAnalysis]:
        """복수 베팅 경기 선정

        Args:
            analyses: analyze_all_matches() 결과
            max_multi: 최대 복수 베팅 경기 수 (기본: 4)

        Returns:
            복수 베팅 권장 경기 리스트 (최대 4개)
        """
        # 이미 정렬되어 있음 (이변 점수 내림차순)
        multi_games = []

        for analysis in analyses:
            if analysis.multi_bet_recommended:
                multi_games.append(analysis)
                if len(multi_games) >= max_multi:
                    break

        # 복수 게임이 4개 미만이면 점수 높은 순으로 추가
        if len(multi_games) < max_multi:
            for analysis in analyses:
                if analysis not in multi_games:
                    multi_games.append(analysis)
                    if len(multi_games) >= max_multi:
                        break

        return multi_games


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_enhanced_upset_detector: Optional[EnhancedUpsetDetector] = None


def get_enhanced_upset_detector() -> EnhancedUpsetDetector:
    """싱글톤 인스턴스 반환"""
    global _enhanced_upset_detector
    if _enhanced_upset_detector is None:
        _enhanced_upset_detector = EnhancedUpsetDetector()
    return _enhanced_upset_detector


# 짧은 별칭
get_upset_detector = get_enhanced_upset_detector


# =============================================================================
# 테스트
# =============================================================================

if __name__ == "__main__":
    # 테스트 실행
    detector = EnhancedUpsetDetector()

    # 테스트 케이스: 맨시티 vs 리버풀
    analysis = detector.analyze_upset_potential(
        home_team="맨시티",
        away_team="리버풀",
        ai_probs={"home": 0.42, "draw": 0.30, "away": 0.28},
        ai_confidence=0.52,
        ai_agreement=0.48,
        home_stats={"league_position": 1, "wins": 15, "losses": 2},
        away_stats={"league_position": 2, "wins": 14, "losses": 2},
        home_form={"winning_streak": 0, "losing_streak": 2},
        away_form={"winning_streak": 4, "losing_streak": 0},
        h2h={"home_wins": 2, "away_wins": 5, "draws": 3, "total_matches": 10},
        home_injuries={"players": [{"name": "De Bruyne"}, {"name": "Rodri"}], "key_players_injured": ["De Bruyne"]},
        away_injuries={"players": []},
        odds={"home": 1.85, "draw": 3.60, "away": 4.20},
        sport_type="soccer",
    )

    print("=" * 60)
    print("이변 분석 테스트 결과")
    print("=" * 60)
    print(f"경기: {analysis.home_team} vs {analysis.away_team}")
    print(f"이변 점수: {analysis.upset_score:.0f}점")
    print(f"이변 위험: {analysis.upset_risk}")
    print(f"복수 베팅 권장: {analysis.multi_bet_recommended}")
    print(f"복수 선택지: {analysis.multi_bet_selections}")
    print()
    print("이변 신호:")
    for s in analysis.signals:
        print(f"  [{s.importance}] {s.description} (+{s.score}점)")
    print()
    print("요약:")
    print(analysis.summary)
