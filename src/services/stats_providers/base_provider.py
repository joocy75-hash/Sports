"""
Base Provider for Team Statistics

추상 베이스 클래스로, 모든 통계 제공자는 이 인터페이스를 구현해야 합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class TeamStats:
    """
    팀 통계 데이터 모델

    Attributes:
        team_name: 팀 이름
        league: 리그 이름
        attack_rating: 공격 레이팅 (0-100)
        defense_rating: 수비 레이팅 (0-100)
        recent_form: 최근 5경기 폼 점수 (0-100)
        win_rate: 승률 (0.0-1.0)
        home_advantage: 홈 어드밴티지 점수 (0-100, 홈 경기인 경우에만 적용)
        avg_goals_scored: 경기당 평균 득점 (축구)
        avg_goals_conceded: 경기당 평균 실점 (축구)
        avg_points_scored: 경기당 평균 득점 (농구)
        avg_points_conceded: 경기당 평균 실점 (농구)
        last_updated: 데이터 마지막 업데이트 시각
        source: 데이터 소스 ('api_football', 'balldontlie', 'default', 'cache')
    """
    team_name: str
    league: str
    attack_rating: float  # 0-100
    defense_rating: float  # 0-100
    recent_form: float  # 0-100
    win_rate: float  # 0.0-1.0
    home_advantage: float = 5.0  # 0-100
    avg_goals_scored: Optional[float] = None  # 축구
    avg_goals_conceded: Optional[float] = None  # 축구
    avg_points_scored: Optional[float] = None  # 농구
    avg_points_conceded: Optional[float] = None  # 농구
    last_updated: datetime = None
    source: str = "unknown"

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (캐싱용)"""
        return {
            "team_name": self.team_name,
            "league": self.league,
            "attack_rating": self.attack_rating,
            "defense_rating": self.defense_rating,
            "recent_form": self.recent_form,
            "win_rate": self.win_rate,
            "home_advantage": self.home_advantage,
            "avg_goals_scored": self.avg_goals_scored,
            "avg_goals_conceded": self.avg_goals_conceded,
            "avg_points_scored": self.avg_points_scored,
            "avg_points_conceded": self.avg_points_conceded,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamStats":
        """딕셔너리로부터 생성 (캐시 로드용)"""
        if "last_updated" in data and data["last_updated"]:
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        return cls(**data)


class BaseStatsProvider(ABC):
    """
    팀 통계 제공자 추상 베이스 클래스

    모든 통계 제공자는 이 클래스를 상속받아 구현해야 합니다.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: API 키 (필요한 경우)
        """
        self.api_key = api_key
        self.provider_name = "base"

    @abstractmethod
    async def get_team_stats(
        self,
        team_name: str,
        league: str,
        is_home: bool = True
    ) -> Optional[TeamStats]:
        """
        팀 통계 가져오기

        Args:
            team_name: 팀 이름
            league: 리그 이름
            is_home: 홈 경기 여부

        Returns:
            TeamStats 또는 None (실패 시)
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        API 사용 가능 여부 확인

        Returns:
            True if API is available and responding
        """
        pass

    def normalize_team_name(self, team_name: str) -> str:
        """
        팀 이름 정규화

        베트맨 형식 → API 형식 변환
        예: "맨체스U" → "Manchester United"

        Args:
            team_name: 원본 팀 이름

        Returns:
            정규화된 팀 이름
        """
        # 기본 구현: 그대로 반환
        # 각 provider에서 오버라이드 가능
        return team_name.strip()

    def get_default_stats(
        self,
        team_name: str,
        league: str,
        is_home: bool = True
    ) -> TeamStats:
        """
        기본 통계값 반환 (API 실패 시 사용)

        Args:
            team_name: 팀 이름
            league: 리그 이름
            is_home: 홈 경기 여부

        Returns:
            기본값으로 채워진 TeamStats
        """
        return TeamStats(
            team_name=team_name,
            league=league,
            attack_rating=50.0,
            defense_rating=50.0,
            recent_form=50.0,
            win_rate=0.5,
            home_advantage=5.0 if is_home else 0.0,
            avg_goals_scored=1.5,  # 축구 기본값
            avg_goals_conceded=1.5,
            avg_points_scored=105.0,  # 농구 기본값
            avg_points_conceded=105.0,
            last_updated=datetime.now(),
            source="default",
        )
