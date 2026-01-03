"""
토토 텔레그램 알림 서비스

CLAUDE.md 섹션 4의 텔레그램 알림 형식 구현
"""

import logging
from typing import Dict, List
from datetime import datetime
from src.services.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class TotoTelegramNotifier:
    """토토 14경기 텔레그램 알림"""

    def __init__(self):
        self.notifier = TelegramNotifier()

    async def send_toto_analysis(
        self,
        game_type: str,
        round_number: int,
        matches: List[Dict],
        multi_games: List[int] = None,
    ):
        """
        토토 14경기 분석 결과 텔레그램 전송

        CLAUDE.md 섹션 4 형식:
        - 14경기 전체 예측
        - 단식 정답 (14경기)
        - 복수 베팅 경기 (최대 4경기)
        """
        multi_games = multi_games or []

        # 게임 타입별 이모지
        emoji = "⚽" if "축구" in game_type else "🏀"

        # 헤더
        message = f"{emoji} *{game_type} {round_number}회차*\n"
        message += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 14경기 전체 예측
        message += "📋 *14경기 전체 예측*\n\n"

        single_answers = []
        multi_info = []

        for idx, match_data in enumerate(matches, 1):
            match = match_data["match"]
            pred = match_data["prediction"]

            home = match["home_team"]
            away = match["away_team"]

            # 복수 베팅 여부
            is_multi = match["game_number"] in multi_games
            marker = "[복수]" if is_multi else ""

            # 확률 표시
            if "축구" in game_type:
                probs = f"({pred['home_prob']:.0f}%/{pred['draw_prob']:.0f}%/{pred['away_prob']:.0f}%)"
            else:
                probs = f"({pred['home_prob']:.0f}%/{pred['diff_prob']:.0f}%/{pred['away_prob']:.0f}%)"

            # 추천 픽
            recommended = pred["recommended"]
            pick_symbol = self._get_pick_symbol(recommended, game_type)

            # 이변 경기 표시
            upset_marker = ""
            if pred.get("is_underdog"):
                upset_marker = f" ⚠️ 이변 {pred['upset_probability']:.0f}%"

            # 경기 정보
            message += f"{idx:02d}. {home} vs {away} {marker}\n"

            if is_multi:
                # 복수 베팅: 추천 2개 표시
                multi_picks = pred.get("multi_picks", [])
                picks_str = ",".join(multi_picks)
                message += f"     ⚠️ *[{picks_str}]* {probs}{upset_marker}\n\n"

                # 복수 정보 저장
                multi_info.append({
                    "number": idx,
                    "home": home,
                    "away": away,
                    "picks": multi_picks
                })
            else:
                # 단일 베팅
                message += f"     🔒 [{pick_symbol}] {probs}{upset_marker}\n\n"

            # 단식 정답 저장
            single_answers.append(f"{idx}:{pick_symbol}")

        # 단식 정답
        message += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += "📝 *단식 정답*\n"

        # 7경기씩 두 줄로 표시
        line1 = " ".join(single_answers[:7])
        line2 = " ".join(single_answers[7:14])
        message += f"`{line1}`\n"
        message += f"`{line2}`\n"

        # 복수 베팅 정보
        if multi_info:
            message += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            total_combos = 2 ** len(multi_info)
            message += f"🎰 *복수 {len(multi_info)}경기* (총 {total_combos}조합)\n"

            for m in multi_info:
                picks_str = ",".join(m["picks"])
                message += f"{m['number']:02d}번 {m['home']} vs {m['away']} → {picks_str}\n"

        message += "━━━━━━━━━━━━━━━━━━━━━━━━\n"

        # 텔레그램 전송
        await self.notifier.send_message(message, parse_mode="Markdown")

        logger.info(f"[TotoTelegram] {game_type} {round_number}회차 분석 전송 완료")

    def _get_pick_symbol(self, recommended: str, game_type: str) -> str:
        """
        추천 픽을 기호로 변환

        축구: home → 1, draw → X, away → 2
        농구: home → 승, 5point → 5, away → 패
        """
        if "축구" in game_type:
            mapping = {
                "home": "1",
                "draw": "X",
                "away": "2",
            }
        else:
            mapping = {
                "home": "승",
                "5point": "5",
                "away": "패",
            }

        return mapping.get(recommended, recommended)

    async def send_analysis_summary(
        self,
        game_type: str,
        round_number: int,
        total_matches: int,
        ai_count: int,
        upset_count: int,
        multi_count: int,
    ):
        """
        분석 요약 전송 (간단한 알림)
        """
        emoji = "⚽" if "축구" in game_type else "🏀"

        message = f"{emoji} *{game_type} {round_number}회차 분석 완료*\n\n"
        message += f"✅ 총 {total_matches}경기 분석\n"
        message += f"🤖 {ai_count}개 AI 앙상블\n"
        message += f"⚠️ 이변 가능: {upset_count}경기\n"
        message += f"🎰 복수 베팅: {multi_count}경기 ({2**multi_count}조합)\n"

        await self.notifier.send_message(message, parse_mode="Markdown")

        logger.info(f"[TotoTelegram] {game_type} {round_number}회차 요약 전송 완료")
