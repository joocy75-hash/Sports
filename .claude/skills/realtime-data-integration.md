# 실시간 데이터 연동 스킬 (v4.0.0 업그레이드)

> **스킬 버전**: 1.0.0
> **대상 프로젝트 버전**: v3.3.0 → v4.0.0
> **작성일**: 2026-01-10
> **상세 계획서**: [docs/REALTIME_DATA_INTEGRATION_PLAN.md](../../docs/REALTIME_DATA_INTEGRATION_PLAN.md)

---

## 스킬 개요

이 스킬은 프로토 14경기 AI 분석 시스템에 **실시간 데이터 연동**을 추가하는 대규모 업그레이드 작업입니다.

### 현재 상태 (v3.3.0)
- AI가 팀 이름만으로 예측 (실시간 데이터 없음)
- 5개 AI 앙상블 (GPT, Claude, Gemini, DeepSeek, Kimi)
- 3단계 데이터 소스 (젠토토 → 베트맨 → KSPO API)

### 목표 상태 (v4.0.0)
- 실시간 팀 통계, 폼, 상대전적, 부상자, 배당률 연동
- 풍부한 MatchContext로 AI 예측 정확도 향상
- 예상 정확도: 55% → 65-70%

---

## 다중 AI 작업자 가이드

### 작업 시작 전 필수 확인

```bash
# 1. 현재 버전 확인
cat CLAUDE.md | grep "버전"
# 예상: v3.3.0

# 2. 프로덕션 서버 상태 확인
ssh root@141.164.55.245 "docker ps"
# 예상: sports_analysis (healthy)

# 3. Git 상태 확인
git status
git log --oneline -3
```

### 작업 완료 시 필수 절차

```bash
# 1. 테스트 실행
python3 auto_sports_notifier.py --soccer --test

# 2. Git commit (상세 메시지 필수!)
git add .
git commit -m "feat: [Phase X.Y] 기능명

- 구현 내용 1
- 구현 내용 2
- 테스트 결과

Co-Authored-By: Claude [Model] <noreply@anthropic.com>"

# 3. Git push (자동 배포)
git push origin main

# 4. 배포 확인
ssh root@141.164.55.245 "cd /opt/sports-analysis && git log --oneline -1"

# 5. 다음 작업자를 위해 이 스킬의 체크리스트 업데이트!
```

---

## Phase별 작업 체크리스트

### Phase 1: 데이터 수집 레이어 구축

#### 1.1 팀 통계 수집 모듈 (`team_stats_collector.py`)

**파일 위치**: `src/services/data/team_stats_collector.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| 디렉토리 생성 (`src/services/data/`) | ⬜ 대기 | - | - |
| TeamStats 데이터클래스 정의 | ⬜ 대기 | - | - |
| Football-Data.org API 연동 | ⬜ 대기 | - | - |
| API-Football 백업 연동 | ⬜ 대기 | - | - |
| 캐싱 로직 구현 (TTL 6시간) | ⬜ 대기 | - | - |
| 단위 테스트 작성 | ⬜ 대기 | - | - |
| 통합 테스트 통과 | ⬜ 대기 | - | - |

**테스트 명령어**:
```bash
python3 -m pytest tests/test_team_stats_collector.py -v
```

**완료 기준**:
- [ ] `TeamStatsCollector.get_team_stats("맨시티", "Premier League")` 호출 성공
- [ ] 캐시 히트/미스 로깅 확인
- [ ] Rate limiting 작동 확인

---

#### 1.2 최근 폼 수집 모듈 (`form_collector.py`)

**파일 위치**: `src/services/data/form_collector.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| TeamForm 데이터클래스 정의 | ⬜ 대기 | - | - |
| RecentMatch 데이터클래스 정의 | ⬜ 대기 | - | - |
| 최근 5경기 결과 수집 로직 | ⬜ 대기 | - | - |
| 폼 지표 계산 (승점, 연승/연패) | ⬜ 대기 | - | - |
| 캐싱 로직 구현 (TTL 1시간) | ⬜ 대기 | - | - |
| 단위 테스트 작성 | ⬜ 대기 | - | - |

**테스트 명령어**:
```bash
python3 -m pytest tests/test_form_collector.py -v
```

---

#### 1.3 상대 전적 수집 모듈 (`h2h_collector.py`)

**파일 위치**: `src/services/data/h2h_collector.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| HeadToHead 데이터클래스 정의 | ⬜ 대기 | - | - |
| H2HMatch 데이터클래스 정의 | ⬜ 대기 | - | - |
| 상대 전적 조회 로직 | ⬜ 대기 | - | - |
| 홈/원정 구분 전적 계산 | ⬜ 대기 | - | - |
| 캐싱 로직 구현 (TTL 24시간) | ⬜ 대기 | - | - |
| 단위 테스트 작성 | ⬜ 대기 | - | - |

---

#### 1.4 부상자/출전정지 수집 모듈 (`injuries_collector.py`)

**파일 위치**: `src/services/data/injuries_collector.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| PlayerInjury 데이터클래스 정의 | ⬜ 대기 | - | - |
| TeamInjuries 데이터클래스 정의 | ⬜ 대기 | - | - |
| API-Football injuries 연동 | ⬜ 대기 | - | - |
| Transfermarkt 크롤링 백업 | ⬜ 대기 | - | - |
| 주전 선수 여부 판별 로직 | ⬜ 대기 | - | - |
| 캐싱 로직 구현 (TTL 2시간) | ⬜ 대기 | - | - |

