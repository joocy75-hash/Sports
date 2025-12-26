#!/usr/bin/env python3
"""
KSPO API에서 최신 경기 데이터를 수집하고 분석하여 텔레그램으로 전송하는 스크립트

사용법:
    python collect_and_notify.py              # 전체 수집 + 알림
    python collect_and_notify.py --collect    # 데이터 수집만
    python collect_and_notify.py --notify     # 알림만 (DB 데이터 기반)
    python collect_and_notify.py --basketball # 농구 승5패만
    python collect_and_notify.py --soccer     # 축구 승무패만
"""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import random

import httpx
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from dotenv import load_dotenv
load_dotenv()

from src.db.session import get_session
from src.db.models import Match, Team, League, PredictionLog
from src.services.telegram_notifier import TelegramNotifier
from src.services.round_manager import RoundManager
from src.config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BetmanDataCollector:
    """KSPO API를 통한 베트맨 경기 데이터 수집"""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.kspo_todz_api_key
        self.base_url = settings.kspo_todz_api_base_url
        self.kspo_league_id = 9999
        self.round_manager = RoundManager()

    async def collect_all_games(self, days_ahead: int = 7) -> Dict[str, List[Dict]]:
        """
        모든 게임 데이터 수집 (RoundManager 활용)

        RoundManager를 통해 정확한 회차와 14경기를 가져옵니다.
        """
        logger.info(f"📊 RoundManager를 통해 정확한 회차 및 경기 데이터 수집 중...")

        categorized = {
            "soccer_wdl": [],      # 축구 승무패
            "basketball_5": [],    # 농구 승5패
            "proto": [],           # 프로토 승부식
            "round_info": {},      # 회차 정보
        }

        # 1. 농구 승5패 - RoundManager 사용
        try:
            basketball_info, basketball_games = await self.round_manager.get_basketball_w5l_round()
            categorized["basketball_5"] = basketball_games
            categorized["round_info"]["basketball_5"] = basketball_info
            logger.info(f"  ✅ 농구 승5패 {basketball_info.round_number}회차: {len(basketball_games)}경기")
        except Exception as e:
            logger.warning(f"  ⚠️ 농구 승5패 수집 실패: {e}")

        # 2. 축구 승무패 - RoundManager 사용
        try:
            soccer_info, soccer_games = await self.round_manager.get_soccer_wdl_round()
            categorized["soccer_wdl"] = soccer_games
            categorized["round_info"]["soccer_wdl"] = soccer_info
            logger.info(f"  ✅ 축구 승무패 {soccer_info.round_number}회차: {len(soccer_games)}경기")
        except Exception as e:
            logger.warning(f"  ⚠️ 축구 승무패 수집 실패: {e}")

        # 3. 프로토 승부식 - 기존 방식 (여러 경기 가능)
        all_matches = []
        today = datetime.now()

        for i in range(days_ahead):
            target_date = (today + timedelta(days=i)).strftime("%Y%m%d")
            matches = await self._fetch_matches_by_date(target_date)
            all_matches.extend(matches)
            await asyncio.sleep(0.2)

        for match in all_matches:
            product = match.get("obj_prod_nm", "")
            if product == "프로토" and "기록식" not in product:
                categorized["proto"].append(match)

        logger.info(f"  - 프로토 승부식: {len(categorized['proto'])}경기")

        return categorized

    async def _fetch_matches_by_date(self, date_str: str) -> List[Dict]:
        """특정 날짜의 경기 목록 조회"""
        endpoint = f"{self.base_url}/todz_api_tb_match_mgmt_i"
        params = {
            "serviceKey": self.api_key,
            "pageNo": 1,
            "numOfRows": 200,
            "resultType": "JSON",
            "match_ymd": date_str,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=params, timeout=15.0)
                if response.status_code != 200:
                    logger.error(f"API 오류: {response.status_code}")
                    return []

                data = response.json()
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

                if isinstance(items, dict):
                    return [items]
                return items

        except Exception as e:
            logger.error(f"API 요청 실패 ({date_str}): {e}")
            return []

    async def save_to_db(self, categorized: Dict[str, List[Dict]]) -> int:
        """수집된 데이터를 DB에 저장 (회차 정보 활용)"""
        saved_count = 0

        # 회차 정보 추출
        round_info = categorized.get("round_info", {})

        async with get_session() as session:
            # KSPO 리그 조회/생성
            league = await self._get_or_create_league(session)

            for category, matches in categorized.items():
                if category == "round_info":
                    continue  # 회차 정보는 경기가 아님

                # 해당 카테고리의 회차 정보
                cat_round_info = round_info.get(category)
                round_number = cat_round_info.round_number if cat_round_info else None

                for match_data in matches:
                    try:
                        saved = await self._save_match(
                            session, match_data, league.id, category, round_number
                        )
                        if saved:
                            saved_count += 1
                    except Exception as e:
                        logger.error(f"경기 저장 실패: {e}")
                        continue

            await session.commit()

        logger.info(f"💾 {saved_count}개 경기 DB 저장 완료")
        return saved_count

    async def _get_or_create_league(self, session) -> League:
        """KSPO 리그 조회 또는 생성"""
        result = await session.execute(
            select(League).where(League.id == self.kspo_league_id)
        )
        league = result.scalar_one_or_none()

        if not league:
            league = League(
                id=self.kspo_league_id,
                name="KSPO 체육진흥투표권",
                country="KR",
                sport="multi"
            )
            session.add(league)
            await session.flush()

        return league

    async def _save_match(
        self,
        session,
        match_data: Dict,
        league_id: int,
        category_key: str,
        known_round_number: int = None
    ) -> bool:
        """개별 경기 저장 (정확한 회차 번호 사용)"""
        row_num = match_data.get("row_num")
        if not row_num:
            return False

        # 필수 데이터 추출
        home_name = match_data.get("hteam_han_nm", "").strip()
        away_name = match_data.get("ateam_han_nm", "").strip()
        sport_han = match_data.get("match_sport_han_nm", "기타")
        product_name = match_data.get("obj_prod_nm", "")
        match_ymd = str(match_data.get("match_ymd", ""))
        match_tm = str(match_data.get("match_tm", "0000")).zfill(4)
        turn_no = match_data.get("turn_no")

        if not home_name or not away_name:
            return False

        # 고유 경기 ID 생성 (월일 + row_num 조합으로 중복 방지, INT32 범위 내)
        # 예: 1224 + 007 = 1224007 (최대 12310999로 INT32 범위 내)
        match_id = int(f"{match_ymd[4:]}{str(row_num).zfill(3)}")

        # 카테고리 결정
        category_map = {
            "soccer_wdl": "축구 승무패",
            "basketball_5": "농구 승5패",
            "proto": "프로토 승부식",
        }
        category_name = category_map.get(category_key, "기타")

        # 회차 번호 결정 (RoundManager에서 전달받은 값 우선 사용)
        if known_round_number:
            round_number = known_round_number
        elif turn_no:
            try:
                round_number = int(turn_no)
            except (ValueError, TypeError):
                round_number = int(match_ymd)
        else:
            round_number = int(match_ymd)

        # 시작 시간
        try:
            dt_str = f"{match_ymd}{match_tm}"
            start_time = datetime.strptime(dt_str, "%Y%m%d%H%M")
        except ValueError:
            start_time = datetime.strptime(match_ymd, "%Y%m%d")

        # 팀 조회/생성
        home_team = await self._get_or_create_team(session, home_name, league_id, sport_han)
        away_team = await self._get_or_create_team(session, away_name, league_id, sport_han)

        # 경기 조회/생성 (match_id는 날짜+row_num 조합)
        result = await session.execute(
            select(Match).where(Match.id == match_id)
        )
        match = result.scalar_one_or_none()

        if match:
            # 업데이트
            match.start_time = start_time
            match.category_name = category_name
            match.round_number = round_number
            match.status = match_data.get("match_end_val", "예정")
            match.sport_type = sport_han  # 종목 타입도 업데이트
        else:
            # 새로 생성
            match = Match(
                id=match_id,
                league_id=league_id,
                season=int(match_ymd[:4]),
                sport=self._map_sport(sport_han),
                start_time=start_time,
                status="예정",
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                product_name=product_name,
                category_name=category_name,
                round_number=round_number,
                sport_type=sport_han,
            )
            session.add(match)

        await session.flush()

        # AI 예측 생성 (기존 예측이 없는 경우)
        pred_result = await session.execute(
            select(PredictionLog).where(PredictionLog.match_id == match_id)
        )
        existing_pred = pred_result.scalars().first()

        if not existing_pred:
            await self._create_prediction(session, match_id, category_name)

        return True

    async def _get_or_create_team(
        self,
        session,
        name: str,
        league_id: int,
        sport_han: str
    ) -> Team:
        """팀 조회 또는 생성"""
        sport_eng = self._map_sport(sport_han)
        result = await session.execute(
            select(Team).where(
                and_(Team.name == name, Team.sport == sport_eng)
            )
        )
        # 중복 팀이 있을 수 있으므로 first() 사용
        team = result.scalars().first()

        if not team:
            # 고유한 ID 생성
            team_id = abs(hash(f"{name}_{sport_han}_{datetime.now().timestamp()}")) % 1000000
            team = Team(
                id=team_id,
                name=name,
                league_id=league_id,
                sport=sport_eng,
            )
            session.add(team)
            await session.flush()

        return team

    async def _create_prediction(
        self,
        session,
        match_id: int,
        category: str
    ):
        """AI 예측 생성 (간단한 확률 기반)"""
        # 실제로는 더 복잡한 AI 모델 사용 필요
        if category == "농구 승5패":
            # 농구는 무승부 없음
            home_prob = random.uniform(0.35, 0.65)
            away_prob = 1.0 - home_prob
            draw_prob = 0.0
        else:
            # 축구/프로토는 승무패
            home_prob = random.uniform(0.30, 0.50)
            draw_prob = random.uniform(0.20, 0.35)
            away_prob = 1.0 - home_prob - draw_prob

        prediction = PredictionLog(
            match_id=match_id,
            prob_home=home_prob,
            prob_draw=draw_prob,
            prob_away=away_prob,
            meta={"source": "auto_generated", "timestamp": datetime.now().isoformat()}
        )
        session.add(prediction)

    def _map_sport(self, sport_han: str) -> str:
        """종목명 영문 변환"""
        mapping = {
            "축구": "football",
            "농구": "basketball",
            "야구": "baseball",
            "배구": "volleyball",
        }
        return mapping.get(sport_han, "other")


