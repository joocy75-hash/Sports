"""
FeatureEngineer - 특징 엔지니어링

원시 데이터를 AI 입력 형태로 변환합니다.
팀 강도, 폼, 대결 지표 등을 계산합니다.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class SportType(Enum):
    """스포츠 타입"""

    SOCCER = "soccer"
    BASKETBALL = "basketball"
    BASEBALL = "baseball"


@dataclass
class TeamFeatures:
    """팀별 특징"""

    team_name: str

    # 시즌 성적
    season_wins: int = 0
    season_draws: int = 0
    season_losses: int = 0
    season_goals_for: int = 0
    season_goals_against: int = 0
    league_rank: int = 0

    # 홈/원정 성적
    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0
    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0

    # 최근 폼 (WWDLW 형태)
    recent_form: str = ""
    home_form: str = ""
    away_form: str = ""

    # 득점력
    avg_goals_scored: float = 0.0
    avg_goals_conceded: float = 0.0

    # 기타
    rest_days: int = 3  # 마지막 경기 후 휴식일수
    injury_count: int = 0  # 부상자 수

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MatchFeatures:
    """경기 특징"""

    match_id: str
    sport_type: SportType

    home_team: TeamFeatures
    away_team: TeamFeatures

    # 상대 전적
    h2h_home_wins: int = 0
    h2h_draws: int = 0
    h2h_away_wins: int = 0
    h2h_home_goals: int = 0
    h2h_away_goals: int = 0

    # 맥락 정보
    league_name: str = ""
    match_importance: str = "normal"  # 'low', 'normal', 'high', 'critical'
    is_derby: bool = False

    # 계산된 지표
    home_strength: float = 0.0
    away_strength: float = 0.0
    home_form_score: float = 0.0
    away_form_score: float = 0.0
    h2h_advantage: float = 0.0  # 양수: 홈팀 유리, 음수: 원정팀 유리

    # 최종 특징 벡터
    feature_vector: Dict[str, float] = field(default_factory=dict)

    # 정성적 정보
    home_news_summary: str = ""
    away_news_summary: str = ""
    key_factors: List[str] = field(default_factory=list)


class FeatureEngineer:
    """
    특징 엔지니어링 클래스

    원시 데이터를 AI 분석에 적합한 특징 벡터로 변환합니다.
    """

    def __init__(self, sport_type: SportType = SportType.SOCCER):
        self.sport_type = sport_type
        self.form_weights = [1.4, 1.2, 1.0, 0.8, 0.6]  # 최근 경기에 높은 가중치

    def extract_features(self, match_data: Dict) -> MatchFeatures:
        """
        경기 데이터에서 특징 추출

        Args:
            match_data: KSPO API 등에서 가져온 원시 데이터

        Returns:
            MatchFeatures 객체
        """
        # 홈팀 특징 추출
        home_features = self._extract_team_features(
            match_data.get("home_team", {}),
            match_data.get("home_stats", {}),
            is_home=True,
        )

        # 원정팀 특징 추출
        away_features = self._extract_team_features(
            match_data.get("away_team", {}),
            match_data.get("away_stats", {}),
            is_home=False,
        )

        # 경기 특징 생성
        match_features = MatchFeatures(
            match_id=match_data.get("match_id", ""),
            sport_type=self.sport_type,
            home_team=home_features,
            away_team=away_features,
            league_name=match_data.get("league", ""),
        )

        # 상대 전적 정보 추가
        h2h = match_data.get("h2h", {})
        match_features.h2h_home_wins = h2h.get("home_wins", 0)
        match_features.h2h_draws = h2h.get("draws", 0)
        match_features.h2h_away_wins = h2h.get("away_wins", 0)
        match_features.h2h_home_goals = h2h.get("home_goals", 0)
        match_features.h2h_away_goals = h2h.get("away_goals", 0)

        # 뉴스 정보 추가
        match_features.home_news_summary = match_data.get("home_news", {}).get(
            "summary", ""
        )
        match_features.away_news_summary = match_data.get("away_news", {}).get(
            "summary", ""
        )

        # 계산된 지표 생성
        match_features.home_strength = self._calculate_team_strength(home_features)
        match_features.away_strength = self._calculate_team_strength(away_features)
        match_features.home_form_score = self._form_to_score(home_features.recent_form)
        match_features.away_form_score = self._form_to_score(away_features.recent_form)
        match_features.h2h_advantage = self._calculate_h2h_advantage(match_features)

        # 경기 중요도 판단
        match_features.match_importance = self._determine_importance(match_data)

        # 주요 요인 도출
        match_features.key_factors = self._identify_key_factors(match_features)

        # 최종 특징 벡터 생성
        match_features.feature_vector = self._create_feature_vector(match_features)

        return match_features

    def _extract_team_features(
        self, team_info: Dict, stats: Dict, is_home: bool
    ) -> TeamFeatures:
        """팀 특징 추출"""

        features = TeamFeatures(team_name=team_info.get("name", "Unknown"))

        # 시즌 성적
        season = stats.get("season", {})
        features.season_wins = season.get("wins", 0)
        features.season_draws = season.get("draws", 0)
        features.season_losses = season.get("losses", 0)
        features.season_goals_for = season.get("goals_for", 0)
        features.season_goals_against = season.get("goals_against", 0)
        features.league_rank = season.get("rank", 10)

        # 홈/원정 성적
        home_stats = stats.get("home", {})
        away_stats = stats.get("away", {})
        features.home_wins = home_stats.get("wins", 0)
        features.home_draws = home_stats.get("draws", 0)
        features.home_losses = home_stats.get("losses", 0)
        features.away_wins = away_stats.get("wins", 0)
        features.away_draws = away_stats.get("draws", 0)
        features.away_losses = away_stats.get("losses", 0)

        # 최근 폼
        features.recent_form = stats.get("recent_form", "")
        features.home_form = stats.get("home_form", "")
        features.away_form = stats.get("away_form", "")

        # 평균 득점
        total_matches = (
            features.season_wins + features.season_draws + features.season_losses
        )
        if total_matches > 0:
            features.avg_goals_scored = round(
                features.season_goals_for / total_matches, 2
            )
            features.avg_goals_conceded = round(
                features.season_goals_against / total_matches, 2
            )

        # 휴식 일수
        features.rest_days = stats.get("rest_days", 3)

        # 부상자 수
        features.injury_count = len(stats.get("injuries", []))

        return features

    def _calculate_team_strength(self, team: TeamFeatures) -> float:
        """
        팀 강도 계산 (0.0 ~ 1.0)

        고려 요소:
        - 승률
        - 리그 순위
        - 득실차
        """
        total_matches = team.season_wins + team.season_draws + team.season_losses

        if total_matches == 0:
            return 0.5  # 기본값

        # 승률 (승점 기준)
        points = team.season_wins * 3 + team.season_draws
        max_points = total_matches * 3
        win_rate = points / max_points if max_points > 0 else 0.5

        # 순위 점수 (1위=1.0, 20위=0.0 가정)
        rank_score = max(0, 1 - (team.league_rank - 1) / 19)

        # 득실차 점수 (-30 ~ +30 범위를 0~1로 정규화)
        goal_diff = team.season_goals_for - team.season_goals_against
        gd_score = (goal_diff + 30) / 60
        gd_score = max(0, min(1, gd_score))

        # 가중 평균 (승률 40%, 순위 35%, 득실차 25%)
        strength = (win_rate * 0.40) + (rank_score * 0.35) + (gd_score * 0.25)

        return round(strength, 4)

    def _form_to_score(self, form: str) -> float:
        """
        폼 문자열을 점수로 변환 (0.0 ~ 1.0)

        'WWDLW' → 가중치 적용된 점수
        """
        if not form:
            return 0.5  # 기본값

        form = form.upper()[:5]  # 최근 5경기만

        total_score = 0
        total_weight = 0

        for i, result in enumerate(form):
            weight = self.form_weights[i] if i < len(self.form_weights) else 0.5

            if result == "W":
                score = 1.0
            elif result == "D":
                score = 0.5
            elif result == "L":
                score = 0.0
            else:
                continue

            total_score += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5

        return round(total_score / total_weight, 4)

    def _calculate_h2h_advantage(self, match: MatchFeatures) -> float:
        """
        상대 전적 어드밴티지 계산 (-1.0 ~ 1.0)

        양수: 홈팀 유리
        음수: 원정팀 유리
        0: 균형
        """
        total_h2h = match.h2h_home_wins + match.h2h_draws + match.h2h_away_wins

        if total_h2h == 0:
            return 0.0  # 상대 전적 없음

        # 승리 비율 기반
        home_score = match.h2h_home_wins + (match.h2h_draws * 0.5)
        away_score = match.h2h_away_wins + (match.h2h_draws * 0.5)

        total_score = home_score + away_score
        if total_score == 0:
            return 0.0

        # -1 ~ 1 범위로 변환
        advantage = (home_score - away_score) / total_score

        # 골 차이 보정
        if total_h2h >= 3:
            goal_diff = match.h2h_home_goals - match.h2h_away_goals
            goal_adjustment = goal_diff / (total_h2h * 3)  # 평균 3골 기준
            goal_adjustment = max(-0.2, min(0.2, goal_adjustment))
            advantage += goal_adjustment

        return round(max(-1.0, min(1.0, advantage)), 4)

    def _determine_importance(self, match_data: Dict) -> str:
        """경기 중요도 판단"""

        # 기본값
        importance = "normal"

        # 리그명 체크
        league = match_data.get("league", "").lower()

        if any(x in league for x in ["결승", "final", "챔피언스", "champions"]):
            importance = "critical"
        elif any(x in league for x in ["준결승", "semi", "플레이오프"]):
            importance = "high"
        elif any(x in league for x in ["친선", "friendly"]):
            importance = "low"

        # 순위 경쟁 체크
        home_rank = match_data.get("home_stats", {}).get("season", {}).get("rank", 10)
        away_rank = match_data.get("away_stats", {}).get("season", {}).get("rank", 10)

        if home_rank <= 4 and away_rank <= 4:
            importance = "high"  # 상위권 직접 대결
        elif home_rank >= 16 and away_rank >= 16:
            importance = "high"  # 강등권 직접 대결

        return importance

    def _identify_key_factors(self, match: MatchFeatures) -> List[str]:
        """주요 요인 도출"""

        factors = []

        # 1. 팀 강도 차이
        strength_diff = abs(match.home_strength - match.away_strength)
        if strength_diff > 0.2:
            stronger = "홈팀" if match.home_strength > match.away_strength else "원정팀"
            factors.append(f"{stronger} 전력 우위 (차이: {strength_diff:.2f})")

        # 2. 폼 차이
        form_diff = match.home_form_score - match.away_form_score
        if abs(form_diff) > 0.2:
            better_form = "홈팀" if form_diff > 0 else "원정팀"
            factors.append(f"{better_form} 최근 폼 우수")

        # 3. 홈 어드밴티지
        home_team = match.home_team
        home_total = home_team.home_wins + home_team.home_draws + home_team.home_losses
        if home_total >= 5:
            home_win_rate = home_team.home_wins / home_total
            if home_win_rate >= 0.6:
                factors.append("홈팀 홈 경기 강함")
            elif home_win_rate <= 0.3:
                factors.append("홈팀 홈 경기 약함")

        # 4. 상대 전적
        if abs(match.h2h_advantage) > 0.3:
            h2h_winner = "홈팀" if match.h2h_advantage > 0 else "원정팀"
            factors.append(f"{h2h_winner} 상대 전적 우위")

        # 5. 부상자 영향
        if match.home_team.injury_count >= 3:
            factors.append(f"홈팀 부상자 다수 ({match.home_team.injury_count}명)")
        if match.away_team.injury_count >= 3:
            factors.append(f"원정팀 부상자 다수 ({match.away_team.injury_count}명)")

        # 6. 피로도
        if match.home_team.rest_days <= 2:
            factors.append("홈팀 피로 우려 (휴식일 부족)")
        if match.away_team.rest_days <= 2:
            factors.append("원정팀 피로 우려 (휴식일 부족)")

        # 7. 경기 중요도
        if match.match_importance == "high":
            factors.append("고중요도 경기 (예측 변동성 높음)")
        elif match.match_importance == "critical":
            factors.append("결정적 경기 (양팀 모두 필승)")

        return factors[:5]  # 최대 5개

    def _create_feature_vector(self, match: MatchFeatures) -> Dict[str, float]:
        """정규화된 특징 벡터 생성"""

        vector = {
            # 팀 강도 (0~1)
            "home_strength": match.home_strength,
            "away_strength": match.away_strength,
            "strength_diff": match.home_strength - match.away_strength,
            # 폼 (0~1)
            "home_form": match.home_form_score,
            "away_form": match.away_form_score,
            "form_diff": match.home_form_score - match.away_form_score,
            # 상대 전적 (-1~1)
            "h2h_advantage": match.h2h_advantage,
            # 홈 어드밴티지
            "home_advantage_factor": 0.1,  # 기본 홈 어드밴티지
            # 득점력
            "home_avg_scored": min(match.home_team.avg_goals_scored / 3, 1),
            "away_avg_scored": min(match.away_team.avg_goals_scored / 3, 1),
            "home_avg_conceded": min(match.home_team.avg_goals_conceded / 3, 1),
            "away_avg_conceded": min(match.away_team.avg_goals_conceded / 3, 1),
            # 순위 (정규화)
            "home_rank_score": max(0, 1 - (match.home_team.league_rank - 1) / 19),
            "away_rank_score": max(0, 1 - (match.away_team.league_rank - 1) / 19),
            # 피로도 (낮을수록 피로)
            "home_rest_factor": min(match.home_team.rest_days / 7, 1),
            "away_rest_factor": min(match.away_team.rest_days / 7, 1),
            # 부상자 영향 (높을수록 부정적)
            "home_injury_impact": min(match.home_team.injury_count / 5, 1),
            "away_injury_impact": min(match.away_team.injury_count / 5, 1),
        }

        return {k: round(v, 4) for k, v in vector.items()}

    def batch_extract(self, matches_data: List[Dict]) -> List[MatchFeatures]:
        """여러 경기 일괄 처리"""
        return [self.extract_features(m) for m in matches_data]

    def to_ai_prompt_context(self, features: MatchFeatures) -> str:
        """AI 프롬프트용 컨텍스트 문자열 생성"""

        context = f"""## 경기 정보
