#!/usr/bin/env python3
"""
프로토 14경기 자동 분석 및 텔레그램 알림 시스템

핵심 기능:
1. 최신 회차 자동 업데이트 (RoundManager)
2. AI 자동 분석 (5개 AI 앙상블)
3. 텔레그램 알림 전송

사용법:
    python auto_sports_notifier.py                    # 전체 분석 (축구+농구)
    python auto_sports_notifier.py --soccer           # 축구 승무패만
    python auto_sports_notifier.py --basketball       # 농구 승5패만
    python auto_sports_notifier.py --test             # 테스트 모드 (전송 안함)
    python auto_sports_notifier.py --schedule         # 스케줄러 모드 (6시간마다)
"""

import asyncio
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

from src.services.round_manager import RoundManager, RoundInfo
from src.services.telegram_notifier import TelegramNotifier
from src.services.ai_orchestrator import AIOrchestrator
from src.services.ai.models import MatchContext, SportType
from src.services.prediction_tracker import prediction_tracker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 상태 저장 파일
STATE_DIR = Path(__file__).parent / ".state"
STATE_DIR.mkdir(exist_ok=True)
LAST_ROUND_FILE = STATE_DIR / "last_notified_rounds.json"


@dataclass
class GamePrediction:
    """경기 예측 결과"""
    game_number: int
    home_team: str
    away_team: str
    match_time: str

    # 확률 (AI 분석 결과)
    prob_home: float
    prob_draw: float  # 축구: 무승부, 농구: 5점 이내
    prob_away: float

    # 추천
    recommended: str  # "1", "X", "2" 또는 "승", "5", "패"
    confidence: float

    # 복식 여부
    is_multi: bool = False
    multi_selections: List[str] = None

    # AI 분석 세부 정보
    ai_agreement: float = 0.0  # AI 일치도
    analysis_note: str = ""