---

#### 1.5 실시간 배당률 수집 모듈 (`odds_collector.py`)

**파일 위치**: `src/services/data/odds_collector.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| MatchOdds 데이터클래스 정의 | ⬜ 대기 | - | - |
| OddsSnapshot 데이터클래스 정의 | ⬜ 대기 | - | - |
| The Odds API 연동 | ⬜ 대기 | - | - |
| 젠토토/베트맨 배당 수집 연동 | ⬜ 대기 | - | - |
| 내재 확률 계산 로직 | ⬜ 대기 | - | - |
| 배당 변동 분석 로직 | ⬜ 대기 | - | - |
| 캐싱 로직 구현 (TTL 5분) | ⬜ 대기 | - | - |

---

### Phase 2: 데이터 통합 및 MatchContext 확장

#### 2.1 통합 데이터 서비스 (`match_enricher.py`)

**파일 위치**: `src/services/data/match_enricher.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| MatchEnricher 클래스 구현 | ⬜ 대기 | - | - |
| 병렬 데이터 수집 (asyncio.gather) | ⬜ 대기 | - | - |
| 부분 실패 처리 (return_exceptions) | ⬜ 대기 | - | - |
| enriched_context 문자열 생성 | ⬜ 대기 | - | - |
| 14경기 일괄 처리 최적화 | ⬜ 대기 | - | - |
| 통합 테스트 | ⬜ 대기 | - | - |

---

#### 2.2 MatchContext 모델 확장

**파일 위치**: `src/services/ai/models.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| home_stats / away_stats 필드 추가 | ⬜ 대기 | - | - |
| home_form / away_form 필드 추가 | ⬜ 대기 | - | - |
| h2h_record 필드 추가 | ⬜ 대기 | - | - |
| injuries 필드 추가 | ⬜ 대기 | - | - |
| odds_implied_prob 필드 추가 | ⬜ 대기 | - | - |
| data_completeness 필드 추가 | ⬜ 대기 | - | - |
| to_prompt_string() 메서드 개선 | ⬜ 대기 | - | - |
| 하위 호환성 유지 확인 | ⬜ 대기 | - | - |

---

### Phase 3: AI 프롬프트 개선

#### 3.1 시스템 프롬프트 개선

**파일 위치**: `src/services/ai/base_analyzer.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| 축구 승무패 프롬프트 개선 | ⬜ 대기 | - | - |
| 농구 승5패 프롬프트 개선 | ⬜ 대기 | - | - |
| 데이터 기반 분석 가중치 명시 | ⬜ 대기 | - | - |
| 이변 감지 포인트 강화 | ⬜ 대기 | - | - |
| upset_risk 출력 필드 추가 | ⬜ 대기 | - | - |
| 프롬프트 A/B 테스트 | ⬜ 대기 | - | - |

---

### Phase 4: 팀명 매핑 시스템 강화

#### 4.1 팀명 매핑 데이터베이스

**파일 위치**: `src/services/data/team_mapping.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| SOCCER_TEAM_MAPPING 구축 (프리미어리그) | ⬜ 대기 | - | - |
| SOCCER_TEAM_MAPPING 구축 (세리에A) | ⬜ 대기 | - | - |
| SOCCER_TEAM_MAPPING 구축 (분데스리가) | ⬜ 대기 | - | - |
| SOCCER_TEAM_MAPPING 구축 (라리가) | ⬜ 대기 | - | - |
| SOCCER_TEAM_MAPPING 구축 (리그앙) | ⬜ 대기 | - | - |
| SOCCER_TEAM_MAPPING 구축 (챔피언십) | ⬜ 대기 | - | - |
| BASKETBALL_TEAM_MAPPING 구축 (NBA) | ⬜ 대기 | - | - |
| BASKETBALL_TEAM_MAPPING 구축 (KBL) | ⬜ 대기 | - | - |
| TeamMapper 클래스 구현 | ⬜ 대기 | - | - |
| Fuzzy 매칭 로직 구현 | ⬜ 대기 | - | - |
| 매핑 정확도 테스트 (90%+) | ⬜ 대기 | - | - |

---

### Phase 5: 캐싱 및 성능 최적화

#### 5.1 캐싱 전략 구현

**파일 위치**: `src/services/data/cache_manager.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| CacheTTL Enum 정의 | ⬜ 대기 | - | - |
| CacheManager 클래스 (파일 백엔드) | ⬜ 대기 | - | - |
| Redis 백엔드 옵션 (선택) | ⬜ 대기 | - | - |
| 캐시 무효화 로직 | ⬜ 대기 | - | - |
| 캐시 통계 로깅 | ⬜ 대기 | - | - |

