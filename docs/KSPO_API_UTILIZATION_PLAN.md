# KSPO API 활용 개선 작업 계획서

> **작성일**: 2025-12-25
> **목적**: KSPO API의 실제 용도에 맞는 활용 방안 수립 및 구현 계획

---

## 1. 현황 분석

### 1.1 KSPO API의 실제 용도

```
✅ 적합한 용도:
- 경기 결과 아카이브 (match_end_val)
- 과거 경기 데이터 조회
- 팀별 역사적 통계 분석

❌ 부적합한 용도 (현재 시스템에서 시도 중):
- 발매 회차별 14경기 수집 (turn_no=NULL, row_num 불일치)
- 실시간 발매 정보 조회
```

### 1.2 현재 활용 현황

| 기능 | 코드 존재 | 실제 동작 | 상태 |
|------|----------|----------|------|
| 경기 결과 수집 | ✅ | ❌ | 미연동 |
| 적중률 추적 | ❌ | ❌ | 미구현 |
| AI 학습 데이터 | ❌ | ❌ | 미구현 |
| 팀 통계 계산 | ❌ | ❌ | 미구현 |

### 1.3 개선 필요 영역

```
1. 경기 결과 자동 수집 시스템
2. 예측 vs 실제 결과 비교 (적중률 추적)
3. 과거 데이터 기반 팀 통계 계산
4. AI 프롬프트에 실제 데이터 반영
```

---

## 2. 작업 목표

### 2.1 최종 목표

```
KSPO API를 "경기 결과 아카이브" 용도로 올바르게 활용하여:
1. 예측 적중률을 자동으로 추적
2. 과거 데이터 기반 팀 통계를 AI 분석에 활용
3. 시스템의 예측 정확도를 지속적으로 개선
```

### 2.2 성공 지표

| 지표 | 목표 |
|------|------|
| 적중률 자동 계산 | 매 회차 종료 후 24시간 내 |
| 팀 통계 데이터 | 최근 20경기 기반 |
| AI 프롬프트 반영 | 실제 통계 데이터 포함 |
| 텔레그램 알림 | 적중률 리포트 자동 발송 |

---

## 3. 작업 상세 계획

### 3.1 Phase 1: 경기 결과 수집 시스템 (우선순위: 높음)

#### 3.1.1 목표
- 경기 종료 후 KSPO API에서 결과(`match_end_val`) 자동 수집
- 예측 데이터와 매칭하여 적중 여부 판정

#### 3.1.2 구현 파일

```
src/services/
├── result_collector.py      # [신규] 경기 결과 수집기
├── prediction_tracker.py    # [신규] 예측 추적 및 적중률 계산
└── round_manager.py         # [수정] 결과 수집 연동
```

#### 3.1.3 데이터 구조

```python
# .state/predictions/ 디렉토리 구조
predictions/
├── soccer_wdl/
│   ├── round_152.json       # 152회차 예측 저장
│   ├── round_152_result.json # 152회차 결과 및 적중률
│   └── ...
└── basketball_w5l/
    └── ...

# round_152.json 구조
{
    "round_number": 152,
    "game_type": "soccer_wdl",
    "predicted_at": "2025-12-25T17:30:00",
    "deadline": "2025-12-27T00:00:00",
    "predictions": [
        {
            "game_number": 1,
            "home_team": "레스터C",
            "away_team": "왓포드",
            "predicted": "1",           # 예측 결과
            "confidence": 0.57,
            "probabilities": {"1": 0.57, "X": 0.25, "2": 0.18}
        },
        ...
    ]
}

# round_152_result.json 구조
{
    "round_number": 152,
    "collected_at": "2025-12-28T10:00:00",
    "results": [
        {
            "game_number": 1,
            "home_team": "레스터C",
            "away_team": "왓포드",
            "predicted": "1",
            "actual": "1",              # 실제 결과 (KSPO API에서)
            "score": "2:1",             # 실제 스코어
            "is_correct": true          # 적중 여부
        },
        ...
    ],
    "summary": {
        "total_games": 14,
        "correct_predictions": 10,
        "hit_rate": 0.714,              # 71.4%
        "single_hit": true,             # 단식 적중 여부
        "multi_combinations_hit": 3     # 복수 조합 중 적중 수
    }
}
```

#### 3.1.4 ResultCollector 클래스 설계

