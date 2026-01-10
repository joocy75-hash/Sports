"""
팀 통계 수집 모듈 (Phase 1.1)

외부 API에서 팀 시즌 통계를 수집합니다.
- Football-Data.org API (1순위)
- API-Football (2순위 백업)

캐시 TTL: 6시간 (CacheTTL.TEAM_STATS)

사용 예시:
    from src.services.data.team_stats_collector import team_stats_collector

    # 팀 통계 조회 (축구)
    stats = await team_stats_collector.get_team_stats("맨시티", "Premier League", "soccer")

    # 팀 통계 조회 (농구)
    stats = await team_stats_collector.get_team_stats("LA레이커스", "NBA", "basketball")
"""

import asyncio
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp

from .cache_manager import CacheManager, CacheTTL, get_cache_manager
from .rate_limiter import rate_limited, get_rate_limiter
from .team_mapping import TeamMapper, team_mapper

logger = logging.getLogger(__name__)


# =============================================================================
# TeamStats 데이터클래스
# =============================================================================

@dataclass
class TeamStats:
    """팀 시즌 통계 데이터

    Attributes:
        team_id: 팀 고유 ID (API별로 다를 수 있음)
        team_name: 팀명 (정규화된 한글명)
        league: 리그명
        season: 시즌 (예: "2025-2026")
        matches_played: 경기 수
        wins: 승리 수
        draws: 무승부 수 (축구용)
        losses: 패배 수
        goals_scored: 득점 (축구) / 총 득점 (농구)
        goals_conceded: 실점 (축구) / 총 실점 (농구)
        goals_scored_avg: 경기당 평균 득점
        goals_conceded_avg: 경기당 평균 실점
        home_wins: 홈 승리 수
        home_draws: 홈 무승부 수
        home_losses: 홈 패배 수
        away_wins: 원정 승리 수
        away_draws: 원정 무승부 수
        away_losses: 원정 패배 수
        league_position: 리그 순위
        points: 승점 (축구용)
        xG: Expected Goals (축구 고급 통계, 선택)
        xGA: Expected Goals Against (축구 고급 통계, 선택)
        updated_at: 데이터 갱신 시간
    """

    team_id: str
    team_name: str
    league: str
    season: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
    goals_scored_avg: float
    goals_conceded_avg: float
    home_wins: int
    home_draws: int
    home_losses: int
    away_wins: int
    away_draws: int
    away_losses: int
    league_position: int
    points: int
    xG: Optional[float] = None
    xGA: Optional[float] = None
    updated_at: datetime = None

    def __post_init__(self):
        """초기화 후 처리"""
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        data = asdict(self)
        # datetime을 ISO 문자열로 변환
        if isinstance(data.get("updated_at"), datetime):
            data["updated_at"] = data["updated_at"].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamStats":
        """딕셔너리에서 생성"""
        # ISO 문자열을 datetime으로 변환
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(
                data["updated_at"].replace('Z', '+00:00')
            )
        return cls(**data)

    @property
    def win_rate(self) -> float:
        """승률 계산"""
        if self.matches_played == 0:
            return 0.0
        return self.wins / self.matches_played

    @property
    def goal_difference(self) -> int:
        """골득실차"""
        return self.goals_scored - self.goals_conceded

    @property
    def home_form(self) -> Dict[str, int]:
        """홈 폼 요약"""
        return {
            "wins": self.home_wins,
            "draws": self.home_draws,
            "losses": self.home_losses,
            "total": self.home_wins + self.home_draws + self.home_losses
        }

    @property
    def away_form(self) -> Dict[str, int]:
        """원정 폼 요약"""
        return {
            "wins": self.away_wins,
            "draws": self.away_draws,
            "losses": self.away_losses,
            "total": self.away_wins + self.away_draws + self.away_losses
        }


# =============================================================================
# TeamStatsCollector 클래스
# =============================================================================

