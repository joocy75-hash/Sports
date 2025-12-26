"""
텔레그램 봇 자동 알림 시스템

프로토 14경기 분석 결과를 텔레그램으로 자동 전송
"""

import os
import logging
from typing import Optional, List
import asyncio
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramBot:
    """텔레그램 봇"""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Args:
            bot_token: 텔레그램 봇 토큰 (환경변수 TELEGRAM_BOT_TOKEN)
            chat_id: 수신자 채팅 ID (환경변수 TELEGRAM_CHAT_ID)
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')

        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다")

        if not self.chat_id:
            logger.warning("TELEGRAM_CHAT_ID가 설정되지 않았습니다")

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(
        self,
        message: str,
        parse_mode: str = 'HTML',
        disable_notification: bool = False
    ) -> bool:
        """
        메시지 전송

        Args:
            message: 전송할 메시지
            parse_mode: 'HTML', 'Markdown', or None
            disable_notification: 무음 알림

        Returns:
            성공 여부
        """
        if not self.bot_token or not self.chat_id:
            logger.error("텔레그램 봇 토큰 또는 채팅 ID가 설정되지 않았습니다")
            return False

        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_notification': disable_notification
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"텔레그램 메시지 전송 성공: {len(message)} chars")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"텔레그램 전송 실패 ({response.status}): {error_text}")
                        return False

        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 오류: {e}", exc_info=True)
            return False

    async def send_long_message(
        self,
        message: str,
        max_length: int = 4096,
        parse_mode: str = 'HTML'
    ) -> bool:
        """
        긴 메시지를 분할하여 전송 (텔레그램 4096자 제한)

        Args:
            message: 전송할 메시지
            max_length: 최대 길이 (기본 4096)
            parse_mode: 파싱 모드

        Returns:
            성공 여부
        """
        if len(message) <= max_length:
            return await self.send_message(message, parse_mode=parse_mode)

        # 메시지 분할
        parts = []
        current = ""

        for line in message.split('\n'):
            if len(current) + len(line) + 1 <= max_length:
                current += line + '\n'
            else:
                if current:
                    parts.append(current)
                current = line + '\n'

        if current:
            parts.append(current)

        # 순차 전송
        success = True
        for i, part in enumerate(parts):
            logger.info(f"텔레그램 메시지 전송 ({i+1}/{len(parts)})")
            result = await self.send_message(part, parse_mode=parse_mode)
            if not result:
                success = False
            await asyncio.sleep(0.5)  # Rate limit 방지

        return success

    async def send_proto_analysis(
        self,
        round_id: str,
        game_type: str,
        marking_text: str
    ) -> bool:
        """
        프로토 분석 결과 전송

        Args:
            round_id: 회차 ID
            game_type: '승무패' or '승5패'
            marking_text: 마킹 리스트 텍스트

        Returns:
            성공 여부
        """
        # HTML 포맷으로 변환
        html_message = self._format_proto_html(round_id, game_type, marking_text)

        return await self.send_long_message(html_message, parse_mode='HTML')

    def _format_proto_html(
        self,
        round_id: str,
        game_type: str,
        marking_text: str
    ) -> str:
        """프로토 분석 결과를 HTML 포맷으로 변환"""

        # 기본 텍스트를 HTML로 변환
        lines = marking_text.split('\n')
        html_lines = []

        for line in lines:
            # 헤더
            if line.startswith('='):
                continue
            elif line.startswith('프로토'):
                html_lines.append(f"<b>{line}</b>")
            elif line.startswith('분석 시각'):
                html_lines.append(f"<i>{line}</i>")
            # 경기 번호
            elif line.startswith('['):
                # [01] 팀A vs 팀B [복수]
                html_lines.append(f"\n<b>{line}</b>")
            # 추천 결과
            elif line.strip().startswith('→'):
                html_lines.append(f"<code>{line}</code>")
            # 구분선
            elif line.startswith('-'):
                html_lines.append("─" * 40)
            # 통계
            elif any(keyword in line for keyword in ['고신뢰', '복수 베팅', '평균', '추천 전략', '전략 근거']):
                html_lines.append(f"<b>{line}</b>")
            else:
                html_lines.append(line)

        return '\n'.join(html_lines)

    async def send_alert(
        self,
        title: str,
        message: str,
        emoji: str = '🔔'
    ) -> bool:
        """
        알림 전송

        Args:
            title: 제목
            message: 내용
            emoji: 이모지

        Returns:
            성공 여부
        """
        formatted = f"{emoji} <b>{title}</b>\n\n{message}"
        return await self.send_message(formatted, parse_mode='HTML')

    async def test_connection(self) -> bool:
        """
        연결 테스트

        Returns:
            성공 여부
        """
        try:
            message = f"🤖 텔레그램 봇 연결 테스트\n시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            return await self.send_message(message)
        except Exception as e:
            logger.error(f"텔레그램 연결 테스트 실패: {e}")
            return False


