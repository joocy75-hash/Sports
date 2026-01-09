# 실시간 데이터 연동 작업 계획서

> **버전**: 1.0.0
> **작성일**: 2026-01-10
> **목표 버전**: v4.0.0
> **예상 작업량**: 대규모 (코어 기능 개선)

---

## 1. 개요

### 1.1 현재 상태 분석

```
현재 시스템 (v3.3.0):
┌─────────────────────────────────────────────────────────┐
│                    AI 분석 흐름                          │
├─────────────────────────────────────────────────────────┤
│  경기명 ("코모1907 vs 볼로냐")                           │
│           │                                              │
│           ▼                                              │
│  ┌─────────────────────────────────┐                    │
│  │ AI 모델 (GPT, Claude 등)        │                    │
│  │ - 사전 학습된 지식만 사용        │ ◄── 현재 한계     │
│  │ - 실시간 데이터 없음            │                    │
│  └─────────────────────────────────┘                    │
│           │                                              │
│           ▼                                              │
│  예측 결과 (정확도 한계)                                 │
└─────────────────────────────────────────────────────────┘
```

### 1.2 목표 상태

```
목표 시스템 (v4.0.0):
┌─────────────────────────────────────────────────────────┐
│                    AI 분석 흐름 (개선)                    │
├─────────────────────────────────────────────────────────┤
│  경기명 + 실시간 데이터                                  │
│           │                                              │
│           ▼                                              │
│  ┌─────────────────────────────────┐                    │
│  │ 데이터 수집 레이어 (NEW)        │                    │
│  │ ├── 팀 통계 API                 │                    │
│  │ ├── 최근 폼 데이터              │                    │
│  │ ├── 상대 전적 (H2H)             │                    │
│  │ ├── 부상자/출전정지             │                    │
│  │ └── 실시간 배당률               │                    │
│  └─────────────────────────────────┘                    │
│           │                                              │
│           ▼                                              │
│  ┌─────────────────────────────────┐                    │
│  │ 풍부한 MatchContext             │                    │
│  │ - 팀 통계: 득점/실점/승률 등     │                    │
│  │ - 폼: 최근 5경기 W/D/L          │                    │
│  │ - H2H: 최근 10경기 상대전적     │                    │
│  │ - 부상자: 주전 선수 결장 정보    │                    │
│  │ - 배당: 실시간 배당률 변동       │                    │
│  └─────────────────────────────────┘                    │
│           │                                              │
│           ▼                                              │
│  ┌─────────────────────────────────┐                    │
│  │ AI 모델 (GPT, Claude 등)        │                    │
│  │ - 실시간 데이터 기반 분석        │ ◄── 정확도 향상   │
│  │ - 맥락 있는 예측                │                    │
│  └─────────────────────────────────┘                    │
│           │                                              │
│           ▼                                              │
│  예측 결과 (정확도 대폭 향상)                            │
└─────────────────────────────────────────────────────────┘
```

### 1.3 기대 효과

| 항목 | 현재 | 목표 | 개선율 |
|------|------|------|--------|
| 예측 정확도 | ~55% (추정) | ~65-70% | +10-15% |
| AI 컨텍스트 품질 | 낮음 | 높음 | - |
| 이변 감지 정확도 | 중간 | 높음 | - |
| 데이터 신선도 | 없음 | 실시간 | - |

---

## 2. 데이터 소스 분석

### 2.1 축구 데이터 API 비교

| API | 무료 티어 | 커버리지 | 데이터 품질 | 추천도 |
|-----|----------|----------|------------|--------|
| **Football-Data.org** | 10 req/min | 주요 유럽 리그 | 높음 | ⭐⭐⭐⭐⭐ |
| **API-Football** | 100 req/day | 전 세계 리그 | 매우 높음 | ⭐⭐⭐⭐ |
| **OpenLigaDB** | 무제한 | 분데스리가 | 중간 | ⭐⭐⭐ |
| **Sportmonks** | 유료만 | 전 세계 | 매우 높음 | ⭐⭐⭐⭐ |
| **TheSportsDB** | 무제한 | 전 세계 | 중간 | ⭐⭐⭐ |

### 2.2 농구 데이터 API 비교

| API | 무료 티어 | 커버리지 | 데이터 품질 | 추천도 |
|-----|----------|----------|------------|--------|
| **API-Basketball** | 100 req/day | NBA, 유럽, KBL | 높음 | ⭐⭐⭐⭐⭐ |
| **BallDontLie** | 무제한 | NBA만 | 중간 | ⭐⭐⭐ |
| **SportsData.io** | 1000 req/month | NBA, WNBA | 높음 | ⭐⭐⭐⭐ |
| **KBL 공식** | 없음 | KBL | 높음 | 크롤링 필요 |

