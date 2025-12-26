#!/usr/bin/env python3
"""
프로토/토토 분석 결과를 텔레그램으로 전송하는 스크립트
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload

from dotenv import load_dotenv
load_dotenv()

from src.db.session import get_session
from src.db.models import Match
from src.services.telegram_notifier import TelegramNotifier


class TotoProtoReporter:
    """프로토/토토 분석 결과를 텔레그램으로 전송"""

    def __init__(self):
        self.notifier = TelegramNotifier()

    async def send_proto_results(self, days_ahead: int = 7) -> bool:
        """프로토 승부식 분석 결과 전송"""
        matches = await self._get_proto_matches(days_ahead)

        if not matches:
            await self.notifier.send_message("📅 예정된 프로토 경기가 없습니다.")
            return False

        # 회차별로 그룹화
        by_round = {}
        for match in matches:
            round_num = match.get("round_number", "미정")
            if round_num not in by_round:
                by_round[round_num] = []
            by_round[round_num].append(match)

        # 각 회차별로 메시지 생성
        for round_num, round_matches in sorted(by_round.items()):
            msg = await self._format_proto_message(round_num, round_matches)
            await self.notifier.send_message(msg)
            await asyncio.sleep(1)  # 메시지 간 간격

        return True

    async def send_toto_soccer_results(self, days_ahead: int = 7) -> bool:
        """축구토토 승무패 분석 결과 전송"""
        matches = await self._get_toto_soccer_matches(days_ahead)

        if not matches:
            await self.notifier.send_message("📅 예정된 축구토토 승무패 경기가 없습니다.")
            return False

        msg = await self._format_toto_soccer_message(matches)
        return await self.notifier.send_message(msg)

    async def send_basketball_results(self, days_ahead: int = 7) -> bool:
        """농구토토 승5패 분석 결과 전송"""
        matches = await self._get_basketball_matches(days_ahead)

        if not matches:
            await self.notifier.send_message("📅 예정된 농구토토 경기가 없습니다.")
            return False

        msg = await self._format_basketball_message(matches)
        return await self.notifier.send_message(msg)

    async def send_all_toto_proto(self, days_ahead: int = 7) -> bool:
        """모든 토토/프로토 분석 결과 전송"""
        print("📊 프로토 승부식 전송 중...")
        await self.send_proto_results(days_ahead)
        await asyncio.sleep(2)

        print("⚽ 축구토토 승무패 전송 중...")
        await self.send_toto_soccer_results(days_ahead)
        await asyncio.sleep(2)

        print("🏀 농구토토 승5패 전송 중...")
        await self.send_basketball_results(days_ahead)

        return True

    # ===== 데이터 조회 =====

    async def _get_proto_matches(self, days_ahead: int) -> List[Dict]:
        """프로토 승부식 경기 조회"""
        return await self._get_matches_by_category(
            ["프로토 승부식"],
            days_ahead
        )

    async def _get_toto_soccer_matches(self, days_ahead: int) -> List[Dict]:
        """축구토토 승무패 경기 조회"""
        return await self._get_matches_by_category(
            ["축구 승무패"],
            days_ahead
        )

    async def _get_basketball_matches(self, days_ahead: int) -> List[Dict]:
        """농구토토 승5패 경기 조회"""
        return await self._get_matches_by_category(
            ["농구 승5패"],
            days_ahead
        )

    async def _get_matches_by_category(
        self,
        categories: List[str],
        days_ahead: int
    ) -> List[Dict]:
        """카테고리별 경기 조회 (축구/농구는 14경기만)"""
        now = datetime.now()
        end_date = now + timedelta(days=days_ahead)

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
                        Match.category_name.in_(categories),
                        Match.start_time >= now,
                        Match.start_time <= end_date,
                    )
                )
                .order_by(Match.round_number.desc(), Match.start_time)
            )

            result = await session.execute(stmt)
            matches = result.unique().scalars().all()

            formatted = [self._format_match(match) for match in matches]

            # 축구 승무패, 농구 승5패는 가장 가까운 회차의 14경기만 반환
            if any(cat in ["축구 승무패", "농구 승5패"] for cat in categories) and formatted:
                # 가장 가까운 회차 찾기 (start_time 기준 가장 빠른 경기의 회차)
                formatted.sort(key=lambda x: x["kickoff_time"])
                target_round = formatted[0]["round_number"]

                # 해당 회차 경기만 필터 (최대 14경기)
                same_round = [m for m in formatted if m["round_number"] == target_round]
                same_round.sort(key=lambda x: x["kickoff_time"])
                return same_round[:14]

            return formatted

    def _format_match(self, match: Match) -> Dict:
        """경기 데이터를 딕셔너리로 변환"""
        pred = match.predictions[-1] if match.predictions else None

        data = {
            "id": match.id,
            "home_team": match.home_team.name,
            "away_team": match.away_team.name,
            "league": match.league.name if match.league else "리그 미정",
            "kickoff_time": match.start_time,
            "product_name": match.product_name,
            "category_name": match.category_name,
            "round_number": match.round_number,
            "sport_type": match.sport_type,
            "recommendation": match.recommendation,
        }

        if pred:
            data["probs"] = {
                "home": pred.prob_home,
                "draw": pred.prob_draw,
                "away": pred.prob_away,
            }

            # 최고 확률 예측
            max_prob = max(pred.prob_home, pred.prob_draw, pred.prob_away)
            if max_prob == pred.prob_home:
                prediction = "홈 승리"
                mark = "1"
            elif max_prob == pred.prob_away:
                prediction = "원정 승리"
                mark = "2"
            else:
                prediction = "무승부"
                mark = "X"

            data["prediction"] = prediction
            data["mark"] = mark
            data["confidence"] = max_prob

        return data

    # ===== 메시지 포맷 =====

    async def _format_proto_message(
        self,
        round_number: int,
        matches: List[Dict]
    ) -> str:
        """프로토 승부식 메시지 포맷"""
        msg = f"""
