"""
팀 통계 크롤러 및 데이터 수집기

API-Football을 주 데이터 소스로 사용하여 팀 통계 수집
FBref 등 추가 소스는 선택적으로 사용 가능
"""

import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class TeamStatistics:
    """팀 통계 데이터 클래스"""

    team_name: str
    team_id: Optional[int] = None

    # 시즌 통계
    matches_played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0

    # 득실점
    goals_scored: int = 0
    goals_conceded: int = 0
    goals_scored_avg: float = 0.0
    goals_conceded_avg: float = 0.0

    # 홈/원정 분리
    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0
    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0

    # 고급 통계 (가능한 경우)
    xg: Optional[float] = None  # 기대득점
    xga: Optional[float] = None  # 기대실점
    shots_per_game: Optional[float] = None
    shots_on_target: Optional[float] = None

    # 최근 폼 (최근 5경기)
    recent_form: str = ""  # WWDLW 형식

    # 모멘텀 (0.0 ~ 1.0)
    momentum: float = 0.5

    # 메타 정보
    last_updated: Optional[datetime] = None


class TeamStatsCollector:
    """
    팀 통계 수집기

    1. API-Football에서 팀 시즌 통계 가져오기
    2. 최근 경기 결과로 폼/모멘텀 계산
    3. DB에 저장
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY")
        self.base_url = "https://v3.football.api-sports.io"
        self.session: Optional[aiohttp.ClientSession] = None

        # 팀명 매핑 (한글 -> API ID)
        self.korean_team_mapping = {}

    async def _ensure_session(self):
        """세션 확인 및 생성"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={"x-apisports-key": self.api_key}
            )

    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_team_stats_by_name(
        self,
        team_name: str,
        league_id: int = 39,  # 기본값: 프리미어리그
        season: int = 2024,
    ) -> Optional[TeamStatistics]:
        """
        팀 이름으로 통계 조회

        Args:
            team_name: 팀 이름 (한글 또는 영어)
            league_id: 리그 ID (39=EPL, 140=라리가, 135=세리에A, ...)
            season: 시즌 연도
        """
        await self._ensure_session()

        # 한글 팀명 영어로 변환
        english_name = self._map_korean_to_english(team_name)

        try:
            # 1. 팀 검색
            team_id = await self._search_team(english_name, league_id)

            if not team_id:
                logger.warning(f"Team not found: {team_name}")
                return None

            # 2. 팀 통계 조회
            stats = await self._fetch_team_statistics(team_id, league_id, season)

            # 3. 최근 경기 조회 (폼 계산용)
            recent_matches = await self._fetch_recent_matches(team_id, 5)

            if stats:
                stats.recent_form = self._calculate_form(recent_matches, team_id)
                stats.momentum = self._calculate_momentum(recent_matches, team_id)
                stats.last_updated = datetime.now()

            return stats

        except Exception as e:
            logger.error(f"Error fetching stats for {team_name}: {e}")
            return None

    async def _search_team(
        self, team_name: str, league_id: Optional[int] = None
    ) -> Optional[int]:
        """팀 ID 검색"""
        try:
            url = f"{self.base_url}/teams"
            params = {"search": team_name}

            if league_id:
                params["league"] = league_id

            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                teams = data.get("response", [])

                if teams:
                    return teams[0].get("team", {}).get("id")

                return None

        except Exception as e:
            logger.error(f"Team search error: {e}")
            return None

    async def _fetch_team_statistics(
        self, team_id: int, league_id: int, season: int
    ) -> Optional[TeamStatistics]:
        """API에서 팀 시즌 통계 가져오기"""
        try:
            url = f"{self.base_url}/teams/statistics"
            params = {"team": team_id, "league": league_id, "season": season}

            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                response = data.get("response", {})

                if not response:
                    return None

                team_info = response.get("team", {})
                fixtures = response.get("fixtures", {})
                goals = response.get("goals", {})

                # 경기 수 파싱
                played = fixtures.get("played", {})
                wins_data = fixtures.get("wins", {})
                draws_data = fixtures.get("draws", {})
                loses_data = fixtures.get("loses", {})

                # 득점 파싱
                goals_for = goals.get("for", {}).get("total", {})
                goals_against = goals.get("against", {}).get("total", {})

                avg_for = goals.get("for", {}).get("average", {})
                avg_against = goals.get("against", {}).get("average", {})

                return TeamStatistics(
                    team_name=team_info.get("name", "Unknown"),
                    team_id=team_id,
                    matches_played=played.get("total", 0) or 0,
                    wins=wins_data.get("total", 0) or 0,
                    draws=draws_data.get("total", 0) or 0,
                    losses=loses_data.get("total", 0) or 0,
                    goals_scored=goals_for.get("total", 0) or 0,
                    goals_conceded=goals_against.get("total", 0) or 0,
                    goals_scored_avg=float(avg_for.get("total", "0") or 0),
                    goals_conceded_avg=float(avg_against.get("total", "0") or 0),
                    home_wins=wins_data.get("home", 0) or 0,
                    home_draws=draws_data.get("home", 0) or 0,
                    home_losses=loses_data.get("home", 0) or 0,
                    away_wins=wins_data.get("away", 0) or 0,
                    away_draws=draws_data.get("away", 0) or 0,
                    away_losses=loses_data.get("away", 0) or 0,
                )

        except Exception as e:
            logger.error(f"Fetch statistics error: {e}")
            return None

    async def _fetch_recent_matches(self, team_id: int, count: int = 5) -> List[Dict]:
        """최근 경기 결과 가져오기"""
        try:
            url = f"{self.base_url}/fixtures"
            params = {
                "team": team_id,
                "last": count,
                "status": "FT",  # 완료된 경기만
            }

            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                return data.get("response", [])

        except Exception as e:
            logger.error(f"Fetch recent matches error: {e}")
            return []

    def _calculate_form(self, matches: List[Dict], team_id: int) -> str:
        """최근 경기 폼 계산 (WWDLW 형식)"""
        form = ""

        for match in matches:
            teams = match.get("teams", {})
            goals = match.get("goals", {})

            home_id = teams.get("home", {}).get("id")
            home_goals = goals.get("home", 0) or 0
            away_goals = goals.get("away", 0) or 0

            if home_id == team_id:
                # 홈 경기
                if home_goals > away_goals:
                    form += "W"
                elif home_goals == away_goals:
                    form += "D"
                else:
                    form += "L"
            else:
                # 원정 경기
                if away_goals > home_goals:
                    form += "W"
                elif away_goals == home_goals:
                    form += "D"
                else:
                    form += "L"

        return form

    def _calculate_momentum(self, matches: List[Dict], team_id: int) -> float:
        """
        모멘텀 계산 (0.0 ~ 1.0)

        최근 경기 결과에 가중치를 두어 계산
        """
        if not matches:
            return 0.5

        form = self._calculate_form(matches, team_id)

        if not form:
            return 0.5

        # 가중치: 최근 경기일수록 높음
        weights = [0.35, 0.25, 0.20, 0.12, 0.08]  # 5경기 가중치
        momentum = 0.0

        for i, result in enumerate(form):
            if i >= len(weights):
                break

            if result == "W":
                momentum += weights[i] * 1.0
            elif result == "D":
                momentum += weights[i] * 0.5
            # L은 0점

        return round(momentum, 2)

    def _map_korean_to_english(self, name: str) -> str:
        """한글 팀명을 영문으로 변환"""
        mapping = {
            # EPL
            "뉴캐슬": "Newcastle",
            "첼시": "Chelsea",
            "본머스": "Bournemouth",
            "브라이턴": "Brighton",
            "울버햄프턴": "Wolverhampton",
            "울버햄튼": "Wolverhampton",
            "브렌트퍼드": "Brentford",
            "토트넘": "Tottenham",
            "리버풀": "Liverpool",
            "에버턴": "Everton",
            "아스널": "Arsenal",
            "아스톤빌라": "Aston Villa",
            "아스톤 빌라": "Aston Villa",
            "맨체스터유나이티드": "Manchester United",
            "맨유": "Manchester United",
            "맨체스터시티": "Manchester City",
            "맨시티": "Manchester City",
            "크리스탈팰리스": "Crystal Palace",
            "크리스탈 팰리스": "Crystal Palace",
            "노팅엄": "Nottingham",
            "풀럼": "Fulham",
            "웨스트햄": "West Ham",
            "레스터": "Leicester",
            "입스위치": "Ipswich",
            "사우스햄튼": "Southampton",
            # La Liga
            "바르셀로나": "Barcelona",
            "레알마드리드": "Real Madrid",
            "아틀레티코마드리드": "Atletico Madrid",
            "세비야": "Sevilla",
            "발렌시아": "Valencia",
            "레알소시에다드": "Real Sociedad",
            "비야레알": "Villarreal",
            "베티스": "Betis",
            "셀타비고": "Celta Vigo",
            "알라베스": "Alaves",
            "지로나": "Girona",
            # Serie A
            "라치오": "Lazio",
            "파르마": "Parma",
            "유벤투스": "Juventus",
            "AS로마": "AS Roma",
            "로마": "Roma",
            "인터밀란": "Inter",
            "인터": "Inter",
            "AC밀란": "AC Milan",
            "밀란": "Milan",
            "나폴리": "Napoli",
            "아탈란타": "Atalanta",
            "볼로냐": "Bologna",
            "피오렌티나": "Fiorentina",
            "토리노": "Torino",
            "우디네세": "Udinese",
            # Bundesliga
            "바이에른뮌헨": "Bayern Munich",
            "바이에른": "Bayern Munich",
            "도르트문트": "Dortmund",
            "보루시아도르트문트": "Borussia Dortmund",
            "라이프치히": "RB Leipzig",
            "레버쿠젠": "Bayer Leverkusen",
            "프랑크푸르트": "Eintracht Frankfurt",
            "볼프스부르크": "Wolfsburg",
            "묀헨글라트바흐": "Monchengladbach",
            "슈투트가르트": "Stuttgart",
            # K리그
            "전북현대": "Jeonbuk",
            "울산현대": "Ulsan",
            "포항스틸러스": "Pohang",
            "수원삼성": "Suwon",
            "FC서울": "FC Seoul",
            "강원FC": "Gangwon",
            "대구FC": "Daegu",
            "인천유나이티드": "Incheon",
            "제주유나이티드": "Jeju",
            "성남FC": "Seongnam",
        }

        # 공백 및 특수문자 정리
        clean_name = name.replace("FC", "").strip()

        return mapping.get(clean_name, mapping.get(name, name))


