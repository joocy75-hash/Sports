import httpx
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Match, Team, League
from src.db.session import get_session
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


# ========== Common Helper Functions ==========


async def get_or_create_team(
    session: AsyncSession, team_name: str, league_id: int
) -> Team:
    """
    한글 팀명으로 Team 레코드 조회 또는 생성
    """
    result = await session.execute(select(Team).where(Team.name == team_name))
    team = result.scalar_one_or_none()

    if team:
        return team

    team = Team(
        id=hash(team_name) % 1000000,  # 임시 ID (한글명 해시)
        name=team_name,
        league_id=league_id,
        sport="football",
    )
    session.add(team)
    await session.flush()
    return team


async def get_or_create_kspo_league(session: AsyncSession) -> League:
    """
    KSPO 전용 리그 레코드 조회 또는 생성
    """
    KSPO_LEAGUE_ID = 9999  # KSPO 전용 리그 ID

    result = await session.execute(select(League).where(League.id == KSPO_LEAGUE_ID))
    league = result.scalar_one_or_none()

    if league:
        return league

    league = League(
        id=KSPO_LEAGUE_ID,
        name="KSPO 체육진흥투표권",
        country="KR",
        sport="football",
    )
    session.add(league)
    await session.flush()
    return league


# ========== API Clients ==========