⚽ **프로토 승부식 {round_number}회차**
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━

"""

        high_confidence = []
        medium_confidence = []
        low_confidence = []

        for i, match in enumerate(matches, 1):
            home = match["home_team"]
            away = match["away_team"]
            league = match.get("league", "")
            kickoff = match["kickoff_time"].strftime("%m/%d %H:%M")

            confidence = match.get("confidence", 0)
            prediction = match.get("prediction", "분석 중")
            mark = match.get("mark", "-")
            recommendation = match.get("recommendation")

            # 아이콘 선택
            if recommendation == "STRONG_VALUE":
                icon = "💎"
            elif recommendation == "VALUE":
                icon = "✅"
            else:
                icon = "ℹ️"

            # 신뢰도별 분류
            if confidence >= 0.65:
                high_confidence.append(i)
            elif confidence >= 0.55:
                medium_confidence.append(i)
            else:
                low_confidence.append(i)

            msg += f"**{i:02d}. {home} vs {away}**\n"
            msg += f"🏆 {league} | ⏰ {kickoff}\n"
            msg += f"{icon} 예측: **[{mark}] {prediction}** ({confidence*100:.1f}%)\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"🔒 **고신뢰도 (65%+)**: {len(high_confidence)}경기\n"
        msg += f"📊 **중신뢰도 (55-65%)**: {len(medium_confidence)}경기\n"
        msg += f"⚠️ **저신뢰도 (55% 미만)**: {len(low_confidence)}경기\n\n"

        if high_confidence:
            msg += f"💎 추천 경기: {', '.join(map(str, high_confidence))}\n\n"

        msg += "_베트맨 스포츠토토 AI 분석 시스템_"

        return msg

    async def _format_toto_soccer_message(self, matches: List[Dict]) -> str:
        """축구토토 승무패 메시지 포맷"""
        msg = f"""
⚽ **축구토토 승무패 14경기**
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━

"""

        high_confidence_games = []

        for i, match in enumerate(matches[:14], 1):  # 최대 14경기
            home = match["home_team"]
            away = match["away_team"]
            kickoff = match["kickoff_time"].strftime("%m/%d %H:%M")

            confidence = match.get("confidence", 0)
            prediction = match.get("prediction", "분석 중")
            mark = match.get("mark", "-")

            icon = "🔒" if confidence >= 0.65 else "📊"

            if confidence >= 0.65:
                high_confidence_games.append(i)

            msg += f"**[{i:02d}] {home} vs {away}**\n"
            msg += f"⏰ {kickoff}\n"
            msg += f"{icon} **[{mark}] {prediction}** ({confidence*100:.1f}%)\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"🔒 고신뢰도 경기: {len(high_confidence_games)}개\n"

        if high_confidence_games:
            msg += f"추천: {', '.join(map(str, high_confidence_games))}\n\n"

        msg += "_베트맨 스포츠토토 AI 분석 시스템_"

        return msg

    async def _format_basketball_message(self, matches: List[Dict]) -> str:
        """농구토토 승5패 메시지 포맷"""
        msg = f"""
🏀 **농구토토 승5패**
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━

"""

        for i, match in enumerate(matches[:5], 1):  # 최대 5경기
            home = match["home_team"]
            away = match["away_team"]
            league = match.get("league", "")
            kickoff = match["kickoff_time"].strftime("%m/%d %H:%M")

            confidence = match.get("confidence", 0)
            prediction = match.get("prediction", "분석 중")

            # 농구는 무승부 없음
            if "홈" in prediction:
                mark = "홈승"
            else:
                mark = "원정승"

            icon = "🔒" if confidence >= 0.60 else "📊"

            msg += f"**[{i}] {home} vs {away}**\n"
            msg += f"🏆 {league} | ⏰ {kickoff}\n"
            msg += f"{icon} **{mark}** ({confidence*100:.1f}%)\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "_베트맨 스포츠토토 AI 분석 시스템_"

        return msg


async def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(
        description="프로토/토토 분석 결과를 텔레그램으로 전송"
    )
    parser.add_argument(
        "--proto",
        action="store_true",
        help="프로토 승부식만 전송"
    )
    parser.add_argument(
        "--soccer",
        action="store_true",
        help="축구토토 승무패만 전송"
    )
    parser.add_argument(
        "--basketball",
        action="store_true",
        help="농구토토 승5패만 전송"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="앞으로 N일간의 경기 조회 (기본값: 7일)"
    )

    args = parser.parse_args()

    reporter = TotoProtoReporter()

    print("=" * 60)
    print("📱 프로토/토토 분석 결과 전송")
    print("=" * 60)
    print()

    try:
        if args.proto:
            print("⚽ 프로토 승부식 전송 중...")
            await reporter.send_proto_results(args.days)
        elif args.soccer:
            print("⚽ 축구토토 승무패 전송 중...")
            await reporter.send_toto_soccer_results(args.days)
        elif args.basketball:
            print("🏀 농구토토 승5패 전송 중...")
            await reporter.send_basketball_results(args.days)
        else:
            # 기본값: 모두 전송
            print("📊 모든 프로토/토토 분석 결과 전송 중...")
            await reporter.send_all_toto_proto(args.days)

        print()
        print("✅ 텔레그램 전송 완료!")
        print("📱 텔레그램 앱에서 메시지를 확인하세요.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