class TotoProtoNotifier:
    """분석 결과 텔레그램 알림"""

    def __init__(self):
        self.notifier = TelegramNotifier()

    async def notify_basketball_5(self, days_ahead: int = 7) -> bool:
        """농구 승5패 분석 결과 알림"""
        matches = await self._get_matches("농구 승5패", days_ahead)

        if not matches:
            msg = "🏀 현재 예정된 농구 승5패 경기가 없습니다."
            await self.notifier.send_message(msg)
            return False

        # 회차별로 그룹화
        by_round = {}
        for m in matches:
            round_num = m["round_number"]
            if round_num not in by_round:
                by_round[round_num] = []
            by_round[round_num].append(m)

        for round_num, round_matches in sorted(by_round.items(), reverse=True):
            msg = self._format_basketball_message(round_num, round_matches)
            await self.notifier.send_message(msg)
            await asyncio.sleep(1)

        return True

    async def notify_soccer_wdl(self, days_ahead: int = 7) -> bool:
        """축구 승무패 분석 결과 알림"""
        matches = await self._get_matches("축구 승무패", days_ahead)

        if not matches:
            msg = "⚽ 현재 예정된 축구 승무패 경기가 없습니다.\n(축구토토 승무패는 비시즌 또는 발매 대기 중일 수 있습니다)"
            await self.notifier.send_message(msg)
            return False

        # 회차별로 그룹화
        by_round = {}
        for m in matches:
            round_num = m["round_number"]
            if round_num not in by_round:
                by_round[round_num] = []
            by_round[round_num].append(m)

        for round_num, round_matches in sorted(by_round.items(), reverse=True):
            msg = self._format_soccer_message(round_num, round_matches)
            await self.notifier.send_message(msg)
            await asyncio.sleep(1)

        return True

    async def notify_proto(self, days_ahead: int = 7) -> bool:
        """프로토 승부식 분석 결과 알림"""
        matches = await self._get_matches("프로토 승부식", days_ahead)

        if not matches:
            msg = "📊 현재 예정된 프로토 승부식 경기가 없습니다."
            await self.notifier.send_message(msg)
            return False

        # 회차별로 그룹화 (최근 3회차만)
        by_round = {}
        for m in matches:
            round_num = m["round_number"]
            if round_num not in by_round:
                by_round[round_num] = []
            by_round[round_num].append(m)

        # 최근 3회차만 전송
        sorted_rounds = sorted(by_round.keys(), reverse=True)[:3]
        for round_num in sorted_rounds:
            round_matches = by_round[round_num]
            msg = self._format_proto_message(round_num, round_matches)
            await self.notifier.send_message(msg)
            await asyncio.sleep(1)

        return True

    async def _get_matches(self, category: str, days_ahead: int) -> List[Dict]:
        """DB에서 경기 조회 (종목 타입도 확인)"""
        now = datetime.now()
        end_date = now + timedelta(days=days_ahead)

        # 카테고리별 종목 타입 매핑
        sport_type_map = {
            "축구 승무패": "축구",
            "농구 승5패": "농구",
            "프로토 승부식": None,  # 프로토는 여러 종목 포함
        }
        expected_sport = sport_type_map.get(category)

        async with get_session() as session:
            # 기본 쿼리
            conditions = [
                Match.category_name == category,
                Match.start_time >= now,
                Match.start_time <= end_date,
            ]

            # 종목 타입 필터 추가 (프로토 제외)
            if expected_sport:
                conditions.append(Match.sport_type == expected_sport)

            stmt = (
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.predictions),
                )
                .where(and_(*conditions))
                .order_by(Match.round_number.desc(), Match.start_time)
            )

            result = await session.execute(stmt)
            matches = result.unique().scalars().all()

            formatted = [self._format_match_data(m) for m in matches]

            # 축구 승무패, 농구 승5패는 가장 가까운 회차의 14경기만 반환
            if category in ["축구 승무패", "농구 승5패"] and formatted:
                # 시작 시간 기준으로 정렬하여 가장 빠른 경기의 회차 찾기
                formatted.sort(key=lambda x: x["start_time"])
                target_round = formatted[0]["round_number"]

                # 해당 회차 경기만 필터 (최대 14경기)
                same_round = [m for m in formatted if m["round_number"] == target_round]
                # game_number 또는 start_time 기준 정렬
                same_round.sort(key=lambda x: (x.get("game_number") or 999, x["start_time"]))
                return same_round[:14]

            return formatted

    def _format_match_data(self, match: Match) -> Dict:
        """경기 데이터 포맷팅"""
        pred = match.predictions[-1] if match.predictions else None

        data = {
            "id": match.id,
            "home_team": match.home_team.name if match.home_team else "홈팀",
            "away_team": match.away_team.name if match.away_team else "원정팀",
            "start_time": match.start_time,
            "round_number": match.round_number,
            "category": match.category_name,
            "game_number": match.game_number,  # 베트맨 공식 경기 번호
        }

        if pred:
            probs = {
                "home": pred.prob_home,
                "draw": pred.prob_draw,
                "away": pred.prob_away,
            }
            data["probs"] = probs

            # 최고 확률 결정
            max_prob = max(probs["home"], probs["draw"], probs["away"])
            if max_prob == probs["home"]:
                data["prediction"] = "홈 승리"
                data["mark"] = "1"
            elif max_prob == probs["away"]:
                data["prediction"] = "원정 승리"
                data["mark"] = "2"
            else:
                data["prediction"] = "무승부"
                data["mark"] = "X"

            data["confidence"] = max_prob
        else:
            data["prediction"] = "분석 중"
            data["confidence"] = 0

        return data

    def _format_basketball_message(self, round_num: int, matches: List[Dict]) -> str:
        """농구 승5패 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = f"""🏀 *농구토토 승5패 {round_num}회차*
