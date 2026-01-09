# CLAUDE.md - 프로토 14경기 AI 분석 시스템 가이드

> **이 파일은 AI 작업자를 위한 프로젝트 핵심 가이드입니다.**
> 새로운 작업자가 와도 이 파일을 읽으면 프로젝트 방향성과 핵심 로직을 이해할 수 있습니다.

---

## ⚠️ 절대 원칙 (AI 작업자 필독!)

### 🚨 개발/배포 워크플로우
```
로컬 개발 (Mac) → Git Push → GitHub Actions CI/CD → 원격 서버 자동 배포
```

**절대 금지:**
- ❌ 원격 서버에서 직접 코드 수정
- ❌ 로컬 환경 우회한 직접 배포
- ❌ GitHub Actions 없이 수동 배포

**필수 준수:**
- ✅ 모든 코드 수정은 로컬에서만
- ✅ Git commit/push로만 배포
- ✅ GitHub Actions가 자동 배포 처리

### 🎯 프로젝트의 진짜 목적

**이 시스템은 "확률 예측"이 아니라 "이변 감지"가 핵심입니다!**

```
일반 배팅: 승률 높은 경기 찾기 (70% 확률 경기)
프로토 14경기: 이변 가능한 경기 찾기 (불확실한 경기)
```

**왜?**
- 14경기를 **모두 맞춰야** 당첨 (ALL or NOTHING)
- 13개 맞추고 1개 틀리면 **전액 손실**
- **1개 이변 경기** 때문에 전체가 실패 → **이변 감지가 생명줄**
- 확률 높은 경기는 누구나 맞춤 → **차별화는 이변 경기 회피**

**핵심 전략:**
```
고신뢰 경기 10개 → 단일 베팅 (확신)
이변 가능 경기 4개 → 복수 베팅 (안전장치)
```

---

## 1. 프로젝트 핵심 목적

### 왜 이 시스템을 만들었는가?

**기존 문제점:**
- 배당률은 북메이커가 이미 계산한 확률 → 편향 가능성
- 배당 기반 분석은 "누군가가 정해놓은 확률"에 의존
- **배당만 보면 이변을 감지하지 못함** ⚠️

**우리의 해결책:**
- **AI가 순수 데이터(팀 통계, 폼, 전적)만으로 독립적으로 확률 계산**
- **배당 없이 자체 확률 산출** → 더 정확한 예측 가능
- **5개 AI 앙상블**(GPT-4, Claude, Gemini, Kimi, DeepSeek)로 합의된 결과 도출
- **AI 간 불일치 = 이변 신호** → 가장 중요한 지표!

### 프로토 14경기 시스템 특성

```
⚠️ 핵심: ALL or NOTHING - 14경기를 모두 맞춰야 당첨
```

- 13개 맞추고 1개 틀리면 **전액 손실**
- 따라서 **이변 감지가 핵심** (불확실한 경기 찾기)
- 축구 승무패는 **복수 베팅 가능** (경기당 여러 결과 선택)

### 경기 일정 (중요!)
```
축구 승무패: 매주 토요일 1회 (가끔 주 2회)
농구 승5패: 매주 토요일 1회 (가끔 주 2회)
경기 수: 반드시 14경기 고정 ⚠️
```

**⚠️ 14경기 미만 수집은 치명적 오류!**
- 13경기 이하로 수집되면 시스템 전체 무용지물
- 베트맨 크롤러 실패 시 즉시 알림 필요
- KSPO API는 14경기 보장 안함 (fallback만 사용)

---

## 2. 지원 게임 타입

| 게임 | 경기 수 | 결과 옵션 | 특징 |
|------|---------|----------|------|
| **축구 승무패** | 14경기 | 승/무/패 | 복수 베팅 가능 |
| **농구 승5패** | 14경기 | 승/5/패 | 점수차 5점 기준 |
| **프로토 승부식** | 가변 | 승/무/패 | 다양한 종목 |

### 농구 승5패 규칙 (중요!)
```
승(W): 홈팀이 6점 이상 차이로 승리  (예: 100-90 → 승)
5:    점수 차이가 5점 이내           (예: 100-97 → 5)
패(L): 원정팀이 6점 이상 차이로 승리 (예: 90-100 → 패)
```

---

## 3. 핵심 분석 로직

### 3.1 AI 확률 계산 (배당 없이!)

```python
# 잘못된 방식 (배당 의존)
implied_prob = 1 / odds  # ❌ 북메이커가 정한 확률

# 올바른 방식 (순수 데이터 기반)
ai_prob = calculate_from_stats(
    team_stats,      # 팀 통계 (공격/수비 레이팅)
    recent_form,     # 최근 폼 (5경기)
    head_to_head,    # 상대 전적
    home_advantage,  # 홈 어드밴티지
    injuries         # 부상자 정보
)  # ✅ AI가 직접 계산
```

### 3.2 이변 감지 로직 ⚠️ (최우선 과제!)

**⚡ 이변 감지가 시스템의 핵심입니다!**

이 시스템의 가치는 **"70% 확률 경기를 맞추는 것"**이 아니라,
**"불확실한 경기를 찾아서 복수 베팅으로 대비하는 것"**입니다.

#### 이변 신호 4가지

```python
# 이변 점수 계산 (auto_sports_notifier.py의 _select_multi_games 로직)
upset_score = 0

# 신호 1: 확률 분포가 애매함 (가장 중요!) ⭐⭐⭐
prob_gap = sorted_probs[0] - sorted_probs[1]  # 1위와 2위 차이
if prob_gap < 0.10:    upset_score += 50  # 매우 애매함
elif prob_gap < 0.15:  upset_score += 40
elif prob_gap < 0.20:  upset_score += 30
elif prob_gap < 0.25:  upset_score += 20
elif prob_gap < 0.30:  upset_score += 10

# 신호 2: 신뢰도가 낮음 (AI도 확신 못함) ⭐⭐
if confidence < 0.40:  upset_score += 40
elif confidence < 0.45: upset_score += 30
elif confidence < 0.50: upset_score += 20
elif confidence < 0.55: upset_score += 10

# 신호 3: AI 모델 간 불일치 ⭐⭐⭐
# AI 5개가 의견 다르면 = 예측 어려운 경기 = 이변 가능
if ai_agreement < 0.40:  upset_score += 35
elif ai_agreement < 0.50: upset_score += 25
elif ai_agreement < 0.60: upset_score += 15
elif ai_agreement < 0.70: upset_score += 5

# 신호 4: 무승부/접전 확률 높음
if prob_draw >= 0.30:  upset_score += 25
elif prob_draw >= 0.25: upset_score += 15
elif prob_draw >= 0.20: upset_score += 5

# upset_score가 높을수록 이변 가능성 높음
# 상위 4경기를 복수 베팅으로 선정
```

#### 왜 이변 감지가 중요한가?

```
예시 1: 이변 감지 없이 단일 베팅만 한 경우
14경기 중 13경기 맞춤 + 1경기 이변으로 실패
→ 결과: 전액 손실 (0원)

예시 2: 이변 감지로 4경기 복수 베팅
14경기 중 13경기 맞춤 + 1경기 이변이지만 복수에 포함
→ 결과: 당첨 (16조합 중 1조합)
```

**⚠️ AI 작업자 주의사항:**
- 이변 감지 로직을 절대 약화시키지 말 것
- AI 간 불일치를 "오류"가 아닌 "이변 신호"로 해석
- 복수 베팅 4경기는 반드시 유지 (3경기도, 5경기도 안됨)
- upset_score 계산 로직은 신중하게 수정

