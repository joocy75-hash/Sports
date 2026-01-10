"""
배당률 수집 모듈 (Phase 1.5)

외부 API에서 실시간 배당률 데이터를 수집합니다.
- The Odds API (https://the-odds-api.com)

캐시 TTL: 5분 (CacheTTL.ODDS)

사용 예시:
    from src.services.data.odds_collector import odds_collector, get_odds_collector

    # 경기 배당률 조회
    odds = await odds_collector.get_match_odds(
        home_team="맨시티",
        away_team="리버풀",
        league="Premier League"
    )

    if odds:
        print(f"홈승: {odds.home_odds} ({odds.home_prob:.1%})")
        print(f"무승부: {odds.draw_odds} ({odds.draw_prob:.1%})")
        print(f"원정승: {odds.away_odds} ({odds.away_prob:.1%})")
        print(f"오버라운드: {odds.overround:.1%}")
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
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
class OddsSnapshot:
    """배당률 스냅샷

    특정 시점의 배당률 기록을 저장합니다.
    배당률 변동 추적에 사용됩니다.

    Attributes:
        timestamp: 기록 시간 (UTC)
        home_odds: 홈팀 승리 배당률
        draw_odds: 무승부 배당률
        away_odds: 원정팀 승리 배당률
    """
    timestamp: datetime
    home_odds: float
    draw_odds: float
    away_odds: float

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "home_odds": self.home_odds,
            "draw_odds": self.draw_odds,
            "away_odds": self.away_odds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OddsSnapshot":
        """딕셔너리에서 생성"""
        timestamp_str = data.get("timestamp", "")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        return cls(
            timestamp=timestamp,
            home_odds=float(data.get("home_odds", 0.0)),
            draw_odds=float(data.get("draw_odds", 0.0)),
            away_odds=float(data.get("away_odds", 0.0)),
        )

    def __eq__(self, other: object) -> bool:
        """동등성 비교 (배당률만 비교)"""
        if not isinstance(other, OddsSnapshot):
            return False
        return (
            abs(self.home_odds - other.home_odds) < 0.01 and
            abs(self.draw_odds - other.draw_odds) < 0.01 and
            abs(self.away_odds - other.away_odds) < 0.01
        )


@dataclass
class OddsMovement:
    """배당률 변동 분석

    현재 배당률과 이전 배당률을 비교하여 변동 방향과 의미를 분석합니다.

    Attributes:
        direction: 변동 방향 ('home_drift', 'away_drift', 'draw_drift', 'stable')
        magnitude: 변동 크기 (절대값 차이)
        significance: 중요도 ('high', 'medium', 'low')
        interpretation: 해석 메시지
    """
    direction: str  # 'home_drift', 'away_drift', 'draw_drift', 'stable'
    magnitude: float
    significance: str  # 'high', 'medium', 'low'
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "direction": self.direction,
            "magnitude": self.magnitude,
            "significance": self.significance,
            "interpretation": self.interpretation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OddsMovement":
        """딕셔너리에서 생성"""
        return cls(
            direction=data.get("direction", "stable"),
            magnitude=float(data.get("magnitude", 0.0)),
            significance=data.get("significance", "low"),
            interpretation=data.get("interpretation", ""),
        )


@dataclass
class MatchOdds:
    """경기 배당률 데이터

    특정 경기의 현재 배당률, 내재 확률, 변동 이력을 포함합니다.

    Attributes:
        match_id: 경기 고유 ID (API 제공)
        home_team: 홈팀명
        away_team: 원정팀명
        home_odds: 홈팀 승리 배당률
        draw_odds: 무승부 배당률
        away_odds: 원정팀 승리 배당률
        home_prob: 홈팀 승리 내재 확률 (0.0 ~ 1.0)
        draw_prob: 무승부 내재 확률 (0.0 ~ 1.0)
        away_prob: 원정팀 승리 내재 확률 (0.0 ~ 1.0)
        odds_history: 배당률 변동 이력
        bookmaker_odds: 각 북메이커별 배당률 정보
        overround: 북메이커 마진 (%) - 100% 초과분
        movement: 배당률 변동 분석 결과
        updated_at: 마지막 갱신 시간
    """
    match_id: str
    home_team: str
    away_team: str
    home_odds: float
    draw_odds: float
    away_odds: float
    home_prob: float  # implied probability
    draw_prob: float
    away_prob: float
    odds_history: List[OddsSnapshot] = field(default_factory=list)
    bookmaker_odds: Optional[Dict[str, Dict[str, float]]] = None
    overround: float = 0.0  # bookmaker margin %
    movement: Optional[OddsMovement] = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "match_id": self.match_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_odds": self.home_odds,
            "draw_odds": self.draw_odds,
            "away_odds": self.away_odds,
            "home_prob": self.home_prob,
            "draw_prob": self.draw_prob,
            "away_prob": self.away_prob,
            "odds_history": [s.to_dict() for s in self.odds_history],
            "bookmaker_odds": self.bookmaker_odds,
            "overround": self.overround,
            "movement": self.movement.to_dict() if self.movement else None,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatchOdds":
        """딕셔너리에서 생성"""
        updated_at_str = data.get("updated_at", "")
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
            except ValueError:
                updated_at = datetime.now(timezone.utc)
        else:
            updated_at = datetime.now(timezone.utc)

        movement_data = data.get("movement")
        movement = OddsMovement.from_dict(movement_data) if movement_data else None

        return cls(
            match_id=data.get("match_id", ""),
            home_team=data.get("home_team", ""),
            away_team=data.get("away_team", ""),
            home_odds=float(data.get("home_odds", 0.0)),
            draw_odds=float(data.get("draw_odds", 0.0)),
            away_odds=float(data.get("away_odds", 0.0)),
            home_prob=float(data.get("home_prob", 0.0)),
            draw_prob=float(data.get("draw_prob", 0.0)),
            away_prob=float(data.get("away_prob", 0.0)),
            odds_history=[
                OddsSnapshot.from_dict(s) for s in data.get("odds_history", [])
            ],
            bookmaker_odds=data.get("bookmaker_odds"),
            overround=float(data.get("overround", 0.0)),
            movement=movement,
            updated_at=updated_at,
        )

    def get_favorite(self) -> str:
        """우승 후보 반환 (가장 낮은 배당률)"""
        if self.home_odds < self.draw_odds and self.home_odds < self.away_odds:
            return "home"
        elif self.away_odds < self.draw_odds and self.away_odds < self.home_odds:
            return "away"
        else:
            return "draw"

    def get_value_bet(self, threshold: float = 0.05) -> Optional[str]:
        """가치 베팅 후보 반환

        내재 확률이 정규화된 확률보다 threshold 이상 높으면 가치 베팅

        Args:
            threshold: 최소 차이 (기본 5%)

        Returns:
            "home", "draw", "away" 또는 None
        """
        # 정규화된 확률과 비교
        if self.overround <= 0:
            return None

        # overround를 제거한 실제 예상 확률
        fair_home = self.home_prob / (1 + self.overround / 100)
        fair_draw = self.draw_prob / (1 + self.overround / 100)
        fair_away = self.away_prob / (1 + self.overround / 100)

        if self.home_prob - fair_home > threshold:
            return "home"
        elif self.draw_prob - fair_draw > threshold:
            return "draw"
        elif self.away_prob - fair_away > threshold:
            return "away"

        return None


# =============================================================================
# OddsCollector 클래스
# =============================================================================

class OddsCollector:
    """배당률 수집기

    The Odds API에서 실시간 배당률 데이터를 수집합니다.

    특징:
    - 유럽 지역 배당률 (EU regions)
    - 1x2 마켓 (h2h) 지원
    - 배당률 변동 추적
    - 내재 확률 계산

    사용 예시:
        collector = OddsCollector()

        # 경기 배당률 조회
        odds = await collector.get_match_odds(
            home_team="맨시티",
            away_team="리버풀",
            league="Premier League"
        )

        # 리그 전체 배당률 조회
        all_odds = await collector.get_league_odds("Premier League")
    """

    # The Odds API 설정
    ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"

    # 스포츠 키 매핑 (리그명 -> API sport_key)
    SPORT_KEYS = {
        # 축구
        "Premier League": "soccer_epl",
        "Serie A": "soccer_italy_serie_a",
        "Bundesliga": "soccer_germany_bundesliga",
        "La Liga": "soccer_spain_la_liga",
        "Ligue 1": "soccer_france_ligue_one",
        "Championship": "soccer_england_championship",
        "Eredivisie": "soccer_netherlands_eredivisie",
        "Primeira Liga": "soccer_portugal_primeira_liga",
        "K League": "soccer_korea_kleague1",
        "J1 League": "soccer_japan_j_league",
        # 농구
        "NBA": "basketball_nba",
        "EuroLeague": "basketball_euroleague",
        "KBL": None,  # The Odds API에서 미지원
    }

    # 주요 북메이커 (신뢰도 순)
    PREFERRED_BOOKMAKERS = [
        "pinnacle",      # 피나클 (기준선)
        "bet365",        # 벳365
        "williamhill",   # 윌리엄힐
        "unibet",        # 유니벳
        "betfair",       # 벳페어
        "1xbet",         # 원엑스벳
    ]

    def __init__(
        self,
        mapper: Optional[TeamMapper] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        """OddsCollector 초기화

        Args:
            mapper: 팀명 매퍼 (기본값: 전역 인스턴스)
            cache_manager: 캐시 매니저 (기본값: 전역 인스턴스)
        """
        self.team_mapper = mapper or team_mapper
        self.cache_manager = cache_manager or get_cache_manager()

        # API 키 로드
        self._api_key = os.getenv("ODDS_API_KEY")

        # aiohttp 세션 (lazy 초기화)
        self._session: Optional[aiohttp.ClientSession] = None

        # 배당률 이력 캐시 (메모리)
        self._odds_history_cache: Dict[str, List[OddsSnapshot]] = {}

        # 초기화 로그
        api_status = "활성" if self._api_key else "비활성 (ODDS_API_KEY 미설정)"
        logger.info(f"OddsCollector 초기화: {api_status}")

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
        logger.debug("OddsCollector 세션 종료")

    def _get_cache_key(
        self,
        home_team: str,
        away_team: str,
        league: str
    ) -> str:
        """캐시 키 생성

        Args:
            home_team: 홈팀명
            away_team: 원정팀명
            league: 리그명

        Returns:
            캐시 키 문자열
        """
        league_part = league.replace(" ", "_").lower()
        home_part = home_team.replace(" ", "_").lower()
        away_part = away_team.replace(" ", "_").lower()
        return f"odds:{league_part}:{home_part}_vs_{away_part}"

    async def get_match_odds(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[MatchOdds]:
        """경기 배당률 조회

        캐시에서 먼저 조회하고, 없으면 API에서 수집합니다.

        Args:
            home_team: 홈팀명 (한글 또는 영문)
            away_team: 원정팀명 (한글 또는 영문)
            league: 리그명 (예: "Premier League")
            match_date: 경기 날짜 (YYYY-MM-DD, 선택사항)
            force_refresh: 캐시 무시하고 강제 새로고침

        Returns:
            MatchOdds 객체 또는 None (수집 실패 시)
        """
        # API 키 확인
        if not self._api_key:
            logger.warning("배당률 수집 불가: ODDS_API_KEY 미설정")
            return None

        # sport_key 확인
        sport_key = self.SPORT_KEYS.get(league)
        if not sport_key:
            logger.warning(f"지원하지 않는 리그: {league}")
            return None

        # 캐시 키 생성
        cache_key = self._get_cache_key(home_team, away_team, league)

        # 1. 캐시 조회
        if not force_refresh:
            cached_data = await self.cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"캐시에서 배당률 로드: {home_team} vs {away_team}")
                odds = MatchOdds.from_dict(cached_data)

                # 이력에 현재 스냅샷이 없으면 추가
                self._update_odds_history(cache_key, odds)

                return odds

        # 2. API에서 수집
        try:
            # 리그 전체 배당률 조회
            all_odds = await self._fetch_from_odds_api(sport_key)

            if not all_odds:
                logger.warning(f"배당률 데이터 없음: {league}")
                return None

            # 경기 찾기
            match_data = self._find_match_odds(
                all_odds, home_team, away_team, match_date
            )

            if not match_data:
                logger.warning(f"경기 찾기 실패: {home_team} vs {away_team}")
                return None

            # MatchOdds 객체 생성
            odds = self._parse_match_odds(match_data, home_team, away_team)

            if odds:
                # 이력 업데이트
                self._update_odds_history(cache_key, odds)

                # 변동 분석
                history = self._odds_history_cache.get(cache_key, [])
                if len(history) > 1:
                    odds.movement = self._analyze_odds_movement(odds, history)

                # 캐시 저장
                await self.cache_manager.set(
                    cache_key,
                    odds.to_dict(),
                    CacheTTL.ODDS  # 5분
                )

                logger.info(f"배당률 수집 완료: {home_team} vs {away_team}")

            return odds

        except Exception as e:
            logger.error(f"배당률 수집 오류: {home_team} vs {away_team}, {e}")
            return None

    @rate_limited("odds_api", timeout=30.0)
    async def _fetch_from_odds_api(self, sport_key: str) -> List[Dict[str, Any]]:
        """The Odds API에서 배당률 조회

        API 문서: https://the-odds-api.com/liveapi/guides/v4/

        Args:
            sport_key: API 스포츠 키 (예: "soccer_epl")

        Returns:
            배당률 데이터 리스트
        """
        if not self._api_key:
            logger.warning("ODDS_API_KEY가 설정되지 않음")
            return []

        session = await self._get_session()

        url = f"{self.ODDS_API_BASE_URL}/sports/{sport_key}/odds"
        params = {
            "apiKey": self._api_key,
            "regions": "eu",  # 유럽 배당률
            "markets": "h2h",  # 1x2 마켓
            "oddsFormat": "decimal",  # 소수점 배당률
        }

        try:
            async with session.get(url, params=params, timeout=20) as response:
                if response.status == 401:
                    logger.error("The Odds API 인증 실패: 잘못된 API 키")
                    return []
                elif response.status == 422:
                    logger.warning(f"The Odds API: 지원하지 않는 스포츠 키: {sport_key}")
                    return []
                elif response.status == 429:
                    logger.warning("The Odds API rate limit 도달")
                    return []
                elif response.status != 200:
                    logger.error(f"The Odds API 응답 오류: {response.status}")
                    return []

                data = await response.json()

                # 남은 요청 수 확인 (헤더)
                remaining = response.headers.get("x-requests-remaining", "N/A")
                used = response.headers.get("x-requests-used", "N/A")
                logger.debug(f"The Odds API: 사용={used}, 남음={remaining}")

                return data

        except asyncio.TimeoutError:
            logger.error(f"The Odds API 타임아웃: {sport_key}")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"The Odds API 연결 오류: {e}")
            return []
        except Exception as e:
            logger.error(f"The Odds API 오류: {e}")
            return []

    def _find_match_odds(
        self,
        odds_list: List[Dict[str, Any]],
        home_team: str,
        away_team: str,
        match_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """경기 배당률 찾기

        팀명을 fuzzy matching으로 비교하여 해당 경기를 찾습니다.

        Args:
            odds_list: 전체 배당률 리스트
            home_team: 홈팀명
            away_team: 원정팀명
            match_date: 경기 날짜 (선택)

        Returns:
            매칭된 경기 데이터 또는 None
        """
        # 팀명 정규화
        norm_home = self.team_mapper.get_normalized_name(home_team, "soccer") or home_team
        norm_away = self.team_mapper.get_normalized_name(away_team, "soccer") or away_team

        best_match = None
        best_score = 0.0
        min_score_threshold = 0.5  # 최소 유사도

        for match in odds_list:
            api_home = match.get("home_team", "")
            api_away = match.get("away_team", "")

            # 유사도 계산
            home_score = self._calculate_similarity(norm_home, api_home)
            away_score = self._calculate_similarity(norm_away, api_away)

            # 영문 별칭으로도 시도
            if home_score < 0.6:
                eng_home = self._get_english_name(home_team)
                if eng_home:
                    home_score = max(home_score, self._calculate_similarity(eng_home, api_home))

            if away_score < 0.6:
                eng_away = self._get_english_name(away_team)
                if eng_away:
                    away_score = max(away_score, self._calculate_similarity(eng_away, api_away))

            # 양팀 모두 일정 유사도 이상이어야 함
            if home_score >= min_score_threshold and away_score >= min_score_threshold:
                combined_score = (home_score + away_score) / 2

                # 날짜 필터링 (제공된 경우)
                if match_date:
                    commence_time = match.get("commence_time", "")
                    if commence_time and match_date not in commence_time:
                        continue

                if combined_score > best_score:
                    best_score = combined_score
                    best_match = match

        if best_match:
            logger.debug(
                f"경기 매칭: {home_team} vs {away_team} -> "
                f"{best_match.get('home_team')} vs {best_match.get('away_team')} "
                f"(score: {best_score:.2f})"
            )

        return best_match

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """문자열 유사도 계산

        Args:
            str1: 비교 문자열 1
            str2: 비교 문자열 2

        Returns:
            유사도 (0.0 ~ 1.0)
        """
        # 소문자로 변환
        str1_lower = str1.lower().strip()
        str2_lower = str2.lower().strip()

        # 완전 일치
        if str1_lower == str2_lower:
            return 1.0

        # 부분 문자열 포함
        if str1_lower in str2_lower or str2_lower in str1_lower:
            return 0.8

        # SequenceMatcher 사용
        return SequenceMatcher(None, str1_lower, str2_lower).ratio()

    def _get_english_name(self, korean_name: str) -> Optional[str]:
        """한글 팀명에서 영문 별칭 조회

        Args:
            korean_name: 한글 팀명

        Returns:
            영문 팀명 또는 None
        """
        # team_mapping에서 별칭 조회
        from src.services.data.team_mapping import SOCCER_TEAM_MAPPING

        for norm_name, info in SOCCER_TEAM_MAPPING.items():
            if korean_name == norm_name or korean_name in info.get("aliases", []):
                # 영문 별칭 찾기
                for alias in info.get("aliases", []):
                    if alias.isascii():  # ASCII만 포함 = 영문
                        return alias

        return None

    def _parse_match_odds(
        self,
        match_data: Dict[str, Any],
        home_team: str,
        away_team: str
    ) -> Optional[MatchOdds]:
        """API 응답에서 MatchOdds 객체 생성

        Args:
            match_data: API 응답 경기 데이터
            home_team: 요청한 홈팀명 (정규화용)
            away_team: 요청한 원정팀명 (정규화용)

        Returns:
            MatchOdds 객체 또는 None
        """
        try:
            match_id = match_data.get("id", "")
            bookmakers = match_data.get("bookmakers", [])

            if not bookmakers:
                logger.warning(f"북메이커 데이터 없음: {match_id}")
                return None

            # 북메이커별 배당률 수집
            bookmaker_odds: Dict[str, Dict[str, float]] = {}
            all_home_odds = []
            all_draw_odds = []
            all_away_odds = []

            api_home_team = match_data.get("home_team", "")
            api_away_team = match_data.get("away_team", "")

            for bookmaker in bookmakers:
                bookmaker_key = bookmaker.get("key", "")
                markets = bookmaker.get("markets", [])

                for market in markets:
                    if market.get("key") != "h2h":
                        continue

                    outcomes = market.get("outcomes", [])
                    bm_odds = {}

                    for outcome in outcomes:
                        name = outcome.get("name", "")
                        price = float(outcome.get("price", 0.0))

                        if name == api_home_team:
                            bm_odds["home"] = price
                            all_home_odds.append(price)
                        elif name == api_away_team:
                            bm_odds["away"] = price
                            all_away_odds.append(price)
                        elif name.lower() == "draw":
                            bm_odds["draw"] = price
                            all_draw_odds.append(price)

                    if bm_odds:
                        bookmaker_odds[bookmaker_key] = bm_odds

            # 평균 배당률 계산 (또는 선호 북메이커 사용)
            home_odds, draw_odds, away_odds = self._get_best_odds(
                bookmaker_odds, all_home_odds, all_draw_odds, all_away_odds
            )

            if home_odds <= 0 or away_odds <= 0:
                logger.warning(f"유효한 배당률 없음: {match_id}")
                return None

            # 내재 확률 계산
            probs = self._calculate_implied_probability(home_odds, draw_odds, away_odds)

            # 정규화된 팀명 사용
            norm_home = self.team_mapper.get_normalized_name(home_team, "soccer") or home_team
            norm_away = self.team_mapper.get_normalized_name(away_team, "soccer") or away_team

            return MatchOdds(
                match_id=match_id,
                home_team=norm_home,
                away_team=norm_away,
                home_odds=home_odds,
                draw_odds=draw_odds,
                away_odds=away_odds,
                home_prob=probs["home_prob"],
                draw_prob=probs["draw_prob"],
                away_prob=probs["away_prob"],
                odds_history=[],
                bookmaker_odds=bookmaker_odds,
                overround=probs["overround"],
                movement=None,
                updated_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"배당률 파싱 오류: {e}")
            return None

    def _get_best_odds(
        self,
        bookmaker_odds: Dict[str, Dict[str, float]],
        all_home: List[float],
        all_draw: List[float],
        all_away: List[float]
    ) -> tuple[float, float, float]:
        """최적 배당률 선택

        선호 북메이커의 배당률을 우선 사용하고, 없으면 평균 사용

        Args:
            bookmaker_odds: 북메이커별 배당률
            all_home: 모든 홈 배당률
            all_draw: 모든 무승부 배당률
            all_away: 모든 원정 배당률

        Returns:
            (홈 배당률, 무승부 배당률, 원정 배당률)
        """
        # 선호 북메이커 순서대로 시도
        for bm in self.PREFERRED_BOOKMAKERS:
            if bm in bookmaker_odds:
                odds = bookmaker_odds[bm]
                if "home" in odds and "away" in odds:
                    return (
                        odds.get("home", 0.0),
                        odds.get("draw", 0.0),  # 농구는 무승부 없음
                        odds.get("away", 0.0)
                    )

        # 없으면 평균 사용
        home_avg = sum(all_home) / len(all_home) if all_home else 0.0
        draw_avg = sum(all_draw) / len(all_draw) if all_draw else 0.0
        away_avg = sum(all_away) / len(all_away) if all_away else 0.0

        return (home_avg, draw_avg, away_avg)

    def _calculate_implied_probability(
        self,
        home_odds: float,
        draw_odds: float,
        away_odds: float
    ) -> Dict[str, float]:
        """내재 확률 계산

        배당률에서 내재 확률을 계산하고 정규화합니다.

        Args:
            home_odds: 홈팀 승리 배당률
            draw_odds: 무승부 배당률
            away_odds: 원정팀 승리 배당률

        Returns:
            {
                "home_prob": float,
                "draw_prob": float,
                "away_prob": float,
                "overround": float (%)
            }
        """
        # 내재 확률 = 1 / 배당률
        raw_home = 1 / home_odds if home_odds > 0 else 0.0
        raw_draw = 1 / draw_odds if draw_odds > 0 else 0.0
        raw_away = 1 / away_odds if away_odds > 0 else 0.0

        # 총합 (오버라운드 포함)
        total = raw_home + raw_draw + raw_away

        # 오버라운드 (북메이커 마진)
        overround = (total - 1.0) * 100 if total > 0 else 0.0

        # 정규화 (합계 = 1.0)
        if total > 0:
            home_prob = raw_home / total
            draw_prob = raw_draw / total
            away_prob = raw_away / total
        else:
            home_prob = draw_prob = away_prob = 0.0

        return {
            "home_prob": round(home_prob, 4),
            "draw_prob": round(draw_prob, 4),
            "away_prob": round(away_prob, 4),
            "overround": round(overround, 2),
        }

    def _update_odds_history(self, cache_key: str, odds: MatchOdds) -> None:
        """배당률 이력 업데이트

        Args:
            cache_key: 캐시 키
            odds: 현재 배당률
        """
        snapshot = OddsSnapshot(
            timestamp=datetime.now(timezone.utc),
            home_odds=odds.home_odds,
            draw_odds=odds.draw_odds,
            away_odds=odds.away_odds,
        )

        if cache_key not in self._odds_history_cache:
            self._odds_history_cache[cache_key] = []

        history = self._odds_history_cache[cache_key]

        # 중복 방지 (마지막과 동일하면 추가하지 않음)
        if not history or history[-1] != snapshot:
            history.append(snapshot)

            # 최대 100개 유지
            if len(history) > 100:
                self._odds_history_cache[cache_key] = history[-100:]

        # odds 객체에도 이력 추가
        odds.odds_history = self._odds_history_cache[cache_key].copy()

    def _analyze_odds_movement(
        self,
        current: MatchOdds,
        history: List[OddsSnapshot]
    ) -> OddsMovement:
        """배당률 변동 분석

        현재 배당률과 이력을 비교하여 변동 방향과 의미를 분석합니다.

        Args:
            current: 현재 배당률
            history: 배당률 이력

        Returns:
            OddsMovement 객체
        """
        if len(history) < 2:
            return OddsMovement(
                direction="stable",
                magnitude=0.0,
                significance="low",
                interpretation="이력 부족으로 분석 불가",
            )

        # 첫 번째 기록과 비교
        first = history[0]
        home_change = current.home_odds - first.home_odds
        draw_change = current.draw_odds - first.draw_odds
        away_change = current.away_odds - first.away_odds

        # 가장 큰 변화 찾기
        changes = [
            ("home_drift", home_change),
            ("draw_drift", draw_change),
            ("away_drift", away_change),
        ]
        max_change = max(changes, key=lambda x: abs(x[1]))

        direction, magnitude = max_change[0], abs(max_change[1])

        # 의미 해석
        if magnitude < 0.05:
            direction = "stable"
            significance = "low"
            interpretation = "배당률 변동 없음"
        elif magnitude < 0.15:
            significance = "low"
            if "home" in direction:
                if home_change > 0:
                    interpretation = "홈팀 승리 가능성 소폭 하락"
                else:
                    interpretation = "홈팀 승리 가능성 소폭 상승"
            elif "away" in direction:
                if away_change > 0:
                    interpretation = "원정팀 승리 가능성 소폭 하락"
                else:
                    interpretation = "원정팀 승리 가능성 소폭 상승"
            else:
                if draw_change > 0:
                    interpretation = "무승부 가능성 소폭 하락"
                else:
                    interpretation = "무승부 가능성 소폭 상승"
        elif magnitude < 0.30:
            significance = "medium"
            if "home" in direction:
                if home_change > 0:
                    interpretation = "홈팀 승리 가능성 중간 수준 하락 - 베팅 패턴 주시"
                else:
                    interpretation = "홈팀 승리 가능성 중간 수준 상승 - 스마트머니 유입 가능"
            elif "away" in direction:
                if away_change > 0:
                    interpretation = "원정팀 승리 가능성 중간 수준 하락"
                else:
                    interpretation = "원정팀 승리 가능성 중간 수준 상승 - 스마트머니 유입 가능"
            else:
                interpretation = "무승부 배당 중간 수준 변동"
        else:
            significance = "high"
            if "home" in direction:
                if home_change > 0:
                    interpretation = "홈팀 배당 급등 - 부상/출전정보 확인 필요"
                else:
                    interpretation = "홈팀 배당 급락 - 대규모 베팅 유입 (주의)"
            elif "away" in direction:
                if away_change > 0:
                    interpretation = "원정팀 배당 급등 - 부상/출전정보 확인 필요"
                else:
                    interpretation = "원정팀 배당 급락 - 대규모 베팅 유입 (주의)"
            else:
                interpretation = "무승부 배당 급변 - 이상 징후 감지"

        return OddsMovement(
            direction=direction,
            magnitude=round(magnitude, 3),
            significance=significance,
            interpretation=interpretation,
        )

    async def get_league_odds(
        self,
        league: str,
        force_refresh: bool = False
    ) -> List[MatchOdds]:
        """리그 전체 배당률 조회

        Args:
            league: 리그명
            force_refresh: 캐시 무시 여부

        Returns:
            MatchOdds 리스트
        """
        if not self._api_key:
            logger.warning("배당률 수집 불가: ODDS_API_KEY 미설정")
            return []

        sport_key = self.SPORT_KEYS.get(league)
        if not sport_key:
            logger.warning(f"지원하지 않는 리그: {league}")
            return []

        try:
            all_odds = await self._fetch_from_odds_api(sport_key)

            result = []
            for match_data in all_odds:
                home_team = match_data.get("home_team", "")
                away_team = match_data.get("away_team", "")

                odds = self._parse_match_odds(match_data, home_team, away_team)
                if odds:
                    result.append(odds)

            logger.info(f"{league} 배당률 수집 완료: {len(result)}경기")
            return result

        except Exception as e:
            logger.error(f"리그 배당률 수집 오류: {league}, {e}")
            return []

    async def get_multiple_match_odds(
        self,
        matches: List[tuple[str, str, str]],
        force_refresh: bool = False
    ) -> Dict[str, Optional[MatchOdds]]:
        """여러 경기 배당률 일괄 조회

        Args:
            matches: [(홈팀, 원정팀, 리그), ...] 리스트
            force_refresh: 캐시 무시 여부

        Returns:
            {"{홈팀} vs {원정팀}": MatchOdds} 딕셔너리
        """
        tasks = []
        keys = []

        for home_team, away_team, league in matches:
            task = self.get_match_odds(
                home_team, away_team, league,
                force_refresh=force_refresh
            )
            tasks.append(task)
            keys.append(f"{home_team} vs {away_team}")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        odds_dict = {}
        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                logger.error(f"배당률 조회 실패: {key}, {result}")
                odds_dict[key] = None
            else:
                odds_dict[key] = result

        return odds_dict

    def get_api_status(self) -> Dict[str, Any]:
        """API 상태 정보 반환

        Returns:
            API 설정 및 상태 정보
        """
        limiter = RATE_LIMITERS.get("odds_api")
        limiter_stats = limiter.get_stats() if limiter else {}

        return {
            "api_key_configured": bool(self._api_key),
            "base_url": self.ODDS_API_BASE_URL,
            "supported_leagues": list(self.SPORT_KEYS.keys()),
            "rate_limiter": limiter_stats,
            "history_cache_size": len(self._odds_history_cache),
        }


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_odds_collector_instance: Optional[OddsCollector] = None


def get_odds_collector() -> OddsCollector:
    """OddsCollector 싱글톤 인스턴스 반환"""
    global _odds_collector_instance

    if _odds_collector_instance is None:
        _odds_collector_instance = OddsCollector()

    return _odds_collector_instance


# 편의를 위한 전역 인스턴스 (lazy 초기화)
odds_collector: Optional[OddsCollector] = None


def _init_odds_collector() -> OddsCollector:
    """지연 초기화된 odds_collector 반환"""
    global odds_collector
    if odds_collector is None:
        odds_collector = get_odds_collector()
    return odds_collector


# =============================================================================
# 테스트 함수
# =============================================================================

async def test_odds_collector():
    """OddsCollector 테스트"""
    print("=" * 70)
    print("OddsCollector 테스트")
    print("=" * 70)

    collector = OddsCollector()

    # 환경 확인
    print("\n[1] 환경 확인")
    print("-" * 50)
    status = collector.get_api_status()
    print(f"  ODDS_API_KEY: {'설정됨' if status['api_key_configured'] else '미설정'}")
    print(f"  지원 리그: {len(status['supported_leagues'])}개")

    if not status['api_key_configured']:
        print("\n  API 키가 설정되지 않아 테스트를 건너뜁니다.")
        print("  .env 파일에 ODDS_API_KEY를 설정하세요.")
        print("  The Odds API 키 발급: https://the-odds-api.com")
        await collector.close()
        return

    # 리그 배당률 조회 테스트
    print("\n[2] 리그 배당률 조회 테스트")
    print("-" * 50)

    test_leagues = ["Premier League"]

    for league in test_leagues:
        print(f"\n  {league}:")
        try:
            odds_list = await collector.get_league_odds(league)
            print(f"    - 경기 수: {len(odds_list)}")

            if odds_list:
                # 첫 3경기만 출력
                for odds in odds_list[:3]:
                    print(f"    - {odds.home_team} vs {odds.away_team}")
                    print(f"      홈: {odds.home_odds} ({odds.home_prob:.1%})")
                    print(f"      무: {odds.draw_odds} ({odds.draw_prob:.1%})")
                    print(f"      원: {odds.away_odds} ({odds.away_prob:.1%})")
                    print(f"      오버라운드: {odds.overround:.1%}")
        except Exception as e:
            print(f"    오류: {e}")

    # 특정 경기 조회 테스트
    print("\n[3] 특정 경기 배당률 조회 테스트")
    print("-" * 50)

    test_matches = [
        ("맨시티", "리버풀", "Premier League"),
        ("아스널", "첼시", "Premier League"),
    ]

    for home, away, league in test_matches:
        print(f"\n  {home} vs {away} ({league}):")
        try:
            odds = await collector.get_match_odds(home, away, league)
            if odds:
                print(f"    홈승: {odds.home_odds} ({odds.home_prob:.1%})")
                print(f"    무승부: {odds.draw_odds} ({odds.draw_prob:.1%})")
                print(f"    원정승: {odds.away_odds} ({odds.away_prob:.1%})")
                print(f"    오버라운드: {odds.overround:.1%}")
                print(f"    우승후보: {odds.get_favorite()}")

                if odds.movement:
                    print(f"    변동: {odds.movement.direction} ({odds.movement.significance})")
                    print(f"    해석: {odds.movement.interpretation}")
            else:
                print("    경기 찾기 실패 (현재 발매 중인 경기가 아닐 수 있음)")
        except Exception as e:
            print(f"    오류: {e}")

    # Rate Limiter 상태
    print("\n[4] Rate Limiter 상태")
    print("-" * 50)
    limiter = RATE_LIMITERS.get("odds_api")
    if limiter:
        stats = limiter.get_stats()
        print(f"  요청 제한: {stats['max_requests']}/{stats['time_window']}초")
        print(f"  사용량: {stats['current_requests']}/{stats['max_requests']}")
        print(f"  남은 요청: {stats['remaining']}")

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

    asyncio.run(test_odds_collector())
