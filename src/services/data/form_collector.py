"""
팀 최근 폼 수집 모듈

각 팀의 최근 경기 결과를 수집하여 폼 지표를 계산합니다.
외부 API (API-Football, Football-Data.org)를 사용하여 데이터를 수집합니다.

사용 예시:
    from src.services.data.form_collector import FormCollector, form_collector

    collector = FormCollector()

    # 팀의 최근 폼 조회
    form = await collector.get_team_form("맨시티", league="Premier League")

    # 결과 확인
    print(f"최근 결과: {form.recent_results}")  # ['W', 'W', 'D', 'L', 'W']
    print(f"폼 승점: {form.form_points}")  # 10
    print(f"연승 기록: {form.winning_streak}")  # 0
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from src.services.data.cache_manager import CacheManager, CacheTTL, get_cache_manager
from src.services.data.rate_limiter import rate_limited, get_rate_limiter, RATE_LIMITERS
from src.services.data.team_mapping import TeamMapper, team_mapper

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class RecentMatch:
    """최근 경기 정보

    Attributes:
        date: 경기 날짜 (YYYY-MM-DD)
        opponent: 상대팀명
        home_away: 홈/원정 ('H' or 'A')
        result: 경기 결과 ('W', 'D', 'L')
        score: 스코어 문자열 (예: '2-1')
        goals_scored: 득점
        goals_conceded: 실점
    """
    date: str
    opponent: str
    home_away: str  # 'H' or 'A'
    result: str  # 'W', 'D', 'L'
    score: str  # '2-1'
    goals_scored: int
    goals_conceded: int

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "date": self.date,
            "opponent": self.opponent,
            "home_away": self.home_away,
            "result": self.result,
            "score": self.score,
            "goals_scored": self.goals_scored,
            "goals_conceded": self.goals_conceded,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecentMatch":
        """딕셔너리에서 객체 생성"""
        return cls(
            date=data.get("date", ""),
            opponent=data.get("opponent", ""),
            home_away=data.get("home_away", ""),
            result=data.get("result", ""),
            score=data.get("score", ""),
            goals_scored=data.get("goals_scored", 0),
            goals_conceded=data.get("goals_conceded", 0),
        )


@dataclass
class TeamForm:
    """팀 폼 데이터

    Attributes:
        team_name: 팀명 (정규화됨)
        recent_results: 최근 경기 결과 리스트 ['W', 'W', 'D', 'L', 'W']
        recent_matches: 최근 경기 상세 정보
        form_points: 최근 경기 승점 합계 (승=3, 무=1, 패=0)
        form_goals_scored: 최근 경기 총 득점
        form_goals_conceded: 최근 경기 총 실점
        form_goal_diff: 최근 경기 골득실
        winning_streak: 현재 연승 기록
        losing_streak: 현재 연패 기록
        unbeaten_streak: 현재 무패 기록
        updated_at: 데이터 갱신 시간
    """
    team_name: str
    recent_results: List[str] = field(default_factory=list)  # ['W', 'W', 'D', 'L', 'W']
    recent_matches: List[RecentMatch] = field(default_factory=list)
    form_points: int = 0  # 최근 5경기 승점
    form_goals_scored: int = 0
    form_goals_conceded: int = 0
    form_goal_diff: int = 0
    winning_streak: int = 0
    losing_streak: int = 0
    unbeaten_streak: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "team_name": self.team_name,
            "recent_results": self.recent_results,
            "recent_matches": [m.to_dict() for m in self.recent_matches],
            "form_points": self.form_points,
            "form_goals_scored": self.form_goals_scored,
            "form_goals_conceded": self.form_goals_conceded,
            "form_goal_diff": self.form_goal_diff,
            "winning_streak": self.winning_streak,
            "losing_streak": self.losing_streak,
            "unbeaten_streak": self.unbeaten_streak,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamForm":
        """딕셔너리에서 객체 생성"""
        updated_at_str = data.get("updated_at", "")
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
            except ValueError:
                updated_at = datetime.now(timezone.utc)
        else:
            updated_at = datetime.now(timezone.utc)

        return cls(
            team_name=data.get("team_name", ""),
            recent_results=data.get("recent_results", []),
            recent_matches=[
                RecentMatch.from_dict(m) for m in data.get("recent_matches", [])
            ],
            form_points=data.get("form_points", 0),
            form_goals_scored=data.get("form_goals_scored", 0),
            form_goals_conceded=data.get("form_goals_conceded", 0),
            form_goal_diff=data.get("form_goal_diff", 0),
            winning_streak=data.get("winning_streak", 0),
            losing_streak=data.get("losing_streak", 0),
            unbeaten_streak=data.get("unbeaten_streak", 0),
            updated_at=updated_at,
        )

    def get_form_string(self) -> str:
        """폼 문자열 반환 (예: 'WWDLW')"""
        return "".join(self.recent_results)

    def get_form_rating(self) -> float:
        """폼 레이팅 반환 (0.0 ~ 1.0)

        최근 5경기 기준으로:
        - 승: 1.0
        - 무: 0.5
        - 패: 0.0
        """
        if not self.recent_results:
            return 0.5  # 기본값

        total = 0.0
        for result in self.recent_results:
            if result == 'W':
                total += 1.0
            elif result == 'D':
                total += 0.5
            # 'L'은 0.0

        return total / len(self.recent_results)


# =============================================================================
# FormCollector 클래스
# =============================================================================

class FormCollector:
    """팀 최근 폼 수집기

    API-Football 또는 Football-Data.org에서 팀의 최근 경기 결과를 수집합니다.

    사용 예시:
        collector = FormCollector()

        # 팀 폼 조회
        form = await collector.get_team_form("맨시티", league="Premier League")

        if form:
            print(f"폼: {form.get_form_string()}")  # WWDLW
            print(f"폼 레이팅: {form.get_form_rating():.2f}")  # 0.70
    """

    def __init__(self):
        """FormCollector 초기화"""
        self.team_mapper: TeamMapper = team_mapper
        self.cache_manager: CacheManager = get_cache_manager()

        # API 키 로드
        self.api_football_key: Optional[str] = os.getenv("API_FOOTBALL_KEY")
        self.football_data_key: Optional[str] = os.getenv("FOOTBALL_DATA_TOKEN")

        # API 기본 URL
        self.api_football_url = "https://v3.football.api-sports.io"
        self.football_data_url = "https://api.football-data.org/v4"

        # 세션은 lazy 초기화
        self._session: Optional[aiohttp.ClientSession] = None

        # API 사용 가능 여부 확인
        self._api_football_available = bool(self.api_football_key)
        self._football_data_available = bool(self.football_data_key)

        logger.info(
            f"FormCollector 초기화: "
            f"api_football={'활성' if self._api_football_available else '비활성'}, "
            f"football_data={'활성' if self._football_data_available else '비활성'}"
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp 세션 가져오기 (lazy 초기화)"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """리소스 정리"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_cache_key(self, team_name: str, league: Optional[str] = None) -> str:
        """캐시 키 생성

        Args:
            team_name: 팀명
            league: 리그명 (옵션)

        Returns:
            캐시 키 문자열
        """
        league_part = league.replace(" ", "_").lower() if league else "unknown"
        team_part = team_name.replace(" ", "_").lower()
        return f"form:{league_part}:{team_part}"

    async def get_team_form(
        self,
        team_name: str,
        league: Optional[str] = None,
        num_matches: int = 5,
        force_refresh: bool = False
    ) -> Optional[TeamForm]:
        """팀의 최근 폼 조회

        Args:
            team_name: 팀명 (한글 또는 영문)
            league: 리그명 (예: "Premier League")
            num_matches: 조회할 경기 수 (기본값: 5)
            force_refresh: 캐시 무시 여부

        Returns:
            TeamForm 객체 또는 None (API 키 없거나 실패 시)
        """
        # API 키 확인
        if not self._api_football_available and not self._football_data_available:
            logger.warning("폼 수집 불가: API 키가 설정되지 않음")
            return None

        # 팀명 정규화
        normalized_name = self.team_mapper.get_normalized_name(team_name, sport="soccer")
        if not normalized_name:
            logger.warning(f"팀명 매칭 실패: {team_name}")
            normalized_name = team_name  # 원본 사용

        # 캐시 확인
        cache_key = self._get_cache_key(normalized_name, league)
        if not force_refresh:
            cached_data = await self.cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"캐시에서 폼 로드: {normalized_name}")
                return TeamForm.from_dict(cached_data)

        # API에서 데이터 조회
        team_form = await self._fetch_team_form(normalized_name, league, num_matches)

        # 캐시 저장
        if team_form:
            await self.cache_manager.set(
                cache_key,
                team_form.to_dict(),
                CacheTTL.RECENT_FORM  # 1시간
            )

        return team_form

    async def _fetch_team_form(
        self,
        team_name: str,
        league: Optional[str],
        num_matches: int
    ) -> Optional[TeamForm]:
        """API에서 팀 폼 데이터 조회

        API-Football 우선, 실패 시 Football-Data.org 사용

        Args:
            team_name: 정규화된 팀명
            league: 리그명
            num_matches: 경기 수

        Returns:
            TeamForm 또는 None
        """
        # 1순위: API-Football
        if self._api_football_available:
            try:
                matches = await self._fetch_from_api_football(team_name, num_matches)
                if matches:
                    return self._calculate_form_metrics(team_name, matches)
            except Exception as e:
                logger.error(f"API-Football 조회 실패: {team_name}, {e}")

        # 2순위: Football-Data.org
        if self._football_data_available:
            try:
                matches = await self._fetch_from_football_data(team_name, league, num_matches)
                if matches:
                    return self._calculate_form_metrics(team_name, matches)
            except Exception as e:
                logger.error(f"Football-Data 조회 실패: {team_name}, {e}")

        logger.warning(f"폼 데이터 조회 실패: {team_name}")
        return None

    @rate_limited("api_football", timeout=30.0)
    async def _fetch_from_api_football(
        self,
        team_name: str,
        num_matches: int
    ) -> List[Dict[str, Any]]:
        """API-Football에서 경기 데이터 조회

        API 문서: https://www.api-football.com/documentation-v3

        Args:
            team_name: 팀명
            num_matches: 경기 수

        Returns:
            경기 데이터 리스트
        """
        # 팀 ID 조회
        team_id = self.team_mapper.get_api_id(team_name, api="api_football", sport="soccer")
        if not team_id:
            logger.warning(f"API-Football 팀 ID 없음: {team_name}")
            return []

        session = await self._get_session()
        headers = {
            "x-apisports-key": self.api_football_key,
        }

        # 최근 경기 조회 (fixtures endpoint)
        url = f"{self.api_football_url}/fixtures"
        params = {
            "team": team_id,
            "last": num_matches,
            "status": "FT",  # Full Time (종료된 경기만)
        }

        try:
            async with session.get(url, headers=headers, params=params, timeout=20) as response:
                if response.status != 200:
                    logger.error(f"API-Football 응답 오류: {response.status}")
                    return []

                data = await response.json()
                fixtures = data.get("response", [])

                matches = []
                for fixture in fixtures:
                    match_data = self._parse_api_football_fixture(fixture, team_id)
                    if match_data:
                        matches.append(match_data)

                logger.debug(f"API-Football: {team_name} - {len(matches)}경기 조회")
                return matches

        except asyncio.TimeoutError:
            logger.error(f"API-Football 타임아웃: {team_name}")
            return []
        except Exception as e:
            logger.error(f"API-Football 오류: {team_name}, {e}")
            return []

    def _parse_api_football_fixture(
        self,
        fixture: Dict[str, Any],
        team_id: int
    ) -> Optional[Dict[str, Any]]:
        """API-Football fixture 파싱

        Args:
            fixture: API 응답 fixture 객체
            team_id: 조회 팀 ID

        Returns:
            파싱된 경기 데이터 또는 None
        """
        try:
            fixture_info = fixture.get("fixture", {})
            teams = fixture.get("teams", {})
            goals = fixture.get("goals", {})

            home_team = teams.get("home", {})
            away_team = teams.get("away", {})

            # 홈/원정 판단
            is_home = home_team.get("id") == team_id

            if is_home:
                goals_scored = goals.get("home", 0) or 0
                goals_conceded = goals.get("away", 0) or 0
                opponent = away_team.get("name", "Unknown")
                home_away = "H"
            else:
                goals_scored = goals.get("away", 0) or 0
                goals_conceded = goals.get("home", 0) or 0
                opponent = home_team.get("name", "Unknown")
                home_away = "A"

            # 결과 판단
            if goals_scored > goals_conceded:
                result = "W"
            elif goals_scored < goals_conceded:
                result = "L"
            else:
                result = "D"

            # 날짜 파싱
            date_str = fixture_info.get("date", "")
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    date = date_str[:10]  # YYYY-MM-DD 부분만
            else:
                date = ""

            return {
                "date": date,
                "opponent": opponent,
                "home_away": home_away,
                "result": result,
                "goals_scored": goals_scored,
                "goals_conceded": goals_conceded,
            }

        except Exception as e:
            logger.error(f"API-Football 파싱 오류: {e}")
            return None

    @rate_limited("football_data", timeout=30.0)
    async def _fetch_from_football_data(
        self,
        team_name: str,
        league: Optional[str],
        num_matches: int
    ) -> List[Dict[str, Any]]:
        """Football-Data.org에서 경기 데이터 조회

        API 문서: https://www.football-data.org/documentation/quickstart

        Args:
            team_name: 팀명
            league: 리그명
            num_matches: 경기 수

        Returns:
            경기 데이터 리스트
        """
        # 팀 ID 조회
        team_id = self.team_mapper.get_api_id(team_name, api="football_data", sport="soccer")
        if not team_id:
            logger.warning(f"Football-Data 팀 ID 없음: {team_name}")
            return []

        session = await self._get_session()
        headers = {
            "X-Auth-Token": self.football_data_key,
        }

        # 최근 경기 조회
        url = f"{self.football_data_url}/teams/{team_id}/matches"
        params = {
            "status": "FINISHED",
            "limit": num_matches,
        }

        try:
            async with session.get(url, headers=headers, params=params, timeout=20) as response:
                if response.status == 429:
                    logger.warning("Football-Data API rate limit 도달")
                    return []
                if response.status != 200:
                    logger.error(f"Football-Data 응답 오류: {response.status}")
                    return []

                data = await response.json()
                raw_matches = data.get("matches", [])

                matches = []
                for match in raw_matches:
                    match_data = self._parse_football_data_match(match, team_id)
                    if match_data:
                        matches.append(match_data)

                # 최근 경기순으로 정렬 (내림차순)
                matches.sort(key=lambda x: x.get("date", ""), reverse=True)
                matches = matches[:num_matches]

                logger.debug(f"Football-Data: {team_name} - {len(matches)}경기 조회")
                return matches

        except asyncio.TimeoutError:
            logger.error(f"Football-Data 타임아웃: {team_name}")
            return []
        except Exception as e:
            logger.error(f"Football-Data 오류: {team_name}, {e}")
            return []

    def _parse_football_data_match(
        self,
        match: Dict[str, Any],
        team_id: int
    ) -> Optional[Dict[str, Any]]:
        """Football-Data match 파싱

        Args:
            match: API 응답 match 객체
            team_id: 조회 팀 ID

        Returns:
            파싱된 경기 데이터 또는 None
        """
        try:
            home_team = match.get("homeTeam", {})
            away_team = match.get("awayTeam", {})
            score = match.get("score", {}).get("fullTime", {})

            # 홈/원정 판단
            is_home = home_team.get("id") == team_id

            home_goals = score.get("home")
            away_goals = score.get("away")

            # 점수가 없으면 스킵
            if home_goals is None or away_goals is None:
                return None

            if is_home:
                goals_scored = home_goals
                goals_conceded = away_goals
                opponent = away_team.get("shortName") or away_team.get("name", "Unknown")
                home_away = "H"
            else:
                goals_scored = away_goals
                goals_conceded = home_goals
                opponent = home_team.get("shortName") or home_team.get("name", "Unknown")
                home_away = "A"

            # 결과 판단
            if goals_scored > goals_conceded:
                result = "W"
            elif goals_scored < goals_conceded:
                result = "L"
            else:
                result = "D"

            # 날짜 파싱
            utc_date = match.get("utcDate", "")
            if utc_date:
                try:
                    dt = datetime.fromisoformat(utc_date.replace('Z', '+00:00'))
                    date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    date = utc_date[:10]
            else:
                date = ""

            return {
                "date": date,
                "opponent": opponent,
                "home_away": home_away,
                "result": result,
                "goals_scored": goals_scored,
                "goals_conceded": goals_conceded,
            }

        except Exception as e:
            logger.error(f"Football-Data 파싱 오류: {e}")
            return None

    def _calculate_form_metrics(
        self,
        team_name: str,
        matches: List[Dict[str, Any]]
    ) -> TeamForm:
        """폼 지표 계산

        Args:
            team_name: 팀명
            matches: 경기 데이터 리스트

        Returns:
            TeamForm 객체
        """
        # 최근 순으로 정렬
        matches.sort(key=lambda x: x.get("date", ""), reverse=True)

        recent_results = []
        recent_matches = []
        form_points = 0
        form_goals_scored = 0
        form_goals_conceded = 0

        for match_data in matches:
            result = match_data.get("result", "")
            goals_scored = match_data.get("goals_scored", 0)
            goals_conceded = match_data.get("goals_conceded", 0)

            recent_results.append(result)

            # 승점 계산
            if result == "W":
                form_points += 3
            elif result == "D":
                form_points += 1

            form_goals_scored += goals_scored
            form_goals_conceded += goals_conceded

            # RecentMatch 객체 생성
            recent_matches.append(RecentMatch(
                date=match_data.get("date", ""),
                opponent=match_data.get("opponent", ""),
                home_away=match_data.get("home_away", ""),
                result=result,
                score=f"{goals_scored}-{goals_conceded}",
                goals_scored=goals_scored,
                goals_conceded=goals_conceded,
            ))

        # 연승/연패/무패 계산
        winning_streak = self._calculate_streak(recent_results, "W")
        losing_streak = self._calculate_streak(recent_results, "L")
        unbeaten_streak = self._calculate_unbeaten_streak(recent_results)

        return TeamForm(
            team_name=team_name,
            recent_results=recent_results,
            recent_matches=recent_matches,
            form_points=form_points,
            form_goals_scored=form_goals_scored,
            form_goals_conceded=form_goals_conceded,
            form_goal_diff=form_goals_scored - form_goals_conceded,
            winning_streak=winning_streak,
            losing_streak=losing_streak,
            unbeaten_streak=unbeaten_streak,
            updated_at=datetime.now(timezone.utc),
        )

    def _calculate_streak(self, results: List[str], target: str) -> int:
        """연속 기록 계산

        Args:
            results: 결과 리스트 ['W', 'W', 'D', ...]
            target: 목표 결과 ('W' or 'L')

        Returns:
            현재 연속 기록 수
        """
        streak = 0
        for result in results:
            if result == target:
                streak += 1
            else:
                break
        return streak

    def _calculate_unbeaten_streak(self, results: List[str]) -> int:
        """무패 연속 기록 계산

        Args:
            results: 결과 리스트

        Returns:
            현재 무패 연속 기록 수
        """
        streak = 0
        for result in results:
            if result in ("W", "D"):
                streak += 1
            else:
                break
        return streak

    async def get_multiple_team_forms(
        self,
        team_names: List[str],
        league: Optional[str] = None,
        num_matches: int = 5
    ) -> Dict[str, Optional[TeamForm]]:
        """여러 팀의 폼 일괄 조회

        Args:
            team_names: 팀명 리스트
            league: 리그명
            num_matches: 경기 수

        Returns:
            {팀명: TeamForm} 딕셔너리
        """
        tasks = [
            self.get_team_form(team_name, league, num_matches)
            for team_name in team_names
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        form_dict = {}
        for team_name, result in zip(team_names, results):
            if isinstance(result, Exception):
                logger.error(f"폼 조회 실패: {team_name}, {result}")
                form_dict[team_name] = None
            else:
                form_dict[team_name] = result

        return form_dict


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_form_collector_instance: Optional[FormCollector] = None


def get_form_collector() -> FormCollector:
    """FormCollector 싱글톤 인스턴스 반환"""
    global _form_collector_instance

    if _form_collector_instance is None:
        _form_collector_instance = FormCollector()

    return _form_collector_instance


# 편의를 위한 전역 인스턴스 (lazy 초기화)
form_collector = None


def _init_form_collector() -> FormCollector:
    """지연 초기화된 form_collector 반환"""
    global form_collector
    if form_collector is None:
        form_collector = get_form_collector()
    return form_collector


# =============================================================================
# 테스트 함수
# =============================================================================

async def test_form_collector():
    """FormCollector 테스트"""
    print("=" * 70)
    print("FormCollector 테스트")
    print("=" * 70)

    collector = FormCollector()

    # 환경 확인
    print("\n[1] 환경 확인")
    print("-" * 50)
    print(f"  API-Football: {'활성' if collector._api_football_available else '비활성'}")
    print(f"  Football-Data: {'활성' if collector._football_data_available else '비활성'}")

    if not collector._api_football_available and not collector._football_data_available:
        print("\n  API 키가 설정되지 않아 테스트를 건너뜁니다.")
        print("  .env 파일에 API_FOOTBALL_KEY 또는 FOOTBALL_DATA_TOKEN을 설정하세요.")
        await collector.close()
        return

    # 팀 폼 조회 테스트
    print("\n[2] 팀 폼 조회 테스트")
    print("-" * 50)

    test_teams = [
        ("맨시티", "Premier League"),
        ("리버풀", "Premier League"),
        ("아스널", "Premier League"),
    ]

    for team_name, league in test_teams:
        print(f"\n  {team_name} ({league}):")
        try:
            form = await collector.get_team_form(team_name, league)
            if form:
                print(f"    폼 문자열: {form.get_form_string()}")
                print(f"    폼 레이팅: {form.get_form_rating():.2f}")
                print(f"    폼 승점: {form.form_points}")
                print(f"    골득실: {form.form_goal_diff}")
                print(f"    연승: {form.winning_streak}, 연패: {form.losing_streak}, 무패: {form.unbeaten_streak}")
                if form.recent_matches:
                    print(f"    최근 경기:")
                    for i, match in enumerate(form.recent_matches[:3], 1):
                        ha = "H" if match.home_away == "H" else "A"
                        print(f"      {i}. {match.date} ({ha}) vs {match.opponent}: {match.score} [{match.result}]")
            else:
                print("    데이터 조회 실패")
        except Exception as e:
            print(f"    오류: {e}")

    # 리소스 정리
    await collector.close()

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

    asyncio.run(test_form_collector())