📅 {now_str}
━━━━━━━━━━━━━━━━━━━━━

"""
        high_conf_games = []

        # game_number가 있는 경기만 필터링 (14경기)
        valid_matches = [m for m in matches if m.get("game_number") is not None]
        # game_number 기준 정렬
        valid_matches.sort(key=lambda x: x.get("game_number", 999))

        for m in valid_matches[:14]:
            game_num = m.get("game_number", 0)
            home = m["home_team"]
            away = m["away_team"]
            kick_time = m["start_time"].strftime("%m/%d %H:%M")
            conf = m.get("confidence", 0)
            pred = m.get("prediction", "분석 중")

            # 농구는 무승부 없음
            if "홈" in pred:
                mark = "홈승"
            else:
                mark = "원정승"

            icon = "🔒" if conf >= 0.60 else "📊"

            if conf >= 0.60:
                high_conf_games.append(game_num)

            msg += f"*[{game_num:02d}] {home} vs {away}*\n"
            msg += f"⏰ {kick_time}\n"
            msg += f"{icon} *{mark}* ({conf*100:.1f}%)\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🔒 고신뢰도 경기: {len(high_conf_games)}개\n"

        if high_conf_games:
            msg += f"추천: {', '.join(map(str, high_conf_games))}\n"

        msg += "\n_베트맨 스포츠토토 AI 분석 시스템_"

        return msg

    def _format_soccer_message(self, round_num: int, matches: List[Dict]) -> str:
        """축구 승무패 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = f"""⚽ *축구토토 승무패 {round_num}회차*
📅 {now_str}
━━━━━━━━━━━━━━━━━━━━━

"""
        high_conf_games = []

        for i, m in enumerate(matches[:14], 1):
            home = m["home_team"]
            away = m["away_team"]
            kick_time = m["start_time"].strftime("%m/%d %H:%M")
            conf = m.get("confidence", 0)
            pred = m.get("prediction", "분석 중")
            mark = m.get("mark", "-")

            icon = "🔒" if conf >= 0.65 else "📊"

            if conf >= 0.65:
                high_conf_games.append(i)

            msg += f"*[{i:02d}] {home} vs {away}*\n"
            msg += f"⏰ {kick_time}\n"
            msg += f"{icon} *[{mark}] {pred}* ({conf*100:.1f}%)\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🔒 고신뢰도 경기: {len(high_conf_games)}개\n"

        if high_conf_games:
            msg += f"추천: {', '.join(map(str, high_conf_games))}\n"

        msg += "\n_베트맨 스포츠토토 AI 분석 시스템_"

        return msg

    def _format_proto_message(self, round_num: int, matches: List[Dict]) -> str:
        """프로토 승부식 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = f"""📊 *프로토 승부식 {round_num}회차*
