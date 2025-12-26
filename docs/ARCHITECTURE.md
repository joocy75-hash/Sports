# 시스템 아키텍처

## 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        auto_sports_notifier.py                          │
│                         (메인 실행 스크립트)                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
            │ RoundManager │ │AIOrchestrator│ │TelegramNotify│
            │ (데이터 수집) │ │ (AI 분석)    │ │ (알림 전송)  │
            └──────────────┘ └──────────────┘ └──────────────┘
                    │               │
        ┌───────────┴───────────┐   │
        │                       │   │
        ▼                       ▼   ▼
┌───────────────┐      ┌───────────────┐   ┌────────────────────────────┐
│ BetmanCrawler │      │  KSPO API     │   │        5개 AI 모델          │
│ (1순위)       │      │  (2순위)      │   ├────────────────────────────┤
│               │      │               │   │ GPT-4o    │ Claude Sonnet  │
│ Playwright    │      │ 공공데이터API  │   │ Gemini    │ DeepSeek V3    │
│ 14경기 정확   │      │ 12~14경기     │   │ Kimi K2   │                │
└───────────────┘      └───────────────┘   └────────────────────────────┘
```

---

## 데이터 흐름

### 1. 데이터 수집 흐름

```
사용자: python3 auto_sports_notifier.py --soccer
                    │
                    ▼
            ┌──────────────┐
            │ RoundManager │
            │  source=auto │
            └──────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       │
┌───────────────┐               │
│ BetmanCrawler │               │
│ (1순위 시도)  │               │
└───────────────┘               │
        │                       │
   성공? ├── YES ──► 14경기 반환 ──► AI 분석으로
        │
        └── NO
                │
                ▼
        ┌───────────────┐
        │  KSPO API     │
        │ (2순위 시도)  │
        └───────────────┘
                │
                └──► 12~14경기 반환 ──► AI 분석으로
```

### 2. AI 분석 흐름

```
14경기 데이터 입력
        │
        ▼
┌───────────────────────────────────────────────┐
│               AIOrchestrator                  │
│                                               │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│   │  GPT-4  │ │ Claude  │ │ Gemini  │        │
│   └────┬────┘ └────┬────┘ └────┬────┘        │
│        │           │           │              │
│   ┌────┴────┐ ┌────┴────┐                    │
│   │DeepSeek │ │  Kimi   │                    │
│   └────┬────┘ └────┬────┘                    │
│        │           │                          │
│        └─────┬─────┘                          │
│              │                                │
│              ▼                                │
│   ┌─────────────────────┐                    │
│   │   앙상블 합의 계산   │                    │
│   │   (가중 평균 투표)   │                    │
│   └─────────────────────┘                    │
│              │                                │
│              ▼                                │
│   ┌─────────────────────┐                    │
│   │   이변 감지 로직     │                    │
│   │   (4가지 신호 분석)  │                    │
│   └─────────────────────┘                    │
└───────────────────────────────────────────────┘
        │
        ▼
예측 결과 (14경기 + 복수 베팅 4경기)
        │
        ▼
┌───────────────────┐
│ TelegramNotifier  │
│ (메시지 포맷팅)   │
└───────────────────┘
        │
        ▼
텔레그램 전송
```

---

## 핵심 클래스 관계

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           RoundManager                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ + get_soccer_wdl_round(source, force_refresh)                           │
│ + get_basketball_w5l_round(source, force_refresh)                       │
│ - _fetch_from_crawler(game_type)                                        │
│ - _fetch_from_api(game_type)                                            │
│ - _convert_crawler_to_api_format(crawler_data)                          │
├─────────────────────────────────────────────────────────────────────────┤
│ 의존: BetmanCrawler, KSPOApiClient                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│        BetmanCrawler          │   │        KSPOApiClient          │
├───────────────────────────────┤   ├───────────────────────────────┤
│ + get_soccer_wdl_games()      │   │ + fetch_matches(date)         │
│ + get_basketball_w5l_games()  │   │ - _parse_response()           │
│ - _parse_game_list()          │   └───────────────────────────────┘
│ - _extract_via_javascript()   │
├───────────────────────────────┤
│ 의존: Playwright              │
└───────────────────────────────┘
```

