"""
WeightCalculator - 특징별 가중치 계산기

각 특징에 적절한 가중치를 부여하여 최종 예측에 반영합니다.
"""

from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SportType(Enum):
    """스포츠 타입"""

    SOCCER = "soccer"
    BASKETBALL = "basketball"
    BASEBALL = "baseball"


class SeasonPhase(Enum):
    """시즌 단계"""

    EARLY = "early"  # 시즌 초반 (1-10경기)
    MID = "mid"  # 시즌 중반
    LATE = "late"  # 시즌 후반
    PLAYOFF = "playoff"  # 플레이오프


@dataclass
class WeightConfig:
    """가중치 설정"""

    recent_form: float = 0.30
    head_to_head: float = 0.20
    season_stats: float = 0.15
    home_away: float = 0.15
    injuries: float = 0.10
    tactical: float = 0.05
    other: float = 0.05

    def validate(self) -> bool:
        """가중치 합이 1.0인지 검증"""
        total = (
            self.recent_form
            + self.head_to_head
            + self.season_stats
            + self.home_away
            + self.injuries
            + self.tactical
            + self.other
        )
        return abs(total - 1.0) < 0.001

    def to_dict(self) -> Dict[str, float]:
        return {
            "recent_form": self.recent_form,
            "head_to_head": self.head_to_head,
            "season_stats": self.season_stats,
            "home_away": self.home_away,
            "injuries": self.injuries,
            "tactical": self.tactical,
            "other": self.other,
        }


