"""
토토 게임 전용 서비스
- 축구 승무패 (14경기)
- 농구 승5패 (14경기)
- 야구 승1패 (14경기)
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Match
from src.services.predictor import AdvancedStatisticalPredictor

logger = logging.getLogger(__name__)


class TotoGame:
    """토토 게임 타입"""
    SOCCER_WDL = "축구 승무패"      # Win-Draw-Loss
    BASKETBALL_W5L = "농구 승5패"  # Win-5-Loss (5점차)
    BASEBALL_W1L = "야구 승1패"    # Win-1-Loss (1점차)

# 게임 타입별 sport_type 매핑
GAME_TYPE_TO_SPORT = {
    "축구 승무패": "축구",
    "농구 승5패": "농구",
    "야구 승1패": "야구",
}


class TotoService:
    """토토 게임 서비스"""

    def __init__(self):
        self.predictor = AdvancedStatisticalPredictor()

    async def get_toto_package(
        self,
        session: AsyncSession,
        game_type: str,
        round_number: Optional[int] = None
    ) -> Dict:
        """
        토토 14경기 패키지 가져오기

        Args:
            session: 데이터베이스 세션
            game_type: 게임 타입 (축구/농구/야구)
            round_number: 회차 번호 (None이면 최신 회차)

        Returns:
            14경기 패키지 + AI 예측 + 조합 추천
        """
        # 1. 회차 결정
        if round_number is None:
            round_number = await self._get_latest_round(session, game_type)

        # 2. 14경기 가져오기
        matches = await self._get_matches(session, game_type, round_number)

        if not matches:
            return {
                "success": False,
                "error": f"{game_type} {round_number}회차 경기가 없습니다",
                "game_type": game_type,
                "round_number": round_number,
                "matches": []
            }

        # 3. 각 경기 AI 예측
        match_predictions = []
        for match in matches:
            prediction = await self._predict_match(match, game_type)
            match_predictions.append({
                "match": self._format_match(match),
                "prediction": prediction
            })

        # 4. 조합 추천 생성
        recommendations = self._generate_combinations(match_predictions, game_type)

        return {
            "success": True,
            "game_type": game_type,
            "round_number": round_number,
            "total_matches": len(matches),
            "matches": match_predictions,
            "recommendations": recommendations,
            "fetched_at": datetime.now().isoformat()
        }

    async def _get_latest_round(
        self,
        session: AsyncSession,
        game_type: str
    ) -> int:
        """최신 회차 번호 가져오기"""
        stmt = (
            select(Match.round_number)
            .where(Match.category_name == game_type)
            .where(Match.round_number.isnot(None))
            .order_by(Match.round_number.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        latest_round = result.scalar_one_or_none()
        return latest_round or 0

    async def _get_matches(
        self,
        session: AsyncSession,
        game_type: str,
        round_number: int
    ) -> List[Match]:
        """특정 회차의 경기 가져오기"""
        stmt = (
            select(Match)
            .where(Match.category_name == game_type)
            .where(Match.round_number == round_number)
            .order_by(Match.start_time)
        )
        result = await session.execute(stmt)
        matches = result.scalars().all()
        return list(matches)

    async def _predict_match(
        self,
        match: Match,
        game_type: str
    ) -> Dict:
        """
        경기 예측

        Returns:
            game_type에 따라 다른 예측 결과
            - 축구: home/draw/away 확률
            - 농구: home/5point/away 확률
            - 야구: home/1point/away 확률
        """
        # 기본 통계 (실제로는 DB에서 가져와야 함)
        home_stats = {
            "xg": 1.5,
            "xga": 1.2,
            "momentum": 0.6
        }
        away_stats = {
            "xg": 1.3,
            "xga": 1.4,
            "momentum": 0.5
        }

        # Poisson 기반 예측
        try:
            prediction = self.predictor.predict_score_probabilities(
                home_stats,
                away_stats
            )
        except Exception as e:
            logger.error(f"예측 실패: {e}")
            # 기본값
            if game_type == TotoGame.SOCCER_WDL:
                return {
                    "home_prob": 40,
                    "draw_prob": 30,
                    "away_prob": 30,
                    "confidence": 30,
                    "recommended": None
                }
            else:  # 농구, 야구 (5점차/1점차)
                return {
                    "home_prob": 40,
                    "diff_prob": 25,  # 5점차 또는 1점차
                    "away_prob": 35,
                    "confidence": 30,
                    "recommended": None
                }

        # 예측 결과 변환
        probs = prediction["probabilities"]

        if game_type == TotoGame.SOCCER_WDL:
            # 축구: 승무패
            home_prob = round(probs["home"] * 100, 1)
            draw_prob = round(probs["draw"] * 100, 1)
            away_prob = round(probs["away"] * 100, 1)

            # 추천 (가장 높은 확률)
            max_prob = max(home_prob, draw_prob, away_prob)
            if max_prob == home_prob and home_prob > 45:
                recommended = "home"
            elif max_prob == away_prob and away_prob > 45:
                recommended = "away"
            elif draw_prob > 35:
                recommended = "draw"
            else:
                recommended = None

            return {
                "home_prob": home_prob,
                "draw_prob": draw_prob,
                "away_prob": away_prob,
                "confidence": round(max_prob, 1),
                "recommended": recommended,
                "reasoning": self._generate_reasoning(home_prob, draw_prob, away_prob)
            }

        elif game_type == TotoGame.BASKETBALL_W5L:
            # 농구: 승/5점차/패
            home_prob = round(probs["home"] * 100, 1)
            away_prob = round(probs["away"] * 100, 1)

            # 5점차 확률 계산 (간단히 추정)
            diff_prob = round(100 - home_prob - away_prob, 1)
            if diff_prob < 0:
                diff_prob = 15.0
                home_prob = round((100 - diff_prob) * (probs["home"] / (probs["home"] + probs["away"])), 1)
                away_prob = round(100 - home_prob - diff_prob, 1)

            max_prob = max(home_prob, diff_prob, away_prob)
            if max_prob == home_prob and home_prob > 45:
                recommended = "home"
            elif max_prob == away_prob and away_prob > 45:
                recommended = "away"
            elif diff_prob > 30:
                recommended = "5point"
            else:
                recommended = None

            return {
                "home_prob": home_prob,
                "diff_prob": diff_prob,  # 5점차
                "away_prob": away_prob,
                "confidence": round(max_prob, 1),
                "recommended": recommended,
                "reasoning": f"홈팀 승리 {home_prob}%, 5점차 {diff_prob}%, 원정 승리 {away_prob}%"
            }

        elif game_type == TotoGame.BASEBALL_W1L:
            # 야구: 승/1점차/패
            home_prob = round(probs["home"] * 100, 1)
            away_prob = round(probs["away"] * 100, 1)

            # 1점차 확률 (야구는 1점차 경기가 많음)
            diff_prob = round(100 - home_prob - away_prob, 1)
            if diff_prob < 0:
                diff_prob = 20.0  # 야구는 1점차가 더 흔함
                home_prob = round((100 - diff_prob) * (probs["home"] / (probs["home"] + probs["away"])), 1)
                away_prob = round(100 - home_prob - diff_prob, 1)

            max_prob = max(home_prob, diff_prob, away_prob)
            if max_prob == home_prob and home_prob > 45:
                recommended = "home"
            elif max_prob == away_prob and away_prob > 45:
                recommended = "away"
            elif diff_prob > 35:
                recommended = "1point"
            else:
                recommended = None

            return {
                "home_prob": home_prob,
                "diff_prob": diff_prob,  # 1점차
                "away_prob": away_prob,
                "confidence": round(max_prob, 1),
                "recommended": recommended,
                "reasoning": f"홈팀 승리 {home_prob}%, 1점차 {diff_prob}%, 원정 승리 {away_prob}%"
            }

        return {}

    def _format_match(self, match: Match) -> Dict:
        """경기 정보 포맷팅"""
        return {
            "id": match.id,
            "home_team": match.home_team_id,  # 실제로는 팀 이름 필요
            "away_team": match.away_team_id,
            "league": match.category_name,
            "start_time": match.start_time.isoformat(),
            "status": match.status,
            "odds": {
                "home": match.odds_home,
                "draw": match.odds_draw,
                "away": match.odds_away
            }
        }

    def _generate_reasoning(
        self,
        home_prob: float,
        draw_prob: float,
        away_prob: float
    ) -> str:
        """예측 근거 생성"""
        if home_prob > draw_prob and home_prob > away_prob:
            return f"홈팀 승리 확률이 {home_prob}%로 가장 높습니다"
        elif away_prob > draw_prob and away_prob > home_prob:
            return f"원정팀 승리 확률이 {away_prob}%로 가장 높습니다"
        else:
            return f"무승부 확률이 {draw_prob}%로 높습니다"

    def _generate_combinations(
        self,
        match_predictions: List[Dict],
        game_type: str
    ) -> List[Dict]:
        """
        AI 추천 조합 생성

        14경기 중 신뢰도 높은 경기들로 3가지 조합 추천
        """
        # 신뢰도 순으로 정렬
        sorted_matches = sorted(
            match_predictions,
            key=lambda x: x["prediction"].get("confidence", 0),
            reverse=True
        )

        # 조합 1: 가장 안전한 조합 (신뢰도 높은 것만)
        safe_combination = []
        for mp in sorted_matches:
            pred = mp["prediction"]
            recommended = pred.get("recommended")
            confidence = pred.get("confidence", 0)

            if recommended and confidence > 70:
                safe_combination.append({
                    "match_id": mp["match"]["id"],
                    "selection": recommended,
                    "confidence": confidence
                })

        # 조합 2: 균형 조합
        balanced_combination = []
        for mp in sorted_matches[:10]:  # 상위 10경기
            pred = mp["prediction"]
            recommended = pred.get("recommended")

            if recommended:
                balanced_combination.append({
                    "match_id": mp["match"]["id"],
                    "selection": recommended,
                    "confidence": pred.get("confidence", 0)
                })

        # 조합 3: 고배당 도전 (낮은 확률이지만 적중 시 높은 배당)
        risky_combination = []
        for mp in match_predictions:
            pred = mp["prediction"]

            # 어웨이 또는 무승부 위주 (보통 배당이 높음)
            if game_type == TotoGame.SOCCER_WDL:
                if pred.get("draw_prob", 0) > 30 or pred.get("away_prob", 0) > 40:
                    recommended = "away" if pred.get("away_prob", 0) > pred.get("draw_prob", 0) else "draw"
                    risky_combination.append({
                        "match_id": mp["match"]["id"],
                        "selection": recommended,
                        "confidence": pred.get("confidence", 0)
                    })
            else:
                # 농구/야구는 득점차 선택을 포함
                risky_combination.append({
                    "match_id": mp["match"]["id"],
                    "selection": pred.get("recommended", "home"),
                    "confidence": pred.get("confidence", 0)
                })

        return [
            {
                "name": "안전 조합",
                "description": "신뢰도 70% 이상 경기만 선택",
                "selections": safe_combination[:min(14, len(safe_combination))],
                "expected_win_rate": self._calculate_expected_win_rate(safe_combination[:14]),
                "risk_level": "low"
            },
            {
                "name": "균형 조합",
                "description": "신뢰도 상위 경기 중심",
                "selections": balanced_combination[:min(14, len(balanced_combination))],
                "expected_win_rate": self._calculate_expected_win_rate(balanced_combination[:14]),
                "risk_level": "medium"
            },
            {
                "name": "고배당 도전",
                "description": "높은 배당 기대 조합",
                "selections": risky_combination[:min(14, len(risky_combination))],
                "expected_win_rate": self._calculate_expected_win_rate(risky_combination[:14]),
                "risk_level": "high"
            }
        ]

    def _calculate_expected_win_rate(self, selections: List[Dict]) -> float:
        """조합의 예상 적중률 계산"""
        if not selections:
            return 0.0

        # 각 경기의 신뢰도를 곱하여 전체 적중 확률 계산
        total_prob = 1.0
        for selection in selections:
            confidence = selection.get("confidence", 50) / 100
            total_prob *= confidence

        return round(total_prob * 100, 2)
