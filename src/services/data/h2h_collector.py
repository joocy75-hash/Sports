"""
상대 전적(Head-to-Head) 수집 모듈

두 팀 간의 역대 상대 전적 데이터를 수집하고 분석합니다.
API-Football의 fixtures/headtohead 엔드포인트를 사용합니다.

사용 예시:
    from src.services.data.h2h_collector import H2HCollector, h2h_collector

    collector = H2HCollector()

    # 상대 전적 조회 (최근 10경기)
    h2h = await collector.get_head_to_head("맨시티", "리버풀", limit=10)
    if h2h:
        print(f"총 {h2h.total_matches}경기")
        print(f"맨시티 승: {h2h.home_team_wins}")
        print(f"무승부: {h2h.draws}")
        print(f"리버풀 승: {h2h.away_team_wins}")
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from dotenv import load_dotenv

from .cache_manager import CacheManager, CacheTTL, get_cache_manager
from .rate_limiter import RateLimiter, get_rate_limiter, rate_limited
from .team_mapping import TeamMapper, team_mapper

# 환경변수 로드
load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class H2HMatch:
    """개별 상대 전적 경기

    두 팀 간의 개별 과거 경기 정보를 담습니다.

    Attributes:
        date: 경기 날짜 (YYYY-MM-DD)
        competition: 대회명 (예: "Premier League", "FA Cup")
        home_team: 홈팀명
        away_team: 원정팀명
        score: 스코어 (예: '2-1')
        winner: 승자 ('home', 'away', 'draw')
    """
    date: str
    competition: str
    home_team: str
    away_team: str
    score: str  # '2-1'
    winner: str  # 'home', 'away', 'draw'

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "date": self.date,
            "competition": self.competition,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "score": self.score,
            "winner": self.winner
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "H2HMatch":
        """딕셔너리에서 생성"""
        return cls(
            date=data["date"],
            competition=data["competition"],
            home_team=data["home_team"],
            away_team=data["away_team"],
            score=data["score"],
            winner=data["winner"]
        )


@dataclass
class HeadToHead:
    """상대 전적 요약

    두 팀 간의 전체 상대 전적 통계를 담습니다.

    Attributes:
        home_team: 홈팀명 (조회 시 첫 번째 팀)
        away_team: 원정팀명 (조회 시 두 번째 팀)
        total_matches: 총 경기 수
        home_team_wins: 홈팀 승리 수
        draws: 무승부 수
        away_team_wins: 원정팀 승리 수
        home_team_goals: 홈팀 총 득점
        away_team_goals: 원정팀 총 득점
        recent_matches: 최근 경기 목록 (H2HMatch 리스트)
        home_venue_record: 홈팀이 홈에서 한 경기의 전적 {wins, draws, losses}
        away_venue_record: 원정팀이 홈에서 한 경기의 전적 {wins, draws, losses}
        updated_at: 데이터 갱신 시각
    """
    home_team: str
    away_team: str
    total_matches: int
    home_team_wins: int
    draws: int
    away_team_wins: int
    home_team_goals: int
    away_team_goals: int
    recent_matches: List[H2HMatch] = field(default_factory=list)
    home_venue_record: Dict[str, int] = field(default_factory=dict)  # 홈팀이 홈에서 한 경기 전적
    away_venue_record: Dict[str, int] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (캐시 저장용)"""
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "total_matches": self.total_matches,
            "home_team_wins": self.home_team_wins,
            "draws": self.draws,
            "away_team_wins": self.away_team_wins,
            "home_team_goals": self.home_team_goals,
            "away_team_goals": self.away_team_goals,
            "recent_matches": [m.to_dict() for m in self.recent_matches],
            "home_venue_record": self.home_venue_record,
            "away_venue_record": self.away_venue_record,
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HeadToHead":
        """딕셔너리에서 생성 (캐시 로드용)"""
        updated_at_str = data.get("updated_at")
        if updated_at_str:
            updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
        else:
            updated_at = datetime.now(timezone.utc)

        return cls(
            home_team=data["home_team"],
            away_team=data["away_team"],
            total_matches=data["total_matches"],
            home_team_wins=data["home_team_wins"],
            draws=data["draws"],
            away_team_wins=data["away_team_wins"],
            home_team_goals=data["home_team_goals"],
            away_team_goals=data["away_team_goals"],
            recent_matches=[H2HMatch.from_dict(m) for m in data.get("recent_matches", [])],
            home_venue_record=data.get("home_venue_record", {}),
            away_venue_record=data.get("away_venue_record", {}),
            updated_at=updated_at
        )

    @property
    def home_team_win_rate(self) -> float:
        """홈팀 승률"""
        if self.total_matches == 0:
            return 0.0
        return self.home_team_wins / self.total_matches

    @property
    def away_team_win_rate(self) -> float:
        """원정팀 승률"""
        if self.total_matches == 0:
            return 0.0
        return self.away_team_wins / self.total_matches

    @property
    def draw_rate(self) -> float:
        """무승부 비율"""
        if self.total_matches == 0:
            return 0.0
        return self.draws / self.total_matches

    @property
    def avg_goals_per_match(self) -> float:
        """경기당 평균 골"""
        if self.total_matches == 0:
            return 0.0
        return (self.home_team_goals + self.away_team_goals) / self.total_matches