### 2.3 배당률 데이터 소스

| 소스 | 방식 | 실시간 | 추천도 |
|------|------|--------|--------|
| **Odds API** | REST API | ✅ | ⭐⭐⭐⭐⭐ |
| **젠토토** | 크롤링 | ⚠️ | ⭐⭐⭐⭐ |
| **베트맨** | 크롤링 | ⚠️ | ⭐⭐⭐⭐ |
| **해외 북메이커** | API | ✅ | ⭐⭐⭐ |

### 2.4 부상자/출전정지 데이터

| 소스 | 방식 | 갱신 주기 | 추천도 |
|------|------|----------|--------|
| **Transfermarkt** | 크롤링 | 일 1회 | ⭐⭐⭐⭐⭐ |
| **Rotowire** | 크롤링 | 실시간 | ⭐⭐⭐⭐ |
| **API-Football** | API | 실시간 | ⭐⭐⭐⭐⭐ |
| **공식 팀 사이트** | 크롤링 | 불규칙 | ⭐⭐ |

---

## 3. 상세 작업 계획

### Phase 1: 데이터 수집 레이어 구축

#### 3.1.1 팀 통계 수집 모듈 (`team_stats_collector.py`)

**목표**: 팀별 시즌 통계 수집 및 캐싱

**수집 데이터**:
```python
@dataclass
class TeamStats:
    """팀 시즌 통계"""
    team_id: str
    team_name: str
    league: str
    season: str

    # 기본 통계
    matches_played: int
    wins: int
    draws: int
    losses: int

    # 득실점
    goals_scored: int
    goals_conceded: int
    goals_scored_avg: float  # 경기당 평균 득점
    goals_conceded_avg: float  # 경기당 평균 실점

    # 홈/원정 분리 통계
    home_wins: int
    home_draws: int
    home_losses: int
    home_goals_scored: int
    home_goals_conceded: int

    away_wins: int
    away_draws: int
    away_losses: int
    away_goals_scored: int
    away_goals_conceded: int

    # 리그 순위
    league_position: int
    points: int

    # 고급 통계 (가능한 경우)
    xG: Optional[float] = None  # Expected Goals
    xGA: Optional[float] = None  # Expected Goals Against
    possession_avg: Optional[float] = None
    shots_on_target_avg: Optional[float] = None

    # 메타데이터
    updated_at: datetime = None
```

**구현 상세**:
```python
# src/services/data/team_stats_collector.py

class TeamStatsCollector:
    """팀 통계 수집기"""

    def __init__(self):
        self.football_api = FootballDataAPI()
        self.basketball_api = APIBasketball()
        self.cache = RedisCache()  # 또는 파일 캐시

    async def get_team_stats(
        self,
        team_name: str,
        league: str,
        sport: str = "soccer"
    ) -> TeamStats:
        """
        팀 통계 조회 (캐시 우선)

        1. 캐시 확인 (TTL: 6시간)
        2. 캐시 미스 시 API 호출
        3. 팀명 매칭 (정규화 필요)
        """
        pass

    async def _fetch_from_football_data(
        self,
        team_name: str,
        league: str
    ) -> TeamStats:
        """Football-Data.org API 호출"""
        pass

    async def _fetch_from_api_football(
        self,
        team_name: str,
        league: str
    ) -> TeamStats:
        """API-Football 호출 (백업)"""
        pass

    def _normalize_team_name(self, name: str) -> str:
        """팀명 정규화 (베트맨 ↔ API 매칭)"""
        # 기존 team_name_normalizer.py 확장
        pass
```

**API 연동 예시 (Football-Data.org)**:
```python
async def _fetch_from_football_data(self, team_id: int) -> dict:
    """
    Football-Data.org API 호출

    Endpoint: GET /v4/teams/{id}
    Rate Limit: 10 requests/minute (무료)
    """
    url = f"https://api.football-data.org/v4/teams/{team_id}"
    headers = {"X-Auth-Token": self.api_key}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                # Rate limit - 대기 후 재시도
                await asyncio.sleep(60)
                return await self._fetch_from_football_data(team_id)
```

---

#### 3.1.2 최근 폼 수집 모듈 (`form_collector.py`)

**목표**: 팀별 최근 5경기 결과 수집

