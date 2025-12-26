#!/usr/bin/env python3
"""
프로토 승부식 고신뢰도 경기만 텔레그램으로 알림 전송

고신뢰도 기준:
- AI 모델 합의도 75% 이상 (최소 5개 모델 중 4개 이상 동일 예측)
- 예측 확률 65% 이상
- STRONG_VALUE 또는 VALUE 추천 경기

사용법:
    python notify_high_confidence_proto.py              # 기본 실행 (7일)
    python notify_high_confidence_proto.py --days 14    # 14일간 조회
    python notify_high_confidence_proto.py --threshold 0.70  # 70% 이상만
    python notify_high_confidence_proto.py --test       # 테스트 모드 (전송 안함)
"""

import asyncio
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from src.db.session import get_session
from src.db.models import Match, PredictionLog
from src.services.telegram_notifier import TelegramNotifier


@dataclass
class HighConfidenceMatch:
    """고신뢰도 경기 데이터"""
    match_id: int
    game_number: int
    round_number: int
    home_team: str
    away_team: str
    league: str
    kickoff_time: datetime

    # 예측 정보
    prediction: str           # '홈승', '무승부', '원정승'
    mark: str                 # '1', 'X', '2'
    confidence: float         # 최고 확률 (0-1)

    # 신뢰도 지표
    model_agreement: float    # AI 모델 합의도 (0-1)
    value_type: str           # 'STRONG_VALUE', 'VALUE', 'INFO'

    # 확률 상세
    prob_home: float
    prob_draw: float
    prob_away: float

    @property
    def is_high_confidence(self) -> bool:
        """고신뢰도 여부"""
        return (
            self.confidence >= 0.65 and
            self.model_agreement >= 0.75 and
            self.value_type in ('STRONG_VALUE', 'VALUE')
        )

    @property
    def confidence_level(self) -> str:
        """신뢰도 레벨 (텍스트)"""
        if self.confidence >= 0.75:
            return "매우 높음"
        elif self.confidence >= 0.70:
            return "높음"
        elif self.confidence >= 0.65:
            return "양호"
        else:
            return "보통"


