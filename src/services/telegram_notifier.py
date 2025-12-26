"""
텔레그램 알림 서비스
- 고신뢰도 AI 픽 자동 알림
- 경기 결과 알림
- 적중률 통계 알림
"""

import os
import logging
from typing import List, Dict, Optional
from telegram import Bot
from telegram.error import TelegramError
import asyncio

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    텔레그램 알림 전송 서비스
    """

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram 설정이 없습니다. 알림이 비활성화됩니다.")
            self.enabled = False
        else:
            self.bot = Bot(token=self.bot_token)
            self.enabled = True
            logger.info("✅ Telegram 알림 서비스 활성화")

    async def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        텔레그램 메시지 전송

        Args:
            message: 전송할 메시지
            parse_mode: 메시지 포맷 ('Markdown' or 'HTML')

        Returns:
            성공 여부
        """
        if not self.enabled:
            logger.warning("Telegram이 비활성화되어 있습니다.")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id, text=message, parse_mode=parse_mode
            )
            logger.info("✅ Telegram 메시지 전송 성공")
            return True
        except TelegramError as e:
            logger.error(f"❌ Telegram 메시지 전송 실패: {e}")
            return False

    async def notify_high_confidence_pick(
        self, match_info: str, analysis: Dict, threshold: float = 0.65
    ) -> bool:
        """
        고신뢰도 픽 알림

        Args:
            match_info: 경기 정보 (예: "맨시티 vs 첼시")
            analysis: AI 분석 결과
            threshold: 최소 신뢰도 (기본 65%)

        Returns:
            전송 성공 여부
        """
        probs = analysis.get("probs", {})
        max_prob = max(probs.get("home", 0), probs.get("draw", 0), probs.get("away", 0))

        if max_prob < threshold:
            logger.debug(f"신뢰도 {max_prob * 100:.1f}%로 알림 기준 미달")
            return False

        # 예측 결과 결정
        if max_prob == probs.get("home"):
            prediction = "홈 승리"
            icon = "🏠"
        elif max_prob == probs.get("away"):
            prediction = "원정 승리"
            icon = "✈️"
        else:
            prediction = "무승부"
            icon = "🤝"

        # AI Fair Odds
        ai_odds = analysis.get("ai_odds", {})
        recommendation = analysis.get("recommendation", {})

        message = f"""
🎯 **고신뢰도 AI 픽 알림**

📊 **경기**: {match_info}

{icon} **예측**: {prediction}
🔢 **신뢰도**: {max_prob * 100:.1f}%
💰 **AI 배당**: {ai_odds.get(prediction.split()[0].lower(), 0):.2f}

📌 **추천 전략**: {recommendation.get('mark', 'N/A')} {recommendation.get('icon', '')}

---
*베트맨 스포츠토토 AI 분석 시스템*
"""

        return await self.send_message(message)

    async def notify_match_result(
        self, match_info: str, predicted: str, actual: str, is_correct: bool
    ) -> bool:
        """
        경기 결과 알림

        Args:
            match_info: 경기 정보
            predicted: AI 예측
            actual: 실제 결과
            is_correct: 적중 여부

        Returns:
            전송 성공 여부
        """
        status_icon = "✅" if is_correct else "❌"
        status_text = "적중!" if is_correct else "오예측"

        message = f"""
{status_icon} **경기 결과 - {status_text}**

📊 **경기**: {match_info}

🤖 **AI 예측**: {predicted}
⚽ **실제 결과**: {actual}

---
*베트맨 스포츠토토 AI 분석 시스템*
"""

        return await self.send_message(message)

    async def notify_daily_summary(
        self, total_matches: int, hit_rate: float, roi: float
    ) -> bool:
        """
        일일 요약 통계 알림

        Args:
            total_matches: 전체 경기 수
            hit_rate: 적중률
            roi: ROI (수익률)

        Returns:
            전송 성공 여부
        """
        message = f"""
📈 **오늘의 AI 분석 요약**

🎯 **전체 경기**: {total_matches}경기
✅ **적중률**: {hit_rate * 100:.1f}%
💰 **ROI**: {roi * 100:+.1f}%

---
*베트맨 스포츠토토 AI 분석 시스템*
_자동 생성 리포트_
"""

        return await self.send_message(message)

    async def notify_top_picks(self, picks: List[Dict]) -> bool:
        """
        오늘의 Top Picks 알림

        Args:
            picks: Top 3 픽 리스트

        Returns:
            전송 성공 여부
        """
        if not picks:
            return False

        message = "🌟 **오늘의 Top 3 AI 추천 경기**\n\n"

        for idx, pick in enumerate(picks[:3], 1):
            match_info = pick.get("match_info", "알 수 없음")
            probs = pick.get("analysis", {}).get("probs", {})
            recommendation = pick.get("analysis", {}).get("recommendation", {})

            max_prob = max(probs.get("home", 0), probs.get("draw", 0), probs.get("away", 0))

            message += f"""
**{idx}. {match_info}**
{recommendation.get('icon', '🎯')} {recommendation.get('mark', 'N/A')}
🔢 신뢰도: {max_prob * 100:.0f}%

"""

        message += "---\n*베트맨 스포츠토토 AI 분석 시스템*"

        return await self.send_message(message)

    async def notify_hit_rate_report(self, report) -> bool:
        """
        적중률 리포트 텔레그램 전송

        Args:
            report: HitRateReport 객체

        Returns:
            전송 성공 여부
        """
        from src.services.hit_rate_reporter import hit_rate_reporter
        message = hit_rate_reporter.format_telegram_message(report)
        return await self.send_message(message)

    async def notify_round_result(
        self,
        round_number: int,
        game_type: str,
        hit_rate: float,
        correct: int,
        total: int,
        is_single_hit: bool = False
    ) -> bool:
        """
        회차 결과 간단 알림

        Args:
            round_number: 회차 번호
            game_type: 게임 타입 ("soccer_wdl" | "basketball_w5l")
            hit_rate: 적중률 (0.0 ~ 1.0)
            correct: 적중 경기 수
            total: 전체 경기 수
            is_single_hit: 14/14 전체 적중 여부

        Returns:
            전송 성공 여부
        """
        icon = "⚽" if game_type == "soccer_wdl" else "🏀"
        game_name = "축구 승무패" if game_type == "soccer_wdl" else "농구 승5패"

        status = "\n🎉 *14경기 전체 적중!* 🎉" if is_single_hit else ""

        message = f"""
{icon} *{game_name} {round_number}회차 결과*

📊 *적중률*: {hit_rate * 100:.1f}% ({correct}/{total})
{status}

---
_프로토 AI 분석 시스템_
"""

        return await self.send_message(message)

    async def notify_cumulative_stats(self, stats) -> bool:
        """
        누적 통계 알림

        Args:
            stats: CumulativeStats 객체

        Returns:
            전송 성공 여부
        """
        icon = "⚽" if stats.game_type == "soccer_wdl" else "🏀"
        game_name = "축구 승무패" if stats.game_type == "soccer_wdl" else "농구 승5패"

        recent_5_str = f"• 최근 5회차: {stats.recent_5_avg * 100:.1f}%" if stats.recent_5_avg > 0 else ""
        recent_10_str = f"• 최근 10회차: {stats.recent_10_avg * 100:.1f}%" if stats.recent_10_avg > 0 else ""

        message = f"""
📈 *{game_name} 누적 통계*

📊 *총 {stats.total_rounds}회차 분석*

✅ 평균 적중률: {stats.avg_hit_rate * 100:.1f}%
🏆 최고 적중률: {stats.best_hit_rate * 100:.1f}% ({stats.best_round}회차)
📉 최저 적중률: {stats.worst_hit_rate * 100:.1f}% ({stats.worst_round}회차)

📈 *최근 트렌드*
{recent_5_str}
{recent_10_str}

---
_프로토 AI 분석 시스템_
"""

        return await self.send_message(message)


# 전역 인스턴스
telegram_notifier = TelegramNotifier()


async def main_test():
    """테스트용 메인 함수"""
    notifier = TelegramNotifier()

    # 테스트 알림
    await notifier.send_message("🧪 Telegram 알림 테스트")

    # 고신뢰도 픽 테스트
    test_analysis = {
        "probs": {"home": 0.75, "draw": 0.15, "away": 0.10},
        "ai_odds": {"home": 1.33, "draw": 6.67, "away": 10.0},
        "recommendation": {"mark": "[승]", "icon": "🔒"},
    }
    await notifier.notify_high_confidence_pick("맨시티 vs 첼시", test_analysis)


if __name__ == "__main__":
    asyncio.run(main_test())