```python
# src/services/result_collector.py

class ResultCollector:
    """KSPO API를 활용한 경기 결과 수집기"""

    async def collect_round_results(
        self,
        round_number: int,
        game_type: str = "soccer_wdl"
    ) -> RoundResult:
        """
        특정 회차의 경기 결과 수집

        로직:
        1. 저장된 예측 데이터 로드 (predictions/round_XXX.json)
        2. 예측의 경기 날짜 추출
        3. KSPO API에서 해당 날짜 경기 결과 조회
        4. 팀명 매칭으로 결과 연결
        5. 적중 여부 계산
        """

    async def match_results_with_predictions(
        self,
        predictions: List[GamePrediction],
        api_results: List[Dict]
    ) -> List[GameResult]:
        """
        예측과 API 결과 매칭

        문제점 해결:
        - KSPO API의 row_num이 경기 번호가 아니므로 팀명으로 매칭
        - 팀명 정규화 필요 (레스터C ↔ 레스터시티)
        """

    def calculate_hit_rate(self, results: List[GameResult]) -> HitRateSummary:
        """적중률 계산"""
```

#### 3.1.5 팀명 매칭 로직

```python
# KSPO API 팀명 ↔ 베트맨 팀명 매칭 필요

TEAM_NAME_MAPPING = {
    # 베트맨(짧은) → KSPO API(정식)
    "레스터C": ["레스터시티", "레스터 시티"],
    "맨체스U": ["맨체스터유나이티드", "맨체스터 유나이티드"],
    "맨체스C": ["맨체스터시티", "맨체스터 시티"],
    "노팅엄포": ["노팅엄포리스트", "노팅엄 포리스트"],
    ...
}

def match_team_names(betman_name: str, kspo_name: str) -> bool:
    """팀명 매칭 (정규화 + 유사도)"""
    # 1. 정확히 일치
    # 2. 매핑 테이블 확인
    # 3. 유사도 80% 이상
```

#### 3.1.6 결과 수집 타이밍

```python
# 경기 결과 수집 스케줄

async def schedule_result_collection():
    """
    결과 수집 스케줄링

    로직:
    1. 저장된 예측 중 deadline이 지난 것 확인
    2. deadline + 24시간 후에 결과 수집 시도
    3. 모든 경기 결과가 있으면 적중률 계산
    4. 일부 누락 시 다음 날 재시도
    """
```

---

### 3.2 Phase 2: 적중률 추적 및 알림 시스템 (우선순위: 높음)

#### 3.2.1 목표
- 회차별 적중률 자동 계산 및 저장
- 누적 적중률 통계 관리
- 텔레그램으로 적중률 리포트 발송

#### 3.2.2 구현 파일

```
src/services/
├── prediction_tracker.py    # [신규] 예측 추적기
├── hit_rate_reporter.py     # [신규] 적중률 리포트 생성
└── telegram_notifier.py     # [수정] 적중률 알림 추가
```

#### 3.2.3 PredictionTracker 클래스 설계

```python
# src/services/prediction_tracker.py

class PredictionTracker:
    """예측 저장 및 추적"""

    async def save_prediction(
        self,
        round_info: RoundInfo,
        predictions: List[GamePrediction]
    ) -> str:
        """
        예측 결과 저장
        - auto_sports_notifier.py에서 분석 완료 후 호출
        - .state/predictions/{game_type}/round_{N}.json 저장
        """

    async def get_pending_rounds(self, game_type: str) -> List[int]:
        """
        결과 미수집 회차 목록 반환
        - deadline이 지났지만 result.json이 없는 회차
        """

    async def update_result(
        self,
        round_number: int,
        game_type: str,
        results: List[GameResult]
    ) -> HitRateSummary:
        """결과 업데이트 및 적중률 계산"""

    async def get_cumulative_stats(
        self,
        game_type: str,
        last_n_rounds: int = 10
    ) -> CumulativeStats:
        """
        누적 통계 조회
        - 최근 N회차 평균 적중률
        - 단식/복식 적중률 분리
        """
```

#### 3.2.4 적중률 리포트 형식

