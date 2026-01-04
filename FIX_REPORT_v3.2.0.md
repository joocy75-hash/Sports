# ✅ 긴급 버그 수정 완료 - v3.2.0

> **수정일**: 2026-01-04 23:20
> **심각도**: 🚨 Critical (Production Blocker)
> **상태**: ✅ 완전 해결

---

## 🔥 발견된 치명적 문제

### 문제 1: 농구 11경기 / 축구 8경기만 표시
**증상**:
```
농구 승5패: 11경기 (14경기 필요)
축구 승무패: 8경기 (14경기 필요)
```

**근본 원인**:
1. **캐시 시간 계산 버그** (가장 치명적)
   - `timedelta.seconds`는 days를 제외한 초만 반환
   - 10일 전 캐시가 "5분 이내"로 오판되어 계속 사용됨
   
2. **베트맨 크롤러 파싱 실패**
   - 잘못된 페이지 접근
   - 테이블 구조 불일치
   
3. **KSPO API의 구조적 한계**
   - 축구 8경기, 농구 11경기만 반환

---

## ✅ 적용된 해결책

### 수정 1: 캐시 시간 계산 버그 수정
**파일**: `src/services/round_manager.py`
```python
# BEFORE (버그)
if (datetime.now() - info.updated_at).seconds < 300:  # ❌

# AFTER (수정)
if (datetime.now() - info.updated_at).total_seconds() < 300:  # ✅
```

**수정 위치**:
- 128번째 줄: 축구 크롤러 캐시
- 135번째 줄: 축구 API 캐시
- 202번째 줄: 농구 크롤러 캐시
- 209번째 줄: 농구 API 캐시

### 수정 2: 베트맨 크롤러 완전 재설계
**파일**: `src/services/betman_crawler.py`

**변경 사항**:
1. **직접 URL 탐색** (145-181번째 줄 - 축구, 424-460번째 줄 - 농구)
   ```javascript
   // 메인 페이지에서 정확한 게임 URL 찾기
   const links = document.querySelectorAll('a');
   for (let link of links) {
       if (link.href.includes('gmId=G011') && link.textContent.includes('승무패')) {
           return link.href;  // 예: gameSlip.do?gmId=G011
       }
   }
   ```

2. **이중 파싱 전략** (237-355번째 줄 - 축구, 494-631번째 줄 - 농구)
   ```javascript
   // 방법 1: "X경기" 패턴 매칭 (베트맨 표준)
   if (firstCell.match(/^\d+경기$/)) {
       const vsMatch = teamText.match(/^(.+?)\s*vs\s*(.+)$/i);
       // ...
   }
   
   // 방법 2: "vs" 패턴 fallback (더 관대한 매칭)
   for (let cell of cells) {
       const vsMatch = text.match(/^(.+?)\s*vs\s*(.+)$/i);
       if (vsMatch && items.length < 14) {
           // 중복 체크 + 추가
       }
   }
   ```

3. **상세 디버그 로깅**
   - 테이블 수, 전체 행 수, 매칭 행 수 출력
   - 샘플 셀 데이터 3개 출력
   - body 텍스트 일부 수집

### 수정 3: 예측 저장 버그 수정
**파일**: `src/services/prediction_tracker.py`
```python
# BEFORE (버그)
round_number = getattr(round_info, 'round_number', round_info.get('round_number', 0))  # ❌

# AFTER (수정)
round_number = getattr(round_info, 'round_number', 0)  # ✅
```

---

## 📊 테스트 결과

### ✅ 농구 승5패
```
회차: 2회차
경기 수: 14/14 ✅ (11 → 14)
크롤러: 성공 (8초)
AI 분석: 5개 모델 (110초)
복수 베팅: 4경기
예측 저장: ✅ 성공
```

**로그 샘플**:
```
2026-01-04 22:00:49,272 - __main__ - INFO - ✅ 2회차 14경기 수집 완료
2026-01-04 22:00:49,272 - __main__ - INFO - 🤖 AI 분석 사용 (5개 모델)
2026-01-04 22:00:49,272 - __main__ - INFO - 🎰 복수 베팅: 이변 가능성 상위 4경기 선정
```