**수집 데이터**:
```python
@dataclass
class TeamForm:
    """팀 최근 폼"""
    team_name: str

    # 최근 5경기 결과 ['W', 'W', 'D', 'L', 'W']
    recent_results: List[str]

    # 최근 5경기 상세
    recent_matches: List[RecentMatch]

    # 폼 지표
    form_points: int  # 최근 5경기 승점 (W=3, D=1, L=0)
    form_goals_scored: int
    form_goals_conceded: int
    form_goal_diff: int

    # 연승/연패 여부
    winning_streak: int
    losing_streak: int
    unbeaten_streak: int

    updated_at: datetime

@dataclass
class RecentMatch:
    """최근 경기 상세"""
    date: str
    opponent: str
    home_away: str  # 'H' or 'A'
    result: str  # 'W', 'D', 'L'
    score: str  # '2-1'
    goals_scored: int
    goals_conceded: int
```

**구현 상세**:
```python
# src/services/data/form_collector.py

class FormCollector:
    """최근 폼 수집기"""

    async def get_team_form(
        self,
        team_name: str,
        league: str,
        num_matches: int = 5
    ) -> TeamForm:
        """
        팀 최근 폼 조회

        1. API에서 최근 경기 목록 조회
        2. 결과 분석 (W/D/L)
        3. 폼 지표 계산
        """
        pass

    def _calculate_form_metrics(
        self,
        matches: List[RecentMatch]
    ) -> dict:
        """폼 지표 계산"""
        # 승점, 득실점, 연승/연패 등
        pass
```

---

#### 3.1.3 상대 전적 수집 모듈 (`h2h_collector.py`)

**목표**: 두 팀 간 최근 상대 전적 수집

**수집 데이터**:
```python
@dataclass
class HeadToHead:
    """상대 전적"""
    home_team: str
    away_team: str

    # 총 전적
    total_matches: int
    home_team_wins: int
    draws: int
    away_team_wins: int

    # 득실점
    home_team_goals: int
    away_team_goals: int

    # 최근 5경기 상세
    recent_matches: List[H2HMatch]

    # 홈/원정 구분 전적
    home_venue_record: dict  # 홈팀 홈경기 전적
    away_venue_record: dict  # 홈팀 원정경기 전적

    updated_at: datetime

@dataclass
class H2HMatch:
    """상대전적 개별 경기"""
    date: str
    competition: str
    home_team: str
    away_team: str
    score: str  # '2-1'
    winner: str  # 'home', 'away', 'draw'
```

**구현 상세**:
```python
# src/services/data/h2h_collector.py

class H2HCollector:
    """상대 전적 수집기"""

    async def get_head_to_head(
        self,
        team1: str,
        team2: str,
        limit: int = 10
    ) -> HeadToHead:
        """
        상대 전적 조회

        1. 두 팀 ID 조회
        2. API에서 상대 전적 조회
        3. 통계 계산
        """
        pass
```

---

#### 3.1.4 부상자/출전정지 수집 모듈 (`injuries_collector.py`)

**목표**: 팀별 부상자 및 출전 정지 선수 목록 수집

**수집 데이터**:
```python
@dataclass
class PlayerInjury:
    """선수 부상/출전정지 정보"""
    player_name: str
    team: str
    position: str  # 'GK', 'DF', 'MF', 'FW'

    # 상태
    status: str  # 'injured', 'suspended', 'doubtful'
    injury_type: Optional[str]  # 'Hamstring', 'Knee', etc.

    # 복귀 예정
    expected_return: Optional[str]

    # 중요도
    is_key_player: bool  # 주전 여부
    season_appearances: int
    season_goals: int
    season_assists: int

@dataclass
class TeamInjuries:
    """팀 부상자 목록"""
    team_name: str
    injuries: List[PlayerInjury]
    suspensions: List[PlayerInjury]
    doubts: List[PlayerInjury]

    # 요약
    total_unavailable: int
    key_players_out: int

    updated_at: datetime
```

**구현 상세**:
```python
# src/services/data/injuries_collector.py

class InjuriesCollector:
    """부상자 정보 수집기"""

    async def get_team_injuries(
        self,
        team_name: str
    ) -> TeamInjuries:
        """
        팀 부상자 정보 조회

        1. API-Football injuries endpoint
        2. 또는 Transfermarkt 크롤링
        """
        pass

    async def _fetch_from_api_football(self, team_id: int) -> dict:
        """
        API-Football Injuries endpoint

        GET https://v3.football.api-sports.io/injuries
        """
        pass

    async def _scrape_transfermarkt(self, team_name: str) -> dict:
        """
        Transfermarkt 크롤링 (백업)

        URL: https://www.transfermarkt.com/{team}/verletzungen/verein/{id}
        """
        pass
```

