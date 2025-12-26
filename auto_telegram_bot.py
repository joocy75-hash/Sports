#!/usr/bin/env python3
"""
프로토 14경기 텔레그램 봇 시스템

기능:
1. 인라인 버튼으로 승무패/승5패 분석 요청
2. 5개 AI 앙상블 분석 (GPT, Claude, Gemini, DeepSeek, Kimi)
3. 정확한 14경기 수집 (베트맨 크롤러)
4. 텔레그램 알림 전송
5. 스케줄러로 주기적 자동 분석

사용법:
    python auto_telegram_bot.py          # 봇 시작 (버튼 대기)
    python auto_telegram_bot.py --once   # 한번 실행하고 종료
"""

import os
import sys
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import aiohttp
from dotenv import load_dotenv

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# AutoSportsNotifier 임포트 (5개 AI 앙상블 분석)
try:
    from auto_sports_notifier import AutoSportsNotifier
    AI_NOTIFIER_AVAILABLE = True
except ImportError as e:
    AI_NOTIFIER_AVAILABLE = False
    logging.warning(f"AutoSportsNotifier 사용 불가: {e}")

# RoundManager 임포트 (정확한 14경기 수집)
try:
    from src.services.round_manager import RoundManager
    ROUND_MANAGER_AVAILABLE = True
except ImportError:
    ROUND_MANAGER_AVAILABLE = False
    logging.warning("RoundManager 사용 불가 - 캐시 또는 KSPO API 사용")

# 캐시 파일 경로 (베트맨 크롤러에서 생성한 14경기 캐시)
from pathlib import Path
CACHE_DIR = Path(__file__).parent / ".state"
SOCCER_CACHE_FILE = CACHE_DIR / "betman_soccer_wdl.json"
BASKETBALL_CACHE_FILE = CACHE_DIR / "betman_basketball_w5l.json"

# DB 연결 (옵션)
try:
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    DATABASE_URL = os.getenv('DATABASE_URL', '').replace('postgresql://', 'postgresql+asyncpg://')
    if DATABASE_URL:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        DB_AVAILABLE = True
    else:
        DB_AVAILABLE = False
except ImportError:
    DB_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
KSPO_API_KEY = os.getenv('KSPO_TODZ_API_KEY')
KSPO_BASE_URL = os.getenv('KSPO_TODZ_API_BASE_URL', 'https://apis.data.go.kr/B551015')