class WeightCalculator:
    """
    특징별 가중치 계산기

    스포츠 종류, 시즌 단계, 경기 중요도에 따라
    동적으로 가중치를 조정합니다.
    """

    # 기본 가중치 (축구)
    DEFAULT_WEIGHTS_SOCCER = WeightConfig(
        recent_form=0.30,
        head_to_head=0.20,
        season_stats=0.15,
        home_away=0.15,
        injuries=0.10,
        tactical=0.05,
        other=0.05,
    )

    # 농구 가중치 (홈 어드밴티지 낮음, 최근 폼 중요)
    DEFAULT_WEIGHTS_BASKETBALL = WeightConfig(
        recent_form=0.35,
        head_to_head=0.15,
        season_stats=0.20,
        home_away=0.10,
        injuries=0.12,
        tactical=0.05,
        other=0.03,
    )

    # 야구 가중치 (투수 중요)
    DEFAULT_WEIGHTS_BASEBALL = WeightConfig(
        recent_form=0.25,
        head_to_head=0.15,
        season_stats=0.20,
        home_away=0.08,
        injuries=0.15,  # 선발 투수 = 부상 카테고리로 처리
        tactical=0.12,
        other=0.05,
    )

    def __init__(self, sport_type: SportType = SportType.SOCCER):
        self.sport_type = sport_type
        self.base_weights = self._get_base_weights(sport_type)

    def _get_base_weights(self, sport_type: SportType) -> WeightConfig:
        """스포츠별 기본 가중치"""
        weights_map = {
            SportType.SOCCER: self.DEFAULT_WEIGHTS_SOCCER,
            SportType.BASKETBALL: self.DEFAULT_WEIGHTS_BASKETBALL,
            SportType.BASEBALL: self.DEFAULT_WEIGHTS_BASEBALL,
        }
        return weights_map.get(sport_type, self.DEFAULT_WEIGHTS_SOCCER)

    def get_weights(
        self,
        season_phase: SeasonPhase = SeasonPhase.MID,
        match_importance: str = "normal",
        has_injury_data: bool = True,
        has_h2h_data: bool = True,
    ) -> WeightConfig:
        """
        상황별 가중치 계산

        Args:
            season_phase: 시즌 단계
            match_importance: 경기 중요도 ('low', 'normal', 'high', 'critical')
            has_injury_data: 부상 데이터 존재 여부
            has_h2h_data: 상대 전적 데이터 존재 여부

        Returns:
            조정된 가중치
        """
        # 기본 가중치 복사
        weights = WeightConfig(
            recent_form=self.base_weights.recent_form,
            head_to_head=self.base_weights.head_to_head,
            season_stats=self.base_weights.season_stats,
            home_away=self.base_weights.home_away,
            injuries=self.base_weights.injuries,
            tactical=self.base_weights.tactical,
            other=self.base_weights.other,
        )

        # 시즌 단계별 조정
        weights = self._adjust_for_season(weights, season_phase)

        # 경기 중요도별 조정
        weights = self._adjust_for_importance(weights, match_importance)

        # 데이터 가용성 조정
        weights = self._adjust_for_data_availability(
            weights, has_injury_data, has_h2h_data
        )

        # 정규화 (합이 1.0이 되도록)
        weights = self._normalize_weights(weights)

        return weights

    def _adjust_for_season(
        self, weights: WeightConfig, season_phase: SeasonPhase
    ) -> WeightConfig:
        """시즌 단계별 조정"""

        if season_phase == SeasonPhase.EARLY:
            # 시즌 초반: 시즌 통계 신뢰도 낮음
            weights.season_stats -= 0.05
            weights.recent_form += 0.03
            weights.head_to_head += 0.02

        elif season_phase == SeasonPhase.LATE:
            # 시즌 후반: 순위 경쟁 치열, 피로도 중요
            weights.season_stats += 0.03
            weights.injuries += 0.02
            weights.other -= 0.05

        elif season_phase == SeasonPhase.PLAYOFF:
            # 플레이오프: 전술, 경험 중요
            weights.tactical += 0.05
            weights.recent_form -= 0.03
            weights.other -= 0.02

        return weights

    def _adjust_for_importance(
        self, weights: WeightConfig, importance: str
    ) -> WeightConfig:
        """경기 중요도별 조정"""

        if importance == "low":
            # 친선경기 등: 전력 차이가 덜 중요
            weights.season_stats -= 0.03
            weights.other += 0.03

        elif importance == "high":
            # 중요 경기: 모든 요소 중요
            weights.tactical += 0.03
            weights.injuries += 0.02
            weights.other -= 0.05

        elif importance == "critical":
            # 결정적 경기: 멘탈, 경험 중요
            weights.tactical += 0.05
            weights.head_to_head += 0.03
            weights.other -= 0.05
            weights.recent_form -= 0.03

        return weights

    def _adjust_for_data_availability(
        self, weights: WeightConfig, has_injury_data: bool, has_h2h_data: bool
    ) -> WeightConfig:
        """데이터 가용성에 따른 조정"""

        if not has_injury_data:
            # 부상 데이터 없으면 다른 요소에 분배
            injury_weight = weights.injuries
            weights.injuries = 0.02  # 최소값
            extra = injury_weight - 0.02
            weights.recent_form += extra * 0.5
            weights.season_stats += extra * 0.5

        if not has_h2h_data:
            # 상대 전적 없으면 다른 요소에 분배
            h2h_weight = weights.head_to_head
            weights.head_to_head = 0.05  # 최소값
            extra = h2h_weight - 0.05
            weights.recent_form += extra * 0.5
            weights.season_stats += extra * 0.5

        return weights

    def _normalize_weights(self, weights: WeightConfig) -> WeightConfig:
        """가중치 정규화 (합이 1.0이 되도록)"""

        total = (
            weights.recent_form
            + weights.head_to_head
            + weights.season_stats
            + weights.home_away
            + weights.injuries
            + weights.tactical
            + weights.other
        )

        if total <= 0:
            return self.base_weights

        return WeightConfig(
            recent_form=round(weights.recent_form / total, 3),
            head_to_head=round(weights.head_to_head / total, 3),
            season_stats=round(weights.season_stats / total, 3),
            home_away=round(weights.home_away / total, 3),
            injuries=round(weights.injuries / total, 3),
            tactical=round(weights.tactical / total, 3),
            other=round(weights.other / total, 3),
        )

    def calculate_weighted_score(
        self, feature_scores: Dict[str, float], weights: Optional[WeightConfig] = None
    ) -> float:
        """
        가중치 적용 점수 계산

        Args:
            feature_scores: {
                'recent_form': 0.8,
                'head_to_head': 0.6,
                ...
            }
            weights: 가중치 설정 (None이면 기본값)

        Returns:
            가중 평균 점수 (0.0 ~ 1.0)
        """
        if weights is None:
            weights = self.base_weights

        weight_dict = weights.to_dict()

        total_score = 0.0
        total_weight = 0.0

        for key, weight in weight_dict.items():
            if key in feature_scores:
                score = feature_scores[key]
                total_score += score * weight
                total_weight += weight

        if total_weight == 0:
            return 0.5  # 기본값

        return round(total_score / total_weight, 4)

    def explain_weights(self, weights: WeightConfig) -> str:
        """가중치 설명 문자열 생성"""

        explanation = "📊 적용된 가중치:\n"
        weight_dict = weights.to_dict()

        weight_names = {
            "recent_form": "최근 폼",
            "head_to_head": "상대 전적",
            "season_stats": "시즌 성적",
            "home_away": "홈/원정",
            "injuries": "부상/컨디션",
            "tactical": "전술/감독",
            "other": "기타",
        }

        # 가중치 순으로 정렬
        sorted_weights = sorted(weight_dict.items(), key=lambda x: x[1], reverse=True)

        for key, value in sorted_weights:
            name = weight_names.get(key, key)
            bar = "█" * int(value * 20)
            explanation += f"  {name}: {value:.1%} {bar}\n"

        return explanation


# 편의 함수
def get_soccer_weights(
    season_phase: str = "mid", match_importance: str = "normal"
) -> Dict[str, float]:
    """축구 가중치 가져오기"""
    calculator = WeightCalculator(SportType.SOCCER)
    phase = (
        SeasonPhase(season_phase)
        if season_phase in [e.value for e in SeasonPhase]
        else SeasonPhase.MID
    )
    weights = calculator.get_weights(phase, match_importance)
    return weights.to_dict()


def get_basketball_weights(
    season_phase: str = "mid", match_importance: str = "normal"
) -> Dict[str, float]:
    """농구 가중치 가져오기"""
    calculator = WeightCalculator(SportType.BASKETBALL)
    phase = (
        SeasonPhase(season_phase)
        if season_phase in [e.value for e in SeasonPhase]
        else SeasonPhase.MID
    )
    weights = calculator.get_weights(phase, match_importance)
    return weights.to_dict()