---

#### 3.1.5 실시간 배당률 수집 모듈 (`odds_collector.py`)

**목표**: 경기별 실시간 배당률 수집 및 변동 추적

**수집 데이터**:
```python
@dataclass
class MatchOdds:
    """경기 배당률"""
    match_id: str
    home_team: str
    away_team: str

    # 현재 배당률 (1X2)
    home_odds: float
    draw_odds: float
    away_odds: float

    # 내재 확률 (implied probability)
    home_prob: float
    draw_prob: float
    away_prob: float

    # 배당률 변동
    odds_history: List[OddsSnapshot]

    # 북메이커별 배당 (옵션)
    bookmaker_odds: Optional[Dict[str, dict]]

    # 오버마진 (북메이커 마진)
    overround: float

    updated_at: datetime

@dataclass
class OddsSnapshot:
    """배당률 스냅샷 (변동 추적용)"""
    timestamp: datetime
    home_odds: float
    draw_odds: float
    away_odds: float

@dataclass
class OddsMovement:
    """배당률 변동 분석"""
    direction: str  # 'home_drift', 'away_drift', 'stable'
    magnitude: float  # 변동 폭
    significance: str  # 'high', 'medium', 'low'
    interpretation: str  # "홈팀 배당 급등 - 스마트 머니 원정팀 지지"
```

**구현 상세**:
```python
# src/services/data/odds_collector.py

class OddsCollector:
    """배당률 수집기"""

    def __init__(self):
        self.odds_api = TheOddsAPI()
        self.zentoto_crawler = ZentotoCrawler()

    async def get_match_odds(
        self,
        home_team: str,
        away_team: str,
        match_date: str
    ) -> MatchOdds:
        """
        경기 배당률 조회

        1. The Odds API (해외 북메이커)
        2. 젠토토/베트맨 (국내)
        3. 내재 확률 계산
        """
        pass

    def _calculate_implied_probability(
        self,
        home: float,
        draw: float,
        away: float
    ) -> dict:
        """
        내재 확률 계산

        implied_prob = 1 / odds
        정규화하여 합계 = 1.0
        """
        raw_home = 1 / home
        raw_draw = 1 / draw
        raw_away = 1 / away
        total = raw_home + raw_draw + raw_away

        return {
            "home": raw_home / total,
            "draw": raw_draw / total,
            "away": raw_away / total,
            "overround": (total - 1) * 100  # 북메이커 마진 %
        }

    def _analyze_odds_movement(
        self,
        history: List[OddsSnapshot]
    ) -> OddsMovement:
        """
        배당률 변동 분석

        - 배당 상승 = 해당 결과에 대한 지지 감소
        - 배당 하락 = 해당 결과에 대한 지지 증가 (스마트 머니)
        """
        pass
```

---

### Phase 2: 데이터 통합 및 MatchContext 확장

#### 3.2.1 통합 데이터 서비스 (`match_enricher.py`)

**목표**: 모든 데이터 소스를 통합하여 풍부한 MatchContext 생성