### 3.3 복수 베팅 전략 (축구 승무패)

```
전략: 14경기 중 이변 가능성 높은 4경기를 복수 베팅
- 고신뢰 경기 10개 → 단일 베팅 (확신 있는 경기)
- 이변 가능 경기 4개 → 복수 베팅 (안전장치)
- 총 조합: 2^4 = 16조합

목표:
- 확률 높은 10경기는 당연히 맞춤 (누구나 맞춤)
- 애매한 4경기는 복수로 커버 → 이변 대비 ✅
```

**복수 베팅 예시:**
```
02번 노리치C vs 찰턴 → 1/X (홈승 또는 무승부)
05번 스토크C vs 프레스턴 → X/1 (무승부 또는 홈승)
12번 번리 vs 에버턴 → 2/1 (원정승 또는 홈승)
13번 웨스트햄 vs 풀럼 → 1/X (홈승 또는 무승부)
```

이렇게 하면:
- 4개 중 1개라도 이변 발생 → 복수에서 커버됨
- 전체 14경기 적중 가능성 대폭 상승

---

## 4. 텔레그램 알림 형식

### 축구 승무패 예시
```
⚽ *축구토토 승무패 152회차*
📅 2025-12-25 17:24
━━━━━━━━━━━━━━━━━━━━━━━━

📋 *14경기 전체 예측*

01. 레스터C vs 왓포드
     🔒 [1] (57%)

02. 노리치C vs 찰턴 [복수]
     ⚠️ *[1/X]* (56%)

...

━━━━━━━━━━━━━━━━━━━━━━━━
📝 *단식 정답*
`1:1 2:1 3:2 4:1 5:X 6:1 7:2`
`8:1 9:2 10:1 11:1 12:2 13:1 14:1`

━━━━━━━━━━━━━━━━━━━━━━━━
🎰 *복수 4경기* (총 16조합)
02번 노리치C vs 찰턴 → 1,X
05번 스토크C vs 프레스턴 → X,1
12번 번리 vs 에버턴 → 2,1
13번 웨스트햄 vs 풀럼 → 1,X
━━━━━━━━━━━━━━━━━━━━━━━━
```

### 농구 승5패 예시
```
🏀 *농구토토 승5패 47회차*
📅 2025-12-27 09:00
━━━━━━━━━━━━━━━━━━━━━━━━

📋 *14경기 전체 예측*

01. 울산현대모비스 vs 수원KT소닉붐
     🔒 [승] (52%)

08. 미네소타팀버울 vs 뉴욕닉스
     ⚠️ [5/패] (40%/30%)

...

━━━━━━━━━━━━━━━━━━━━━━━━
📝 *단식 정답*
`1:승 2:승 3:5 4:승 5:승 6:승 7:승`
`8:5 9:승 10:승 11:승 12:승 13:패 14:승`
━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 5. 핵심 파일 구조 (⭐ 2026-01-10 업데이트 - v3.3.0)

```
스포츠분석/
│
├── 📄 메인 실행 파일
│   ├── auto_sports_notifier.py      # ⭐ 통합 자동화 (축구+농구, AI분석, 텔레그램)
│   ├── basketball_w5l_notifier.py   # 농구 승5패 전용 (레거시)
│   ├── basketball_w5l_analyzer.py   # 농구 승5패 확률 계산 엔진
│   ├── collect_and_notify.py        # 통합 데이터 수집 (레거시, DB 사용)
│   └── test_zentoto_crawler.py      # ⭐ [v3.3.0] 젠토토 크롤러 테스트
│
├── 📂 src/services/                  # ⭐ 핵심 서비스 모듈
│   ├── round_manager.py             # ⭐ 회차 관리 + 3단계 데이터 소스 (핵심!)
│   ├── zentoto_crawler.py           # ⭐ [v3.3.0] 젠토토 크롤러 (1순위!)
│   ├── betman_crawler.py            # 베트맨 웹 크롤러 (2순위)
│   ├── data_validator.py            # 데이터 검증 시스템
│   ├── telegram_notifier.py         # 텔레그램 메시지 전송
│   ├── kspo_api_client.py           # KSPO API 클라이언트 (3순위 fallback)
│   ├── ai_orchestrator.py           # 5개 AI 앙상블 관리
│   └── 📂 ai/                        # 각 AI 분석기
│       ├── gpt_analyzer.py
│       ├── claude_analyzer.py
│       ├── gemini_analyzer.py
│       ├── deepseek_analyzer.py
│       └── kimi_analyzer.py
│
├── 📂 .state/                        # 상태 저장 디렉토리
│   ├── zentoto_soccer_wdl.json      # ⭐ [v3.3.0] 젠토토 캐시 (축구)
│   ├── zentoto_basketball_w5l.json  # ⭐ [v3.3.0] 젠토토 캐시 (농구)
│   ├── soccer_wdl_next_round.json   # ⭐ [v3.3.0] 다음 회차 미리 확보 캐시
│   ├── basketball_w5l_next_round.json # ⭐ [v3.3.0] 다음 회차 미리 확보 캐시
│   ├── betman_soccer_wdl.json       # 베트맨 크롤러 캐시 (축구)
│   ├── betman_basketball_w5l.json   # 베트맨 크롤러 캐시 (농구)
│   ├── soccer_wdl_round.json        # API 캐시 (축구) - fallback용
│   ├── basketball_w5l_round.json    # API 캐시 (농구) - fallback용
│   ├── last_notified_rounds.json    # 마지막 알림 회차
│   └── 📂 validation_reports/        # 검증 보고서
│
├── 📂 docs/                          # ⭐ [NEW] 문서
│   └── DATA_VALIDATION.md           # 데이터 검증 가이드
│
├── 📄 테스트 스크립트
│   ├── test_data_validation.py      # ⭐ [NEW] 데이터 검증 테스트
│   └── test_round_manager_integration.py  # ⭐ [NEW] 통합 테스트
│
└── 📄 설정
    ├── .env                          # API 키 (비공개)
    └── CLAUDE.md                     # 이 문서 (AI 작업자 가이드)
```

---

## 6. 데이터 수집 아키텍처 (⚠️ 매우 중요! - 2026-01-10 v3.3.0 업데이트)

### 6.1 3단계 데이터 수집 시스템 (v3.3.0 변경!)

```
⚠️ v3.3.0 핵심 변경: 젠토토 크롤러가 1순위로 추가됨!
젠토토는 발매 전에 다음 회차를 미리 등록하므로, 가장 먼저 시도합니다.
```

```
┌─────────────────────────────────────────────────────────────┐
│                    RoundManager                              │
│              (3단계 데이터 소스 통합 관리)                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   1순위: 젠토토 크롤러 (ZentotoCrawler) ⭐ NEW v3.3.0        │
│   ├── ✅ 정확한 14경기 수집 보장                              │
│   ├── ✅ 다음 회차 미리 확보 가능! (핵심 장점)                 │
│   ├── ✅ 발매 마감 후에도 데이터 유지                          │
│   └── ⚠️ Playwright 필요 (브라우저 자동화)                   │
│                                                              │
│   2순위: 베트맨 크롤러 (BetmanCrawler)                        │
│   ├── ✅ 정확한 14경기 수집 보장                              │
│   ├── ✅ 공식 발매 사이트 (정확도 최고)                        │
│   ├── ⚠️ 한국 IP에서만 접근 가능 (Geo-blocking)              │
│   └── ⚠️ 발매 마감 후 데이터 사라짐                          │
│                                                              │
│   3순위: KSPO API (Fallback)                                 │
│   ├── ⚠️ 경기 누락 가능 (12~14경기)                          │
│   ├── ⚠️ row_num 불일치 문제                                 │
│   ├── ⚠️ turn_no가 NULL인 경우 많음                          │
│   └── ✅ 빠른 응답 속도                                       │
│                                                              │
│   4순위: 캐시 데이터 (최후 수단)                               │
│   └── 모든 소스 실패 시 최근 캐시 사용                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 데이터 소스별 비교 (v3.3.0 업데이트)

