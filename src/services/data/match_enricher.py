"""
경기 데이터 통합 서비스 모듈 (Phase 2.1)

모든 데이터 수집기를 통합하여 풍부한 경기 컨텍스트를 생성합니다.
병렬 수집으로 성능을 최적화하고, 부분 실패를 허용합니다.

통합 데이터 소스:
- 팀 통계 (TeamStatsCollector)
- 최근 폼 (FormCollector)
- 상대 전적 (H2HCollector)
- 부상자 정보 (InjuriesCollector) - 선택적
- 배당률 (OddsCollector) - 선택적

사용 예시:
    from src.services.data.match_enricher import match_enricher, get_match_enricher

    enricher = get_match_enricher()

    # 단일 경기 강화
    context = await enricher.enrich_match(
        home_team="맨시티",
        away_team="리버풀",
        league="Premier League",
        sport_type="soccer"
    )

    # AI 프롬프트용 문자열 생성
    prompt_context = context.to_prompt_string()

    # 14경기 일괄 처리
    matches = [
        {"home_team": "맨시티", "away_team": "리버풀", "league": "Premier League"},
        {"home_team": "아스널", "away_team": "첼시", "league": "Premier League"},
        # ...
    ]
    contexts = await enricher.enrich_multiple_matches(matches, sport_type="soccer")
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class EnrichedMatchContext:
    """풍부한 경기 컨텍스트 데이터

    모든 데이터 수집기로부터 수집된 데이터를 통합합니다.
    일부 데이터가 없어도 나머지 데이터로 분석 가능합니다.

    Attributes:
        match_id: 경기 고유 ID (선택)
        home_team: 홈팀명
        away_team: 원정팀명
        league: 리그명
        match_date: 경기 날짜 (YYYY-MM-DD, 선택)
        sport_type: 스포츠 종류 ("soccer" 또는 "basketball")

        home_stats: 홈팀 시즌 통계 (TeamStats.to_dict())
        away_stats: 원정팀 시즌 통계 (TeamStats.to_dict())
        home_form: 홈팀 최근 폼 (TeamForm.to_dict())
        away_form: 원정팀 최근 폼 (TeamForm.to_dict())
        h2h_record: 상대 전적 (HeadToHead.to_dict())
        home_injuries: 홈팀 부상자 정보 (선택)
        away_injuries: 원정팀 부상자 정보 (선택)
        odds: 배당률 정보 (선택)

        data_completeness: 데이터 완성도 (0.0 ~ 1.0)
        enrichment_errors: 수집 중 발생한 에러 목록
        updated_at: 데이터 갱신 시각
    """

    # 기본 정보
    match_id: Optional[str] = None
    home_team: str = ""
    away_team: str = ""
    league: str = ""
    match_date: Optional[str] = None
    sport_type: str = "soccer"

    # 수집된 데이터 (모두 Optional - 부분 실패 허용)
    home_stats: Optional[Dict[str, Any]] = None
    away_stats: Optional[Dict[str, Any]] = None
    home_form: Optional[Dict[str, Any]] = None
    away_form: Optional[Dict[str, Any]] = None
    h2h_record: Optional[Dict[str, Any]] = None
    home_injuries: Optional[Dict[str, Any]] = None
    away_injuries: Optional[Dict[str, Any]] = None
    odds: Optional[Dict[str, Any]] = None

    # 메타데이터
    data_completeness: float = 0.0
    enrichment_errors: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "match_id": self.match_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "league": self.league,
            "match_date": self.match_date,
            "sport_type": self.sport_type,
            "home_stats": self.home_stats,
            "away_stats": self.away_stats,
            "home_form": self.home_form,
            "away_form": self.away_form,
            "h2h_record": self.h2h_record,
            "home_injuries": self.home_injuries,
            "away_injuries": self.away_injuries,
            "odds": self.odds,
            "data_completeness": self.data_completeness,
            "enrichment_errors": self.enrichment_errors,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnrichedMatchContext":
        """딕셔너리에서 생성"""
        updated_at_str = data.get("updated_at")
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
            except ValueError:
                updated_at = datetime.now(timezone.utc)
        else:
            updated_at = datetime.now(timezone.utc)

        return cls(
            match_id=data.get("match_id"),
            home_team=data.get("home_team", ""),
            away_team=data.get("away_team", ""),
            league=data.get("league", ""),
            match_date=data.get("match_date"),
            sport_type=data.get("sport_type", "soccer"),
            home_stats=data.get("home_stats"),
            away_stats=data.get("away_stats"),
            home_form=data.get("home_form"),
            away_form=data.get("away_form"),
            h2h_record=data.get("h2h_record"),
            home_injuries=data.get("home_injuries"),
            away_injuries=data.get("away_injuries"),
            odds=data.get("odds"),
            data_completeness=data.get("data_completeness", 0.0),
            enrichment_errors=data.get("enrichment_errors", []),
            updated_at=updated_at,
        )

    def to_prompt_string(self) -> str:
        """AI 프롬프트용 문자열 생성

        수집된 모든 데이터를 AI 분석에 적합한 형식으로 포맷팅합니다.
        데이터가 없는 섹션은 자동으로 생략됩니다.

        Returns:
            AI 프롬프트에 삽입할 수 있는 형식화된 문자열
        """
        lines = []

        # 경기 기본 정보
        lines.append(f"===== {self.home_team} vs {self.away_team} =====")
        lines.append(f"리그: {self.league}")
        if self.match_date:
            lines.append(f"경기일: {self.match_date}")
        lines.append("")

        # 팀 시즌 통계
        if self.home_stats or self.away_stats:
            lines.append("【팀 시즌 통계】")
            lines.append(self._format_team_stats_section())
            lines.append("")

        # 최근 폼 (5경기)
        if self.home_form or self.away_form:
            lines.append("【최근 5경기 폼】")
            lines.append(self._format_form_section())
            lines.append("")

        # 상대 전적
        if self.h2h_record:
            lines.append("【상대 전적】")
            lines.append(self._format_h2h_section())
            lines.append("")

        # 부상자/출전정지
        if self.home_injuries or self.away_injuries:
            lines.append("【부상자/출전정지】")
            lines.append(self._format_injuries_section())
            lines.append("")

        # 배당률 분석
        if self.odds:
            lines.append("【배당률 분석】")
            lines.append(self._format_odds_section())
            lines.append("")

        # 데이터 품질 메모
        lines.append(f"[데이터 완성도: {self.data_completeness:.0%}]")

        return "\n".join(lines)

    def _format_team_stats_section(self) -> str:
        """팀 통계 섹션 포맷팅"""
        lines = []

        # 홈팀 통계
        if self.home_stats:
            hs = self.home_stats
            lines.append(f"  [{self.home_team}] (홈)")
            lines.append(f"    - 순위: {hs.get('league_position', 'N/A')}위 ({hs.get('points', 0)}점)")
            lines.append(f"    - 전적: {hs.get('wins', 0)}승 {hs.get('draws', 0)}무 {hs.get('losses', 0)}패")
            lines.append(f"    - 득/실점: {hs.get('goals_scored', 0)}:{hs.get('goals_conceded', 0)} "
                        f"(경기당 {hs.get('goals_scored_avg', 0):.1f}:{hs.get('goals_conceded_avg', 0):.1f})")
            lines.append(f"    - 홈 전적: {hs.get('home_wins', 0)}승 {hs.get('home_draws', 0)}무 {hs.get('home_losses', 0)}패")

            # xG가 있으면 추가
            if hs.get('xG') is not None:
                lines.append(f"    - xG/xGA: {hs.get('xG', 0):.1f}/{hs.get('xGA', 0):.1f}")

        # 원정팀 통계
        if self.away_stats:
            aways = self.away_stats
            lines.append(f"  [{self.away_team}] (원정)")
            lines.append(f"    - 순위: {aways.get('league_position', 'N/A')}위 ({aways.get('points', 0)}점)")
            lines.append(f"    - 전적: {aways.get('wins', 0)}승 {aways.get('draws', 0)}무 {aways.get('losses', 0)}패")
            lines.append(f"    - 득/실점: {aways.get('goals_scored', 0)}:{aways.get('goals_conceded', 0)} "
                        f"(경기당 {aways.get('goals_scored_avg', 0):.1f}:{aways.get('goals_conceded_avg', 0):.1f})")
            lines.append(f"    - 원정 전적: {aways.get('away_wins', 0)}승 {aways.get('away_draws', 0)}무 {aways.get('away_losses', 0)}패")

            if aways.get('xG') is not None:
                lines.append(f"    - xG/xGA: {aways.get('xG', 0):.1f}/{aways.get('xGA', 0):.1f}")

        return "\n".join(lines) if lines else "  데이터 없음"

    def _format_form_section(self) -> str:
        """폼 섹션 포맷팅"""
        lines = []

        # 홈팀 폼
        if self.home_form:
            hf = self.home_form
            results = hf.get('recent_results', [])
            form_str = "".join(results) if results else "N/A"
            form_points = hf.get('form_points', 0)
            goal_diff = hf.get('form_goal_diff', 0)

            lines.append(f"  [{self.home_team}]")
            lines.append(f"    - 폼: {form_str} ({form_points}점)")
            lines.append(f"    - 득실: +{goal_diff}" if goal_diff >= 0 else f"    - 득실: {goal_diff}")

            # 연승/연패 정보
            streaks = []
            if hf.get('winning_streak', 0) > 0:
                streaks.append(f"{hf['winning_streak']}연승")
            if hf.get('losing_streak', 0) > 0:
                streaks.append(f"{hf['losing_streak']}연패")
            if hf.get('unbeaten_streak', 0) >= 3:
                streaks.append(f"{hf['unbeaten_streak']}경기 무패")
            if streaks:
                lines.append(f"    - 현재: {', '.join(streaks)}")

            # 최근 경기 결과
            recent_matches = hf.get('recent_matches', [])
            if recent_matches:
                lines.append("    - 최근 경기:")
                for match in recent_matches[:3]:
                    ha = "H" if match.get('home_away') == 'H' else "A"
                    result = match.get('result', '?')
                    score = match.get('score', '?-?')
                    opponent = match.get('opponent', 'Unknown')[:10]  # 팀명 길이 제한
                    lines.append(f"      [{result}] {score} vs {opponent} ({ha})")

        # 원정팀 폼
        if self.away_form:
            af = self.away_form
            results = af.get('recent_results', [])
            form_str = "".join(results) if results else "N/A"
            form_points = af.get('form_points', 0)
            goal_diff = af.get('form_goal_diff', 0)

            lines.append(f"  [{self.away_team}]")
            lines.append(f"    - 폼: {form_str} ({form_points}점)")
            lines.append(f"    - 득실: +{goal_diff}" if goal_diff >= 0 else f"    - 득실: {goal_diff}")

            streaks = []
            if af.get('winning_streak', 0) > 0:
                streaks.append(f"{af['winning_streak']}연승")
            if af.get('losing_streak', 0) > 0:
                streaks.append(f"{af['losing_streak']}연패")
            if af.get('unbeaten_streak', 0) >= 3:
                streaks.append(f"{af['unbeaten_streak']}경기 무패")
            if streaks:
                lines.append(f"    - 현재: {', '.join(streaks)}")

            recent_matches = af.get('recent_matches', [])
            if recent_matches:
                lines.append("    - 최근 경기:")
                for match in recent_matches[:3]:
                    ha = "H" if match.get('home_away') == 'H' else "A"
                    result = match.get('result', '?')
                    score = match.get('score', '?-?')
                    opponent = match.get('opponent', 'Unknown')[:10]
                    lines.append(f"      [{result}] {score} vs {opponent} ({ha})")

        return "\n".join(lines) if lines else "  데이터 없음"

    def _format_h2h_section(self) -> str:
        """상대 전적 섹션 포맷팅"""
        if not self.h2h_record:
            return "  데이터 없음"

        h2h = self.h2h_record
        lines = []

        total = h2h.get('total_matches', 0)
        home_wins = h2h.get('home_team_wins', 0)
        draws = h2h.get('draws', 0)
        away_wins = h2h.get('away_team_wins', 0)

        lines.append(f"  총 {total}경기 대결")
        lines.append(f"  - {self.home_team}: {home_wins}승 ({home_wins/total*100:.0f}%)" if total > 0 else f"  - {self.home_team}: {home_wins}승")
        lines.append(f"  - 무승부: {draws}")
        lines.append(f"  - {self.away_team}: {away_wins}승 ({away_wins/total*100:.0f}%)" if total > 0 else f"  - {self.away_team}: {away_wins}승")

        # 총 득점
        home_goals = h2h.get('home_team_goals', 0)
        away_goals = h2h.get('away_team_goals', 0)
        lines.append(f"  - 총 득점: {home_goals}:{away_goals}")

        # 최근 대결 결과
        recent_matches = h2h.get('recent_matches', [])
        if recent_matches:
            lines.append("  - 최근 대결:")
            for match in recent_matches[:5]:
                date = match.get('date', '')[:10]
                home = match.get('home_team', 'Home')[:8]
                away = match.get('away_team', 'Away')[:8]
                score = match.get('score', '?-?')
                comp = match.get('competition', '')[:12]
                lines.append(f"    {date}: {home} {score} {away} ({comp})")

        return "\n".join(lines)

    def _format_injuries_section(self) -> str:
        """부상자 섹션 포맷팅"""
        lines = []

        if self.home_injuries:
            hi = self.home_injuries
            lines.append(f"  [{self.home_team}]")

            injuries = hi.get('injuries', [])
            if injuries:
                for injury in injuries[:5]:  # 최대 5명
                    player = injury.get('player_name', 'Unknown')
                    reason = injury.get('reason', 'Unknown')
                    expected_return = injury.get('expected_return', '')
                    lines.append(f"    - {player}: {reason}" + (f" (복귀 예정: {expected_return})" if expected_return else ""))
            else:
                lines.append("    - 주요 부상자 없음")

        if self.away_injuries:
            ai = self.away_injuries
            lines.append(f"  [{self.away_team}]")

            injuries = ai.get('injuries', [])
            if injuries:
                for injury in injuries[:5]:
                    player = injury.get('player_name', 'Unknown')
                    reason = injury.get('reason', 'Unknown')
                    expected_return = injury.get('expected_return', '')
                    lines.append(f"    - {player}: {reason}" + (f" (복귀 예정: {expected_return})" if expected_return else ""))
            else:
                lines.append("    - 주요 부상자 없음")

        return "\n".join(lines) if lines else "  데이터 없음"

    def _format_odds_section(self) -> str:
        """배당률 섹션 포맷팅"""
        if not self.odds:
            return "  데이터 없음"

        odds = self.odds
        lines = []

        # 1X2 배당률 (축구)
        if self.sport_type == "soccer":
            home_odds = odds.get('home_odds', 0)
            draw_odds = odds.get('draw_odds', 0)
            away_odds = odds.get('away_odds', 0)

            if home_odds and draw_odds and away_odds:
                lines.append(f"  1X2 배당률: {home_odds:.2f} / {draw_odds:.2f} / {away_odds:.2f}")

                # 내재 확률 계산
                total_prob = (1/home_odds + 1/draw_odds + 1/away_odds) if home_odds and draw_odds and away_odds else 0
                if total_prob > 0:
                    home_prob = (1/home_odds) / total_prob * 100
                    draw_prob = (1/draw_odds) / total_prob * 100
                    away_prob = (1/away_odds) / total_prob * 100
                    lines.append(f"  내재 확률: 홈승 {home_prob:.1f}% / 무 {draw_prob:.1f}% / 원정승 {away_prob:.1f}%")

                    # 마진 계산
                    margin = (1/home_odds + 1/draw_odds + 1/away_odds - 1) * 100
                    lines.append(f"  북메이커 마진: {margin:.1f}%")

        # 승/패 배당률 (농구)
        elif self.sport_type == "basketball":
            home_odds = odds.get('home_odds', 0)
            away_odds = odds.get('away_odds', 0)

            if home_odds and away_odds:
                lines.append(f"  승/패 배당률: {home_odds:.2f} / {away_odds:.2f}")

                total_prob = (1/home_odds + 1/away_odds) if home_odds and away_odds else 0
                if total_prob > 0:
                    home_prob = (1/home_odds) / total_prob * 100
                    away_prob = (1/away_odds) / total_prob * 100
                    lines.append(f"  내재 확률: 홈승 {home_prob:.1f}% / 원정승 {away_prob:.1f}%")

            # 핸디캡 배당률
            handicap = odds.get('handicap')
            handicap_home = odds.get('handicap_home_odds')
            handicap_away = odds.get('handicap_away_odds')
            if handicap is not None and handicap_home and handicap_away:
                lines.append(f"  핸디캡 ({handicap:+}): {handicap_home:.2f} / {handicap_away:.2f}")

        # 배당률 출처
        source = odds.get('source', 'Unknown')
        lines.append(f"  [출처: {source}]")

        return "\n".join(lines)

    def get_data_quality_report(self) -> str:
        """데이터 품질 리포트 생성

        수집된 데이터의 품질과 누락 항목을 분석합니다.

        Returns:
            품질 리포트 문자열
        """
        lines = []
        lines.append(f"===== 데이터 품질 리포트 =====")
        lines.append(f"경기: {self.home_team} vs {self.away_team}")
        lines.append(f"완성도: {self.data_completeness:.0%}")
        lines.append("")

        # 수집 상태 체크
        data_sources = [
            ("홈팀 통계", self.home_stats),
            ("원정팀 통계", self.away_stats),
            ("홈팀 폼", self.home_form),
            ("원정팀 폼", self.away_form),
            ("상대 전적", self.h2h_record),
            ("홈팀 부상자", self.home_injuries),
            ("원정팀 부상자", self.away_injuries),
            ("배당률", self.odds),
        ]

        lines.append("수집 상태:")
        for name, data in data_sources:
            status = "O" if data else "X"
            lines.append(f"  [{status}] {name}")

        # 에러 목록
        if self.enrichment_errors:
            lines.append("")
            lines.append("에러 목록:")
            for error in self.enrichment_errors:
                lines.append(f"  - {error}")

        return "\n".join(lines)

    def has_minimum_data(self) -> bool:
        """최소 분석 가능 데이터가 있는지 확인

        최소한 팀 통계 또는 폼 데이터가 있어야 분석 가능합니다.

        Returns:
            True if 최소 데이터 충족, False otherwise
        """
        has_stats = self.home_stats is not None or self.away_stats is not None
        has_form = self.home_form is not None or self.away_form is not None

        return has_stats or has_form


# =============================================================================
# MatchEnricher 클래스
# =============================================================================

class MatchEnricher:
    """경기 데이터 통합 서비스

    모든 데이터 수집기를 통합하여 풍부한 MatchContext를 생성합니다.
    병렬 수집으로 성능을 최적화하고, 부분 실패를 허용합니다.

    통합 데이터 소스:
    - TeamStatsCollector: 팀 시즌 통계
    - FormCollector: 최근 5경기 폼
    - H2HCollector: 상대 전적
    - InjuriesCollector: 부상자 정보 (선택)
    - OddsCollector: 배당률 (선택)

    사용 예시:
        enricher = MatchEnricher()

        # 단일 경기 강화
        context = await enricher.enrich_match(
            home_team="맨시티",
            away_team="리버풀",
            league="Premier League"
        )

        print(context.to_prompt_string())
    """

    def __init__(self):
        """MatchEnricher 초기화

        모든 데이터 수집기를 로드합니다.
        일부 수집기가 없어도 나머지로 동작합니다.
        """
        # 필수 수집기 로드
        self.stats_collector = None
        self.form_collector = None
        self.h2h_collector = None

        # 선택적 수집기 (없을 수 있음)
        self.injuries_collector = None
        self.odds_collector = None

        # 수집기 로드 시도
        self._load_collectors()

        logger.info(
            f"MatchEnricher 초기화: "
            f"stats={'O' if self.stats_collector else 'X'}, "
            f"form={'O' if self.form_collector else 'X'}, "
            f"h2h={'O' if self.h2h_collector else 'X'}, "
            f"injuries={'O' if self.injuries_collector else 'X'}, "
            f"odds={'O' if self.odds_collector else 'X'}"
        )

    def _load_collectors(self) -> None:
        """데이터 수집기 로드

        ImportError가 발생해도 무시하고 계속 진행합니다.
        """
        # TeamStatsCollector
        try:
            from .team_stats_collector import team_stats_collector
            self.stats_collector = team_stats_collector
        except ImportError as e:
            logger.warning(f"TeamStatsCollector 로드 실패: {e}")

        # FormCollector
        try:
            from .form_collector import get_form_collector
            self.form_collector = get_form_collector()
        except ImportError as e:
            logger.warning(f"FormCollector 로드 실패: {e}")

        # H2HCollector
        try:
            from .h2h_collector import get_h2h_collector
            self.h2h_collector = get_h2h_collector()
        except ImportError as e:
            logger.warning(f"H2HCollector 로드 실패: {e}")

        # InjuriesCollector (선택적)
        try:
            from .injuries_collector import get_injuries_collector
            self.injuries_collector = get_injuries_collector()
        except ImportError:
            logger.debug("InjuriesCollector 미구현 - 건너뜀")

        # OddsCollector (선택적)
        try:
            from .odds_collector import get_odds_collector
            self.odds_collector = get_odds_collector()
        except ImportError:
            logger.debug("OddsCollector 미구현 - 건너뜀")

    async def enrich_match(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_date: Optional[str] = None,
        sport_type: str = "soccer",
        match_id: Optional[str] = None,
        include_injuries: bool = True,
        include_odds: bool = True
    ) -> EnrichedMatchContext:
        """경기 정보를 풍부한 컨텍스트로 확장

        병렬로 모든 데이터를 수집하고 통합합니다.
        일부 데이터 수집이 실패해도 나머지는 반환합니다.

        Args:
            home_team: 홈팀명
            away_team: 원정팀명
            league: 리그명
            match_date: 경기 날짜 (YYYY-MM-DD, 선택)
            sport_type: 스포츠 종류 ("soccer" 또는 "basketball")
            match_id: 경기 고유 ID (선택)
            include_injuries: 부상자 정보 포함 여부
            include_odds: 배당률 정보 포함 여부

        Returns:
            EnrichedMatchContext 객체 (수집된 데이터 포함)
        """
        errors: List[str] = []

        # 병렬 데이터 수집 태스크 생성
        tasks = [
            # 팀 통계 (홈, 원정)
            self._get_team_stats_safe(home_team, league, sport_type),
            self._get_team_stats_safe(away_team, league, sport_type),
            # 폼 데이터 (홈, 원정)
            self._get_form_safe(home_team, league),
            self._get_form_safe(away_team, league),
            # 상대 전적
            self._get_h2h_safe(home_team, away_team, sport_type),
            # 부상자 정보 (선택적)
            self._get_injuries_if_enabled(home_team, league, include_injuries),
            self._get_injuries_if_enabled(away_team, league, include_injuries),
            # 배당률 (선택적)
            self._get_odds_if_enabled(home_team, away_team, league, match_date, include_odds),
        ]

        # 병렬 수집 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 파싱
        home_stats = self._extract_result(results[0], "홈팀 통계", errors)
        away_stats = self._extract_result(results[1], "원정팀 통계", errors)
        home_form = self._extract_result(results[2], "홈팀 폼", errors)
        away_form = self._extract_result(results[3], "원정팀 폼", errors)
        h2h_record = self._extract_result(results[4], "상대 전적", errors)
        home_injuries = self._extract_result(results[5], "홈팀 부상자", errors) if include_injuries else None
        away_injuries = self._extract_result(results[6], "원정팀 부상자", errors) if include_injuries else None
        odds = self._extract_result(results[7], "배당률", errors) if include_odds else None

        # 데이터 완성도 계산
        data_completeness = self._calculate_completeness(
            home_stats=home_stats,
            away_stats=away_stats,
            home_form=home_form,
            away_form=away_form,
            h2h_record=h2h_record,
            home_injuries=home_injuries if include_injuries else "skip",
            away_injuries=away_injuries if include_injuries else "skip",
            odds=odds if include_odds else "skip",
        )

        # EnrichedMatchContext 생성
        context = EnrichedMatchContext(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            league=league,
            match_date=match_date,
            sport_type=sport_type,
            home_stats=home_stats,
            away_stats=away_stats,
            home_form=home_form,
            away_form=away_form,
            h2h_record=h2h_record,
            home_injuries=home_injuries,
            away_injuries=away_injuries,
            odds=odds,
            data_completeness=data_completeness,
            enrichment_errors=errors,
            updated_at=datetime.now(timezone.utc),
        )

        logger.info(
            f"경기 데이터 강화 완료: {home_team} vs {away_team}, "
            f"완성도={data_completeness:.0%}, 에러={len(errors)}개"
        )

        return context

    async def enrich_multiple_matches(
        self,
        matches: List[Dict[str, Any]],
        sport_type: str = "soccer",
        include_injuries: bool = True,
        include_odds: bool = True
    ) -> List[Union[EnrichedMatchContext, Exception]]:
        """14경기 일괄 처리

        여러 경기를 병렬로 처리하여 성능을 최적화합니다.

        Args:
            matches: 경기 정보 리스트
                [{"home_team": ..., "away_team": ..., "league": ..., "match_date": ...}, ...]
            sport_type: 스포츠 종류
            include_injuries: 부상자 정보 포함 여부
            include_odds: 배당률 정보 포함 여부

        Returns:
            EnrichedMatchContext 리스트 (또는 예외)
        """
        tasks = []

        for match in matches:
            task = self.enrich_match(
                home_team=match.get("home_team", ""),
                away_team=match.get("away_team", ""),
                league=match.get("league", "Unknown"),
                match_date=match.get("match_date"),
                sport_type=sport_type,
                match_id=match.get("match_id"),
                include_injuries=include_injuries,
                include_odds=include_odds,
            )
            tasks.append(task)

        # 모든 경기 병렬 처리
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 로깅
        success_count = sum(1 for r in results if isinstance(r, EnrichedMatchContext))
        error_count = len(results) - success_count

        logger.info(
            f"일괄 경기 데이터 강화 완료: "
            f"총 {len(matches)}경기, 성공={success_count}, 실패={error_count}"
        )

        return results

    # =========================================================================
    # 안전한 데이터 수집 메서드 (예외를 잡아서 None 반환)
    # =========================================================================

    async def _get_team_stats_safe(
        self,
        team_name: str,
        league: str,
        sport: str
    ) -> Optional[Dict[str, Any]]:
        """팀 통계를 안전하게 수집"""
        if not self.stats_collector:
            return None

        try:
            stats = await self.stats_collector.get_team_stats(team_name, league, sport)
            return stats.to_dict() if stats else None
        except Exception as e:
            logger.warning(f"팀 통계 수집 실패 ({team_name}): {e}")
            return None

    async def _get_form_safe(
        self,
        team_name: str,
        league: str
    ) -> Optional[Dict[str, Any]]:
        """폼 데이터를 안전하게 수집"""
        if not self.form_collector:
            return None

        try:
            form = await self.form_collector.get_team_form(team_name, league)
            return form.to_dict() if form else None
        except Exception as e:
            logger.warning(f"폼 데이터 수집 실패 ({team_name}): {e}")
            return None

    async def _get_h2h_safe(
        self,
        home_team: str,
        away_team: str,
        sport: str
    ) -> Optional[Dict[str, Any]]:
        """상대 전적을 안전하게 수집"""
        if not self.h2h_collector:
            return None

        try:
            h2h = await self.h2h_collector.get_head_to_head(home_team, away_team, sport=sport)
            return h2h.to_dict() if h2h else None
        except Exception as e:
            logger.warning(f"상대 전적 수집 실패 ({home_team} vs {away_team}): {e}")
            return None

    async def _get_injuries_if_enabled(
        self,
        team_name: str,
        league: str,
        enabled: bool
    ) -> Optional[Dict[str, Any]]:
        """부상자 정보를 조건부로 수집"""
        if not enabled or not self.injuries_collector:
            return None

        try:
            injuries = await self.injuries_collector.get_team_injuries(team_name, league)
            return injuries.to_dict() if injuries else None
        except Exception as e:
            logger.warning(f"부상자 정보 수집 실패 ({team_name}): {e}")
            return None

    async def _get_odds_if_enabled(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_date: Optional[str],
        enabled: bool
    ) -> Optional[Dict[str, Any]]:
        """배당률을 조건부로 수집"""
        if not enabled or not self.odds_collector:
            return None

        try:
            odds = await self.odds_collector.get_match_odds(home_team, away_team, league, match_date)
            return odds.to_dict() if odds else None
        except Exception as e:
            logger.warning(f"배당률 수집 실패 ({home_team} vs {away_team}): {e}")
            return None

    # =========================================================================
    # 유틸리티 메서드
    # =========================================================================

    def _extract_result(
        self,
        result: Any,
        name: str,
        errors: List[str]
    ) -> Optional[Dict[str, Any]]:
        """수집 결과에서 데이터 추출

        예외가 발생한 경우 에러 목록에 추가하고 None 반환

        Args:
            result: asyncio.gather 결과
            name: 데이터 소스 이름 (에러 메시지용)
            errors: 에러 목록 (mutable)

        Returns:
            추출된 딕셔너리 또는 None
        """
        if isinstance(result, Exception):
            errors.append(f"{name}: {str(result)[:50]}")
            return None

        if result is None:
            # 데이터가 없는 것은 에러가 아님 (API 키 미설정 등)
            return None

        return result

    def _calculate_completeness(self, **data_sources: Any) -> float:
        """데이터 완성도 계산

        각 데이터 소스의 존재 여부를 확인하여 완성도를 계산합니다.
        "skip"으로 표시된 항목은 계산에서 제외됩니다.

        Args:
            **data_sources: 데이터 소스별 데이터 (None = 없음, "skip" = 제외)

        Returns:
            0.0 ~ 1.0 사이의 완성도
        """
        total = 0
        available = 0

        for name, data in data_sources.items():
            if data == "skip":
                continue

            total += 1
            if data is not None:
                available += 1

        return available / total if total > 0 else 0.0

    def build_prompt_context(self, enriched: EnrichedMatchContext) -> str:
        """AI 프롬프트용 컨텍스트 문자열 생성

        EnrichedMatchContext.to_prompt_string()의 래퍼입니다.

        Args:
            enriched: 강화된 경기 컨텍스트

        Returns:
            AI 프롬프트에 삽입할 수 있는 형식화된 문자열
        """
        return enriched.to_prompt_string()

    async def close(self) -> None:
        """리소스 정리

        form_collector 등의 세션을 닫습니다.
        """
        if self.form_collector and hasattr(self.form_collector, 'close'):
            try:
                await self.form_collector.close()
            except Exception as e:
                logger.warning(f"FormCollector 종료 실패: {e}")


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_match_enricher_instance: Optional[MatchEnricher] = None


def get_match_enricher() -> MatchEnricher:
    """MatchEnricher 싱글톤 인스턴스 반환"""
    global _match_enricher_instance

    if _match_enricher_instance is None:
        _match_enricher_instance = MatchEnricher()

    return _match_enricher_instance


# 편의를 위한 전역 변수 (lazy 초기화)
match_enricher: Optional[MatchEnricher] = None


def _init_match_enricher() -> MatchEnricher:
    """지연 초기화된 match_enricher 반환"""
    global match_enricher
    if match_enricher is None:
        match_enricher = get_match_enricher()
    return match_enricher


# =============================================================================
# 테스트 함수
# =============================================================================

async def test_match_enricher():
    """MatchEnricher 테스트"""
    print("=" * 70)
    print("MatchEnricher 테스트")
    print("=" * 70)

    enricher = MatchEnricher()

    # 수집기 상태 확인
    print("\n[1] 수집기 상태")
    print("-" * 50)
    print(f"  stats_collector: {'O' if enricher.stats_collector else 'X'}")
    print(f"  form_collector: {'O' if enricher.form_collector else 'X'}")
    print(f"  h2h_collector: {'O' if enricher.h2h_collector else 'X'}")
    print(f"  injuries_collector: {'O' if enricher.injuries_collector else 'X'}")
    print(f"  odds_collector: {'O' if enricher.odds_collector else 'X'}")

    # 단일 경기 테스트
    print("\n[2] 단일 경기 강화 테스트")
    print("-" * 50)

    context = await enricher.enrich_match(
        home_team="맨시티",
        away_team="리버풀",
        league="Premier League",
        match_date="2026-01-15",
        sport_type="soccer"
    )

    print(f"  홈팀: {context.home_team}")
    print(f"  원정팀: {context.away_team}")
    print(f"  리그: {context.league}")
    print(f"  완성도: {context.data_completeness:.0%}")
    print(f"  에러 수: {len(context.enrichment_errors)}")

    if context.enrichment_errors:
        print("  에러 목록:")
        for error in context.enrichment_errors[:3]:
            print(f"    - {error}")

    # 데이터 품질 리포트
    print("\n[3] 데이터 품질 리포트")
    print("-" * 50)
    print(context.get_data_quality_report())

    # 프롬프트 문자열 미리보기 (일부만)
    print("\n[4] AI 프롬프트 문자열 (처음 500자)")
    print("-" * 50)
    prompt_str = context.to_prompt_string()
    print(prompt_str[:500])
    if len(prompt_str) > 500:
        print(f"... (총 {len(prompt_str)}자)")

    # 일괄 처리 테스트
    print("\n[5] 일괄 처리 테스트 (3경기)")
    print("-" * 50)

    matches = [
        {"home_team": "아스널", "away_team": "첼시", "league": "Premier League"},
        {"home_team": "바르셀로나", "away_team": "레알마드리드", "league": "La Liga"},
        {"home_team": "바이에른뮌헨", "away_team": "도르트문트", "league": "Bundesliga"},
    ]

    results = await enricher.enrich_multiple_matches(matches, sport_type="soccer")

    for i, result in enumerate(results):
        if isinstance(result, EnrichedMatchContext):
            print(f"  {i+1}. {result.home_team} vs {result.away_team}: 완성도 {result.data_completeness:.0%}")
        else:
            print(f"  {i+1}. 에러: {result}")

    # 리소스 정리
    await enricher.close()

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)


if __name__ == "__main__":
    # dotenv 로드
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    asyncio.run(test_match_enricher())