**구현 상세**:
```python
# src/services/data/match_enricher.py

class MatchEnricher:
    """경기 데이터 통합 서비스"""

    def __init__(self):
        self.stats_collector = TeamStatsCollector()
        self.form_collector = FormCollector()
        self.h2h_collector = H2HCollector()
        self.injuries_collector = InjuriesCollector()
        self.odds_collector = OddsCollector()

    async def enrich_match(
        self,
        basic_context: MatchContext
    ) -> MatchContext:
        """
        기본 경기 정보에 실시간 데이터 추가

        1. 병렬로 모든 데이터 수집
        2. MatchContext에 통합
        3. 캐시 저장
        """
        # 병렬 데이터 수집
        home_stats, away_stats, home_form, away_form, h2h, home_injuries, away_injuries, odds = await asyncio.gather(
            self.stats_collector.get_team_stats(basic_context.home_team, basic_context.league),
            self.stats_collector.get_team_stats(basic_context.away_team, basic_context.league),
            self.form_collector.get_team_form(basic_context.home_team, basic_context.league),
            self.form_collector.get_team_form(basic_context.away_team, basic_context.league),
            self.h2h_collector.get_head_to_head(basic_context.home_team, basic_context.away_team),
            self.injuries_collector.get_team_injuries(basic_context.home_team),
            self.injuries_collector.get_team_injuries(basic_context.away_team),
            self.odds_collector.get_match_odds(basic_context.home_team, basic_context.away_team, basic_context.start_time),
            return_exceptions=True  # 일부 실패해도 계속 진행
        )

        # MatchContext 확장
        enriched = MatchContext(
            match_id=basic_context.match_id,
            home_team=basic_context.home_team,
            away_team=basic_context.away_team,
            league=basic_context.league,
            start_time=basic_context.start_time,
            sport_type=basic_context.sport_type,

            # 새로 추가된 데이터
            home_stats=self._to_dict(home_stats),
            away_stats=self._to_dict(away_stats),
            home_form=home_form.recent_results if home_form else None,
            away_form=away_form.recent_results if away_form else None,
            h2h_record=self._to_dict(h2h),
            injuries={
                "home": self._to_dict(home_injuries),
                "away": self._to_dict(away_injuries)
            },
            odds_home=odds.home_odds if odds else None,
            odds_draw=odds.draw_odds if odds else None,
            odds_away=odds.away_odds if odds else None,

            # 풍부한 컨텍스트 문자열
            enriched_context=self._build_enriched_context(
                home_stats, away_stats, home_form, away_form,
                h2h, home_injuries, away_injuries, odds
            )
        )

        return enriched

    def _build_enriched_context(self, ...) -> str:
        """AI에게 전달할 풍부한 컨텍스트 문자열 생성"""
        lines = []

        # 팀 통계 요약
        if home_stats and away_stats:
            lines.append("【팀 시즌 통계】")
            lines.append(f"홈팀: {home_stats.matches_played}경기 {home_stats.wins}승 {home_stats.draws}무 {home_stats.losses}패")
            lines.append(f"  - 평균 득점: {home_stats.goals_scored_avg:.2f}, 평균 실점: {home_stats.goals_conceded_avg:.2f}")
            lines.append(f"  - 리그 순위: {home_stats.league_position}위")
            # ... 원정팀도 동일

        # 최근 폼
        if home_form and away_form:
            lines.append("\n【최근 5경기 폼】")
            lines.append(f"홈팀: {' '.join(home_form.recent_results)} (승점 {home_form.form_points})")
            lines.append(f"원정팀: {' '.join(away_form.recent_results)} (승점 {away_form.form_points})")

        # 상대 전적
        if h2h:
            lines.append(f"\n【상대 전적 (최근 {h2h.total_matches}경기)】")
            lines.append(f"홈팀 {h2h.home_team_wins}승, 무승부 {h2h.draws}, 원정팀 {h2h.away_team_wins}승")

        # 부상자
        if home_injuries or away_injuries:
            lines.append("\n【부상자/출전정지】")
            if home_injuries and home_injuries.key_players_out > 0:
                lines.append(f"홈팀 주전 {home_injuries.key_players_out}명 결장")
            if away_injuries and away_injuries.key_players_out > 0:
                lines.append(f"원정팀 주전 {away_injuries.key_players_out}명 결장")

        # 배당률 분석
        if odds:
            lines.append(f"\n【배당률】")
            lines.append(f"홈승 {odds.home_odds:.2f} / 무 {odds.draw_odds:.2f} / 원정승 {odds.away_odds:.2f}")
            lines.append(f"내재 확률: 홈 {odds.home_prob*100:.1f}% / 무 {odds.draw_prob*100:.1f}% / 원정 {odds.away_prob*100:.1f}%")

        return "\n".join(lines)
```

---

#### 3.2.2 MatchContext 모델 확장

**변경 파일**: `src/services/ai/models.py`

```python
@dataclass
class MatchContext:
    """경기 분석을 위한 컨텍스트 정보 (확장)"""

    # === 기본 정보 (기존) ===
    match_id: int
    home_team: str
    away_team: str
    league: str
    start_time: str
    sport_type: SportType = SportType.SOCCER

    # === 팀 통계 (NEW) ===
    home_stats: Optional[Dict] = None
    away_stats: Optional[Dict] = None

    # === 최근 폼 (NEW) ===
    home_form: Optional[List[str]] = None  # ['W', 'W', 'D', 'L', 'W']
    away_form: Optional[List[str]] = None
    home_form_details: Optional[Dict] = None  # 폼 상세 지표
    away_form_details: Optional[Dict] = None

    # === 상대 전적 (NEW) ===
    h2h_record: Optional[Dict] = None
    h2h_recent_matches: Optional[List[Dict]] = None

    # === 부상자/출전정지 (NEW) ===
    injuries: Optional[Dict] = None  # {'home': [...], 'away': [...]}

    # === 배당률 (확장) ===
    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None
    odds_implied_prob: Optional[Dict] = None  # NEW: 내재 확률
    odds_movement: Optional[Dict] = None  # NEW: 배당 변동

    # === 기타 (기존) ===
    enriched_context: Optional[str] = None
    recent_news: Optional[str] = None

    # === 데이터 품질 지표 (NEW) ===
    data_completeness: Optional[float] = None  # 0.0 ~ 1.0
    data_freshness: Optional[datetime] = None

    def to_prompt_string(self) -> str:
        """프롬프트용 문자열 변환 (개선)"""
        # ... 기존 코드 + enriched_context 포함
        if self.enriched_context:
            return self.enriched_context
        # fallback: 기존 방식
```