| 항목 | 젠토토 크롤러 ⭐ | 베트맨 크롤러 | KSPO API |
|------|-----------------|--------------|----------|
| **경기 수** | 14경기 (100%) | 14경기 (100%) | 12~14경기 (불안정) |
| **회차 번호** | 정확 | 정확 | 종종 NULL |
| **다음 회차** | ✅ 미리 확보 가능 | ❌ 불가 | ❌ 불가 |
| **발매 마감 후** | ✅ 데이터 유지 | ❌ 사라짐 | ✅ 유지 |
| **Geo-blocking** | 확인 필요 | 한국 IP만 | 없음 |
| **속도** | ~8초 | ~8초 | ~2초 |
| **의존성** | Playwright | Playwright | HTTP 요청만 |

### 6.3 RoundManager 사용법

```python
from src.services.round_manager import RoundManager

manager = RoundManager()

# 1. 자동 모드 (권장) - 크롤러 우선, 실패 시 API
info, games = await manager.get_soccer_wdl_round()
# 결과: 152회차, 14경기

# 2. 크롤러 전용 모드
info, games = await manager.get_soccer_wdl_round(source="crawler")

# 3. API 전용 모드 (빠르지만 부정확할 수 있음)
info, games = await manager.get_soccer_wdl_round(source="api")

# 4. 강제 새로고침
info, games = await manager.get_soccer_wdl_round(force_refresh=True)
```

### 6.4 KSPO API의 근본적 한계 (⚠️ 중요!)

```
🚨 핵심 문제: KSPO API는 "발매 회차별 14경기"를 위한 API가 아닙니다!

이 API는 경기 결과 아카이브 용도로 설계되었으며,
베트맨 발매 시스템과 완전히 다른 목적의 API입니다.
```

**베트맨 vs KSPO API 비교:**

| 항목 | 베트맨 웹사이트 | KSPO API |
|------|---------------|----------|
| 목적 | 실시간 발매 정보 | 경기 아카이브 |
| 회차 번호 | 정확 (152회차) | **모두 NULL** |
| 경기 번호 | 1~14 순서 보장 | **DB 시퀀스 (405, 406...)** |
| 경기 수 | 정확히 14경기 | **불규칙 (12~19경기)** |

**실제 API 응답 분석 (2025-12-25):**

```
12/27 축구 토토/프로토:
- 경기 수: 12경기 (14경기가 아님!)
- turn_no: 모두 NULL
- row_nums: [405, 406, 408, 409, 410...] ← DB 인덱스!

12/28 축구 토토/프로토:
- 경기 수: 7경기
- turn_no: 모두 NULL
- row_nums: [442, 443, 444, 445...]
```

**왜 이런 차이가 발생하는가?**

```
베트맨 내부 시스템:
  [회차 관리 DB] → [발매 시스템] → [웹사이트]
        │
        │ 회차별 14경기 정보 (정확)
        │
        ▼
  [공공데이터 연동 모듈]
        │
        │ ⚠️ 회차 정보가 연동되지 않음!
        │    - turn_no = NULL로 전송
        │    - row_num = DB 시퀀스로 변환
        ▼
  [KSPO API] → 회차 없이 경기 데이터만 제공
```

> 📖 상세 분석: [docs/KSPO_API_LIMITATIONS.md](docs/KSPO_API_LIMITATIONS.md)

### 6.5 베트맨 크롤러 구현 세부사항

**파일 위치**: `src/services/betman_crawler.py`

```python
# 핵심 구조
class BetmanCrawler:
    """Playwright 기반 베트맨 웹사이트 크롤러"""

    async def get_soccer_wdl_games(self) -> Tuple[RoundInfo, List[GameInfo]]:
        """
        축구 승무패 14경기 크롤링

        Returns:
            RoundInfo: 회차 정보 (round_number, deadline 등)
            List[GameInfo]: 14경기 정보 리스트
        """

    async def get_basketball_w5l_games(self) -> Tuple[RoundInfo, List[GameInfo]]:
        """농구 승5패 14경기 크롤링"""
```

**크롤링 대상 URL**:
```
https://www.betman.co.kr/main/mainPage/gamebuy/buyableGameList.do
```

**크롤링 방식**:
1. Playwright로 페이지 로드
2. 축구/농구 탭 클릭
3. JavaScript로 DOM에서 경기 정보 추출
4. 정규표현식으로 "홈팀vs원정팀" 파싱

### 6.6 데이터 검증 시스템

**파일 위치**: `src/services/data_validator.py`

```python
from src.services.data_validator import DataValidator

validator = DataValidator()

# 크롤러 vs API 데이터 비교
result = await validator.compare_sources("soccer_wdl")
print(f"일치율: {result.match_rate * 100:.1f}%")
print(f"불일치 항목: {len(result.mismatches)}개")

# 마크다운 보고서 생성
report = await validator.generate_report("soccer_wdl")
```

**검증 항목**:
- 경기 수 일치 여부
- 팀명 일치 여부 (정규화 적용)
- 경기 순서 일치 여부
- 날짜/시간 일치 여부

---

## 7. 실행 명령어

### 통합 자동화 스크립트 (권장)
```bash
# ⭐ 전체 분석 (축구 + 농구) - 텔레그램 전송
python3 auto_sports_notifier.py

# 축구 승무패만 분석
python3 auto_sports_notifier.py --soccer

# 농구 승5패만 분석
python3 auto_sports_notifier.py --basketball

# 테스트 모드 (전송 안함, 콘솔 출력만)
python3 auto_sports_notifier.py --test
python3 auto_sports_notifier.py --soccer --test
python3 auto_sports_notifier.py --basketball --test

# 스케줄러 모드 (6시간마다 자동 체크)
python3 auto_sports_notifier.py --schedule
python3 auto_sports_notifier.py --schedule --interval 4  # 4시간 간격
```

### 데이터 검증
```bash
# 축구 승무패 데이터 검증
python3 test_data_validation.py --soccer

# 농구 승5패 데이터 검증
python3 test_data_validation.py --basketball

# 검증 보고서 저장
python3 test_data_validation.py --soccer --save-report
```

### 기존 스크립트 (레거시)
```bash
# 농구 승5패 분석 (기존)
python3 basketball_w5l_notifier.py --test

# 전체 수집 + 알림 (기존 - DB 사용)
python3 collect_and_notify.py --soccer
```

### 백엔드 서버
```bash
# 가상환경 활성화
source deepseek_env/bin/activate

# 서버 실행
python -m uvicorn src.api.unified_server:app --reload --port 8000

# 프론트엔드 (새 터미널)
cd frontend && npm run dev
```

---

## 8. 환경 변수 (.env)

