#!/usr/bin/env python3
"""
농구 승5패 텔레그램 알림 및 자동 분석 시스템

기능:
1. 14경기 전체 정답표 + 복식 4개 텔레그램 전송
2. 새 회차 자동 감지 및 분석
3. 스케줄러로 정기 실행

사용법:
    python basketball_w5l_notifier.py              # 즉시 분석 및 알림
    python basketball_w5l_notifier.py --schedule   # 스케줄러 모드 (주기적 실행)
    python basketball_w5l_notifier.py --test       # 테스트 모드 (전송 안함)
"""

import asyncio
import argparse
import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from basketball_w5l_analyzer import (
    BasketballW5LAnalyzer,
    W5LPrediction,
    W5LCombination
)
from src.services.telegram_notifier import TelegramNotifier
from src.services.round_manager import RoundManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 상태 저장 파일
STATE_FILE = Path(__file__).parent / ".basketball_w5l_state.json"


class BasketballW5LNotifier:
    """농구 승5패 텔레그램 알림 서비스"""

    def __init__(self):
        self.notifier = TelegramNotifier()
        self.analyzer = BasketballW5LAnalyzer()
        self.round_manager = RoundManager()
        self.last_round = self._load_last_round()

    def _load_last_round(self) -> Optional[int]:
        """마지막 분석 회차 로드"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("last_round")
            except Exception:
                pass
        return None

    def _save_last_round(self, round_num: int):
        """마지막 분석 회차 저장"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({
                    "last_round": round_num,
                    "updated_at": datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")

    async def collect_games(self) -> Tuple[List[Dict], int]:
        """
        경기 데이터 수집 및 회차 확인 (RoundManager 활용)

        RoundManager가 정확한 회차와 14경기를 자동으로 가져옵니다.
        """
        logger.info("📊 RoundManager를 통해 농구 경기 데이터 수집 중...")

        try:
            round_info, games = await self.round_manager.get_basketball_w5l_round()

            if not games:
                logger.warning("수집된 농구 경기가 없습니다.")
                return [], 0

            logger.info(f"✅ {round_info.round_number}회차 {len(games)}경기 수집 완료")
            logger.info(f"   경기일: {round_info.match_date}, 마감: {round_info.deadline}")

            return games, round_info.round_number

        except Exception as e:
            logger.error(f"경기 수집 실패: {e}")
            return [], 0

    def analyze_games(self, games: List[Dict]) -> List[W5LPrediction]:
        """14경기 분석"""
        predictions = []

        for game in games:
            game_num = game.get("row_num", 0)
            home = game.get("hteam_han_nm", "")
            away = game.get("ateam_han_nm", "")
            match_tm = str(game.get("match_tm", "0000")).zfill(4)
            match_time = f"{match_tm[:2]}:{match_tm[2:]}"

            pred = self.analyzer.analyze_game(
                game_number=game_num,
                home_team=home,
                away_team=away,
                match_time=match_time
            )
            predictions.append(pred)

        return predictions

    def find_multi_selections(
        self,
        predictions: List[W5LPrediction],
        max_multi: int = 4
    ) -> List[Tuple[int, str, str]]:
        """복식 선택 경기 찾기"""
        # 불확실한 경기 (신뢰도 42% 미만 또는 5 확률 30% 이상)
        uncertain = []

        for i, pred in enumerate(predictions):
            # 복식 필요 조건
            needs_multi = (
                pred.confidence < 0.42 or
                (pred.prob_5 >= 0.30 and pred.recommended != "5") or
                (pred.prob_lose >= 0.28 and pred.recommended == "승")
            )

            if needs_multi:
                # 상위 2개 선택지
                probs = sorted([
                    ("승", pred.prob_win),
                    ("5", pred.prob_5),
                    ("패", pred.prob_lose)
                ], key=lambda x: x[1], reverse=True)

                top2 = f"{probs[0][0]}/{probs[1][0]}"
                uncertain.append((i + 1, top2, f"{probs[0][1]*100:.0f}%/{probs[1][1]*100:.0f}%"))

        # 5 확률 높은 순으로 정렬
        uncertain.sort(key=lambda x: predictions[x[0]-1].prob_5, reverse=True)

        return uncertain[:max_multi]

    def format_telegram_message(
        self,
        predictions: List[W5LPrediction],
        multi_games: List[Tuple[int, str, str]],
        round_num: int
    ) -> str:
        """텔레그램 메시지 포맷팅"""

        lines = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 헤더
        lines.append(f"🏀 *농구토토 승5패 {round_num}회차*")
        lines.append(f"📅 {now_str}")
        lines.append("━" * 24)
        lines.append("")

        # 14경기 전체 정답표
        lines.append("📋 *14경기 전체 예측*")
        lines.append("")

        multi_nums = {m[0] for m in multi_games}

        for i, pred in enumerate(predictions, 1):
            # 팀명 축약
            home_short = pred.home_team[:7] if len(pred.home_team) > 7 else pred.home_team
            away_short = pred.away_team[:7] if len(pred.away_team) > 7 else pred.away_team

            # 신뢰도 아이콘
            if pred.confidence >= 0.45:
                icon = "🔒"
            elif pred.confidence >= 0.38:
                icon = "✅"
            else:
                icon = "⚠️"

            # 복식 여부
            if i in multi_nums:
                multi_info = next(m for m in multi_games if m[0] == i)
                mark = f"*{multi_info[1]}*"
            else:
                mark = f"[{pred.recommended}]"

            lines.append(f"{i:02d}. {home_short} vs {away_short}")
            lines.append(f"     {icon} {mark} ({pred.confidence*100:.0f}%)")
            lines.append("")

        lines.append("━" * 24)
        lines.append("")

        # 단식 정답
        lines.append("📝 *단식 정답*")
        single_answers = [pred.recommended for pred in predictions]

        # 경기 수에 맞게 표시 (14경기 미만도 지원)
        total_games = len(single_answers)
        if total_games >= 14:
            line1 = " ".join([f"{i+1}:{single_answers[i]}" for i in range(7)])
            line2 = " ".join([f"{i+1}:{single_answers[i]}" for i in range(7, 14)])
            lines.append(f"`{line1}`")
            lines.append(f"`{line2}`")
        elif total_games > 0:
            # 14경기 미만인 경우 한 줄로 표시
            line = " ".join([f"{i+1}:{single_answers[i]}" for i in range(total_games)])
            lines.append(f"`{line}`")
        lines.append("")

        # 복식 추천
        lines.append("━" * 24)
        lines.append("")
        lines.append(f"🎰 *복식 {len(multi_games)}경기* (총 {2**len(multi_games)}조합)")
        lines.append("")

        for num, selection, prob in multi_games:
            pred = predictions[num - 1]
            home_short = pred.home_team[:6] if len(pred.home_team) > 6 else pred.home_team
            away_short = pred.away_team[:6] if len(pred.away_team) > 6 else pred.away_team
            lines.append(f"*{num:02d}번* {home_short} vs {away_short}")
            lines.append(f"     → *{selection}* ({prob})")
            lines.append("")

        lines.append("━" * 24)
        lines.append("")

        # 핵심 포인트
        lines.append("⚡ *핵심 포인트*")

        # 5 확률 가장 높은 경기
        max_5_game = max(predictions, key=lambda x: x.prob_5)
        lines.append(f"• 접전(5) 최고: {predictions.index(max_5_game)+1}번 ({max_5_game.prob_5*100:.0f}%)")

        # 고신뢰 경기 수
        high_conf = sum(1 for p in predictions if p.confidence >= 0.45)
        lines.append(f"• 고신뢰(🔒) 경기: {high_conf}개")

        # 전체 승 예측 수
        win_count = sum(1 for p in predictions if p.recommended == "승")
        lines.append(f"• 홈승(승) 예측: {win_count}경기")

        lines.append("")
        lines.append("━" * 24)
        lines.append("_베트맨 스포츠토토 AI 분석_")

        return "\n".join(lines)

    async def send_analysis(
        self,
        predictions: List[W5LPrediction],
        multi_games: List[Tuple[int, str, str]],
        round_num: int,
        test_mode: bool = False
    ) -> bool:
        """분석 결과 텔레그램 전송"""

        message = self.format_telegram_message(predictions, multi_games, round_num)

        if test_mode:
            print("\n" + "=" * 50)
            print("📱 테스트 모드 - 전송하지 않음")
            print("=" * 50)
            print(message)
            print("=" * 50)
            return True

        logger.info("📤 텔레그램으로 전송 중...")
        success = await self.notifier.send_message(message)

        if success:
            logger.info("✅ 텔레그램 전송 완료!")
            self._save_last_round(round_num)
        else:
            logger.error("❌ 텔레그램 전송 실패")

        return success

    async def run_analysis(self, test_mode: bool = False) -> bool:
        """전체 분석 프로세스 실행"""

        logger.info("🏀 농구 승5패 분석 시작...")

        # 1. 데이터 수집
        games, round_num = await self.collect_games()

        if not games:
            logger.warning("분석할 경기가 없습니다.")
            return False

        if len(games) < 14:
            logger.warning(f"경기 수 부족: {len(games)}경기 (14경기 필요)")

        # 2. 14경기 분석
        logger.info(f"📊 {len(games)}경기 분석 중...")
        predictions = self.analyze_games(games)

        # 3. 복식 선택
        multi_games = self.find_multi_selections(predictions)
        logger.info(f"🎰 복식 {len(multi_games)}경기 선정")

        # 4. 텔레그램 전송
        success = await self.send_analysis(predictions, multi_games, round_num, test_mode)

        return success

    async def check_new_round(self) -> bool:
        """새 회차 확인 (RoundManager 활용)"""
        new_round = await self.round_manager.check_new_round("basketball_w5l")

        if new_round:
            logger.info(f"🆕 새 회차 감지: {new_round}회차")
            self.last_round = new_round
            return True

        return False

    async def run_scheduler(self, interval_hours: int = 6):
        """스케줄러 모드 실행"""

        logger.info(f"⏰ 스케줄러 모드 시작 (간격: {interval_hours}시간)")
        logger.info("   - 새 회차 감지 시 자동 분석 및 알림")
        logger.info("   - Ctrl+C로 종료")

        while True:
            try:
                # 새 회차 확인
                if await self.check_new_round():
                    await self.run_analysis()
                else:
                    logger.info(f"📅 새 회차 없음. {interval_hours}시간 후 재확인...")

                # 대기
                await asyncio.sleep(interval_hours * 3600)

            except KeyboardInterrupt:
                logger.info("스케줄러 종료")
                break
            except Exception as e:
                logger.error(f"스케줄러 오류: {e}")
                await asyncio.sleep(300)  # 5분 후 재시도


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="농구 승5패 텔레그램 알림 시스템"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드 (전송하지 않고 출력만)"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="스케줄러 모드 (주기적 실행)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=6,
        help="스케줄러 간격 (시간, 기본: 6)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🏀 농구 승5패 분석 및 알림 시스템")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    notifier = BasketballW5LNotifier()

    try:
        if args.schedule:
            await notifier.run_scheduler(args.interval)
        else:
            await notifier.run_analysis(test_mode=args.test)
    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    print("✅ 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
