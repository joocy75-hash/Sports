"""
부상자 정보 수집 모듈 (Phase 1.4)

외부 API에서 팀별 부상자, 출장정지, 의심 선수 정보를 수집합니다.
- API-Football injuries endpoint 사용
- 주요 선수 부재 여부 자동 판별
- 포지션별 결장 분석

캐시 TTL: 2시간 (CacheTTL.INJURIES)

사용 예시:
    from src.services.data.injuries_collector import injuries_collector

    # 팀 부상자 정보 조회 (축구)
    injuries = await injuries_collector.get_team_injuries("맨시티", league="Premier League")

    # 결과 확인
    print(f"총 결장: {injuries.total_unavailable}명")
    print(f"주요 선수 결장: {injuries.key_players_out}명")
    for player in injuries.injuries:
        print(f"  - {player.player_name} ({player.position}): {player.injury_type}")
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from src.services.data.cache_manager import CacheManager, CacheTTL, get_cache_manager
from src.services.data.rate_limiter import rate_limited, get_rate_limiter, RATE_LIMITERS
from src.services.data.team_mapping import TeamMapper, team_mapper

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class PlayerInjury:
    """선수 부상/결장 정보

    Attributes:
        player_name: 선수명
        team: 팀명
        position: 포지션 ('GK', 'DF', 'MF', 'FW', 'Unknown')
        status: 상태 ('injured', 'suspended', 'doubtful')
        injury_type: 부상 유형 (예: 'Hamstring', 'Knee Injury', 'Muscle Injury')
        expected_return: 예상 복귀일 (예: '2026-01-20' 또는 'Unknown')
        is_key_player: 주요 선수 여부 (출장 수 기준)
        season_appearances: 시즌 출장 수
        season_goals: 시즌 골 수
        season_assists: 시즌 어시스트 수
    """
    player_name: str
    team: str
    position: str = "Unknown"  # 'GK', 'DF', 'MF', 'FW', 'Unknown'
    status: str = "injured"  # 'injured', 'suspended', 'doubtful'
    injury_type: Optional[str] = None  # 'Hamstring', 'Knee', etc.
    expected_return: Optional[str] = None
    is_key_player: bool = False
    season_appearances: int = 0
    season_goals: int = 0
    season_assists: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "player_name": self.player_name,
            "team": self.team,
            "position": self.position,
            "status": self.status,
            "injury_type": self.injury_type,
            "expected_return": self.expected_return,
            "is_key_player": self.is_key_player,
            "season_appearances": self.season_appearances,
            "season_goals": self.season_goals,
            "season_assists": self.season_assists,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerInjury":
        """딕셔너리에서 객체 생성"""
        return cls(
            player_name=data.get("player_name", ""),
            team=data.get("team", ""),
            position=data.get("position", "Unknown"),
            status=data.get("status", "injured"),
            injury_type=data.get("injury_type"),
            expected_return=data.get("expected_return"),
            is_key_player=data.get("is_key_player", False),
            season_appearances=data.get("season_appearances", 0),
            season_goals=data.get("season_goals", 0),
            season_assists=data.get("season_assists", 0),
        )

    def get_severity_score(self) -> int:
        """결장 심각도 점수 반환 (0-100)

        주요 선수, 포지션, 부상 유형 등을 고려하여 점수 산정
        """
        score = 0

        # 주요 선수 여부 (최대 40점)
        if self.is_key_player:
            score += 40

        # 포지션별 중요도 (최대 20점)
        position_scores = {
            "GK": 20,  # 골키퍼는 교체가 어려움
            "FW": 15,  # 공격수는 득점에 직결
            "MF": 12,  # 미드필더는 경기 조율
            "DF": 10,  # 수비수
            "Unknown": 5,
        }
        score += position_scores.get(self.position, 5)

        # 상태별 심각도 (최대 20점)
        status_scores = {
            "injured": 20,
            "suspended": 18,
            "doubtful": 10,
        }
        score += status_scores.get(self.status, 10)

        # 시즌 기여도 (골+어시 기반, 최대 20점)
        contributions = self.season_goals + self.season_assists
        score += min(contributions * 2, 20)

        return min(score, 100)


@dataclass
class TeamInjuries:
    """팀 부상자 정보 종합

    Attributes:
        team_name: 팀명 (정규화됨)
        injuries: 부상 선수 리스트
        suspensions: 출장정지 선수 리스트
        doubts: 출전 의심 선수 리스트
        total_unavailable: 총 결장 선수 수
        key_players_out: 주요 선수 결장 수
        updated_at: 데이터 갱신 시간
    """
    team_name: str
    injuries: List[PlayerInjury] = field(default_factory=list)
    suspensions: List[PlayerInjury] = field(default_factory=list)
    doubts: List[PlayerInjury] = field(default_factory=list)
    total_unavailable: int = 0
    key_players_out: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """초기화 후 처리 - 통계 계산"""
        self._recalculate_stats()

    def _recalculate_stats(self) -> None:
        """통계 재계산"""
        all_players = self.injuries + self.suspensions + self.doubts
        self.total_unavailable = len(all_players)
        self.key_players_out = sum(1 for p in all_players if p.is_key_player)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "team_name": self.team_name,
            "injuries": [p.to_dict() for p in self.injuries],
            "suspensions": [p.to_dict() for p in self.suspensions],
            "doubts": [p.to_dict() for p in self.doubts],
            "total_unavailable": self.total_unavailable,
            "key_players_out": self.key_players_out,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamInjuries":
        """딕셔너리에서 객체 생성"""
        updated_at_str = data.get("updated_at", "")
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
            except ValueError:
                updated_at = datetime.now(timezone.utc)
        else:
            updated_at = datetime.now(timezone.utc)

        injuries = [
            PlayerInjury.from_dict(p)
            for p in data.get("injuries", [])
        ]
        suspensions = [
            PlayerInjury.from_dict(p)
            for p in data.get("suspensions", [])
        ]
        doubts = [
            PlayerInjury.from_dict(p)
            for p in data.get("doubts", [])
        ]

        return cls(
            team_name=data.get("team_name", ""),
            injuries=injuries,
            suspensions=suspensions,
            doubts=doubts,
            total_unavailable=data.get("total_unavailable", 0),
            key_players_out=data.get("key_players_out", 0),
            updated_at=updated_at,
        )

    def get_by_position(self, position: str) -> List[PlayerInjury]:
        """포지션별 결장 선수 조회

        Args:
            position: 포지션 ('GK', 'DF', 'MF', 'FW')

        Returns:
            해당 포지션의 결장 선수 리스트
        """
        all_players = self.injuries + self.suspensions + self.doubts
        return [p for p in all_players if p.position == position]

    def get_position_summary(self) -> Dict[str, int]:
        """포지션별 결장 선수 수 요약

        Returns:
            {position: count} 딕셔너리
        """
        summary = {"GK": 0, "DF": 0, "MF": 0, "FW": 0, "Unknown": 0}
        all_players = self.injuries + self.suspensions + self.doubts

        for player in all_players:
            if player.position in summary:
                summary[player.position] += 1
            else:
                summary["Unknown"] += 1

        return summary

    def get_impact_score(self) -> int:
        """팀 전력 손실 영향도 점수 (0-100)

        모든 결장 선수의 심각도 점수를 종합하여 팀 영향도 산출
        """
        all_players = self.injuries + self.suspensions + self.doubts

        if not all_players:
            return 0

        # 개별 선수 영향도 합산 (최대 100점 제한)
        total_score = sum(p.get_severity_score() for p in all_players)

        # 정규화: 결장 선수 수에 따른 추가 패널티
        # 3명 이상 결장 시 추가 영향
        if len(all_players) >= 5:
            total_score = min(total_score, 100)
        elif len(all_players) >= 3:
            total_score = min(total_score * 0.8, 85)
        else:
            total_score = min(total_score * 0.6, 70)

        return int(min(total_score, 100))

    def get_all_unavailable(self) -> List[PlayerInjury]:
        """모든 결장 선수 리스트 반환"""
        return self.injuries + self.suspensions + self.doubts


# =============================================================================
# InjuriesCollector 클래스
# =============================================================================

class InjuriesCollector:
    """부상자 정보 수집기

    API-Football의 injuries 엔드포인트를 사용하여
    팀별 부상자, 출장정지, 의심 선수 정보를 수집합니다.

    사용 예시:
        collector = InjuriesCollector()

        # 팀 부상자 조회
        injuries = await collector.get_team_injuries("맨시티", league="Premier League")

        if injuries:
            print(f"총 결장: {injuries.total_unavailable}명")
            for player in injuries.injuries:
                print(f"  - {player.player_name}: {player.injury_type}")
    """

    # API-Football 설정
    API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"

    # 리그 ID 매핑 (API-Football)
    API_FOOTBALL_LEAGUE_IDS = {
        "Premier League": 39,
        "Serie A": 135,
        "Bundesliga": 78,
        "La Liga": 140,
        "Ligue 1": 61,
        "Championship": 40,
        "Eredivisie": 88,
        "Primeira Liga": 94,
    }

    # 주요 선수 판별 기준 (시즌 출장 수)
    KEY_PLAYER_APPEARANCES_THRESHOLD = 10

    def __init__(self):
        """InjuriesCollector 초기화"""
        self.team_mapper: TeamMapper = team_mapper
        self.cache_manager: CacheManager = get_cache_manager()

        # API 키 로드
        self.api_football_key: Optional[str] = os.getenv("API_FOOTBALL_KEY")

        # 세션은 lazy 초기화
        self._session: Optional[aiohttp.ClientSession] = None

        # API 사용 가능 여부 확인
        self._api_football_available = bool(self.api_football_key)

        logger.info(
            f"InjuriesCollector 초기화: "
            f"api_football={'활성' if self._api_football_available else '비활성'}"
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp 세션 가져오기 (lazy 초기화)"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """리소스 정리"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_cache_key(self, team_name: str, league: Optional[str] = None) -> str:
        """캐시 키 생성

        Args:
            team_name: 팀명
            league: 리그명 (옵션)

        Returns:
            캐시 키 문자열
        """
        league_part = league.replace(" ", "_").lower() if league else "unknown"
        team_part = team_name.replace(" ", "_").lower()
        return f"injuries:{league_part}:{team_part}"

    def _get_current_season(self) -> int:
        """현재 시즌 연도 반환

        축구 시즌은 보통 8월에 시작하므로,
        8월 이후면 현재 연도, 이전이면 작년 연도 반환
        """
        now = datetime.now()
        return now.year if now.month >= 8 else now.year - 1

    async def get_team_injuries(
        self,
        team_name: str,
        league: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[TeamInjuries]:
        """팀 부상자 정보 조회

        캐시에서 먼저 조회하고, 없으면 API에서 수집합니다.

        Args:
            team_name: 팀명 (한글 또는 영문)
            league: 리그명 (예: "Premier League")
            force_refresh: 캐시 무시 여부

        Returns:
            TeamInjuries 객체 또는 None (API 키 없거나 실패 시)
        """
        # API 키 확인
        if not self._api_football_available:
            logger.warning("부상자 정보 수집 불가: API_FOOTBALL_KEY가 설정되지 않음")
            return None

        # 팀명 정규화
        normalized_name = self.team_mapper.get_normalized_name(team_name, sport="soccer")
        if not normalized_name:
            logger.warning(f"팀명 매칭 실패: {team_name}")
            normalized_name = team_name  # 원본 사용

        # 캐시 확인
        cache_key = self._get_cache_key(normalized_name, league)
        if not force_refresh:
            cached_data = await self.cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"캐시에서 부상자 정보 로드: {normalized_name}")
                return TeamInjuries.from_dict(cached_data)

        # API에서 데이터 조회
        team_injuries = await self._fetch_team_injuries(normalized_name, league)

        # 캐시 저장
        if team_injuries:
            await self.cache_manager.set(
                cache_key,
                team_injuries.to_dict(),
                CacheTTL.INJURIES  # 2시간
            )
            logger.info(f"부상자 정보 수집 완료: {normalized_name} ({team_injuries.total_unavailable}명)")

        return team_injuries

    async def _fetch_team_injuries(
        self,
        team_name: str,
        league: Optional[str]
    ) -> Optional[TeamInjuries]:
        """API에서 팀 부상자 데이터 조회

        Args:
            team_name: 정규화된 팀명
            league: 리그명

        Returns:
            TeamInjuries 또는 None
        """
        # 팀 ID 조회
        team_id = self.team_mapper.get_api_id(team_name, api="api_football", sport="soccer")
        if not team_id:
            logger.warning(f"API-Football 팀 ID 없음: {team_name}")
            return self._create_empty_injuries(team_name)

        try:
            injuries_data = await self._fetch_from_api_football(team_id)
            if injuries_data:
                return self._parse_api_football_injuries(injuries_data, team_name)
            else:
                return self._create_empty_injuries(team_name)
        except Exception as e:
            logger.error(f"API-Football 부상자 조회 실패: {team_name}, {e}")
            return self._create_empty_injuries(team_name)

    @rate_limited("api_football", timeout=30.0)
    async def _fetch_from_api_football(
        self,
        team_id: int
    ) -> Optional[List[Dict[str, Any]]]:
        """API-Football에서 부상자 데이터 조회

        API 문서: https://www.api-football.com/documentation-v3#tag/Injuries

        Args:
            team_id: API-Football 팀 ID

        Returns:
            부상자 데이터 리스트 또는 None
        """
        if not self.api_football_key:
            logger.warning("API_FOOTBALL_KEY가 설정되지 않음")
            return None

        session = await self._get_session()

        # 현재 시즌 연도
        season_year = self._get_current_season()

        headers = {
            "x-apisports-key": self.api_football_key,
        }

        # 부상자 정보 조회 (injuries 엔드포인트)
        url = f"{self.API_FOOTBALL_BASE_URL}/injuries"
        params = {
            "team": team_id,
            "season": season_year,
        }

        try:
            async with session.get(url, headers=headers, params=params, timeout=20) as response:
                if response.status == 429:
                    logger.warning("API-Football rate limit 도달")
                    return None

                if response.status != 200:
                    logger.error(f"API-Football 응답 오류: {response.status}")
                    text = await response.text()
                    logger.debug(f"응답 내용: {text[:500]}")
                    return None

                data = await response.json()
                injuries = data.get("response", [])

                logger.debug(f"API-Football: team_id={team_id} - {len(injuries)}건 조회")
                return injuries

        except asyncio.TimeoutError:
            logger.error(f"API-Football 타임아웃: team_id={team_id}")
            return None
        except Exception as e:
            logger.error(f"API-Football 오류: team_id={team_id}, {e}")
            return None

    def _parse_api_football_injuries(
        self,
        data: List[Dict[str, Any]],
        team_name: str
    ) -> TeamInjuries:
        """API-Football 부상자 응답 파싱

        API 응답 구조:
        {
            "response": [
                {
                    "player": {"id": 123, "name": "Player Name", "photo": "..."},
                    "team": {"id": 456, "name": "Team Name"},
                    "fixture": {"id": 789, "date": "2025-01-10T15:00:00+00:00"},
                    "league": {...},
                    "type": "Missing Fixture",
                    "reason": "Injury - Hamstring"
                }
            ]
        }

        Args:
            data: API 응답 데이터 리스트
            team_name: 팀명

        Returns:
            TeamInjuries 객체
        """
        injuries_list: List[PlayerInjury] = []
        suspensions_list: List[PlayerInjury] = []
        doubts_list: List[PlayerInjury] = []

        # 선수별 그룹화 (중복 제거)
        player_map: Dict[str, Dict[str, Any]] = {}

        for item in data:
            try:
                player_info = item.get("player", {})
                player_name = player_info.get("name", "Unknown")
                player_id = str(player_info.get("id", ""))

                # 이미 처리한 선수면 스킵 (가장 최근 정보만 사용)
                if player_id in player_map:
                    continue

                reason = item.get("reason", "")
                injury_type = item.get("type", "")

                # 상태 및 부상 유형 파싱
                status, parsed_injury_type = self._parse_injury_reason(reason, injury_type)

                # 포지션 추출 (API-Football injuries에는 포지션 없음, 별도 조회 필요)
                # 현재는 Unknown으로 설정
                position = "Unknown"

                player_injury = PlayerInjury(
                    player_name=player_name,
                    team=team_name,
                    position=position,
                    status=status,
                    injury_type=parsed_injury_type,
                    expected_return=None,  # API에서 제공 안함
                    is_key_player=False,  # 별도 판별 필요
                    season_appearances=0,
                    season_goals=0,
                    season_assists=0,
                )

                player_map[player_id] = {
                    "injury": player_injury,
                    "status": status,
                }

            except Exception as e:
                logger.warning(f"부상자 데이터 파싱 오류: {e}")
                continue

        # 상태별 분류
        for player_data in player_map.values():
            injury = player_data["injury"]
            status = player_data["status"]

            if status == "injured":
                injuries_list.append(injury)
            elif status == "suspended":
                suspensions_list.append(injury)
            elif status == "doubtful":
                doubts_list.append(injury)
            else:
                injuries_list.append(injury)  # 기본값

        return TeamInjuries(
            team_name=team_name,
            injuries=injuries_list,
            suspensions=suspensions_list,
            doubts=doubts_list,
            updated_at=datetime.now(timezone.utc),
        )

    def _parse_injury_reason(
        self,
        reason: str,
        injury_type: str
    ) -> tuple:
        """부상 사유 파싱

        Args:
            reason: 부상 사유 문자열 (예: "Injury - Hamstring", "Red Card")
            injury_type: 부상 유형 (예: "Missing Fixture")

        Returns:
            (status, injury_type_parsed) 튜플
        """
        reason_lower = reason.lower()
        status = "injured"  # 기본값
        injury_type_parsed = None

        # 출장정지 판별
        if any(keyword in reason_lower for keyword in ["red card", "suspension", "suspended", "yellow cards"]):
            status = "suspended"
            injury_type_parsed = "Suspension"

        # 의심 판별
        elif any(keyword in reason_lower for keyword in ["doubtful", "knock", "minor", "slight"]):
            status = "doubtful"
            # 부상 유형 추출
            if " - " in reason:
                injury_type_parsed = reason.split(" - ", 1)[1].strip()
            else:
                injury_type_parsed = reason

        # 부상 판별
        elif "injury" in reason_lower or "-" in reason:
            status = "injured"
            # 부상 유형 추출
            if " - " in reason:
                injury_type_parsed = reason.split(" - ", 1)[1].strip()
            else:
                injury_type_parsed = reason

        # 기타 사유
        else:
            status = "injured"
            injury_type_parsed = reason if reason else "Unknown"

        return status, injury_type_parsed

    def _create_empty_injuries(self, team_name: str) -> TeamInjuries:
        """빈 부상자 정보 생성

        Args:
            team_name: 팀명

        Returns:
            빈 TeamInjuries 객체
        """
        return TeamInjuries(
            team_name=team_name,
            injuries=[],
            suspensions=[],
            doubts=[],
            updated_at=datetime.now(timezone.utc),
        )

    async def get_multiple_team_injuries(
        self,
        team_names: List[str],
        league: Optional[str] = None
    ) -> Dict[str, Optional[TeamInjuries]]:
        """여러 팀의 부상자 정보 일괄 조회

        Args:
            team_names: 팀명 리스트
            league: 리그명

        Returns:
            {팀명: TeamInjuries} 딕셔너리
        """
        tasks = [
            self.get_team_injuries(team_name, league)
            for team_name in team_names
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        injuries_dict = {}
        for team_name, result in zip(team_names, results):
            if isinstance(result, Exception):
                logger.error(f"부상자 조회 실패: {team_name}, {result}")
                injuries_dict[team_name] = None
            else:
                injuries_dict[team_name] = result

        return injuries_dict

    async def compare_team_injuries(
        self,
        home_team: str,
        away_team: str,
        league: Optional[str] = None
    ) -> Dict[str, Any]:
        """두 팀의 부상자 상황 비교

        Args:
            home_team: 홈팀명
            away_team: 원정팀명
            league: 리그명

        Returns:
            비교 결과 딕셔너리
        """
        home_injuries = await self.get_team_injuries(home_team, league)
        away_injuries = await self.get_team_injuries(away_team, league)

        home_impact = home_injuries.get_impact_score() if home_injuries else 0
        away_impact = away_injuries.get_impact_score() if away_injuries else 0

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_injuries": home_injuries,
            "away_injuries": away_injuries,
            "home_impact_score": home_impact,
            "away_impact_score": away_impact,
            "advantage": "home" if away_impact > home_impact else ("away" if home_impact > away_impact else "even"),
            "impact_difference": abs(home_impact - away_impact),
        }


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_injuries_collector_instance: Optional[InjuriesCollector] = None