```bash
# 데이터베이스
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost/sports_analysis

# AI API 키 (최소 1개 필수)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
DEEPSEEK_API_KEY=...
KIMI_API_KEY=...  # Moonshot AI

# 텔레그램 (필수)
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_CHAT_ID=987654321

# KSPO (베트맨) API - fallback용
KSPO_TODZ_API_KEY=...
KSPO_TODZ_API_BASE_URL=https://apis.data.go.kr/B551014/SRVC_OD_API_TB_SOSFO_MATCH_MGMT
```

### 필수 패키지 설치
```bash
# Playwright 설치 (베트맨 크롤러용)
pip install playwright
playwright install chromium

# 기타 필수 패키지
pip install aiohttp python-dotenv
```

---

## 9. 절대 하지 말아야 할 것 ⚠️

### ❌ 잘못된 접근
1. **배당률 기반 확률 계산** - 북메이커 확률에 의존하면 안됨
2. **단순 승률 비교** - 홈팀 승률 > 원정팀 승률 = 홈승 (너무 단순)
3. **14경기 미만 수집** ⚠️ 치명적! - 반드시 14경기 전체 필요
4. **복수 베팅 미고려** - 이변 경기 4개는 반드시 복수 베팅 권장
5. **KSPO API만 사용** - 경기 누락 가능, 반드시 크롤러 우선 사용
6. **원격 서버에서 직접 코드 수정** ⚠️ - 반드시 로컬 → Git → CI/CD
7. **이변 감지 로직 약화** - 시스템의 핵심 가치를 훼손함

### ✅ 올바른 접근
1. **순수 데이터 기반 AI 확률 계산**
2. **5개 AI 앙상블 합의**
3. **이변 감지 로직 적용** ⭐ 최우선
4. **14경기 전체 마킹 리스트 + 복수 4경기**
5. **베트맨 크롤러로 정확한 14경기 수집** ⭐ 필수
6. **로컬 개발 → Git Push → GitHub Actions 배포**
7. **AI 불일치를 이변 신호로 해석**

---

## 9-1. 14경기 수집의 중요성 (치명적!)

**⚠️ 가장 중요한 규칙: 반드시 14경기를 수집해야 함!**

### 왜 14경기가 필수인가?

프로토 시스템은 **정확히 14경기 결과를 모두 맞춰야 당첨**입니다.
- 13경기만 있으면 → 베팅 불가능
- 15경기가 있으면 → 잘못된 데이터
- **정확히 14경기만 유효**

### 데이터 소스 우선순위

```
1순위: 베트맨 크롤러 (BetmanCrawler)
  ✅ 14경기 100% 보장
  ✅ 정확한 회차 번호
  ✅ 베트맨 웹사이트와 100% 일치
  ⚠️ Playwright 필요 (느림: ~8초)

2순위: KSPO API (Fallback만)
  ⚠️ 경기 누락 가능 (8~11경기)
  ⚠️ row_num 불일치
  ⚠️ turn_no가 NULL인 경우 많음
  ✅ 빠른 응답 (2초)

3순위: 캐시 데이터
  ⚠️ 5분 이내만 유효
  ⚠️ 오래된 데이터 위험
```

### 크롤러 실패 시 대응

```python
# round_manager.py의 로직
try:
    # 1순위: 크롤러 시도
    info, games = await crawler.get_soccer_wdl_games()
    if len(games) == 14:  # ✅ 성공
        return info, games
    else:
        logger.error(f"크롤러: {len(games)}경기 (14 필요)")
        raise ValueError("14경기 수집 실패")

except Exception as e:
    # 2순위: API fallback
    info, games = await api.get_soccer_wdl()
    if len(games) < 14:
        logger.critical(f"⚠️ 치명적: {len(games)}경기만 수집됨!")
        # 텔레그램 알림 전송
        await send_error_alert(f"14경기 수집 실패: {len(games)}경기")
```

### AI 작업자 체크리스트

코드 수정 시 반드시 확인:
- [ ] `len(games) == 14` 검증 로직이 있는가?
- [ ] 크롤러 실패 시 fallback이 있는가?
- [ ] 14경기 미만일 때 알림을 보내는가?
- [ ] 캐시 데이터도 14경기인지 검증하는가?

---

## 10. 현재 구현 상태 (2026-01-10 v3.3.0)

### ✅ 완료된 기능

| 기능 | 상태 | 버전 | 비고 |
|------|------|------|------|
| KSPO API 데이터 수집 | ✅ | v1.0 | 3순위 fallback |
| 농구 승5패 확률 계산 | ✅ | v1.0 | 정규분포 모델 |
| 축구 승무패 14경기 수집 | ✅ | v1.0 | 필수 |
| 텔레그램 알림 전송 | ✅ | v1.0 | 자동화 |
| 14경기 전체 마킹 리스트 | ✅ | v1.0 | 필수 |
| 복수 베팅 4경기 선정 | ✅ | v1.0 | 이변 감지 핵심 |
| 5개 AI 앙상블 통합 | ✅ | v2.0 | GPT, Claude, Gemini, DeepSeek, Kimi |
| 통합 자동화 스크립트 | ✅ | v2.1 | `auto_sports_notifier.py` |
| 베트맨 웹 크롤러 | ✅ | v3.0 | 2순위 데이터 소스 |
| 이중화 데이터 수집 | ✅ | v3.0 | 크롤러 → API fallback |
| 데이터 검증 시스템 | ✅ | v3.0 | `data_validator.py` |
| 적중률 추적 시스템 | ✅ | v3.1 | 예측/결과 비교 |
| 경기 결과 자동 수집 | ✅ | v3.1 | KSPO API 연동 |
| 한국 서버 마이그레이션 | ✅ | v3.2.1 | Geo-blocking 해결 |
| **젠토토 크롤러** | ✅ | **v3.3.0** | **1순위 데이터 소스** ⭐ |
| **3단계 데이터 소스 체계** | ✅ | **v3.3.0** | 젠토토 → 베트맨 → API |
| **다음 회차 미리 확보** | ✅ | **v3.3.0** | 발매 전 경기 수집 |

### 🔄 개선 필요

- [ ] 실시간 팀 통계 연동 (현재: 하드코딩된 시즌 평균)
- [ ] Gemini API 키 갱신 필요 (현재 403 오류)
- [ ] 적중률 대시보드 UI 개발

### 📦 v3.3.0 신규 모듈 (2026-01-10)

- **`zentoto_crawler.py`**: 젠토토 웹 크롤러 (1순위 데이터 소스)
- **`test_zentoto_crawler.py`**: 젠토토 크롤러 통합 테스트

### 📦 v3.1.0 모듈 (2025-12-25)

- **`result_collector.py`**: KSPO API에서 경기 결과 자동 수집
- **`prediction_tracker.py`**: 예측 저장/로드 및 누적 통계 관리
- **`hit_rate_reporter.py`**: 적중률 리포트 생성 및 텔레그램 포맷팅
- **`team_name_normalizer.py`**: 베트맨 ↔ KSPO 팀명 매칭 (fuzzy matching)

---

## 11. 문제 해결

### 경기 수가 14개가 아닐 때

```python
# 원인: KSPO API 사용 중이면 발생 가능
# 해결: 크롤러 모드 강제 사용

info, games = await manager.get_soccer_wdl_round(source="crawler")
```

### Playwright 오류 발생 시

```bash
# Playwright 재설치
pip install --upgrade playwright
playwright install chromium

# 또는 API 모드로 fallback (일부 경기 누락 가능)
info, games = await manager.get_soccer_wdl_round(source="api")
```