```
📊 *축구 승무패 152회차 적중률 리포트*
📅 2025-12-28 10:00

━━━━━━━━━━━━━━━━━━━━━━━━
📋 *경기별 결과*

01. 레스터C vs 왓포드
     예측: [1] → 실제: 1 (2:1) ✅

02. 노리치C vs 찰턴
     예측: [1/X] → 실제: X (1:1) ✅

03. 옥스퍼드 vs 사우샘프
     예측: [2] → 실제: 2 (0:2) ✅

...

14. 첼시 vs A빌라
     예측: [1] → 실제: X (1:1) ❌

━━━━━━━━━━━━━━━━━━━━━━━━
📈 *적중 통계*

• 단식 적중률: 71.4% (10/14)
• 복수 4경기 적중: 3/4 (75%)
• 16조합 중 적중: 4조합

━━━━━━━━━━━━━━━━━━━━━━━━
📊 *누적 통계 (최근 10회차)*

• 평균 단식 적중률: 68.5%
• 평균 복수 적중률: 72.3%
• 최고 적중률: 85.7% (148회차)
• 최저 적중률: 50.0% (145회차)
━━━━━━━━━━━━━━━━━━━━━━━━
```

#### 3.2.5 알림 스케줄

```python
# 적중률 알림 스케줄
RESULT_CHECK_SCHEDULE = {
    "soccer_wdl": {
        "check_after_hours": 24,      # deadline 후 24시간
        "retry_interval_hours": 6,    # 재시도 간격
        "max_retries": 5              # 최대 재시도
    },
    "basketball_w5l": {
        "check_after_hours": 12,
        "retry_interval_hours": 4,
        "max_retries": 5
    }
}
```

---

### 3.3 Phase 3: 팀 통계 계산 시스템 (우선순위: 중간)

#### 3.3.1 목표
- KSPO API 과거 데이터로 팀별 통계 계산
- 최근 N경기 폼, 홈/원정 성적 등 산출
- AI 분석에 실제 데이터 제공

#### 3.3.2 구현 파일

```
src/services/
├── team_stats_calculator.py  # [신규] 팀 통계 계산기
├── historical_data_loader.py # [신규] 과거 데이터 로더
└── ai_orchestrator.py        # [수정] 실제 통계 연동
```

#### 3.3.3 수집할 통계 항목

```python
@dataclass
class TeamStats:
    """팀 통계 데이터"""
    team_name: str

    # 최근 폼 (최근 5경기)
    recent_form: str              # "WWDLW"
    recent_points: int            # 최근 5경기 승점
    recent_goals_scored: float    # 최근 평균 득점
    recent_goals_conceded: float  # 최근 평균 실점

    # 홈/원정 성적 (최근 10경기)
    home_win_rate: float          # 홈 승률
    home_avg_goals: float         # 홈 평균 득점
    away_win_rate: float          # 원정 승률
    away_avg_goals: float         # 원정 평균 득점

    # 시즌 전체
    season_position: int          # 리그 순위 (가능하면)
    season_win_rate: float        # 시즌 승률

    # 메타 정보
    last_updated: datetime
    games_analyzed: int           # 분석한 경기 수
```

#### 3.3.4 TeamStatsCalculator 설계

```python
# src/services/team_stats_calculator.py

class TeamStatsCalculator:
    """KSPO API 과거 데이터 기반 팀 통계 계산"""

    def __init__(self):
        self.kspo_client = KSPOApiClient()
        self.cache_dir = Path(".state/team_stats")

    async def calculate_team_stats(
        self,
        team_name: str,
        sport: str = "축구",
        lookback_days: int = 90
    ) -> TeamStats:
        """
        팀 통계 계산

        로직:
        1. KSPO API에서 최근 N일 경기 조회
        2. 해당 팀이 참여한 경기 필터링
        3. 홈/원정 성적 분리 계산
        4. 최근 폼 계산
        """

    async def get_head_to_head(
        self,
        team1: str,
        team2: str,
        lookback_days: int = 365
    ) -> H2HStats:
        """상대 전적 조회"""

    async def refresh_all_stats(
        self,
        teams: List[str],
        sport: str = "축구"
    ) -> Dict[str, TeamStats]:
        """모든 팀 통계 일괄 갱신"""
```

#### 3.3.5 팀명 매칭 문제 해결

```python
# KSPO API 팀명이 불규칙하므로 정규화 필요

class TeamNameNormalizer:
    """팀명 정규화"""

    # 정규화 매핑 (다양한 표기 → 표준 표기)
    NORMALIZATION_MAP = {
        "레스터시티": "레스터시티",
        "레스터 시티": "레스터시티",
        "레스터C": "레스터시티",
        "Leicester": "레스터시티",
        ...
    }

    def normalize(self, team_name: str) -> str:
        """팀명 정규화"""

    def find_team_in_api_data(
        self,
        target_team: str,
        api_matches: List[Dict]
    ) -> List[Dict]:
        """API 데이터에서 해당 팀 경기 찾기"""
```

---

### 3.4 Phase 4: AI 프롬프트 실데이터 연동 (우선순위: 중간)