def get_injuries_collector() -> InjuriesCollector:
    """InjuriesCollector 싱글톤 인스턴스 반환"""
    global _injuries_collector_instance

    if _injuries_collector_instance is None:
        _injuries_collector_instance = InjuriesCollector()

    return _injuries_collector_instance


# 편의를 위한 전역 인스턴스 (lazy 초기화)
injuries_collector = None


def _init_injuries_collector() -> InjuriesCollector:
    """지연 초기화된 injuries_collector 반환"""
    global injuries_collector
    if injuries_collector is None:
        injuries_collector = get_injuries_collector()
    return injuries_collector


# =============================================================================
# 테스트 함수
# =============================================================================

async def test_injuries_collector():
    """InjuriesCollector 테스트"""
    print("=" * 70)
    print("InjuriesCollector 테스트")
    print("=" * 70)

    collector = InjuriesCollector()

    # 환경 확인
    print("\n[1] 환경 확인")
    print("-" * 50)
    print(f"  API-Football: {'활성' if collector._api_football_available else '비활성'}")

    if not collector._api_football_available:
        print("\n  API 키가 설정되지 않아 테스트를 건너뜁니다.")
        print("  .env 파일에 API_FOOTBALL_KEY를 설정하세요.")
        await collector.close()
        return

    # 팀 부상자 조회 테스트
    print("\n[2] 팀 부상자 조회 테스트")
    print("-" * 50)

    test_teams = [
        ("맨시티", "Premier League"),
        ("리버풀", "Premier League"),
        ("아스널", "Premier League"),
    ]

    for team_name, league in test_teams:
        print(f"\n  {team_name} ({league}):")
        try:
            injuries = await collector.get_team_injuries(team_name, league)
            if injuries:
                print(f"    총 결장: {injuries.total_unavailable}명")
                print(f"    주요 선수 결장: {injuries.key_players_out}명")
                print(f"    팀 영향도 점수: {injuries.get_impact_score()}/100")

                # 포지션별 요약
                position_summary = injuries.get_position_summary()
                print(f"    포지션별: GK={position_summary['GK']}, DF={position_summary['DF']}, "
                      f"MF={position_summary['MF']}, FW={position_summary['FW']}")

                # 부상자 목록 (최대 3명)
                if injuries.injuries:
                    print("    부상자:")
                    for i, player in enumerate(injuries.injuries[:3], 1):
                        print(f"      {i}. {player.player_name} ({player.position}): {player.injury_type}")
                    if len(injuries.injuries) > 3:
                        print(f"      ... 외 {len(injuries.injuries) - 3}명")

                # 출장정지
                if injuries.suspensions:
                    print("    출장정지:")
                    for player in injuries.suspensions[:2]:
                        print(f"      - {player.player_name}")

                # 출전 의심
                if injuries.doubts:
                    print("    출전 의심:")
                    for player in injuries.doubts[:2]:
                        print(f"      - {player.player_name}")

            else:
                print("    데이터 조회 실패")

        except Exception as e:
            print(f"    오류: {e}")

    # 두 팀 비교 테스트
    print("\n[3] 두 팀 부상 상황 비교")
    print("-" * 50)

    try:
        comparison = await collector.compare_team_injuries("맨시티", "리버풀", "Premier League")
        print(f"  홈팀 ({comparison['home_team']}): 영향도 {comparison['home_impact_score']}/100")
        print(f"  원정팀 ({comparison['away_team']}): 영향도 {comparison['away_impact_score']}/100")
        print(f"  유리한 팀: {comparison['advantage']}")
        print(f"  영향도 차이: {comparison['impact_difference']}점")
    except Exception as e:
        print(f"  비교 실패: {e}")

    # 리소스 정리
    await collector.close()

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)


if __name__ == "__main__":
    # dotenv 로드
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    asyncio.run(test_injuries_collector())