class KSPOApiClient:
    """
    국민체육진흥공단(KSPO) 체육진흥투표권 발매대상 경기정보 API 클라이언트
    TODZ_API 사용 (기존)
    """

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.kspo_todz_api_key
        self.base_url = settings.kspo_todz_api_base_url

        if not self.api_key or not self.base_url:
            logger.warning("KSPO TODZ API Key or Base URL is missing.")

    async def get_match_list(
        self, match_ymd: str = None, page_no: int = 1, num_of_rows: int = 100
    ) -> List[Dict]:
        """
        경기 목록 조회
        :param match_ymd: 경기일자 (YYYYMMDD) - 없으면 오늘 날짜
        :return: 경기 목록 리스트
        """
        if not match_ymd:
            match_ymd = datetime.now().strftime("%Y%m%d")

        endpoint = f"{self.base_url}/todz_api_tb_match_mgmt_i"

        params = {
            "serviceKey": self.api_key,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "resultType": "JSON",
            "match_ymd": match_ymd,
        }
        # match_end_val 필드가 경기 결과를 나타냄 (승/무/패/취소 등)

        try:
            async with httpx.AsyncClient() as client:
                # serviceKey는 이미 인코딩된 상태이므로 params에 넣으면 이중 인코딩 될 수 있음.
                # 따라서 URL에 직접 붙이거나, httpx가 인코딩하지 않도록 주의해야 함.
                # 여기서는 safe chars로 처리하거나, 직접 URL 구성

                # 공공데이터포털 키는 종종 디코딩이 필요할 수도 있고 인코딩된 걸 그대로 써야할 수도 있음.
                # 제공받은 키가 인코딩된 키라면 그대로 사용.

                response = await client.get(endpoint, params=params, timeout=10.0)

                if response.status_code != 200:
                    logger.error(
                        f"KSPO API Error: {response.status_code} - {response.text}"
                    )
                    return []

                data = response.json()

                # 응답 구조 파싱 (JSON 기준)
                # response -> body -> items -> item
                items = (
                    data.get("response", {})
                    .get("body", {})
                    .get("items", {})
                    .get("item", [])
                )

                if isinstance(items, dict):
                    return [items]
                return items

        except Exception as e:
            logger.error(f"Failed to fetch KSPO match list: {e}")
            # JSON 파싱 실패 시 XML로 재시도 로직 등을 추가할 수 있음
            return []

    async def get_toto_matches(self) -> List[Dict]:
        """
        승무패(축구토토) 대상 경기만 필터링하여 가져오기
        """
        # 최근 3일치 데이터를 가져와서 '승무패' 상품 찾기
        # API에 상품명 필터가 없으므로 가져온 후 필터링

        all_matches = []
        today = datetime.now()

        # 오늘부터 3일 뒤까지 조회
        for i in range(3):
            target_date = (today + timedelta(days=i)).strftime("%Y%m%d")
            matches = await self.get_match_list(match_ymd=target_date)
            all_matches.extend(matches)

        # 필터링: obj_prod_nm (대상상품명)에 '승무패'가 포함된 것
        toto_matches = [
            m
            for m in all_matches
            if "승무패" in m.get("obj_prod_nm", "")
            or "축구토토" in m.get("obj_prod_nm", "")
        ]

        return toto_matches

    async def get_proto_matches(self) -> List[Dict]:
        """
        프로토(승부식) 대상 경기만 필터링하여 가져오기
        """
        all_matches = []
        today = datetime.now()

        # 오늘부터 3일 뒤까지 조회
        for i in range(4):
            target_date = (today + timedelta(days=i)).strftime("%Y%m%d")
            matches = await self.get_match_list(match_ymd=target_date)
            all_matches.extend(matches)

        # 필터링: obj_prod_nm에 '프로토'가 포함된 것
        proto_matches = [m for m in all_matches if "프로토" in m.get("obj_prod_nm", "")]

        # 중복 제거 (row_num 기준)
        seen = set()
        unique_matches = []
        for m in proto_matches:
            if m["row_num"] not in seen:
                seen.add(m["row_num"])
                unique_matches.append(m)

        return unique_matches

    async def save_matches_to_db(self, matches_data: List[Dict]) -> int:
        """
        KSPO API에서 가져온 경기 데이터를 DB에 저장 (전 종목 지원)
        """
        saved_count = 0
        async with get_session() as session:
            # KSPO 전용 리그 생성 (또는 조회)
            league = await get_or_create_kspo_league(session)

            for match_data in matches_data:
                try:
                    # 1. 필수 필드 추출
                    row_num = match_data.get("row_num")
                    if not row_num:
                        continue

                    match_ymd = str(match_data.get("match_ymd", ""))
                    match_tm = str(match_data.get("match_tm", "0000"))
                    hteam_name = match_data.get("hteam_han_nm")
                    ateam_name = match_data.get("ateam_han_nm")
                    sport_type = match_data.get("match_sport_han_nm", "기타")
                    product_name = match_data.get("obj_prod_nm", "")
                    turn_no = match_data.get("turn_no")

                    if not all([match_ymd, hteam_name, ateam_name]):
                        continue

                    # 2. 카테고리 및 회차 정규화 (베트맨 스타일)
                    category_name, round_number = self._normalize_category_and_round(
                        product_name, sport_type, turn_no, match_ymd
                    )

                    if category_name is None or round_number is None:
                        continue

                    # 3. 날짜/시간 결합
                    try:
                        dt_str = f"{match_ymd}{match_tm.zfill(4)}"
                        start_time = datetime.strptime(dt_str, "%Y%m%d%H%M")
                    except ValueError:
                        start_time = datetime.strptime(match_ymd, "%Y%m%d")

                    # 4. 팀 생성/조회 (종목 정보 포함)
                    home_team = await self._get_or_create_team_with_sport(
                        session, hteam_name, league.id, sport_type
                    )
                    away_team = await self._get_or_create_team_with_sport(
                        session, ateam_name, league.id, sport_type
                    )

                    # 5. DB Upsert
                    result = await session.execute(
                        select(Match).where(Match.id == int(row_num))
                    )
                    match = result.scalar_one_or_none()

                    status = match_data.get("match_end_val", "예정")
                    score_h = match_data.get("home_score")
                    score_a = match_data.get("away_score")

                    if match:
                        match.status = status
                        match.score_home = score_h
                        match.score_away = score_a
                        match.category_name = category_name
                        match.round_number = round_number
                        match.start_time = start_time
                    else:
                        match = Match(
                            id=int(row_num),
                            league_id=league.id,
                            season=int(match_ymd[:4]),
                            sport=self._map_sport_to_eng(sport_type),
                            start_time=start_time,
                            status=status,
                            home_team_id=home_team.id,
                            away_team_id=away_team.id,
                            score_home=score_h,
                            score_away=score_a,
                            product_name=product_name,
                            category_name=category_name,
                            round_number=round_number,
                            sport_type=sport_type,
                        )
                        session.add(match)

                    saved_count += 1

                except Exception as e:
                    logger.error(
                        f"KSPO 경기 저장 중 오류 (row_num={match_data.get('row_num')}): {e}"
                    )
                    continue

            await session.commit()
        return saved_count

    def _normalize_category_and_round(self, product, sport, turn, ymd):
        """베트맨 스타일 카테고리명 및 회차 번호 정규화"""
        product = product or ""
        sport = sport or ""

        # 카테고리 결정
        if "승무패" in product or (
            "토토" in product and sport == "축구" and "프로토" not in product
        ):
            category = "축구 승무패"
        elif "승5패" in product or (
            "토토" in product and sport == "농구" and "프로토" not in product
        ):
            category = "농구 승5패"
        elif "승1패" in product or (
            "토토" in product and sport == "야구" and "프로토" not in product
        ):
            return None, None
        elif "언더오버" in product:
            return None, None
        elif "기록식" in product:
            if "프로토" in product:
                category = "프로토 기록식"
            else:
                return None, None
        elif "프로토" in product:
            if "기록식" in product:
                category = "프로토 기록식"
            else:
                # '프로토' 또는 '토토/프로토'로 들어오는 경우 대부분 승부식임
                category = "프로토 승부식"
        else:
            category = f"{product} {sport}".strip() or "기타"

        # 회차 번호 결정 (turn_no가 있으면 사용, 없으면 날짜 기반)
        try:
            round_no = int(turn) if turn else int(ymd)
        except (ValueError, TypeError):
            round_no = int(ymd)

        return category, round_no

    def _map_sport_to_eng(self, sport_han):
        mapping = {
            "축구": "football",
            "농구": "basketball",
            "야구": "baseball",
            "배구": "volleyball",
            "골프": "golf",
        }
        return mapping.get(sport_han, "other")

    async def _get_or_create_team_with_sport(self, session, name, league_id, sport_han):
        result = await session.execute(
            select(Team)
            .where(Team.name == name)
            .where(Team.sport == self._map_sport_to_eng(sport_han))
        )
        team = result.scalar_one_or_none()
        if team:
            return team

        team = Team(
            id=hash(f"{name}_{sport_han}") % 1000000,
            name=name,
            league_id=league_id,
            sport=self._map_sport_to_eng(sport_han),
        )
        session.add(team)
        await session.flush()
        return team