class TelegramNotifier:
    """텔레그램 알림 관리자"""

    def __init__(self, bot: Optional[TelegramBot] = None):
        """
        Args:
            bot: TelegramBot 인스턴스 (None이면 자동 생성)
        """
        self.bot = bot or TelegramBot()

    async def notify_proto_round_analyzed(
        self,
        round_id: str,
        game_type: str,
        marking_text: str,
        high_confidence_count: int,
        upset_count: int,
        strategy: str
    ) -> bool:
        """
        프로토 회차 분석 완료 알림

        Args:
            round_id: 회차 ID
            game_type: 게임 타입
            marking_text: 마킹 리스트
            high_confidence_count: 고신뢰 경기 수
            upset_count: 복수 베팅 경기 수
            strategy: 추천 전략

        Returns:
            성공 여부
        """
        logger.info(f"프로토 {game_type} {round_id}회 분석 완료 알림 전송 중...")

        # 요약 메시지
        summary = (
            f"📊 <b>프로토 {game_type} {round_id}회 분석 완료</b>\n\n"
            f"✅ 고신뢰 경기: {high_confidence_count}개\n"
            f"⚠️ 복수 베팅 추천: {upset_count}개\n"
            f"🎯 추천 전략: {strategy}\n\n"
            f"─────────────────────\n"
        )

        # 전체 메시지
        full_message = summary + marking_text

        return await self.bot.send_long_message(full_message, parse_mode='HTML')

    async def notify_auto_analysis_started(
        self,
        round_id: str,
        game_type: str,
        match_count: int
    ) -> bool:
        """
        자동 분석 시작 알림

        Args:
            round_id: 회차 ID
            game_type: 게임 타입
            match_count: 경기 수

        Returns:
            성공 여부
        """
        message = (
            f"🔍 <b>자동 분석 시작</b>\n\n"
            f"회차: {round_id}\n"
            f"게임: {game_type}\n"
            f"경기 수: {match_count}개\n\n"
            f"분석 중... (약 1-2분 소요)"
        )

        return await self.bot.send_message(message, parse_mode='HTML', disable_notification=True)

    async def notify_error(
        self,
        error_type: str,
        error_message: str
    ) -> bool:
        """
        에러 알림

        Args:
            error_type: 에러 타입
            error_message: 에러 메시지

        Returns:
            성공 여부
        """
        message = (
            f"❌ <b>오류 발생</b>\n\n"
            f"타입: {error_type}\n"
            f"메시지: {error_message}\n\n"
            f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return await self.bot.send_message(message, parse_mode='HTML')

    async def notify_daily_summary(
        self,
        date: str,
        analyzed_rounds: int,
        total_matches: int,
        avg_confidence: float
    ) -> bool:
        """
        일일 요약 알림

        Args:
            date: 날짜
            analyzed_rounds: 분석한 회차 수
            total_matches: 총 경기 수
            avg_confidence: 평균 신뢰도

        Returns:
            성공 여부
        """
        message = (
            f"📅 <b>일일 분석 요약 ({date})</b>\n\n"
            f"분석 회차: {analyzed_rounds}개\n"
            f"총 경기: {total_matches}개\n"
            f"평균 AI 합의도: {avg_confidence:.1%}\n\n"
            f"모든 분석 결과는 위 메시지를 참조하세요."
        )

        return await self.bot.send_message(message, parse_mode='HTML')
