#!/usr/bin/env python3
"""
분석 결과를 텔레그램으로 전송하는 스크립트

사용법:
    python send_analysis_results.py           # 오늘의 모든 분석 결과
    python send_analysis_results.py --today   # 오늘의 경기만
    python send_analysis_results.py --top 5   # 상위 5개 추천
    python send_analysis_results.py --match 12345  # 특정 경기
"""

import asyncio
import argparse
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

from src.db.session import get_session
from src.db.models import Match
from src.services.telegram_notifier import TelegramNotifier


class AnalysisReporter:
    """분석 결과를 텔레그램으로 전송"""

    def __init__(self):
        self.notifier = TelegramNotifier()

    async def send_today_summary(self) -> bool:
        """오늘의 분석 요약 전송"""
        matches = await self._get_today_matches()

        if not matches:
            await self.notifier.send_message("📅 오늘 분석된 경기가 없습니다.")
            return False

        # 통계 계산
        total_matches = len(matches)
        high_confidence = sum(
            1
            for m in matches
            if m.get("confidence", 0) >= 0.65
        )
        value_picks = sum(
            1
            for m in matches
            if m.get("recommendation") in ["VALUE", "STRONG_VALUE"]
        )

        # 메시지 작성
        msg = f"""
📊 **오늘의 AI 분석 요약**
📅 {datetime.now().strftime("%Y-%m-%d %H:%M")}

🎯 **전체 경기**: {total_matches}경기
💎 **Value Pick**: {value_picks}개
🔒 **고신뢰도 (65%+)**: {high_confidence}개

━━━━━━━━━━━━━━━━━━━━━
"""

        # Top 5 추천 경기 추가
        top_matches = sorted(
            matches,
            key=lambda x: (
                x.get("confidence", 0),
                x.get("edge", 0)
            ),
            reverse=True
        )[:5]

        if top_matches:
            msg += "\n🌟 **Top 5 추천 경기**\n\n"

            for i, match in enumerate(top_matches, 1):
                home_team = match["home_team"]
                away_team = match["away_team"]
                league = match["league"]
                kickoff = match["kickoff_time"].strftime("%H:%M")
                prediction = match.get("prediction", "N/A")
                confidence = match.get("confidence", 0) * 100
                edge = match.get("edge", 0)

                icon = self._get_recommendation_icon(match.get("recommendation"))

                msg += f"**{i}. {home_team} vs {away_team}**\n"
                msg += f"🏆 {league} | ⏰ {kickoff}\n"
                msg += f"{icon} {prediction} (신뢰도: {confidence:.1f}%)\n"

                if edge > 0:
                    msg += f"📈 Edge: {edge:.1f}%\n"

                msg += "\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "_베트맨 스포츠토토 AI 분석 시스템_"

        return await self.notifier.send_message(msg)

    async def send_top_picks(self, limit: int = 5) -> bool:
        """상위 N개 추천 경기 전송"""
        matches = await self._get_today_matches()

        if not matches:
            await self.notifier.send_message("📅 오늘 분석된 경기가 없습니다.")
            return False

        # Value Pick 필터링 및 정렬
        value_matches = [
            m for m in matches
            if m.get("recommendation") in ["VALUE", "STRONG_VALUE"]
        ]

        if not value_matches:
            await self.notifier.send_message("💎 오늘 감지된 Value Pick이 없습니다.")
            return False

        # Edge 기준 정렬
        value_matches.sort(key=lambda x: x.get("edge", 0), reverse=True)
        top_matches = value_matches[:limit]

        msg = f"💎 **Top {len(top_matches)} Value Picks**\n"
        msg += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"

        for i, match in enumerate(top_matches, 1):
            home_team = match["home_team"]
            away_team = match["away_team"]
            league = match["league"]
            kickoff = match["kickoff_time"].strftime("%H:%M")
            prediction = match.get("prediction", "N/A")
            confidence = match.get("confidence", 0) * 100
            edge = match.get("edge", 0)
            stake = match.get("recommended_stake", 0)

            icon = self._get_recommendation_icon(match.get("recommendation"))

            msg += f"**{i}. {home_team} vs {away_team}**\n"
            msg += f"🏆 {league} | ⏰ {kickoff}\n"
            msg += f"{icon} **{prediction}**\n"
            msg += f"🔢 신뢰도: {confidence:.1f}%\n"
            msg += f"📈 Edge: {edge:.1f}%\n"

            if stake > 0:
                msg += f"💰 추천 베팅: {stake:.1f}%\n"

            # 배당 정보
            if match.get("odds"):
                odds = match["odds"]
                msg += f"📊 배당: 홈 {odds.get('home', 0):.2f} | "
                msg += f"무 {odds.get('draw', 0):.2f} | "
                msg += f"원정 {odds.get('away', 0):.2f}\n"

            msg += "\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "_베트맨 스포츠토토 AI 분석 시스템_"

        return await self.notifier.send_message(msg)

    async def send_match_detail(self, match_id: int) -> bool:
        """특정 경기의 상세 분석 전송"""
        match = await self._get_match_detail(match_id)

        if not match:
            await self.notifier.send_message(f"❌ 경기 ID {match_id}를 찾을 수 없습니다.")
            return False

        home_team = match["home_team"]
        away_team = match["away_team"]
        league = match["league"]
        kickoff = match["kickoff_time"].strftime("%Y-%m-%d %H:%M")

        msg = f"""
⚽ **경기 상세 분석**

**{home_team} vs {away_team}**
🏆 {league}
⏰ {kickoff}

━━━━━━━━━━━━━━━━━━━━━
"""

        # AI 예측
        probs = match.get("probs", {})
        if probs:
            msg += "\n🤖 **AI 모델 예측**\n"
            msg += f"🏠 홈 승리: {probs.get('home', 0) * 100:.1f}%\n"
            msg += f"🤝 무승부: {probs.get('draw', 0) * 100:.1f}%\n"
            msg += f"✈️ 원정 승리: {probs.get('away', 0) * 100:.1f}%\n"

        # 배당 정보
        odds = match.get("odds", {})
        if odds:
            msg += "\n📊 **배당 (Pinnacle)**\n"
            msg += f"홈: {odds.get('home', 0):.2f} | "
            msg += f"무: {odds.get('draw', 0):.2f} | "
            msg += f"원정: {odds.get('away', 0):.2f}\n"

        # AI Fair Odds
        ai_odds = match.get("ai_odds", {})
        if ai_odds:
            msg += "\n💡 **AI Fair Odds**\n"
            msg += f"홈: {ai_odds.get('home', 0):.2f} | "
            msg += f"무: {ai_odds.get('draw', 0):.2f} | "
            msg += f"원정: {ai_odds.get('away', 0):.2f}\n"

        # 추천
        recommendation = match.get("recommendation")
        if recommendation:
            icon = self._get_recommendation_icon(recommendation)
            prediction = match.get("prediction", "N/A")
            confidence = match.get("confidence", 0) * 100

            msg += f"\n{icon} **추천: {prediction}**\n"
            msg += f"🔢 신뢰도: {confidence:.1f}%\n"

            edge = match.get("edge", 0)
            if edge > 0:
                msg += f"📈 Edge: {edge:.1f}%\n"

            stake = match.get("recommended_stake", 0)
            if stake > 0:
                msg += f"💰 추천 베팅: {stake:.1f}%\n"

        # 팀 통계 (있는 경우)
        if match.get("team_stats"):
            stats = match["team_stats"]
            msg += "\n📈 **최근 5경기 폼**\n"
            msg += f"🏠 {home_team}: {stats.get('home_form', 'N/A')}\n"
            msg += f"✈️ {away_team}: {stats.get('away_form', 'N/A')}\n"

        msg += "\n━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "_베트맨 스포츠토토 AI 분석 시스템_"

        return await self.notifier.send_message(msg)

    async def send_high_confidence_picks(self, threshold: float = 0.65) -> bool:
        """고신뢰도 픽만 전송"""
        matches = await self._get_today_matches()

        high_confidence = [
            m for m in matches
            if m.get("confidence", 0) >= threshold
        ]

        if not high_confidence:
            await self.notifier.send_message(
                f"🔒 신뢰도 {threshold * 100:.0f}% 이상인 경기가 없습니다."
            )
            return False

        msg = f"🔒 **고신뢰도 픽 ({threshold * 100:.0f}%+)**\n"
        msg += f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"

        for match in high_confidence:
            home_team = match["home_team"]
            away_team = match["away_team"]
            prediction = match.get("prediction", "N/A")
            confidence = match.get("confidence", 0) * 100

            msg += f"⚽ **{home_team} vs {away_team}**\n"
            msg += f"📍 {prediction} ({confidence:.1f}%)\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "_베트맨 스포츠토토 AI 분석 시스템_"

        return await self.notifier.send_message(msg)

    # ===== Helper Methods =====

    async def _get_today_matches(self) -> List[Dict]:
        """오늘의 경기 조회"""
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
                    joinedload(Match.predictions),
                )
                .where(
                    and_(
                        Match.start_time >= start_of_day,
                        Match.start_time <= end_of_day,
                    )
                )
                .order_by(Match.start_time)
            )

            result = await session.execute(stmt)
            matches = result.unique().scalars().all()

            return [self._format_match(match) for match in matches]

    async def _get_match_detail(self, match_id: int) -> Optional[Dict]:
        """특정 경기 상세 조회"""
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

            result = await session.execute(stmt)
            match = result.unique().scalar_one_or_none()

            if not match:
                return None

            return self._format_match(match)

    def _format_match(self, match: Match) -> Dict:
        """경기 데이터를 딕셔너리로 변환"""
        # 최신 예측 가져오기
        pred = match.predictions[-1] if match.predictions else None

        # 기본 정보
        data = {
            "id": match.id,
            "home_team": match.home_team.name,
            "away_team": match.away_team.name,
            "league": match.league.name,
            "kickoff_time": match.start_time,
            "status": match.status,
            "recommendation": match.recommendation,
            "recommended_stake": match.recommended_stake_pct,
        }

        # 배당 정보
        data["odds"] = {
            "home": match.odds_home,
            "draw": match.odds_draw,
            "away": match.odds_away,
        }

        if pred:
            # 예측 확률
            data["probs"] = {
                "home": pred.prob_home,
                "draw": pred.prob_draw,
                "away": pred.prob_away,
            }

            # AI Fair Odds 계산 (확률의 역수)
            data["ai_odds"] = {
                "home": 1 / pred.prob_home if pred.prob_home > 0 else 0,
                "draw": 1 / pred.prob_draw if pred.prob_draw > 0 else 0,
                "away": 1 / pred.prob_away if pred.prob_away > 0 else 0,
            }

            # 가장 높은 확률의 결과 찾기
            max_prob = max(pred.prob_home, pred.prob_draw, pred.prob_away)
            if max_prob == pred.prob_home:
                prediction = "홈 승리"
            elif max_prob == pred.prob_away:
                prediction = "원정 승리"
            else:
                prediction = "무승부"

            data["prediction"] = prediction
            data["confidence"] = max_prob

            # Edge 계산 (Value) - 가장 큰 값 사용
            edges = [
                pred.value_home or 0,
                pred.value_draw or 0,
                pred.value_away or 0
            ]
            data["edge"] = max(edges)

        return data

    def _get_recommendation_icon(self, recommendation: Optional[str]) -> str:
        """추천 등급에 따른 아이콘 반환"""
        if recommendation == "STRONG_VALUE":
            return "💎"
        elif recommendation == "VALUE":
            return "✅"
        else:
            return "ℹ️"


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="분석 결과를 텔레그램으로 전송"
    )
    parser.add_argument(
        "--today",
        action="store_true",
        help="오늘의 모든 분석 결과 요약 전송"
    )
    parser.add_argument(
        "--top",
        type=int,
        metavar="N",
        help="상위 N개 Value Pick 전송"
    )
    parser.add_argument(
        "--match",
        type=int,
        metavar="ID",
        help="특정 경기 ID의 상세 분석 전송"
    )
    parser.add_argument(
        "--high-confidence",
        type=float,
        metavar="THRESHOLD",
        help="고신뢰도 픽 전송 (기본값: 0.65)"
    )

    args = parser.parse_args()

    reporter = AnalysisReporter()

    print("=" * 60)
    print("📱 텔레그램 분석 결과 전송")
    print("=" * 60)
    print()

    try:
        if args.match:
            print(f"📊 경기 ID {args.match} 상세 분석 전송 중...")
            success = await reporter.send_match_detail(args.match)
        elif args.top:
            print(f"💎 Top {args.top} Value Picks 전송 중...")
            success = await reporter.send_top_picks(args.top)
        elif args.high_confidence is not None:
            threshold = args.high_confidence
            print(f"🔒 고신뢰도 픽 ({threshold * 100:.0f}%+) 전송 중...")
            success = await reporter.send_high_confidence_picks(threshold)
        else:
            # 기본값: 오늘의 요약
            print("📊 오늘의 분석 요약 전송 중...")
            success = await reporter.send_today_summary()

        if success:
            print()
            print("✅ 텔레그램 전송 완료!")
            print("📱 텔레그램 앱에서 메시지를 확인하세요.")
        else:
            print()
            print("⚠️ 전송에 문제가 있을 수 있습니다.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
