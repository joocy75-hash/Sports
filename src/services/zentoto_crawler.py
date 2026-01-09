#!/usr/bin/env python3
"""
젠토토 웹사이트 크롤러 - 축구 승무패 / 농구 승5패 14경기 수집

베트맨 크롤러의 한계 해결:
1. 발매 전 다음 회차 경기 미리 확보
2. 베트맨 UI 변경에 대한 백업
3. 더 안정적인 테이블 구조

젠토토는 프로토 경기 정보를 미리 등록하므로,
발매 시작 전에 다음 회차 경기 목록을 확보할 수 있음
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)

# 상태 저장 경로
STATE_DIR = Path(__file__).parent.parent.parent / ".state"
STATE_DIR.mkdir(exist_ok=True)


@dataclass
class RoundInfo:
    """회차 정보"""
    round_number: int
    year: int  # 연도 (2026)
    game_type: str  # "soccer_wdl" | "basketball_w5l"
    deadline: Optional[datetime] = None  # 마감 시간
    sale_start: Optional[datetime] = None  # 발매 시작
    sale_end: Optional[datetime] = None  # 발매 마감
    match_date: str = ""  # YYYYMMDD
    game_count: int = 0  # 경기 수 (14경기)
    status: str = "unknown"  # "발매중" | "발매예정" | "마감" | "결과발표"
    source: str = "zentoto"  # 데이터 소스
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "year": self.year,
            "game_type": self.game_type,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "sale_start": self.sale_start.isoformat() if self.sale_start else None,
            "sale_end": self.sale_end.isoformat() if self.sale_end else None,
            "match_date": self.match_date,
            "game_count": self.game_count,
            "status": self.status,
            "source": self.source,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoundInfo":
        return cls(
            round_number=data["round_number"],
            year=data.get("year", datetime.now().year),
            game_type=data["game_type"],
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            sale_start=datetime.fromisoformat(data["sale_start"]) if data.get("sale_start") else None,
            sale_end=datetime.fromisoformat(data["sale_end"]) if data.get("sale_end") else None,
            match_date=data.get("match_date", ""),
            game_count=data.get("game_count", 0),
            status=data.get("status", "unknown"),
            source=data.get("source", "zentoto"),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
        )


@dataclass
class GameInfo:
    """경기 정보"""
    game_number: int  # 경기 번호 (1~14)
    home_team: str  # 홈팀명 (한글)
    away_team: str  # 원정팀명 (한글)
    match_date: str = ""  # 경기 날짜 (YYYYMMDD)
    match_time: str = ""  # 경기 시간 (HHMM)
    league_name: Optional[str] = None  # 리그명
    home_odds: Optional[float] = None  # 홈팀 배당률
    draw_odds: Optional[float] = None  # 무승부 배당률 (축구)
    away_odds: Optional[float] = None  # 원정팀 배당률
    five_odds: Optional[float] = None  # 5점차 이내 배당률 (농구)

    def to_dict(self) -> dict:
        return {
            "game_number": self.game_number,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "match_date": self.match_date,
            "match_time": self.match_time,
            "league_name": self.league_name,
            "home_odds": self.home_odds,
            "draw_odds": self.draw_odds,
            "away_odds": self.away_odds,
            "five_odds": self.five_odds,
        }


class ZentotoCrawler:
    """젠토토 웹사이트 크롤러

    젠토토는 프로토 경기 정보를 미리 등록하므로,
    베트맨 발매 전에 다음 회차 경기를 확보할 수 있음
    """

    # 젠토토 URL
    BASE_URL = "https://www.zentoto.com"
    SOCCER_URL = "https://www.zentoto.com/toto/soccer"
    BASKETBALL_URL = "https://www.zentoto.com/toto/basketball"

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self._playwright = None

        # 상태 파일
        self.soccer_state_file = STATE_DIR / "zentoto_soccer_wdl.json"
        self.basketball_state_file = STATE_DIR / "zentoto_basketball_w5l.json"

        # 캐시 (5분)
        self._cache: Dict[str, Tuple[RoundInfo, List[GameInfo], datetime]] = {}
        self._cache_ttl = 300  # 5분

    async def __aenter__(self):
        """컨텍스트 매니저 진입"""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        await self._close_browser()

    async def _init_browser(self):
        """브라우저 초기화"""
        if self.browser:
            return

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        logger.info("젠토토 크롤러: 브라우저 시작됨")

    async def _close_browser(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("젠토토 크롤러: 브라우저 종료됨")

    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시 유효성 확인"""
        if cache_key not in self._cache:
            return False
        _, _, cached_at = self._cache[cache_key]
        return (datetime.now() - cached_at).total_seconds() < self._cache_ttl

    # ========== 축구 승무패 ==========

    async def get_soccer_wdl_games(
        self,
        year: Optional[int] = None,
        round_number: Optional[int] = None,
        force_refresh: bool = False
    ) -> Tuple[RoundInfo, List[GameInfo]]:
        """
        축구 승무패 14경기 조회

        Args:
            year: 연도 (기본: 현재 연도)
            round_number: 회차 번호 (기본: 최신 회차)
            force_refresh: 캐시 무시하고 새로 조회

        Returns:
            (RoundInfo, List[GameInfo]): 회차 정보 및 14경기 목록
        """
        cache_key = f"soccer_wdl_{year}_{round_number}"

        # 캐시 확인
        if not force_refresh and self._is_cache_valid(cache_key):
            info, games, _ = self._cache[cache_key]
            logger.info(f"캐시에서 축구 승무패 {info.year}년 {info.round_number}회차 로드")
            return info, games

        await self._init_browser()

        try:
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # 젠토토 축구 승무패 페이지 로드
            url = self.SOCCER_URL
            if year and round_number:
                url = f"{self.SOCCER_URL}?year={year}&round={round_number}"

            logger.info(f"젠토토 축구 승무패 페이지 로딩: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # 동적 콘텐츠 로딩 대기

            # 페이지 파싱
            round_info, games = await self._parse_soccer_page(page)

            await page.close()

            # 캐시 저장
            self._cache[cache_key] = (round_info, games, datetime.now())
            self._save_state(self.soccer_state_file, round_info, games)

            logger.info(f"축구 승무패 {round_info.year}년 {round_info.round_number}회차 {len(games)}경기 수집 완료")
            return round_info, games

        except Exception as e:
            logger.error(f"젠토토 축구 승무패 크롤링 실패: {e}")

            # 저장된 상태에서 로드
            saved = self._load_state(self.soccer_state_file)
            if saved:
                logger.warning("저장된 데이터 사용")
                return saved

            raise ValueError(f"젠토토 축구 승무패 크롤링 실패: {e}")

    async def _parse_soccer_page(self, page: Page) -> Tuple[RoundInfo, List[GameInfo]]:
        """축구 승무패 페이지 파싱"""

        # 1. 회차 정보 추출
        round_info = await self._extract_round_info(page, "soccer_wdl")

        # 2. 14경기 목록 추출
        games = await self._extract_games(page, "soccer")

        round_info.game_count = len(games)

        return round_info, games

    # ========== 농구 승5패 ==========

    async def get_basketball_w5l_games(
        self,
        year: Optional[int] = None,
        round_number: Optional[int] = None,
        force_refresh: bool = False
    ) -> Tuple[RoundInfo, List[GameInfo]]:
        """
        농구 승5패 14경기 조회

        Args:
            year: 연도 (기본: 현재 연도)
            round_number: 회차 번호 (기본: 최신 회차)
            force_refresh: 캐시 무시하고 새로 조회

        Returns:
            (RoundInfo, List[GameInfo]): 회차 정보 및 14경기 목록
        """
        cache_key = f"basketball_w5l_{year}_{round_number}"

        # 캐시 확인
        if not force_refresh and self._is_cache_valid(cache_key):
            info, games, _ = self._cache[cache_key]
            logger.info(f"캐시에서 농구 승5패 {info.year}년 {info.round_number}회차 로드")
            return info, games

        await self._init_browser()

        try:
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # 젠토토 농구 승5패 페이지 로드
            url = self.BASKETBALL_URL
            if year and round_number:
                url = f"{self.BASKETBALL_URL}?year={year}&round={round_number}"

            logger.info(f"젠토토 농구 승5패 페이지 로딩: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # 페이지 파싱
            round_info, games = await self._parse_basketball_page(page)

            await page.close()

            # 캐시 저장
            self._cache[cache_key] = (round_info, games, datetime.now())
            self._save_state(self.basketball_state_file, round_info, games)

            logger.info(f"농구 승5패 {round_info.year}년 {round_info.round_number}회차 {len(games)}경기 수집 완료")
            return round_info, games

        except Exception as e:
            logger.error(f"젠토토 농구 승5패 크롤링 실패: {e}")

            # 저장된 상태에서 로드
            saved = self._load_state(self.basketball_state_file)
            if saved:
                logger.warning("저장된 데이터 사용")
                return saved

            raise ValueError(f"젠토토 농구 승5패 크롤링 실패: {e}")

    async def _parse_basketball_page(self, page: Page) -> Tuple[RoundInfo, List[GameInfo]]:
        """농구 승5패 페이지 파싱"""

        # 1. 회차 정보 추출
        round_info = await self._extract_round_info(page, "basketball_w5l")

        # 2. 14경기 목록 추출
        games = await self._extract_games(page, "basketball")

        round_info.game_count = len(games)

        return round_info, games

    # ========== 다음 회차 미리 확보 ==========

    async def get_next_round_games(
        self,
        game_type: str = "soccer_wdl"
    ) -> Optional[Tuple[RoundInfo, List[GameInfo]]]:
        """
        다음 회차 경기 미리 확보 (발매 전)

        젠토토는 발매 전에 다음 회차 경기를 미리 등록하므로,
        이 메서드로 다음 회차를 미리 확보할 수 있음

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"

        Returns:
            다음 회차 정보 및 경기 목록 (없으면 None)
        """
        await self._init_browser()

        try:
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # 해당 페이지 로드
            if game_type == "soccer_wdl":
                url = self.SOCCER_URL
            else:
                url = self.BASKETBALL_URL

            logger.info(f"다음 회차 확인 중: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # 드롭다운에서 사용 가능한 회차 목록 추출
            available_rounds = await self._get_available_rounds(page)

            if not available_rounds:
                logger.warning("사용 가능한 회차 목록을 찾을 수 없음")
                await page.close()
                return None

            # 현재 회차 확인
            current_round = await self._extract_round_info(page, game_type)

            # 다음 회차가 있는지 확인
            next_round_num = current_round.round_number + 1
            next_year = current_round.year

            # 연도 변경 처리 (예: 2026년 마지막 회차 → 2027년 1회차)
            next_round_key = f"{next_year}년 {next_round_num}회차"

            if next_round_key in available_rounds:
                logger.info(f"다음 회차 발견: {next_round_key}")

                # 다음 회차 선택
                await self._select_round(page, next_year, next_round_num)
                await asyncio.sleep(2)

                # 다음 회차 정보 파싱
                if game_type == "soccer_wdl":
                    round_info, games = await self._parse_soccer_page(page)
                else:
                    round_info, games = await self._parse_basketball_page(page)

                await page.close()

                if len(games) >= 14:
                    logger.info(f"다음 회차 {len(games)}경기 미리 확보 완료!")
                    return round_info, games
                else:
                    logger.warning(f"다음 회차 경기 수 부족: {len(games)}경기")
                    return None
            else:
                logger.info(f"다음 회차({next_round_key})가 아직 등록되지 않음")
                await page.close()
                return None

        except Exception as e:
            logger.error(f"다음 회차 확인 실패: {e}")
            return None

    async def _get_available_rounds(self, page: Page) -> List[str]:
        """드롭다운에서 사용 가능한 회차 목록 추출"""
        try:
            rounds = await page.evaluate("""
                () => {
                    const options = document.querySelectorAll('select option, .dropdown-item, [data-round]');
                    const rounds = [];
                    for (const opt of options) {
                        const text = opt.textContent.trim();
                        if (text.includes('회차')) {
                            rounds.push(text);
                        }
                    }
                    return rounds;
                }
            """)
            return rounds or []
        except Exception as e:
            logger.debug(f"회차 목록 추출 실패: {e}")
            return []

    async def _select_round(self, page: Page, year: int, round_number: int):
        """특정 회차 선택"""
        try:
            # URL 파라미터로 이동
            current_url = page.url
            base_url = current_url.split('?')[0]
            new_url = f"{base_url}?year={year}&round={round_number}"
            await page.goto(new_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            logger.debug(f"회차 선택 실패: {e}")

    # ========== 파싱 유틸리티 ==========

    async def _extract_round_info(self, page: Page, game_type: str) -> RoundInfo:
        """회차 정보 추출"""
        try:
            data = await page.evaluate("""
                () => {
                    const result = {
                        year: null,
                        round: null,
                        status: null,
                        sale_period: null
                    };

                    // 회차 정보 찾기 (예: "2026년 3회차")
                    const text = document.body.innerText;

                    // 연도와 회차 추출
                    const roundMatch = text.match(/(\\d{4})년\\s*(\\d+)회차/);
                    if (roundMatch) {
                        result.year = parseInt(roundMatch[1]);
                        result.round = parseInt(roundMatch[2]);
                    }

                    // 발매 상태 찾기
                    if (text.includes('발매중')) {
                        result.status = '발매중';
                    } else if (text.includes('발매예정')) {
                        result.status = '발매예정';
                    } else if (text.includes('마감')) {
                        result.status = '마감';
                    } else if (text.includes('결과발표')) {
                        result.status = '결과발표';
                    }

                    // 발매 기간 찾기 (예: "2026-01-08 (08:00) ~ 2026-01-10 (23:00)")
                    const periodMatch = text.match(/(\\d{4}-\\d{2}-\\d{2})\\s*\\((\\d{2}:\\d{2})\\)\\s*~\\s*(\\d{4}-\\d{2}-\\d{2})\\s*\\((\\d{2}:\\d{2})\\)/);
                    if (periodMatch) {
                        result.sale_period = {
                            start_date: periodMatch[1],
                            start_time: periodMatch[2],
                            end_date: periodMatch[3],
                            end_time: periodMatch[4]
                        };
                    }

                    return result;
                }
            """)

            year = data.get("year") or datetime.now().year
            round_number = data.get("round") or 1
            status = data.get("status") or "unknown"

            # 발매 기간 파싱
            sale_start = None
            sale_end = None
            if data.get("sale_period"):
                sp = data["sale_period"]
                try:
                    sale_start = datetime.strptime(
                        f"{sp['start_date']} {sp['start_time']}",
                        "%Y-%m-%d %H:%M"
                    )
                    sale_end = datetime.strptime(
                        f"{sp['end_date']} {sp['end_time']}",
                        "%Y-%m-%d %H:%M"
                    )
                except Exception:
                    pass

            return RoundInfo(
                round_number=round_number,
                year=year,
                game_type=game_type,
                status=status,
                sale_start=sale_start,
                sale_end=sale_end,
                deadline=sale_end,
                match_date=sale_end.strftime("%Y%m%d") if sale_end else "",
                source="zentoto",
                updated_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"회차 정보 추출 실패: {e}")
            return RoundInfo(
                round_number=1,
                year=datetime.now().year,
                game_type=game_type,
                source="zentoto",
            )

    async def _extract_games(self, page: Page, sport: str) -> List[GameInfo]:
        """경기 목록 추출 - 젠토토 테이블 구조 파싱"""
        try:
            games_data = await page.evaluate("""
                (sport) => {
                    const games = [];
                    const text = document.body.innerText;
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);

                    // 젠토토 구조 분석:
                    // [21] 1                          <- 경기 번호
                    // [22] 9	6	3	33	6	코모1907    <- 통계 + 홈팀명 (탭 구분)
                    // [23] 경기분석
                    // [24] VS
                    // [25] 볼로냐	8	26	7	5	6       <- 원정팀명 + 통계 (탭 구분)

                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];

                        // 경기 번호 찾기 (1~14 단독 숫자)
                        if (/^\\d{1,2}$/.test(line)) {
                            const gameNum = parseInt(line);
                            if (gameNum >= 1 && gameNum <= 14) {
                                let homeTeam = null;
                                let awayTeam = null;

                                // 다음 라인: "통계\\t통계\\t홈팀" 형식
                                if (i + 1 < lines.length) {
                                    const homeLine = lines[i + 1];
                                    // 탭으로 분리, 마지막이 팀명
                                    const homeParts = homeLine.split('\\t');
                                    if (homeParts.length > 0) {
                                        const lastPart = homeParts[homeParts.length - 1].trim();
                                        // 팀명 검증: 한글/영문으로 시작
                                        if (/^[가-힣a-zA-Z]/.test(lastPart) && lastPart.length >= 2) {
                                            homeTeam = lastPart;
                                        }
                                    }
                                }

                                // VS 라인 이후: "원정팀\\t통계\\t통계" 형식
                                for (let j = i + 2; j < Math.min(i + 6, lines.length); j++) {
                                    if (lines[j] === 'VS' && j + 1 < lines.length) {
                                        const awayLine = lines[j + 1];
                                        // 탭으로 분리, 첫번째가 팀명
                                        const awayParts = awayLine.split('\\t');
                                        if (awayParts.length > 0) {
                                            const firstPart = awayParts[0].trim();
                                            // 팀명 검증
                                            if (/^[가-힣a-zA-Z]/.test(firstPart) && firstPart.length >= 2) {
                                                awayTeam = firstPart;
                                            }
                                        }
                                        break;
                                    }
                                }

                                // 경기 추가
                                if (homeTeam && awayTeam) {
                                    const isDuplicate = games.some(g =>
                                        g.home_team === homeTeam && g.away_team === awayTeam
                                    );
                                    if (!isDuplicate) {
                                        games.push({
                                            game_number: gameNum,
                                            home_team: homeTeam,
                                            away_team: awayTeam
                                        });
                                    }
                                }
                            }
                        }
                    }

                    // 경기 번호순 정렬
                    games.sort((a, b) => a.game_number - b.game_number);

                    return games;
                }
            """, sport)

            if not games_data:
                logger.warning("JavaScript에서 경기 데이터 추출 실패, 대체 방법 시도")
                games_data = await self._extract_games_alternative(page, sport)

            games = [
                GameInfo(
                    game_number=g.get("game_number", i + 1),
                    home_team=g["home_team"],
                    away_team=g["away_team"],
                    match_date=g.get("match_date", ""),
                    match_time=g.get("match_time", ""),
                    league_name=g.get("league_name"),
                )
                for i, g in enumerate(games_data[:14])
            ]

            logger.info(f"{len(games)}경기 추출 완료 ({sport})")
            return games

        except Exception as e:
            logger.error(f"경기 목록 추출 실패: {e}")
            return []

    async def _extract_games_alternative(self, page: Page, sport: str) -> List[dict]:
        """대체 경기 추출 방법 (테이블 기반)"""
        try:
            games_data = await page.evaluate("""
                () => {
                    const games = [];

                    // 테이블 행에서 추출
                    const rows = document.querySelectorAll('tr, .game-row, .match-item');

                    for (const row of rows) {
                        const text = row.textContent;

                        // VS 패턴 찾기
                        const vsMatch = text.match(/([가-힣a-zA-Z0-9]+)\\s*(?:VS|vs|:)\\s*([가-힣a-zA-Z0-9]+)/);

                        if (vsMatch && games.length < 14) {
                            const homeTeam = vsMatch[1].trim();
                            const awayTeam = vsMatch[2].trim();

                            if (homeTeam.length >= 2 && awayTeam.length >= 2) {
                                const isDuplicate = games.some(g =>
                                    g.home_team === homeTeam && g.away_team === awayTeam
                                );

                                if (!isDuplicate) {
                                    games.push({
                                        game_number: games.length + 1,
                                        home_team: homeTeam,
                                        away_team: awayTeam
                                    });
                                }
                            }
                        }
                    }

                    return games;
                }
            """)

            return games_data or []

        except Exception as e:
            logger.debug(f"대체 추출 실패: {e}")
            return []

    # ========== 상태 저장/로드 ==========

    def _save_state(self, filepath: Path, info: RoundInfo, games: List[GameInfo]):
        """상태 저장"""
        try:
            data = {
                "round_info": info.to_dict(),
                "games": [g.to_dict() for g in games],
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"상태 저장: {filepath}")
        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")

    def _load_state(self, filepath: Path) -> Optional[Tuple[RoundInfo, List[GameInfo]]]:
        """상태 로드"""
        try:
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    info = RoundInfo.from_dict(data["round_info"])
                    games = [
                        GameInfo(
                            game_number=g["game_number"],
                            home_team=g["home_team"],
                            away_team=g["away_team"],
                            match_date=g.get("match_date", ""),
                            match_time=g.get("match_time", ""),
                            league_name=g.get("league_name"),
                            home_odds=g.get("home_odds"),
                            draw_odds=g.get("draw_odds"),
                            away_odds=g.get("away_odds"),
                            five_odds=g.get("five_odds"),
                        )
                        for g in data["games"]
                    ]
                    logger.info(f"상태 로드: {filepath}")
                    return info, games
        except Exception as e:
            logger.error(f"상태 로드 실패: {e}")
        return None


# ========== 편의 함수 ==========

async def fetch_soccer_wdl(
    year: Optional[int] = None,
    round_number: Optional[int] = None
) -> Tuple[RoundInfo, List[GameInfo]]:
    """축구 승무패 경기 조회 (간편 함수)"""
    async with ZentotoCrawler() as crawler:
        return await crawler.get_soccer_wdl_games(year, round_number)


async def fetch_basketball_w5l(
    year: Optional[int] = None,
    round_number: Optional[int] = None
) -> Tuple[RoundInfo, List[GameInfo]]:
    """농구 승5패 경기 조회 (간편 함수)"""
    async with ZentotoCrawler() as crawler:
        return await crawler.get_basketball_w5l_games(year, round_number)


async def fetch_next_round(game_type: str = "soccer_wdl") -> Optional[Tuple[RoundInfo, List[GameInfo]]]:
    """다음 회차 미리 확보 (간편 함수)"""
    async with ZentotoCrawler() as crawler:
        return await crawler.get_next_round_games(game_type)


# ========== 테스트 ==========

async def test_crawler():
    """크롤러 테스트"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    print("=" * 60)
    print("젠토토 크롤러 테스트")
    print("=" * 60)

    async with ZentotoCrawler(headless=True) as crawler:
        # 축구 승무패 테스트
        print("\n[축구 승무패]")
        try:
            info, games = await crawler.get_soccer_wdl_games(force_refresh=True)
            print(f"  회차: {info.year}년 {info.round_number}회차")
            print(f"  상태: {info.status}")
            print(f"  경기 수: {info.game_count}")
            print(f"  발매 기간: {info.sale_start} ~ {info.sale_end}")
            print()
            print("  경기 목록:")
            for g in games:
                print(f"    {g.game_number:02d}. {g.home_team} vs {g.away_team}")
        except Exception as e:
            print(f"  오류: {e}")

        print()

        # 농구 승5패 테스트
        print("[농구 승5패]")
        try:
            info, games = await crawler.get_basketball_w5l_games(force_refresh=True)
            print(f"  회차: {info.year}년 {info.round_number}회차")
            print(f"  상태: {info.status}")
            print(f"  경기 수: {info.game_count}")
            print()
            print("  경기 목록:")
            for g in games:
                print(f"    {g.game_number:02d}. {g.home_team} vs {g.away_team}")
        except Exception as e:
            print(f"  오류: {e}")

        print()

        # 다음 회차 확인 테스트
        print("[다음 회차 확인 - 축구]")
        try:
            result = await crawler.get_next_round_games("soccer_wdl")
            if result:
                info, games = result
                print(f"  ✅ 다음 회차 발견: {info.year}년 {info.round_number}회차")
                print(f"  경기 수: {len(games)}")
            else:
                print("  ❌ 다음 회차가 아직 등록되지 않음")
        except Exception as e:
            print(f"  오류: {e}")

    print()
    print("=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_crawler())
