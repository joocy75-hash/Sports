# 베트맨 크롤러 통합 가이드

> **RoundManager 개선: 베트맨 크롤러 우선 사용 + KSPO API Fallback**

---

## 변경 사항 요약

### 기존 문제점
- KSPO API만 사용 → 경기 누락, row_num 불일치, turn_no NULL 문제
- 40경기 이상 수집되는 경우 발생
- 회차 번호 추정 로직 필요

### 해결 방법
- **베트맨 크롤러 1순위**: 정확한 14경기 + 회차 번호
- **KSPO API 2순위**: 크롤러 실패 시 자동 fallback
- 별도 캐시 관리로 성능 최적화

---

## 데이터 소스 우선순위

```
1순위: 베트맨 크롤러
  ✅ 정확한 14경기 (row_num 1~14)
  ✅ 정확한 회차 번호
  ✅ 누락 없음
  ❌ 네트워크 의존성 (크롤링 실패 가능)

2순위: KSPO API
  ✅ 공식 API (안정적)
  ✅ 빠른 응답
  ❌ 경기 누락 가능
  ❌ turn_no NULL 가능
  ❌ 여러 회차 혼재 가능

3순위: 캐시된 데이터
  ✅ 즉시 응답
  ❌ 최신 데이터 아님
```

---

## RoundManager 사용법

### 1. 기본 사용 (Auto 모드 - 권장)

```python
from src.services.round_manager import RoundManager

manager = RoundManager()

# 축구 승무패 (크롤러 우선, 실패 시 API)
info, games = await manager.get_soccer_wdl_round(force_refresh=True)

# 농구 승5패 (크롤러 우선, 실패 시 API)
info, games = await manager.get_basketball_w5l_round(force_refresh=True)
```

### 2. 소스 지정 모드

```python
# 크롤러만 사용 (API 사용 안 함)
info, games = await manager.get_soccer_wdl_round(
    force_refresh=True,
    source="crawler"
)

# API만 사용 (크롤러 사용 안 함)
info, games = await manager.get_soccer_wdl_round(
    force_refresh=True,
    source="api"
)

# Auto 모드 (기본값 - 크롤러 우선)
info, games = await manager.get_soccer_wdl_round(
    force_refresh=True,
    source="auto"  # 생략 가능
)
```

### 3. 캐시 활용

```python
# 첫 요청 (크롤러 또는 API에서 데이터 수집)
info, games = await manager.get_soccer_wdl_round(force_refresh=True)

# 5분 이내 재요청 (캐시 사용 - 즉시 응답)
info, games = await manager.get_soccer_wdl_round(force_refresh=False)

# 강제 갱신 (캐시 무시)
info, games = await manager.get_soccer_wdl_round(force_refresh=True)
```

---

## 내부 동작 흐름

### Auto 모드 (source="auto")

```
1. 캐시 확인
   ├─ 크롤러 캐시 (5분 이내) → 반환
   └─ API 캐시 (5분 이내) → 반환

2. 베트맨 크롤러 시도
   ├─ 성공 & 14경기 → 크롤러 캐시 저장 → 반환
   └─ 실패 or 경기 부족 → 다음 단계

3. KSPO API 시도
   ├─ 성공 → API 캐시 저장 → 반환
   └─ 실패 → 다음 단계

4. 저장된 상태 파일 로드
   ├─ 파일 존재 → 반환
   └─ 파일 없음 → 예외 발생
```

---

## 데이터 형식 변환

크롤러 데이터는 자동으로 KSPO API 형식으로 변환되어 기존 코드와 호환됩니다.

### 크롤러 원본 (GameInfo)

```python
GameInfo(
    game_number=1,
    home_team="레스터C",
    away_team="왓포드",
    match_date="20251225",
    match_time="0000",
    league_name="챔피언십"
)
```

### 변환 후 (API 형식)

```python
{
    "row_num": 1,                    # int 형식 유지
    "hteam_han_nm": "레스터C",
    "ateam_han_nm": "왓포드",
    "match_ymd": "20251225",
    "match_tm": "0000",
    "match_sport_han_nm": "축구",
    "obj_prod_nm": "토토/프로토",
    "leag_han_nm": "챔피언십",
    "turn_no": 152                   # int 형식 유지
}
```

---

## 캐시 관리

### 별도 캐시

```python
# RoundManager 내부
self._cache = {}           # API 캐시
self._crawler_cache = {}   # 크롤러 캐시 (별도 관리)
```

### 캐시 우선순위

