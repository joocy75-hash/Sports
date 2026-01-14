#!/usr/bin/env python3
"""
와이즈토토 웹사이트 크롤러 - 축구 승무패 / 농구 승5패 14경기 수집

데이터 소스 1순위:
- 와이즈토토는 프로토/토토 경기 정보를 제공하는 분석 사이트
- 베트맨보다 안정적인 데이터 제공
- URL: https://www.wisetoto.com/index.htm?tab_type=toto

페이지 구조:
- 메인 페이지에서 토토 탭 선택 시 경기 목록 표시
- JavaScript 동적 로딩 방식
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
    year: int
    game_type: str  # "soccer_wdl" | "basketball_w5l"
    deadline: Optional[datetime] = None
    sale_start: Optional[datetime] = None
    sale_end: Optional[datetime] = None
    match_date: str = ""
    game_count: int = 0
    status: str = "unknown"
    source: str = "wisetoto"
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
            source=data.get("source", "wisetoto"),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
        )


@dataclass
class GameInfo:
    """경기 정보"""
    game_number: int
    home_team: str
    away_team: str
    match_date: str = ""
    match_time: str = ""
    league_name: Optional[str] = None
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    five_odds: Optional[float] = None

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


class WisetotoCrawler:
    """와이즈토토 웹사이트 크롤러"""

    # 와이즈토토 URL
    BASE_URL = "https://www.wisetoto.com"
    TOTO_URL = "https://www.wisetoto.com/index.htm?tab_type=toto"
    
    # 승무패/승5패 게임 타입
    SOCCER_WDL = "soccer_wdl"      # 축구 승무패
    BASKETBALL_W5L = "basketball_w5l"  # 농구 승5패

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self._playwright = None

        # 상태 파일
        self.soccer_state_file = STATE_DIR / "wisetoto_soccer_wdl.json"
        self.basketball_state_file = STATE_DIR / "wisetoto_basketball_w5l.json"

        # 캐시 (5분)
        self._cache: Dict[str, Tuple[RoundInfo, List[GameInfo], datetime]] = {}
        self._cache_ttl = 300

    async def __aenter__(self):
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_browser()

    async def _init_browser(self):
        """브라우저 초기화"""
        if self.browser:
            return

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        logger.info("와이즈토토 크롤러: 브라우저 시작됨")

    async def _close_browser(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("와이즈토토 크롤러: 브라우저 종료됨")

    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시 유효성 확인"""
        if cache_key not in self._cache:
            return False
        _, _, cached_at = self._cache[cache_key]
        return (datetime.now() - cached_at).total_seconds() < self._cache_ttl

    # ========== 축구 승무패 ==========

    async def get_soccer_wdl_games(
        self,
        force_refresh: bool = False
    ) -> Tuple[RoundInfo, List[GameInfo]]:
        """
        축구 승무패 14경기 조회

        Returns:
            (RoundInfo, List[GameInfo]): 회차 정보 및 14경기 목록
        """
        cache_key = "soccer_wdl"

        if not force_refresh and self._is_cache_valid(cache_key):
            info, games, _ = self._cache[cache_key]
            logger.info(f"캐시에서 축구 승무패 {info.round_number}회차 로드")
            return info, games

        await self._init_browser()

        try:
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            logger.info(f"와이즈토토 토토 페이지 로딩: {self.TOTO_URL}")
            await page.goto(self.TOTO_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)  # 동적 콘텐츠 로딩 대기

            # 축구 승무패 탭 클릭 (있다면)
            try:
                soccer_tab = await page.query_selector('text=승무패')
                if soccer_tab:
                    await soccer_tab.click()
                    await asyncio.sleep(2)
            except Exception:
                pass

            # 페이지 파싱
            round_info, games = await self._parse_toto_page(page, self.SOCCER_WDL)

            await page.close()

            if games:
                self._cache[cache_key] = (round_info, games, datetime.now())
                self._save_state(self.soccer_state_file, round_info, games)
                logger.info(f"축구 승무패 {round_info.round_number}회차 {len(games)}경기 수집 완료")

            return round_info, games

        except Exception as e:
            logger.error(f"와이즈토토 축구 승무패 크롤링 실패: {e}")

            saved = self._load_state(self.soccer_state_file)
            if saved:
                logger.warning("저장된 데이터 사용")
                return saved

            raise ValueError(f"와이즈토토 축구 승무패 크롤링 실패: {e}")

    # ========== 농구 승5패 ==========

    async def get_basketball_w5l_games(
        self,
        force_refresh: bool = False
    ) -> Tuple[RoundInfo, List[GameInfo]]:
        """
        농구 승5패 14경기 조회

        Returns:
            (RoundInfo, List[GameInfo]): 회차 정보 및 14경기 목록
        """
        cache_key = "basketball_w5l"

        if not force_refresh and self._is_cache_valid(cache_key):
            info, games, _ = self._cache[cache_key]
            logger.info(f"캐시에서 농구 승5패 {info.round_number}회차 로드")
            return info, games

        await self._init_browser()

        try:
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            logger.info(f"와이즈토토 토토 페이지 로딩: {self.TOTO_URL}")
            await page.goto(self.TOTO_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # 농구 승5패 탭 클릭 (있다면)
            try:
                basketball_tab = await page.query_selector('text=승5패')
                if basketball_tab:
                    await basketball_tab.click()
                    await asyncio.sleep(2)
            except Exception:
                pass

            # 페이지 파싱
            round_info, games = await self._parse_toto_page(page, self.BASKETBALL_W5L)

            await page.close()

            if games:
                self._cache[cache_key] = (round_info, games, datetime.now())
                self._save_state(self.basketball_state_file, round_info, games)
                logger.info(f"농구 승5패 {round_info.round_number}회차 {len(games)}경기 수집 완료")

            return round_info, games

        except Exception as e:
            logger.error(f"와이즈토토 농구 승5패 크롤링 실패: {e}")

            saved = self._load_state(self.basketball_state_file)
            if saved:
                logger.warning("저장된 데이터 사용")
                return saved

            raise ValueError(f"와이즈토토 농구 승5패 크롤링 실패: {e}")

    # ========== 페이지 파싱 ==========

    async def _parse_toto_page(self, page: Page, game_type: str) -> Tuple[RoundInfo, List[GameInfo]]:
        """토토 페이지 파싱"""

        # 1. 회차 정보 추출
        round_info = await self._extract_round_info(page, game_type)

        # 2. 경기 목록 추출
        games = await self._extract_games(page, game_type)

        round_info.game_count = len(games)

        return round_info, games

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

                    const text = document.body.innerText;

                    // 회차 추출 패턴들
                    // "승무패4회차", "승5패34회차", "4회차" 등
                    const patterns = [
                        /승무패\\s*(\\d+)회차/,
                        /승5패\\s*(\\d+)회차/,
                        /(\\d+)회차/,
                        /제?(\\d+)회/
                    ];

                    for (const pattern of patterns) {
                        const match = text.match(pattern);
                        if (match) {
                            result.round = parseInt(match[1]);
                            break;
                        }
                    }

                    // 연도 추출
                    const yearMatch = text.match(/(20\\d{2})년/);
                    if (yearMatch) {
                        result.year = parseInt(yearMatch[1]);
                    }

                    // 발매 기간 추출
                    const periodMatch = text.match(/발매기간\\s*:\\s*(\\d{4}-\\d{2}-\\d{2})\\s*(\\d{2}:\\d{2})?\\s*~?/);
                    if (periodMatch) {
                        result.sale_period = {
                            start_date: periodMatch[1],
                            start_time: periodMatch[2] || "00:00"
                        };
                    }

                    // 상태 추출
                    if (text.includes('발매중')) {
                        result.status = '발매중';
                    } else if (text.includes('마감')) {
                        result.status = '마감';
                    }

                    return result;
                }
            """)

            year = data.get("year") or datetime.now().year
            round_number = data.get("round") or 1
            status = data.get("status") or "unknown"

            return RoundInfo(
                round_number=round_number,
                year=year,
                game_type=game_type,
                status=status,
                source="wisetoto",
                updated_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"회차 정보 추출 실패: {e}")
            return RoundInfo(
                round_number=1,
                year=datetime.now().year,
                game_type=game_type,
                source="wisetoto",
            )

    async def _extract_games(self, page: Page, game_type: str) -> List[GameInfo]:
        """경기 목록 추출"""
        try:
            # 와이즈토토 페이지 구조에 맞게 파싱
            games_data = await page.evaluate("""
                (gameType) => {
                    const games = [];
                    const text = document.body.innerText;
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);

                    // 팀명 vs 팀명 패턴 찾기
                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];

                        // "홈팀 vs 원정팀" 또는 "홈팀 VS 원정팀" 패턴
                        const vsMatch = line.match(/([가-힣a-zA-Z0-9]+)\\s*(?:vs|VS)\\s*([가-힣a-zA-Z0-9]+)/i);
                        if (vsMatch) {
                            const homeTeam = vsMatch[1].trim();
                            const awayTeam = vsMatch[2].trim();

                            // 팀명 유효성 검사 (2글자 이상)
                            if (homeTeam.length >= 2 && awayTeam.length >= 2) {
                                // 중복 체크
                                const isDuplicate = games.some(g =>
                                    g.home_team === homeTeam && g.away_team === awayTeam
                                );

                                if (!isDuplicate && games.length < 14) {
                                    games.push({
                                        game_number: games.length + 1,
                                        home_team: homeTeam,
                                        away_team: awayTeam
                                    });
                                }
                            }
                        }
                    }

                    // 테이블 구조에서도 추출 시도
                    if (games.length < 14) {
                        const rows = document.querySelectorAll('tr, .game-row, .match-row, [class*="game"], [class*="match"]');
                        
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td, .team, [class*="team"]');
                            const rowText = row.textContent;

                            // 셀에서 팀명 추출
                            if (cells.length >= 2) {
                                for (let j = 0; j < cells.length - 1; j++) {
                                    const cell1 = cells[j].textContent.trim();
                                    const cell2 = cells[j + 1].textContent.trim();

                                    // 팀명처럼 보이는 경우
                                    if (cell1.length >= 2 && cell1.length <= 10 &&
                                        cell2.length >= 2 && cell2.length <= 10 &&
                                        /^[가-힣a-zA-Z]/.test(cell1) &&
                                        /^[가-힣a-zA-Z]/.test(cell2)) {

                                        const isDuplicate = games.some(g =>
                                            g.home_team === cell1 && g.away_team === cell2
                                        );

                                        if (!isDuplicate && games.length < 14) {
                                            games.push({
                                                game_number: games.length + 1,
                                                home_team: cell1,
                                                away_team: cell2
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    }

                    return games;
                }
            """, game_type)

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

            logger.info(f"와이즈토토에서 {len(games)}경기 추출 완료 ({game_type})")
            return games

        except Exception as e:
            logger.error(f"경기 목록 추출 실패: {e}")
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


# ========== 테스트 ==========

async def test_crawler():
    """크롤러 테스트"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    print("=" * 60)
    print("와이즈토토 크롤러 테스트")
    print("=" * 60)

    async with WisetotoCrawler(headless=True) as crawler:
        # 축구 승무패 테스트
        print("\n[축구 승무패]")
        try:
            info, games = await crawler.get_soccer_wdl_games(force_refresh=True)
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
    print("=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_crawler())
