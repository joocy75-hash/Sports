#!/usr/bin/env python3
"""
회차 관리 모듈 - 축구 승무패 / 농구 승5패 정확한 회차 및 경기 관리

핵심 기능:
1. 와이즈토토 크롤러 우선 사용 (안정적인 데이터 제공) ⭐ 1순위
2. 젠토토 크롤러 (다음 회차 미리 확보 가능) ⭐ 2순위
3. 베트맨 크롤러 (공식 발매 사이트) - 3순위
4. KSPO API fallback (모든 크롤러 실패 시) - 4순위
5. 회차별 경기 데이터 캐싱 및 검증

데이터 소스 우선순위:
- 1순위: 와이즈토토 크롤러 (안정적인 분석 사이트) ⭐ NEW
- 2순위: 젠토토 크롤러 (다음 회차 미리 확보 가능)
- 3순위: 베트맨 크롤러 (공식 발매 사이트)
- 4순위: KSPO API (최후 수단)

와이즈토토의 장점:
- 안정적인 데이터 제공
- 베트맨보다 빠른 업데이트
- 분석 정보 포함
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# 상태 저장 경로
STATE_DIR = Path(__file__).parent.parent.parent / ".state"
STATE_DIR.mkdir(exist_ok=True)


@dataclass
class RoundInfo:
    """회차 정보"""
    round_number: int
    game_type: str  # "soccer_wdl" | "basketball_w5l"
    deadline: Optional[datetime]  # 마감 시간
    match_date: str  # YYYYMMDD
    game_count: int  # 경기 수 (14경기)
    status: str  # "open" | "closed" | "result"
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "game_type": self.game_type,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "match_date": self.match_date,
            "game_count": self.game_count,
            "status": self.status,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoundInfo":
        return cls(
            round_number=data["round_number"],
            game_type=data["game_type"],
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            match_date=data["match_date"],
            game_count=data["game_count"],
            status=data["status"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class RoundManager:
    """회차 및 경기 관리자 (젠토토 우선, 베트맨 백업, API fallback)"""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.kspo_todz_api_key
        self.base_url = settings.kspo_todz_api_base_url

        # 크롤러 (Lazy initialization)
        self._wisetoto_crawler = None  # 1순위
        self._zentoto_crawler = None   # 2순위
        self._betman_crawler = None    # 3순위

        # 상태 파일
        self.soccer_state_file = STATE_DIR / "soccer_wdl_round.json"
        self.basketball_state_file = STATE_DIR / "basketball_w5l_round.json"

        # 다음 회차 캐시 파일
        self.soccer_next_round_file = STATE_DIR / "soccer_wdl_next_round.json"
        self.basketball_next_round_file = STATE_DIR / "basketball_w5l_next_round.json"

        # 캐시 (별도 관리: 와이즈토토 캐시 + 젠토토 캐시 + 베트맨 캐시 + API 캐시)
        self._cache: Dict[str, Tuple[RoundInfo, List[Dict]]] = {}
        self._wisetoto_cache: Dict[str, Tuple[RoundInfo, List[Dict]]] = {}
        self._zentoto_cache: Dict[str, Tuple[RoundInfo, List[Dict]]] = {}
        self._crawler_cache: Dict[str, Tuple[RoundInfo, List[Dict]]] = {}

    async def _get_wisetoto_crawler(self):
        """와이즈토토 크롤러 Lazy initialization (1순위)"""
        if self._wisetoto_crawler is None:
            try:
                from src.services.wisetoto_crawler import WisetotoCrawler
                self._wisetoto_crawler = WisetotoCrawler(headless=True)
                await self._wisetoto_crawler._init_browser()
                logger.info("와이즈토토 크롤러 초기화 완료")
            except Exception as e:
                logger.warning(f"와이즈토토 크롤러 초기화 실패: {e}")
                self._wisetoto_crawler = None
        return self._wisetoto_crawler

    async def _get_zentoto_crawler(self):
        """젠토토 크롤러 Lazy initialization"""
        if self._zentoto_crawler is None:
            try:
                from src.services.zentoto_crawler import ZentotoCrawler
                self._zentoto_crawler = ZentotoCrawler(headless=True)
                await self._zentoto_crawler._init_browser()
                logger.info("젠토토 크롤러 초기화 완료")
            except Exception as e:
                logger.warning(f"젠토토 크롤러 초기화 실패: {e}")
                self._zentoto_crawler = None
        return self._zentoto_crawler

    async def _get_betman_crawler(self):
        """베트맨 크롤러 Lazy initialization"""
        if self._betman_crawler is None:
            try:
                from src.services.betman_crawler import BetmanCrawler
                self._betman_crawler = BetmanCrawler(headless=True)
                await self._betman_crawler._init_browser()
                logger.info("베트맨 크롤러 초기화 완료")
            except Exception as e:
                logger.warning(f"베트맨 크롤러 초기화 실패: {e}")
                self._betman_crawler = None
        return self._betman_crawler

    # ========== 축구 승무패 ==========

    async def get_soccer_wdl_round(
        self,
        force_refresh: bool = False,
        source: str = "auto"
    ) -> Tuple[RoundInfo, List[Dict]]:
        """
        축구 승무패 현재 회차 및 14경기 조회

        Args:
            force_refresh: 캐시 무시하고 새로 조회
            source: 데이터 소스 ("auto" | "wisetoto" | "zentoto" | "crawler" | "api")
                - "auto": 와이즈토토 → 젠토토 → 베트맨 → API 순서 (기본값)
                - "wisetoto": 와이즈토토만 사용
                - "zentoto": 젠토토만 사용
                - "crawler": 베트맨만 사용
                - "api": API만 사용

        Returns:
            (RoundInfo, List[Dict]): 회차 정보 및 14경기 목록
        """
        cache_key = "soccer_wdl"

        # 캐시 확인 (5분 이내)
        if not force_refresh:
            # 와이즈토토 캐시 우선 확인
            if source in ["auto", "wisetoto"] and cache_key in self._wisetoto_cache:
                info, games = self._wisetoto_cache[cache_key]
                if (datetime.now() - info.updated_at).total_seconds() < 300:
                    logger.info(f"와이즈토토 캐시에서 축구 승무패 {info.round_number}회차 로드")
                    return info, games

            # 젠토토 캐시 확인
            if source in ["auto", "zentoto"] and cache_key in self._zentoto_cache:
                info, games = self._zentoto_cache[cache_key]
                if (datetime.now() - info.updated_at).total_seconds() < 300:
                    logger.info(f"젠토토 캐시에서 축구 승무패 {info.round_number}회차 로드")
                    return info, games

            # 베트맨 캐시 확인
            if source in ["auto", "crawler"] and cache_key in self._crawler_cache:
                info, games = self._crawler_cache[cache_key]
                if (datetime.now() - info.updated_at).total_seconds() < 300:
                    logger.info(f"베트맨 캐시에서 축구 승무패 {info.round_number}회차 로드")
                    return info, games

            # API 캐시 확인
            if source in ["auto", "api"] and cache_key in self._cache:
                info, games = self._cache[cache_key]
                if (datetime.now() - info.updated_at).total_seconds() < 300:
                    logger.info(f"API 캐시에서 축구 승무패 {info.round_number}회차 로드")
                    return info, games

        # 1순위: 와이즈토토 크롤러 (안정적인 데이터 제공) ⭐
        if source in ["auto", "wisetoto"]:
            try:
                info, games = await self._fetch_from_wisetoto("soccer")
                if games and len(games) == 14:
                    logger.info(f"✅ 와이즈토토: 축구 승무패 {info.round_number}회차 14경기 수집")
                    self._wisetoto_cache[cache_key] = (info, games)
                    self._save_state(self.soccer_state_file, info, games)
                    return info, games
                else:
                    logger.warning(f"와이즈토토에서 {len(games) if games else 0}경기 수집 (14경기 필요)")
            except Exception as e:
                logger.warning(f"와이즈토토 실패, 젠토토 fallback 시도: {e}")

        # 2순위: 젠토토 크롤러 (다음 회차 미리 확보 가능!)
        if source in ["auto", "zentoto"]:
            try:
                info, games = await self._fetch_from_zentoto("soccer")
                if games and len(games) == 14:
                    logger.info(f"✅ 젠토토: 축구 승무패 {info.round_number}회차 14경기 수집")
                    self._zentoto_cache[cache_key] = (info, games)
                    self._save_state(self.soccer_state_file, info, games)
                    return info, games
                else:
                    logger.warning(f"젠토토에서 {len(games) if games else 0}경기 수집 (14경기 필요)")
            except Exception as e:
                logger.warning(f"젠토토 실패, 베트맨 fallback 시도: {e}")

        # 3순위: 베트맨 크롤러
        if source in ["auto", "crawler"]:
            try:
                info, games = await self._fetch_from_crawler("soccer")
                if games and len(games) == 14:
                    logger.info(f"✅ 베트맨: 축구 승무패 {info.round_number}회차 14경기 수집")
                    self._crawler_cache[cache_key] = (info, games)
                    self._save_state(self.soccer_state_file, info, games)
                    return info, games
                else:
                    logger.warning(f"베트맨에서 {len(games) if games else 0}경기 수집 (14경기 필요)")
            except Exception as e:
                logger.warning(f"베트맨 실패, API fallback 시도: {e}")

        # 4순위: KSPO API
        if source in ["auto", "api"]:
            try:
                info, games = await self._fetch_from_api("soccer")
                if games:
                    logger.info(f"✅ API: 축구 승무패 {info.round_number}회차 {len(games)}경기 수집")
                    self._cache[cache_key] = (info, games)
                    self._save_state(self.soccer_state_file, info, games)
                    return info, games
            except Exception as e:
                logger.error(f"API 조회 실패: {e}")

        # 저장된 상태에서 로드 (최후 수단)
        saved = self._load_state(self.soccer_state_file)
        if saved:
            logger.warning("저장된 데이터 사용 (모든 소스 실패)")
            return saved

        raise ValueError("축구 승무패 경기 데이터를 찾을 수 없습니다 (와이즈토토/젠토토/베트맨/API 모두 실패)")

    # ========== 농구 승5패 ==========

    async def get_basketball_w5l_round(
        self,
        force_refresh: bool = False,
        source: str = "auto"
    ) -> Tuple[RoundInfo, List[Dict]]:
        """
        농구 승5패 현재 회차 및 14경기 조회

        Args:
            force_refresh: 캐시 무시하고 새로 조회
            source: 데이터 소스 ("auto" | "wisetoto" | "zentoto" | "crawler" | "api")
                - "auto": 와이즈토토 → 젠토토 → 베트맨 → API 순서 (기본값)
                - "wisetoto": 와이즈토토만 사용
                - "zentoto": 젠토토만 사용
                - "crawler": 베트맨만 사용
                - "api": API만 사용

        Returns:
            (RoundInfo, List[Dict]): 회차 정보 및 14경기 목록
        """
        cache_key = "basketball_w5l"

        # 캐시 확인 (5분 이내)
        if not force_refresh:
            # 와이즈토토 캐시 우선 확인
            if source in ["auto", "wisetoto"] and cache_key in self._wisetoto_cache:
                info, games = self._wisetoto_cache[cache_key]
                if (datetime.now() - info.updated_at).total_seconds() < 300:
                    logger.info(f"와이즈토토 캐시에서 농구 승5패 {info.round_number}회차 로드")
                    return info, games

            # 젠토토 캐시 확인
            if source in ["auto", "zentoto"] and cache_key in self._zentoto_cache:
                info, games = self._zentoto_cache[cache_key]
                if (datetime.now() - info.updated_at).total_seconds() < 300:
                    logger.info(f"젠토토 캐시에서 농구 승5패 {info.round_number}회차 로드")
                    return info, games

            # 베트맨 캐시 확인
            if source in ["auto", "crawler"] and cache_key in self._crawler_cache:
                info, games = self._crawler_cache[cache_key]
                if (datetime.now() - info.updated_at).total_seconds() < 300:
                    logger.info(f"베트맨 캐시에서 농구 승5패 {info.round_number}회차 로드")
                    return info, games

            # API 캐시 확인
            if source in ["auto", "api"] and cache_key in self._cache:
                info, games = self._cache[cache_key]
                if (datetime.now() - info.updated_at).total_seconds() < 300:
                    logger.info(f"API 캐시에서 농구 승5패 {info.round_number}회차 로드")
                    return info, games

        # 1순위: 와이즈토토 크롤러 (안정적인 데이터 제공) ⭐
        if source in ["auto", "wisetoto"]:
            try:
                info, games = await self._fetch_from_wisetoto("basketball")
                if games and len(games) == 14:
                    logger.info(f"✅ 와이즈토토: 농구 승5패 {info.round_number}회차 14경기 수집")
                    self._wisetoto_cache[cache_key] = (info, games)
                    self._save_state(self.basketball_state_file, info, games)
                    return info, games
                else:
                    logger.warning(f"와이즈토토에서 {len(games) if games else 0}경기 수집 (14경기 필요)")
            except Exception as e:
                logger.warning(f"와이즈토토 실패, 젠토토 fallback 시도: {e}")

        # 2순위: 젠토토 크롤러 (다음 회차 미리 확보 가능!)
        if source in ["auto", "zentoto"]:
            try:
                info, games = await self._fetch_from_zentoto("basketball")
                if games and len(games) == 14:
                    logger.info(f"✅ 젠토토: 농구 승5패 {info.round_number}회차 14경기 수집")
                    self._zentoto_cache[cache_key] = (info, games)
                    self._save_state(self.basketball_state_file, info, games)
                    return info, games
                else:
                    logger.warning(f"젠토토에서 {len(games) if games else 0}경기 수집 (14경기 필요)")
            except Exception as e:
                logger.warning(f"젠토토 실패, 베트맨 fallback 시도: {e}")

        # 3순위: 베트맨 크롤러
        if source in ["auto", "crawler"]:
            try:
                info, games = await self._fetch_from_crawler("basketball")
                if games and len(games) == 14:
                    logger.info(f"✅ 베트맨: 농구 승5패 {info.round_number}회차 14경기 수집")
                    self._crawler_cache[cache_key] = (info, games)
                    self._save_state(self.basketball_state_file, info, games)
                    return info, games
                else:
                    logger.warning(f"베트맨에서 {len(games) if games else 0}경기 수집 (14경기 필요)")
            except Exception as e:
                logger.warning(f"베트맨 실패, API fallback 시도: {e}")

        # 4순위: KSPO API
        if source in ["auto", "api"]:
            try:
                info, games = await self._fetch_from_api("basketball")
                if games:
                    logger.info(f"✅ API: 농구 승5패 {info.round_number}회차 {len(games)}경기 수집")
                    self._cache[cache_key] = (info, games)
                    self._save_state(self.basketball_state_file, info, games)
                    return info, games
            except Exception as e:
                logger.error(f"API 조회 실패: {e}")

        # 저장된 상태에서 로드 (최후 수단)
        saved = self._load_state(self.basketball_state_file)
        if saved:
            logger.warning("저장된 데이터 사용 (모든 소스 실패)")
            return saved

        raise ValueError("농구 승5패 경기 데이터를 찾을 수 없습니다 (젠토토/베트맨/API 모두 실패)")

    # ========== 핵심 데이터 수집 로직 ==========

    async def _fetch_from_wisetoto(self, sport: str) -> Tuple[RoundInfo, List[Dict]]:
        """
        와이즈토토 크롤러에서 데이터 수집 (1순위)

        Args:
            sport: "soccer" | "basketball"

        Returns:
            (RoundInfo, List[Dict]): 회차 정보 및 경기 목록 (API 형식으로 변환됨)
        """
        crawler = await self._get_wisetoto_crawler()
        if not crawler:
            raise ValueError("와이즈토토 크롤러를 초기화할 수 없습니다")

        # 크롤러에서 데이터 수집
        if sport == "soccer":
            wisetoto_info, wisetoto_games = await crawler.get_soccer_wdl_games(force_refresh=True)
        else:  # basketball
            wisetoto_info, wisetoto_games = await crawler.get_basketball_w5l_games(force_refresh=True)

        # 와이즈토토 데이터를 API 형식으로 변환
        games = self._convert_wisetoto_to_api_format(wisetoto_info, wisetoto_games, sport)

        # RoundInfo 변환
        round_info = RoundInfo(
            round_number=wisetoto_info.round_number,
            game_type=wisetoto_info.game_type,
            deadline=wisetoto_info.deadline,
            match_date=wisetoto_info.match_date,
            game_count=len(games),
            status="open" if wisetoto_info.status == "발매중" else "closed",
            updated_at=datetime.now(),
        )

        return round_info, games

    def _convert_wisetoto_to_api_format(
        self,
        wisetoto_info,
        wisetoto_games,
        sport: str
    ) -> List[Dict]:
        """
        와이즈토토 데이터를 KSPO API 형식으로 변환

        Args:
            wisetoto_info: 와이즈토토 RoundInfo
            wisetoto_games: 와이즈토토 GameInfo 목록
            sport: "soccer" | "basketball"

        Returns:
            API 형식 경기 목록 (기존 코드 호환)
        """
        games = []

        for game in wisetoto_games:
            api_game = {
                "row_num": game.game_number,
                "hteam_han_nm": game.home_team,
                "ateam_han_nm": game.away_team,
                "match_ymd": game.match_date,
                "match_tm": game.match_time,
                "match_sport_han_nm": "축구" if sport == "soccer" else "농구",
                "obj_prod_nm": "토토/프로토",
                "leag_han_nm": game.league_name or "",
                "turn_no": wisetoto_info.round_number,
                "source": "wisetoto",  # 데이터 출처 표시
            }
            games.append(api_game)

        return games

    async def _fetch_from_zentoto(self, sport: str) -> Tuple[RoundInfo, List[Dict]]:
        """
        젠토토 크롤러에서 데이터 수집

        Args:
            sport: "soccer" | "basketball"

        Returns:
            (RoundInfo, List[Dict]): 회차 정보 및 경기 목록 (API 형식으로 변환됨)
        """
        crawler = await self._get_zentoto_crawler()
        if not crawler:
            raise ValueError("젠토토 크롤러를 초기화할 수 없습니다")

        # 크롤러에서 데이터 수집
        if sport == "soccer":
            zentoto_info, zentoto_games = await crawler.get_soccer_wdl_games(force_refresh=True)
        else:  # basketball
            zentoto_info, zentoto_games = await crawler.get_basketball_w5l_games(force_refresh=True)

        # 젠토토 데이터를 API 형식으로 변환
        games = self._convert_zentoto_to_api_format(zentoto_info, zentoto_games, sport)

        # RoundInfo 변환
        round_info = RoundInfo(
            round_number=zentoto_info.round_number,
            game_type=zentoto_info.game_type,
            deadline=zentoto_info.deadline,
            match_date=zentoto_info.match_date,
            game_count=len(games),
            status="open" if zentoto_info.status == "발매중" else "closed",
            updated_at=datetime.now(),
        )

        return round_info, games

    def _convert_zentoto_to_api_format(
        self,
        zentoto_info,
        zentoto_games,
        sport: str
    ) -> List[Dict]:
        """
        젠토토 데이터를 KSPO API 형식으로 변환 (v2.0 - 투표율 포함)

        Args:
            zentoto_info: 젠토토 RoundInfo
            zentoto_games: 젠토토 GameInfo 목록
            sport: "soccer" | "basketball"

        Returns:
            API 형식 경기 목록 (기존 코드 호환 + 투표율 추가)
        """
        games = []

        for game in zentoto_games:
            api_game = {
                "row_num": game.game_number,
                "hteam_han_nm": game.home_team,
                "ateam_han_nm": game.away_team,
                "match_ymd": game.match_date,
                "match_tm": game.match_time,
                "match_sport_han_nm": "축구" if sport == "soccer" else "농구",
                "obj_prod_nm": "토토/프로토",
                "leag_han_nm": game.league_name or "",
                "turn_no": zentoto_info.round_number,
                "source": "zentoto",
                # v2.0: 투표율 추가 (젠토토에서 수집)
                "home_vote": game.home_vote,  # 승 투표율 (0.0~1.0)
                "draw_vote": game.draw_vote,  # 무 투표율 (0.0~1.0)
                "away_vote": game.away_vote,  # 패 투표율 (0.0~1.0)
            }
            games.append(api_game)

        return games

    async def _fetch_from_crawler(self, sport: str) -> Tuple[RoundInfo, List[Dict]]:
        """
        베트맨 크롤러에서 데이터 수집

        Args:
            sport: "soccer" | "basketball"

        Returns:
            (RoundInfo, List[Dict]): 회차 정보 및 경기 목록 (API 형식으로 변환됨)
        """
        crawler = await self._get_betman_crawler()
        if not crawler:
            raise ValueError("베트맨 크롤러를 초기화할 수 없습니다")

        # 크롤러에서 데이터 수집
        if sport == "soccer":
            crawler_info, crawler_games = await crawler.get_soccer_wdl_games(force_refresh=True)
        else:  # basketball
            crawler_info, crawler_games = await crawler.get_basketball_w5l_games(force_refresh=True)

        # 크롤러 데이터를 API 형식으로 변환
        games = self._convert_crawler_to_api_format(crawler_info, crawler_games, sport)

        # RoundInfo 변환
        round_info = RoundInfo(
            round_number=crawler_info.round_number,
            game_type=crawler_info.game_type,
            deadline=crawler_info.deadline,
            match_date=crawler_info.match_date,
            game_count=len(games),
            status=crawler_info.status,
            updated_at=datetime.now(),
        )

        return round_info, games

    def _convert_crawler_to_api_format(
        self,
        crawler_info,
        crawler_games,
        sport: str
    ) -> List[Dict]:
        """
        크롤러 데이터를 KSPO API 형식으로 변환

        Args:
            crawler_info: 크롤러 RoundInfo
            crawler_games: 크롤러 GameInfo 목록
            sport: "soccer" | "basketball"

        Returns:
            API 형식 경기 목록 (기존 코드 호환)
        """
        games = []

        for game in crawler_games:
            api_game = {
                "row_num": game.game_number,  # int로 유지 (기존 코드 호환)
                "hteam_han_nm": game.home_team,
                "ateam_han_nm": game.away_team,
                "match_ymd": game.match_date,
                "match_tm": game.match_time,
                "match_sport_han_nm": "축구" if sport == "soccer" else "농구",
                "obj_prod_nm": "토토/프로토",
                "leag_han_nm": game.league_name or "",
                "turn_no": crawler_info.round_number,  # int로 유지
            }
            games.append(api_game)

        return games

    async def _fetch_from_api(self, sport: str) -> Tuple[RoundInfo, List[Dict]]:
        """
        KSPO API에서 데이터 수집 (기존 로직)

        Args:
            sport: "soccer" | "basketball"

        Returns:
            (RoundInfo, List[Dict]): 회차 정보 및 경기 목록
        """
        sport_name = "축구" if sport == "soccer" else "농구"
        games, round_info = await self._fetch_toto_games(sport_name, "토토/프로토")

        if not games:
            raise ValueError(f"{sport_name} 경기 데이터가 없습니다")

        # 14경기 검증
        if len(games) != 14:
            logger.warning(f"{sport_name}: {len(games)}경기 (14경기 필요)")

        return round_info, games

    async def _fetch_toto_games(
        self,
        sport: str,
        product: str,
        days_ahead: int = 14
    ) -> Tuple[List[Dict], Optional[RoundInfo]]:
        """
        토토 경기 수집 (축구 승무패 / 농구 승5패)

        핵심 로직:
        1. 향후 days_ahead일간 데이터 수집
        2. 종목 + 상품 필터링
        3. 가장 가까운 날짜의 14경기 추출
        4. row_num 1~14 정렬
        """
        all_matches = []
        today = datetime.now()

        # 1. 향후 데이터 수집
        for i in range(days_ahead):
            target_date = (today + timedelta(days=i)).strftime("%Y%m%d")
            matches = await self._fetch_matches_by_date(target_date)
            all_matches.extend(matches)
            await asyncio.sleep(0.2)

        if not all_matches:
            return [], None

        # 2. 종목 + 상품 필터링
        filtered = [
            m for m in all_matches
            if m.get("match_sport_han_nm") == sport
            and m.get("obj_prod_nm") == product
        ]

        if not filtered:
            # 프로토 상품에서 누락된 경기 보완 시도
            filtered = [
                m for m in all_matches
                if m.get("match_sport_han_nm") == sport
                and "토토" in m.get("obj_prod_nm", "")
            ]

        if not filtered:
            return [], None

        # 3. 날짜별 그룹화
        by_date: Dict[str, List[Dict]] = {}
        for m in filtered:
            date = str(m.get("match_ymd", ""))
            if date:
                by_date.setdefault(date, []).append(m)

        # 4. 가장 가까운 미래 날짜 선택 (오늘 이후)
        today_str = today.strftime("%Y%m%d")
        future_dates = sorted([d for d in by_date.keys() if d >= today_str])

        if not future_dates:
            # 오늘 날짜도 포함
            future_dates = sorted(by_date.keys())

        if not future_dates:
            return [], None

        target_date = future_dates[0]
        target_games = by_date[target_date]

        # 5. row_num 1~14 추출 및 정렬
        # row_num이 있는 경기만 필터
        numbered_games = [g for g in target_games if g.get("row_num")]
        numbered_games.sort(key=lambda x: int(x.get("row_num", 999)))

        # 14경기만
        final_games = numbered_games[:14]

        # 6. 회차 정보 추출
        turn_no = None
        for g in final_games:
            if g.get("turn_no"):
                turn_no = int(g["turn_no"])
                break

        # turn_no가 없으면 날짜 기반으로 추정
        if not turn_no:
            turn_no = self._estimate_round_number(sport, target_date)

        # 마감 시간 추출 (첫 경기 시작 시간)
        deadline = None
        if final_games:
            first_game = final_games[0]
            try:
                match_tm = str(first_game.get("match_tm", "0000")).zfill(4)
                dt_str = f"{target_date}{match_tm}"
                deadline = datetime.strptime(dt_str, "%Y%m%d%H%M")
            except ValueError:
                pass

        game_type = "soccer_wdl" if sport == "축구" else "basketball_w5l"

        round_info = RoundInfo(
            round_number=turn_no,
            game_type=game_type,
            deadline=deadline,
            match_date=target_date,
            game_count=len(final_games),
            status="open" if deadline and deadline > datetime.now() else "closed",
            updated_at=datetime.now(),
        )

        return final_games, round_info

    async def _fetch_matches_by_date(self, date_str: str) -> List[Dict]:
        """특정 날짜의 경기 목록 조회"""
        endpoint = f"{self.base_url}/todz_api_tb_match_mgmt_i"
        params = {
            "serviceKey": self.api_key,
            "pageNo": 1,
            "numOfRows": 200,
            "resultType": "JSON",
            "match_ymd": date_str,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=params, timeout=15.0)

                if response.status_code != 200:
                    logger.error(f"API 오류: {response.status_code}")
                    return []

                data = response.json()
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

                if isinstance(items, dict):
                    return [items]
                return items

        except Exception as e:
            logger.error(f"API 요청 실패 ({date_str}): {e}")
            return []

    def _estimate_round_number(self, sport: str, match_date: str) -> int:
        """
        회차 번호 추정 (API에서 turn_no가 없는 경우)

        베트맨 회차 규칙:
        - 축구 승무패: 매주 토~일 진행 (2025년 84회차 기준점 사용)
        - 농구 승5패: 시즌 중 매일 진행
        """
        try:
            dt = datetime.strptime(match_date, "%Y%m%d")

            if sport == "축구":
                # 2025년 12월 27일 = 84회차 기준
                # 축구토토 승무패는 보통 주 1회 진행
                base_date = datetime(2025, 12, 27)
                base_round = 84
                weeks_diff = (dt - base_date).days // 7
                return base_round + weeks_diff

            elif sport == "농구":
                # 농구 승5패: 2024-25 시즌 기준
                # 시즌 시작 (10월 중순)부터 약 2일에 1회차
                base_date = datetime(2024, 10, 19)  # KBL 시즌 시작
                base_round = 1
                days_diff = (dt - base_date).days
                return max(1, base_round + days_diff // 2)

        except Exception:
            pass

        # 기본값: 날짜 기반
        return int(match_date)

    # ========== 상태 저장/로드 ==========

    def _save_state(self, filepath: Path, info: RoundInfo, games: List[Dict]):
        """상태 저장"""
        try:
            data = {
                "round_info": info.to_dict(),
                "games": games,
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")

    def _load_state(self, filepath: Path) -> Optional[Tuple[RoundInfo, List[Dict]]]:
        """상태 로드"""
        try:
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    info = RoundInfo.from_dict(data["round_info"])
                    games = data["games"]
                    return info, games
        except Exception as e:
            logger.error(f"상태 로드 실패: {e}")
        return None

    # ========== 유틸리티 ==========

    async def check_new_round(self, game_type: str) -> Optional[int]:
        """
        새 회차 확인

        Returns:
            새 회차 번호 (없으면 None)
        """
        if game_type == "soccer_wdl":
            state_file = self.soccer_state_file
            fetch_func = self.get_soccer_wdl_round
        else:
            state_file = self.basketball_state_file
            fetch_func = self.get_basketball_w5l_round

        # 저장된 회차
        saved = self._load_state(state_file)
        old_round = saved[0].round_number if saved else 0

        # 현재 회차 조회
        try:
            info, _ = await fetch_func(force_refresh=True)
            new_round = info.round_number

            if new_round > old_round:
                logger.info(f"🆕 새 회차 감지: {game_type} {old_round} → {new_round}")
                return new_round

        except Exception as e:
            logger.error(f"회차 확인 실패: {e}")

        return None

    def get_last_round(self, game_type: str) -> Optional[int]:
        """마지막 분석 회차 조회"""
        if game_type == "soccer_wdl":
            state_file = self.soccer_state_file
        else:
            state_file = self.basketball_state_file

        saved = self._load_state(state_file)
        return saved[0].round_number if saved else None

    # ========== 다음 회차 미리 확보 (젠토토 활용) ==========

    async def prefetch_next_round(self, game_type: str = "soccer_wdl") -> Optional[Tuple[RoundInfo, List[Dict]]]:
        """
        다음 회차 경기 미리 확보 (발매 전)

        젠토토는 발매 전에 다음 회차 경기를 미리 등록하므로,
        이 메서드로 다음 회차를 미리 확보할 수 있음

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"

        Returns:
            다음 회차 정보 및 경기 목록 (없으면 None)
        """
        crawler = await self._get_zentoto_crawler()
        if not crawler:
            logger.warning("젠토토 크롤러 초기화 실패, 다음 회차 확보 불가")
            return None

        try:
            result = await crawler.get_next_round_games(game_type)
            if result:
                zentoto_info, zentoto_games = result

                # API 형식으로 변환
                sport = "soccer" if game_type == "soccer_wdl" else "basketball"
                games = self._convert_zentoto_to_api_format(zentoto_info, zentoto_games, sport)

                round_info = RoundInfo(
                    round_number=zentoto_info.round_number,
                    game_type=game_type,
                    deadline=zentoto_info.deadline,
                    match_date=zentoto_info.match_date,
                    game_count=len(games),
                    status="pending",  # 발매 전
                    updated_at=datetime.now(),
                )

                # 다음 회차 캐시 저장
                if game_type == "soccer_wdl":
                    next_round_file = self.soccer_next_round_file
                else:
                    next_round_file = self.basketball_next_round_file

                self._save_state(next_round_file, round_info, games)
                logger.info(f"✅ 다음 회차 미리 확보: {game_type} {round_info.round_number}회차 {len(games)}경기")

                return round_info, games
            else:
                logger.info(f"다음 회차가 아직 등록되지 않음: {game_type}")
                return None

        except Exception as e:
            logger.error(f"다음 회차 확보 실패: {e}")
            return None

    def get_prefetched_next_round(self, game_type: str) -> Optional[Tuple[RoundInfo, List[Dict]]]:
        """
        미리 확보해둔 다음 회차 조회 (캐시에서)

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"

        Returns:
            미리 확보된 다음 회차 정보 (없으면 None)
        """
        if game_type == "soccer_wdl":
            next_round_file = self.soccer_next_round_file
        else:
            next_round_file = self.basketball_next_round_file

        return self._load_state(next_round_file)

    async def check_and_prefetch(self, game_type: str = "soccer_wdl") -> dict:
        """
        현재 회차 확인 + 다음 회차 미리 확보 (통합)

        주기적으로 호출하여:
        1. 현재 발매중인 회차 정보 확보
        2. 다음 회차가 등록되어 있으면 미리 확보

        Returns:
            {
                "current": (RoundInfo, games) or None,
                "next": (RoundInfo, games) or None,
            }
        """
        result = {"current": None, "next": None}

        # 현재 회차
        try:
            if game_type == "soccer_wdl":
                info, games = await self.get_soccer_wdl_round()
            else:
                info, games = await self.get_basketball_w5l_round()
            result["current"] = (info, games)
            logger.info(f"현재 회차: {game_type} {info.round_number}회차")
        except Exception as e:
            logger.error(f"현재 회차 조회 실패: {e}")

        # 다음 회차 미리 확보
        try:
            next_result = await self.prefetch_next_round(game_type)
            if next_result:
                result["next"] = next_result
        except Exception as e:
            logger.error(f"다음 회차 확보 실패: {e}")

        return result


# ========== 테스트 ==========

async def test_round_manager():
    """테스트 실행"""
    manager = RoundManager()

    print("=" * 60)
    print("🏀 농구 승5패 회차 조회")
    print("=" * 60)

    try:
        info, games = await manager.get_basketball_w5l_round()
        print(f"회차: {info.round_number}")
        print(f"경기일: {info.match_date}")
        print(f"경기 수: {info.game_count}")
        print(f"마감: {info.deadline}")
        print(f"상태: {info.status}")
        print()
        print("경기 목록:")
        for i, g in enumerate(games, 1):
            home = g.get("hteam_han_nm", "")
            away = g.get("ateam_han_nm", "")
            row = g.get("row_num", "?")
            print(f"  {i:02d}. [{row}] {home} vs {away}")
    except Exception as e:
        print(f"오류: {e}")

    print()
    print("=" * 60)
    print("⚽ 축구 승무패 회차 조회")
    print("=" * 60)

    try:
        info, games = await manager.get_soccer_wdl_round()
        print(f"회차: {info.round_number}")
        print(f"경기일: {info.match_date}")
        print(f"경기 수: {info.game_count}")
        print(f"마감: {info.deadline}")
        print(f"상태: {info.status}")
        print()
        print("경기 목록:")
        for i, g in enumerate(games, 1):
            home = g.get("hteam_han_nm", "")
            away = g.get("ateam_han_nm", "")
            row = g.get("row_num", "?")
            print(f"  {i:02d}. [{row}] {home} vs {away}")
    except Exception as e:
        print(f"오류: {e}")


if __name__ == "__main__":
    asyncio.run(test_round_manager())