---

#### 5.2 API Rate Limiting

**파일 위치**: `src/services/data/rate_limiter.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| RateLimiter 클래스 구현 | ⬜ 대기 | - | - |
| Football-Data.org 리미터 (10/min) | ⬜ 대기 | - | - |
| API-Football 리미터 (100/day) | ⬜ 대기 | - | - |
| The Odds API 리미터 (500/month) | ⬜ 대기 | - | - |
| Rate limit 초과 시 대기 로직 | ⬜ 대기 | - | - |

---

### Phase 6: 통합 및 배포

#### 6.1 auto_sports_notifier.py 통합

**파일 위치**: `auto_sports_notifier.py`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| MatchEnricher 통합 | ⬜ 대기 | - | - |
| 데이터 수집 → AI 분석 파이프라인 | ⬜ 대기 | - | - |
| 에러 핸들링 (데이터 수집 실패 시) | ⬜ 대기 | - | - |
| 성능 로깅 (수집 시간 등) | ⬜ 대기 | - | - |
| 통합 테스트 통과 | ⬜ 대기 | - | - |
| 프로덕션 배포 | ⬜ 대기 | - | - |

---

#### 6.2 환경 변수 설정

**파일 위치**: `.env` / `.env.example`

| 작업 | 상태 | 담당 AI | 완료일 |
|------|------|---------|--------|
| FOOTBALL_DATA_API_KEY 추가 | ⬜ 대기 | - | - |
| API_FOOTBALL_KEY 추가 | ⬜ 대기 | - | - |
| API_BASKETBALL_KEY 추가 | ⬜ 대기 | - | - |
| ODDS_API_KEY 추가 | ⬜ 대기 | - | - |
| 서버 환경 변수 설정 | ⬜ 대기 | - | - |

---

## 작업 우선순위 가이드

### P0 (최우선) - 이것부터 시작!

1. **팀명 매핑 DB** - 모든 데이터 수집의 기반
2. **팀 통계 수집** - 가장 중요한 데이터
3. **최근 폼 수집** - 현재 컨디션 반영

### P1 (중요)

4. **상대 전적 수집** - 심리적 우위 분석
5. **배당률 수집** - 시장 예측 참고
6. **MatchContext 확장** - 데이터 통합

### P2 (부가)

7. **부상자 정보** - 정확한 로스터
8. **캐싱 최적화** - 성능 개선
9. **AI 프롬프트 개선** - 분석 품질 향상

---

## 다음 작업자를 위한 인수인계

### 마지막 완료 작업

```
Phase: (작업자가 업데이트)
작업 내용: (작업자가 업데이트)
완료일: (작업자가 업데이트)
담당 AI: (작업자가 업데이트)
커밋: (작업자가 업데이트)
```

### 다음 작업 추천

```
Phase: (작업자가 업데이트)
작업 내용: (작업자가 업데이트)
예상 난이도: (작업자가 업데이트)
선행 조건: (작업자가 업데이트)
```

### 주의사항 / 이슈

```
(작업자가 발견한 이슈나 주의사항 기록)
```

---

## API 키 발급 가이드

### Football-Data.org (무료)
1. https://www.football-data.org/client/register 접속
2. 회원가입 후 API 키 발급
3. 무료 티어: 10 requests/min, 주요 유럽 리그

### API-Football (무료 100/day)
1. https://rapidapi.com/api-sports/api/api-football 접속
2. RapidAPI 회원가입
3. Subscribe to Basic (Free)

### The Odds API (무료 500/month)
1. https://the-odds-api.com/ 접속
2. Get API Key 클릭
3. Free tier 선택

---

## 문제 해결 가이드

### API Rate Limit 초과
```python
# 해결: 캐시 TTL 늘리기
CacheTTL.TEAM_STATS = 12 * 3600  # 6시간 → 12시간
```

### 팀명 매칭 실패
```python
# 해결: team_mapping.py에 매핑 추가
SOCCER_TEAM_MAPPING["새팀명"] = {
    "aliases": ["대체명1", "대체명2"],
    "api_football_id": 123,
}
```

### 데이터 수집 실패
```python
# 해결: 기존 프롬프트 기반 분석으로 fallback
if not enriched_context:
    # 기존 방식 유지
    pass
```

---

## 참고 문서

- [CLAUDE.md](../../CLAUDE.md) - 프로젝트 전체 가이드
- [REALTIME_DATA_INTEGRATION_PLAN.md](../../docs/REALTIME_DATA_INTEGRATION_PLAN.md) - 상세 구현 계획
- [Football-Data.org Docs](https://www.football-data.org/documentation/quickstart)
- [API-Football Docs](https://www.api-football.com/documentation-v3)

---

**스킬 버전**: 1.0.0
**최종 수정**: 2026-01-10
