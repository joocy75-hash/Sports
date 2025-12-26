"""
복수 마킹 최적화 알고리즘

스포츠토토 14경기에서 최적의 마킹 조합(단통/복수/지우개) 추천
예산 제약 내에서 기대 수익률을 최대화하는 조합 생성
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class MatchMarking:
    """단일 경기 마킹 정보"""

    match_index: int
    home_team: str
    away_team: str
    probabilities: Dict[str, float]  # {'H': 0.45, 'D': 0.30, 'A': 0.25}
    confidence: int  # 0-100
    marking_type: str  # 'single', 'double', 'triple'
    selections: List[str]  # ['H'] or ['H', 'D'] or ['H', 'D', 'A']
    icon: str  # '🔒', '🛡️', '💣'
    reason: str


@dataclass
class MarkingStrategy:
    """14경기 전체 마킹 전략"""

    matches: List[MatchMarking]
    total_combinations: int
    total_cost: int  # 원화
    expected_probability: float  # 적중 예상 확률
    expected_return: float  # 기대 수익
    expected_roi: float  # 기대 ROI (%)
    budget_status: str  # '예산 내', '예산 초과'
    optimization_applied: bool


class MarkingOptimizer:
    """
    복수 마킹 최적화기

    1. 각 경기별 신뢰도에 따라 마킹 타입 결정
    2. 예산 내에서 조합 수 최적화
    3. 기대 수익률 계산
    """

    # 마킹 결정 임계값
    SINGLE_CONFIDENCE_THRESHOLD = 70  # 단통 신뢰도 임계값
    SINGLE_PROBABILITY_THRESHOLD = 0.55  # 단통 확률 임계값
    DOUBLE_PROBABILITY_THRESHOLD = 0.75  # 복수 상위2개 합 임계값

    # 예산 설정
    DEFAULT_BUDGET = 100000  # 10만원
    COST_PER_COMBINATION = 1000  # 조합당 1000원

    def __init__(self, budget: int = DEFAULT_BUDGET):
        self.budget = budget
        self.max_combinations = budget // self.COST_PER_COMBINATION

    def optimize(
        self, matches: List[Dict], strategy: str = "balanced"
    ) -> MarkingStrategy:
        """
        14경기 마킹 최적화

        Args:
            matches: 경기 정보 리스트
                [{'home': str, 'away': str, 'prediction': {...}, 'confidence': int}, ...]
            strategy: 전략 유형
                - "aggressive": 적극적 (단통 많이, 고배당 노림)
                - "balanced": 균형 (기본값)
                - "conservative": 보수적 (복수 마킹 많이, 안정적)

        Returns:
            MarkingStrategy: 최적화된 마킹 전략
        """
        # 1. 각 경기별 기본 마킹 결정
        match_markings = self._determine_initial_markings(matches, strategy)

        # 2. 조합 수 계산
        total_combinations = self._calculate_combinations(match_markings)
        total_cost = total_combinations * self.COST_PER_COMBINATION

        # 3. 예산 초과 시 최적화
        if total_cost > self.budget:
            match_markings = self._optimize_for_budget(match_markings)
            total_combinations = self._calculate_combinations(match_markings)
            total_cost = total_combinations * self.COST_PER_COMBINATION
            optimization_applied = True
        else:
            optimization_applied = False

        # 4. 기대 확률 및 수익 계산
        expected_prob = self._calculate_expected_probability(match_markings)

        # 토토 기본 배당률 가정 (14경기 전경기 적중 시 약 3-5만배)
        # 실제 배당은 KSPO에서 제공하는 값 사용 필요
        base_payout = 50000  # 5만배 가정
        expected_return = expected_prob * total_cost * base_payout
        expected_roi = (
            ((expected_return - total_cost) / total_cost) * 100 if total_cost > 0 else 0
        )

        budget_status = "예산 내" if total_cost <= self.budget else "예산 초과"

        return MarkingStrategy(
            matches=match_markings,
            total_combinations=total_combinations,
            total_cost=total_cost,
            expected_probability=expected_prob,
            expected_return=expected_return,
            expected_roi=expected_roi,
            budget_status=budget_status,
            optimization_applied=optimization_applied,
        )

    def _determine_initial_markings(
        self, matches: List[Dict], strategy: str
    ) -> List[MatchMarking]:
        """각 경기별 초기 마킹 결정"""
        markings = []

        # 전략별 임계값 조정
        conf_threshold = self.SINGLE_CONFIDENCE_THRESHOLD
        prob_threshold = self.SINGLE_PROBABILITY_THRESHOLD

        if strategy == "aggressive":
            conf_threshold = 65
            prob_threshold = 0.50
        elif strategy == "conservative":
            conf_threshold = 75
            prob_threshold = 0.60

        for idx, match in enumerate(matches):
            prediction = match.get("prediction", {})
            probs = prediction.get("probabilities", prediction)
            confidence = match.get("confidence", 50)

            # 확률 파싱
            p_home = probs.get("home", probs.get("H", 0.33))
            p_draw = probs.get("draw", probs.get("D", 0.33))
            p_away = probs.get("away", probs.get("A", 0.33))

            prob_dict = {"H": p_home, "D": p_draw, "A": p_away}

            # 확률 순위
            sorted_probs = sorted(prob_dict.items(), key=lambda x: x[1], reverse=True)
            top_choice, top_prob = sorted_probs[0]
            second_choice, second_prob = sorted_probs[1]
            third_choice, third_prob = sorted_probs[2]

            # 마킹 결정
            if confidence >= conf_threshold and top_prob >= prob_threshold:
                # 단통
                marking_type = "single"
                selections = [top_choice]
                icon = "🔒"
                reason = f"신뢰도 {confidence}%, {self._get_korean_name(top_choice)} {top_prob * 100:.0f}%"
            elif (top_prob + second_prob) >= self.DOUBLE_PROBABILITY_THRESHOLD:
                # 복수 마킹 (2개)
                marking_type = "double"
                selections = [top_choice, second_choice]
                icon = "🛡️"
                reason = f"상위2개 합 {(top_prob + second_prob) * 100:.0f}%"
            else:
                # 지우개 (3개)
                marking_type = "triple"
                selections = ["H", "D", "A"]
                icon = "💣"
                reason = f"불확실 (최대 {top_prob * 100:.0f}%)"

            markings.append(
                MatchMarking(
                    match_index=idx + 1,
                    home_team=match.get("home", match.get("home_team", f"홈{idx + 1}")),
                    away_team=match.get(
                        "away", match.get("away_team", f"원정{idx + 1}")
                    ),
                    probabilities=prob_dict,
                    confidence=confidence,
                    marking_type=marking_type,
                    selections=selections,
                    icon=icon,
                    reason=reason,
                )
            )

        return markings

    def _calculate_combinations(self, markings: List[MatchMarking]) -> int:
        """총 조합 수 계산"""
        combinations = 1
        for m in markings:
            combinations *= len(m.selections)
        return combinations

    def _optimize_for_budget(self, markings: List[MatchMarking]) -> List[MatchMarking]:
        """
        예산 초과 시 조합 수 줄이기

        전략:
        1. 지우개(3개) -> 복수(2개)로 변경 (가장 확률 낮은 것 제거)
        2. 여전히 초과면 복수(2개) -> 단통(1개)로 변경
        """
        current_combinations = self._calculate_combinations(markings)

        # 예산 내 최대 조합 수
        target = self.max_combinations

        if current_combinations <= target:
            return markings

        # 신뢰도 기준으로 정렬 (낮은 신뢰도부터 조정)
        sorted_indices = sorted(
            range(len(markings)), key=lambda i: markings[i].confidence
        )

        for idx in sorted_indices:
            if current_combinations <= target:
                break

            m = markings[idx]

            # 3개 -> 2개
            if m.marking_type == "triple":
                sorted_probs = sorted(
                    m.probabilities.items(), key=lambda x: x[1], reverse=True
                )
                new_selections = [sorted_probs[0][0], sorted_probs[1][0]]

                markings[idx] = MatchMarking(
                    match_index=m.match_index,
                    home_team=m.home_team,
                    away_team=m.away_team,
                    probabilities=m.probabilities,
                    confidence=m.confidence,
                    marking_type="double",
                    selections=new_selections,
                    icon="🛡️",
                    reason=f"예산 최적화: {m.reason}",
                )
                current_combinations = self._calculate_combinations(markings)

        # 여전히 초과면 복수 -> 단통
        for idx in sorted_indices:
            if current_combinations <= target:
                break

            m = markings[idx]

            if m.marking_type == "double":
                top_choice = max(m.probabilities.items(), key=lambda x: x[1])[0]

                markings[idx] = MatchMarking(
                    match_index=m.match_index,
                    home_team=m.home_team,
                    away_team=m.away_team,
                    probabilities=m.probabilities,
                    confidence=m.confidence,
                    marking_type="single",
                    selections=[top_choice],
                    icon="🔒",
                    reason=f"예산 최적화: {m.reason}",
                )
                current_combinations = self._calculate_combinations(markings)

        return markings

    def _calculate_expected_probability(self, markings: List[MatchMarking]) -> float:
        """
        전체 적중 예상 확률 계산

        각 경기 마킹된 선택지의 확률 합 * 다음 경기...
        """
        prob = 1.0

        for m in markings:
            match_prob = sum(m.probabilities[s] for s in m.selections)
            prob *= match_prob

        return prob

    def _get_korean_name(self, choice: str) -> str:
        """선택지 한글명"""
        names = {"H": "승", "D": "무", "A": "패"}
        return names.get(choice, choice)

    def generate_report(self, strategy: MarkingStrategy) -> str:
        """마킹 전략 리포트 생성"""
        lines = []
        lines.append("=" * 50)
        lines.append("📊 AI 토토 마킹 전략")
        lines.append("=" * 50)
        lines.append("")

        # 요약
        lines.append(f"📍 총 조합 수: {strategy.total_combinations:,}조합")
        lines.append(f"💰 투자 금액: {strategy.total_cost:,}원")
        lines.append(f"📈 예상 적중률: {strategy.expected_probability * 100:.6f}%")
        lines.append(f"🎯 상태: {strategy.budget_status}")
        if strategy.optimization_applied:
            lines.append("⚠️ 예산 최적화 적용됨")
        lines.append("")

        # 경기별 마킹
        lines.append("-" * 50)
        lines.append("📋 경기별 마킹")
        lines.append("-" * 50)

        single_count = 0
        double_count = 0
        triple_count = 0

        for m in strategy.matches:
            selection_str = "/".join([self._get_korean_name(s) for s in m.selections])
            lines.append(
                f"{m.match_index:2d}. {m.icon} [{selection_str}] "
                f"{m.home_team} vs {m.away_team}"
            )
            lines.append(f"    └ {m.reason}")

            if m.marking_type == "single":
                single_count += 1
            elif m.marking_type == "double":
                double_count += 1
            else:
                triple_count += 1

        lines.append("")
        lines.append("-" * 50)
        lines.append("📊 분석 요약")
        lines.append(f"  🔒 단통: {single_count}경기")
        lines.append(f"  🛡️ 복수: {double_count}경기")
        lines.append(f"  💣 지우개: {triple_count}경기")
        lines.append("=" * 50)

        return "\n".join(lines)


def generate_toto_strategy(
    matches: List[Dict], budget: int = 100000, strategy: str = "balanced"
) -> Tuple[MarkingStrategy, str]:
    """
    토토 마킹 전략 생성 헬퍼 함수

    Args:
        matches: 14경기 정보 리스트
        budget: 예산 (원)
        strategy: 전략 타입 ("aggressive", "balanced", "conservative")

    Returns:
        (MarkingStrategy, report_text)
    """
    optimizer = MarkingOptimizer(budget=budget)
    result = optimizer.optimize(matches, strategy)
    report = optimizer.generate_report(result)

    return result, report


# 테스트/데모용 함수
def demo_optimization():
    """데모 실행"""
    # 가상의 14경기 데이터
    sample_matches = [
        {
            "home": "리버풀",
            "away": "맨시티",
            "prediction": {"home": 0.45, "draw": 0.30, "away": 0.25},
            "confidence": 75,
        },
        {
            "home": "아스널",
            "away": "첼시",
            "prediction": {"home": 0.55, "draw": 0.25, "away": 0.20},
            "confidence": 80,
        },
        {
            "home": "토트넘",
            "away": "뉴캐슬",
            "prediction": {"home": 0.40, "draw": 0.35, "away": 0.25},
            "confidence": 55,
        },
        {
            "home": "에버턴",
            "away": "풀럼",
            "prediction": {"home": 0.35, "draw": 0.35, "away": 0.30},
            "confidence": 40,
        },
        {
            "home": "브라이턴",
            "away": "본머스",
            "prediction": {"home": 0.50, "draw": 0.30, "away": 0.20},
            "confidence": 70,
        },
        {
            "home": "레스터",
            "away": "웨스트햄",
            "prediction": {"home": 0.38, "draw": 0.32, "away": 0.30},
            "confidence": 45,
        },
        {
            "home": "바르셀로나",
            "away": "레알마드리드",
            "prediction": {"home": 0.40, "draw": 0.30, "away": 0.30},
            "confidence": 50,
        },
        {
            "home": "유벤투스",
            "away": "인터밀란",
            "prediction": {"home": 0.35, "draw": 0.35, "away": 0.30},
            "confidence": 45,
        },
        {
            "home": "바이에른",
            "away": "도르트문트",
            "prediction": {"home": 0.55, "draw": 0.25, "away": 0.20},
            "confidence": 78,
        },
        {
            "home": "PSG",
            "away": "마르세유",
            "prediction": {"home": 0.60, "draw": 0.25, "away": 0.15},
            "confidence": 85,
        },
        {
            "home": "울산현대",
            "away": "전북현대",
            "prediction": {"home": 0.42, "draw": 0.33, "away": 0.25},
            "confidence": 55,
        },
        {
            "home": "포항",
            "away": "FC서울",
            "prediction": {"home": 0.45, "draw": 0.30, "away": 0.25},
            "confidence": 60,
        },
        {
            "home": "대구FC",
            "away": "강원FC",
            "prediction": {"home": 0.40, "draw": 0.32, "away": 0.28},
            "confidence": 50,
        },
        {
            "home": "인천",
            "away": "제주",
            "prediction": {"home": 0.38, "draw": 0.34, "away": 0.28},
            "confidence": 48,
        },
    ]

    result, report = generate_toto_strategy(sample_matches, budget=100000)
    print(report)

    return result


if __name__ == "__main__":
    demo_optimization()