# =============================================================================
# H2HCollector 클래스
# =============================================================================

class H2HCollector:
    """상대 전적(Head-to-Head) 수집기

    API-Football의 fixtures/headtohead 엔드포인트를 사용하여
    두 팀 간의 역대 상대 전적을 수집합니다.

    기능:
    - 팀명 자동 정규화 (TeamMapper 사용)
    - API 응답 캐싱 (24시간 TTL)
    - Rate Limiting 적용 (API 쿼터 관리)

    사용 예시:
        collector = H2HCollector()
        h2h = await collector.get_head_to_head("맨시티", "리버풀")

        if h2h:
            print(f"총 경기: {h2h.total_matches}")
            print(f"맨시티 승: {h2h.home_team_wins}, 무: {h2h.draws}, 리버풀 승: {h2h.away_team_wins}")
    """

    # API-Football 엔드포인트
    API_BASE_URL = "https://v3.football.api-sports.io"

    def __init__(
        self,
        api_key: Optional[str] = None,
        team_mapper: Optional[TeamMapper] = None,
        cache_manager: Optional[CacheManager] = None,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """초기화

        Args:
            api_key: API-Football API 키 (없으면 환경변수 사용)
            team_mapper: 팀명 매퍼 (없으면 기본 인스턴스 사용)
            cache_manager: 캐시 매니저 (없으면 기본 인스턴스 사용)
            rate_limiter: Rate Limiter (없으면 기본 인스턴스 사용)
        """
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY")
        self._team_mapper = team_mapper or team_mapper
        self._cache_manager = cache_manager or get_cache_manager()
        self._rate_limiter = rate_limiter or get_rate_limiter("api_football")

        # API 키 경고
        if not self.api_key:
            logger.warning(
                "API_FOOTBALL_KEY not configured. "
                "H2HCollector will return None for all requests."
            )

        logger.info("H2HCollector initialized")

    def _get_cache_key(self, team1_id: int, team2_id: int) -> str:
        """캐시 키 생성

        팀 ID를 정렬하여 일관된 캐시 키 생성 (A vs B == B vs A)

        Args:
            team1_id: 첫 번째 팀 ID
            team2_id: 두 번째 팀 ID

        Returns:
            캐시 키 문자열
        """
        # ID를 정렬하여 A vs B와 B vs A가 같은 키를 사용하도록 함
        sorted_ids = sorted([team1_id, team2_id])
        return f"h2h:{sorted_ids[0]}:{sorted_ids[1]}"

    async def _fetch_h2h_data(
        self,
        team1_id: int,
        team2_id: int,
        limit: int = 10
    ) -> Optional[Dict[str, Any]]:
        """API에서 상대 전적 데이터 조회

        Args:
            team1_id: 첫 번째 팀 API ID
            team2_id: 두 번째 팀 API ID
            limit: 최근 경기 수 제한

        Returns:
            API 응답 데이터 또는 None (실패 시)
        """
        if not self.api_key:
            return None

        # Rate Limiting
        await self._rate_limiter.acquire()

        url = f"{self.API_BASE_URL}/fixtures/headtohead"
        headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": self.api_key
        }
        params = {
            "h2h": f"{team1_id}-{team2_id}",
            "last": str(limit)
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"API-Football H2H request failed: {response.status}")
                        return None

                    data = await response.json()

                    # API 에러 체크
                    if data.get("errors"):
                        logger.error(f"API-Football H2H errors: {data['errors']}")
                        return None

                    # 결과 수 체크
                    results = data.get("results", 0)
                    if results == 0:
                        logger.warning(f"No H2H data found for teams {team1_id} vs {team2_id}")
                        return None

                    logger.debug(f"H2H data fetched: {team1_id} vs {team2_id}, {results} matches")
                    return data

        except aiohttp.ClientError as e:
            logger.error(f"H2H API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching H2H data: {e}")
            return None

    def _calculate_h2h_stats(
        self,
        matches: List[Dict[str, Any]],
        team1_name: str,
        team2_name: str,
        team1_id: int,
        team2_id: int
    ) -> Tuple[Dict[str, Any], List[H2HMatch]]:
        """상대 전적 통계 계산

        Args:
            matches: API 응답의 경기 리스트
            team1_name: 첫 번째 팀명 (정규화된)
            team2_name: 두 번째 팀명 (정규화된)
            team1_id: 첫 번째 팀 API ID
            team2_id: 두 번째 팀 API ID

        Returns:
            (통계 딕셔너리, H2HMatch 리스트) 튜플
        """
        stats = {
            "total_matches": len(matches),
            "team1_wins": 0,
            "draws": 0,
            "team2_wins": 0,
            "team1_goals": 0,
            "team2_goals": 0,
            "team1_home_wins": 0,
            "team1_home_draws": 0,
            "team1_home_losses": 0,
            "team2_home_wins": 0,
            "team2_home_draws": 0,
            "team2_home_losses": 0
        }

        recent_matches: List[H2HMatch] = []

        for match in matches:
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            goals = match.get("goals", {})
            league = match.get("league", {})

            # 경기 정보 추출
            match_date = fixture.get("date", "")[:10]  # YYYY-MM-DD
            competition = league.get("name", "Unknown")

            home_team_data = teams.get("home", {})
            away_team_data = teams.get("away", {})

            home_team_id = home_team_data.get("id")
            home_team_name_api = home_team_data.get("name", "")
            away_team_name_api = away_team_data.get("name", "")

            home_goals = goals.get("home", 0) or 0
            away_goals = goals.get("away", 0) or 0

            score = f"{home_goals}-{away_goals}"

            # 승자 결정
            if home_goals > away_goals:
                winner = "home"
            elif away_goals > home_goals:
                winner = "away"
            else:
                winner = "draw"

            # 통계 업데이트 (team1 기준)
            if home_team_id == team1_id:
                # team1이 홈팀인 경우
                stats["team1_goals"] += home_goals
                stats["team2_goals"] += away_goals

                if winner == "home":
                    stats["team1_wins"] += 1
                    stats["team1_home_wins"] += 1
                elif winner == "away":
                    stats["team2_wins"] += 1
                    stats["team1_home_losses"] += 1
                else:
                    stats["draws"] += 1
                    stats["team1_home_draws"] += 1

            else:
                # team1이 원정팀인 경우 (team2가 홈팀)
                stats["team1_goals"] += away_goals
                stats["team2_goals"] += home_goals

                if winner == "away":
                    stats["team1_wins"] += 1
                    stats["team2_home_losses"] += 1
                elif winner == "home":
                    stats["team2_wins"] += 1
                    stats["team2_home_wins"] += 1
                else:
                    stats["draws"] += 1
                    stats["team2_home_draws"] += 1

            # H2HMatch 객체 생성
            h2h_match = H2HMatch(
                date=match_date,
                competition=competition,
                home_team=home_team_name_api,
                away_team=away_team_name_api,
                score=score,
                winner=winner
            )
            recent_matches.append(h2h_match)

        # 날짜순 정렬 (최신순)
        recent_matches.sort(key=lambda x: x.date, reverse=True)

        return stats, recent_matches

    async def get_head_to_head(
        self,
        team1: str,
        team2: str,
        limit: int = 10,
        sport: str = "soccer",
        force_refresh: bool = False
    ) -> Optional[HeadToHead]:
        """두 팀 간의 상대 전적 조회

        Args:
            team1: 첫 번째 팀명 (한글 또는 영문)
            team2: 두 번째 팀명 (한글 또는 영문)
            limit: 최근 경기 수 제한 (기본값: 10)
            sport: 스포츠 종류 (기본값: "soccer")
            force_refresh: 캐시 무시하고 새로 조회 (기본값: False)

        Returns:
            HeadToHead 객체 또는 None (조회 실패 시)

        사용 예시:
            h2h = await collector.get_head_to_head("맨시티", "리버풀")
            if h2h:
                print(f"맨시티 승률: {h2h.home_team_win_rate:.1%}")
        """
        # API 키 체크
        if not self.api_key:
            logger.warning("API key not configured, returning None")
            return None

        # 팀명 정규화 및 API ID 조회
        team1_normalized = self._team_mapper.get_normalized_name(team1, sport=sport)
        team2_normalized = self._team_mapper.get_normalized_name(team2, sport=sport)

        if not team1_normalized:
            logger.warning(f"Could not normalize team name: {team1}")
            return None
        if not team2_normalized:
            logger.warning(f"Could not normalize team name: {team2}")
            return None

        # API ID 조회
        team1_id = self._team_mapper.get_api_id(team1_normalized, api="api_football", sport=sport)
        team2_id = self._team_mapper.get_api_id(team2_normalized, api="api_football", sport=sport)

        if not team1_id:
            logger.warning(f"Could not find API ID for team: {team1_normalized}")
            return None
        if not team2_id:
            logger.warning(f"Could not find API ID for team: {team2_normalized}")
            return None

        # 캐시 키 생성
        cache_key = self._get_cache_key(team1_id, team2_id)

        # 캐시 조회 (force_refresh가 아닌 경우)
        if not force_refresh:
            cached_data = await self._cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"H2H cache hit: {team1_normalized} vs {team2_normalized}")
                return HeadToHead.from_dict(cached_data)

        # API 조회
        logger.info(f"Fetching H2H data: {team1_normalized} vs {team2_normalized}")
        api_data = await self._fetch_h2h_data(team1_id, team2_id, limit)

        if not api_data:
            return None

        # 데이터 파싱
        matches = api_data.get("response", [])
        if not matches:
            logger.warning(f"No matches in H2H response for {team1_normalized} vs {team2_normalized}")
            return None

        # 통계 계산
        stats, recent_matches = self._calculate_h2h_stats(
            matches, team1_normalized, team2_normalized, team1_id, team2_id
        )

        # HeadToHead 객체 생성
        h2h = HeadToHead(
            home_team=team1_normalized,
            away_team=team2_normalized,
            total_matches=stats["total_matches"],
            home_team_wins=stats["team1_wins"],
            draws=stats["draws"],
            away_team_wins=stats["team2_wins"],
            home_team_goals=stats["team1_goals"],
            away_team_goals=stats["team2_goals"],
            recent_matches=recent_matches,
            home_venue_record={
                "wins": stats["team1_home_wins"],
                "draws": stats["team1_home_draws"],
                "losses": stats["team1_home_losses"]
            },
            away_venue_record={
                "wins": stats["team2_home_wins"],
                "draws": stats["team2_home_draws"],
                "losses": stats["team2_home_losses"]
            },
            updated_at=datetime.now(timezone.utc)
        )

        # 캐시 저장 (24시간 TTL)
        await self._cache_manager.set(
            cache_key,
            h2h.to_dict(),
            CacheTTL.HEAD_TO_HEAD
        )

        logger.info(
            f"H2H data collected: {team1_normalized} vs {team2_normalized}, "
            f"{h2h.total_matches} matches, "
            f"W:{h2h.home_team_wins}/D:{h2h.draws}/L:{h2h.away_team_wins}"
        )

        return h2h

    async def get_h2h_for_match(
        self,
        home_team: str,
        away_team: str,
        sport: str = "soccer"
    ) -> Optional[HeadToHead]:
        """특정 경기의 상대 전적 조회 (편의 메서드)

        get_head_to_head의 별칭으로, 경기 정보에서 바로 호출하기 편하도록 제공합니다.

        Args:
            home_team: 홈팀명
            away_team: 원정팀명
            sport: 스포츠 종류

        Returns:
            HeadToHead 객체 또는 None
        """
        return await self.get_head_to_head(home_team, away_team, sport=sport)

    async def invalidate_h2h_cache(self, team1: str, team2: str, sport: str = "soccer") -> bool:
        """특정 팀 조합의 캐시 무효화

        Args:
            team1: 첫 번째 팀명
            team2: 두 번째 팀명
            sport: 스포츠 종류

        Returns:
            성공 여부
        """
        # 팀 ID 조회
        team1_id = self._team_mapper.get_api_id(team1, api="api_football", sport=sport)
        team2_id = self._team_mapper.get_api_id(team2, api="api_football", sport=sport)

        if not team1_id or not team2_id:
            return False

        cache_key = self._get_cache_key(team1_id, team2_id)
        deleted = await self._cache_manager.invalidate(cache_key)

        return deleted > 0