# 기본 통계 데이터 (API 접근 불가 시)
DEFAULT_TEAM_STATS = {
    # EPL 주요 팀 (2024-25 시즌 기준 추정치)
    "Liverpool": TeamStatistics(
        team_name="Liverpool",
        goals_scored_avg=2.3,
        goals_conceded_avg=0.8,
        momentum=0.9,
        recent_form="WWWWD",
    ),
    "Arsenal": TeamStatistics(
        team_name="Arsenal",
        goals_scored_avg=2.0,
        goals_conceded_avg=0.9,
        momentum=0.75,
        recent_form="WWDWL",
    ),
    "Manchester City": TeamStatistics(
        team_name="Manchester City",
        goals_scored_avg=2.1,
        goals_conceded_avg=1.2,
        momentum=0.6,
        recent_form="WLDLD",
    ),
    "Chelsea": TeamStatistics(
        team_name="Chelsea",
        goals_scored_avg=1.8,
        goals_conceded_avg=1.0,
        momentum=0.7,
        recent_form="WDWWL",
    ),
    "Newcastle": TeamStatistics(
        team_name="Newcastle",
        goals_scored_avg=1.5,
        goals_conceded_avg=1.1,
        momentum=0.65,
        recent_form="DWWDL",
    ),
    "Tottenham": TeamStatistics(
        team_name="Tottenham",
        goals_scored_avg=1.9,
        goals_conceded_avg=1.3,
        momentum=0.55,
        recent_form="WLDWL",
    ),
}


async def get_team_stats(
    team_name: str, league_id: int = 39, use_api: bool = True
) -> TeamStatistics:
    """
    팀 통계 가져오기 (헬퍼 함수)

    API 실패 시 기본값 반환
    """
    if use_api:
        collector = TeamStatsCollector()
        try:
            stats = await collector.fetch_team_stats_by_name(team_name, league_id)
            if stats:
                return stats
        except Exception as e:
            logger.warning(f"API failed, using defaults: {e}")
        finally:
            await collector.close()

    # API 실패 시 기본값
    english_name = TeamStatsCollector()._map_korean_to_english(team_name)

    if english_name in DEFAULT_TEAM_STATS:
        return DEFAULT_TEAM_STATS[english_name]

    # 완전 기본값
    return TeamStatistics(
        team_name=team_name,
        goals_scored_avg=1.2,
        goals_conceded_avg=1.2,
        momentum=0.5,
        recent_form="DDDDD",
    )