class AutoSportsNotifier:
    """프로토 14경기 자동 분석 및 알림"""

    def __init__(self):
        self.round_manager = RoundManager()
        self.notifier = TelegramNotifier()
        self.ai_orchestrator = AIOrchestrator()
        self.last_rounds = self._load_last_rounds()

    def _load_last_rounds(self) -> Dict[str, int]:
        """마지막 알림 회차 로드"""
        if LAST_ROUND_FILE.exists():
            try:
                with open(LAST_ROUND_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"soccer_wdl": 0, "basketball_w5l": 0}

    def _save_last_rounds(self):
        """마지막 알림 회차 저장"""
        try:
            with open(LAST_ROUND_FILE, 'w') as f:
                json.dump(self.last_rounds, f)
        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")

    # ==================== 축구 승무패 ====================

    async def analyze_soccer(self, test_mode: bool = False) -> bool:
        """축구 승무패 14경기 분석 및 알림"""
        logger.info("⚽ 축구 승무패 분석 시작...")

        try:
            # 1. 최신 14경기 수집
            round_info, games = await self.round_manager.get_soccer_wdl_round(force_refresh=True)

            if not games:
                logger.warning("축구 승무패 경기가 없습니다.")
                return False

            # ⚠️ 14경기 검증 (치명적!)
            if len(games) != 14:
                logger.error(f"🚨 치명적: 축구 {len(games)}경기 수집 (14경기 필요!)")
                logger.error("   → 텔레그램 전송 차단 (불완전한 예측 방지)")
                return False

            logger.info(f"✅ {round_info.round_number}회차 {len(games)}경기 수집 완료")

            # 2. AI 분석
            predictions = await self._analyze_games(games, game_type="soccer")

            # 3. 복식 4경기 선정
            multi_games = self._select_multi_games(predictions, game_type="soccer")

            # 4. 예측 저장 (적중률 추적용)
            self._save_predictions(round_info, predictions, multi_games, "soccer_wdl")

            # 5. 텔레그램 메시지 생성 및 전송
            message = self._format_soccer_message(round_info, predictions, multi_games)

            if test_mode:
                print("\n" + "=" * 60)
                print("📱 테스트 모드 - 전송하지 않음")
                print("=" * 60)
                print(message)
                print("=" * 60)
                return True

            success = await self.notifier.send_message(message)

            if success:
                self.last_rounds["soccer_wdl"] = round_info.round_number
                self._save_last_rounds()
                logger.info("✅ 축구 승무패 텔레그램 전송 완료!")

            return success

        except Exception as e:
            logger.error(f"축구 승무패 분석 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================== 농구 승5패 ====================

    async def analyze_basketball(self, test_mode: bool = False) -> bool:
        """농구 승5패 14경기 분석 및 알림"""
        logger.info("🏀 농구 승5패 분석 시작...")

        try:
            # 1. 최신 14경기 수집
            round_info, games = await self.round_manager.get_basketball_w5l_round(force_refresh=True)

            if not games:
                logger.warning("농구 승5패 경기가 없습니다.")
                return False

            # ⚠️ 14경기 검증 (치명적!)
            if len(games) != 14:
                logger.error(f"🚨 치명적: 농구 {len(games)}경기 수집 (14경기 필요!)")
                logger.error("   → 텔레그램 전송 차단 (불완전한 예측 방지)")
                return False

            logger.info(f"✅ {round_info.round_number}회차 {len(games)}경기 수집 완료")

            # 2. AI 분석
            predictions = await self._analyze_games(games, game_type="basketball")

            # 3. 복식 4경기 선정
            multi_games = self._select_multi_games(predictions, game_type="basketball")

            # 4. 예측 저장 (적중률 추적용)
            self._save_predictions(round_info, predictions, multi_games, "basketball_w5l")

            # 5. 텔레그램 메시지 생성 및 전송
            message = self._format_basketball_message(round_info, predictions, multi_games)

            if test_mode:
                print("\n" + "=" * 60)
                print("📱 테스트 모드 - 전송하지 않음")
                print("=" * 60)
                print(message)
                print("=" * 60)
                return True

            success = await self.notifier.send_message(message)

            if success:
                self.last_rounds["basketball_w5l"] = round_info.round_number
                self._save_last_rounds()
                logger.info("✅ 농구 승5패 텔레그램 전송 완료!")

            return success

        except Exception as e:
            logger.error(f"농구 승5패 분석 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================== AI 분석 로직 ====================

    async def _analyze_games(
        self,
        games: List[Dict],
        game_type: str
    ) -> List[GamePrediction]:
        """
        AI를 사용한 경기 분석

        AI Orchestrator가 활성화되어 있으면 5개 AI 앙상블 사용,
        그렇지 않으면 기본 확률 계산 사용
        """
        predictions = []
        active_ais = self.ai_orchestrator.get_active_analyzers()
        use_ai = len(active_ais) > 0

        if use_ai:
            logger.info(f"🤖 AI 분석 사용 ({len(active_ais)}개 모델: {', '.join(active_ais)})")
        else:
            logger.info("📊 기본 확률 모델 사용 (AI API 키 없음)")

        for i, game in enumerate(games[:14], 1):
            home = game.get("hteam_han_nm", "홈팀")
            away = game.get("ateam_han_nm", "원정팀")
            match_tm = str(game.get("match_tm", "0000")).zfill(4)
            match_time = f"{match_tm[:2]}:{match_tm[2:]}"
            row_num = game.get("row_num", i)

            if use_ai:
                # AI 앙상블 분석
                pred = await self._analyze_with_ai(
                    game_number=row_num,
                    home_team=home,
                    away_team=away,
                    match_time=match_time,
                    game_type=game_type
                )
            else:
                # 기본 확률 모델
                pred = self._analyze_basic(
                    game_number=row_num,
                    home_team=home,
                    away_team=away,
                    match_time=match_time,
                    game_type=game_type
                )

            predictions.append(pred)

        return predictions

    async def _analyze_with_ai(
        self,
        game_number: int,
        home_team: str,
        away_team: str,
        match_time: str,
        game_type: str
    ) -> GamePrediction:
        """AI 앙상블을 사용한 분석"""
        try:
            # MatchContext 생성
            context = MatchContext(
                match_id=int(f"{game_number}"),
                home_team=home_team,
                away_team=away_team,
                league="축구토토" if game_type == "soccer" else "NBA/KBL",
                start_time=match_time,
                sport_type=SportType.SOCCER if game_type == "soccer" else SportType.BASKETBALL
            )

            # AI 분석 실행
            result = await self.ai_orchestrator.analyze_match(context, use_cache=True)

            # 결과 변환
            probs = result.consensus.probabilities
            prob_home = probs.get("home", 0.33)
            prob_draw = probs.get("draw", 0.34)
            prob_away = probs.get("away", 0.33)

            # 추천 결정
            if game_type == "soccer":
                if prob_home >= prob_draw and prob_home >= prob_away:
                    recommended = "1"
                    confidence = prob_home
                elif prob_away >= prob_draw:
                    recommended = "2"
                    confidence = prob_away
                else:
                    recommended = "X"
                    confidence = prob_draw
            else:  # basketball
                if prob_home >= prob_draw and prob_home >= prob_away:
                    recommended = "승"
                    confidence = prob_home
                elif prob_away >= prob_draw:
                    recommended = "패"
                    confidence = prob_away
                else:
                    recommended = "5"
                    confidence = prob_draw

            return GamePrediction(
                game_number=game_number,
                home_team=home_team,
                away_team=away_team,
                match_time=match_time,
                prob_home=prob_home,
                prob_draw=prob_draw,
                prob_away=prob_away,
                recommended=recommended,
                confidence=confidence,
                ai_agreement=result.consensus.agreement_rate,
                analysis_note=result.consensus.recommendation
            )

        except Exception as e:
            logger.warning(f"AI 분석 실패 (경기 {game_number}): {e}, 기본 모델 사용")
            return self._analyze_basic(
                game_number, home_team, away_team, match_time, game_type
            )

    def _analyze_basic(
        self,
        game_number: int,
        home_team: str,
        away_team: str,
        match_time: str,
        game_type: str
    ) -> GamePrediction:
        """기본 확률 모델 (AI 없이)"""
        import random

        # 홈 어드밴티지 기반 기본 확률
        if game_type == "soccer":
            # 축구: 홈 승리 45%, 무승부 28%, 원정 승리 27%
            base_home = 0.45 + random.uniform(-0.10, 0.10)
            base_draw = 0.28 + random.uniform(-0.05, 0.05)
            base_away = 1.0 - base_home - base_draw
        else:
            # 농구: 홈 승리 50%, 5점 이내 25%, 원정 승리 25%
            base_home = 0.50 + random.uniform(-0.12, 0.12)
            base_draw = 0.25 + random.uniform(-0.05, 0.08)
            base_away = 1.0 - base_home - base_draw

        # 확률 정규화
        total = base_home + base_draw + base_away
        prob_home = base_home / total
        prob_draw = base_draw / total
        prob_away = base_away / total

        # 추천 결정
        if game_type == "soccer":
            if prob_home >= prob_draw and prob_home >= prob_away:
                recommended = "1"
                confidence = prob_home
            elif prob_away >= prob_draw:
                recommended = "2"
                confidence = prob_away
            else:
                recommended = "X"
                confidence = prob_draw
        else:
            if prob_home >= prob_draw and prob_home >= prob_away:
                recommended = "승"
                confidence = prob_home
            elif prob_away >= prob_draw:
                recommended = "패"
                confidence = prob_away
            else:
                recommended = "5"
                confidence = prob_draw

        return GamePrediction(
            game_number=game_number,
            home_team=home_team,
            away_team=away_team,
            match_time=match_time,
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            recommended=recommended,
            confidence=confidence,
            ai_agreement=0.0,
            analysis_note="기본 모델"
        )

    # ==================== 복식 선정 ====================

    def _select_multi_games(
        self,
        predictions: List[GamePrediction],
        game_type: str,
        max_multi: int = 4
    ) -> List[Tuple[int, str, str]]:
        """
        복식 베팅 경기 선정 (이변 가능성 높은 4경기)

        핵심 로직:
        1. 모든 경기에 대해 이변 점수(upset_score) 계산
        2. 이변 점수가 높은 순으로 정렬
        3. 상위 4개 선정 (항상 4경기 복수 베팅)

        Returns:
            List[(game_number, selections, probs_str)]
        """
        candidates = []

        for pred in predictions:
            # 이변 신호 점수 계산 (모든 경기에 대해)
            upset_score = 0.0

            # 확률 분포 계산
            probs = sorted([pred.prob_home, pred.prob_draw, pred.prob_away], reverse=True)
            prob_gap = probs[0] - probs[1]

            # 1. 확률 분포 애매함 (1위-2위 차이가 작을수록 높은 점수)
            if prob_gap < 0.10:
                upset_score += 50  # 매우 애매함
            elif prob_gap < 0.15:
                upset_score += 40
            elif prob_gap < 0.20:
                upset_score += 30
            elif prob_gap < 0.25:
                upset_score += 20
            elif prob_gap < 0.30:
                upset_score += 10

            # 2. 신뢰도 기반 점수 (낮을수록 이변 가능성 높음)
            if pred.confidence < 0.40:
                upset_score += 40
            elif pred.confidence < 0.45:
                upset_score += 30
            elif pred.confidence < 0.50:
                upset_score += 20
            elif pred.confidence < 0.55:
                upset_score += 10

            # 3. AI 불일치 (일치도 낮을수록 이변 가능성) - AI 사용 시에만
            if pred.ai_agreement > 0:
                if pred.ai_agreement < 0.40:
                    upset_score += 35
                elif pred.ai_agreement < 0.50:
                    upset_score += 25
                elif pred.ai_agreement < 0.60:
                    upset_score += 15
                elif pred.ai_agreement < 0.70:
                    upset_score += 5

            # 4. 무승부/5 확률 (높을수록 이변 가능성)
            if pred.prob_draw >= 0.30:
                upset_score += 25
            elif pred.prob_draw >= 0.25:
                upset_score += 15
            elif pred.prob_draw >= 0.20:
                upset_score += 5

            # 상위 2개 선택지 결정
            if game_type == "soccer":
                probs_dict = {"1": pred.prob_home, "X": pred.prob_draw, "2": pred.prob_away}
            else:
                probs_dict = {"승": pred.prob_home, "5": pred.prob_draw, "패": pred.prob_away}

            sorted_probs = sorted(probs_dict.items(), key=lambda x: x[1], reverse=True)
            selections = f"{sorted_probs[0][0]}/{sorted_probs[1][0]}"
            probs_str = f"{sorted_probs[0][1]*100:.0f}%/{sorted_probs[1][1]*100:.0f}%"

            candidates.append((
                pred.game_number,
                selections,
                probs_str,
                upset_score,
                pred
            ))

        # 이변 점수 순으로 정렬
        candidates.sort(key=lambda x: x[3], reverse=True)

        # 상위 4개 선정 (항상 max_multi개 선정)
        multi_games = [(c[0], c[1], c[2]) for c in candidates[:max_multi]]

        logger.info(f"🎰 복수 베팅: 이변 가능성 상위 {len(multi_games)}경기 선정")
        for c in candidates[:max_multi]:
            logger.info(f"   - {c[0]:02d}번: {c[1]} (upset_score={c[3]:.0f})")

        # 선정된 경기에 복식 표시
        multi_nums = {m[0] for m in multi_games}
        for pred in predictions:
            if pred.game_number in multi_nums:
                pred.is_multi = True
                match = next(m for m in multi_games if m[0] == pred.game_number)
                pred.multi_selections = match[1].split("/")

        return multi_games

    # ==================== 예측 저장 ====================

    def _save_predictions(
        self,
        round_info: RoundInfo,
        predictions: List[GamePrediction],
        multi_games: List[Tuple[int, str, str]],
        game_type: str
    ):
        """예측 데이터 저장 (적중률 추적용)"""
        try:
            # GamePrediction → Dict 변환
            pred_dicts = []
            for pred in predictions:
                pred_dict = {
                    "game_number": pred.game_number,
                    "home_team": pred.home_team,
                    "away_team": pred.away_team,
                    "match_date": getattr(round_info, 'match_date', ''),
                    "match_time": pred.match_time,
                    "predicted": pred.recommended,
                    "confidence": pred.confidence,
                    "multi_selections": pred.multi_selections if pred.is_multi else [],
                }
                pred_dicts.append(pred_dict)

            # 복수 베팅 경기 번호 추출
            multi_nums = [m[0] for m in multi_games]

            # 저장
            success = prediction_tracker.save_prediction(
                round_info=round_info,
                predictions=pred_dicts,
                multi_games=multi_nums,
                game_type=game_type
            )

            if success:
                logger.info(f"💾 예측 저장 완료: {round_info.round_number}회차 ({game_type})")
            else:
                logger.warning(f"예측 저장 실패: {round_info.round_number}회차 ({game_type})")

        except Exception as e:
            logger.error(f"예측 저장 오류: {e}")

    # ==================== 메시지 포맷팅 ====================

    def _format_soccer_message(
        self,
        round_info: RoundInfo,
        predictions: List[GamePrediction],
        multi_games: List[Tuple[int, str, str]]
    ) -> str:
        """축구 승무패 텔레그램 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = []
        lines.append(f"⚽ *축구토토 승무패 {round_info.round_number}회차*")
        lines.append(f"📅 {now_str}")
        lines.append("━" * 24)
        lines.append("")
        lines.append("📋 *14경기 전체 예측*")
        lines.append("")

        for pred in predictions:
            home_short = pred.home_team[:8] if len(pred.home_team) > 8 else pred.home_team
            away_short = pred.away_team[:8] if len(pred.away_team) > 8 else pred.away_team

            # 1/X/2를 팀명으로 변환
            def code_to_team(code):
                if code == "1":
                    return pred.home_team[:5]
                elif code == "2":
                    return pred.away_team[:5]
                else:
                    return "무승부"

            if pred.is_multi:
                icon = "⚠️"
                team_picks = [code_to_team(s) for s in pred.multi_selections]
                mark = f"*[{'/'.join(team_picks)}]*"
                suffix = " [복수]"
            else:
                icon = "🔒" if pred.confidence >= 0.55 else "📊"
                pick_name = code_to_team(pred.recommended)
                mark = f"[{pick_name}]"
                suffix = ""

            lines.append(f"{int(pred.game_number):02d}. {home_short} vs {away_short}{suffix}")
            lines.append(f"     {icon} {mark} ({pred.confidence*100:.0f}%)")
            lines.append("")

        lines.append("━" * 24)
        lines.append("")

        # 단식 정답 (팀명으로 표시)
        lines.append("📝 *단식 정답*")

        def get_pick_name(pred):
            if pred.recommended == "1":
                return pred.home_team[:4]
            elif pred.recommended == "2":
                return pred.away_team[:4]
            else:
                return "무"

        if len(predictions) >= 14:
            line1 = " ".join([f"{i+1}:{get_pick_name(predictions[i])}" for i in range(7)])
            line2 = " ".join([f"{i+1}:{get_pick_name(predictions[i])}" for i in range(7, 14)])
            lines.append(f"`{line1}`")
            lines.append(f"`{line2}`")
        elif predictions:
            line = " ".join([f"{i+1}:{get_pick_name(predictions[i])}" for i in range(len(predictions))])
            lines.append(f"`{line}`")
        lines.append("")

        # 복식 추천
        lines.append("━" * 24)
        lines.append("")
        lines.append(f"🎰 *복수 {len(multi_games)}경기* (총 {2**len(multi_games)}조합)")

        for num, selections, probs in multi_games:
            pred = next(p for p in predictions if p.game_number == num)
            # 1/X/2를 팀명으로 변환
            sel_list = selections.split("/")
            team_picks = []
            for s in sel_list:
                if s == "1":
                    team_picks.append(pred.home_team[:5])
                elif s == "2":
                    team_picks.append(pred.away_team[:5])
                else:
                    team_picks.append("무승부")
            team_sel = "/".join(team_picks)
            lines.append(f"{num:02d}번 {pred.home_team[:5]}vs{pred.away_team[:5]} → *{team_sel}*")

        lines.append("")
        lines.append("━" * 24)
        lines.append("_베트맨 스포츠토토 AI 분석 시스템_")

        return "\n".join(lines)

    def _format_basketball_message(
        self,
        round_info: RoundInfo,
        predictions: List[GamePrediction],
        multi_games: List[Tuple[int, str, str]]
    ) -> str:
        """농구 승5패 텔레그램 메시지 포맷"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = []
        lines.append(f"🏀 *농구토토 승5패 {round_info.round_number}회차*")
        lines.append(f"📅 {now_str}")
        lines.append("━" * 24)
        lines.append("")
        lines.append("📋 *14경기 전체 예측*")
        lines.append("")

        for pred in predictions:
            home_short = pred.home_team[:7] if len(pred.home_team) > 7 else pred.home_team
            away_short = pred.away_team[:7] if len(pred.away_team) > 7 else pred.away_team

            # 승/5/패를 팀명으로 변환
            def code_to_team(code):
                if code == "승":
                    return pred.home_team[:5]
                elif code == "패":
                    return pred.away_team[:5]
                else:
                    return "접전"

            if pred.is_multi:
                icon = "⚠️"
                team_picks = [code_to_team(s) for s in pred.multi_selections]
                mark = f"*[{'/'.join(team_picks)}]*"
                suffix = " [복수]"
            else:
                icon = "🔒" if pred.confidence >= 0.50 else "📊"
                pick_name = code_to_team(pred.recommended)
                mark = f"[{pick_name}]"
                suffix = ""

            lines.append(f"{int(pred.game_number):02d}. {home_short} vs {away_short}{suffix}")
            lines.append(f"     {icon} {mark} ({pred.confidence*100:.0f}%)")
            lines.append("")

        lines.append("━" * 24)
        lines.append("")

        # 단식 정답 (팀명으로 표시)
        lines.append("📝 *단식 정답*")

        def get_pick_name(pred):
            if pred.recommended == "승":
                return pred.home_team[:4]
            elif pred.recommended == "패":
                return pred.away_team[:4]
            else:
                return "접전"

        if len(predictions) >= 14:
            line1 = " ".join([f"{i+1}:{get_pick_name(predictions[i])}" for i in range(7)])
            line2 = " ".join([f"{i+1}:{get_pick_name(predictions[i])}" for i in range(7, 14)])
            lines.append(f"`{line1}`")
            lines.append(f"`{line2}`")
        elif predictions:
            line = " ".join([f"{i+1}:{get_pick_name(predictions[i])}" for i in range(len(predictions))])
            lines.append(f"`{line}`")
        lines.append("")

        # 복식 추천
        lines.append("━" * 24)
        lines.append("")
        lines.append(f"🎰 *복식 {len(multi_games)}경기* (총 {2**len(multi_games)}조합)")

        for num, selections, probs in multi_games:
            pred = next(p for p in predictions if p.game_number == num)
            # 승/5/패를 팀명으로 변환
            sel_list = selections.split("/")
            team_picks = []
            for s in sel_list:
                if s == "승":
                    team_picks.append(pred.home_team[:5])
                elif s == "패":
                    team_picks.append(pred.away_team[:5])
                else:
                    team_picks.append("접전")
            team_sel = "/".join(team_picks)
            lines.append(f"{num:02d}번 {pred.home_team[:5]}vs{pred.away_team[:5]} → *{team_sel}*")

        lines.append("")
        lines.append("━" * 24)

        # 핵심 포인트
        lines.append("")
        lines.append("⚡ *핵심 포인트*")

        # 5 확률 가장 높은 경기
        max_5_pred = max(predictions, key=lambda x: x.prob_draw)
        lines.append(f"• 접전(5) 최고: {max_5_pred.game_number}번 ({max_5_pred.prob_draw*100:.0f}%)")

        # 고신뢰 경기 수
        high_conf = sum(1 for p in predictions if p.confidence >= 0.50)
        lines.append(f"• 고신뢰(🔒) 경기: {high_conf}개")

        # 홈승 예측 수
        win_count = sum(1 for p in predictions if p.recommended == "승")
        lines.append(f"• 홈승(승) 예측: {win_count}경기")

        lines.append("")
        lines.append("━" * 24)
        lines.append("_베트맨 스포츠토토 AI 분석 시스템_")

        return "\n".join(lines)

    # ==================== 스케줄러 ====================

    async def check_and_notify(self, test_mode: bool = False) -> Dict[str, bool]:
        """새 회차 확인 및 알림"""
        results = {"soccer": False, "basketball": False}

        # 축구 승무패 확인
        try:
            new_round = await self.round_manager.check_new_round("soccer_wdl")
            if new_round and new_round > self.last_rounds.get("soccer_wdl", 0):
                logger.info(f"🆕 축구 승무패 새 회차 감지: {new_round}회차")
                results["soccer"] = await self.analyze_soccer(test_mode)
        except Exception as e:
            logger.error(f"축구 승무패 확인 실패: {e}")

        # 농구 승5패 확인
        try:
            new_round = await self.round_manager.check_new_round("basketball_w5l")
            if new_round and new_round > self.last_rounds.get("basketball_w5l", 0):
                logger.info(f"🆕 농구 승5패 새 회차 감지: {new_round}회차")
                results["basketball"] = await self.analyze_basketball(test_mode)
        except Exception as e:
            logger.error(f"농구 승5패 확인 실패: {e}")

        return results

    async def run_scheduler(self, interval_hours: int = 6):
        """스케줄러 모드 실행"""
        logger.info(f"⏰ 스케줄러 모드 시작 (간격: {interval_hours}시간)")
        logger.info("   - 새 회차 감지 시 자동 분석 및 알림")
        logger.info("   - Ctrl+C로 종료")

        while True:
            try:
                results = await self.check_and_notify()

                if not results["soccer"] and not results["basketball"]:
                    logger.info(f"📅 새 회차 없음. {interval_hours}시간 후 재확인...")

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
        description="프로토 14경기 자동 분석 및 텔레그램 알림"
    )
    parser.add_argument("--soccer", action="store_true", help="축구 승무패만 분석")
    parser.add_argument("--basketball", action="store_true", help="농구 승5패만 분석")
    parser.add_argument("--test", action="store_true", help="테스트 모드 (전송 안함)")
    parser.add_argument("--schedule", action="store_true", help="스케줄러 모드")
    parser.add_argument("--interval", type=int, default=6, help="스케줄러 간격 (시간)")

    args = parser.parse_args()

    print("=" * 60)
    print("🎯 프로토 14경기 자동 분석 및 알림 시스템")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    notifier = AutoSportsNotifier()

    try:
        if args.schedule:
            await notifier.run_scheduler(args.interval)
        elif args.soccer:
            await notifier.analyze_soccer(test_mode=args.test)
        elif args.basketball:
            await notifier.analyze_basketball(test_mode=args.test)
        else:
            # 전체 분석
            print("🏀 농구 승5패 분석 중...")
            await notifier.analyze_basketball(test_mode=args.test)
            await asyncio.sleep(2)

            print("\n⚽ 축구 승무패 분석 중...")
            await notifier.analyze_soccer(test_mode=args.test)

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    print("✅ 완료!")
    print("📱 텔레그램 앱에서 메시지를 확인하세요.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
