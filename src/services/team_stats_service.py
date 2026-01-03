"""
Team Statistics Service

팀 통계를 수집하고 캐싱하는 중앙 서비스

아키텍처:
1. 메모리 캐시 (딕셔너리, TTL 1일)
2. 파일 캐시 (.state/team_stats/)
3. API 호출 (API-Football, BallDontLie)
4. 기본값 폴백

캐시 적중률 목표: 80%+
API 호출 제한:
- API-Football: 100 req/day (축구)
- BallDontLie: 60 req/min (농구, unlimited daily)
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta

from .stats_providers.base_provider import BaseStatsProvider, TeamStats
from .stats_providers.api_football_provider import APIFootballProvider
from .stats_providers.balldontlie_provider import BallDontLieProvider

logger = logging.getLogger(__name__)


class TeamStatsService:
    """
    팀 통계 서비스 (3-tier 캐싱 + Multi-provider fallback)

    캐시 구조:
    - Tier 1: 메모리 캐시 (빠름, 휘발성)
    - Tier 2: 파일 캐시 (영구, .state/team_stats/)
    - Tier 3: API 호출 (느림, 비용 발생)
    - Fallback: 기본값

    TTL: 1일 (24시간)
    """

    def __init__(
        self,
        api_football_key: Optional[str] = None,
        balldontlie_key: Optional[str] = None,
        cache_dir: Optional[str] = None,
        cache_ttl_hours: int = 24,
    ):
        """
        Args:
            api_football_key: API-Football.com API 키
            balldontlie_key: BallDontLie API 키
            cache_dir: 캐시 디렉토리 경로
            cache_ttl_hours: 캐시 유효 시간 (시간)
        """
        # Providers 초기화
        self.soccer_provider = APIFootballProvider(api_key=api_football_key)
        self.basketball_provider = BallDontLieProvider(api_key=balldontlie_key)

        # 캐시 설정
        self.cache_dir = Path(cache_dir or ".state/team_stats")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        # 메모리 캐시 (key: team_name|league|is_home, value: TeamStats)
        self._memory_cache: Dict[str, TeamStats] = {}

        # 통계 추적
        self.stats = {
            "memory_hits": 0,
            "file_hits": 0,
            "api_calls": 0,
            "fallback_uses": 0,
            "total_requests": 0,
        }

        logger.info(f"TeamStatsService initialized (cache_dir={self.cache_dir}, TTL={cache_ttl_hours}h)")

    def _get_cache_key(self, team_name: str, league: str, is_home: bool) -> str:
        """캐시 키 생성"""
        home_flag = "home" if is_home else "away"
        return f"{team_name}|{league}|{home_flag}"

    def _get_cache_file(self, team_name: str, league: str, is_home: bool) -> Path:
        """캐시 파일 경로 생성"""
        cache_key = self._get_cache_key(team_name, league, is_home)
        # 파일명에 사용할 수 없는 문자 제거
        safe_key = cache_key.replace("|", "_").replace(" ", "_")
        return self.cache_dir / f"{safe_key}.json"

    def _is_cache_valid(self, team_stats: TeamStats) -> bool:
        """캐시 유효성 검사 (TTL 기반)"""
        if not team_stats.last_updated:
            return False

        age = datetime.now() - team_stats.last_updated
        is_valid = age < self.cache_ttl

        if not is_valid:
            logger.debug(f"Cache expired: {team_stats.team_name} (age={age})")

        return is_valid

    async def get_team_stats(
        self,
        team_name: str,
        league: str,
        sport_type: str,  # "soccer" or "basketball"
        is_home: bool = True,
        force_refresh: bool = False,
    ) -> TeamStats:
        """
        팀 통계 가져오기 (3-tier 캐싱)

        Args:
            team_name: 팀 이름 (베트맨 형식)
            league: 리그 이름
            sport_type: "soccer" 또는 "basketball"
            is_home: 홈 경기 여부
            force_refresh: True면 캐시 무시하고 API 호출

        Returns:
            TeamStats (항상 반환, 실패 시 기본값)
        """
        self.stats["total_requests"] += 1
        cache_key = self._get_cache_key(team_name, league, is_home)

        # ===== Tier 1: 메모리 캐시 =====
        if not force_refresh and cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            if self._is_cache_valid(cached):
                self.stats["memory_hits"] += 1
                logger.debug(f"✅ Memory cache hit: {team_name}")
                return cached
            else:
                # 만료된 캐시 삭제
                del self._memory_cache[cache_key]

        # ===== Tier 2: 파일 캐시 =====
        if not force_refresh:
            file_cached = self._load_from_file(team_name, league, is_home)
            if file_cached and self._is_cache_valid(file_cached):
                self.stats["file_hits"] += 1
                logger.debug(f"✅ File cache hit: {team_name}")
                # 메모리 캐시에도 저장
                self._memory_cache[cache_key] = file_cached
                return file_cached

        # ===== Tier 3: API 호출 =====
        provider = self._get_provider(sport_type)
        team_stats = None

        if provider:
            try:
                team_stats = await provider.get_team_stats(team_name, league, is_home)
                if team_stats:
                    self.stats["api_calls"] += 1
                    logger.info(f"✅ API call success: {team_name} (provider={provider.provider_name})")

                    # 캐시에 저장
                    self._save_to_cache(team_stats, cache_key)
                    return team_stats
            except Exception as e:
                logger.error(f"API call failed for {team_name}: {e}")

        # ===== Fallback: 기본값 =====
        logger.warning(f"⚠️ Using default stats for {team_name}")
        self.stats["fallback_uses"] += 1

        default_stats = provider.get_default_stats(team_name, league, is_home) if provider else TeamStats(
            team_name=team_name,
            league=league,
            attack_rating=50.0,
            defense_rating=50.0,
            recent_form=50.0,
            win_rate=0.5,
            home_advantage=5.0 if is_home else 0.0,
            source="default"
        )

        # 기본값도 캐시 (단, TTL은 짧게)
        default_stats.last_updated = datetime.now() - timedelta(hours=23)  # 1시간 후 만료
        self._save_to_cache(default_stats, cache_key)

        return default_stats

    def _get_provider(self, sport_type: str) -> Optional[BaseStatsProvider]:
        """스포츠 타입에 따라 적절한 provider 반환"""
        if sport_type.lower() == "soccer":
            return self.soccer_provider
        elif sport_type.lower() == "basketball":
            return self.basketball_provider
        else:
            logger.error(f"Unknown sport type: {sport_type}")
            return None

    def _save_to_cache(self, team_stats: TeamStats, cache_key: str):
        """메모리 + 파일 캐시에 저장"""
        # 메모리 캐시
        self._memory_cache[cache_key] = team_stats

        # 파일 캐시
        team_name, league, is_home_str = cache_key.split("|")
        is_home = is_home_str == "home"
        cache_file = self._get_cache_file(team_name, league, is_home)

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(team_stats.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved to file cache: {cache_file}")
        except Exception as e:
            logger.error(f"Failed to save cache file: {e}")

    def _load_from_file(self, team_name: str, league: str, is_home: bool) -> Optional[TeamStats]:
        """파일 캐시에서 로드"""
        cache_file = self._get_cache_file(team_name, league, is_home)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                team_stats = TeamStats.from_dict(data)
                logger.debug(f"Loaded from file cache: {cache_file}")
                return team_stats
        except Exception as e:
            logger.error(f"Failed to load cache file {cache_file}: {e}")
            return None

    def get_cache_stats(self) -> Dict[str, any]:
        """캐시 통계 반환"""
        total = self.stats["total_requests"]
        if total == 0:
            hit_rate = 0.0
        else:
            cache_hits = self.stats["memory_hits"] + self.stats["file_hits"]
            hit_rate = cache_hits / total

        return {
            **self.stats,
            "cache_hit_rate": hit_rate,
            "cache_size": len(self._memory_cache),
        }

    def clear_cache(self, memory_only: bool = False):
        """캐시 삭제"""
        self._memory_cache.clear()
        logger.info("Memory cache cleared")

        if not memory_only:
            # 파일 캐시도 삭제
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                    logger.debug(f"Deleted cache file: {cache_file}")
                except Exception as e:
                    logger.error(f"Failed to delete {cache_file}: {e}")

            logger.info("File cache cleared")

    async def close(self):
        """리소스 정리"""
        if self.soccer_provider:
            await self.soccer_provider.close()
        if self.basketball_provider:
            await self.basketball_provider.close()

        logger.info("TeamStatsService closed")


# 싱글톤 인스턴스 (전역 사용)
_team_stats_service: Optional[TeamStatsService] = None


def get_team_stats_service(
    api_football_key: Optional[str] = None,
    balldontlie_key: Optional[str] = None,
) -> TeamStatsService:
    """
    TeamStatsService 싱글톤 인스턴스 가져오기

    Args:
        api_football_key: API-Football.com API 키 (.env에서 로드)
        balldontlie_key: BallDontLie API 키 (.env에서 로드)

    Returns:
        TeamStatsService 인스턴스
    """
    global _team_stats_service

    if _team_stats_service is None:
        # .env에서 API 키 로드
        if api_football_key is None:
            api_football_key = os.getenv("API_FOOTBALL_KEY")
        if balldontlie_key is None:
            balldontlie_key = os.getenv("BALLDONTLIE_KEY")

        _team_stats_service = TeamStatsService(
            api_football_key=api_football_key,
            balldontlie_key=balldontlie_key,
        )

    return _team_stats_service