class TeamStatsCollector:
    """팀 통계 수집기

    외부 API에서 팀 통계를 수집하고 캐싱합니다.
    - 1순위: Football-Data.org API
    - 2순위: API-Football (백업)

    사용 예시:
        collector = TeamStatsCollector()
        stats = await collector.get_team_stats("맨시티", "Premier League", "soccer")
    """

    # Football-Data.org API 설정
    FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"

    # API-Football 설정
    API_FOOTBALL_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"

    # 리그 ID 매핑 (Football-Data.org)
    FOOTBALL_DATA_LEAGUE_IDS = {
        "Premier League": "PL",
        "Serie A": "SA",
        "Bundesliga": "BL1",
        "La Liga": "PD",
        "Ligue 1": "FL1",
        "Championship": "ELC",
        "Eredivisie": "DED",
        "Primeira Liga": "PPL",
    }

    # 리그 ID 매핑 (API-Football)
    API_FOOTBALL_LEAGUE_IDS = {
        "Premier League": 39,
        "Serie A": 135,
        "Bundesliga": 78,
        "La Liga": 140,
        "Ligue 1": 61,
        "Championship": 40,
        "Eredivisie": 88,
        "Primeira Liga": 94,
        "NBA": 12,  # API-Basketball에서 사용
    }

    def __init__(
        self,
        mapper: Optional[TeamMapper] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        """초기화

        Args:
            mapper: 팀명 매퍼 (기본값: 전역 인스턴스)
            cache_manager: 캐시 매니저 (기본값: 전역 인스턴스)
        """
        # team_mapping.py에서 전역 인스턴스 임포트
        from .team_mapping import team_mapper as default_mapper
        self.team_mapper = mapper or default_mapper
        self.cache_manager = cache_manager or get_cache_manager()

        # API 키 로드
        self._football_data_api_key = os.getenv("FOOTBALL_DATA_API_KEY")
        self._api_football_key = os.getenv("API_FOOTBALL_KEY")

        # 초기화 로그
        has_football_data = bool(self._football_data_api_key)
        has_api_football = bool(self._api_football_key)
        logger.info(
            f"TeamStatsCollector 초기화: "
            f"Football-Data={'O' if has_football_data else 'X'}, "
            f"API-Football={'O' if has_api_football else 'X'}"
        )

    def _get_cache_key(self, team_name: str, league: str, sport: str) -> str:
        """캐시 키 생성"""
        # 정규화된 팀명 사용
        normalized = self.team_mapper.get_normalized_name(team_name, sport) or team_name
        return f"team_stats:{sport}:{league}:{normalized}"

    def _get_current_season(self) -> str:
        """현재 시즌 문자열 반환 (예: '2025-2026')"""
        now = datetime.now()
        # 축구 시즌은 보통 8월에 시작
        if now.month >= 8:
            return f"{now.year}-{now.year + 1}"
        else:
            return f"{now.year - 1}-{now.year}"

    async def get_team_stats(
        self,
        team_name: str,
        league: str,
        sport: str = "soccer",
        force_refresh: bool = False
    ) -> Optional[TeamStats]:
        """팀 통계 조회

        캐시에서 먼저 조회하고, 없으면 API에서 수집합니다.

        Args:
            team_name: 팀명 (한글 또는 영문)
            league: 리그명 (예: "Premier League", "NBA")
            sport: 스포츠 종류 ("soccer" or "basketball")
            force_refresh: 캐시 무시하고 강제 새로고침

        Returns:
            TeamStats 객체 또는 None (수집 실패 시)
        """
        cache_key = self._get_cache_key(team_name, league, sport)

        # 1. 캐시 조회 (force_refresh가 아닌 경우)
        if not force_refresh:
            cached_data = await self.cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"캐시 히트: {cache_key}")
                return TeamStats.from_dict(cached_data)

        # 2. API에서 수집
        stats = None

        if sport == "soccer":
            stats = await self._fetch_soccer_stats(team_name, league)
        elif sport == "basketball":
            stats = await self._fetch_basketball_stats(team_name, league)
        else:
            logger.error(f"지원하지 않는 스포츠: {sport}")
            return None

        # 3. 캐시 저장
        if stats:
            await self.cache_manager.set(
                cache_key,
                stats.to_dict(),
                CacheTTL.TEAM_STATS
            )
            logger.info(f"팀 통계 수집 완료: {team_name} ({league})")

        return stats

    async def _fetch_soccer_stats(
        self,
        team_name: str,
        league: str
    ) -> Optional[TeamStats]:
        """축구 팀 통계 수집

        1순위: Football-Data.org
        2순위: API-Football

        Args:
            team_name: 팀명
            league: 리그명

        Returns:
            TeamStats 객체 또는 None
        """
        # 팀 ID 조회
        football_data_id = self.team_mapper.get_api_id(
            team_name, api="football_data", sport="soccer"
        )
        api_football_id = self.team_mapper.get_api_id(
            team_name, api="api_football", sport="soccer"
        )

        # 1순위: Football-Data.org
        if self._football_data_api_key and football_data_id:
            try:
                stats = await self._fetch_from_football_data(football_data_id, league)
                if stats:
                    return stats
                logger.warning(f"Football-Data.org 수집 실패: {team_name}")
            except Exception as e:
                logger.error(f"Football-Data.org 오류: {e}")

        # 2순위: API-Football
        if self._api_football_key and api_football_id:
            try:
                stats = await self._fetch_from_api_football(api_football_id, league)
                if stats:
                    return stats
                logger.warning(f"API-Football 수집 실패: {team_name}")
            except Exception as e:
                logger.error(f"API-Football 오류: {e}")

        logger.error(f"모든 API 수집 실패: {team_name} ({league})")
        return None

    @rate_limited("football_data")
    async def _fetch_from_football_data(
        self,
        team_id: int,
        league: str
    ) -> Optional[TeamStats]:
        """Football-Data.org API에서 팀 통계 수집

        API 문서: https://docs.football-data.org/

        Args:
            team_id: Football-Data.org 팀 ID
            league: 리그명

        Returns:
            TeamStats 객체 또는 None
        """
        if not self._football_data_api_key:
            logger.warning("FOOTBALL_DATA_API_KEY가 설정되지 않음")
            return None

        league_code = self.FOOTBALL_DATA_LEAGUE_IDS.get(league)
        if not league_code:
            logger.warning(f"Football-Data.org에서 지원하지 않는 리그: {league}")
            return None

        headers = {
            "X-Auth-Token": self._football_data_api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                # 팀 정보 조회
                team_url = f"{self.FOOTBALL_DATA_BASE_URL}/teams/{team_id}"
                async with session.get(team_url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Football-Data.org 팀 조회 실패: {resp.status}")
                        return None
                    team_data = await resp.json()

                # 순위표에서 팀 통계 조회
                standings_url = f"{self.FOOTBALL_DATA_BASE_URL}/competitions/{league_code}/standings"
                async with session.get(standings_url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Football-Data.org 순위표 조회 실패: {resp.status}")
                        return None
                    standings_data = await resp.json()

            # 팀 통계 추출
            team_stats = self._parse_football_data_response(
                team_data, standings_data, team_id, league
            )
            return team_stats

        except aiohttp.ClientError as e:
            logger.error(f"Football-Data.org API 호출 오류: {e}")
            return None

    def _parse_football_data_response(
        self,
        team_data: Dict,
        standings_data: Dict,
        team_id: int,
        league: str
    ) -> Optional[TeamStats]:
        """Football-Data.org 응답 파싱

        Args:
            team_data: 팀 정보 응답
            standings_data: 순위표 응답
            team_id: 팀 ID
            league: 리그명

        Returns:
            TeamStats 객체 또는 None
        """
        try:
            # 순위표에서 팀 찾기
            team_standing = None
            for standing in standings_data.get("standings", []):
                if standing.get("type") != "TOTAL":
                    continue
                for entry in standing.get("table", []):
                    if entry.get("team", {}).get("id") == team_id:
                        team_standing = entry
                        break
                if team_standing:
                    break

            if not team_standing:
                logger.warning(f"순위표에서 팀을 찾을 수 없음: {team_id}")
                return None

            # 홈/원정 통계 추출
            home_stats = None
            away_stats = None
            for standing in standings_data.get("standings", []):
                if standing.get("type") == "HOME":
                    for entry in standing.get("table", []):
                        if entry.get("team", {}).get("id") == team_id:
                            home_stats = entry
                            break
                elif standing.get("type") == "AWAY":
                    for entry in standing.get("table", []):
                        if entry.get("team", {}).get("id") == team_id:
                            away_stats = entry
                            break

            # TeamStats 생성
            matches_played = team_standing.get("playedGames", 0)
            goals_scored = team_standing.get("goalsFor", 0)
            goals_conceded = team_standing.get("goalsAgainst", 0)

            # 정규화된 팀명 조회
            team_name = team_data.get("name", "")
            normalized_name = self.team_mapper.get_normalized_name(team_name, "soccer") or team_name

            return TeamStats(
                team_id=str(team_id),
                team_name=normalized_name,
                league=league,
                season=self._get_current_season(),
                matches_played=matches_played,
                wins=team_standing.get("won", 0),
                draws=team_standing.get("draw", 0),
                losses=team_standing.get("lost", 0),
                goals_scored=goals_scored,
                goals_conceded=goals_conceded,
                goals_scored_avg=round(goals_scored / matches_played, 2) if matches_played > 0 else 0.0,
                goals_conceded_avg=round(goals_conceded / matches_played, 2) if matches_played > 0 else 0.0,
                home_wins=home_stats.get("won", 0) if home_stats else 0,
                home_draws=home_stats.get("draw", 0) if home_stats else 0,
                home_losses=home_stats.get("lost", 0) if home_stats else 0,
                away_wins=away_stats.get("won", 0) if away_stats else 0,
                away_draws=away_stats.get("draw", 0) if away_stats else 0,
                away_losses=away_stats.get("lost", 0) if away_stats else 0,
                league_position=team_standing.get("position", 0),
                points=team_standing.get("points", 0),
                xG=None,  # Football-Data.org에서는 xG 미제공
                xGA=None,
            )

        except (KeyError, TypeError) as e:
            logger.error(f"Football-Data.org 응답 파싱 오류: {e}")
            return None

    @rate_limited("api_football")
    async def _fetch_from_api_football(
        self,
        team_id: int,
        league: str
    ) -> Optional[TeamStats]:
        """API-Football에서 팀 통계 수집

        API 문서: https://www.api-football.com/documentation-v3

        Args:
            team_id: API-Football 팀 ID
            league: 리그명

        Returns:
            TeamStats 객체 또는 None
        """
        if not self._api_football_key:
            logger.warning("API_FOOTBALL_KEY가 설정되지 않음")
            return None

        league_id = self.API_FOOTBALL_LEAGUE_IDS.get(league)
        if not league_id:
            logger.warning(f"API-Football에서 지원하지 않는 리그: {league}")
            return None

        # 현재 시즌 연도 계산
        now = datetime.now()
        season_year = now.year if now.month >= 8 else now.year - 1

        headers = {
            "X-RapidAPI-Key": self._api_football_key,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }

        try:
            async with aiohttp.ClientSession() as session:
                # 팀 통계 조회
                stats_url = f"{self.API_FOOTBALL_BASE_URL}/teams/statistics"
                params = {
                    "team": team_id,
                    "league": league_id,
                    "season": season_year
                }

                async with session.get(stats_url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"API-Football 통계 조회 실패: {resp.status}")
                        return None
                    data = await resp.json()

                # 순위 조회
                standings_url = f"{self.API_FOOTBALL_BASE_URL}/standings"
                standings_params = {
                    "league": league_id,
                    "season": season_year
                }

                async with session.get(standings_url, headers=headers, params=standings_params) as resp:
                    if resp.status != 200:
                        logger.error(f"API-Football 순위 조회 실패: {resp.status}")
                        standings_data = None
                    else:
                        standings_data = await resp.json()

            # 응답 파싱
            return self._parse_api_football_response(data, standings_data, team_id, league)

        except aiohttp.ClientError as e:
            logger.error(f"API-Football API 호출 오류: {e}")
            return None

    def _parse_api_football_response(
        self,
        stats_data: Dict,
        standings_data: Optional[Dict],
        team_id: int,
        league: str
    ) -> Optional[TeamStats]:
        """API-Football 응답 파싱

        Args:
            stats_data: 팀 통계 응답
            standings_data: 순위표 응답
            team_id: 팀 ID
            league: 리그명

        Returns:
            TeamStats 객체 또는 None
        """
        try:
            response = stats_data.get("response", {})
            if not response:
                logger.warning("API-Football: 빈 응답")
                return None

            team_info = response.get("team", {})
            fixtures = response.get("fixtures", {})
            goals = response.get("goals", {})

            # 기본 경기 통계
            played_home = fixtures.get("played", {}).get("home", 0) or 0
            played_away = fixtures.get("played", {}).get("away", 0) or 0
            matches_played = played_home + played_away

            wins_home = fixtures.get("wins", {}).get("home", 0) or 0
            wins_away = fixtures.get("wins", {}).get("away", 0) or 0

            draws_home = fixtures.get("draws", {}).get("home", 0) or 0
            draws_away = fixtures.get("draws", {}).get("away", 0) or 0

            loses_home = fixtures.get("loses", {}).get("home", 0) or 0
            loses_away = fixtures.get("loses", {}).get("away", 0) or 0

            # 득실점
            goals_for = goals.get("for", {})
            goals_against = goals.get("against", {})

            goals_scored = goals_for.get("total", {}).get("total", 0) or 0
            goals_conceded = goals_against.get("total", {}).get("total", 0) or 0

            goals_scored_avg = float(goals_for.get("average", {}).get("total", 0) or 0)
            goals_conceded_avg = float(goals_against.get("average", {}).get("total", 0) or 0)

            # 순위 추출
            league_position = 0
            points = 0
            if standings_data:
                standings = standings_data.get("response", [])
                if standings:
                    league_standings = standings[0].get("league", {}).get("standings", [[]])
                    if league_standings:
                        for entry in league_standings[0]:
                            if entry.get("team", {}).get("id") == team_id:
                                league_position = entry.get("rank", 0)
                                points = entry.get("points", 0)
                                break

            # 정규화된 팀명
            team_name = team_info.get("name", "")
            normalized_name = self.team_mapper.get_normalized_name(team_name, "soccer") or team_name

            return TeamStats(
                team_id=str(team_id),
                team_name=normalized_name,
                league=league,
                season=self._get_current_season(),
                matches_played=matches_played,
                wins=wins_home + wins_away,
                draws=draws_home + draws_away,
                losses=loses_home + loses_away,
                goals_scored=goals_scored,
                goals_conceded=goals_conceded,
                goals_scored_avg=goals_scored_avg,
                goals_conceded_avg=goals_conceded_avg,
                home_wins=wins_home,
                home_draws=draws_home,
                home_losses=loses_home,
                away_wins=wins_away,
                away_draws=draws_away,
                away_losses=loses_away,
                league_position=league_position,
                points=points,
                xG=None,  # xG는 별도 API 필요
                xGA=None,
            )

        except (KeyError, TypeError) as e:
            logger.error(f"API-Football 응답 파싱 오류: {e}")
            return None

    async def _fetch_basketball_stats(
        self,
        team_name: str,
        league: str
    ) -> Optional[TeamStats]:
        """농구 팀 통계 수집

        현재는 기본 구조만 제공, 추후 API-Basketball 연동 예정

        Args:
            team_name: 팀명
            league: 리그명 ("NBA" 또는 "KBL")

        Returns:
            TeamStats 객체 또는 None
        """
        # TODO: API-Basketball 연동 구현
        # NBA: api-basketball.com 또는 balldontlie.io
        # KBL: 별도 데이터 소스 필요

        logger.warning(f"농구 통계 수집은 아직 미구현: {team_name} ({league})")
        return None

    async def get_multiple_team_stats(
        self,
        teams: list[tuple[str, str]],
        sport: str = "soccer",
        force_refresh: bool = False
    ) -> Dict[str, Optional[TeamStats]]:
        """여러 팀의 통계 일괄 조회

        Args:
            teams: [(팀명, 리그명), ...] 리스트
            sport: 스포츠 종류
            force_refresh: 캐시 무시 여부

        Returns:
            {팀명: TeamStats} 딕셔너리
        """
        results = {}

        # 병렬 처리 (rate limiter가 자동으로 조절)
        tasks = []
        for team_name, league in teams:
            task = self.get_team_stats(team_name, league, sport, force_refresh)
            tasks.append((team_name, task))

        for team_name, task in tasks:
            try:
                stats = await task
                results[team_name] = stats
            except Exception as e:
                logger.error(f"팀 통계 조회 실패: {team_name}, {e}")
                results[team_name] = None

        return results


# =============================================================================
# 전역 인스턴스
# =============================================================================

team_stats_collector = TeamStatsCollector()


# =============================================================================
# 편의 함수
# =============================================================================

async def get_team_stats(
    team_name: str,
    league: str,
    sport: str = "soccer"
) -> Optional[TeamStats]:
    """팀 통계 조회 편의 함수"""
    return await team_stats_collector.get_team_stats(team_name, league, sport)


# =============================================================================
# 테스트 함수
# =============================================================================

async def test_team_stats_collector():
    """TeamStatsCollector 테스트"""
    print("=" * 70)
    print("TeamStatsCollector 테스트")
    print("=" * 70)

    collector = TeamStatsCollector()

    # API 키 상태 확인
    print("\n[1] API 키 상태")
    print("-" * 50)
    print(f"  FOOTBALL_DATA_API_KEY: {'설정됨' if os.getenv('FOOTBALL_DATA_API_KEY') else '미설정'}")
    print(f"  API_FOOTBALL_KEY: {'설정됨' if os.getenv('API_FOOTBALL_KEY') else '미설정'}")

    # 축구 팀 테스트
    print("\n[2] 축구 팀 통계 조회 테스트")
    print("-" * 50)

    test_teams = [
        ("맨시티", "Premier League"),
        ("리버풀", "Premier League"),
        ("아스널", "Premier League"),
    ]

    for team_name, league in test_teams:
        print(f"\n  {team_name} ({league}):")
        stats = await collector.get_team_stats(team_name, league, "soccer")

        if stats:
            print(f"    - 경기 수: {stats.matches_played}")
            print(f"    - 승/무/패: {stats.wins}/{stats.draws}/{stats.losses}")
            print(f"    - 득/실점: {stats.goals_scored}/{stats.goals_conceded}")
            print(f"    - 순위: {stats.league_position}위 ({stats.points}점)")
        else:
            print("    - 수집 실패 (API 키 미설정 또는 API 오류)")

    # 농구 팀 테스트 (미구현 확인)
    print("\n[3] 농구 팀 통계 조회 테스트")
    print("-" * 50)
    stats = await collector.get_team_stats("LA레이커스", "NBA", "basketball")
    print(f"  LA레이커스: {'수집됨' if stats else '미구현'}")

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_team_stats_collector())
