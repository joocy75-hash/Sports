"""
축구 승무패 14경기 전용 AI 분석기

베트맨 스타일의 분석 결과 생성:
- 확률(%) + 예상 환급금(원) 표시
- 기본 추천 14개 (파란색) + 복수선택 4개 (주황색)
- 단통/투마킹/지우개 전략 자동 결정
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.db.models import Match, Team, TeamStats, PredictionLog
from src.services.predictor import AdvancedStatisticalPredictor

logger = logging.getLogger(__name__)


@dataclass
class MatchPrediction:
    """단일 경기 예측 결과"""

    match_id: int
    match_number: int
    start_time: str
    home_team: str
    away_team: str
    league_name: str
    odds: Dict[str, float]  # {"home": 2.10, "draw": 3.40, "away": 3.20}
    probabilities: Dict[str, float]  # {"home": 0.42, "draw": 0.28, "away": 0.30}
    expected_return: Dict[str, int]  # {"home": 181230, "draw": 266130, "away": 526717}
    primary_pick: str  # "home", "draw", "away"
    secondary_pick: Optional[str]  # 투마킹/지우개 시 2순위
    is_bonus_pick: bool  # 복수선택 4개에 포함되는지
    strategy: str  # "단통", "투마킹", "지우개"
    confidence: int  # 1-5 별점


@dataclass
class RoundAnalysis:
    """회차 전체 분석 결과"""

    round_number: int
    category: str
    analyzed_at: str
    matches: List[Dict]
    summary: Dict[str, int]


class SoccerAnalyzer:
    """축구 승무패 14경기 전용 분석기"""

    # 100원 기준 예상 환급금 계산용 상수
    BASE_BET_AMOUNT = 100
    TOTAL_POOL_MULTIPLIER = 974000  # 예상 총 풀 금액 (약 97.4만원)

    def __init__(self):
        self.predictor = AdvancedStatisticalPredictor()

    async def analyze_round(self, round_number: int, category: str) -> RoundAnalysis:
        """
        회차 전체 14경기 분석 (최적화 버전)
        """
        async with get_session() as session:
            # 1. DB에서 해당 회차 경기 조회
            matches = await self._get_round_matches(session, round_number, category)

            if not matches:
                logger.warning(
                    f"No matches found for round {round_number}, category {category}"
                )
                return RoundAnalysis(
                    round_number=round_number,
                    category=category,
                    analyzed_at=datetime.now().isoformat(),
                    matches=[],
                    summary={"error": "경기를 찾을 수 없습니다"},
                )

            # 2. 필요한 모든 팀 ID 수집
            team_ids = set()
            for m in matches:
                if m.home_team_id:
                    team_ids.add(m.home_team_id)
                if m.away_team_id:
                    team_ids.add(m.away_team_id)

            # 3. 팀 정보 및 통계 일괄 조회
            teams_map = {}
            if team_ids:
                teams_result = await session.execute(
                    select(Team).where(Team.id.in_(list(team_ids)))
                )
                teams_map = {t.id: t for t in teams_result.scalars().all()}

                stats_result = await session.execute(
                    select(TeamStats)
                    .where(TeamStats.team_id.in_(list(team_ids)))
                    .order_by(TeamStats.team_id, TeamStats.updated_at.desc())
                )
                stats_map = {}
                for s in stats_result.scalars().all():
                    if s.team_id not in stats_map:
                        stats_map[s.team_id] = s
            else:
                stats_map = {}

            # 4. 각 경기별 예측 수행
            predictions: List[MatchPrediction] = []
            for idx, match in enumerate(matches, 1):
                # 팀 정보 가져오기
                home_team = teams_map.get(match.home_team_id)
                away_team = teams_map.get(match.away_team_id)
                home_name = (
                    home_team.name if home_team else f"Team {match.home_team_id}"
                )
                away_name = (
                    away_team.name if away_team else f"Team {match.away_team_id}"
                )

                # 팀 통계 가져오기
                home_stats_db = stats_map.get(match.home_team_id)
                away_stats_db = stats_map.get(match.away_team_id)

                home_stats = self._format_stats(home_stats_db)
                away_stats = self._format_stats(away_stats_db)

                # 확률 계산
                if "농구 승5패" in category:
                    prediction_result = (
                        self.predictor.predict_basketball_win5_probabilities(
                            home_stats, away_stats
                        )
                    )
                elif "야구 승1패" in category:
                    prediction_result = (
                        self.predictor.predict_baseball_win1_probabilities(
                            home_stats, away_stats
                        )
                    )
                else:
                    prediction_result = self.predictor.predict_score_probabilities(
                        home_stats, away_stats
                    )

                probs = prediction_result["probabilities"]
                odds = {
                    "home": match.odds_home or 2.0,
                    "draw": match.odds_draw or 3.5,
                    "away": match.odds_away or 3.0,
                }
                expected_return = self._calculate_expected_return(probs, odds)
                strategy, primary_pick, secondary_pick = self._determine_strategy(probs)
                confidence = self._calculate_confidence(probs, odds)

                predictions.append(
                    MatchPrediction(
                        match_id=match.id,
                        match_number=idx,
                        start_time=match.start_time.isoformat()
                        if match.start_time
                        else "",
                        home_team=home_name,
                        away_team=away_name,
                        league_name="KSPO 체육진흥투표권",  # 임시
                        odds=odds,
                        probabilities={
                            "home": float(round(probs["home"], 4)),
                            "draw": float(round(probs["draw"], 4)),
                            "away": float(round(probs["away"], 4)),
                        },
                        expected_return=expected_return,
                        primary_pick=primary_pick,
                        secondary_pick=secondary_pick,
                        is_bonus_pick=False,
                        strategy=strategy,
                        confidence=confidence,
                    )
                )

            # 5. 복수선택 4개 배분
            predictions = self._assign_bonus_picks(predictions)

            # 6. 결과 변환 및 DB 저장
            match_results = [asdict(p) for p in predictions]
            summary = self._calculate_summary(predictions)
            await self._save_predictions(session, predictions, round_number, category)

            return RoundAnalysis(
                round_number=round_number,
                category=category,
                analyzed_at=datetime.now().isoformat(),
                matches=match_results,
                summary=summary,
            )

    def _format_stats(self, stats: Optional[TeamStats]) -> Dict[str, float]:
        """DB 통계 객체를 딕셔너리로 변환"""
        if not stats:
            return self._default_stats()
        return {
            "goals_scored_avg": stats.xg if stats.xg else 1.3,
            "goals_conceded_avg": stats.xga if stats.xga else 1.2,
            "momentum": stats.momentum if stats.momentum else 1.0,
        }

    async def _get_round_matches(
        self, session: AsyncSession, round_number: int, category: str
    ) -> List[Match]:
        """DB에서 해당 회차의 경기 목록 조회"""
        stmt = (
            select(Match)
            .where(Match.round_number == round_number)
            .where(Match.league_id == 9999)
        )

        if category in ["프로토", "프로토 승부식"]:
            stmt = stmt.where(Match.category_name.like("프로토 %"))
        else:
            stmt = stmt.where(Match.category_name == category)

        stmt = stmt.order_by(Match.start_time, Match.id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _analyze_single_match(
        self, session: AsyncSession, match: Match, match_number: int, category: str
    ) -> MatchPrediction:
        """단일 경기 AI 분석"""

        # 1. 팀 정보 조회
        home_team = await session.get(Team, match.home_team_id)
        away_team = await session.get(Team, match.away_team_id)

        home_name = home_team.name if home_team else f"Team {match.home_team_id}"
        away_name = away_team.name if away_team else f"Team {match.away_team_id}"

        # 2. 팀 통계 조회
        home_stats = await self._get_team_stats(session, match.home_team_id)
        away_stats = await self._get_team_stats(session, match.away_team_id)

        # 3. 카테고리에 따른 확률 계산
        if "농구 승5패" in category:
            prediction_result = self.predictor.predict_basketball_win5_probabilities(
                home_stats, away_stats
            )
        elif "야구 승1패" in category:
            prediction_result = self.predictor.predict_baseball_win1_probabilities(
                home_stats, away_stats
            )
        else:
            # 기본 축구 승무패 또는 프로토
            prediction_result = self.predictor.predict_score_probabilities(
                home_stats, away_stats
            )

        probs = prediction_result["probabilities"]

        # 4. 배당률 가져오기
        odds = {
            "home": match.odds_home or 2.0,
            "draw": match.odds_draw or 3.5,
            "away": match.odds_away or 3.0,
        }

        # 5. 예상 환급금 계산 (100원 기준)
        expected_return = self._calculate_expected_return(probs, odds)

        # 6. 마킹 전략 결정
        strategy, primary_pick, secondary_pick = self._determine_strategy(probs)

        # 7. 신뢰도 계산
        confidence = self._calculate_confidence(probs, odds)

        # 8. 리그명 조회
        league_name = ""
        if match.league_id:
            from src.db.models import League

            league = await session.get(League, match.league_id)
            league_name = league.name if league else ""

        return MatchPrediction(
            match_id=match.id,
            match_number=match_number,
            start_time=match.start_time.isoformat() if match.start_time else "",
            home_team=home_name,
            away_team=away_name,
            league_name=league_name,
            odds=odds,
            probabilities={
                "home": float(round(probs["home"], 4)),
                "draw": float(round(probs["draw"], 4)),
                "away": float(round(probs["away"], 4)),
            },
            expected_return=expected_return,
            primary_pick=primary_pick,
            secondary_pick=secondary_pick,
            is_bonus_pick=False,  # 나중에 _assign_bonus_picks에서 설정
            strategy=strategy,
            confidence=confidence,
        )

    async def _get_team_stats(
        self, session: AsyncSession, team_id: int
    ) -> Dict[str, float]:
        """팀 통계 조회 (없으면 기본값 반환)"""
        if not team_id:
            return self._default_stats()

        stmt = (
            select(TeamStats)
            .where(TeamStats.team_id == team_id)
            .order_by(TeamStats.updated_at.desc())
            .limit(1)
        )
        stats = await session.scalar(stmt)

        if not stats:
            return self._default_stats()

        return {
            "goals_scored_avg": stats.xg if stats.xg else 1.3,
            "goals_conceded_avg": stats.xga if stats.xga else 1.2,
            "momentum": stats.momentum if stats.momentum else 1.0,
        }

    def _default_stats(self) -> Dict[str, float]:
        """기본 팀 통계"""
        return {
            "goals_scored_avg": 1.3,
            "goals_conceded_avg": 1.2,
            "momentum": 1.0,
        }

    def _calculate_expected_return(
        self, probs: Dict[str, float], odds: Dict[str, float]
    ) -> Dict[str, int]:
        """
        예상 환급금 계산 (100원 기준)

        계산 방식:
        - 확률 기반 기대 환급금 = 확률 * 배당 * 100원 * 조정계수
        """
        base = self.BASE_BET_AMOUNT

        # 단순 계산: 확률 * 배당 * 베팅금액 * 풀 조정
        # 베트맨 스타일 표시를 위해 큰 숫자로 표현
        return {
            "home": int(probs["home"] * odds["home"] * base * 10000),
            "draw": int(probs["draw"] * odds["draw"] * base * 10000),
            "away": int(probs["away"] * odds["away"] * base * 10000),
        }

    def _determine_strategy(
        self, probs: Dict[str, float]
    ) -> Tuple[str, str, Optional[str]]:
        """
        마킹 전략 결정

        Returns:
            Tuple[strategy, primary_pick, secondary_pick]
        """
        p_home = probs["home"]
        p_draw = probs["draw"]
        p_away = probs["away"]

        # 확률 순서 정렬
        sorted_probs = sorted(
            [("home", p_home), ("draw", p_draw), ("away", p_away)],
            key=lambda x: x[1],
            reverse=True,
        )

        first, first_prob = sorted_probs[0]
        second, second_prob = sorted_probs[1]
        third, third_prob = sorted_probs[2]

        # 1. 단통 (최고 확률 >= 60%)
        if first_prob >= 0.60:
            return "단통", first, None

        # 2. 투마킹 조건들
        # 승무 (승 + 무 >= 75% & 패 < 25%)
        if p_home + p_draw >= 0.75 and p_away < 0.25:
            if p_home >= p_draw:
                return "투마킹", "home", "draw"
            else:
                return "투마킹", "draw", "home"

        # 무패 (무 + 패 >= 75% & 승 < 25%)
        if p_draw + p_away >= 0.75 and p_home < 0.25:
            if p_away >= p_draw:
                return "투마킹", "away", "draw"
            else:
                return "투마킹", "draw", "away"

        # 승패 - 남자의 승부 (승 + 패 >= 80% & 무 < 20%)
        if p_home + p_away >= 0.80 and p_draw < 0.20:
            if p_home >= p_away:
                return "투마킹", "home", "away"
            else:
                return "투마킹", "away", "home"

        # 일반 투마킹 (상위 2개 합 >= 70%)
        if first_prob + second_prob >= 0.70:
            return "투마킹", first, second

        # 3. 지우개 (그 외)
        return "지우개", first, second

    def _calculate_confidence(
        self, probs: Dict[str, float], odds: Dict[str, float]
    ) -> int:
        """
        신뢰도 등급 계산 (1-5)

        기준:
        - ★★★★★: Edge > 10%, 최고확률 > 55%
        - ★★★★☆: Edge > 5%, 최고확률 > 50%
        - ★★★☆☆: Edge > 0%, 최고확률 > 45%
        - ★★☆☆☆: Edge > -5%
        - ★☆☆☆☆: 그 외
        """
        max_prob = max(probs.values())
        max_key = max(probs, key=probs.get)

        # Edge 계산: 모델확률 - 함축확률(1/배당)
        implied_prob = 1 / odds[max_key] if odds[max_key] > 0 else 0
        edge = max_prob - implied_prob

        if edge > 0.10 and max_prob > 0.55:
            return 5
        elif edge > 0.05 and max_prob > 0.50:
            return 4
        elif edge > 0 and max_prob > 0.45:
            return 3
        elif edge > -0.05:
            return 2
        else:
            return 1

    def _assign_bonus_picks(
        self, predictions: List[MatchPrediction]
    ) -> List[MatchPrediction]:
        """
        복수선택 4개 배분

        로직:
        1. 투마킹 경기에서 2순위 확률이 높은 순서대로 4개 선택
        2. 투마킹이 4개 미만이면 지우개 경기에서 추가
        """
        # 투마킹/지우개 경기 중 secondary_pick이 있는 것들
        candidates = []
        for p in predictions:
            if p.secondary_pick and p.strategy in ["투마킹", "지우개"]:
                # 2순위 확률 가져오기
                second_prob = p.probabilities.get(p.secondary_pick, 0)
                candidates.append((p, second_prob))

        # 2순위 확률 기준 정렬
        candidates.sort(key=lambda x: x[1], reverse=True)

        # 상위 4개에 is_bonus_pick = True 설정
        bonus_count = 0
        for pred, _ in candidates:
            if bonus_count >= 4:
                break
            pred.is_bonus_pick = True
            bonus_count += 1

        return predictions

    def _calculate_summary(self, predictions: List[MatchPrediction]) -> Dict:
        """요약 통계 계산"""
        단통_count = sum(1 for p in predictions if p.strategy == "단통")
        투마킹_count = sum(1 for p in predictions if p.strategy == "투마킹")
        지우개_count = sum(1 for p in predictions if p.strategy == "지우개")
        bonus_count = sum(1 for p in predictions if p.is_bonus_pick)

        return {
            "total_matches": len(predictions),
            "단통_count": 단통_count,
            "투마킹_count": 투마킹_count,
            "지우개_count": 지우개_count,
            "primary_picks": len(predictions),
            "bonus_picks": bonus_count,
        }

    async def _save_predictions(
        self,
        session: AsyncSession,
        predictions: List[MatchPrediction],
        round_number: int,
        category: str,
    ):
        """예측 결과를 PredictionLog에 저장"""
        for pred in predictions:
            log = PredictionLog(
                match_id=pred.match_id,
                created_at=datetime.now(),
                prob_home=pred.probabilities["home"],
                prob_draw=pred.probabilities["draw"],
                prob_away=pred.probabilities["away"],
                expected_score_home=0,  # 추후 추가
                expected_score_away=0,
                value_home=0,
                value_draw=0,
                value_away=0,
                meta={
                    "round_number": round_number,
                    "category": category,
                    "strategy": pred.strategy,
                    "primary_pick": pred.primary_pick,
                    "secondary_pick": pred.secondary_pick,
                    "is_bonus_pick": pred.is_bonus_pick,
                    "confidence": pred.confidence,
                    "analyzer": "SoccerAnalyzer_v1",
                },
            )
            session.add(log)

        await session.commit()
        logger.info(f"Saved {len(predictions)} predictions for round {round_number}")