---

### Phase 3: AI 프롬프트 개선

#### 3.3.1 시스템 프롬프트 개선

**변경 파일**: `src/services/ai/base_analyzer.py`

```python
def _get_soccer_system_prompt(self) -> str:
    """축구 승무패 시스템 프롬프트 (개선)"""
    return """당신은 스포츠토토 축구 승무패 14경기 분석 전문가입니다.

【분석 대상】
- 축구 승무패 14경기 (1X2 방식)
- 홈승(1), 무승부(X), 원정승(2) 중 선택

【데이터 기반 분석】 ⭐ NEW
제공되는 실시간 데이터를 기반으로 분석하세요:
1. 팀 시즌 통계 (승률, 득실점, 리그 순위)
2. 최근 5경기 폼 (W/D/L 패턴)
3. 상대 전적 (H2H 최근 기록)
4. 부상자/출전정지 (주전 결장 여부)
5. 배당률 및 내재 확률

【분석 가중치】
- 최근 폼 (30%): 최근 5경기 결과가 현재 컨디션 반영
- 홈/원정 경기력 (25%): 홈 어드밴티지 고려
- 상대 전적 (15%): 심리적 우위
- 부상자 영향 (15%): 주전 결장 시 전력 감소
- 배당률 분석 (15%): 시장 예측 참고

【이변 감지 포인트】 ⭐ 중요
다음 상황에서 이변 가능성 높음:
- 상위팀 원정 + 최근 폼 부진
- 하위팀 홈 + 상대 전적 우위
- 주전 대거 이탈
- 배당률이 실력 차이에 비해 낮음

【출력 형식】
{
    "winner": "Home" | "Draw" | "Away",
    "confidence": 0-100,
    "probabilities": {"home": 0.0-1.0, "draw": 0.0-1.0, "away": 0.0-1.0},
    "reasoning": "데이터 기반 핵심 분석 (한국어, 3-4문장)",
    "key_factor": "결정적 요인",
    "upset_risk": "low" | "medium" | "high"  // NEW: 이변 위험도
}"""
```

---

### Phase 4: 팀명 매칭 시스템 강화

#### 3.4.1 팀명 매핑 데이터베이스

**새 파일**: `src/services/data/team_mapping.py`