### 텔레그램 전송 실패
```bash
# 토큰 확인
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Chat ID 확인
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

### 데이터 불일치 확인
```bash
# 크롤러 vs API 데이터 비교
python3 test_data_validation.py --soccer --verbose
```

---

## 12. 핵심 원칙 요약

```
⭐ 최우선: 이변 감지 = 시스템의 핵심 가치
1. 배당 없이 AI가 직접 확률 계산
2. 5개 AI 앙상블 → AI 불일치 = 이변 신호
3. 이변 감지 로직으로 불확실한 경기 탐지 (upset_score)
4. 14경기 전체 마킹 리스트 + 복수 4경기 (반드시!)
5. 텔레그램으로 자동 알림
6. ⭐ 베트맨 크롤러로 정확한 14경기 수집 (KSPO API는 fallback)
7. ⭐ 로컬 개발 → Git Push → GitHub Actions → 원격 배포
```

---

## 12-1. GitHub Actions 자동 배포 워크플로우

### 배포 절차 (반드시 준수!)

```bash
# 1. 로컬에서 코드 수정
vim src/services/round_manager.py

# 2. 테스트 (반드시!)
python3 auto_sports_notifier.py --basketball --test

# 3. Git commit
git add .
git commit -m "fix: 캐시 시간 계산 버그 수정

- timedelta.seconds → total_seconds() 변경
- 10일 전 캐시 무효화 정상 작동 확인"

# 4. Git push (GitHub Actions 자동 실행)
git push origin main

# 5. GitHub Actions 모니터링
# https://github.com/USER/REPO/actions 에서 확인

# 6. 원격 서버 자동 배포 (GitHub Actions가 처리)
# SSH 접속 → Git Pull → Docker 재시작
```

### GitHub Actions 워크플로우 파일

`.github/workflows/deploy.yml` (이미 설정됨)
```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/sports-analysis
            git pull origin main
            docker-compose down
            docker-compose up -d --build
```

### 원격 서버 확인

```bash
# SSH 접속 (⚠️ 한국 서버 사용!)
ssh root@141.164.55.245

# 로그 확인
cd /opt/sports-analysis
docker logs sports_analysis --tail=100 -f

# 컨테이너 상태
docker ps

# 스케줄러 작동 확인
docker logs sports_analysis --tail=50
```

**⚠️ 주의사항:**
- 원격 서버에서 절대 직접 코드 수정하지 말 것
- 모든 변경은 로컬 → Git → CI/CD 경로로만
- 긴급 수정 시에도 반드시 로컬에서 작업 후 Git push

---

## 12-2. 프로덕션 서버 정보 (⚠️ 2026-01-05 중요 변경!)

### 🚨 서버 마이그레이션 완료 (독일 → 한국)

**배경:**
- 기존 독일 서버(5.161.112.248)에서 betman.co.kr 접근 시 **지리적 차단(Geo-blocking)** 발생
- 베트맨 크롤러가 타임아웃으로 14경기 수집 실패
- 한국 서버로 마이그레이션하여 완전 해결

---

### 현재 프로덕션 서버 (✅ 활성)

```
서버 위치: 한국 서울 (Vultr Seoul)
IP 주소: 141.164.55.245
SSH 사용자: root
프로젝트 경로: /opt/sports-analysis
Docker 컨테이너: sports_analysis (정상 실행 중)
```

**SSH 접속:**
```bash
ssh root@141.164.55.245
# SSH 키 인증 설정됨 (비밀번호 불필요)
```

**서버 상태 확인:**
```bash
# 컨테이너 상태
ssh root@141.164.55.245 "docker ps"

# 로그 확인
ssh root@141.164.55.245 "docker logs sports_analysis --tail=100 -f"

# 프로젝트 디렉토리
ssh root@141.164.55.245 "cd /opt/sports-analysis && ls -la"
```

**베트맨 접근 테스트:**
```bash
ssh root@141.164.55.245 "curl -I https://www.betman.co.kr"
# 정상 응답: HTTP/1.1 200 OK ✅
```

---

### 구 서버 (❌ 폐기됨 - 2026-01-05)

```
서버 위치: 독일 (Germany)
IP 주소: 5.161.112.248
상태: Docker 컨테이너 중지됨, 정리 완료
폐기 사유: betman.co.kr 지리적 차단으로 크롤링 불가
```

**⚠️ 주의:**
- **절대 5.161.112.248 서버를 사용하지 마세요**
- 모든 코드/문서에서 독일 서버 IP는 **141.164.55.245**로 변경됨
- GitHub Actions secrets도 한국 서버로 업데이트됨

---

### GitHub Actions Secrets 설정

다음 secrets이 한국 서버로 업데이트되었습니다:

```yaml
SERVER_HOST: 141.164.55.245
SERVER_USER: root
SSH_PRIVATE_KEY: (한국 서버용 SSH 개인키)
```

**설정 확인:**
```bash
gh secret list
# SERVER_HOST: 141.164.55.245 확인
```

---

### 마이그레이션 상세 로그 (2026-01-05)

**문제 발견:**
```
독일 서버 (5.161.112.248):
✅ KSPO API 정상
❌ 베트맨 크롤러 타임아웃 (30초, 60초 모두 실패)
❌ 14경기 중 7~8경기만 수집
원인: betman.co.kr가 해외 IP 차단
```

**해결 과정:**
```
1. 한국 서버 (141.164.55.245) 신규 구축
2. SSH 키 등록 및 접근 테스트 ✅
3. betman.co.kr 접근 테스트: HTTP 200 ✅
4. 프로젝트 Git clone 및 환경 설정 ✅
5. Docker 빌드 및 컨테이너 실행 ✅
6. 시스템 통합 테스트:
   - AI 앙상블 (5개 모델) 정상 ✅
   - 이변 감지 로직 정상 ✅
   - 텔레그램 알림 정상 ✅
7. 독일 서버 Docker 정리 및 폐기 ✅
```

**테스트 결과 (2026-01-05 00:48 KST):**
```
🏀 농구 승5패 222회차 테스트
- 베트맨 크롤러: 파싱 실패 (현재 14경기 회차 미발매)
- KSPO API: 4경기 수집 성공
- AI 분석: 5개 모델 모두 정상 작동
- 이변 감지: 복수 베팅 4경기 선정 성공
- 예측 저장: 정상

