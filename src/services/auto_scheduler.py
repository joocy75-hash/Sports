"""
자동 분석 스케줄러

정기적으로 프로토 경기를 자동 분석하여 텔레그램으로 전송
- 농구 승5패: 매일 특정 시간
- 축구 승무패: 매일 특정 시간
"""

import logging
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, time
import aiohttp

from src.services.telegram_bot import TelegramNotifier, TelegramBot

# BetmanScraper는 선택적 의존성
try:
    from src.services.scraper import BetmanScraper
except ImportError:
    BetmanScraper = None

logger = logging.getLogger(__name__)


class AutoScheduler:
    """자동 분석 스케줄러"""

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        notifier: Optional[TelegramNotifier] = None
    ):
        """
        Args:
            api_base_url: 백엔드 API URL
            notifier: 텔레그램 알림기 (None이면 자동 생성)
        """
        self.api_base_url = api_base_url
        self.notifier = notifier or TelegramNotifier()
        self.scraper = BetmanScraper() if BetmanScraper else None

        # 분석 스케줄 설정
        self.schedules = {
            '승5패': time(hour=9, minute=0),   # 매일 09:00 농구 분석
            '승무패': time(hour=10, minute=0)  # 매일 10:00 축구 분석
        }

        self.running = False

    async def start(self):
        """스케줄러 시작"""
        self.running = True
        logger.info("자동 분석 스케줄러 시작")

        # 시작 알림
        await self.notifier.bot.send_alert(
            title="자동 분석 시작",
            message=f"승5패: {self.schedules['승5패'].strftime('%H:%M')}\n승무패: {self.schedules['승무패'].strftime('%H:%M')}",
            emoji="🚀"
        )

        # 무한 루프
        while self.running:
            try:
                await self._check_and_run()
                await asyncio.sleep(60)  # 1분마다 체크
            except Exception as e:
                logger.error(f"스케줄러 오류: {e}", exc_info=True)
                await self.notifier.notify_error("스케줄러 오류", str(e))
                await asyncio.sleep(300)  # 5분 대기 후 재시도

    def stop(self):
        """스케줄러 중지"""
        self.running = False
        logger.info("자동 분석 스케줄러 중지")

    async def _check_and_run(self):
        """현재 시간이 스케줄 시간이면 분석 실행"""
        now = datetime.now().time()

        for game_type, schedule_time in self.schedules.items():
            # 정각 ±1분 이내인지 확인
            if self._is_time_match(now, schedule_time):
                logger.info(f"{game_type} 자동 분석 시작 (스케줄: {schedule_time})")
                await self.run_analysis(game_type)

    def _is_time_match(self, current: time, target: time, tolerance_minutes: int = 1) -> bool:
        """시간이 일치하는지 확인"""
        current_minutes = current.hour * 60 + current.minute
        target_minutes = target.hour * 60 + target.minute

        return abs(current_minutes - target_minutes) <= tolerance_minutes

    async def run_analysis(self, game_type: str) -> bool:
        """
        특정 게임 타입 분석 실행

        Args:
            game_type: '승5패' or '승무패'

        Returns:
            성공 여부
        """
        try:
            # 1. 최신 회차 정보 가져오기
            logger.info(f"{game_type} 최신 회차 정보 조회 중...")
            round_data = await self._fetch_latest_round(game_type)

            if not round_data:
                logger.warning(f"{game_type} 회차 정보를 가져올 수 없습니다")
                return False

            round_id = round_data['round_id']
            matches = round_data['matches']

            logger.info(f"{game_type} {round_id}회 분석 시작 ({len(matches)}개 경기)")

            # 2. 분석 시작 알림
            await self.notifier.notify_auto_analysis_started(
                round_id=round_id,
                game_type=game_type,
                match_count=len(matches)
            )

            # 3. AI 분석 API 호출
            result = await self._call_proto_analysis_api(
                round_id=round_id,
                game_type=game_type,
                matches=matches
            )

            if not result:
                logger.error(f"{game_type} {round_id}회 분석 실패")
                await self.notifier.notify_error(
                    error_type=f"{game_type} 분석 실패",
                    error_message=f"{round_id}회 분석 중 오류 발생"
                )
                return False

            # 4. 분석 완료 알림 (마킹 리스트 포함)
            await self.notifier.notify_proto_round_analyzed(
                round_id=round_id,
                game_type=game_type,
                marking_text=result['marking_text'],
                high_confidence_count=result['statistics']['high_confidence_count'],
                upset_count=result['statistics']['upset_prone_count'],
                strategy=result['strategy']['recommended_strategy']
            )

            logger.info(f"{game_type} {round_id}회 분석 완료 및 알림 전송 성공")
            return True

        except Exception as e:
            logger.error(f"{game_type} 분석 오류: {e}", exc_info=True)
            await self.notifier.notify_error(
                error_type=f"{game_type} 자동 분석 오류",
                error_message=str(e)
            )
            return False

    async def _fetch_latest_round(self, game_type: str) -> Optional[Dict]:
        """
        최신 회차 정보 가져오기

        Args:
            game_type: '승5패' or '승무패'

        Returns:
            {
                'round_id': '2024001',
                'matches': [...]
            }
        """
        try:
            # 카테고리 매핑
            category_map = {
                '승5패': 'basket',  # 농구
                '승무패': 'soccer'   # 축구
            }

            category = category_map.get(game_type)
            if not category:
                logger.error(f"알 수 없는 게임 타입: {game_type}")
                return None

            # 베트맨에서 경기 정보 스크래핑
            games = await self.scraper.scrape_category(category)

            if not games or len(games) == 0:
                logger.warning(f"{game_type} 경기가 없습니다")
                return None

            # 첫 경기의 round 정보 사용
            first_game = games[0]
            round_id = first_game.get('round', datetime.now().strftime('%Y%m%d'))

            # 경기 데이터 변환
            matches = []
            for i, game in enumerate(games[:14], start=1):  # 최대 14경기
                matches.append({
                    'match_id': game.get('match_id', f'{round_id}_{i:02d}'),
                    'match_number': i,
                    'home_team': game.get('home_team', ''),
                    'away_team': game.get('away_team', ''),
                    'league': game.get('league', ''),
                    'match_time': game.get('match_time', ''),
                    'home_form': None,  # TODO: 팀 통계 연동
                    'away_form': None,
                    'home_rank': None,
                    'away_rank': None
                })

            return {
                'round_id': round_id,
                'matches': matches
            }

        except Exception as e:
            logger.error(f"회차 정보 조회 오류: {e}", exc_info=True)
            return None

    async def _call_proto_analysis_api(
        self,
        round_id: str,
        game_type: str,
        matches: List[Dict]
    ) -> Optional[Dict]:
        """
        프로토 분석 API 호출

        Args:
            round_id: 회차 ID
            game_type: 게임 타입
            matches: 경기 리스트

        Returns:
            분석 결과
        """
        try:
            url = f"{self.api_base_url}/api/analysis/proto/round/text"

            payload = {
                'round_id': round_id,
                'game_type': game_type,
                'matches': matches
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"프로토 분석 API 호출 성공: {round_id}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"프로토 분석 API 실패 ({response.status}): {error_text}")
                        return None

        except asyncio.TimeoutError:
            logger.error(f"프로토 분석 API 타임아웃: {round_id}")
            return None
        except Exception as e:
            logger.error(f"프로토 분석 API 호출 오류: {e}", exc_info=True)
            return None

    async def run_manual_analysis(self, game_type: str) -> bool:
        """
        수동으로 특정 게임 타입 분석 실행

        Args:
            game_type: '승5패' or '승무패'

        Returns:
            성공 여부
        """
        logger.info(f"수동 분석 실행: {game_type}")
        return await self.run_analysis(game_type)

    async def run_test(self) -> bool:
        """
        테스트 실행 (텔레그램 연결 확인)

        Returns:
            성공 여부
        """
        logger.info("텔레그램 봇 연결 테스트")
        return await self.notifier.bot.test_connection()

    def set_schedule(self, game_type: str, hour: int, minute: int):
        """
        스케줄 변경

        Args:
            game_type: '승5패' or '승무패'
            hour: 시 (0-23)
            minute: 분 (0-59)
        """
        if game_type in self.schedules:
            self.schedules[game_type] = time(hour=hour, minute=minute)
            logger.info(f"{game_type} 스케줄 변경: {hour:02d}:{minute:02d}")

    def get_schedules(self) -> Dict[str, str]:
        """
        현재 스케줄 조회

        Returns:
            {'승5패': '09:00', '승무패': '10:00'}
        """
        return {
            game_type: schedule.strftime('%H:%M')
            for game_type, schedule in self.schedules.items()
        }