```python
# src/services/data/team_mapping.py

"""
팀명 매핑 데이터베이스

베트맨/젠토토 팀명 ↔ API 팀명 매핑
"""

SOCCER_TEAM_MAPPING = {
    # === 프리미어리그 ===
    "맨시티": {
        "aliases": ["맨체스터시티", "Manchester City", "Man City"],
        "api_football_id": 50,
        "football_data_id": 65,
    },
    "리버풀": {
        "aliases": ["Liverpool", "리버풀FC"],
        "api_football_id": 40,
        "football_data_id": 64,
    },
    "아스널": {
        "aliases": ["Arsenal", "아스날"],
        "api_football_id": 42,
        "football_data_id": 57,
    },
    # ... (전체 팀 매핑)

    # === 세리에A ===
    "코모1907": {
        "aliases": ["Como 1907", "Como", "코모"],
        "api_football_id": 867,
        "football_data_id": None,  # Football-Data.org에 없을 수 있음
    },
    "볼로냐": {
        "aliases": ["Bologna", "볼로냐FC"],
        "api_football_id": 500,
        "football_data_id": 103,
    },
    # ...

    # === 분데스리가 ===
    # ...

    # === 라리가 ===
    # ...
}

BASKETBALL_TEAM_MAPPING = {
    # === NBA ===
    "LA레이커스": {
        "aliases": ["Los Angeles Lakers", "Lakers", "레이커스"],
        "api_basketball_id": 145,
    },
    # ...

    # === KBL ===
    "울산모비스": {
        "aliases": ["울산현대모비스피버스", "울산 현대모비스", "Ulsan Mobis"],
        "kbl_id": "01",
    },
    # ...
}


class TeamMapper:
    """팀명 매퍼"""

    def __init__(self):
        self.soccer_mapping = SOCCER_TEAM_MAPPING
        self.basketball_mapping = BASKETBALL_TEAM_MAPPING

    def get_api_id(
        self,
        team_name: str,
        api: str = "api_football",
        sport: str = "soccer"
    ) -> Optional[int]:
        """팀명으로 API ID 조회"""
        mapping = self.soccer_mapping if sport == "soccer" else self.basketball_mapping

        # 정확한 매칭
        if team_name in mapping:
            return mapping[team_name].get(f"{api}_id")

        # 별칭 매칭
        for key, data in mapping.items():
            if team_name in data.get("aliases", []):
                return data.get(f"{api}_id")

        # Fuzzy 매칭 (최후 수단)
        return self._fuzzy_match(team_name, mapping, api)

    def _fuzzy_match(self, name: str, mapping: dict, api: str) -> Optional[int]:
        """퍼지 매칭"""
        from difflib import SequenceMatcher

        best_match = None
        best_ratio = 0.6  # 최소 60% 일치

        for key, data in mapping.items():
            # 키와 비교
            ratio = SequenceMatcher(None, name.lower(), key.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = data.get(f"{api}_id")

            # 별칭과 비교
            for alias in data.get("aliases", []):
                ratio = SequenceMatcher(None, name.lower(), alias.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = data.get(f"{api}_id")

        return best_match
```

---

### Phase 5: 캐싱 및 성능 최적화

#### 3.5.1 캐싱 전략

```python
# src/services/data/cache_manager.py

"""
캐싱 전략:
- 팀 통계: TTL 6시간 (시즌 중 일 1회 업데이트)
- 최근 폼: TTL 1시간 (경기 직후 변경)
- 상대 전적: TTL 24시간 (거의 변경 안됨)
- 부상자: TTL 2시간 (경기 당일 변경 가능)
- 배당률: TTL 5분 (실시간 변동)
"""

from enum import Enum

class CacheTTL(Enum):
    """캐시 TTL (초)"""
    TEAM_STATS = 6 * 3600      # 6시간
    RECENT_FORM = 3600          # 1시간
    HEAD_TO_HEAD = 24 * 3600   # 24시간
    INJURIES = 2 * 3600        # 2시간
    ODDS = 300                  # 5분
    MATCH_CONTEXT = 1800       # 30분 (통합 컨텍스트)


class CacheManager:
    """캐시 관리자"""

    def __init__(self, backend: str = "file"):
        """
        Args:
            backend: 'file', 'redis', 'memory'
        """
        self.backend = backend
        self.cache_dir = Path(".state/cache")

    async def get(self, key: str) -> Optional[dict]:
        """캐시 조회"""
        pass

    async def set(self, key: str, value: dict, ttl: int) -> None:
        """캐시 저장"""
        pass

    async def invalidate(self, pattern: str) -> None:
        """캐시 무효화 (패턴 매칭)"""
        pass
```

#### 3.5.2 API Rate Limiting

```python
# src/services/data/rate_limiter.py

"""
API Rate Limiting:
- Football-Data.org: 10 req/min (무료)
- API-Football: 100 req/day (무료)
- The Odds API: 500 req/month (무료)
"""

import asyncio
from collections import deque
from datetime import datetime, timedelta

class RateLimiter:
    """API Rate Limiter"""

    def __init__(self, max_requests: int, time_window: int):
        """
        Args:
            max_requests: 최대 요청 수
            time_window: 시간 윈도우 (초)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """요청 권한 획득 (필요시 대기)"""
        async with self.lock:
            now = datetime.now()

            # 오래된 요청 제거
            while self.requests and self.requests[0] < now - timedelta(seconds=self.time_window):
                self.requests.popleft()

            # Rate limit 체크
            if len(self.requests) >= self.max_requests:
                sleep_time = (self.requests[0] + timedelta(seconds=self.time_window) - now).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            self.requests.append(now)


# 글로벌 Rate Limiter 인스턴스
RATE_LIMITERS = {
    "football_data": RateLimiter(max_requests=10, time_window=60),
    "api_football": RateLimiter(max_requests=100, time_window=86400),
    "odds_api": RateLimiter(max_requests=500, time_window=2592000),
}
```

---

## 4. 파일 구조 (예상)