---

## 데이터 모델

### RoundInfo (회차 정보)

```python
@dataclass
class RoundInfo:
    round_number: int       # 회차 번호 (예: 152)
    game_type: str          # "soccer_wdl" | "basketball_w5l"
    deadline: datetime      # 마감 시간
    match_date: str         # 경기 날짜 (예: "20251225")
    game_count: int         # 경기 수 (14)
    status: str             # "open" | "closed"
    updated_at: datetime    # 마지막 업데이트
```

### GameInfo (경기 정보)

```python
@dataclass
class GameInfo:
    game_number: int        # 경기 번호 (1~14)
    home_team: str          # 홈팀명
    away_team: str          # 원정팀명
    match_date: str         # 경기 날짜
    match_time: str         # 경기 시간 (HHMM)
    league: Optional[str]   # 리그명
```

### GamePrediction (예측 결과)

```python
@dataclass
class GamePrediction:
    game_number: int                # 경기 번호
    home_team: str                  # 홈팀명
    away_team: str                  # 원정팀명
    recommended: str                # "1" | "X" | "2"
    confidence: float               # 신뢰도 (0~1)
    is_multi: bool                  # 복수 베팅 여부
    multi_selections: List[str]     # 복수 선택 ["1", "X"]
    probabilities: Dict[str, float] # {"1": 0.5, "X": 0.3, "2": 0.2}
    upset_probability: float        # 이변 확률
```

---

## 캐시 구조

```
.state/
├── betman_soccer_wdl.json       # 베트맨 크롤러 캐시 (축구)
│   └── {round_info, games, updated_at, cache_ttl}
│
├── betman_basketball_w5l.json   # 베트맨 크롤러 캐시 (농구)
│   └── {round_info, games, updated_at, cache_ttl}
│
├── soccer_wdl_round.json        # KSPO API 캐시 (축구)
│   └── {round_info, games}
│
├── basketball_w5l_round.json    # KSPO API 캐시 (농구)
│   └── {round_info, games}
│
├── last_notified_rounds.json    # 마지막 알림 회차
│   └── {soccer_wdl: 152, basketball_w5l: 217}
│
└── validation_reports/          # 검증 보고서
    └── soccer_wdl_20251225_*.md
```

### 캐시 TTL (Time-To-Live)

| 캐시 | TTL | 설명 |
|------|-----|------|
| 베트맨 크롤러 | 5분 | 자주 변경되지 않음 |
| KSPO API | 30분 | API 응답 속도 빠름 |
| 알림 회차 | 무제한 | 중복 알림 방지 |

---

## 환경 변수

```bash
# 필수
TELEGRAM_BOT_TOKEN=...     # 텔레그램 봇 토큰
TELEGRAM_CHAT_ID=...       # 텔레그램 채팅 ID

# AI API 키 (최소 1개)
OPENAI_API_KEY=...         # GPT-4
ANTHROPIC_API_KEY=...      # Claude
GOOGLE_API_KEY=...         # Gemini
DEEPSEEK_API_KEY=...       # DeepSeek
KIMI_API_KEY=...           # Kimi (Moonshot AI)

# 선택
KSPO_TODZ_API_KEY=...      # KSPO API (fallback용)
DATABASE_URL=...           # PostgreSQL (레거시)
```

---

## 에러 처리

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           에러 처리 계층                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. 데이터 수집 레벨                                                     │
│     ├── 크롤러 실패 → API fallback                                       │
│     ├── API 실패 → 캐시 데이터 사용                                       │
│     └── 캐시 없음 → 에러 로그 + 알림 스킵                                  │
│                                                                         │
│  2. AI 분석 레벨                                                         │
│     ├── 개별 AI 실패 → 해당 AI 제외하고 합의                              │
│     ├── 모든 AI 실패 → 기본 확률 (33%/33%/33%) 사용                       │
│     └── 타임아웃 → 60초 후 강제 종료                                      │
│                                                                         │
│  3. 알림 레벨                                                            │
│     ├── 텔레그램 전송 실패 → 3회 재시도                                   │
│     └── 최종 실패 → 로컬 파일 저장                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

**버전**: 3.0.0
**최종 업데이트**: 2025-12-25