- 홈팀: {features.home_team.team_name}
- 원정팀: {features.away_team.team_name}
- 리그: {features.league_name}

## 홈팀 ({features.home_team.team_name}) 데이터
- 시즌 전적: {features.home_team.season_wins}승 {features.home_team.season_draws}무 {features.home_team.season_losses}패
- 리그 순위: {features.home_team.league_rank}위
- 최근 5경기 폼: {features.home_team.recent_form}
- 평균 득점/실점: {features.home_team.avg_goals_scored:.1f} / {features.home_team.avg_goals_conceded:.1f}
- 홈 전적: {features.home_team.home_wins}승 {features.home_team.home_draws}무 {features.home_team.home_losses}패
- 팀 강도 지수: {features.home_strength:.2f}

## 원정팀 ({features.away_team.team_name}) 데이터
- 시즌 전적: {features.away_team.season_wins}승 {features.away_team.season_draws}무 {features.away_team.season_losses}패
- 리그 순위: {features.away_team.league_rank}위
- 최근 5경기 폼: {features.away_team.recent_form}
- 평균 득점/실점: {features.away_team.avg_goals_scored:.1f} / {features.away_team.avg_goals_conceded:.1f}
- 원정 전적: {features.away_team.away_wins}승 {features.away_team.away_draws}무 {features.away_team.away_losses}패
- 팀 강도 지수: {features.away_strength:.2f}

## 상대 전적
- 홈팀 승리: {features.h2h_home_wins}회
- 무승부: {features.h2h_draws}회
- 원정팀 승리: {features.h2h_away_wins}회
- 상대 전적 어드밴티지: {"홈팀 유리" if features.h2h_advantage > 0.1 else "원정팀 유리" if features.h2h_advantage < -0.1 else "균형"}

## 주요 분석 포인트
"""
        for factor in features.key_factors:
            context += f"- {factor}\n"

        if features.home_news_summary:
            context += f"\n## 홈팀 최근 뉴스\n{features.home_news_summary}\n"

        if features.away_news_summary:
            context += f"\n## 원정팀 최근 뉴스\n{features.away_news_summary}\n"

        return context