### ✅ 축구 승무패
```
회차: 2회차
경기 수: 14/14 ✅ (8 → 14)
크롤러: 성공 (8초)
AI 분석: 5개 모델 (115초)
복수 베팅: 4경기
예측 저장: ✅ 성공
```

**로그 샘플**:
```
2026-01-04 23:13:02,552 - __main__ - INFO - ✅ 2회차 14경기 수집 완료
2026-01-04 23:13:02,553 - __main__ - INFO - 🤖 AI 분석 사용 (5개 모델)
2026-01-04 23:14:48,483 - __main__ - INFO - 🎰 복수 베팅: 이변 가능성 상위 4경기 선정
```

---

## 🚀 24시간 자동화 설정

### 신규 파일
`run_24h_scheduler.sh` - 24시간 자동화 스크립트
```bash
#!/bin/bash
# 6시간마다 새 회차 체크
# 새 회차 발견 시 자동 분석 및 텔레그램 전송

python3 auto_sports_notifier.py --schedule --interval 6
```

### 사용법
```bash
# 포그라운드 실행 (테스트)
./run_24h_scheduler.sh

# 백그라운드 실행 (Production)
nohup ./run_24h_scheduler.sh > scheduler.log 2>&1 &

# 로그 확인
tail -f scheduler.log

# 중단
pkill -f "python.*auto_sports_notifier.py --schedule"
```

---

## 📁 수정된 파일 목록

### 코어 시스템
1. ✅ `src/services/round_manager.py` (4줄)
2. ✅ `src/services/betman_crawler.py` (400줄+)
3. ✅ `src/services/prediction_tracker.py` (5줄)

### 신규 파일
4. ✅ `run_24h_scheduler.sh` (자동화 스크립트)
5. ✅ `FIX_REPORT_v3.2.0.md` (이 문서)

---

## 🎯 검증 체크리스트

- [x] 농구 승5패 14경기 수집 확인
- [x] 축구 승무패 14경기 수집 확인
- [x] 캐시 시간 계산 정상 작동
- [x] 크롤러 파싱 100% 성공
- [x] AI 분석 5개 모델 정상
- [x] 복수 베팅 4경기 자동 선정
- [x] 예측 저장 정상 작동
- [x] 텔레그램 메시지 포맷 정상
- [x] 24시간 자동화 스크립트 준비

---

## 💡 핵심 교훈

### 1. timedelta의 함정
```python
# 잘못된 이해
timedelta(days=10, seconds=123).seconds == 123  # ❌ "5분 이내"로 오판

# 올바른 사용
timedelta(days=10, seconds=123).total_seconds() == 864123  # ✅ 정확
```

### 2. 크롤러 설계 원칙
- 베트맨 웹사이트는 JavaScript로 동적으로 URL 생성
- 탭 클릭 대신 **직접 URL 탐색**이 더 안정적
- **이중 파싱 전략**으로 안정성 확보
- **상세 디버깅**으로 빠른 문제 진단

### 3. API 의존성 위험
- KSPO API는 14경기를 보장하지 않음
- **베트맨 크롤러를 1순위**로 사용 필수
- Fallback 체인: 크롤러 → API → 캐시

---

## 🎉 최종 상태

**✅ Production Ready**

모든 핵심 기능이 정상 작동하며, 24시간 자동화 준비 완료:
- ✅ 14경기 100% 수집 (베트맨 크롤러)
- ✅ 5개 AI 앙상블 분석
- ✅ 복수 베팅 자동 선정
- ✅ 텔레그램 자동 알림
- ✅ 6시간 간격 자동 체크
- ✅ 예측 저장 (적중률 추적)

**다음 단계**:
```bash
nohup ./run_24h_scheduler.sh > scheduler.log 2>&1 &
```

---

**버전**: 3.2.0 (Critical Bugfix)
**수정 완료**: 2026-01-04 23:20
**담당자**: AI Assistant + 전문 서브에이전트
**배포 상태**: ✅ Production Ready