# =============================================================================
# 전역 인스턴스
# =============================================================================

# 싱글톤 인스턴스
_h2h_collector_instance: Optional[H2HCollector] = None


def get_h2h_collector() -> H2HCollector:
    """H2HCollector 싱글톤 인스턴스 반환"""
    global _h2h_collector_instance

    if _h2h_collector_instance is None:
        _h2h_collector_instance = H2HCollector()

    return _h2h_collector_instance


# 편의를 위한 전역 인스턴스 (import 시 바로 사용 가능)
h2h_collector = H2HCollector()


# =============================================================================
# 테스트 함수
# =============================================================================

async def test_h2h_collector():
    """H2HCollector 테스트"""
    print("=" * 70)
    print("H2HCollector 테스트")
    print("=" * 70)

    collector = H2HCollector()

    # API 키 확인
    if not collector.api_key:
        print("\n[!] API_FOOTBALL_KEY가 설정되지 않았습니다.")
        print("    .env 파일에 API_FOOTBALL_KEY를 설정하세요.")
        print("=" * 70)
        return

    # 테스트 케이스
    test_cases = [
        ("맨시티", "리버풀"),
        ("아스널", "첼시"),
        ("레알마드리드", "바르셀로나"),
    ]

    for team1, team2 in test_cases:
        print(f"\n[테스트] {team1} vs {team2}")
        print("-" * 50)

        h2h = await collector.get_head_to_head(team1, team2, limit=10)

        if h2h:
            print(f"  총 경기: {h2h.total_matches}")
            print(f"  {team1} 승: {h2h.home_team_wins} ({h2h.home_team_win_rate:.1%})")
            print(f"  무승부: {h2h.draws} ({h2h.draw_rate:.1%})")
            print(f"  {team2} 승: {h2h.away_team_wins} ({h2h.away_team_win_rate:.1%})")
            print(f"  총 득점: {h2h.home_team_goals}:{h2h.away_team_goals}")
            print(f"  경기당 평균 골: {h2h.avg_goals_per_match:.2f}")

            if h2h.recent_matches:
                print("\n  최근 경기:")
                for match in h2h.recent_matches[:3]:
                    print(f"    {match.date}: {match.home_team} {match.score} {match.away_team} ({match.competition})")
        else:
            print("  데이터 조회 실패")

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_h2h_collector())
