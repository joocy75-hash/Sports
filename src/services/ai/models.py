"""
AI Analysis Common Data Models

모든 AI Analyzer가 공유하는 데이터 모델 정의
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from datetime import datetime
from enum import Enum


class SportType(str, Enum):
    """스포츠 타입"""
    SOCCER = "soccer"      # 축구 승무패 14경기
    BASKETBALL = "basketball"  # 농구 5승식 14경기


class WinnerType(str, Enum):
    """승리 예측 타입"""
    HOME = "Home"
    DRAW = "Draw"
    AWAY = "Away"


class ConfidenceLevel(str, Enum):
    """신뢰도 수준"""
    HIGH = "high"      # 80-100
    MEDIUM = "medium"  # 60-79
    LOW = "low"        # 40-59
    UNCERTAIN = "uncertain"  # 0-39


@dataclass
class MatchContext:
    """경기 분석을 위한 컨텍스트 정보"""
    match_id: int
    home_team: str
    away_team: str
    league: str
    start_time: str

    # 스포츠 타입 (축구/농구)
    sport_type: SportType = SportType.SOCCER

    # 선택적 통계 정보
    home_stats: Optional[Dict] = None
    away_stats: Optional[Dict] = None
    h2h_record: Optional[Dict] = None
    home_form: Optional[List[str]] = None  # ['W', 'W', 'D', 'L', 'W']
    away_form: Optional[List[str]] = None

    # 배당률 정보
    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None

    # 부가 정보 (Perplexity 등에서 수집)
    enriched_context: Optional[str] = None
    injuries: Optional[Dict] = None
    recent_news: Optional[str] = None

    def to_prompt_string(self) -> str:
        """프롬프트용 문자열 변환"""
        sport_label = "축구" if self.sport_type == SportType.SOCCER else "농구"
        lines = [
            f"[{sport_label}] 경기: {self.home_team} vs {self.away_team}",
            f"리그: {self.league}",
            f"시작 시간: {self.start_time}",
        ]

        # 축구: 승무패 배당률
        if self.sport_type == SportType.SOCCER:
            if self.odds_home and self.odds_draw and self.odds_away:
                lines.append(f"배당률: 홈승 {self.odds_home:.2f} / 무승부 {self.odds_draw:.2f} / 원정승 {self.odds_away:.2f}")
        # 농구: 승패 배당률 (무승부 없음)
        else:
            if self.odds_home and self.odds_away:
                lines.append(f"배당률: 홈승 {self.odds_home:.2f} / 원정승 {self.odds_away:.2f}")

        if self.home_form:
            lines.append(f"홈팀 최근 폼: {' '.join(self.home_form)}")
        if self.away_form:
            lines.append(f"원정팀 최근 폼: {' '.join(self.away_form)}")

        if self.home_stats:
            lines.append(f"홈팀 통계: {self.home_stats}")
        if self.away_stats:
            lines.append(f"원정팀 통계: {self.away_stats}")

        if self.h2h_record:
            lines.append(f"상대 전적: {self.h2h_record}")

        if self.enriched_context:
            lines.append(f"\n추가 정보:\n{self.enriched_context}")

        return "\n".join(lines)


@dataclass
class AIOpinion:
    """개별 AI의 분석 의견"""
    provider: str  # 'gpt', 'kimi'
    winner: WinnerType
    confidence: int  # 0-100
    reasoning: str
    key_factor: Optional[str] = None
    probabilities: Optional[Dict[str, float]] = None  # {'home': 0.55, 'draw': 0.25, 'away': 0.20}
    raw_response: Optional[Dict] = None  # 원본 응답 (디버깅용)
    latency_ms: Optional[int] = None  # 응답 시간


@dataclass
class ConsensusResult:
    """다중 AI 의견 종합 결과"""
    winner: WinnerType
    confidence: int  # 가중 평균 신뢰도
    confidence_level: ConfidenceLevel
    probabilities: Dict[str, float]  # 종합 확률
    agreement_rate: float  # AI 간 일치율 (0-1)
    recommendation: str  # 한글 추천 메시지


@dataclass
class AIAnalysisResult:
    """AI 분석 최종 결과"""
    match_id: int
    consensus: ConsensusResult
    ai_opinions: List[AIOpinion]

    # 메타데이터
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    cached: bool = False
    cache_key: Optional[str] = None
    total_latency_ms: Optional[int] = None

    def to_dict(self) -> Dict:
        """딕셔너리 변환 (API 응답용)"""
        return {
            "match_id": self.match_id,
            "consensus": {
                "winner": self.consensus.winner.value,
                "confidence": self.consensus.confidence,
                "confidence_level": self.consensus.confidence_level.value,
                "probabilities": self.consensus.probabilities,
                "agreement_rate": self.consensus.agreement_rate,
                "recommendation": self.consensus.recommendation,
            },
            "ai_opinions": [
                {
                    "provider": op.provider,
                    "winner": op.winner.value,
                    "confidence": op.confidence,
                    "reasoning": op.reasoning,
                    "key_factor": op.key_factor,
                    "probabilities": op.probabilities,
                    "latency_ms": op.latency_ms,
                }
                for op in self.ai_opinions
            ],
            "analyzed_at": self.analyzed_at,
            "cached": self.cached,
            "total_latency_ms": self.total_latency_ms,
        }