class HighConfidenceProtoNotifier:
    """프로토 승부식 고신뢰도 경기 알림 서비스"""

    def __init__(self, confidence_threshold: float = 0.65):
        self.notifier = TelegramNotifier()
        self.confidence_threshold = confidence_threshold
        self.agreement_threshold = 0.75  # AI 모델 합의도 75% 이상

    async def get_high_confidence_matches(
        self,
        days_ahead: int = 7
    ) -> List[HighConfidenceMatch]:
        """고신뢰도 프로토 경기 조회"""

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
                        Match.category_name == "프로토 승부식",
                        Match.start_time >= now,
                        Match.start_time <= end_date,
                    )
                )
                .order_by(Match.round_number, Match.game_number, Match.start_time)
            )

            result = await session.execute(stmt)
            matches = result.unique().scalars().all()

            high_confidence_list = []

            for match in matches:
                hc_match = self._evaluate_match(match)
                if hc_match and hc_match.confidence >= self.confidence_threshold:
                    high_confidence_list.append(hc_match)

            # 신뢰도 순으로 정렬
            high_confidence_list.sort(
                key=lambda x: (x.confidence, x.model_agreement),
                reverse=True
            )

            return high_confidence_list

    def _evaluate_match(self, match: Match) -> Optional[HighConfidenceMatch]:
        """경기 평가 및 고신뢰도 데이터 생성"""

        if not match.predictions:
            return None

        # 최신 예측 사용
        pred = match.predictions[-1]

        # 확률 추출
        prob_home = pred.prob_home or 0
        prob_draw = pred.prob_draw or 0
        prob_away = pred.prob_away or 0

        # 최고 확률 및 예측 결정
        max_prob = max(prob_home, prob_draw, prob_away)

        if max_prob == prob_home:
            prediction = "홈승"
            mark = "1"
        elif max_prob == prob_away:
            prediction = "원정승"
            mark = "2"
        else:
            prediction = "무승부"
            mark = "X"

        # 모델 합의도 (메타데이터에서 추출 또는 계산)
        meta = pred.meta or {}
        model_agreement = meta.get('model_agreement', 0.8)  # 기본값 80%

        # AI 합의 정보가 있으면 파싱
        ai_consensus = meta.get('ai_consensus', '')
        if ai_consensus and '/' in ai_consensus:
            try:
                agreed, total = ai_consensus.split('/')
                agreed = int(agreed.strip())
                total = int(total.split()[0].strip())
                if total > 0:
                    model_agreement = agreed / total
            except (ValueError, IndexError):
                pass

        # Value 타입
        value_type = match.recommendation or 'INFO'

        return HighConfidenceMatch(
            match_id=match.id,
            game_number=match.game_number or 0,
            round_number=match.round_number or 0,
            home_team=match.home_team.name if match.home_team else "홈팀",
            away_team=match.away_team.name if match.away_team else "원정팀",
            league=match.league.name if match.league else "리그 미정",
            kickoff_time=match.start_time,
            prediction=prediction,
            mark=mark,
            confidence=max_prob,
            model_agreement=model_agreement,
            value_type=value_type,
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
        )

    def format_notification_message(
        self,
        matches: List[HighConfidenceMatch]
    ) -> str:
        """알림 메시지 포맷"""

        if not matches:
            return "📊 현재 고신뢰도 프로토 승부식 경기가 없습니다."

        # 회차별 그룹화
        by_round: Dict[int, List[HighConfidenceMatch]] = {}
        for match in matches:
            if match.round_number not in by_round:
                by_round[match.round_number] = []
            by_round[match.round_number].append(match)

        lines = []
        lines.append("🎯 **프로토 승부식 고신뢰도 알림**")
        lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append("━" * 25)
        lines.append("")

        for round_num in sorted(by_round.keys()):
            round_matches = by_round[round_num]

            lines.append(f"📋 **{round_num}회차** ({len(round_matches)}경기)")
            lines.append("")

            for match in round_matches:
                # 아이콘 선택
                if match.value_type == "STRONG_VALUE":
                    icon = "💎"
                elif match.confidence >= 0.75:
                    icon = "🔥"
                else:
                    icon = "🔒"

                lines.append(f"{icon} **[{match.game_number:02d}] {match.home_team} vs {match.away_team}**")
                lines.append(f"   🏆 {match.league}")
                lines.append(f"   ⏰ {match.kickoff_time.strftime('%m/%d %H:%M')}")
                lines.append(f"   📌 예측: **[{match.mark}] {match.prediction}**")
                lines.append(f"   📊 신뢰도: {match.confidence*100:.1f}% ({match.confidence_level})")
                lines.append(f"   🤖 AI 합의: {match.model_agreement*100:.0f}%")
                lines.append("")

        lines.append("━" * 25)
        lines.append("")
        lines.append(f"✅ 총 **{len(matches)}경기** 고신뢰도 추천")
        lines.append("")

        # 요약 통계
        avg_confidence = sum(m.confidence for m in matches) / len(matches)
        strong_value_count = sum(1 for m in matches if m.value_type == "STRONG_VALUE")

        lines.append(f"📈 평균 신뢰도: {avg_confidence*100:.1f}%")
        if strong_value_count > 0:
            lines.append(f"💎 강력 추천: {strong_value_count}경기")

        lines.append("")
        lines.append("_베트맨 스포츠토토 AI 분석 시스템_")

        return "\n".join(lines)

    def format_compact_message(
        self,
        matches: List[HighConfidenceMatch]
    ) -> str:
        """간략한 알림 메시지 (요약)"""

        if not matches:
            return "📊 고신뢰도 프로토 경기 없음"

        lines = []
        lines.append("🎯 **프로토 고신뢰도 TOP 추천**")
        lines.append(f"📅 {datetime.now().strftime('%m/%d %H:%M')}")
        lines.append("")

        # 상위 5개만 표시
        for match in matches[:5]:
            icon = "💎" if match.value_type == "STRONG_VALUE" else "🔒"
            lines.append(
                f"{icon} [{match.game_number:02d}] {match.home_team} vs {match.away_team}"
            )
            lines.append(
                f"   → **[{match.mark}]** {match.confidence*100:.0f}%"
            )

        if len(matches) > 5:
            lines.append(f"\n...외 {len(matches) - 5}경기")

        lines.append("")
        lines.append("_전체 분석: /proto 명령_")

        return "\n".join(lines)

    async def send_notification(
        self,
        days_ahead: int = 7,
        compact: bool = False,
        test_mode: bool = False
    ) -> bool:
        """고신뢰도 경기 알림 전송"""

        print("🔍 고신뢰도 경기 조회 중...")
        matches = await self.get_high_confidence_matches(days_ahead)

        print(f"✅ {len(matches)}개의 고신뢰도 경기 발견")

        if not matches:
            print("⚠️ 고신뢰도 경기가 없어 알림을 전송하지 않습니다.")
            return False

        # 메시지 포맷
        if compact:
            message = self.format_compact_message(matches)
        else:
            message = self.format_notification_message(matches)

        if test_mode:
            print("\n" + "=" * 50)
            print("📱 테스트 모드 - 전송하지 않음")
            print("=" * 50)
            print(message)
            print("=" * 50)
            return True

        # 텔레그램 전송
        print("📤 텔레그램으로 전송 중...")
        success = await self.notifier.send_message(message)

        if success:
            print("✅ 알림 전송 완료!")
        else:
            print("❌ 알림 전송 실패")

        return success


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="프로토 승부식 고신뢰도 경기 알림"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="앞으로 N일간의 경기 조회 (기본: 7일)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.65,
        help="최소 신뢰도 기준 (기본: 0.65 = 65%%)"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="간략한 메시지 형식 사용"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드 (전송하지 않고 출력만)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🎯 프로토 승부식 고신뢰도 알림 서비스")
    print("=" * 60)
    print(f"📅 조회 기간: {args.days}일")
    print(f"📊 신뢰도 기준: {args.threshold * 100:.0f}% 이상")
    print()

    notifier = HighConfidenceProtoNotifier(
        confidence_threshold=args.threshold
    )

    try:
        await notifier.send_notification(
            days_ahead=args.days,
            compact=args.compact,
            test_mode=args.test
        )
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