#### 3.4.1 목표
- AI 분석 시 실제 팀 통계 데이터 주입
- 하드코딩된 정보 대신 KSPO 데이터 활용

#### 3.4.2 수정 파일

```
src/services/
├── ai_orchestrator.py        # [수정] 통계 데이터 주입
└── ai/
    ├── gpt_analyzer.py       # [수정] 프롬프트 개선
    ├── claude_analyzer.py    # [수정] 프롬프트 개선
    └── ...
```

#### 3.4.3 개선된 AI 프롬프트 예시

```python
# 현재 (하드코딩)
prompt = f"""
{home_team} vs {away_team} 경기를 분석해주세요.
홈팀과 원정팀의 최근 폼, 상대 전적 등을 고려하여...
"""

# 개선 후 (실데이터)
prompt = f"""
{home_team} vs {away_team} 경기를 분석해주세요.

📊 실제 팀 데이터 (KSPO API 기준):

[{home_team}] 홈팀 통계:
- 최근 5경기 폼: {home_stats.recent_form} ({home_stats.recent_points}점)
- 홈 경기 승률: {home_stats.home_win_rate:.1%}
- 최근 평균 득점: {home_stats.recent_goals_scored:.1f}골
- 최근 평균 실점: {home_stats.recent_goals_conceded:.1f}골

[{away_team}] 원정팀 통계:
- 최근 5경기 폼: {away_stats.recent_form} ({away_stats.recent_points}점)
- 원정 경기 승률: {away_stats.away_win_rate:.1%}
- 최근 평균 득점: {away_stats.recent_goals_scored:.1f}골
- 최근 평균 실점: {away_stats.recent_goals_conceded:.1f}골

[상대 전적] (최근 1년):
- 총 {h2h.total_matches}경기: {h2h.home_wins}승 {h2h.draws}무 {h2h.away_wins}패
- 평균 득점: {h2h.avg_goals:.1f}골

위 실제 데이터를 바탕으로 승/무/패 확률을 분석해주세요.
"""
```

---

### 3.5 Phase 5: 자동화 및 스케줄링 (우선순위: 낮음)

#### 3.5.1 목표
- 모든 수집/계산 프로세스 자동화
- 스케줄러 통합

#### 3.5.2 스케줄 설계

```python
# 자동화 스케줄

SCHEDULES = {
    "prediction_save": {
        "trigger": "after_analysis",  # 분석 완료 직후
        "action": "save_prediction"
    },
    "result_collection": {
        "trigger": "cron",
        "schedule": "0 */6 * * *",    # 6시간마다
        "action": "collect_pending_results"
    },
    "team_stats_refresh": {
        "trigger": "cron",
        "schedule": "0 0 * * *",      # 매일 자정
        "action": "refresh_team_stats"
    },
    "hit_rate_report": {
        "trigger": "after_result_collection",
        "action": "send_hit_rate_report"
    }
}
```

---

## 4. 구현 우선순위 및 일정

### 4.1 Phase별 우선순위

| Phase | 내용 | 우선순위 | 예상 작업량 |
|-------|------|----------|------------|
| Phase 1 | 경기 결과 수집 | 🔴 높음 | 중간 |
| Phase 2 | 적중률 추적/알림 | 🔴 높음 | 중간 |
| Phase 3 | 팀 통계 계산 | 🟡 중간 | 높음 |
| Phase 4 | AI 프롬프트 연동 | 🟡 중간 | 낮음 |
| Phase 5 | 자동화/스케줄링 | 🟢 낮음 | 낮음 |

### 4.2 의존성 관계

```
Phase 1 (결과 수집)
    │
    ▼
Phase 2 (적중률 추적) ──────┐
    │                      │
    ▼                      ▼
Phase 3 (팀 통계) ──► Phase 4 (AI 연동)
    │
    ▼
Phase 5 (자동화)
```

### 4.3 권장 구현 순서

```
1단계: Phase 1 + Phase 2 (핵심 기능)
   - 예측 저장 → 결과 수집 → 적중률 계산 → 텔레그램 알림
   - 시스템의 가치를 즉시 확인 가능

2단계: Phase 3 (데이터 품질 개선)
   - 과거 데이터 기반 팀 통계
   - AI 분석 정확도 향상 기대

3단계: Phase 4 + Phase 5 (고도화)
   - AI 프롬프트 개선
   - 완전 자동화
```

---

## 5. 예상 문제점 및 해결 방안

### 5.1 팀명 매칭 문제