```
src/services/
├── data/                          # NEW: 데이터 수집 레이어
│   ├── __init__.py
│   ├── team_stats_collector.py    # 팀 통계 수집
│   ├── form_collector.py          # 최근 폼 수집
│   ├── h2h_collector.py           # 상대 전적 수집
│   ├── injuries_collector.py      # 부상자 정보 수집
│   ├── odds_collector.py          # 배당률 수집
│   ├── match_enricher.py          # 데이터 통합
│   ├── team_mapping.py            # 팀명 매핑 DB
│   ├── cache_manager.py           # 캐시 관리
│   └── rate_limiter.py            # API Rate Limiting
│
├── api_clients/                   # NEW: 외부 API 클라이언트
│   ├── __init__.py
│   ├── football_data_api.py       # Football-Data.org
│   ├── api_football.py            # API-Football
│   ├── api_basketball.py          # API-Basketball
│   ├── odds_api.py                # The Odds API
│   └── transfermarkt_scraper.py   # Transfermarkt 크롤러
│
├── ai/                            # 기존 (수정)
│   ├── models.py                  # MatchContext 확장
│   ├── base_analyzer.py           # 프롬프트 개선
│   └── ...
│
└── ...
```

---

## 5. 환경 변수 추가

```bash
# .env (추가)

# === 축구 데이터 API ===
FOOTBALL_DATA_API_KEY=your_key_here
API_FOOTBALL_KEY=your_key_here

# === 농구 데이터 API ===
API_BASKETBALL_KEY=your_key_here

# === 배당률 API ===
ODDS_API_KEY=your_key_here

# === 캐시 설정 ===
CACHE_BACKEND=file  # file, redis, memory
REDIS_URL=redis://localhost:6379/0  # Redis 사용 시

# === Rate Limiting ===
FOOTBALL_DATA_RATE_LIMIT=10  # per minute
API_FOOTBALL_RATE_LIMIT=100  # per day
```

---

## 6. 작업 우선순위

### 높음 (P0) - 핵심 기능
1. **팀 통계 수집** - 가장 중요한 데이터
2. **최근 폼 수집** - 현재 컨디션 반영
3. **팀명 매핑 DB** - 모든 수집의 기반

### 중간 (P1) - 중요 기능
4. **상대 전적 수집** - 심리적 우위 분석
5. **배당률 수집** - 시장 예측 참고
6. **MatchContext 확장** - 데이터 통합

### 낮음 (P2) - 부가 기능
7. **부상자 정보** - 정확한 로스터 파악
8. **캐싱 최적화** - 성능 개선
9. **AI 프롬프트 개선** - 분석 품질 향상

---

## 7. 리스크 및 대응

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| API Rate Limit | 데이터 수집 실패 | 캐싱 강화, 다중 API 백업 |
| 팀명 매칭 실패 | 데이터 연결 불가 | Fuzzy 매칭, 수동 매핑 보완 |
| API 유료 전환 | 비용 발생 | 무료 API 우선, 필수만 유료 |
| 데이터 지연 | 실시간성 저하 | TTL 조정, 우선순위 데이터만 |
| 리그 커버리지 | 일부 리그 미지원 | 크롤링 백업, 점진적 확장 |

---

## 8. 성공 지표 (KPI)

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| 예측 정확도 | ~55% | 65%+ | 적중률 추적 시스템 |
| 데이터 커버리지 | 0% | 90%+ | 수집 성공률 |
| 이변 감지율 | - | 70%+ | 복수 베팅 적중률 |
| API 응답 시간 | - | <3초 | 평균 latency |
| 캐시 히트율 | - | 80%+ | 캐시 통계 |

---

## 9. 참고 자료

### API 문서
- [Football-Data.org](https://www.football-data.org/documentation/quickstart)
- [API-Football](https://www.api-football.com/documentation-v3)
- [API-Basketball](https://www.api-basketball.com/documentation)
- [The Odds API](https://the-odds-api.com/liveapi/guides/v4/)

### 크롤링 대상
- [Transfermarkt](https://www.transfermarkt.com/) - 부상자 정보
- [젠토토](https://www.zentoto.com/) - 국내 배당률
- [베트맨](https://www.betman.co.kr/) - 국내 공식

---

**문서 버전**: 1.0.0
**최종 수정**: 2026-01-10
**작성자**: AI Assistant

> 이 계획서는 실시간 데이터 연동을 위한 상세 청사진입니다.
> 단계별로 구현하되, P0 항목부터 우선 착수하세요.
