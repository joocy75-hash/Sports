"""
BallDontLie API Provider

농구 팀 통계를 BallDontLie API로부터 가져옵니다.

API 문서: https://docs.balldontlie.io/
Free tier: Unlimited requests (rate limited to 60 req/min)
"""

import aiohttp
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .base_provider import BaseStatsProvider, TeamStats

logger = logging.getLogger(__name__)


class BallDontLieProvider(BaseStatsProvider):
    """
    BallDontLie API 기반 농구 통계 제공자

    NBA, KBL 등 농구 리그 통계 제공
    Free tier: Unlimited (60 req/min rate limit)
    """

    BASE_URL = "https://api.balldontlie.io/v1"

    # 베트맨 팀명 → BallDontLie 팀명 매핑
    TEAM_NAME_MAPPING = {
        # NBA
        "보스턴": "Celtics",
        "뉴욕닉스": "Knicks",
        "브루클린": "Nets",
        "필라델피아": "76ers",
        "토론토": "Raptors",
        "시카고": "Bulls",
        "클리블랜드": "Cavaliers",
        "디트로이트": "Pistons",
        "인디애나": "Pacers",
        "밀워키": "Bucks",
        "애틀랜타": "Hawks",
        "샬럿": "Hornets",
        "마이애미": "Heat",
        "올랜도": "Magic",
        "워싱턴": "Wizards",
        "덴버": "Nuggets",
        "미네소타": "Timberwolves",
        "미네소타팀버울": "Timberwolves",
        "오클라호마": "Thunder",
        "포틀랜드": "Trail Blazers",
        "유타": "Jazz",
        "골든스테이트": "Warriors",
        "LA클리퍼스": "Clippers",
        "LA레이커스": "Lakers",
        "피닉스": "Suns",
        "새크라멘토": "Kings",
        "댈러스": "Mavericks",
        "휴스턴": "Rockets",
        "멤피스": "Grizzlies",
        "뉴올리언스": "Pelicans",
        "샌안토니오": "Spurs",

        # KBL
        "울산모비스": "Ulsan Hyundai Mobis Phoebus",
        "울산현대모비스": "Ulsan Hyundai Mobis Phoebus",
        "수원KT": "Suwon KT Sonicboom",
        "수원KT소닉붐": "Suwon KT Sonicboom",
        "서울삼성": "Seoul Samsung Thunders",
        "서울SK": "Seoul SK Knights",
        "창원LG": "Changwon LG Sakers",
        "고양소노": "Goyang Sono Skygunners",
        "안양정관장": "Anyang KGC",
        "부산KCC": "Busan KCC Egis",
        "원주DB": "Wonju DB Promy",
        "대구한국가스공사": "Daegu KOGAS Pegasus",
    }

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.provider_name = "balldontlie"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp 세션 가져오기"""
        if self.session is None or self.session.closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    async def close(self):
        """세션 종료"""
        if self.session and not self.session.closed:
            await self.session.close()

    def normalize_team_name(self, team_name: str) -> str:
        """베트맨 팀명 → BallDontLie 팀명 변환"""
        normalized = self.TEAM_NAME_MAPPING.get(team_name.strip(), team_name)
        logger.debug(f"Team name normalized: {team_name} → {normalized}")
        return normalized

    async def is_available(self) -> bool:
        """API 사용 가능 여부 확인"""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/teams"
            params = {"per_page": 1}  # 최소한의 요청

            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    logger.info("BallDontLie API is available")
                    return True
                else:
                    logger.warning(f"BallDontLie status check failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"BallDontLie availability check failed: {e}")
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
            league: 리그 이름 (NBA, KBL 등)
            is_home: 홈 경기 여부

        Returns:
            TeamStats 또는 None (실패 시)
        """
        try:
            # 1. 팀명 정규화
            normalized_team = self.normalize_team_name(team_name)

            # 2. 팀 검색
            team_data = await self._search_team(normalized_team)
            if not team_data:
                logger.warning(f"Team not found: {normalized_team}")
                return None

            team_id = team_data["id"]

            # 3. 팀 통계 조회 (현재 시즌)
            stats_data = await self._get_season_averages(team_id)
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

            logger.info(f"✅ BallDontLie: Got stats for {team_name} (source: {team_stats.source})")
            return team_stats

        except Exception as e:
            logger.error(f"BallDontLie error for {team_name}: {e}", exc_info=True)
            return None

    async def _search_team(self, team_name: str) -> Optional[Dict[str, Any]]:
        """팀 검색"""
        session = await self._get_session()
        url = f"{self.BASE_URL}/teams"
        params = {
            "search": team_name,
            "per_page": 100,  # 모든 팀 조회
        }

        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.error(f"Team search failed: {response.status}")
                return None

            data = await response.json()
            teams = data.get("data", [])

            # 팀명으로 매칭
            for team in teams:
                if team_name.lower() in team["full_name"].lower() or \
                   team_name.lower() in team["name"].lower():
                    logger.debug(f"Found team: {team['full_name']} (id={team['id']})")
                    return team

            logger.warning(f"No team found: {team_name}")
            return None

    async def _get_season_averages(self, team_id: int) -> Optional[Dict[str, Any]]:
        """팀 시즌 평균 통계 조회"""
        session = await self._get_session()
        url = f"{self.BASE_URL}/season_averages"
        current_season = datetime.now().year

        params = {
            "season": current_season,
            "team_ids[]": team_id,
        }

        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.error(f"Season averages failed: {response.status}")
                return None

            data = await response.json()
            averages = data.get("data", [])

            if not averages:
                logger.warning(f"No season averages for team_id={team_id}")
                return None

            # 첫 번째 결과 반환 (팀 평균)
            return averages[0]

    def _convert_to_team_stats(
        self,
        team_name: str,
        league: str,
        stats_data: Dict[str, Any],
        is_home: bool
    ) -> TeamStats:
        """
        BallDontLie 응답 → TeamStats 변환

        농구 특화 공식:
        - 공격 레이팅: 득점 + FG% + 어시스트
        - 수비 레이팅: 리바운드 + 스틸 + 블록
        - 홈 어드밴티지: 2-3점 (축구보다 작음)
        """
        # 1. 기본 통계 추출
        try:
            avg_points_scored = float(stats_data.get("pts", 105.0))
            fg_pct = float(stats_data.get("fg_pct", 0.45))
            fg3_pct = float(stats_data.get("fg3_pct", 0.35))
            assists = float(stats_data.get("ast", 20.0))
            rebounds = float(stats_data.get("reb", 40.0))
            steals = float(stats_data.get("stl", 7.0))
            blocks = float(stats_data.get("blk", 4.0))
            turnovers = float(stats_data.get("turnover", 12.0))

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
                home_advantage=3.0 if is_home else 0.0,
                avg_points_scored=105.0,
                avg_points_conceded=105.0,
                last_updated=datetime.now(),
                source=self.provider_name,
            )

        # 2. 공격 레이팅 계산 (0-100)
        # NBA 평균: 112점, FG% 46%, 어시스트 24개

        # 득점력 (50점 만점): 105점 = 40점, 120점 = 50점
        scoring_rating = min(50, max(0, (avg_points_scored - 90) / 30 * 50))

        # 슈팅 효율성 (30점 만점): FG% 45% = 25점, FG% 50% = 30점
        shooting_rating = min(30, max(0, (fg_pct - 0.40) / 0.10 * 30))

        # 3점슛 능력 (10점 만점): 3P% 35% = 8점, 3P% 40% = 10점
        three_point_rating = min(10, max(0, (fg3_pct - 0.30) / 0.10 * 10))

        # 어시스트 능력 (10점 만점): 20개 = 7점, 28개 = 10점
        assist_rating = min(10, max(0, (assists - 15) / 13 * 10))

        attack_rating = scoring_rating + shooting_rating + three_point_rating + assist_rating

        # 3. 수비 레이팅 계산 (0-100)
        # NBA 평균: 리바운드 43개, 스틸 7.5개, 블록 4.5개

        # 리바운드 (50점 만점): 40개 = 40점, 48개 = 50점
        rebound_rating = min(50, max(0, (rebounds - 35) / 13 * 50))

        # 스틸 (30점 만점): 7개 = 25점, 9개 = 30점
        steal_rating = min(30, max(0, (steals - 5) / 4 * 30))

        # 블록 (20점 만점): 4개 = 15점, 6개 = 20점
        block_rating = min(20, max(0, (blocks - 2) / 4 * 20))

        defense_rating = rebound_rating + steal_rating + block_rating

        # 턴오버가 많으면 감점 (최대 -10점)
        # 12개 이하 = 0점 감점, 16개 이상 = -10점
        turnover_penalty = min(10, max(0, (turnovers - 12) / 4 * 10))
        defense_rating = max(0, defense_rating - turnover_penalty)

        # 4. 최근 폼 계산 (농구는 승률 기반)
        # BallDontLie API는 시즌 평균만 제공하므로 FG%로 폼 추정
        # FG% 높으면 좋은 폼으로 간주
        recent_form = min(100, max(0, (fg_pct - 0.40) / 0.10 * 100))

        # 5. 승률 (추정값)
        # 득점 - 실점 차이로 승률 추정 (농구는 실점 데이터 없음)
        # 득점 높으면 승률 높다고 가정
        if avg_points_scored >= 115:
            win_rate = 0.65
        elif avg_points_scored >= 110:
            win_rate = 0.55
        elif avg_points_scored >= 105:
            win_rate = 0.50
        elif avg_points_scored >= 100:
            win_rate = 0.40
        else:
            win_rate = 0.30

        # 6. 홈 어드밴티지 (농구는 축구보다 작음, 2-3점)
        home_advantage = 3.0 if is_home else 0.0

        # 7. 실점 추정 (API에 없으므로 리그 평균 사용)
        # 수비가 좋으면 실점 적다고 가정
        avg_points_conceded = 112.0 - (defense_rating - 50) * 0.2

        logger.debug(
            f"Converted {team_name}: "
            f"attack={attack_rating:.1f}, defense={defense_rating:.1f}, "
            f"form={recent_form:.1f}, pts={avg_points_scored:.1f}"
        )

        return TeamStats(
            team_name=team_name,
            league=league,
            attack_rating=round(attack_rating, 1),
            defense_rating=round(defense_rating, 1),
            recent_form=round(recent_form, 1),
            win_rate=round(win_rate, 3),
            home_advantage=round(home_advantage, 1),
            avg_points_scored=round(avg_points_scored, 1),
            avg_points_conceded=round(avg_points_conceded, 1),
            last_updated=datetime.now(),
            source=self.provider_name,
        )