✅ 시스템 전체 정상 작동 확인
⚠️ 크롤러 파싱 실패는 14경기 회차 미발매 때문 (정상)
```

---

### 다음 작업자를 위한 체크리스트

프로젝트를 처음 접하는 작업자는 다음을 확인하세요:

- [ ] 프로덕션 서버는 **141.164.55.245 (한국 서울)** 입니다
- [ ] **5.161.112.248 (독일)** 서버는 폐기되었습니다
- [ ] SSH 접속: `ssh root@141.164.55.245`
- [ ] 프로젝트 경로: `/opt/sports-analysis`
- [ ] Docker 컨테이너명: `sports_analysis`
- [ ] GitHub Actions가 자동 배포합니다 (수동 배포 금지)
- [ ] 베트맨 크롤러는 한국 서버에서만 정상 작동합니다

**절대 금지:**
- ❌ 독일 서버(5.161.112.248)에 배포
- ❌ 서버에서 직접 코드 수정
- ❌ VPN/Proxy로 독일 서버에서 크롤링 시도

**필수 준수:**
- ✅ 한국 서버(141.164.55.245) 사용
- ✅ 로컬 개발 → Git Push → CI/CD 배포
- ✅ 베트맨 크롤러는 한국 IP에서만 작동

---

## 12-3. 현재 프로덕션 배포 상태 (2026-01-10 04:50 KST)

### 🟢 시스템 정상 운영 중

```
┌─────────────────────────────────────────────────────────────┐
│                    프로덕션 상태 요약                         │
├─────────────────────────────────────────────────────────────┤
│  서버: 141.164.55.245 (한국 서울, Vultr)                     │
│  컨테이너: sports_analysis (healthy)                         │
│  버전: v3.3.0 (cf05ec0)                                      │
│  스케줄러: 6시간 간격 자동 실행 중                             │
│  마지막 배포: 2026-01-10 04:49 KST                           │
└─────────────────────────────────────────────────────────────┘
```

### 최근 배포 검증 결과

```
✅ 젠토토 크롤러: 정상 (축구 3회차 14경기, 농구 1회차 14경기)
✅ 베트맨 크롤러: 대기 중 (젠토토 성공으로 미사용)
✅ AI 앙상블: 5개 모델 활성화
   - GPT-4o: 정상
   - Claude Sonnet: 정상
   - Gemini 1.5 Flash: ⚠️ API 키 갱신 필요 (403)
   - DeepSeek V3: 정상
   - Kimi K2: 정상 (간헐적 429)
✅ 텔레그램 알림: 정상
✅ 예측 저장: 정상 (.state/predictions/)
✅ 스케줄러: 6시간 간격 실행 중
```

### 서버 리소스

```
CPU: 0.00% (대기 중)
Memory: 160.6MB / 1GB (16%)
Network: 5.38MB 수신 / 463KB 송신
```

### 빠른 서버 확인 명령어

```bash
# 컨테이너 상태
ssh root@141.164.55.245 "docker ps"

# 최근 로그
ssh root@141.164.55.245 "docker logs sports_analysis --tail=50"

# 에러만 확인
ssh root@141.164.55.245 "docker logs sports_analysis 2>&1 | grep -E 'ERROR|실패'"

# Git 커밋 확인
ssh root@141.164.55.245 "cd /opt/sports-analysis && git log --oneline -3"
```

---

## 13. 변경 이력

### 최근 변경사항 (v3.x)

| 날짜 | 버전 | 주요 변경 | 상세 |
|------|------|----------|------|
| **2026-01-10** | **v3.3.0** | 🎯 젠토토 크롤러 도입 | 3단계 데이터 소스 체계 구축 |
| 2026-01-05 | v3.2.1 | 🌏 한국 서버 마이그레이션 | Geo-blocking 해결 |
| 2026-01-04 | v3.2.0 | 🚨 치명적 버그 수정 | 캐시/크롤러/예측저장 |
| 2025-12-25 | v3.1.0 | 적중률 추적 시스템 | 예측/결과 비교 자동화 |
| 2025-12-25 | v3.0.0 | 베트맨 크롤러 | 이중화 데이터 수집 |

### v3.3.0 상세 (2026-01-10)
- ⭐ **젠토토 크롤러 신규 구현** (`zentoto_crawler.py`)
- ⭐ **RoundManager 3단계 우선순위**: 젠토토 → 베트맨 → KSPO API
- ⭐ **다음 회차 미리 확보 기능** (발매 전에 경기 수집 가능)
- `test_zentoto_crawler.py` 통합 테스트 스크립트 추가
- 프로덕션 배포 완료 및 검증

### v3.2.1 상세 (2026-01-05)
- ✅ 한국 서버 (141.164.55.245) 배포 완료
- ❌ 독일 서버 (5.161.112.248) 폐기
- 🚨 Geo-blocking 문제 해결: betman.co.kr 접근 정상화
- GitHub Actions secrets 한국 서버로 업데이트

### v3.2.0 상세 (2026-01-04)
- 캐시 시간 계산 버그 수정 (10일 전 데이터 사용 문제)
- 베트맨 크롤러 완전 재설계 (14경기 100% 수집)
- 예측 저장 타입 오류 수정
- 24시간 자동화 스크립트 추가

### 이전 버전 (v1.x ~ v2.x)

| 버전 | 주요 변경 |
|------|----------|
| v2.1.0 | 통합 자동화 스크립트, 회차 계산 로직 |
| v2.0.0 | 5개 AI 앙상블 통합, RoundManager |
| v1.0.0 | 초기 버전 (2025-12-24) |

---

## 14. 주요 개선 사항 상세 (v3.0.0)

### 14.1 KSPO API 문제점 발견 및 해결

**발견된 문제**:
```
베트맨 웹사이트: 14경기 (1~14번 정확)
KSPO API: 12경기 (10~14번 누락, row_num 불일치)

예시 비교:
┌────────┬─────────────────────┬────────────────────────┐
│ 번호   │ 베트맨 (정확)       │ KSPO API (문제)        │
├────────┼─────────────────────┼────────────────────────┤
│ 1번    │ 레스터C vs 왓포드   │ 스토크시티 vs 프레스턴 │
│ 2번    │ 노리치C vs 찰턴     │ 미들즈브러 vs 블랙번   │
│ ...    │ ...                 │ ...                    │
│ 10번   │ 아스널 vs 브라이턴  │ ❌ 누락                │
│ 14번   │ 첼시 vs A빌라       │ ❌ 누락                │
└────────┴─────────────────────┴────────────────────────┘
```

**해결 방법**:
1. 베트맨 크롤러 개발 (Playwright 기반)
2. RoundManager에 크롤러 통합
3. 크롤러 실패 시 API fallback

### 14.2 데이터 흐름도 (⚠️ v3.3.0 업데이트!)

```
사용자 요청
     │
     ▼
┌─────────────┐
│ RoundManager │
└─────────────┘
     │
     ├─── source="auto" (기본값) ◄── ⭐ 권장!
     │         │
     │         ▼
     │    ┌──────────────┐
     │    │ 젠토토 크롤러 │ ◄── 1순위 (다음 회차 미리 확보 가능!) ⭐ NEW
     │    └──────────────┘
     │         │
     │         ├── 성공 → 14경기 반환
     │         │
     │         └── 실패
     │              │
     │              ▼
     │         ┌──────────────┐
     │         │ 베트맨 크롤러 │ ◄── 2순위 (공식 발매 사이트)
     │         └──────────────┘
     │              │
     │              ├── 성공 → 14경기 반환
     │              │
     │              └── 실패
     │                   │
     │                   ▼
     │              ┌──────────┐
     │              │ KSPO API │ ◄── 3순위 (최후 수단)
     │              └──────────┘
     │                   │
     │                   └── 12~14경기 반환 (경기 누락 가능)
     │
     ├─── source="zentoto" (젠토토만) ◄── NEW
     │
     ├─── source="crawler" (베트맨만)
     │
     └─── source="api" (API만)
```

### 14.3 검증 결과

```
✅ 데이터 검증 완료 (2025-12-25)

베트맨 웹사이트 vs 시스템 수집 데이터:
- 일치율: 100% (14/14 경기)
- 회차 번호: 정확 (152회차)
- 팀명: 모두 일치
- 경기 순서: 모두 일치