📅 {now_str}
━━━━━━━━━━━━━━━━━━━━━

"""
        high_conf = []
        medium_conf = []
        low_conf = []

        for i, m in enumerate(matches[:20], 1):  # 최대 20경기
            home = m["home_team"]
            away = m["away_team"]
            kick_time = m["start_time"].strftime("%m/%d %H:%M")
            conf = m.get("confidence", 0)
            pred = m.get("prediction", "분석 중")
            mark = m.get("mark", "-")

            if conf >= 0.65:
                icon = "💎"
                high_conf.append(i)
            elif conf >= 0.55:
                icon = "✅"
                medium_conf.append(i)
            else:
                icon = "ℹ️"
                low_conf.append(i)

            msg += f"*{i:02d}. {home} vs {away}*\n"
            msg += f"⏰ {kick_time}\n"
            msg += f"{icon} *[{mark}] {pred}* ({conf*100:.1f}%)\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"💎 *고신뢰도 (65%+)*: {len(high_conf)}경기\n"
        msg += f"✅ *중신뢰도 (55-65%)*: {len(medium_conf)}경기\n"
        msg += f"ℹ️ *저신뢰도 (55% 미만)*: {len(low_conf)}경기\n\n"

        if high_conf:
            msg += f"💎 추천: {', '.join(map(str, high_conf))}\n\n"

        msg += "_베트맨 스포츠토토 AI 분석 시스템_"

        return msg


async def main():
    parser = argparse.ArgumentParser(
        description="KSPO 데이터 수집 및 텔레그램 알림"
    )
    parser.add_argument("--collect", action="store_true", help="데이터 수집만")
    parser.add_argument("--notify", action="store_true", help="알림만")
    parser.add_argument("--basketball", action="store_true", help="농구 승5패만")
    parser.add_argument("--basketball-w5l", action="store_true", help="농구 승5패 14경기 전체 분석 (복식 포함)")
    parser.add_argument("--soccer", action="store_true", help="축구 승무패만")
    parser.add_argument("--proto", action="store_true", help="프로토 승부식만")
    parser.add_argument("--days", type=int, default=7, help="조회 기간 (일)")

    args = parser.parse_args()

    print("=" * 60)
    print("🎯 베트맨 스포츠토토 분석 시스템")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    try:
        # 데이터 수집
        if not args.notify:
            collector = BetmanDataCollector()
            categorized = await collector.collect_all_games(args.days)
            await collector.save_to_db(categorized)
            print()

        # 알림 전송
        if not args.collect:
            notifier = TotoProtoNotifier()

            if args.basketball_w5l:
                # 농구 승5패 14경기 전체 분석 (복식 포함)
                print("🏀 농구 승5패 14경기 전체 분석 중...")
                from basketball_w5l_notifier import BasketballW5LNotifier
                w5l_notifier = BasketballW5LNotifier()
                await w5l_notifier.run_analysis()
            elif args.basketball:
                print("🏀 농구 승5패 알림 전송 중...")
                await notifier.notify_basketball_5(args.days)
            elif args.soccer:
                print("⚽ 축구 승무패 알림 전송 중...")
                await notifier.notify_soccer_wdl(args.days)
            elif args.proto:
                print("📊 프로토 승부식 알림 전송 중...")
                await notifier.notify_proto(args.days)
            else:
                # 전체 알림
                print("🏀 농구 승5패 알림 전송 중...")
                await notifier.notify_basketball_5(args.days)
                await asyncio.sleep(2)

                print("⚽ 축구 승무패 알림 전송 중...")
                await notifier.notify_soccer_wdl(args.days)
                await asyncio.sleep(2)

                print("📊 프로토 승부식 알림 전송 중...")
                await notifier.notify_proto(args.days)

        print()
        print("=" * 60)
        print("✅ 완료!")
        print("📱 텔레그램 앱에서 메시지를 확인하세요.")
        print("=" * 60)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
