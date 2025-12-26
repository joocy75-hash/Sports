# 빠른 시작 가이드

> **베트맨 크롤러 통합 RoundManager 사용법**

---

## 1분 요약

```python
from src.services.round_manager import RoundManager

manager = RoundManager()

# 축구 승무패 (크롤러 우선, 실패 시 API 자동 전환)
info, games = await manager.get_soccer_wdl_round()

# 농구 승5패 (크롤러 우선, 실패 시 API 자동 전환)
info, games = await manager.get_basketball_w5l_round()

# 결과: 항상 14경기, 정확한 회차 번호!
```

---

## 주요 변경 사항

### Before (기존)
```python
# KSPO API만 사용
info, games = await manager.get_soccer_wdl_round()
# → 12~14경기 (불확실)
# → 회차 번호 추정 필요
```

### After (현재)
```python
# 베트맨 크롤러 우선, API fallback
info, games = await manager.get_soccer_wdl_round()
# → 항상 14경기 (정확)
# → 정확한 회차 번호 (152회차)
```

---

## 실행 방법

### 메인 스크립트 (변경 없음)

```bash
# 축구 승무패 분석
python3 auto_sports_notifier.py --soccer

# 농구 승5패 분석
python3 auto_sports_notifier.py --basketball

# 전체 분석
python3 auto_sports_notifier.py

# 테스트 모드
python3 auto_sports_notifier.py --test
```

### 새로운 옵션 (선택 사항)

```python
# 크롤러만 사용 (API 안 쓰기)
info, games = await manager.get_soccer_wdl_round(source="crawler")

# API만 사용 (크롤러 안 쓰기)
info, games = await manager.get_soccer_wdl_round(source="api")

# Auto 모드 (기본값 - 크롤러 우선, 실패 시 API)
info, games = await manager.get_soccer_wdl_round(source="auto")
```

---

## 테스트

```bash
# 통합 테스트 실행
python3 test_round_manager_integration.py

# 예상 결과:
# 총 5개 테스트 중 5개 통과 (100%)
# 🎉 모든 테스트 통과! RoundManager 통합 성공!
```

---

## 데이터 우선순위

```
1순위: 베트맨 크롤러 (가장 정확 - 14경기, 정확한 회차)
   ↓ 실패 시
2순위: KSPO API (안정적 - 12~14경기)
   ↓ 실패 시
3순위: 캐시 데이터 (저장된 데이터)
```

---

## 로그 확인

### 성공 (크롤러)
```
INFO - ✅ 크롤러: 축구 승무패 152회차 14경기 수집
```

### Fallback (API)
```
WARNING - 크롤러 실패, API fallback 시도
INFO - ✅ API: 축구 승무패 84회차 12경기 수집
```

### 캐시 히트
```
INFO - 크롤러 캐시에서 축구 승무패 152회차 로드
```

---

## 문제 해결

### 크롤러 타임아웃
```
❌ 문제: Page.goto: Timeout 30000ms exceeded

✅ 해결: 자동으로 API fallback 실행 (걱정 안 해도 됨)
```

### 경기 수 부족
```
❌ 문제: 12경기만 수집됨

✅ 해결:
1. 크롤러 사용 (14경기 보장)
2. 또는 발매 전 상태 (정상)
```

---

## 핵심 포인트

✅ **기존 코드 100% 호환** - 아무것도 수정 안 해도 됨
✅ **자동 fallback** - 크롤러 실패해도 자동으로 API 사용
✅ **14경기 정확** - 크롤러 사용 시 항상 14경기
✅ **정확한 회차** - 추정 아닌 실제 회차 번호 (152회차)

---

## 더 알아보기

- `CLAUDE.md` - 프로젝트 전체 가이드
- `CRAWLER_INTEGRATION.md` - 상세 통합 가이드
- `INTEGRATION_SUMMARY.md` - 작업 완료 보고서