테스트 명령어:
python3 test_data_validation.py --soccer
```

---

## 15. 적중률 추적 시스템 (v3.1.0)

### 15.1 시스템 구조

```
┌─────────────────────────────────────────────────────────┐
│             적중률 추적 시스템 흐름도                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [예측 생성] ──► [prediction_tracker.save_prediction]   │
│       │                    │                            │
│       │                    ▼                            │
│       │         .state/predictions/{game_type}/         │
│       │              round_{N}.json                     │
│       │                                                 │
│  [경기 종료 후] ──► [result_collector.collect_results]  │
│       │                    │                            │
│       │         (team_name_normalizer 사용)             │
│       │                    │                            │
│       │                    ▼                            │
│       │         .state/results/{game_type}_{N}.json     │
│       │                                                 │
│  [리포트 생성] ──► [hit_rate_reporter.generate_report]  │
│       │                    │                            │
│       │                    ▼                            │
│  [텔레그램 전송] ──► [telegram_notifier.notify_*]       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 15.2 사용 예시

```python
from src.services.prediction_tracker import prediction_tracker
from src.services.result_collector import result_collector
from src.services.hit_rate_reporter import hit_rate_reporter
from src.services.telegram_notifier import telegram_notifier

# 1. 예측 저장 (분석 완료 후)
prediction_tracker.save_prediction(
    round_info=round_info,
    predictions=predictions,
    multi_games=[2, 5, 12, 13]  # 복수 베팅 경기
)

# 2. 결과 수집 (경기 종료 후)
result = await result_collector.collect_round_results(152, "soccer_wdl")

# 3. 리포트 생성
report = hit_rate_reporter.generate_report(152, "soccer_wdl")

# 4. 텔레그램 전송
await telegram_notifier.notify_hit_rate_report(report)
```

### 15.3 팀명 정규화

베트맨과 KSPO API의 팀명 차이를 자동 매칭:

| 베트맨 (축약) | KSPO API (정식) | 매칭 방식 |
|-------------|----------------|----------|
| 레스터C | 레스터시티 | mapping |
| 맨체스U | 맨체스터유나이티드 | mapping |
| A빌라 | 아스톤빌라 | mapping |
| 울산모비스 | 울산현대모비스피버스 | mapping |
| 미네소타 | 미네소타팀버울브스 | fuzzy (60%+) |

---

## 16. 젠토토 크롤러 신규 도입 (v3.3.0) ⭐ NEW

### 16.1 왜 젠토토 크롤러가 필요한가?

**기존 문제점:**
```
베트맨 크롤러 한계:
1. 발매 마감 후 → 경기 정보 사라짐
2. 발매 전 → 다음 회차 정보 없음
3. 한국 IP에서만 접근 가능 (Geo-blocking)
4. UI 변경 시 파싱 실패 위험
```

**젠토토의 장점:**
```
✅ 발매 전에 다음 회차 경기가 미리 등록됨
✅ 발매 마감 후에도 데이터 유지
✅ 베트맨 UI 변경에 대한 백업
✅ 테이블 구조가 더 안정적
```

### 16.2 3단계 데이터 소스 우선순위 체계

**v3.3.0부터 변경된 우선순위:**

| 순위 | 데이터 소스 | 특징 | 사용 시점 |
|------|------------|------|----------|
| **1순위** | **젠토토 크롤러** ⭐ | 다음 회차 미리 확보 | 평상시 사용 (권장) |
| **2순위** | 베트맨 크롤러 | 공식 발매 사이트 | 젠토토 실패 시 |
| **3순위** | KSPO API | 경기 아카이브 | 모든 크롤러 실패 시 |

### 16.3 젠토토 크롤러 구현 세부사항

**파일 위치**: `src/services/zentoto_crawler.py`

```python
class ZentotoCrawler:
    """젠토토 웹사이트 크롤러

    젠토토는 프로토 경기 정보를 미리 등록하므로,
    베트맨 발매 전에 다음 회차 경기를 확보할 수 있음
    """

    # 젠토토 URL
    BASE_URL = "https://www.zentoto.com"
    SOCCER_URL = "https://www.zentoto.com/toto/soccer"
    BASKETBALL_URL = "https://www.zentoto.com/toto/basketball"

    async def get_soccer_wdl_games(self, year=None, round_number=None, force_refresh=False):
        """축구 승무패 14경기 조회"""

    async def get_basketball_w5l_games(self, year=None, round_number=None, force_refresh=False):
        """농구 승5패 14경기 조회"""

    async def get_next_round_games(self, game_type="soccer_wdl"):
        """⭐ 다음 회차 경기 미리 확보 (발매 전)"""
```

**핵심 데이터 클래스:**

```python
@dataclass
class RoundInfo:
    """회차 정보"""
    round_number: int      # 회차 번호 (예: 152)
    year: int              # 연도 (예: 2026)
    game_type: str         # "soccer_wdl" | "basketball_w5l"
    deadline: datetime     # 마감 시간
    sale_start: datetime   # 발매 시작
    sale_end: datetime     # 발매 마감
    match_date: str        # YYYYMMDD
    game_count: int        # 경기 수 (14경기)
    status: str            # "발매중" | "발매예정" | "마감" | "결과발표"
    source: str            # "zentoto"
    updated_at: datetime

@dataclass
class GameInfo:
    """경기 정보"""
    game_number: int       # 경기 번호 (1~14)
    home_team: str         # 홈팀명 (한글)
    away_team: str         # 원정팀명 (한글)
    match_date: str        # YYYYMMDD
    match_time: str        # HHMM
    league_name: str       # 리그명
    home_odds: float       # 홈팀 배당률
    draw_odds: float       # 무승부 배당률 (축구)
    away_odds: float       # 원정팀 배당률
    five_odds: float       # 5점차 이내 배당률 (농구)
```

### 16.4 젠토토 페이지 파싱 로직

**젠토토 테이블 구조:**
```
[21] 1                          ← 경기 번호
[22] 9  6  3  33  6  코모1907   ← 통계 + 홈팀명 (탭 구분)
[23] 경기분석
[24] VS
[25] 볼로냐  8  26  7  5  6     ← 원정팀명 + 통계 (탭 구분)
```

**파싱 알고리즘:**
```python
# 1. 경기 번호 찾기 (1~14 단독 숫자)
if /^\d{1,2}$/.test(line):
    game_num = parseInt(line)
    if 1 <= game_num <= 14:

        # 2. 다음 라인: "통계\t통계\t홈팀" 형식
        home_parts = next_line.split('\t')
        home_team = home_parts[-1]  # 마지막이 팀명

        # 3. VS 라인 이후: "원정팀\t통계\t통계" 형식
        away_parts = vs_next_line.split('\t')
        away_team = away_parts[0]  # 첫번째가 팀명

        # 4. 경기 추가
        games.append({game_num, home_team, away_team})
```

### 16.5 RoundManager 업데이트 (v3.3.0)

**변경된 메서드 시그니처:**

```python
class RoundManager:
    """회차 및 경기 관리자 (젠토토 우선, 베트맨 백업, API fallback)"""

    async def get_soccer_wdl_round(
        self,
        force_refresh: bool = False,
        source: str = "auto"  # ⭐ NEW: "zentoto" 옵션 추가
    ) -> Tuple[RoundInfo, List[Dict]]:
        """
        Args:
            source: 데이터 소스
                - "auto": 젠토토 → 베트맨 → API 순서 (기본값) ⭐ 변경됨
                - "zentoto": 젠토토만 사용 ⭐ NEW
                - "crawler": 베트맨만 사용
                - "api": API만 사용
        """
```

**새로운 메서드:**

