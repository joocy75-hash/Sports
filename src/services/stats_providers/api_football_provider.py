"""
API-Football.com Provider

축구 팀 통계를 API-Football.com으로부터 가져옵니다.

API 문서: https://www.api-football.com/documentation-v3
Free tier: 100 requests/day
"""

import aiohttp
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .base_provider import BaseStatsProvider, TeamStats

logger = logging.getLogger(__name__)


class APIFootballProvider(BaseStatsProvider):
    """
    API-Football.com 기반 축구 통계 제공자

    Free tier 제한: 100 requests/day
    → 캐싱 필수 (메모리 + 파일, TTL 1일)
    """

    BASE_URL = "https://v3.football.api-sports.io"

    # 베트맨 팀명 → API-Football 팀명 매핑
    TEAM_NAME_MAPPING = {
        # 영국
        "맨체스U": "Manchester United",
        "맨체스C": "Manchester City",
        "리버풀": "Liverpool",
        "첼시": "Chelsea",
        "아스널": "Arsenal",
        "토트넘": "Tottenham",
        "뉴캐슬": "Newcastle",
        "레스터C": "Leicester",
        "웨스트햄": "West Ham",
        "에버턴": "Everton",
        "브라이턴": "Brighton",
        "A빌라": "Aston Villa",
        "울버햄튼": "Wolves",
        "크리스탈팰": "Crystal Palace",
        "본머스": "Bournemouth",
        "브렌트퍼드": "Brentford",
        "풀럼": "Fulham",
        "노팅엄F": "Nottingham Forest",
        "루턴T": "Luton",
        "번리": "Burnley",
        "셰필U": "Sheffield United",

        # 챔피언십
        "리즈U": "Leeds",
        "노리치C": "Norwich",
        "스토크C": "Stoke City",
        "왓포드": "Watford",
        "찰턴": "Charlton",
        "프레스턴": "Preston",
        "미들즈브러": "Middlesbrough",
        "블랙번": "Blackburn",

        # 이탈리아
        "인테르": "Inter",
        "밀란": "AC Milan",
        "유벤투스": "Juventus",
        "나폴리": "Napoli",
        "로마": "Roma",
        "라치오": "Lazio",
        "아탈란타": "Atalanta",
        "피오렌티나": "Fiorentina",
        "제노아": "Genoa",
        "토리노": "Torino",

        # 스페인
        "레알M": "Real Madrid",
        "바르셀로나": "Barcelona",
        "AT마드리드": "Atletico Madrid",
        "세비야": "Sevilla",
        "발렌시아": "Valencia",
        "빌바오": "Athletic Club",
        "레알소시에다드": "Real Sociedad",
        "베티스": "Real Betis",

        # 독일
        "바이에른": "Bayern Munich",
        "도르트문트": "Dortmund",
        "라이프치히": "RB Leipzig",
        "레버쿠젠": "Leverkusen",
        "프랑크푸르트": "Eintracht Frankfurt",

        # 프랑스
        "PSG": "Paris Saint Germain",
        "마르세유": "Marseille",
        "리옹": "Lyon",
        "모나코": "Monaco",
        "릴": "Lille",
    }

    # 리그명 → API-Football 리그 ID 매핑
    LEAGUE_ID_MAPPING = {
        "프리미어리그": 39,
        "챔피언십": 40,
        "세리에A": 135,
        "라리가": 140,
        "분데스리가": 78,
        "리그1": 61,
    }

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.provider_name = "api_football"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp 세션 가져오기 (재사용)"""
        if self.session is None or self.session.closed:
            headers = {
                "x-apisports-key": self.api_key,
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    async def close(self):
        """세션 종료"""
        if self.session and not self.session.closed:
            await self.session.close()

    def normalize_team_name(self, team_name: str) -> str:
        """베트맨 팀명 → API-Football 팀명 변환"""
        normalized = self.TEAM_NAME_MAPPING.get(team_name.strip(), team_name)
        logger.debug(f"Team name normalized: {team_name} → {normalized}")
        return normalized

    def _get_league_id(self, league: str) -> Optional[int]:
        """리그명 → API-Football 리그 ID"""
        return self.LEAGUE_ID_MAPPING.get(league.strip())

    async def is_available(self) -> bool:
        """API 사용 가능 여부 확인"""
        if not self.api_key:
            logger.warning("API-Football: No API key provided")
            return False

        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/status"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    # API status 확인
                    logger.info(f"API-Football status: {data}")
                    return True
                else:
                    logger.warning(f"API-Football status check failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"API-Football availability check failed: {e}")
            return False

    async def get_team_stats(
        self,
        team_name: str,
        league: str,
        is_home: bool = True
    ) -> Optional[TeamStats]:
        """
        팀 통계 가져오기

        Args:
            team_name: 팀 이름 (베트맨 형식)
            league: 리그 이름
            is_home: 홈 경기 여부

        Returns:
            TeamStats 또는 None (실패 시)
        """
        if not self.api_key:
            logger.warning("API-Football: No API key, skipping")
            return None

        try:
            # 1. 팀명 정규화
            normalized_team = self.normalize_team_name(team_name)
            league_id = self._get_league_id(league)

            if not league_id:
                logger.warning(f"Unknown league: {league}")
                return None

            # 2. 팀 ID 조회
            team_id = await self._search_team(normalized_team, league_id)
            if not team_id:
                logger.warning(f"Team not found: {normalized_team} in {league}")
                return None

            # 3. 팀 통계 조회
            stats_data = await self._get_team_statistics(team_id, league_id)
            if not stats_data:
                logger.warning(f"No statistics found for team_id={team_id}")
                return None

            # 4. TeamStats 변환
            team_stats = self._convert_to_team_stats(
                team_name=team_name,
                league=league,
                stats_data=stats_data,
                is_home=is_home
            )

            logger.info(f"✅ API-Football: Got stats for {team_name} (source: {team_stats.source})")
            return team_stats

        except Exception as e:
            logger.error(f"API-Football error for {team_name}: {e}", exc_info=True)
            return None

    async def _search_team(self, team_name: str, league_id: int) -> Optional[int]:
        """팀 검색 → team_id 반환"""
        session = await self._get_session()
        url = f"{self.BASE_URL}/teams"
        params = {
            "name": team_name,
            "league": league_id,
            "season": datetime.now().year,  # 현재 시즌
        }

        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.error(f"Team search failed: {response.status}")
                return None

            data = await response.json()
            results = data.get("response", [])

            if not results:
                logger.warning(f"No team found: {team_name}")
                return None

            # 첫 번째 결과의 team ID 반환
            team_id = results[0]["team"]["id"]
            logger.debug(f"Found team_id={team_id} for {team_name}")
            return team_id

    async def _get_team_statistics(self, team_id: int, league_id: int) -> Optional[Dict[str, Any]]:
        """팀 통계 조회"""
        session = await self._get_session()
        url = f"{self.BASE_URL}/teams/statistics"
        params = {
            "team": team_id,
            "league": league_id,
            "season": datetime.now().year,
        }

        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.error(f"Team statistics failed: {response.status}")
                return None

            data = await response.json()
            response_data = data.get("response")

            if not response_data:
                return None

            logger.debug(f"Got statistics for team_id={team_id}")
            return response_data

    def _convert_to_team_stats(
        self,
        team_name: str,
        league: str,
        stats_data: Dict[str, Any],
        is_home: bool
    ) -> TeamStats:
        """
        API-Football 응답 → TeamStats 변환

        실용적 공식 기반:
        - 공격 레이팅: 득점력 + 폼 (승리 가중)
        - 수비 레이팅: 실점 적음 + 클린시트
        - 최근 폼: 최근 5경기 가중 평균
        """
        # 1. 기본 통계 추출
        try:
            goals_data = stats_data.get("goals", {})
            goals_for = goals_data.get("for", {})
            goals_against = goals_data.get("against", {})

            avg_goals_scored = float(goals_for.get("average", {}).get("total", 1.5))
            avg_goals_conceded = float(goals_against.get("average", {}).get("total", 1.5))

            fixtures_data = stats_data.get("fixtures", {})
            played = fixtures_data.get("played", {}).get("total", 1)
            wins = fixtures_data.get("wins", {}).get("total", 0)
            clean_sheet = stats_data.get("clean_sheet", {}).get("total", 0)

            form = stats_data.get("form", "DDDDD")  # 기본값: 무승부 5경기

        except Exception as e:
            logger.error(f"Failed to parse stats_data for {team_name}: {e}")
            # 파싱 실패 시 기본값 반환
            return TeamStats(
                team_name=team_name,
                league=league,
                attack_rating=50.0,
                defense_rating=50.0,
                recent_form=50.0,
                win_rate=0.5,
                home_advantage=5.0 if is_home else 0.0,
                avg_goals_scored=1.5,
                avg_goals_conceded=1.5,
                last_updated=datetime.now(),
                source=self.provider_name,
            )

        # 2. 공격 레이팅 계산 (0-100)
        # 득점력 기반: 리그 평균 1.5골 기준
        # 2.5골+ = 90점, 1.5골 = 50점, 0.5골 = 20점
        attack_base = min(100, max(0, (avg_goals_scored - 0.5) / 2.0 * 70 + 20))

        # 폼 보정: 최근 승리 많으면 +15점
        win_count = form.count("W")
        form_bonus = (win_count / 5.0) * 15

        attack_rating = min(100, attack_base + form_bonus)

        # 3. 수비 레이팅 계산 (0-100)
        # 실점 적을수록 높은 점수
        # 0.5골 이하 = 90점, 1.5골 = 50점, 2.5골+ = 20점
        defense_base = min(100, max(0, 100 - (avg_goals_conceded - 0.5) / 2.0 * 70))

        # 클린시트 보정: 전체 경기의 40% 이상이면 +20점
        clean_sheet_rate = clean_sheet / played if played > 0 else 0
        clean_sheet_bonus = min(20, clean_sheet_rate * 50)

        defense_rating = min(100, defense_base + clean_sheet_bonus)

        # 4. 최근 폼 계산 (0-100)
        # 최근 경기일수록 가중치 높음
        form_points = 0.0
        for i, result in enumerate(reversed(form[:5])):  # 최근 5경기
            weight = (i + 1) / 5.0  # 0.2, 0.4, 0.6, 0.8, 1.0
            if result == "W":
                form_points += 3 * weight
            elif result == "D":
                form_points += 1 * weight
            # L(패배)는 0점

        # 0-100 정규화 (최대 3*1.0 + 3*0.8 + 3*0.6 + 3*0.4 + 3*0.2 = 9점)
        recent_form = (form_points / 9.0) * 100

        # 5. 승률 계산
        win_rate = wins / played if played > 0 else 0.5

        # 6. 홈 어드밴티지 (통계 기반)
        if is_home:
            home_played = fixtures_data.get("played", {}).get("home", 1)
            away_played = fixtures_data.get("played", {}).get("away", 1)
            home_wins = fixtures_data.get("wins", {}).get("home", 0)
            away_wins = fixtures_data.get("wins", {}).get("away", 0)

            home_win_rate = home_wins / home_played if home_played > 0 else 0.5
            away_win_rate = away_wins / away_played if away_played > 0 else 0.5

            # 홈 승률 - 원정 승률 차이 * 50 (최대 10점)
            home_advantage = max(0, min(10, (home_win_rate - away_win_rate) * 50))
        else:
            home_advantage = 0.0

        logger.debug(
            f"Converted {team_name}: "
            f"attack={attack_rating:.1f}, defense={defense_rating:.1f}, "
            f"form={recent_form:.1f}, goals={avg_goals_scored:.2f}"
        )

        return TeamStats(
            team_name=team_name,
            league=league,
            attack_rating=round(attack_rating, 1),
            defense_rating=round(defense_rating, 1),
            recent_form=round(recent_form, 1),
            win_rate=round(win_rate, 3),
            home_advantage=round(home_advantage, 1),
            avg_goals_scored=round(avg_goals_scored, 2),
            avg_goals_conceded=round(avg_goals_conceded, 2),
            last_updated=datetime.now(),
            source=self.provider_name,
        )
