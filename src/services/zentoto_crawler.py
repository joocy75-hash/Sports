#!/usr/bin/env python3
"""
젠토토 웹사이트 크롤러 - 축구 승무패 / 농구 승5패 14경기 수집

정적 크롤링 방식 (requests + BeautifulSoup):
- Playwright 대비 빠르고 가벼움
- 서버 부하 감소
- 안정적인 데이터 수집

v2.0 개선사항:
- 투표율 추출 (승/무/패 각각)
- 회차 정보 정확한 추출
- 경기 번호 정확한 매핑
- 리그명 추출 시도

데이터 소스 우선순위: 2순위 (와이즈토토 다음)
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import httpx

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
    source: str = "zentoto"
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
    """경기 정보 (v2.0 - 투표율 포함)"""
    game_number: int
    home_team: str
    away_team: str
    match_date: str = ""
    match_time: str = ""
    league_name: Optional[str] = None
    # 투표율 (0.0 ~ 1.0)
    home_vote: Optional[float] = None  # 승 투표율
    draw_vote: Optional[float] = None  # 무 투표율
    away_vote: Optional[float] = None  # 패 투표율
    # 배당률 (로그인 필요하므로 None)
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
            "home_vote": self.home_vote,
            "draw_vote": self.draw_vote,
            "away_vote": self.away_vote,
            "home_odds": self.home_odds,
            "draw_odds": self.draw_odds,
            "away_odds": self.away_odds,
            "five_odds": self.five_odds,
        }


class ZentotoCrawler:
    """젠토토 정적 크롤러 v2.0 (requests + BeautifulSoup + 투표율)"""

    # 젠토토 URL
    BASE_URL = "https://www.zentoto.com"
    SOCCER_URL = "https://www.zentoto.com/toto/soccer"
    BASKETBALL_URL = "https://www.zentoto.com/toto/basketball"

    # HTTP 헤더
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    # 제외할 키워드 (팀명이 아닌 것들)
    SKIP_WORDS = [
        "승", "무", "패", "VS", "HOME", "AWAY", "Team", "No", "Vote", "Result",
        "WELCOME", "젠토토", "도움말", "토토", "축구", "농구", "승무패", "승5패",
        "데이터", "로딩중", "추천픽", "전체메뉴", "랭킹", "TOP", "Rank", "Sheets",
        "LOGIN", "REGISTER", "라이브스코어", "프로토", "픽스터리그", "조합기",
        "투표율", "배당률", "배당승률", "해외배당", "보기", "적중특례", "경기분석",
    ]

    def __init__(self, headless: bool = True):
        """초기화 (headless 파라미터는 호환성을 위해 유지)"""
        self.headless = headless

        # 상태 파일
        self.soccer_state_file = STATE_DIR / "zentoto_soccer_wdl.json"
        self.basketball_state_file = STATE_DIR / "zentoto_basketball_w5l.json"

        # 캐시 (5분)
        self._cache: Dict[str, Tuple[RoundInfo, List[GameInfo], datetime]] = {}
        self._cache_ttl = 300

    async def __aenter__(self):
        """컨텍스트 매니저 진입 (호환성)"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료 (호환성)"""
        pass

    async def _init_browser(self):
        """브라우저 초기화 (호환성 - 실제로는 아무것도 안함)"""
        pass

    async def _close_browser(self):
        """브라우저 종료 (호환성 - 실제로는 아무것도 안함)"""
        pass

    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시 유효성 확인"""
        if cache_key not in self._cache:
            return False
        _, _, cached_at = self._cache[cache_key]
        return (datetime.now() - cached_at).total_seconds() < self._cache_ttl

    async def _fetch_html(self, url: str) -> str:
        """HTML 페이지 가져오기"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.HEADERS)
            response.raise_for_status()
            return response.text

    def _extract_round_info_v2(self, html: str, game_type: str) -> RoundInfo:
        """
        HTML에서 회차 정보 추출 (v2.0 - 정확한 파싱)
        
        젠토토 HTML 구조:
        <option value="260003" selected>2026년 3회차</option>
        """
        year = datetime.now().year
        round_number = 1
        status = "unknown"

        # 선택된 회차 추출: <option value="260003" selected>2026년 3회차</option>
        selected_match = re.search(
            r'<option\s+value="(\d+)"\s+selected>(\d{4})년\s*(\d+)회차</option>',
            html
        )
        if selected_match:
            year = int(selected_match.group(2))
            round_number = int(selected_match.group(3))
            logger.info(f"회차 추출 성공: {year}년 {round_number}회차")
        else:
            # fallback: 일반 패턴
            round_match = re.search(r'(\d{4})년\s*(\d+)회차', html)
            if round_match:
                year = int(round_match.group(1))
                round_number = int(round_match.group(2))

        # 상태 추출
        if "발매중" in html:
            status = "발매중"
        elif "발매예정" in html:
            status = "발매예정"
        elif "마감" in html:
            status = "마감"
        elif "결과발표" in html:
            status = "결과발표"

        # 발매 기간 추출
        sale_start = None
        sale_end = None
        period_match = re.search(
            r'(\d{4}-\d{2}-\d{2})\s*\((\d{2}:\d{2})\)\s*~\s*(\d{4}-\d{2}-\d{2})\s*\((\d{2}:\d{2})\)',
            html
        )
        if period_match:
            try:
                sale_start = datetime.strptime(
                    f"{period_match.group(1)} {period_match.group(2)}",
                    "%Y-%m-%d %H:%M"
                )
                sale_end = datetime.strptime(
                    f"{period_match.group(3)} {period_match.group(4)}",
                    "%Y-%m-%d %H:%M"
                )
            except ValueError:
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

    def _extract_games_v2(self, html: str, game_type: str) -> List[GameInfo]:
        """
        HTML에서 경기 정보 추출 (v2.0 - 투표율 포함)
        
        젠토토 HTML 구조:
        - 팀명: <span class="">코모1907</span>
        - 투표율: <p ... game_no="1" game_sw="W" vote_per="0.4801">48.01%</p>
        """
        try:
            from bs4 import BeautifulSoup
            return self._parse_games_bs4(html, game_type)
        except ImportError:
            logger.warning("BeautifulSoup not installed, using regex fallback")
            return self._parse_games_regex(html, game_type)

    def _parse_games_bs4(self, html: str, game_type: str) -> List[GameInfo]:
        """
        BeautifulSoup으로 경기 정보 파싱 (v2.0 - 개선된 팀명 추출)
        
        젠토토 HTML 구조:
        - 홈팀: <span class="">코모1907</span><img ...>
        - 원정팀: <img ... class="team-logo"><span>볼로냐</span>
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, "html.parser")
        games: Dict[int, GameInfo] = {}
        
        # 1. 투표율 추출 (game_no, game_sw, vote_per 속성)
        vote_elements = soup.find_all("p", attrs={"game_no": True, "vote_per": True})
        
        for elem in vote_elements:
            try:
                game_no = int(elem.get("game_no", 0))
                game_sw = elem.get("game_sw", "")  # W=승, D=무, L=패
                vote_per = float(elem.get("vote_per", 0))
                
                if game_no < 1 or game_no > 14:
                    continue
                
                if game_no not in games:
                    games[game_no] = GameInfo(
                        game_number=game_no,
                        home_team="",
                        away_team="",
                    )
                
                if game_sw == "W":
                    games[game_no].home_vote = vote_per
                elif game_sw == "D":
                    games[game_no].draw_vote = vote_per
                elif game_sw == "L":
                    games[game_no].away_vote = vote_per
                    
            except (ValueError, TypeError):
                continue
        
        # 2. 팀명 추출
        # 홈팀: <span class="">팀명</span> (class가 빈 문자열)
        home_teams = []
        for span in soup.find_all("span", class_=""):
            text = span.get_text(strip=True)
            if self._is_valid_team_name(text):
                home_teams.append(text)
        
        # 원정팀: <img class="team-logo"><span>팀명</span>
        away_teams = []
        for img in soup.find_all("img", class_="team-logo"):
            next_span = img.find_next_sibling("span")
            if next_span:
                text = next_span.get_text(strip=True)
                if self._is_valid_team_name(text):
                    away_teams.append(text)
        
        logger.debug(f"홈팀 {len(home_teams)}개, 원정팀 {len(away_teams)}개 추출 (BS4)")
        
        # 3. 경기 구성 (홈팀-원정팀 매칭)
        for i in range(min(14, len(home_teams), len(away_teams))):
            game_no = i + 1
            if game_no not in games:
                games[game_no] = GameInfo(
                    game_number=game_no,
                    home_team=home_teams[i],
                    away_team=away_teams[i],
                )
            else:
                games[game_no].home_team = home_teams[i]
                games[game_no].away_team = away_teams[i]
        
        # 4. 결과 정렬 및 반환
        result = []
        for i in range(1, 15):
            if i in games and games[i].home_team and games[i].away_team:
                result.append(games[i])
        
        logger.info(f"BeautifulSoup 파싱: {len(result)}경기 추출 (투표율 포함)")
        return result

    def _parse_games_regex(self, html: str, game_type: str) -> List[GameInfo]:
        """
        정규식으로 경기 정보 파싱 (v2.0 - 개선된 팀명 추출)
        
        젠토토 HTML 구조:
        - 홈팀: <span class="">코모1907</span><img ...>
        - 원정팀: <img ...><span>볼로냐</span>
        """
        games: Dict[int, GameInfo] = {}
        
        # 1. 투표율 추출
        vote_pattern = r'game_no="(\d+)"[^>]*game_sw="([WDL])"[^>]*vote_per="([\d.]+)"'
        for match in re.finditer(vote_pattern, html):
            try:
                game_no = int(match.group(1))
                game_sw = match.group(2)
                vote_per = float(match.group(3))
                
                if game_no < 1 or game_no > 14:
                    continue
                
                if game_no not in games:
                    games[game_no] = GameInfo(
                        game_number=game_no,
                        home_team="",
                        away_team="",
                    )
                
                if game_sw == "W":
                    games[game_no].home_vote = vote_per
                elif game_sw == "D":
                    games[game_no].draw_vote = vote_per
                elif game_sw == "L":
                    games[game_no].away_vote = vote_per
                    
            except (ValueError, TypeError):
                continue
        
        # 2. 팀명 추출 (홈팀 + 원정팀 모두)
        # 홈팀: <span class="">팀명</span>
        home_pattern = r'<span class="">([가-힣a-zA-Z0-9]+)</span>'
        home_teams = []
        for match in re.finditer(home_pattern, html):
            text = match.group(1)
            if self._is_valid_team_name(text):
                home_teams.append(text)
        
        # 원정팀: <img ... class="team-logo"><span>팀명</span>
        away_pattern = r'class="team-logo"[^>]*><span>([가-힣a-zA-Z0-9\s]+)</span>'
        away_teams = []
        for match in re.finditer(away_pattern, html):
            text = match.group(1).strip()
            if self._is_valid_team_name(text):
                away_teams.append(text)
        
        logger.debug(f"홈팀 {len(home_teams)}개, 원정팀 {len(away_teams)}개 추출")
        
        # 3. 경기 구성 (홈팀-원정팀 매칭)
        for i in range(min(14, len(home_teams), len(away_teams))):
            game_no = i + 1
            if game_no not in games:
                games[game_no] = GameInfo(
                    game_number=game_no,
                    home_team=home_teams[i],
                    away_team=away_teams[i],
                )
            else:
                games[game_no].home_team = home_teams[i]
                games[game_no].away_team = away_teams[i]
        
        # 4. 결과 정렬 및 반환
        result = []
        for i in range(1, 15):
            if i in games and games[i].home_team and games[i].away_team:
                result.append(games[i])
        
        logger.info(f"Regex 파싱: {len(result)}경기 추출 (투표율 포함)")
        return result

    def _is_valid_team_name(self, text: str) -> bool:
        """유효한 팀명인지 확인"""
        if not text or len(text) < 2 or len(text) > 15:
            return False
        if not re.match(r'^[가-힣a-zA-Z]', text):
            return False
        if text.isdigit():
            return False
        if text in self.SKIP_WORDS:
            return False
        if any(w in text for w in self.SKIP_WORDS):
            return False
        return True

    # ========== 축구 승무패 ==========

    async def get_soccer_wdl_games(
        self,
        year: Optional[int] = None,
        round_number: Optional[int] = None,
        force_refresh: bool = False
    ) -> Tuple[RoundInfo, List[GameInfo]]:
        """축구 승무패 14경기 조회 (v2.0 - 투표율 포함)"""
        cache_key = f"soccer_wdl_{year}_{round_number}"

        # 캐시 확인
        if not force_refresh and self._is_cache_valid(cache_key):
            info, games, _ = self._cache[cache_key]
            logger.info(f"캐시에서 축구 승무패 {info.year}년 {info.round_number}회차 로드")
            return info, games

        try:
            # URL 구성
            url = self.SOCCER_URL
            if year and round_number:
                # 젠토토 URL 형식: ?round=260003 (연도2자리 + 회차3자리)
                round_code = f"{year % 100:02d}{round_number:04d}"
                url = f"{self.SOCCER_URL}?round={round_code}"

            logger.info(f"젠토토 축구 승무패 페이지 로딩: {url}")

            # HTML 가져오기
            html = await self._fetch_html(url)

            # 회차 정보 추출 (v2.0)
            round_info = self._extract_round_info_v2(html, "soccer_wdl")

            # 경기 정보 추출 (v2.0 - 투표율 포함)
            games = self._extract_games_v2(html, "soccer_wdl")

            round_info.game_count = len(games)

            # 캐시 저장
            self._cache[cache_key] = (round_info, games, datetime.now())
            self._save_state(self.soccer_state_file, round_info, games)

            logger.info(f"축구 승무패 {round_info.year}년 {round_info.round_number}회차 {len(games)}경기 수집 완료")
            
            # 투표율 로깅
            for g in games[:3]:  # 처음 3경기만 로깅
                logger.debug(f"  {g.game_number}. {g.home_team} vs {g.away_team} "
                           f"(승:{g.home_vote:.2%}, 무:{g.draw_vote:.2%}, 패:{g.away_vote:.2%})"
                           if g.home_vote else f"  {g.game_number}. {g.home_team} vs {g.away_team}")
            
            return round_info, games

        except Exception as e:
            logger.error(f"젠토토 축구 승무패 크롤링 실패: {e}")

            # 저장된 상태에서 로드
            saved = self._load_state(self.soccer_state_file)
            if saved:
                logger.warning("저장된 데이터 사용")
                return saved

            raise ValueError(f"젠토토 축구 승무패 크롤링 실패: {e}")

    # ========== 농구 승5패 ==========

    async def get_basketball_w5l_games(
        self,
        year: Optional[int] = None,
        round_number: Optional[int] = None,
        force_refresh: bool = False
    ) -> Tuple[RoundInfo, List[GameInfo]]:
        """농구 승5패 14경기 조회 (v2.0 - 투표율 포함)"""
        cache_key = f"basketball_w5l_{year}_{round_number}"

        # 캐시 확인
        if not force_refresh and self._is_cache_valid(cache_key):
            info, games, _ = self._cache[cache_key]
            logger.info(f"캐시에서 농구 승5패 {info.year}년 {info.round_number}회차 로드")
            return info, games

        try:
            # URL 구성
            url = self.BASKETBALL_URL
            if year and round_number:
                round_code = f"{year % 100:02d}{round_number:04d}"
                url = f"{self.BASKETBALL_URL}?round={round_code}"

            logger.info(f"젠토토 농구 승5패 페이지 로딩: {url}")

            # HTML 가져오기
            html = await self._fetch_html(url)

            # 회차 정보 추출 (v2.0)
            round_info = self._extract_round_info_v2(html, "basketball_w5l")

            # 경기 정보 추출 (v2.0 - 투표율 포함)
            games = self._extract_games_v2(html, "basketball_w5l")

            round_info.game_count = len(games)

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

    # ========== 다음 회차 미리 확보 ==========

    async def get_next_round_games(
        self,
        game_type: str = "soccer_wdl"
    ) -> Optional[Tuple[RoundInfo, List[GameInfo]]]:
        """다음 회차 경기 미리 확보"""
        try:
            # 현재 회차 조회
            if game_type == "soccer_wdl":
                current_info, _ = await self.get_soccer_wdl_games()
                url_base = self.SOCCER_URL
            else:
                current_info, _ = await self.get_basketball_w5l_games()
                url_base = self.BASKETBALL_URL

            # 다음 회차 URL
            next_round = current_info.round_number + 1
            next_year = current_info.year
            round_code = f"{next_year % 100:02d}{next_round:04d}"
            url = f"{url_base}?round={round_code}"

            logger.info(f"다음 회차 확인 중: {next_year}년 {next_round}회차")

            # HTML 가져오기
            html = await self._fetch_html(url)

            # 회차 정보 확인
            round_info = self._extract_round_info_v2(html, game_type)

            # 다음 회차가 맞는지 확인
            if round_info.round_number != next_round:
                logger.info(f"다음 회차({next_round})가 아직 등록되지 않음")
                return None

            # 경기 정보 추출
            games = self._extract_games_v2(html, game_type)

            if len(games) >= 14:
                round_info.game_count = len(games)
                logger.info(f"다음 회차 {len(games)}경기 미리 확보 완료!")
                return round_info, games
            else:
                logger.warning(f"다음 회차 경기 수 부족: {len(games)}경기")
                return None

        except Exception as e:
            logger.error(f"다음 회차 확인 실패: {e}")
            return None

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
                            home_vote=g.get("home_vote"),
                            draw_vote=g.get("draw_vote"),
                            away_vote=g.get("away_vote"),
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
    crawler = ZentotoCrawler()
    return await crawler.get_soccer_wdl_games(year, round_number)


async def fetch_basketball_w5l(
    year: Optional[int] = None,
    round_number: Optional[int] = None
) -> Tuple[RoundInfo, List[GameInfo]]:
    """농구 승5패 경기 조회 (간편 함수)"""
    crawler = ZentotoCrawler()
    return await crawler.get_basketball_w5l_games(year, round_number)


async def fetch_next_round(game_type: str = "soccer_wdl") -> Optional[Tuple[RoundInfo, List[GameInfo]]]:
    """다음 회차 미리 확보 (간편 함수)"""
    crawler = ZentotoCrawler()
    return await crawler.get_next_round_games(game_type)


# ========== 테스트 ==========

async def test_crawler():
    """크롤러 테스트 (v2.0 - 투표율 포함)"""
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    print("=" * 70)
    print("젠토토 정적 크롤러 v2.0 테스트 (투표율 포함)")
    print("=" * 70)

    crawler = ZentotoCrawler()

    # 축구 승무패 테스트
    print("\n[축구 승무패]")
    try:
        info, games = await crawler.get_soccer_wdl_games(force_refresh=True)
        print(f"  회차: {info.year}년 {info.round_number}회차")
        print(f"  상태: {info.status}")
        print(f"  경기 수: {info.game_count}")
        print()
        print("  경기 목록 (투표율 포함):")
        for g in games:
            vote_str = ""
            if g.home_vote is not None:
                vote_str = f" | 승:{g.home_vote*100:.1f}% 무:{g.draw_vote*100:.1f}% 패:{g.away_vote*100:.1f}%"
            print(f"    {g.game_number:02d}. {g.home_team} vs {g.away_team}{vote_str}")
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
        print("  경기 목록 (투표율 포함):")
        for g in games:
            vote_str = ""
            if g.home_vote is not None:
                vote_str = f" | 승:{g.home_vote*100:.1f}% 패:{g.away_vote*100:.1f}%"
            print(f"    {g.game_number:02d}. {g.home_team} vs {g.away_team}{vote_str}")
    except Exception as e:
        print(f"  오류: {e}")

    print()
    print("=" * 70)
    print("테스트 완료")
    print("=" * 70)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_crawler())
