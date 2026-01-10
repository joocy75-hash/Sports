"""
AI Analysis Common Data Models

모든 AI Analyzer가 공유하는 데이터 모델 정의

v4.0.0 업데이트 (2026-01-10):
- MatchContext 확장: 실시간 데이터 통합 지원
- EnrichedMatchContext와의 통합 메서드 추가
- 더 풍부한 to_prompt_string() 출력
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum

# 순환 임포트 방지
if TYPE_CHECKING:
    from src.services.data.match_enricher import EnrichedMatchContext


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
    """경기 분석을 위한 컨텍스트 정보

    v4.0.0 업데이트:
    - 실시간 데이터 통합 지원 (EnrichedMatchContext)
    - 부상자/출전정지 정보 상세화
    - 배당률 변동 분석 추가
    - 데이터 품질 메타데이터 추가
    """
    match_id: int
    home_team: str
    away_team: str
    league: str
    start_time: str

    # 스포츠 타입 (축구/농구)
    sport_type: SportType = SportType.SOCCER

    # 선택적 통계 정보 (시즌 전체)
    home_stats: Optional[Dict] = None
    away_stats: Optional[Dict] = None
    h2h_record: Optional[Dict] = None
    home_form: Optional[List[str]] = None  # ['W', 'W', 'D', 'L', 'W']
    away_form: Optional[List[str]] = None

    # 배당률 정보
    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None

    # v4.0.0: 확장된 데이터 필드
    home_form_detail: Optional[Dict] = None  # TeamForm.to_dict()
    away_form_detail: Optional[Dict] = None
    home_injuries: Optional[Dict] = None  # TeamInjuries.to_dict()
    away_injuries: Optional[Dict] = None
    odds_detail: Optional[Dict] = None  # MatchOdds.to_dict() - 변동 포함

    # 데이터 품질 메타데이터
    data_completeness: float = 0.0  # 0.0 ~ 1.0
    data_sources: Optional[List[str]] = None  # ['api_football', 'football_data', ...]
    enrichment_errors: Optional[List[str]] = None

    # 부가 정보 (Perplexity 등에서 수집)
    enriched_context: Optional[str] = None
    injuries: Optional[Dict] = None  # 레거시 호환용
    recent_news: Optional[str] = None

    def to_prompt_string(self) -> str:
        """프롬프트용 문자열 변환 (AI 분석용)

        v4.0.0: 더 풍부하고 구조화된 출력
        """
        sport_label = "축구" if self.sport_type == SportType.SOCCER else "농구"
        sections = []

        # 기본 정보
        header = [
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"[{sport_label}] {self.home_team} vs {self.away_team}",
            f"리그: {self.league} | 시간: {self.start_time}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        sections.append("\n".join(header))

        # 배당률 섹션
        odds_section = self._format_odds_section()
        if odds_section:
            sections.append(odds_section)

        # 시즌 통계 섹션
        stats_section = self._format_stats_section()
        if stats_section:
            sections.append(stats_section)

        # 최근 폼 섹션
        form_section = self._format_form_section()
        if form_section:
            sections.append(form_section)

        # 상대 전적 섹션
        h2h_section = self._format_h2h_section()
        if h2h_section:
            sections.append(h2h_section)

        # 부상자 섹션
        injuries_section = self._format_injuries_section()
        if injuries_section:
            sections.append(injuries_section)

        # 추가 컨텍스트
        if self.enriched_context:
            sections.append(f"【추가 정보】\n{self.enriched_context}")

        # 데이터 품질 표시
        if self.data_completeness > 0:
            quality = "높음" if self.data_completeness >= 0.8 else "보통" if self.data_completeness >= 0.5 else "낮음"
            sections.append(f"[데이터 품질: {quality} ({self.data_completeness:.0%})]")

        return "\n\n".join(sections)

    def _format_odds_section(self) -> Optional[str]:
        """배당률 섹션 포맷팅"""
        lines = ["【배당률 분석】"]

        if self.sport_type == SportType.SOCCER:
            if self.odds_home and self.odds_draw and self.odds_away:
                # 기본 배당률
                lines.append(f"  홈승: {self.odds_home:.2f} | 무승부: {self.odds_draw:.2f} | 원정승: {self.odds_away:.2f}")

                # 내재 확률 계산
                total = (1/self.odds_home) + (1/self.odds_draw) + (1/self.odds_away)
                home_prob = (1/self.odds_home) / total * 100
                draw_prob = (1/self.odds_draw) / total * 100
                away_prob = (1/self.odds_away) / total * 100
                margin = (total - 1) * 100

                lines.append(f"  내재확률: 홈 {home_prob:.1f}% | 무 {draw_prob:.1f}% | 원정 {away_prob:.1f}%")
                lines.append(f"  북메이커 마진: {margin:.1f}%")

                # 배당률 변동 (상세 정보가 있는 경우)
                if self.odds_detail and self.odds_detail.get("movements"):
                    movements = self.odds_detail["movements"]
                    if movements:
                        latest = movements[-1] if isinstance(movements, list) else None
                        if latest and latest.get("direction"):
                            lines.append(f"  배당 추세: {latest.get('direction', 'N/A')}")
            else:
                return None
        else:  # 농구
            if self.odds_home and self.odds_away:
                lines.append(f"  홈승: {self.odds_home:.2f} | 원정승: {self.odds_away:.2f}")
                total = (1/self.odds_home) + (1/self.odds_away)
                home_prob = (1/self.odds_home) / total * 100
                away_prob = (1/self.odds_away) / total * 100
                lines.append(f"  내재확률: 홈 {home_prob:.1f}% | 원정 {away_prob:.1f}%")
            else:
                return None

        return "\n".join(lines)

    def _format_stats_section(self) -> Optional[str]:
        """시즌 통계 섹션 포맷팅"""
        if not self.home_stats and not self.away_stats:
            return None

        lines = ["【시즌 통계】"]

        if self.home_stats:
            hs = self.home_stats
            lines.append(f"  {self.home_team}:")
            lines.append(f"    순위: {hs.get('league_position', 'N/A')}위 | 승점: {hs.get('points', 'N/A')}")
            lines.append(f"    전적: {hs.get('wins', 0)}승 {hs.get('draws', 0)}무 {hs.get('losses', 0)}패")
            lines.append(f"    득/실점: {hs.get('goals_scored', 0)}/{hs.get('goals_conceded', 0)} (득실차: {hs.get('goals_scored', 0) - hs.get('goals_conceded', 0):+d})")
            if hs.get('home_wins') is not None:
                lines.append(f"    홈 성적: {hs.get('home_wins', 0)}승 {hs.get('home_draws', 0)}무 {hs.get('home_losses', 0)}패")

        if self.away_stats:
            aws = self.away_stats
            lines.append(f"  {self.away_team}:")
            lines.append(f"    순위: {aws.get('league_position', 'N/A')}위 | 승점: {aws.get('points', 'N/A')}")
            lines.append(f"    전적: {aws.get('wins', 0)}승 {aws.get('draws', 0)}무 {aws.get('losses', 0)}패")
            lines.append(f"    득/실점: {aws.get('goals_scored', 0)}/{aws.get('goals_conceded', 0)} (득실차: {aws.get('goals_scored', 0) - aws.get('goals_conceded', 0):+d})")
            if aws.get('away_wins') is not None:
                lines.append(f"    원정 성적: {aws.get('away_wins', 0)}승 {aws.get('away_draws', 0)}무 {aws.get('away_losses', 0)}패")

        return "\n".join(lines)

    def _format_form_section(self) -> Optional[str]:
        """최근 폼 섹션 포맷팅"""
        if not self.home_form and not self.away_form and not self.home_form_detail and not self.away_form_detail:
            return None

        lines = ["【최근 5경기 폼】"]

        # 홈팀 폼
        if self.home_form_detail:
            hf = self.home_form_detail
            form_str = hf.get('recent_results', self.home_form or [])
            if isinstance(form_str, list):
                form_str = ''.join(form_str)
            lines.append(f"  {self.home_team}: {form_str}")
            lines.append(f"    폼 승점: {hf.get('form_points', 'N/A')} | 득실: {hf.get('form_goal_diff', 'N/A'):+d}")
            if hf.get('winning_streak', 0) > 0:
                lines.append(f"    🔥 {hf.get('winning_streak')}연승 중")
            elif hf.get('unbeaten_streak', 0) >= 3:
                lines.append(f"    ✅ {hf.get('unbeaten_streak')}경기 무패")
            elif hf.get('losing_streak', 0) > 0:
                lines.append(f"    ⚠️ {hf.get('losing_streak')}연패 중")
        elif self.home_form:
            lines.append(f"  {self.home_team}: {''.join(self.home_form)}")

        # 원정팀 폼
        if self.away_form_detail:
            af = self.away_form_detail
            form_str = af.get('recent_results', self.away_form or [])
            if isinstance(form_str, list):
                form_str = ''.join(form_str)
            lines.append(f"  {self.away_team}: {form_str}")
            lines.append(f"    폼 승점: {af.get('form_points', 'N/A')} | 득실: {af.get('form_goal_diff', 'N/A'):+d}")
            if af.get('winning_streak', 0) > 0:
                lines.append(f"    🔥 {af.get('winning_streak')}연승 중")
            elif af.get('unbeaten_streak', 0) >= 3:
                lines.append(f"    ✅ {af.get('unbeaten_streak')}경기 무패")
            elif af.get('losing_streak', 0) > 0:
                lines.append(f"    ⚠️ {af.get('losing_streak')}연패 중")
        elif self.away_form:
            lines.append(f"  {self.away_team}: {''.join(self.away_form)}")

        return "\n".join(lines)

    def _format_h2h_section(self) -> Optional[str]:
        """상대 전적 섹션 포맷팅"""
        if not self.h2h_record:
            return None

        h2h = self.h2h_record
        lines = ["【상대 전적】"]

        # 전체 전적
        total = h2h.get('total_matches', 0)
        if total > 0:
            lines.append(f"  최근 {total}경기: {self.home_team} {h2h.get('home_wins', 0)}승 {h2h.get('draws', 0)}무 {h2h.get('away_wins', 0)}패")

        # 최근 경기 상세
        recent = h2h.get('recent_matches', [])
        if recent:
            lines.append("  최근 경기:")
            for match in recent[:3]:  # 최근 3경기만
                date = match.get('date', 'N/A')
                score = match.get('score', 'N/A')
                lines.append(f"    {date}: {score}")

        return "\n".join(lines)

    def _format_injuries_section(self) -> Optional[str]:
        """부상자 섹션 포맷팅"""
        # v4.0.0 새 형식 우선
        if not self.home_injuries and not self.away_injuries and not self.injuries:
            return None

        lines = ["【부상자/출전정지】"]

        # 새 형식 (home_injuries, away_injuries)
        if self.home_injuries:
            hi = self.home_injuries
            players = hi.get('players', [])
            if players:
                lines.append(f"  {self.home_team}: {len(players)}명")
                for p in players[:3]:  # 최대 3명
                    status = "🔴 부상" if p.get('type') == 'injury' else "🟡 출전정지"
                    lines.append(f"    {status} {p.get('name', 'Unknown')} ({p.get('reason', 'N/A')})")
            else:
                lines.append(f"  {self.home_team}: 부상자 없음")

        if self.away_injuries:
            ai = self.away_injuries
            players = ai.get('players', [])
            if players:
                lines.append(f"  {self.away_team}: {len(players)}명")
                for p in players[:3]:
                    status = "🔴 부상" if p.get('type') == 'injury' else "🟡 출전정지"
                    lines.append(f"    {status} {p.get('name', 'Unknown')} ({p.get('reason', 'N/A')})")
            else:
                lines.append(f"  {self.away_team}: 부상자 없음")

        # 레거시 형식 (injuries)
        elif self.injuries:
            lines.append(f"  {self.injuries}")

        return "\n".join(lines)

    @classmethod
    def from_enriched(cls, enriched: "EnrichedMatchContext", match_id: int = 0) -> "MatchContext":
        """EnrichedMatchContext에서 MatchContext 생성

        Args:
            enriched: EnrichedMatchContext 객체
            match_id: 경기 번호 (기본값: 0)

        Returns:
            MatchContext 객체
        """
        # 폼 결과 추출
        home_form = None
        away_form = None
        if enriched.home_form:
            home_form = enriched.home_form.get('recent_results', [])
        if enriched.away_form:
            away_form = enriched.away_form.get('recent_results', [])

        # 배당률 추출
        odds_home = odds_draw = odds_away = None
        if enriched.odds:
            odds_home = enriched.odds.get('home_odds')
            odds_draw = enriched.odds.get('draw_odds')
            odds_away = enriched.odds.get('away_odds')

        # 스포츠 타입 변환
        sport = SportType.SOCCER if enriched.sport_type == "soccer" else SportType.BASKETBALL

        return cls(
            match_id=match_id,
            home_team=enriched.home_team,
            away_team=enriched.away_team,
            league=enriched.league,
            start_time=enriched.match_date or "",
            sport_type=sport,
            home_stats=enriched.home_stats,
            away_stats=enriched.away_stats,
            h2h_record=enriched.h2h_record,
            home_form=home_form,
            away_form=away_form,
            odds_home=odds_home,
            odds_draw=odds_draw,
            odds_away=odds_away,
            home_form_detail=enriched.home_form,
            away_form_detail=enriched.away_form,
            home_injuries=enriched.home_injuries,
            away_injuries=enriched.away_injuries,
            odds_detail=enriched.odds,
            data_completeness=enriched.data_completeness,
            enrichment_errors=enriched.enrichment_errors,
        )

    def to_dict(self) -> Dict:
        """딕셔너리 변환 (직렬화용)"""
        return {
            "match_id": self.match_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "league": self.league,
            "start_time": self.start_time,
            "sport_type": self.sport_type.value,
            "home_stats": self.home_stats,
            "away_stats": self.away_stats,
            "h2h_record": self.h2h_record,
            "home_form": self.home_form,
            "away_form": self.away_form,
            "odds_home": self.odds_home,
            "odds_draw": self.odds_draw,
            "odds_away": self.odds_away,
            "home_form_detail": self.home_form_detail,
            "away_form_detail": self.away_form_detail,
            "home_injuries": self.home_injuries,
            "away_injuries": self.away_injuries,
            "odds_detail": self.odds_detail,
            "data_completeness": self.data_completeness,
            "enrichment_errors": self.enrichment_errors,
        }


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