class TelegramBotHandler:
    """텔레그램 봇 핸들러 (인라인 버튼 지원)"""

    def __init__(self):
        self.bot_token = BOT_TOKEN
        self.chat_id = CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.last_update_id = 0

    async def send_message(
        self,
        text: str,
        chat_id: str = None,
        parse_mode: str = 'HTML',
        reply_markup: dict = None
    ) -> bool:
        """메시지 전송"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                'chat_id': chat_id or self.chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            if reply_markup:
                payload['reply_markup'] = json.dumps(reply_markup)

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"메시지 전송 실패: {error}")
                        return False
        except Exception as e:
            logger.error(f"메시지 전송 오류: {e}")
            return False

    async def send_long_message(self, text: str, chat_id: str = None) -> bool:
        """긴 메시지 분할 전송"""
        max_length = 4000
        if len(text) <= max_length:
            return await self.send_message(text, chat_id=chat_id)

        parts = []
        current = ""
        for line in text.split('\n'):
            if len(current) + len(line) + 1 <= max_length:
                current += line + '\n'
            else:
                if current:
                    parts.append(current)
                current = line + '\n'
        if current:
            parts.append(current)

        for part in parts:
            await self.send_message(part, chat_id=chat_id)
            await asyncio.sleep(0.5)
        return True

    async def answer_callback_query(self, callback_query_id: str, text: str = None) -> bool:
        """콜백 쿼리 응답"""
        try:
            url = f"{self.api_url}/answerCallbackQuery"
            payload = {'callback_query_id': callback_query_id}
            if text:
                payload['text'] = text

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"콜백 응답 오류: {e}")
            return False

    async def get_updates(self, timeout: int = 30) -> List[Dict]:
        """업데이트 가져오기 (Long polling)"""
        try:
            url = f"{self.api_url}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': timeout,
                'allowed_updates': ['message', 'callback_query']
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout+10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('ok') and data.get('result'):
                            updates = data['result']
                            if updates:
                                self.last_update_id = updates[-1]['update_id']
                            return updates
                    return []
        except asyncio.TimeoutError:
            return []
        except Exception as e:
            logger.error(f"업데이트 가져오기 오류: {e}")
            return []

    def get_main_menu_keyboard(self) -> dict:
        """메인 메뉴 인라인 키보드"""
        return {
            'inline_keyboard': [
                [
                    {'text': '⚽ 축구 승무패 분석', 'callback_data': 'analyze_soccer'},
                    {'text': '🏀 농구 승5패 분석', 'callback_data': 'analyze_basketball'}
                ],
                [
                    {'text': '🔄 최신 회차 업데이트', 'callback_data': 'update_rounds'}
                ],
                [
                    {'text': '📊 전체 자동 분석', 'callback_data': 'analyze_all'}
                ]
            ]
        }

    async def send_main_menu(self, chat_id: str = None):
        """메인 메뉴 전송"""
        text = (
            "🎯 <b>스포츠 분석 봇</b>\n\n"
            "원하는 분석을 선택하세요:\n\n"
            f"🕐 현재 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        await self.send_message(
            text,
            chat_id=chat_id,
            reply_markup=self.get_main_menu_keyboard()
        )


class KSPODataCollector:
    """KSPO API 데이터 수집기"""

    def __init__(self):
        self.api_key = KSPO_API_KEY
        self.base_url = KSPO_BASE_URL

    async def fetch_matches(self, date: str = None, num_of_rows: int = 200) -> List[Dict]:
        """경기 데이터 수집"""
        if not date:
            date = datetime.now().strftime('%Y%m%d')

        url = f"{self.base_url}/todz_api_tb_match_mgmt_i"
        params = {
            'serviceKey': self.api_key,
            'pageNo': 1,
            'numOfRows': num_of_rows,
            'resultType': 'JSON',
            'match_ymd': date
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as resp:
                    if resp.status == 200:
                        # KSPO API는 text/json으로 응답하므로 content_type=None 필요
                        data = await resp.json(content_type=None)
                        items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                        if isinstance(items, dict):
                            return [items]
                        return items if items else []
                    else:
                        logger.error(f"KSPO API 오류: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"KSPO 데이터 수집 오류: {e}")
            return []

    async def fetch_from_db(self, sport_type: str = None) -> List[Dict]:
        """DB에서 경기 데이터 조회 (KSPO API 폴백)"""
        if not DB_AVAILABLE:
            return []

        try:
            async with async_session() as session:
                # 오늘 이후 경기 조회
                today = datetime.now().strftime('%Y-%m-%d')

                if sport_type:
                    query = text("""
                        SELECT id, home_team_id, away_team_id, start_time, status,
                               odds_home, odds_draw, odds_away, round_number,
                               category_name, sport_type, game_number
                        FROM matches
                        WHERE sport_type = :sport_type
                        AND start_time >= :today
                        ORDER BY round_number DESC, game_number ASC
                        LIMIT 100
                    """)
                    result = await session.execute(query, {'sport_type': sport_type, 'today': today})
                else:
                    query = text("""
                        SELECT id, home_team_id, away_team_id, start_time, status,
                               odds_home, odds_draw, odds_away, round_number,
                               category_name, sport_type, game_number
                        FROM matches
                        WHERE start_time >= :today
                        ORDER BY sport_type, round_number DESC, game_number ASC
                        LIMIT 200
                    """)
                    result = await session.execute(query, {'today': today})

                rows = result.fetchall()
                matches = []
                for row in rows:
                    matches.append({
                        'id': row[0],
                        'home_team_nm': str(row[1]),
                        'away_team_nm': str(row[2]),
                        'match_dt': row[3].strftime('%Y-%m-%d %H:%M') if row[3] else '',
                        'status': row[4],
                        'win_rt': float(row[5]) if row[5] else 2.0,
                        'draw_rt': float(row[6]) if row[6] else 3.5,
                        'lose_rt': float(row[7]) if row[7] else 2.5,
                        'pd_round': str(row[8]) if row[8] else 'unknown',
                        'obj_prod_nm': row[9] or '',
                        'sports_div_nm': row[10] or '',
                        'game_sno': row[11] or 0
                    })
                return matches
        except Exception as e:
            logger.error(f"DB 조회 오류: {e}")
            return []

    async def fetch_all_upcoming_matches(self, days: int = 4) -> Dict[str, List[Dict]]:
        """
        정확한 14경기 수집 (RoundManager 우선 사용)

        Returns:
            {
                'soccer': {회차번호: [14경기]},
                'basketball': {회차번호: [14경기]},
            }
        """
        result = {'soccer': {}, 'basketball': {}}

        # 1. RoundManager 사용 (정확한 14경기 보장)
        if ROUND_MANAGER_AVAILABLE:
            try:
                manager = RoundManager()

                # 축구 승무패
                try:
                    soccer_info, soccer_games = await manager.get_soccer_wdl_round()
                    if soccer_info and soccer_games:
                        round_num = str(soccer_info.round_number)
                        # RoundManager는 Dict 리스트 반환
                        soccer_matches = []
                        for g in soccer_games:
                            soccer_matches.append({
                                'game_sno': g.get('row_num', 0),
                                'hteam_han_nm': g.get('hteam_han_nm', ''),
                                'ateam_han_nm': g.get('ateam_han_nm', ''),
                                'match_ymd': g.get('match_ymd', ''),
                                'match_time': g.get('match_tm', ''),
                                'match_sport_han_nm': '축구',
                                'pd_round': round_num,
                            })
                        result['soccer'][round_num] = soccer_matches
                        logger.info(f"축구 승무패 {round_num}회차: {len(soccer_matches)}경기 (RoundManager)")
                except Exception as e:
                    logger.error(f"축구 RoundManager 오류: {e}")

                # 농구 승5패
                try:
                    bball_info, bball_games = await manager.get_basketball_w5l_round()
                    if bball_info and bball_games:
                        round_num = str(bball_info.round_number)
                        bball_matches = []
                        for g in bball_games:
                            bball_matches.append({
                                'game_sno': g.get('row_num', 0),
                                'hteam_han_nm': g.get('hteam_han_nm', ''),
                                'ateam_han_nm': g.get('ateam_han_nm', ''),
                                'match_ymd': g.get('match_ymd', ''),
                                'match_time': g.get('match_tm', ''),
                                'match_sport_han_nm': '농구',
                                'pd_round': round_num,
                            })
                        result['basketball'][round_num] = bball_matches
                        logger.info(f"농구 승5패 {round_num}회차: {len(bball_matches)}경기 (RoundManager)")
                except Exception as e:
                    logger.error(f"농구 RoundManager 오류: {e}")

                # 데이터가 있으면 반환
                if result['soccer'] or result['basketball']:
                    return result

            except Exception as e:
                logger.error(f"RoundManager 전체 오류: {e}")

        # 2. Fallback: 캐시 파일에서 14경기 읽기
        result = self._load_from_cache()
        if result['soccer'] or result['basketball']:
            logger.info("캐시 파일에서 14경기 로드 성공")
            return result

        # 3. Fallback: KSPO API 직접 사용 (기존 로직)
        logger.warning("캐시 없음, KSPO API 직접 사용 (14경기 보장 안됨)")
        all_matches = []
        today = datetime.now()

        for i in range(days):
            date = (today + timedelta(days=i)).strftime('%Y%m%d')
            matches = await self.fetch_matches(date)
            all_matches.extend(matches)
            logger.info(f"{date}: {len(matches)}경기 수집 (API)")

        if len(all_matches) == 0 and DB_AVAILABLE:
            logger.info("KSPO API 데이터 없음, DB에서 조회 중...")
            all_matches = await self.fetch_from_db()
            logger.info(f"DB에서 {len(all_matches)}경기 조회됨")

        soccer_matches = []
        basketball_matches = []

        for match in all_matches:
            product_name = match.get('obj_prod_nm', '')
            sport_type = match.get('match_sport_han_nm', '') or match.get('sports_div_nm', '')

            if '축구' in sport_type or '승무패' in product_name:
                soccer_matches.append(match)
            elif '농구' in sport_type or '농구' in product_name:
                basketball_matches.append(match)

        return {
            'soccer': self._group_by_round(soccer_matches),
            'basketball': self._group_by_round(basketball_matches)
        }

    def _group_by_round(self, matches: List[Dict]) -> Dict[str, List[Dict]]:
        """회차별 그룹화"""
        rounds = {}
        for match in matches:
            round_num = match.get('pd_round', 'unknown')
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append(match)
        return rounds

    def _load_from_cache(self) -> Dict[str, Dict[str, List[Dict]]]:
        """
        베트맨 크롤러 캐시 파일에서 14경기 로드

        캐시 파일 형식:
        {
            "round_info": {"round_number": 152, ...},
            "games": [{"game_number": 1, "home_team": "레스터C", ...}, ...]
        }
        """
        result = {'soccer': {}, 'basketball': {}}

        # 축구 캐시 로드
        if SOCCER_CACHE_FILE.exists():
            try:
                with open(SOCCER_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    round_info = data.get('round_info', {})
                    games = data.get('games', [])
                    round_num = str(round_info.get('round_number', 'unknown'))

                    soccer_matches = []
                    for g in games:
                        soccer_matches.append({
                            'game_sno': g.get('game_number', 0),
                            'hteam_han_nm': g.get('home_team', ''),
                            'ateam_han_nm': g.get('away_team', ''),
                            'match_ymd': g.get('match_date', ''),
                            'match_time': g.get('match_time', ''),
                            'match_sport_han_nm': '축구',
                            'pd_round': round_num,
                        })

                    if soccer_matches:
                        result['soccer'][round_num] = soccer_matches
                        logger.info(f"[캐시] 축구 승무패 {round_num}회차: {len(soccer_matches)}경기")
            except Exception as e:
                logger.error(f"축구 캐시 로드 오류: {e}")

        # 농구 캐시 로드
        if BASKETBALL_CACHE_FILE.exists():
            try:
                with open(BASKETBALL_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    round_info = data.get('round_info', {})
                    games = data.get('games', [])
                    round_num = str(round_info.get('round_number', 'unknown'))

                    bball_matches = []
                    for g in games:
                        bball_matches.append({
                            'game_sno': g.get('game_number', 0),
                            'hteam_han_nm': g.get('home_team', ''),
                            'ateam_han_nm': g.get('away_team', ''),
                            'match_ymd': g.get('match_date', ''),
                            'match_time': g.get('match_time', ''),
                            'match_sport_han_nm': '농구',
                            'pd_round': round_num,
                        })

                    if bball_matches:
                        result['basketball'][round_num] = bball_matches
                        logger.info(f"[캐시] 농구 승5패 {round_num}회차: {len(bball_matches)}경기")
            except Exception as e:
                logger.error(f"농구 캐시 로드 오류: {e}")

        return result


class MatchAnalyzer:
    """경기 AI 분석기"""

    def __init__(self):
        # 간단한 분석 로직 (실제 AI 모델 대신)
        pass

    def analyze_soccer_match(self, match: Dict) -> Dict:
        """축구 경기 분석 (승무패)"""
        # KSPO API 필드: hteam_han_nm / ateam_han_nm (또는 DB: home_team_nm)
        home_team = match.get('hteam_han_nm', '') or match.get('home_team_nm', '홈')
        away_team = match.get('ateam_han_nm', '') or match.get('away_team_nm', '원정')

        # 배당률 기반 확률 계산 (실제로는 더 복잡한 모델 사용)
        home_odds = float(match.get('win_rt', 0) or 2.0)
        draw_odds = float(match.get('draw_rt', 0) or 3.5)
        away_odds = float(match.get('lose_rt', 0) or 3.0)

        # 배당률 → 확률 변환 (마진 제거 전)
        total = (1/home_odds) + (1/draw_odds) + (1/away_odds)
        home_prob = round((1/home_odds) / total * 100, 1) if home_odds > 0 else 33.3
        draw_prob = round((1/draw_odds) / total * 100, 1) if draw_odds > 0 else 33.3
        away_prob = round((1/away_odds) / total * 100, 1) if away_odds > 0 else 33.3

        # 추천 결정
        max_prob = max(home_prob, draw_prob, away_prob)
        if max_prob == home_prob and home_prob >= 45:
            recommendation = '승'
            confidence = 'HIGH' if home_prob >= 55 else 'MEDIUM'
        elif max_prob == away_prob and away_prob >= 45:
            recommendation = '패'
            confidence = 'HIGH' if away_prob >= 55 else 'MEDIUM'
        elif draw_prob >= 30:
            recommendation = '무'
            confidence = 'MEDIUM' if draw_prob >= 35 else 'LOW'
        else:
            # 복수 추천
            recommendations = []
            if home_prob >= 30: recommendations.append('승')
            if draw_prob >= 25: recommendations.append('무')
            if away_prob >= 30: recommendations.append('패')
            recommendation = '/'.join(recommendations) if recommendations else '승/무/패'
            confidence = 'LOW'

        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_prob': home_prob,
            'draw_prob': draw_prob,
            'away_prob': away_prob,
            'recommendation': recommendation,
            'confidence': confidence,
            'is_multi': '/' in recommendation
        }

    def analyze_basketball_match(self, match: Dict) -> Dict:
        """농구 경기 분석 (승5패: 홈 6점이상 승, 5점차 이내, 원정 6점이상 승)"""
        # KSPO API 필드: hteam_han_nm / ateam_han_nm (또는 DB: home_team_nm)
        home_team = match.get('hteam_han_nm', '') or match.get('home_team_nm', '홈')
        away_team = match.get('ateam_han_nm', '') or match.get('away_team_nm', '원정')

        # 배당률 기반
        home_odds = float(match.get('win_rt', 0) or 1.8)
        diff_odds = float(match.get('draw_rt', 0) or 4.0)  # 5점차 이내
        away_odds = float(match.get('lose_rt', 0) or 2.5)

        total = (1/home_odds) + (1/diff_odds) + (1/away_odds)
        home_prob = round((1/home_odds) / total * 100, 1) if home_odds > 0 else 40
        diff_prob = round((1/diff_odds) / total * 100, 1) if diff_odds > 0 else 20
        away_prob = round((1/away_odds) / total * 100, 1) if away_odds > 0 else 40

        max_prob = max(home_prob, diff_prob, away_prob)
        if max_prob == home_prob and home_prob >= 50:
            recommendation = '승'
            confidence = 'HIGH' if home_prob >= 60 else 'MEDIUM'
        elif max_prob == away_prob and away_prob >= 50:
            recommendation = '패'
            confidence = 'HIGH' if away_prob >= 60 else 'MEDIUM'
        elif diff_prob >= 25:
            recommendation = '5'
            confidence = 'MEDIUM' if diff_prob >= 30 else 'LOW'
        else:
            recommendations = []
            if home_prob >= 35: recommendations.append('승')
            if diff_prob >= 20: recommendations.append('5')
            if away_prob >= 35: recommendations.append('패')
            recommendation = '/'.join(recommendations) if recommendations else '승/5/패'
            confidence = 'LOW'

        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_prob': home_prob,
            'diff_prob': diff_prob,
            'away_prob': away_prob,
            'recommendation': recommendation,
            'confidence': confidence,
            'is_multi': '/' in recommendation
        }


class AutoAnalysisBot:
    """자동 분석 봇 통합 시스템 (5개 AI 앙상블)"""

    def __init__(self):
        self.telegram = TelegramBotHandler()
        self.collector = KSPODataCollector()
        self.analyzer = MatchAnalyzer()
        self.running = True

        # AI 앙상블 분석기 초기화
        if AI_NOTIFIER_AVAILABLE:
            self.ai_notifier = AutoSportsNotifier()
            logger.info("✅ AI 앙상블 분석기 활성화 (5개 AI)")
        else:
            self.ai_notifier = None
            logger.warning("⚠️ AI 앙상블 사용 불가, 기본 분석 사용")

    async def handle_callback(self, callback_query: Dict):
        """콜백 쿼리 처리"""
        callback_id = callback_query['id']
        data = callback_query.get('data', '')
        chat_id = str(callback_query['from']['id'])

        await self.telegram.answer_callback_query(callback_id, "🤖 AI 분석 시작...")

        if data == 'analyze_soccer':
            await self.analyze_and_send_soccer(chat_id)
        elif data == 'analyze_basketball':
            await self.analyze_and_send_basketball(chat_id)
        elif data == 'update_rounds':
            await self.update_and_notify(chat_id)
        elif data == 'analyze_all':
            await self.analyze_all_and_send(chat_id)

    async def handle_message(self, message: Dict):
        """메시지 처리"""
        chat_id = str(message['chat']['id'])
        text = message.get('text', '')

        if text in ['/start', '/menu', '메뉴']:
            await self.telegram.send_main_menu(chat_id)
        elif text in ['/soccer', '/축구', '승무패']:
            await self.analyze_and_send_soccer(chat_id)
        elif text in ['/basketball', '/농구', '승5패']:
            await self.analyze_and_send_basketball(chat_id)
        elif text in ['/all', '/전체', '전체분석']:
            await self.analyze_all_and_send(chat_id)

    async def update_and_notify(self, chat_id: str = None):
        """최신 데이터 업데이트 및 알림"""
        chat_id = chat_id or self.telegram.chat_id
        await self.telegram.send_message("🔄 최신 회차 데이터를 수집 중...", chat_id=chat_id)

        data = await self.collector.fetch_all_upcoming_matches()

        soccer_rounds = data.get('soccer', {})
        basketball_rounds = data.get('basketball', {})

        soccer_count = sum(len(matches) for matches in soccer_rounds.values())
        basketball_count = sum(len(matches) for matches in basketball_rounds.values())

        message = (
            f"✅ <b>데이터 수집 완료</b>\n\n"
            f"⚽ 축구 승무패: {len(soccer_rounds)}회차 / {soccer_count}경기\n"
            f"🏀 농구 승5패: {len(basketball_rounds)}회차 / {basketball_count}경기\n\n"
            f"🕐 수집 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        await self.telegram.send_message(
            message,
            chat_id=chat_id,
            reply_markup=self.telegram.get_main_menu_keyboard()
        )

    async def analyze_and_send_soccer(self, chat_id: str = None):
        """축구 승무패 분석 및 전송 (AI 앙상블 사용)"""
        chat_id = chat_id or self.telegram.chat_id

        # AI 앙상블 분석 사용
        if self.ai_notifier:
            await self.telegram.send_message(
                "⚽ 축구 승무패 AI 분석 중...\n\n"
                "🤖 5개 AI 앙상블 분석 (약 2분 소요)\n"
                "• GPT-4o\n• Claude Sonnet\n• Gemini 1.5\n• DeepSeek V3\n• Kimi K2",
                chat_id=chat_id
            )

            try:
                # AutoSportsNotifier의 분석 실행 (텔레그램 전송 포함)
                success = await self.ai_notifier.analyze_soccer(test_mode=False)

                if success:
                    await self.telegram.send_message(
                        "✅ 축구 승무패 AI 분석 완료!",
                        chat_id=chat_id,
                        reply_markup=self.telegram.get_main_menu_keyboard()
                    )
                else:
                    await self.telegram.send_message(
                        "❌ 축구 승무패 분석 실패. 다시 시도해주세요.",
                        chat_id=chat_id,
                        reply_markup=self.telegram.get_main_menu_keyboard()
                    )
                return

            except Exception as e:
                logger.error(f"AI 분석 오류: {e}")
                await self.telegram.send_message(
                    f"❌ AI 분석 오류: {str(e)[:100]}",
                    chat_id=chat_id,
                    reply_markup=self.telegram.get_main_menu_keyboard()
                )
                return

        # Fallback: 기본 분석
        await self.telegram.send_message("⚽ 축구 승무패 분석 중...", chat_id=chat_id)

        data = await self.collector.fetch_all_upcoming_matches()
        soccer_rounds = data.get('soccer', {})

        if not soccer_rounds:
            await self.telegram.send_message(
                "❌ 분석 가능한 축구 경기가 없습니다.",
                chat_id=chat_id,
                reply_markup=self.telegram.get_main_menu_keyboard()
            )
            return

        for round_num, matches in sorted(soccer_rounds.items()):
            if len(matches) == 0:
                continue

            message = self._format_soccer_analysis(round_num, matches)
            await self.telegram.send_long_message(message, chat_id=chat_id)
            await asyncio.sleep(1)

        await self.telegram.send_message(
            "✅ 축구 승무패 분석 완료!",
            chat_id=chat_id,
            reply_markup=self.telegram.get_main_menu_keyboard()
        )

    async def analyze_and_send_basketball(self, chat_id: str = None):
        """농구 승5패 분석 및 전송 (AI 앙상블 사용)"""
        chat_id = chat_id or self.telegram.chat_id

        # AI 앙상블 분석 사용
        if self.ai_notifier:
            await self.telegram.send_message(
                "🏀 농구 승5패 AI 분석 중...\n\n"
                "🤖 5개 AI 앙상블 분석 (약 2분 소요)\n"
                "• GPT-4o\n• Claude Sonnet\n• Gemini 1.5\n• DeepSeek V3\n• Kimi K2",
                chat_id=chat_id
            )

            try:
                # AutoSportsNotifier의 분석 실행 (텔레그램 전송 포함)
                success = await self.ai_notifier.analyze_basketball(test_mode=False)

                if success:
                    await self.telegram.send_message(
                        "✅ 농구 승5패 AI 분석 완료!",
                        chat_id=chat_id,
                        reply_markup=self.telegram.get_main_menu_keyboard()
                    )
                else:
                    await self.telegram.send_message(
                        "❌ 농구 승5패 분석 실패. 다시 시도해주세요.",
                        chat_id=chat_id,
                        reply_markup=self.telegram.get_main_menu_keyboard()
                    )
                return

            except Exception as e:
                logger.error(f"AI 분석 오류: {e}")
                await self.telegram.send_message(
                    f"❌ AI 분석 오류: {str(e)[:100]}",
                    chat_id=chat_id,
                    reply_markup=self.telegram.get_main_menu_keyboard()
                )
                return

        # Fallback: 기본 분석
        await self.telegram.send_message("🏀 농구 승5패 분석 중...", chat_id=chat_id)

        data = await self.collector.fetch_all_upcoming_matches()
        basketball_rounds = data.get('basketball', {})

        if not basketball_rounds:
            await self.telegram.send_message(
                "❌ 분석 가능한 농구 경기가 없습니다.",
                chat_id=chat_id,
                reply_markup=self.telegram.get_main_menu_keyboard()
            )
            return

        for round_num, matches in sorted(basketball_rounds.items()):
            if len(matches) == 0:
                continue

            message = self._format_basketball_analysis(round_num, matches)
            await self.telegram.send_long_message(message, chat_id=chat_id)
            await asyncio.sleep(1)

        await self.telegram.send_message(
            "✅ 농구 승5패 분석 완료!",
            chat_id=chat_id,
            reply_markup=self.telegram.get_main_menu_keyboard()
        )

    async def analyze_all_and_send(self, chat_id: str = None):
        """전체 분석 및 전송"""
        chat_id = chat_id or self.telegram.chat_id
        await self.telegram.send_message("📊 전체 자동 분석 시작...", chat_id=chat_id)

        await self.analyze_and_send_soccer(chat_id)
        await asyncio.sleep(2)
        await self.analyze_and_send_basketball(chat_id)

        await self.telegram.send_message(
            f"🎉 <b>전체 분석 완료!</b>\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            chat_id=chat_id,
            reply_markup=self.telegram.get_main_menu_keyboard()
        )

    def _format_soccer_analysis(self, round_num: str, matches: List[Dict]) -> str:
        """축구 승무패 분석 결과 포맷"""
        lines = [
            f"⚽ <b>축구 승무패 {round_num}회차</b>",
            f"📅 경기 수: {len(matches)}경기",
            f"🕐 분석 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "=" * 35,
            ""
        ]

        high_confidence_count = 0
        multi_count = 0

        for idx, match in enumerate(matches, 1):
            analysis = self.analyzer.analyze_soccer_match(match)

            game_num = match.get('game_sno', idx)
            match_time = match.get('match_dt', '')

            # 신뢰도 이모지
            if analysis['confidence'] == 'HIGH':
                conf_emoji = '🔥'
                high_confidence_count += 1
            elif analysis['confidence'] == 'MEDIUM':
                conf_emoji = '✅'
            else:
                conf_emoji = '⚠️'

            if analysis['is_multi']:
                multi_count += 1
                multi_tag = ' [복수]'
            else:
                multi_tag = ''

            lines.append(
                f"<b>[{game_num:02d}] {analysis['home_team']} vs {analysis['away_team']}</b>{multi_tag}"
            )
            lines.append(
                f"    승:{analysis['home_prob']}% | 무:{analysis['draw_prob']}% | 패:{analysis['away_prob']}%"
            )
            lines.append(
                f"    {conf_emoji} 추천: <b>{analysis['recommendation']}</b> ({analysis['confidence']})"
            )
            lines.append("")

        lines.append("=" * 35)
        lines.append(f"🔥 고신뢰: {high_confidence_count}개 | ⚠️ 복수: {multi_count}개")

        return '\n'.join(lines)

    def _format_basketball_analysis(self, round_num: str, matches: List[Dict]) -> str:
        """농구 승5패 분석 결과 포맷"""
        lines = [
            f"🏀 <b>농구 승5패 {round_num}회차</b>",
            f"📅 경기 수: {len(matches)}경기",
            f"🕐 분석 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "승: 홈팀 6점 이상 승리",
            "5: 5점차 이내 (접전)",
            "패: 원정팀 6점 이상 승리",
            "",
            "=" * 35,
            ""
        ]

        high_confidence_count = 0
        multi_count = 0

        for idx, match in enumerate(matches, 1):
            analysis = self.analyzer.analyze_basketball_match(match)

            game_num = match.get('game_sno', idx)

            if analysis['confidence'] == 'HIGH':
                conf_emoji = '🔥'
                high_confidence_count += 1
            elif analysis['confidence'] == 'MEDIUM':
                conf_emoji = '✅'
            else:
                conf_emoji = '⚠️'

            if analysis['is_multi']:
                multi_count += 1
                multi_tag = ' [복수]'
            else:
                multi_tag = ''

            lines.append(
                f"<b>[{game_num:02d}] {analysis['home_team']} vs {analysis['away_team']}</b>{multi_tag}"
            )
            lines.append(
                f"    승:{analysis['home_prob']}% | 5:{analysis['diff_prob']}% | 패:{analysis['away_prob']}%"
            )
            lines.append(
                f"    {conf_emoji} 추천: <b>{analysis['recommendation']}</b> ({analysis['confidence']})"
            )
            lines.append("")

        lines.append("=" * 35)
        lines.append(f"🔥 고신뢰: {high_confidence_count}개 | ⚠️ 복수: {multi_count}개")

        return '\n'.join(lines)

    async def run_polling(self):
        """Long polling으로 봇 실행"""
        logger.info("텔레그램 봇 시작 (polling mode)")

        # 시작 메시지
        await self.telegram.send_message(
            f"🤖 <b>스포츠 분석 봇 시작</b>\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            reply_markup=self.telegram.get_main_menu_keyboard()
        )

        while self.running:
            try:
                updates = await self.telegram.get_updates(timeout=30)

                for update in updates:
                    if 'callback_query' in update:
                        await self.handle_callback(update['callback_query'])
                    elif 'message' in update:
                        await self.handle_message(update['message'])

            except Exception as e:
                logger.error(f"Polling 오류: {e}")
                await asyncio.sleep(5)

    async def run_once(self):
        """한번 실행 (자동 분석)"""
        logger.info("자동 분석 시작 (once mode)")
        await self.analyze_all_and_send()
        logger.info("자동 분석 완료")

    async def run_scheduled(self, interval_minutes: int = 60):
        """스케줄 기반 자동 분석"""
        logger.info(f"스케줄 분석 시작 (매 {interval_minutes}분)")

        while self.running:
            try:
                await self.analyze_all_and_send()
                logger.info(f"다음 분석까지 {interval_minutes}분 대기")
                await asyncio.sleep(interval_minutes * 60)
            except Exception as e:
                logger.error(f"스케줄 분석 오류: {e}")
                await asyncio.sleep(60)


async def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='스포츠 분석 텔레그램 봇')
    parser.add_argument('--once', action='store_true', help='한번 실행하고 종료')
    parser.add_argument('--schedule', type=int, metavar='MINUTES', help='주기적 자동 분석 (분)')
    args = parser.parse_args()

    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다")
        sys.exit(1)

    if not CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID가 설정되지 않았습니다")
        sys.exit(1)

    bot = AutoAnalysisBot()

    if args.once:
        await bot.run_once()
    elif args.schedule:
        await bot.run_scheduled(args.schedule)
    else:
        # 기본: polling + 스케줄 병행
        polling_task = asyncio.create_task(bot.run_polling())

        try:
            await polling_task
        except KeyboardInterrupt:
            bot.running = False
            logger.info("봇 종료")


if __name__ == '__main__':
    asyncio.run(main())