1. **크롤러 캐시** (가장 정확) - 5분 유효
2. **API 캐시** (fallback) - 5분 유효
3. **상태 파일** (.state/*.json) - 영구 저장

### 캐시 키

- 축구 승무패: `"soccer_wdl"`
- 농구 승5패: `"basketball_w5l"`

---

## 상태 파일

### 크롤러 상태 파일

```
.state/betman_soccer_wdl.json     # 축구 승무패 크롤러 데이터
.state/betman_basketball_w5l.json # 농구 승5패 크롤러 데이터
```

### API 상태 파일

```
.state/soccer_wdl_round.json      # 축구 승무패 API 데이터
.state/basketball_w5l_round.json  # 농구 승5패 API 데이터
```

---

## 테스트

### 통합 테스트 실행

```bash
# 전체 통합 테스트
python3 test_round_manager_integration.py

# 테스트 항목:
# 1. 축구 Auto 모드 (크롤러 → API)
# 2. 축구 크롤러 전용
# 3. 축구 API 전용
# 4. 농구 Auto 모드
# 5. 캐시 동작 확인
```

### 메인 스크립트 테스트

```bash
# 축구 승무패 테스트 (크롤러 우선)
python3 auto_sports_notifier.py --soccer --test

# 농구 승5패 테스트 (크롤러 우선)
python3 auto_sports_notifier.py --basketball --test

# 전체 테스트
python3 auto_sports_notifier.py --test
```

---

## 성능 비교

| 모드 | 첫 요청 | 캐시 히트 | 정확도 |
|------|---------|-----------|--------|
| 크롤러 우선 (Auto) | ~7초 | 즉시 | ★★★★★ 14경기 정확 |
| API만 | ~3초 | 즉시 | ★★★☆☆ 12~14경기 |
| 크롤러만 | ~7초 | 즉시 | ★★★★★ 14경기 정확 |

---

## 로그 분석

### 성공 케이스 (크롤러)

```
2025-12-25 17:00:46,396 - round_manager - INFO - 베트맨 크롤러 초기화 완료
2025-12-25 17:00:53,112 - betman_crawler - INFO - 축구 승무패 152회차 14경기 수집 완료
2025-12-25 17:00:53,112 - round_manager - INFO - ✅ 크롤러: 축구 승무패 152회차 14경기 수집
```

### Fallback 케이스 (크롤러 실패 → API)

```
2025-12-25 17:01:16,467 - betman_crawler - ERROR - 축구 승무패 크롤링 실패: Timeout
2025-12-25 17:01:16,468 - betman_crawler - WARNING - 저장된 데이터 사용
2025-12-25 17:00:22,334 - round_manager - INFO - ✅ API: 축구 승무패 84회차 12경기 수집
```

### 캐시 히트

```
2025-12-25 17:00:40,305 - round_manager - INFO - 크롤러 캐시에서 축구 승무패 152회차 로드
```

---

## 문제 해결

### 크롤러 타임아웃

**증상**:
```
Page.goto: Timeout 30000ms exceeded
```

**원인**: 베트맨 웹사이트 응답 지연

**해결**:
1. Auto 모드 사용 (자동으로 API fallback)
2. 저장된 캐시 데이터 사용
3. 재시도

### 14경기 부족

**증상**:
```
크롤러에서 12경기 수집 (14경기 필요)
```

**원인**: 발매 전 또는 비시즌

**해결**:
1. 정상 상태 - 대기
2. API fallback 자동 실행
3. 이전 캐시 데이터 사용 가능

### 캐시 무효화

**방법**:
```python
# force_refresh=True 사용
info, games = await manager.get_soccer_wdl_round(force_refresh=True)
```

또는 상태 파일 삭제:
```bash
rm .state/betman_*.json
rm .state/*_round.json
```

---

## 기존 코드 호환성

✅ **완전 호환**: 기존 `auto_sports_notifier.py` 등 모든 코드가 수정 없이 동작

```python
# 기존 코드 (변경 없음)
manager = RoundManager()
info, games = await manager.get_soccer_wdl_round()

# 자동으로 크롤러 우선 사용
# 크롤러 실패 시 자동으로 API fallback
# 데이터 형식은 기존과 동일
```

---

## 요약

### 장점
✅ 정확한 14경기 수집 (크롤러)
✅ 자동 fallback (안정성)
✅ 별도 캐시 관리 (성능)
✅ 기존 코드 호환 (마이그레이션 불필요)

### 주의사항
⚠️ 크롤러 실패 시 API로 전환 (로그 확인 필요)
⚠️ 첫 요청 시 7초 정도 소요 (크롤링)
⚠️ Playwright 브라우저 필요 (설치 필수)

---

**버전**: 1.0.0
**최종 업데이트**: 2025-12-25
**작성**: AI Assistant
