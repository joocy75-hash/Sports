#!/usr/bin/env python3
"""
베트맨 웹사이트 크롤러 - 축구 승무패 / 농구 승5패 14경기 수집

KSPO API의 한계 해결:
1. 경기 누락 문제
2. row_num 불일치 문제
3. turn_no NULL 문제

Playwright를 사용하여 베트맨 웹사이트에서 직접 크롤링
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

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


@dataclass
class GameInfo:
    """경기 정보"""
    game_number: int  # 경기 번호 (1~14)
    home_team: str  # 홈팀명 (한글)
    away_team: str  # 원정팀명 (한글)
    match_date: str  # 경기 날짜 (YYYYMMDD)
    match_time: str  # 경기 시간 (HHMM)
    league_name: Optional[str] = None  # 리그명


class BetmanCrawler:
    """베트맨 웹사이트 크롤러"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None

        # 베트맨 URL
        self.base_url = "https://www.betman.co.kr"

        # 상태 파일
        self.soccer_state_file = STATE_DIR / "betman_soccer_wdl.json"
        self.basketball_state_file = STATE_DIR / "betman_basketball_w5l.json"

        # 캐시
        self._cache: Dict[str, Tuple[RoundInfo, List[GameInfo]]] = {}

    async def __aenter__(self):
        """컨텍스트 매니저 진입"""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        _ = (exc_type, exc_val, exc_tb)  # 사용하지 않는 매개변수
        await self._close_browser()

    async def _init_browser(self):
        """브라우저 초기화"""
        if self.browser:
            return

        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        logger.info("브라우저 시작됨")

    async def _close_browser(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            logger.info("브라우저 종료됨")

    # ========== 축구 승무패 ==========

    async def get_soccer_wdl_games(self, force_refresh: bool = False) -> Tuple[RoundInfo, List[GameInfo]]:
        """
        축구 승무패 14경기 조회

        Returns:
            (RoundInfo, List[GameInfo]): 회차 정보 및 14경기 목록
        """
        cache_key = "soccer_wdl"

        # 캐시 확인 (5분 이내)
        if not force_refresh and cache_key in self._cache:
            info, games = self._cache[cache_key]
            if (datetime.now() - info.updated_at).seconds < 300:
                logger.info(f"캐시에서 축구 승무패 {info.round_number}회차 로드")
                return info, games

        # 브라우저 초기화
        await self._init_browser()

        # 크롤링 실행
        try:
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # 베트맨 게임 구매 페이지 이동
            url = f"{self.base_url}/main/mainPage/gamebuy/buyableGameList.do"
            logger.info(f"페이지 로딩: {url}")

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # 추가 대기

            # 축구 승무패 탭 클릭 (동적으로 찾기)
            # 여러 가능한 선택자 시도
            selectors = [
                "text=승무패",
                "a:has-text('승무패')",
                "[data-game-type='WDL']",
                ".game-tab:has-text('승무패')",
            ]

            clicked = False
            for selector in selectors:
                try:
                    await page.click(selector, timeout=5000)
                    clicked = True
                    logger.info(f"축구 승무패 탭 클릭: {selector}")
                    break
                except PlaywrightTimeout:
                    continue

            if not clicked:
                logger.warning("축구 승무패 탭을 찾지 못함 - 기본 페이지 파싱 시도")

            await asyncio.sleep(2)  # 컨텐츠 로딩 대기

            # 페이지 파싱
            round_info, games = await self._parse_soccer_wdl_page(page)

            await page.close()

            # 캐시 및 저장
            self._cache[cache_key] = (round_info, games)
            self._save_state(self.soccer_state_file, round_info, games)

            logger.info(f"축구 승무패 {round_info.round_number}회차 {len(games)}경기 수집 완료")
            return round_info, games

        except Exception as e:
            logger.error(f"축구 승무패 크롤링 실패: {e}")

            # 저장된 상태에서 로드
            saved = self._load_state(self.soccer_state_file)
            if saved:
                logger.warning("저장된 데이터 사용")
                return saved

            raise ValueError(f"축구 승무패 크롤링 실패: {e}")

    async def _parse_soccer_wdl_page(self, page: Page) -> Tuple[RoundInfo, List[GameInfo]]:
        """축구 승무패 페이지 파싱"""

        # 베트맨은 iframe을 사용함 - iframe으로 전환
        iframe = None
        try:
            # iframe 찾기 (여러 가능한 이름 시도)
            iframe_selectors = [
                "iframe[name='ifrm']",
                "iframe#ifrm",
                "iframe",
            ]

            for selector in iframe_selectors:
                frames = await page.query_selector_all(selector)
                if frames:
                    iframe_element = frames[0]
                    iframe = await iframe_element.content_frame()
                    if iframe:
                        logger.info(f"iframe 찾음: {selector}")
                        break

            if not iframe:
                logger.warning("iframe을 찾지 못함 - 메인 페이지 사용")
                iframe = page

        except Exception as e:
            logger.warning(f"iframe 전환 실패: {e} - 메인 페이지 사용")
            iframe = page

        # 1. 회차 번호 추출
        round_number = await self._extract_round_number(iframe, "축구")

        # 2. 14경기 목록 추출
        games = []

        # JavaScript 평가로 데이터 추출 (베트맨 테이블 구조 정확히 파싱)
        try:
            games_data = await iframe.evaluate("""
                () => {
                    const items = [];
                    const tables = document.querySelectorAll('table');

                    for (let table of tables) {
                        const rows = table.querySelectorAll('tr');

                        for (let row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length < 3) continue;

                            // 첫 번째 셀이 "X경기" 형식인지 확인
                            const firstCell = cells[0].textContent.trim();
                            if (!firstCell.match(/^\\d+경기$/)) continue;

                            // 세 번째 셀 (인덱스 2)에서 팀명 추출
                            const teamCell = cells[2];
                            if (!teamCell) continue;

                            const teamText = teamCell.textContent.trim();

                            // "홈팀vs원정팀" 또는 "홈팀vs 원정팀" 패턴
                            const vsMatch = teamText.match(/^(.+?)vs\\s*(.+)$/);

                            if (vsMatch) {
                                const homeTeam = vsMatch[1].trim();
                                const awayTeam = vsMatch[2].trim();

                                // 경기 시간 추출 (두 번째 셀)
                                const timeCell = cells[1].textContent.trim();
                                const timeMatch = timeCell.match(/(\\d{2}):(\\d{2})/);
                                const matchTime = timeMatch ? timeMatch[1] + timeMatch[2] : '0000';

                                items.push({
                                    game_number: items.length + 1,
                                    home_team: homeTeam,
                                    away_team: awayTeam,
                                    match_time: matchTime
                                });
                            }
                        }

                        // 14경기 수집했으면 중단
                        if (items.length >= 14) break;
                    }

                    return items;
                }
            """)

            logger.info(f"JavaScript로 {len(games_data) if games_data else 0}경기 추출")

            if games_data:
                games = [
                    GameInfo(
                        game_number=g.get("game_number", i + 1),
                        home_team=g["home_team"],
                        away_team=g["away_team"],
                        match_date=datetime.now().strftime("%Y%m%d"),
                        match_time=g.get("match_time", "0000"),
                        league_name=g.get("league_name"),
                    )
                    for i, g in enumerate(games_data[:14])
                ]
        except Exception as e:
            logger.error(f"JavaScript 평가 실패: {e}")

        # 경기가 없으면 스크린샷 저장 후 예외 발생
        if not games:
            screenshot_path = STATE_DIR / f"betman_soccer_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            if iframe != page:
                await iframe.screenshot(path=str(STATE_DIR / f"betman_soccer_iframe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"))

            logger.error(f"경기 데이터를 찾지 못함. 스크린샷: {screenshot_path}")
            raise ValueError("축구 승무패 경기를 파싱할 수 없습니다")

        # 3. 회차 정보 생성
        match_date = datetime.now().strftime("%Y%m%d")
        if games and games[0].match_date != datetime.now().strftime("%Y%m%d"):
            match_date = games[0].match_date

        round_info = RoundInfo(
            round_number=round_number,
            game_type="soccer_wdl",
            deadline=None,  # 추후 파싱
            match_date=match_date,
            game_count=len(games),
            status="open",
            updated_at=datetime.now(),
        )

        return round_info, games

    # ========== 농구 승5패 ==========

    async def get_basketball_w5l_games(self, force_refresh: bool = False) -> Tuple[RoundInfo, List[GameInfo]]:
        """
        농구 승5패 14경기 조회

        Returns:
            (RoundInfo, List[GameInfo]): 회차 정보 및 14경기 목록
        """
        cache_key = "basketball_w5l"

        # 캐시 확인 (5분 이내)
        if not force_refresh and cache_key in self._cache:
            info, games = self._cache[cache_key]
            if (datetime.now() - info.updated_at).seconds < 300:
                logger.info(f"캐시에서 농구 승5패 {info.round_number}회차 로드")
                return info, games

        # 브라우저 초기화
        await self._init_browser()

        # 크롤링 실행
        try:
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # 베트맨 게임 구매 페이지 이동
            url = f"{self.base_url}/main/mainPage/gamebuy/buyableGameList.do"
            logger.info(f"페이지 로딩: {url}")

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # 농구 승5패 탭 클릭
            selectors = [
                "text=승5패",
                "a:has-text('승5패')",
                "[data-game-type='W5L']",
                ".game-tab:has-text('승5패')",
            ]

            clicked = False
            for selector in selectors:
                try:
                    await page.click(selector, timeout=5000)
                    clicked = True
                    logger.info(f"농구 승5패 탭 클릭: {selector}")
                    break
                except PlaywrightTimeout:
                    continue

            if not clicked:
                logger.warning("농구 승5패 탭을 찾지 못함")

            await asyncio.sleep(2)

            # 페이지 파싱
            round_info, games = await self._parse_basketball_w5l_page(page)

            await page.close()

            # 캐시 및 저장
            self._cache[cache_key] = (round_info, games)
            self._save_state(self.basketball_state_file, round_info, games)

            logger.info(f"농구 승5패 {round_info.round_number}회차 {len(games)}경기 수집 완료")
            return round_info, games

        except Exception as e:
            logger.error(f"농구 승5패 크롤링 실패: {e}")

            # 저장된 상태에서 로드
            saved = self._load_state(self.basketball_state_file)
            if saved:
                logger.warning("저장된 데이터 사용")
                return saved

            raise ValueError(f"농구 승5패 크롤링 실패: {e}")

    async def _parse_basketball_w5l_page(self, page: Page) -> Tuple[RoundInfo, List[GameInfo]]:
        """농구 승5패 페이지 파싱 (축구와 유사한 로직)"""

        # 베트맨은 iframe을 사용함 - iframe으로 전환
        iframe = None
        try:
            iframe_selectors = [
                "iframe[name='ifrm']",
                "iframe#ifrm",
                "iframe",
            ]

            for selector in iframe_selectors:
                frames = await page.query_selector_all(selector)
                if frames:
                    iframe_element = frames[0]
                    iframe = await iframe_element.content_frame()
                    if iframe:
                        logger.info(f"iframe 찾음: {selector}")
                        break

            if not iframe:
                logger.warning("iframe을 찾지 못함 - 메인 페이지 사용")
                iframe = page

        except Exception as e:
            logger.warning(f"iframe 전환 실패: {e} - 메인 페이지 사용")
            iframe = page

        round_number = await self._extract_round_number(iframe, "농구")

        games = []

        # JavaScript 평가로 데이터 추출 (베트맨 테이블 구조 정확히 파싱)
        try:
            games_data = await iframe.evaluate("""
                () => {
                    const items = [];
                    const tables = document.querySelectorAll('table');

                    for (let table of tables) {
                        const rows = table.querySelectorAll('tr');

                        for (let row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length < 3) continue;

                            // 첫 번째 셀이 "X경기" 형식인지 확인
                            const firstCell = cells[0].textContent.trim();
                            if (!firstCell.match(/^\\d+경기$/)) continue;

                            // 세 번째 셀 (인덱스 2)에서 팀명 추출
                            const teamCell = cells[2];
                            if (!teamCell) continue;

                            const teamText = teamCell.textContent.trim();

                            // "홈팀vs원정팀" 또는 "홈팀vs 원정팀" 패턴
                            const vsMatch = teamText.match(/^(.+?)vs\\s*(.+)$/);

                            if (vsMatch) {
                                const homeTeam = vsMatch[1].trim();
                                const awayTeam = vsMatch[2].trim();

                                // 경기 시간 추출 (두 번째 셀)
                                const timeCell = cells[1].textContent.trim();
                                const timeMatch = timeCell.match(/(\\d{2}):(\\d{2})/);
                                const matchTime = timeMatch ? timeMatch[1] + timeMatch[2] : '0000';

                                items.push({
                                    game_number: items.length + 1,
                                    home_team: homeTeam,
                                    away_team: awayTeam,
                                    match_time: matchTime
                                });
                            }
                        }

                        // 14경기 수집했으면 중단
                        if (items.length >= 14) break;
                    }

                    return items;
                }
            """)

            logger.info(f"JavaScript로 {len(games_data) if games_data else 0}경기 추출")

            if games_data:
                games = [
                    GameInfo(
                        game_number=g.get("game_number", i + 1),
                        home_team=g["home_team"],
                        away_team=g["away_team"],
                        match_date=datetime.now().strftime("%Y%m%d"),
                        match_time=g.get("match_time", "0000"),
                        league_name=g.get("league_name"),
                    )
                    for i, g in enumerate(games_data[:14])
                ]
        except Exception as e:
            logger.error(f"JavaScript 평가 실패: {e}")

        if not games:
            screenshot_path = STATE_DIR / f"betman_basketball_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            if iframe != page:
                await iframe.screenshot(path=str(STATE_DIR / f"betman_basketball_iframe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"))

            logger.error(f"경기 데이터를 찾지 못함. 스크린샷: {screenshot_path}")
            raise ValueError("농구 승5패 경기를 파싱할 수 없습니다")

        match_date = datetime.now().strftime("%Y%m%d")
        if games and games[0].match_date != datetime.now().strftime("%Y%m%d"):
            match_date = games[0].match_date

        round_info = RoundInfo(
            round_number=round_number,
            game_type="basketball_w5l",
            deadline=None,
            match_date=match_date,
            game_count=len(games),
            status="open",
            updated_at=datetime.now(),
        )

        return round_info, games

    # ========== 파싱 유틸리티 ==========

    async def _extract_round_number(self, page: Page, sport: str) -> int:
        """회차 번호 추출"""
        try:
            # 회차 번호는 보통 "제 XX회차" 형식
            selectors = [
                ".round-number",
                ".turn-number",
                "text=/제\\s*\\d+\\s*회차/",
                "text=/\\d+회차/",
            ]

            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.text_content()
                        # 숫자 추출
                        import re
                        match = re.search(r'(\d+)', text)
                        if match:
                            return int(match.group(1))
                except Exception:
                    continue

            # JavaScript 평가로 추출
            round_num = await page.evaluate("""
                () => {
                    const text = document.body.textContent;
                    const match = text.match(/제?\\s*(\\d+)\\s*회차/);
                    return match ? parseInt(match[1]) : null;
                }
            """)

            if round_num:
                return round_num

        except Exception as e:
            logger.debug(f"회차 번호 추출 실패: {e}")

        # 기본값: 날짜 기반 추정
        return self._estimate_round_number(sport)

    def _estimate_round_number(self, sport: str) -> int:
        """회차 번호 추정 (round_manager.py와 동일 로직)"""
        dt = datetime.now()

        if sport == "축구":
            base_date = datetime(2025, 12, 27)
            base_round = 84
            weeks_diff = (dt - base_date).days // 7
            return base_round + weeks_diff

        elif sport == "농구":
            base_date = datetime(2024, 10, 19)
            base_round = 1
            days_diff = (dt - base_date).days
            return max(1, base_round + days_diff // 2)

        return 1

    async def _parse_table_rows_betman(self, rows, iframe: Page) -> List[GameInfo]:
        """베트맨 테이블 행 파싱"""
        _ = iframe  # 사용하지 않는 매개변수
        games = []

        for i, row in enumerate(rows):
            try:
                cells = await row.query_selector_all("td")
                if len(cells) < 3:
                    continue

                # 베트맨 테이블 구조 분석
                # 각 셀의 텍스트를 가져와서 팀명 추출
                cell_texts = []
                for cell in cells:
                    text = await cell.text_content()
                    text = text.strip()
                    if text:
                        cell_texts.append(text)

                # 팀명 필터링 (숫자만 있는 것, 짧은 것 제외)
                team_candidates = [
                    t for t in cell_texts
                    if len(t) > 2
                    and not t.replace(".", "").replace(":", "").isdigit()
                    and "회차" not in t
                ]

                if len(team_candidates) >= 2:
                    games.append(GameInfo(
                        game_number=len(games) + 1,
                        home_team=team_candidates[0],
                        away_team=team_candidates[1],
                        match_date=datetime.now().strftime("%Y%m%d"),
                        match_time="0000",
                    ))

            except Exception as e:
                logger.debug(f"행 파싱 실패 (인덱스 {i}): {e}")
                continue

        return games

    def _normalize_time(self, time_str: str) -> str:
        """시간 정규화 (HH:MM -> HHMM)"""
        import re
        time_str = time_str.strip()
        match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            return f"{match.group(1).zfill(2)}{match.group(2)}"
        return "0000"

    # ========== 상태 저장/로드 ==========

    def _save_state(self, filepath: Path, info: RoundInfo, games: List[GameInfo]):
        """상태 저장"""
        try:
            data = {
                "round_info": info.to_dict(),
                "games": [
                    {
                        "game_number": g.game_number,
                        "home_team": g.home_team,
                        "away_team": g.away_team,
                        "match_date": g.match_date,
                        "match_time": g.match_time,
                        "league_name": g.league_name,
                    }
                    for g in games
                ],
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
                            match_date=g["match_date"],
                            match_time=g["match_time"],
                            league_name=g.get("league_name"),
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
    logging.basicConfig(level=logging.INFO)

    async with BetmanCrawler(headless=False) as crawler:
        print("=" * 60)
        print("축구 승무패 크롤링 테스트")
        print("=" * 60)

        try:
            info, games = await crawler.get_soccer_wdl_games(force_refresh=True)
            print(f"회차: {info.round_number}")
            print(f"경기일: {info.match_date}")
            print(f"경기 수: {info.game_count}")
            print()
            print("경기 목록:")
            for g in games:
                print(f"  {g.game_number:02d}. {g.home_team} vs {g.away_team} ({g.match_time})")
        except Exception as e:
            print(f"오류: {e}")

        print()
        print("=" * 60)
        print("농구 승5패 크롤링 테스트")
        print("=" * 60)

        try:
            info, games = await crawler.get_basketball_w5l_games(force_refresh=True)
            print(f"회차: {info.round_number}")
            print(f"경기일: {info.match_date}")
            print(f"경기 수: {info.game_count}")
            print()
            print("경기 목록:")
            for g in games:
                print(f"  {g.game_number:02d}. {g.home_team} vs {g.away_team} ({g.match_time})")
        except Exception as e:
            print(f"오류: {e}")


if __name__ == "__main__":
    asyncio.run(test_crawler())
