"""
언더독/이변 감지 시스템

CLAUDE.md 섹션 3.2 "이변 감지 로직" 구현:
- 확률 분포 애매함 (1위-2위 차이 < 15%)
- AI 모델 간 불일치 (표준편차 > 20%)
- 폼-예측 상충 (최근 폼과 예측 반대)
- 랭킹 불일치 (강팀인데 낮은 승률)
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


@dataclass
class UnderdogSignal:
    """이변 신호"""
    signal_type: str  # "prob_close" | "ai_disagree" | "form_conflict" | "rank_mismatch"
    strength: float  # 0.0 ~ 1.0
    description: str
    weight: float  # 신호 가중치


@dataclass
class UnderdogAnalysis:
    """언더독 분석 결과"""
    is_underdog_game: bool  # 이변 가능성 높은 경기인가?
    upset_probability: float  # 이변 확률 (0~100%)
    signals: List[UnderdogSignal]  # 감지된 신호들
    recommendation: str  # "단일" | "복수"
    multi_picks: List[str]  # 복수 베팅 추천 (예: ["1", "X"])
    confidence: float  # 분석 신뢰도


class UnderdogDetector:
    """
    언더독/이변 감지기

    CLAUDE.md의 핵심 원칙:
    "프로토 14경기는 ALL or NOTHING이므로 이변 감지가 핵심"
    """

    def __init__(self):
        # 이변 감지 임계값
        self.PROB_CLOSE_THRESHOLD = 15.0  # 1위-2위 확률 차이 < 15%
        self.AI_DISAGREE_THRESHOLD = 20.0  # AI 표준편차 > 20%
        self.UPSET_THRESHOLD = 55.0  # 이변 확률 >= 55% → 복수 베팅

        # 신호 가중치 (CLAUDE.md 섹션 3.2)
        self.WEIGHTS = {
            "prob_close": 0.35,      # 확률 분포 애매함
            "ai_disagree": 0.30,     # AI 모델 간 불일치
            "form_conflict": 0.20,   # 폼-예측 상충
            "rank_mismatch": 0.15,   # 랭킹 불일치
        }

    def analyze_game(
        self,
        predictions: Dict[str, float],
        ai_opinions: Optional[List[Dict]] = None,
        team_info: Optional[Dict] = None,
    ) -> UnderdogAnalysis:
        """
        경기 이변 가능성 분석

        Args:
            predictions: {"home": 45.5, "draw": 30.2, "away": 24.3}
            ai_opinions: AI별 예측 (선택)
            team_info: 팀 정보 (선택)

        Returns:
            UnderdogAnalysis: 이변 분석 결과
        """
        signals = []

        # 신호 1: 확률 분포 애매함
        signal1 = self._check_probability_closeness(predictions)
        if signal1:
            signals.append(signal1)

        # 신호 2: AI 모델 간 불일치
        if ai_opinions:
            signal2 = self._check_ai_disagreement(ai_opinions)
            if signal2:
                signals.append(signal2)

        # 신호 3: 폼-예측 상충
        if team_info:
            signal3 = self._check_form_conflict(predictions, team_info)
            if signal3:
                signals.append(signal3)

        # 신호 4: 랭킹 불일치
        if team_info:
            signal4 = self._check_rank_mismatch(predictions, team_info)
            if signal4:
                signals.append(signal4)

        # 이변 확률 계산 (CLAUDE.md 공식)
        upset_prob = self._calculate_upset_probability(signals, predictions)

        # AI 컨센서스 부족 시 추가 가중치
        if ai_opinions:
            consensus_penalty = self._calculate_consensus_penalty(ai_opinions)
            upset_prob += consensus_penalty

        # 복수 베팅 추천
        is_underdog = upset_prob >= self.UPSET_THRESHOLD
        recommendation = "복수" if is_underdog else "단일"
        multi_picks = self._recommend_multi_picks(predictions, upset_prob) if is_underdog else []

        # 신뢰도 계산
        confidence = min(100.0, len(signals) * 20.0 + 20.0)

        logger.info(
            f"[UnderdogDetector] 이변 확률={upset_prob:.1f}%, "
            f"신호={len(signals)}개, 추천={recommendation}"
        )

        return UnderdogAnalysis(
            is_underdog_game=is_underdog,
            upset_probability=upset_prob,
            signals=signals,
            recommendation=recommendation,
            multi_picks=multi_picks,
            confidence=confidence,
        )

    def _check_probability_closeness(self, predictions: Dict[str, float]) -> Optional[UnderdogSignal]:
        """
        신호 1: 확률 분포 애매함

        1위와 2위 확률 차이가 15% 미만이면 예측이 불확실함
        """
        # 축구: home, draw, away
        # 농구: home, diff, away
        probs = sorted(predictions.values(), reverse=True)

        if len(probs) < 2:
            return None

        first = probs[0]
        second = probs[1]
        diff = first - second

        if diff < self.PROB_CLOSE_THRESHOLD:
            strength = 1.0 - (diff / self.PROB_CLOSE_THRESHOLD)
            return UnderdogSignal(
                signal_type="prob_close",
                strength=strength,
                description=f"1위({first:.1f}%)와 2위({second:.1f}%) 확률 차이 {diff:.1f}%로 근소",
                weight=self.WEIGHTS["prob_close"],
            )

        return None

    def _check_ai_disagreement(self, ai_opinions: List[Dict]) -> Optional[UnderdogSignal]:
        """
        신호 2: AI 모델 간 불일치

        AI들의 예측이 크게 다르면 경기가 불확실함
        """
        if not ai_opinions or len(ai_opinions) < 3:
            return None

        # 각 AI의 최고 확률 추출
        max_probs = []
        for opinion in ai_opinions:
            if "probabilities" in opinion:
                probs = opinion["probabilities"]
                max_prob = max(probs.values())
                max_probs.append(max_prob)

        if len(max_probs) < 3:
            return None

        # 표준편차 계산
        std_dev = statistics.stdev(max_probs)

        if std_dev > self.AI_DISAGREE_THRESHOLD:
            strength = min(1.0, std_dev / 30.0)
            return UnderdogSignal(
                signal_type="ai_disagree",
                strength=strength,
                description=f"AI 모델 간 표준편차 {std_dev:.1f}%로 의견 불일치",
                weight=self.WEIGHTS["ai_disagree"],
            )

        return None

    def _check_form_conflict(self, predictions: Dict[str, float], team_info: Dict) -> Optional[UnderdogSignal]:
        """
        신호 3: 폼-예측 상충

        최근 폼이 좋은 팀인데 예측 확률이 낮으면 이변 가능
        """
        # 간단한 구현 (추후 고도화)
        # 실제로는 team_info에서 최근 5경기 폼을 확인
        home_form = team_info.get("home_recent_form", 0.5)
        away_form = team_info.get("away_recent_form", 0.5)

        home_prob = predictions.get("home", 33.3) / 100.0
        away_prob = predictions.get("away", 33.3) / 100.0

        # 폼이 좋은데 예측이 낮으면 의심
        home_conflict = abs(home_form - home_prob)
        away_conflict = abs(away_form - away_prob)

        max_conflict = max(home_conflict, away_conflict)

        if max_conflict > 0.3:
            strength = min(1.0, max_conflict)
            return UnderdogSignal(
                signal_type="form_conflict",
                strength=strength,
                description=f"최근 폼과 예측 확률 불일치 (차이 {max_conflict*100:.1f}%)",
                weight=self.WEIGHTS["form_conflict"],
            )

        return None

    def _check_rank_mismatch(self, predictions: Dict[str, float], team_info: Dict) -> Optional[UnderdogSignal]:
        """
        신호 4: 랭킹 불일치

        강팀인데 승률이 낮으면 이변 가능
        """
        # 간단한 구현 (추후 고도화)
        home_rank = team_info.get("home_rank", 10)
        away_rank = team_info.get("away_rank", 10)

        home_prob = predictions.get("home", 33.3)
        away_prob = predictions.get("away", 33.3)

        # 랭킹 상위팀(1~5위)인데 승률 < 50%
        if home_rank <= 5 and home_prob < 50:
            strength = (50 - home_prob) / 50.0
            return UnderdogSignal(
                signal_type="rank_mismatch",
                strength=strength,
                description=f"홈팀 랭킹 {home_rank}위인데 승률 {home_prob:.1f%}로 낮음",
                weight=self.WEIGHTS["rank_mismatch"],
            )

        if away_rank <= 5 and away_prob < 50:
            strength = (50 - away_prob) / 50.0
            return UnderdogSignal(
                signal_type="rank_mismatch",
                strength=strength,
                description=f"원정팀 랭킹 {away_rank}위인데 승률 {away_prob:.1f%}로 낮음",
                weight=self.WEIGHTS["rank_mismatch"],
            )

        return None

    def _calculate_upset_probability(
        self,
        signals: List[UnderdogSignal],
        predictions: Dict[str, float],
    ) -> float:
        """
        이변 확률 계산 (CLAUDE.md 공식)

        upset_probability = (
            (signal_1 * 0.35) +
            (signal_2 * 0.30) +
            (signal_3 * 0.20) +
            (signal_4 * 0.15)
        )
        """
        if not signals:
            return 0.0

        total = 0.0
        for signal in signals:
            contribution = signal.strength * signal.weight * 100
            total += contribution

        # 확률 분포가 균등할수록 이변 가능성 증가
        probs = list(predictions.values())
        if len(probs) >= 2:
            entropy = self._calculate_entropy(probs)
            total += entropy * 10  # 최대 +10%

        return min(100.0, total)

    def _calculate_entropy(self, probs: List[float]) -> float:
        """
        확률 분포의 엔트로피 계산

        확률이 균등하게 분포할수록 높은 값 (불확실성 증가)
        """
        import math

        # 확률 정규화
        total = sum(probs)
        if total == 0:
            return 0.0

        normalized = [p / total for p in probs]

        # 엔트로피 계산: -Σ(p * log(p))
        entropy = 0.0
        for p in normalized:
            if p > 0:
                entropy -= p * math.log(p, 2)

        # 정규화 (0~1)
        max_entropy = math.log(len(probs), 2)
        return entropy / max_entropy if max_entropy > 0 else 0.0

    def _calculate_consensus_penalty(self, ai_opinions: List[Dict]) -> float:
        """
        AI 컨센서스 부족 시 이변 확률 증가

        CLAUDE.md: "(1 - model_consensus) * 20"
        """
        if not ai_opinions or len(ai_opinions) < 3:
            return 0.0

        # 각 AI의 예측 결과 추출
        predictions = []
        for opinion in ai_opinions:
            if "winner" in opinion:
                predictions.append(opinion["winner"])

        if not predictions:
            return 0.0

        # 가장 많이 나온 예측의 비율
        from collections import Counter
        counter = Counter(predictions)
        most_common_count = counter.most_common(1)[0][1]
        consensus = most_common_count / len(predictions)

        # 컨센서스가 낮을수록 이변 확률 증가
        penalty = (1 - consensus) * 20

        logger.debug(f"[UnderdogDetector] AI 컨센서스={consensus:.2f}, 페널티=+{penalty:.1f}%")

        return penalty

    def _recommend_multi_picks(
        self,
        predictions: Dict[str, float],
        upset_prob: float,
    ) -> List[str]:
        """
        복수 베팅 추천

        이변 확률이 높으면 상위 2개 결과를 모두 선택
        """
        # 확률 순으로 정렬
        sorted_picks = sorted(
            predictions.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 상위 2개 선택
        top_picks = [pick[0] for pick in sorted_picks[:2]]

        # 축구: home → 1, draw → X, away → 2
        # 농구: home → 승, diff → 5, away → 패
        mapping = {
            "home": "1",
            "draw": "X",
            "away": "2",
            "diff": "5",
        }

        return [mapping.get(pick, pick) for pick in top_picks]

    def analyze_14_games(
        self,
        all_predictions: List[Dict],
    ) -> Tuple[List[int], int]:
        """
        14경기 중 복수 베팅 경기 선정

        Args:
            all_predictions: 14경기 예측 결과 리스트

        Returns:
            (복수 베팅 경기 번호 리스트, 복수 베팅 수)
        """
        underdog_games = []

        for idx, pred in enumerate(all_predictions, 1):
            analysis = self.analyze_game(
                predictions=pred.get("probabilities", {}),
                ai_opinions=pred.get("ai_opinions"),
                team_info=pred.get("team_info"),
            )

            if analysis.is_underdog_game:
                underdog_games.append(idx)

        # 상위 4경기 선택 (CLAUDE.md 기준)
        multi_games = sorted(
            underdog_games,
            key=lambda x: all_predictions[x-1].get("upset_prob", 0),
            reverse=True
        )[:4]

        logger.info(
            f"[UnderdogDetector] 14경기 분석 완료: "
            f"이변 가능 {len(underdog_games)}경기, 복수 베팅 {len(multi_games)}경기"
        )

        return multi_games, len(multi_games)
