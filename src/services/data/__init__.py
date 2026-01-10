"""
실시간 데이터 통합 서비스 모듈

이 패키지는 실시간 스포츠 데이터 수집, 캐싱, 통합을 담당합니다.
- 캐시 관리: CacheManager
- API Rate Limiting: RateLimiter
- 팀명 매핑: TeamMapper, SOCCER_TEAM_MAPPING, BASKETBALL_TEAM_MAPPING
- 팀 통계 수집: TeamStatsCollector, TeamStats
- 상대 전적: H2HCollector, HeadToHead, H2HMatch
- 최근 폼 수집: FormCollector, TeamForm, RecentMatch
- 부상자 정보: InjuriesCollector, TeamInjuries, PlayerInjury
- 배당률 수집: OddsCollector, MatchOdds, OddsSnapshot, OddsMovement
- 경기 데이터 통합: MatchEnricher, EnrichedMatchContext
- 이변 감지: EnhancedUpsetDetector, UpsetAnalysis, UpsetSignal (v4.0.0)
"""

from .cache_manager import (
    CacheManager,
    CacheTTL,
    cache_get,
    cache_invalidate,
    cache_set,
    get_cache_manager,
)

from .rate_limiter import (
    RateLimiter,
    RATE_LIMITERS,
    rate_limited,
    rate_limited_sync,
    get_rate_limiter,
    register_rate_limiter,
    get_all_stats,
    reset_all_limiters,
    get_critical_limiters,
    wait_for_all_limiters,
)

from .team_mapping import (
    SOCCER_TEAM_MAPPING,
    BASKETBALL_TEAM_MAPPING,
    TeamMapper,
    team_mapper,
)

from .team_stats_collector import (
    TeamStats,
    TeamStatsCollector,
    team_stats_collector,
    get_team_stats,
)

from .h2h_collector import (
    H2HMatch,
    HeadToHead,
    H2HCollector,
    h2h_collector,
    get_h2h_collector,
)

from .form_collector import (
    RecentMatch,
    TeamForm,
    FormCollector,
    get_form_collector,
)

from .injuries_collector import (
    PlayerInjury,
    TeamInjuries,
    InjuriesCollector,
    get_injuries_collector,
)

from .odds_collector import (
    OddsSnapshot,
    OddsMovement,
    MatchOdds,
    OddsCollector,
    get_odds_collector,
    odds_collector,
)

from .match_enricher import (
    EnrichedMatchContext,
    MatchEnricher,
    get_match_enricher,
)

from .enhanced_upset_detector import (
    EnhancedUpsetDetector,
    UpsetAnalysis,
    UpsetSignal,
    UpsetSignalWeights,
    get_upset_detector,
)

__all__ = [
    # Cache Manager
    "CacheManager",
    "CacheTTL",
    "get_cache_manager",
    "cache_get",
    "cache_set",
    "cache_invalidate",
    # Rate Limiter
    "RateLimiter",
    "RATE_LIMITERS",
    "rate_limited",
    "rate_limited_sync",
    "get_rate_limiter",
    "register_rate_limiter",
    "get_all_stats",
    "reset_all_limiters",
    "get_critical_limiters",
    "wait_for_all_limiters",
    # Team Mapping
    "SOCCER_TEAM_MAPPING",
    "BASKETBALL_TEAM_MAPPING",
    "TeamMapper",
    "team_mapper",
    # Team Stats Collector
    "TeamStats",
    "TeamStatsCollector",
    "team_stats_collector",
    "get_team_stats",
    # H2H Collector
    "H2HMatch",
    "HeadToHead",
    "H2HCollector",
    "h2h_collector",
    "get_h2h_collector",
    # Form Collector
    "RecentMatch",
    "TeamForm",
    "FormCollector",
    "get_form_collector",
    # Injuries Collector
    "PlayerInjury",
    "TeamInjuries",
    "InjuriesCollector",
    "get_injuries_collector",
    # Match Enricher
    "EnrichedMatchContext",
    "MatchEnricher",
    "get_match_enricher",
    # Upset Detector (v4.0.0)
    "EnhancedUpsetDetector",
    "UpsetAnalysis",
    "UpsetSignal",
    "UpsetSignalWeights",
    "get_upset_detector",
]