```python
# 다음 회차 미리 확보
async def prefetch_next_round(self, game_type: str = "soccer_wdl"):
    """
    다음 회차 경기 미리 확보 (발매 전)

    젠토토는 발매 전에 다음 회차 경기를 미리 등록하므로,
    이 메서드로 다음 회차를 미리 확보할 수 있음
    """

# 미리 확보된 다음 회차 조회 (캐시에서)
def get_prefetched_next_round(self, game_type: str):
    """미리 확보해둔 다음 회차 조회"""

# 현재 회차 + 다음 회차 통합 확인
async def check_and_prefetch(self, game_type: str = "soccer_wdl"):
    """
    현재 회차 확인 + 다음 회차 미리 확보 (통합)

    Returns:
        {
            "current": (RoundInfo, games) or None,
            "next": (RoundInfo, games) or None,
        }
    """
```

### 16.6 사용 예시

**기본 사용 (auto 모드 - 권장):**
```python
from src.services.round_manager import RoundManager

manager = RoundManager()

# 자동 모드: 젠토토 → 베트맨 → API 순서로 시도
info, games = await manager.get_soccer_wdl_round()
print(f"회차: {info.round_number}회차, {len(games)}경기")
```

**다음 회차 미리 확보:**
```python
# 다음 회차 미리 확보 (발매 전!)
result = await manager.prefetch_next_round("soccer_wdl")
if result:
    info, games = result
    print(f"✅ 다음 회차 확보: {info.round_number}회차")
else:
    print("❌ 다음 회차 아직 미등록")
```

**현재 + 다음 회차 통합 확인:**
```python
result = await manager.check_and_prefetch("soccer_wdl")

if result["current"]:
    info, _ = result["current"]
    print(f"현재 회차: {info.round_number}회차")

if result["next"]:
    info, games = result["next"]
    print(f"다음 회차: {info.round_number}회차 ({len(games)}경기)")
```

**특정 소스만 사용:**
```python
# 젠토토만 사용
info, games = await manager.get_soccer_wdl_round(source="zentoto")

# 베트맨만 사용
info, games = await manager.get_soccer_wdl_round(source="crawler")

# API만 사용 (비권장)
info, games = await manager.get_soccer_wdl_round(source="api")
```

### 16.7 상태 파일 구조

**새로 추가된 상태 파일:**
```
.state/
├── zentoto_soccer_wdl.json       # 젠토토 축구 승무패 캐시 ⭐ NEW
├── zentoto_basketball_w5l.json   # 젠토토 농구 승5패 캐시 ⭐ NEW
├── soccer_wdl_next_round.json    # 다음 회차 캐시 ⭐ NEW
├── basketball_w5l_next_round.json # 다음 회차 캐시 ⭐ NEW
├── betman_soccer_wdl.json        # 베트맨 축구 승무패 캐시
├── betman_basketball_w5l.json    # 베트맨 농구 승5패 캐시
├── soccer_wdl_round.json         # API 축구 승무패 캐시
└── basketball_w5l_round.json     # API 농구 승5패 캐시
```

### 16.8 테스트 스크립트

**파일 위치**: `test_zentoto_crawler.py`

```bash
# 젠토토 크롤러만 테스트
python3 test_zentoto_crawler.py --zentoto

# RoundManager 통합 테스트 (젠토토 → 베트맨 → API)
python3 test_zentoto_crawler.py --integration

# 데이터 소스 비교 테스트
python3 test_zentoto_crawler.py --compare

# 모든 테스트 실행
python3 test_zentoto_crawler.py --all
```

**테스트 결과 예시:**
```
======================================================================
🎯 젠토토 크롤러 테스트
======================================================================

[1] 축구 승무패 크롤링
--------------------------------------------------
  ✅ 회차: 2026년 3회차
  ✅ 상태: 발매중
  ✅ 경기 수: 14경기
  ✅ 14경기 수집 성공!

  경기 목록:
    01. 코모1907 vs 볼로냐
    02. 엠폴리 vs 레체
    03. 우디네세 vs 아탈란타
    04. 카옌 vs 셰필드U
    05. 노리치시티 vs 찰턴아슬레틱
    ... (총 14경기)

[2] 농구 승5패 크롤링
--------------------------------------------------
  ✅ 회차: 2026년 5회차
  ✅ 상태: 발매중
  ✅ 경기 수: 14경기
  ✅ 14경기 수집 성공!

[3] 다음 회차 미리 확보 (축구)
--------------------------------------------------
  ✅ 다음 회차 발견: 2026년 4회차
  ✅ 경기 수: 14경기

======================================================================
✅ 테스트 완료!
======================================================================
```

### 16.9 젠토토 vs 베트맨 vs API 비교

| 항목 | 젠토토 크롤러 ⭐ | 베트맨 크롤러 | KSPO API |
|------|-----------------|--------------|----------|
| **경기 수** | 14경기 (100%) | 14경기 (100%) | 12~14경기 (불안정) |
| **회차 번호** | 정확 | 정확 | 종종 NULL |
| **다음 회차** | ✅ 미리 확보 가능 | ❌ 불가 | ❌ 불가 |
| **발매 마감 후** | ✅ 데이터 유지 | ❌ 사라짐 | ✅ 유지 |
| **Geo-blocking** | 확인 필요 | 한국 IP만 | 없음 |
| **안정성** | 높음 | 보통 (UI 변경 위험) | 높음 |
| **속도** | ~8초 | ~8초 | ~2초 |

### 16.10 AI 작업자 체크리스트 (v3.3.0)

코드 수정 시 반드시 확인:
- [ ] `source="auto"`가 기본값인가? (젠토토 우선)
- [ ] 젠토토 → 베트맨 → API 순서가 유지되는가?
- [ ] `prefetch_next_round()` 로직이 정상인가?
- [ ] 젠토토 캐시(`_zentoto_cache`)와 베트맨 캐시(`_crawler_cache`) 구분되어 있는가?
- [ ] 상태 파일 경로가 올바른가? (`.state/zentoto_*.json`)

**절대 금지:**
- ❌ 젠토토 우선순위를 베트맨보다 낮추지 말 것
- ❌ `get_next_round_games()` 로직 제거하지 말 것
- ❌ 젠토토 캐시와 베트맨 캐시를 혼합하지 말 것

---

## 17. 문서 정보

**버전**: v3.3.0
**최종 업데이트**: 2026-01-10 04:50 KST
**최종 커밋**: cf05ec0
**프로덕션 상태**: 🟢 정상 운영 중

### 빠른 참조

| 주제 | 섹션 |
|------|------|
| 프로젝트 핵심 목적 | 섹션 1 |
| 이변 감지 로직 | 섹션 3.2 |
| 데이터 수집 아키텍처 | 섹션 6 |
| 젠토토 크롤러 | 섹션 16 |
| 적중률 추적 시스템 | 섹션 15 |
| 프로덕션 서버 정보 | 섹션 12-2 |
| 현재 배포 상태 | 섹션 12-3 |

### 필수 설치

```bash
# Playwright (크롤러용)
pip install playwright && playwright install chromium

# 기타 의존성
pip install aiohttp python-dotenv openai anthropic
```

### 긴급 연락처

- GitHub: https://github.com/joocy75-hash/Sports
- 프로덕션 서버: `ssh root@141.164.55.245`

---

> 이 문서를 통해 새로운 작업자도 프로젝트 방향성을 이해하고 일관된 개발을 할 수 있습니다.
