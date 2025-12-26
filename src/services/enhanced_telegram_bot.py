# src/services/enhanced_telegram_bot.py

"""
통합 텔레그램 봇 - 모든 기능 접근

- Sharp Money 알림
- Arbitrage 기회
- Live Betting 분석
- Kelly Criterion 계산
- 포트폴리오 추적
"""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.db.session import get_session
from src.db.models import Match, Team, League, PredictionLog


class EnhancedBettingBot:
    """
    강화된 베팅 봇 - 모든 기능 통합
    """

    def __init__(
        self,
        token: str,
        sharp_detector,
        arbitrage_detector,
        live_engine,
        kelly_calculator,
        toto_analyzer,
        admin_chat_id: str = None,
    ):
        self.token = token
        self.sharp_detector = sharp_detector
        self.arbitrage_detector = arbitrage_detector
        self.live_engine = live_engine
        self.kelly = kelly_calculator
        self.toto_analyzer = toto_analyzer
        self.admin_chat_id = admin_chat_id

        # 봇 초기화
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    async def broadcast_message(self, text: str):
        """관리자 또는 구독자에게 메시지 전송"""
        if self.admin_chat_id:
            try:
                await self.app.bot.send_message(
                    chat_id=self.admin_chat_id, text=text, parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to broadcast to admin: {e}")
        else:
            print("No admin_chat_id configured for broadcast.")

    def _register_handlers(self):
        """명령어 핸들러 등록"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("menu", self.menu_command))
        self.app.add_handler(CommandHandler("today", self.today_command))
        self.app.add_handler(CommandHandler("top", self.top_picks_command))
        self.app.add_handler(CommandHandler("sharp", self.sharp_command))
        self.app.add_handler(CommandHandler("arb", self.arbitrage_command))
        self.app.add_handler(CommandHandler("live", self.live_command))
        self.app.add_handler(CommandHandler("match", self.match_command))
        self.app.add_handler(CommandHandler("analyze", self.analyze_command))
        self.app.add_handler(CommandHandler("kelly", self.kelly_command))
        self.app.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.app.add_handler(CommandHandler("toto", self.toto_command))
        self.app.add_handler(CommandHandler("soccer", self.soccer_command))
        self.app.add_handler(CommandHandler("basketball", self.basketball_command))
        self.app.add_handler(CommandHandler("proto", self.proto_command))
        self.app.add_handler(CommandHandler("subscribe", self.subscribe_command))

        # 콜백 쿼리 핸들러
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령어"""
        welcome_msg = """
🎯 *베트맨 스포츠토토 AI 분석 봇*

환영합니다! 이 봇은 다음 기능을 제공합니다:

📊 *주요 기능:*
• 축구토토 승무패 AI 분석
• 농구토토 승5패 AI 분석
• 프로토 승부식 AI 분석
• Sharp Money 감지
• Kelly Criterion 스테이킹

📌 *빠른 시작:*
아래 버튼을 클릭하거나 /menu 를 입력하세요!
        """
        # 버튼 메뉴 생성
        keyboard = [
            [
                InlineKeyboardButton("⚽ 축구 승무패", callback_data="game_soccer"),
                InlineKeyboardButton("🏀 농구 승5패", callback_data="game_basketball"),
            ],
            [
                InlineKeyboardButton("📊 프로토 승부식", callback_data="game_proto"),
            ],
            [
                InlineKeyboardButton("📅 오늘의 경기", callback_data="menu_today"),
                InlineKeyboardButton("💎 TOP 추천", callback_data="menu_top"),
            ],
            [
                InlineKeyboardButton("❓ 도움말", callback_data="menu_help"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_msg, parse_mode="Markdown", reply_markup=reply_markup)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """메뉴 버튼 표시"""
        msg = """
🎰 *베트맨 AI 분석 메뉴*

아래 버튼을 클릭하여 원하는 분석을 선택하세요:
        """
        keyboard = [
            [
                InlineKeyboardButton("⚽ 축구 승무패", callback_data="game_soccer"),
                InlineKeyboardButton("🏀 농구 승5패", callback_data="game_basketball"),
            ],
            [
                InlineKeyboardButton("📊 프로토 승부식", callback_data="game_proto"),
            ],
            [
                InlineKeyboardButton("📅 오늘의 경기", callback_data="menu_today"),
                InlineKeyboardButton("💎 TOP 추천", callback_data="menu_top"),
            ],
            [
                InlineKeyboardButton("🎯 Sharp Money", callback_data="menu_sharp"),
                InlineKeyboardButton("💰 Arbitrage", callback_data="menu_arb"),
            ],
            [
                InlineKeyboardButton("❓ 도움말", callback_data="menu_help"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """도움말"""
        help_msg = """
📖 **명령어 가이드**

**경기 정보:**
/today - 오늘의 모든 경기
/top - 최고 Value 베팅 Top 5
/match <id> - 특정 경기 상세 정보

**분석 도구:**
/sharp - Sharp Money 감지된 경기
/arb - Arbitrage 기회 (무위험 수익)
/live - 현재 진행 중인 경기 실시간 분석
/analyze <id> - AI 텍스트 분석

**베팅 관리:**
/kelly <prob> <odds> <bankroll> - 최적 스테이크 계산
  예: /kelly 0.55 2.10 1000
/portfolio - 내 베팅 기록 & 성과

**설정:**
/subscribe - 자동 알림 구독
  • Value Bet 알림 (30분 전)
  • Sharp Money 알림
  • Arbitrage 알림

**예제:**
/match 12345
/kelly 0.52 2.20 1000
/analyze 12345

**승무패 분석:**
/toto
(14경기 리스트 붙여넣기)
        """
        await update.message.reply_text(help_msg, parse_mode="Markdown")

    async def today_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """오늘의 경기 목록"""
        matches = await self._get_today_matches()

        if not matches:
            await update.message.reply_text("📅 오늘 예정된 경기가 없습니다.")
            return

        # 리그별 그룹화
        by_league = {}
        for match in matches:
            league = match["league"]
            if league not in by_league:
                by_league[league] = []
            by_league[league].append(match)

        # 메시지 작성
        msg = f"⚽ **오늘의 경기 ({len(matches)}경기)**\n\n"

        keyboard = []

        for league, league_matches in by_league.items():
            msg += f"🏆 **{league}**\n"

            for match in league_matches:
                time = match["kickoff_time"].strftime("%H:%M")
                value_tag = ""

                if match.get("has_value"):
                    if match.get("edge", 0) > 10:
                        value_tag = "💎 "
                    else:
                        value_tag = "✅ "

                match_label = f"{match['home_team']} vs {match['away_team']}"
                msg += f"{value_tag}`{time}` {match_label}\n"

                # 버튼 추가
                btn_text = f"{value_tag}{time} {match_label}"
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            btn_text, callback_data=f"match_{match['id']}"
                        )
                    ]
                )

            msg += "\n"

        msg += "💎 = 강력 추천 | ✅ = 추천\n"
        msg += "아래 버튼을 클릭하여 상세 정보를 확인하세요."

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            msg, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def sharp_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sharp Money 신호"""
        signals = await self.sharp_detector.get_all_sharp_signals_today()

        if not signals:
            await update.message.reply_text("현재 감지된 Sharp Money 신호가 없습니다.")
            return

        msg = f"🎯 **Sharp Money 신호 ({len(signals)})**\n\n"

        keyboard = []

        for i, signal in enumerate(signals[:5], 1):  # Top 5
            match = await self._get_match_info(signal.match_id)

            msg += f"**{i}. {match['home_team']} vs {match['away_team']}**\n"
            msg += f"방향: **{signal.direction.upper()}**\n"
            msg += f"강도: {signal.signal_strength:.0f}/100 "
            msg += f"| 신뢰도: {signal.confidence * 100:.0f}%\n"
            msg += f"지표:\n"

            for ind in signal.indicators:
                msg += f"  • {ind}\n"

            msg += "─" * 30 + "\n\n"

            # 버튼 추가
            btn_text = f"🎯 {match['home_team']} vs {match['away_team']}"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        btn_text, callback_data=f"match_{signal.match_id}"
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            msg, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def arbitrage_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Arbitrage 기회"""
        matches = await self._get_today_matches()
        opportunities = await self.arbitrage_detector.find_all_arbitrage_opportunities(
            matches
        )

        if not opportunities:
            await update.message.reply_text(
                "현재 Arbitrage(무위험 차익) 기회가 없습니다."
            )
            return

        msg = f"💰 **Arbitrage 기회 ({len(opportunities)})**\n\n"

        for i, arb in enumerate(opportunities[:3], 1):  # Top 3
            msg += f"**{i}. {arb.home_team} vs {arb.away_team}**\n"
            msg += (
                f"수익률: **{arb.profit_margin:.2f}%** (${arb.guaranteed_profit:.2f})\n"
            )
            msg += f"총 베팅액: ${arb.total_stake:.2f}\n\n"

            msg += f"**베팅 조합:**\n"
            for outcome, stake in arb.stakes.items():
                msg += f"• {outcome.upper()}: ${stake['amount']:.2f} "
                msg += f"@ {stake['odds']:.2f} ({stake['bookmaker']})\n"

            msg += "\n" + "─" * 30 + "\n\n"

        msg += "⚠️ 주의: 북메이커 이용 약관을 반드시 확인하세요."

        await update.message.reply_text(msg, parse_mode="Markdown")

    async def live_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """현재 Live 경기 분석"""
        live_matches = await self._get_live_matches()

        if not live_matches:
            await update.message.reply_text("현재 진행 중인 경기가 없습니다.")
            return

        msg = "🔴 **실시간 진행 경기 (LIVE)**\n\n"
        keyboard = []

        for match in live_matches[:5]:  # 최대 5경기
            msg += f"**{match['home_team']} {match['home_score']}-{match['away_score']} {match['away_team']}**\n"
            msg += f"{match['minute']}' | {match['league']}\n"

            # 간단한 분석
            analysis = await self.live_engine.analyze_live_match(
                match_id=match["id"],
                current_score=(match["home_score"], match["away_score"]),
                minute=match["minute"],
                live_stats=match["stats"],
                live_odds=match["live_odds"],
            )

            if analysis.live_value_bets:
                best_bet = analysis.live_value_bets[0]
                msg += f"💎 추천: {best_bet['market']} @ {best_bet['odds']} "
                msg += f"(Edge: {best_bet['edge']}%)\n"

            msg += f"모멘텀: {analysis.momentum.upper()}\n\n"

            # 버튼
            btn_text = f"🔴 {match['home_team']} vs {match['away_team']}"
            keyboard.append(
                [InlineKeyboardButton(btn_text, callback_data=f"match_{match['id']}")]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            msg, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def kelly_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kelly Criterion 계산"""
        # 사용법: /kelly 0.55 2.10 1000
        if len(context.args) != 3:
            await update.message.reply_text(
                "사용법: /kelly <승률> <배당> <자본금>\n예: /kelly 0.55 2.10 1000"
            )
            return

        try:
            win_prob = float(context.args[0])
            odds = float(context.args[1])
            bankroll = float(context.args[2])

            # 유효성 검사
            if not (0 < win_prob < 1):
                await update.message.reply_text("승률은 0과 1 사이여야 합니다.")
                return

            if odds < 1.01:
                await update.message.reply_text("배당은 1.01 이상이어야 합니다.")
                return

            # Kelly 계산
            rec = self.kelly.calculate_stake(win_prob, odds, bankroll)

            msg = f"📊 **Kelly Criterion 분석**\n\n"
            msg += f"입력 데이터:\n"
            msg += f"• 승률: {win_prob * 100:.1f}%\n"
            msg += f"• 배당: {odds:.2f}\n"
            msg += f"• 자본금: ${bankroll:.2f}\n\n"

            if rec.recommended_stake == 0:
                msg += "❌ **베팅 권장 안함**\n"
                msg += "Edge가 부족하거나 음수입니다."
            else:
                msg += f"✅ **권장 베팅액: ${rec.recommended_stake:.2f}**\n"
                msg += f"Kelly 비율: {rec.kelly_percentage:.2f}%\n"
                msg += f"기대 수익: ${rec.expected_value:.2f}\n"
                msg += f"예상 ROI: {rec.expected_roi:.2f}%\n"
                msg += f"리스크 수준: {rec.risk_level}\n"
                msg += f"최대 손실: ${rec.max_loss:.2f}\n\n"

                msg += f"📈 Full Kelly: ${rec.full_kelly_stake:.2f}\n"
                msg += f"🎯 1/4 Kelly: ${rec.fractional_kelly_stake:.2f}\n"

            await update.message.reply_text(msg, parse_mode="Markdown")

        except ValueError:
            await update.message.reply_text("잘못된 숫자 형식입니다.")

    async def portfolio_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """포트폴리오 조회"""
        user_id = update.effective_user.id

        # 포트폴리오 데이터 가져오기
        portfolio = await self._get_user_portfolio(user_id)

        msg = f"📊 **나의 포트폴리오**\n\n"
        msg += f"💰 **자산 현황 (Bankroll)**\n"
        msg += f"현재: ${portfolio['current_bankroll']:.2f}\n"
        msg += f"성장률: {portfolio['bankroll_growth']:+.2f}%\n\n"

        msg += f"📈 **성과 지표**\n"
        msg += f"총 베팅: {portfolio['total_bets']}회\n"
        msg += f"승률: {portfolio['win_rate']:.1f}%\n"
        msg += f"ROI: {portfolio['roi']:+.2f}%\n"
        msg += f"순이익: ${portfolio['net_profit']:+.2f}\n\n"

        msg += f"🎯 **연속 기록**\n"
        msg += f"최장 연승: {portfolio['longest_win_streak']}연승\n"
        msg += f"최장 연패: {portfolio['longest_loss_streak']}연패\n"
        msg += f"현재 상태: {portfolio['current_streak']}\n\n"

        msg += f"💵 **베팅 규모**\n"
        msg += f"총 베팅액: ${portfolio['total_staked']:.2f}\n"
        msg += f"평균 베팅액: ${portfolio['avg_stake']:.2f}\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    async def match_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """특정 경기 상세 정보"""
        if not context.args:
            await update.message.reply_text("사용법: /match <경기ID>")
            return

        try:
            match_id = int(context.args[0])
            await self._send_match_detail(update, match_id)

        except ValueError:
            await update.message.reply_text("잘못된 경기 ID 형식입니다.")

    async def _send_match_detail(self, update_or_query, match_id: int):
        """경기 상세 정보 전송 (공통 메서드)"""
        match = await self._get_match_details(match_id)

        # 메시지를 보낼 대상 확인 (Update 또는 CallbackQuery)
        if hasattr(update_or_query, "message"):
            message_obj = update_or_query.message
        else:
            # CallbackQuery의 경우
            message_obj = update_or_query.message

        if not match:
            await message_obj.reply_text("경기를 찾을 수 없습니다.")
            return

        msg = f"⚽ **{match['home_team']} vs {match['away_team']}**\n"
        msg += f"🏆 {match['league']}\n"
        msg += f"⏰ {match['kickoff_time'].strftime('%Y-%m-%d %H:%M')}\n\n"

        msg += f"📊 **배당 (Pinnacle)**\n"
        msg += f"홈: {match['odds']['home']:.2f} | "
        msg += f"무: {match['odds']['draw']:.2f} | "
        msg += f"원정: {match['odds']['away']:.2f}\n\n"

        msg += f"🤖 **AI 모델 예측**\n"
        msg += f"홈 승: {match['pred']['home']:.1f}% | "
        msg += f"무승부: {match['pred']['draw']:.1f}% | "
        msg += f"원정 승: {match['pred']['away']:.1f}%\n\n"

        if match.get("value_picks"):
            msg += f"💎 **Value Picks (추천)**\n"
            for pick in match["value_picks"]:
                msg += f"• {pick['outcome']}: Edge {pick['edge']:.1f}%\n"
            msg += "\n"

        # 버튼 추가
        keyboard = [
            [
                InlineKeyboardButton(
                    "🧠 AI 심층 분석", callback_data=f"analyze_{match_id}"
                ),
                InlineKeyboardButton(
                    "💰 Kelly 계산", callback_data=f"kelly_{match_id}"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message_obj.reply_text(
            msg, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def subscribe_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """알림 구독"""
        user_id = update.effective_user.id

        # 사용자를 구독자 목록에 추가
        await self._add_subscriber(user_id)

        msg = """
✅ **알림 구독 완료!**

다음 알림을 받게 됩니다:

🔔 **자동 알림:**
• Value Bet (킥오프 1시간 전)
• Sharp Money 감지
• Arbitrage 기회
• Live Value (진행 중 경기)

📊 **알림 조건:**
• Value: Edge 5% 이상
• Strong Value: Edge 10% 이상
• Sharp: 신호 강도 60+
• Arbitrage: 수익률 1% 이상

구독 취소: /unsubscribe
        """

        await update.message.reply_text(msg, parse_mode="Markdown")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """인라인 버튼 콜백"""
        query = update.callback_query
        await query.answer()

        data = query.data

        # 게임 타입 버튼
        if data == "game_soccer":
            await self._send_soccer_analysis(query)
        elif data == "game_basketball":
            await self._send_basketball_analysis(query)
        elif data == "game_proto":
            await self._send_proto_analysis(query)

        # 메뉴 버튼
        elif data == "menu_today":
            await self._send_today_matches_inline(query)
        elif data == "menu_top":
            await self._send_top_picks_inline(query)
        elif data == "menu_sharp":
            await self._send_sharp_inline(query)
        elif data == "menu_arb":
            await self._send_arb_inline(query)
        elif data == "menu_help":
            await self._send_help_inline(query)

        elif data.startswith("analyze_"):
            match_id = int(data.split("_")[1])
            # AI 분석 실행
            await self._send_ai_analysis(query, match_id)

        elif data.startswith("kelly_"):
            match_id = int(data.split("_")[1])
            # Kelly 계산 안내
            await query.message.reply_text(
                f"Kelly 계산을 원하시면 다음 명령어를 입력하세요:\n"
                f"/kelly <승률> <배당> <자본금>\n"
                f"예: /kelly 0.55 2.10 1000"
            )

        elif data.startswith("match_"):
            match_id = int(data.split("_")[1])
            await self._send_match_detail(query, match_id)

    # ===== 자동 알림 =====

    async def send_value_alert(self, match: dict, value_pick: dict = None):
        """Value Bet 자동 알림"""
        if value_pick is None and match.get("value_picks"):
            value_pick = match["value_picks"][0]

        if not value_pick:
            return

        subscribers = await self._get_subscribers()

        msg = f"""
💎 **VALUE BET ALERT**

{match["home_team"]} vs {match["away_team"]}
🏆 {match["league"]}
⏰ {match["kickoff_time"].strftime("%H:%M")} (1시간 후)

**Value Pick:**
{value_pick["outcome"].upper()}
배당: {value_pick["odds"]:.2f}
모델 확률: {value_pick["model_prob"]:.1f}%
Edge: {value_pick["edge"]:.1f}%

/match {match["id"]}
        """

        for user_id in subscribers:
            try:
                await self.app.bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to send to {user_id}: {e}")

    # ===== Helper Methods =====

    async def _get_today_matches(self):
        """오늘 경기 조회 (DB 연동)"""
        today = datetime.now().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        async with get_session() as session:
            stmt = (
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.league),
                )
                .where(Match.start_time >= start_of_day, Match.start_time <= end_of_day)
                .order_by(Match.start_time)
            )
            result = await session.execute(stmt)
            matches = result.scalars().all()

            if not matches:
                return []

            match_list = []
            for m in matches:
                # Value Pick Logic (Simple check for now)
                has_value = m.recommendation in ["VALUE", "STRONG_VALUE"]
                value_pick = None
                edge = 0.0

                # If we have a prediction log, use it
                # This is a simplification; ideally we fetch the latest prediction

                match_data = {
                    "id": m.id,
                    "home_team": m.home_team.name,  # Assuming names are translated or we use English
                    "away_team": m.away_team.name,
                    "league": m.league.name,
                    "kickoff_time": m.start_time,
                    "has_value": has_value,
                    "edge": m.predictions[0].value_home
                    if m.predictions and m.predictions[0].value_home
                    else 0,  # Placeholder logic
                    "value_pick": "홈 승" if has_value else None,  # Placeholder
                    "odds": m.odds_home,
                    "stake": m.recommended_stake_pct,
                }
                match_list.append(match_data)

            return match_list

    async def _get_match_info(self, match_id: int):
        """경기 정보 조회 (DB 연동)"""
        async with get_session() as session:
            stmt = (
                select(Match)
                .options(joinedload(Match.home_team), joinedload(Match.away_team))
                .where(Match.id == match_id)
            )
            match = await session.scalar(stmt)

            if not match:
                return None

            return {
                "id": match.id,
                "home_team": match.home_team.name,
                "away_team": match.away_team.name,
                "league": match.league.name if match.league else "Unknown",
                "kickoff_time": match.start_time,
                "home_score": match.score_home if match.score_home is not None else 0,
                "away_score": match.score_away if match.score_away is not None else 0,
                "minute": 0,  # Live data needed for minute
            }

    async def _get_match_details(self, match_id: int):
        """경기 상세 정보 (DB 연동)"""
        async with get_session() as session:
            stmt = (
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.league),
                    joinedload(Match.predictions),
                )
                .where(Match.id == match_id)
            )
            match = await session.scalar(stmt)

            if not match:
                return None

            # Latest prediction
            pred = match.predictions[-1] if match.predictions else None

            return {
                "id": match.id,
                "home_team": match.home_team.name,
                "away_team": match.away_team.name,
                "league": match.league.name,
                "kickoff_time": match.start_time,
                "odds": {
                    "home": match.odds_home or 0.0,
                    "draw": match.odds_draw or 0.0,
                    "away": match.odds_away or 0.0,
                },
                "pred": {
                    "home": (pred.prob_home * 100) if pred else 0.0,
                    "draw": (pred.prob_draw * 100) if pred else 0.0,
                    "away": (pred.prob_away * 100) if pred else 0.0,
                },
                "value_picks": [{"outcome": "홈 승", "edge": pred.value_home}]
                if pred and pred.value_home and pred.value_home > 0
                else [],
            }

    async def _get_live_matches(self):
        """Live 경기 조회 (구현 필요)"""
        pass

    async def send_lineup_alert(self, match_id: int, analysis: dict):
        """선발 라인업 확정 및 재분석 알림 전송"""
        try:
            home_team = analysis.get("home_team", "Home")
            away_team = analysis.get("away_team", "Away")

            msg = (
                f"🚨 **선발 라인업 확정 & 긴급 분석** 🚨\n\n"
                f"⚽ **{home_team} vs {away_team}**\n"
                f"✅ 선발 명단이 제출되어 AI가 재분석을 완료했습니다.\n\n"
            )

            if analysis.get("recommendation") and "VALUE" in analysis["recommendation"]:
                msg += (
                    f"💎 **가치 투자 기회 포착!**\n"
                    f"👉 추천: {analysis.get('value_pick')}\n"
                    f"📈 기대 승률: {analysis.get('win_prob', 0):.1f}%\n"
                    f"💰 권장 베팅: {analysis.get('stake', 0):.1f}%\n"
                )
            else:
                msg += "ℹ️ 특이 사항 없음 (Skip)\n"

            msg += f"\n⏰ 경기 시작: {analysis.get('kickoff_time')}"

            # Inline Button
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📊 상세 분석 보기", callback_data=f"match_{match_id}"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await self.app.bot.send_message(
                chat_id=self.admin_chat_id,
                text=msg,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
        except Exception as e:
            print(f"Failed to send lineup alert: {e}")

    async def _get_user_portfolio(self, user_id: int):
        """사용자 포트폴리오 (구현 필요)"""
        # Placeholder implementation
        return {
            "current_bankroll": 1250.00,
            "bankroll_growth": 25.00,
            "total_bets": 50,
            "win_rate": 60.0,
            "roi": 15.00,
            "net_profit": 150.00,
            "longest_win_streak": 7,
            "longest_loss_streak": 3,
            "current_streak": "Win 2",
            "total_staked": 1000.00,
            "avg_stake": 20.00,
        }

    async def _add_subscriber(self, user_id: int):
        """구독자 추가 (구현 필요)"""
        print(f"User {user_id} subscribed.")
        pass

    async def _get_subscribers(self):
        """구독자 목록 (구현 필요)"""
        # Placeholder: return a dummy list of user IDs
        return [123456789, 987654321]

    async def top_picks_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """최고 Value Picks 조회"""
        matches = await self._get_today_matches()
        if not matches:
            await update.message.reply_text("오늘 등록된 경기가 없습니다.")
            return

        # Value가 있는 경기만 필터링
        value_matches = [m for m in matches if m.get("has_value")]
        # Edge 기준 정렬 (내림차순)
        value_matches.sort(key=lambda x: x.get("edge", 0), reverse=True)

        if not value_matches:
            await update.message.reply_text("현재 감지된 Value Pick이 없습니다.")
            return

        msg = "💎 **TOP VALUE PICKS (최고 추천)**\n\n"
        keyboard = []

        for i, match in enumerate(value_matches[:5], 1):
            msg += f"**{i}. {match['home_team']} vs {match['away_team']}**\n"
            msg += f"픽: **{match['value_pick']}** @ {match['odds']}\n"
            msg += f"Edge: {match['edge']:.1f}% | 추천 금액: {match['stake']}%\n"
            msg += f"/match {match['id']}\n\n"

            # 버튼 추가
            btn_text = f"💎 {match['home_team']} vs {match['away_team']}"
            keyboard.append(
                [InlineKeyboardButton(btn_text, callback_data=f"match_{match['id']}")]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            msg, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """AI 분석 요청"""
        if not context.args:
            await update.message.reply_text("사용법: /analyze <경기ID>")
            return

        try:
            match_id = int(context.args[0])
            await update.message.reply_text(
                "🤖 AI가 경기를 정밀 분석 중입니다... 잠시만 기다려주세요."
            )
            # AI 분석 실행 (기존 로직)
            # 여기서는 예시로 간단히 처리
            await self._send_ai_analysis(update, match_id)

        except ValueError:
            await update.message.reply_text("잘못된 경기 ID 형식입니다.")
        except Exception as e:
            await update.message.reply_text(f"분석 중 오류 발생: {str(e)}")

    async def toto_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """승무패 14경기 분석"""
        # 사용자가 메시지와 함께 텍스트를 보냈는지 확인
        # 커맨드 뒤에 텍스트가 있으면 그것을 사용
        # 없으면 안내 메시지 전송

        if not context.args:
            msg = """
🎰 **승무패 14경기 분석기**

분석할 14경기 리스트를 아래 형식으로 입력해주세요:

`/toto
1. 맨시티 vs 첼시
2. 아스널 vs 리버풀
...`

(팀 이름 사이에는 'vs' 또는 공백이 있어야 합니다)
            """
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

        # 텍스트 복원 (args는 공백으로 분리되므로 다시 합침)
        # 하지만 /toto 뒤의 줄바꿈을 포함한 전체 텍스트를 가져오는 게 좋음
        # update.message.text 에서 '/toto'를 제외한 나머지 부분 추출
        full_text = update.message.text
        # /toto 제거
        input_text = full_text.replace("/toto", "").strip()

        if not input_text:
            await update.message.reply_text("❌ 경기 목록을 입력해주세요.")
            return

        await update.message.reply_text(
            "🤖 AI가 14경기를 정밀 분석 중입니다... (약 10초 소요)"
        )

        try:
            report = await self.toto_analyzer.analyze_14_games(input_text)
            await update.message.reply_text(report, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ 분석 중 오류 발생: {str(e)}")
            await update.message.reply_text(
                "🤖 AI가 경기를 정밀 분석 중입니다... 잠시만 기다려주세요."
            )
            # 실제 분석 로직은 _send_ai_analysis에서 처리
            await self._send_ai_analysis(update, match_id)
        except ValueError:
            await update.message.reply_text("잘못된 경기 ID 형식입니다.")

    async def send_sharp_alert(self, signal):
        """Sharp Money 알림 전송"""
        subscribers = await self._get_subscribers()
        match = await self._get_match_info(signal.match_id)

        msg = f"""
🎯 **SHARP MONEY ALERT (전문가 자금 포착)**

{match["home_team"]} vs {match["away_team"]}
방향: **{signal.direction.upper()}**
강도: {signal.signal_strength:.0f}/100
시간: {datetime.now().strftime("%H:%M")}

/match {signal.match_id} 로 상세 확인
        """

        for user_id in subscribers:
            try:
                await self.app.bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="Markdown"
                )
            except Exception:
                pass

    async def send_arbitrage_alert(self, arb):
        """Arbitrage 알림 전송"""
        subscribers = await self._get_subscribers()

        msg = f"""
💰 **ARBITRAGE ALERT (무위험 차익 기회)**

{arb.home_team} vs {arb.away_team}
수익률: **{arb.profit_margin:.2f}%**
확정 수익: ${arb.guaranteed_profit:.2f}

/arb 명령어로 확인하세요!
        """

        for user_id in subscribers:
            try:
                await self.app.bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="Markdown"
                )
            except Exception:
                pass

    async def send_live_alert(self, analysis):
        """Live Value 알림 전송"""
        subscribers = await self._get_subscribers()
        match = await self._get_match_info(analysis.match_id)

        msg = f"""
🔴 **LIVE VALUE ALERT (실시간 추천)**

{match["home_team"]} vs {match["away_team"]}
스코어: {match["home_score"]}-{match["away_score"]} ({match["minute"]}분)

모멘텀: {analysis.momentum.upper()}
추천: {analysis.live_value_bets[0]["market"]} @ {analysis.live_value_bets[0]["odds"]}

/live 명령어로 확인하세요!
        """

        for user_id in subscribers:
            try:
                await self.app.bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="Markdown"
                )
            except Exception:
                pass

    async def _send_ai_analysis(self, query, match_id: int):
        """AI 분석 전송 (구현 필요)"""
        pass

    # ===== 게임 타입별 분석 =====

    async def soccer_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """축구 승무패 분석 명령어"""
        await update.message.reply_text("⚽ 축구 승무패 분석 데이터를 불러오는 중...")
        await self._send_soccer_analysis_message(update.message)

    async def basketball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """농구 승5패 분석 명령어"""
        await update.message.reply_text("🏀 농구 승5패 분석 데이터를 불러오는 중...")
        await self._send_basketball_analysis_message(update.message)

    async def proto_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """프로토 승부식 분석 명령어"""
        await update.message.reply_text("📊 프로토 승부식 분석 데이터를 불러오는 중...")
        await self._send_proto_analysis_message(update.message)

    async def _send_soccer_analysis(self, query):
        """축구 승무패 분석 (버튼 콜백)"""
        await query.message.reply_text("⚽ 축구 승무패 분석 데이터를 불러오는 중...")
        await self._send_soccer_analysis_message(query.message)

    async def _send_basketball_analysis(self, query):
        """농구 승5패 분석 (버튼 콜백)"""
        await query.message.reply_text("🏀 농구 승5패 분석 데이터를 불러오는 중...")
        await self._send_basketball_analysis_message(query.message)

    async def _send_proto_analysis(self, query):
        """프로토 승부식 분석 (버튼 콜백)"""
        await query.message.reply_text("📊 프로토 승부식 분석 데이터를 불러오는 중...")
        await self._send_proto_analysis_message(query.message)

    async def _send_soccer_analysis_message(self, message):
        """축구 승무패 분석 메시지 전송"""
        from datetime import timedelta

        matches = await self._get_matches_by_category("축구 승무패", days_ahead=7)

        if not matches:
            msg = "⚽ 현재 예정된 축구 승무패 경기가 없습니다.\n(축구토토 승무패는 비시즌 또는 발매 대기 중일 수 있습니다)"
            await message.reply_text(msg)
            return

        # 회차별 그룹화
        by_round = {}
        for m in matches:
            round_num = m.get("round_number", 0)
            if round_num not in by_round:
                by_round[round_num] = []
            by_round[round_num].append(m)

        for round_num, round_matches in sorted(by_round.items(), reverse=True):
            msg = self._format_soccer_message(round_num, round_matches)
            await message.reply_text(msg, parse_mode="Markdown")

    async def _send_basketball_analysis_message(self, message):
        """농구 승5패 분석 메시지 전송"""
        matches = await self._get_matches_by_category("농구 승5패", days_ahead=7)

        if not matches:
            msg = "🏀 현재 예정된 농구 승5패 경기가 없습니다."
            await message.reply_text(msg)
            return

        # 회차별 그룹화
        by_round = {}
        for m in matches:
            round_num = m.get("round_number", 0)
            if round_num not in by_round:
                by_round[round_num] = []
            by_round[round_num].append(m)

        for round_num, round_matches in sorted(by_round.items(), reverse=True)[:2]:  # 최근 2회차
            msg = self._format_basketball_message(round_num, round_matches)
            await message.reply_text(msg, parse_mode="Markdown")

    async def _send_proto_analysis_message(self, message):
        """프로토 승부식 분석 메시지 전송"""
        matches = await self._get_matches_by_category("프로토 승부식", days_ahead=7)

        if not matches:
            msg = "📊 현재 예정된 프로토 승부식 경기가 없습니다."
            await message.reply_text(msg)
            return

        # 회차별 그룹화
        by_round = {}
        for m in matches:
            round_num = m.get("round_number", 0)
            if round_num not in by_round:
                by_round[round_num] = []
            by_round[round_num].append(m)

        for round_num, round_matches in sorted(by_round.items(), reverse=True)[:2]:  # 최근 2회차
            msg = self._format_proto_message(round_num, round_matches[:15])  # 최대 15경기
            await message.reply_text(msg, parse_mode="Markdown")

    async def _get_matches_by_category(self, category: str, days_ahead: int = 7):
        """카테고리별 경기 조회 (종목 타입도 확인, 축구/농구는 14경기만)"""
        from datetime import timedelta
        from sqlalchemy import and_

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
            # 기본 조건
            conditions = [
                Match.category_name == category,
                Match.start_time >= now,
                Match.start_time <= end_date,
            ]

            # 종목 타입 필터 추가 (프로토 제외)
            if expected_sport:
                conditions.append(Match.sport_type == expected_sport)

            # 농구 승5패는 game_number 기준 정렬, 나머지는 시간 기준
            if category == "농구 승5패":
                stmt = (
                    select(Match)
                    .options(
                        joinedload(Match.home_team),
                        joinedload(Match.away_team),
                        joinedload(Match.predictions),
                    )
                    .where(and_(*conditions))
                    .order_by(Match.round_number.desc(), Match.game_number.asc())
                )
            else:
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

            formatted = [self._format_match_for_display(m) for m in matches]

            # 축구 승무패, 농구 승5패는 가장 가까운 회차의 14경기만 반환
            if category in ["축구 승무패", "농구 승5패"] and formatted:
                # 가장 가까운 회차 찾기 (start_time 기준 가장 빠른 경기의 회차)
                formatted.sort(key=lambda x: x["start_time"])
                target_round = formatted[0]["round_number"]

                # 해당 회차 경기만 필터 (최대 14경기)
                same_round = [m for m in formatted if m["round_number"] == target_round]
                same_round.sort(key=lambda x: (x.get("game_number") or 999, x["start_time"]))
                return same_round[:14]

            return formatted

    def _format_match_for_display(self, match: Match) -> dict:
        """경기 데이터 표시용 포맷"""
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
            data["mark"] = "-"
            data["confidence"] = 0

        return data

    def _format_soccer_message(self, round_num: int, matches: list) -> str:
        """축구 승무패 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = f"⚽ *축구토토 승무패 {round_num}회차*\n"
        msg += f"📅 {now_str}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

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

    def _format_basketball_message(self, round_num: int, matches: list) -> str:
        """농구 승5패 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = f"🏀 *농구토토 승5패 {round_num}회차*\n"
        msg += f"📅 {now_str}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

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

    def _format_proto_message(self, round_num: int, matches: list) -> str:
        """프로토 승부식 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = f"📊 *프로토 승부식 {round_num}회차*\n"
        msg += f"📅 {now_str}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

        high_conf = []
        medium_conf = []

        for i, m in enumerate(matches[:15], 1):
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

            msg += f"*{i:02d}. {home} vs {away}*\n"
            msg += f"⏰ {kick_time}\n"
            msg += f"{icon} *[{mark}] {pred}* ({conf*100:.1f}%)\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"💎 *고신뢰도 (65%+)*: {len(high_conf)}경기\n"
        msg += f"✅ *중신뢰도 (55-65%)*: {len(medium_conf)}경기\n"

        if high_conf:
            msg += f"\n💎 추천: {', '.join(map(str, high_conf))}\n"

        msg += "\n_베트맨 스포츠토토 AI 분석 시스템_"

        return msg

    # ===== 메뉴 버튼 콜백 핸들러 =====

    async def _send_today_matches_inline(self, query):
        """오늘의 경기 (인라인)"""
        matches = await self._get_today_matches()

        if not matches:
            await query.message.reply_text("📅 오늘 예정된 경기가 없습니다.")
            return

        msg = f"⚽ *오늘의 경기 ({len(matches)}경기)*\n\n"

        for match in matches[:10]:
            time_str = match["kickoff_time"].strftime("%H:%M")
            value_tag = "💎 " if match.get("has_value") else ""
            msg += f"{value_tag}`{time_str}` {match['home_team']} vs {match['away_team']}\n"

        await query.message.reply_text(msg, parse_mode="Markdown")

    async def _send_top_picks_inline(self, query):
        """TOP 추천 (인라인)"""
        matches = await self._get_today_matches()
        value_matches = [m for m in matches if m.get("has_value")]
        value_matches.sort(key=lambda x: x.get("edge", 0), reverse=True)

        if not value_matches:
            await query.message.reply_text("현재 감지된 Value Pick이 없습니다.")
            return

        msg = "💎 *TOP VALUE PICKS*\n\n"
        for i, m in enumerate(value_matches[:5], 1):
            msg += f"*{i}. {m['home_team']} vs {m['away_team']}*\n"
            msg += f"Edge: {m.get('edge', 0):.1f}%\n\n"

        await query.message.reply_text(msg, parse_mode="Markdown")

    async def _send_sharp_inline(self, query):
        """Sharp Money (인라인)"""
        await query.message.reply_text("🎯 Sharp Money 기능은 /sharp 명령어를 사용해주세요.")

    async def _send_arb_inline(self, query):
        """Arbitrage (인라인)"""
        await query.message.reply_text("💰 Arbitrage 기능은 /arb 명령어를 사용해주세요.")

    async def _send_help_inline(self, query):
        """도움말 (인라인)"""
        help_msg = """
📖 *명령어 가이드*

*토토/프로토 분석:*
/soccer - 축구 승무패 분석
/basketball - 농구 승5패 분석
/proto - 프로토 승부식 분석
/menu - 메뉴 보기

*경기 정보:*
/today - 오늘의 경기
/top - 최고 추천 경기
/match <id> - 상세 정보

*베팅 관리:*
/kelly <승률> <배당> <자본금>
/portfolio - 내 포트폴리오

*알림:*
/subscribe - 자동 알림 구독
        """
        await query.message.reply_text(help_msg, parse_mode="Markdown")

    def run(self):
        """봇 실행"""
        self.app.run_polling()