**문제**: KSPO API 팀명과 베트맨 팀명이 다름
```
베트맨: "레스터C"
KSPO API: "레스터시티"
```

**해결**:
1. 팀명 매핑 테이블 구축 (수동)
2. 유사도 기반 자동 매칭 (difflib)
3. 매칭 실패 시 수동 검토 큐

### 5.2 경기 식별 문제

**문제**: KSPO API에서 특정 경기를 정확히 찾기 어려움
```
같은 날 여러 리그 경기가 섞여 있음
row_num으로 식별 불가
```

**해결**:
1. 홈팀 + 원정팀 + 날짜로 복합 키 사용
2. 팀명 정규화 후 매칭
3. 매칭 신뢰도 점수 계산

### 5.3 데이터 지연 문제

**문제**: KSPO API에 경기 결과가 늦게 반영될 수 있음

**해결**:
1. deadline + 24시간 후 첫 시도
2. 실패 시 6시간 간격 재시도
3. 최대 5회 재시도 후 수동 처리 알림

### 5.4 API 응답 형식 변경

**문제**: KSPO API 응답 형식이 변경될 수 있음

**해결**:
1. 응답 파싱 로직 모듈화
2. 에러 로깅 및 알림
3. 파싱 실패 시 raw 데이터 저장

---

## 6. 테스트 계획

### 6.1 단위 테스트

```python
# tests/test_result_collector.py
class TestResultCollector:
    def test_match_team_names(self):
        """팀명 매칭 테스트"""

    def test_calculate_hit_rate(self):
        """적중률 계산 테스트"""

    def test_parse_match_end_val(self):
        """경기 결과 파싱 테스트"""
```

### 6.2 통합 테스트

```python
# tests/test_integration_kspo.py
class TestKSPOIntegration:
    async def test_full_flow(self):
        """
        전체 플로우 테스트:
        1. 예측 저장
        2. 결과 수집
        3. 적중률 계산
        4. 리포트 생성
        """
```

### 6.3 수동 테스트

```bash
# 과거 회차로 테스트
python3 -m scripts.test_result_collection --round 150

# 적중률 리포트 생성 테스트
python3 -m scripts.generate_hit_rate_report --round 150
```

---

## 7. 파일 구조 (최종)

```
src/services/
├── # 기존 파일
├── round_manager.py
├── betman_crawler.py
├── kspo_api_client.py
├── telegram_notifier.py
├── ai_orchestrator.py
│
├── # 신규 파일 (Phase 1-2)
├── result_collector.py          # 경기 결과 수집
├── prediction_tracker.py        # 예측 저장/추적
├── hit_rate_reporter.py         # 적중률 리포트
│
├── # 신규 파일 (Phase 3-4)
├── team_stats_calculator.py     # 팀 통계 계산
├── historical_data_loader.py    # 과거 데이터 로더
└── team_name_normalizer.py      # 팀명 정규화

.state/
├── # 기존
├── betman_soccer_wdl.json
├── betman_basketball_w5l.json
│
├── # 신규
├── predictions/                  # 예측 저장
│   ├── soccer_wdl/
│   │   ├── round_152.json
│   │   ├── round_152_result.json
│   │   └── ...
│   └── basketball_w5l/
│
├── team_stats/                   # 팀 통계 캐시
│   ├── soccer/
│   │   ├── 레스터시티.json
│   │   ├── 맨체스터유나이티드.json
│   │   └── ...
│   └── basketball/
│
└── hit_rate_history.json         # 적중률 이력
```

---

## 8. 결론

### 8.1 핵심 변화

```
Before: KSPO API로 14경기 수집 시도 (실패)
After:  KSPO API로 경기 결과/통계 수집 (올바른 용도)
```

### 8.2 기대 효과

1. **적중률 자동 추적**: 시스템 성능을 객관적으로 측정
2. **AI 정확도 향상**: 실제 데이터 기반 분석
3. **지속적 개선**: 적중률 데이터로 모델 튜닝 가능

### 8.3 다음 단계

```
이 계획서 승인 후:
1. Phase 1 구현 시작 (result_collector.py)
2. Phase 2 구현 (prediction_tracker.py)
3. 테스트 및 검증
4. Phase 3~5 순차 진행
```

---

**버전**: 1.0.0
**작성일**: 2025-12-25
**작성자**: AI Assistant

> 이 계획서는 KSPO API를 올바른 용도로 활용하기 위한 구체적인 구현 계획입니다.
> 작업 시작 전 검토 및 승인이 필요합니다.
