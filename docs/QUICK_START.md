# 빠른 시작 가이드

> 5분 안에 시스템을 실행할 수 있도록 핵심만 정리한 가이드입니다.

---

## 1. 환경 설정

### 필수 패키지 설치

```bash
# 기본 패키지
pip install aiohttp python-dotenv

# Playwright (베트맨 크롤러용) - 필수!
pip install playwright
playwright install chromium
```

### .env 파일 생성

```bash
# .env 파일 (프로젝트 루트에 생성)

# AI API 키 (최소 1개 필수)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
DEEPSEEK_API_KEY=...

# 텔레그램 (필수)
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_CHAT_ID=987654321

# KSPO API (선택 - fallback용)
KSPO_TODZ_API_KEY=...
```

---

## 2. 실행 명령어

### 축구 승무패 분석

```bash
# 테스트 모드 (텔레그램 전송 없이 콘솔 출력만)
python3 auto_sports_notifier.py --soccer --test

# 실제 텔레그램 전송
python3 auto_sports_notifier.py --soccer
```

### 농구 승5패 분석

```bash
# 테스트 모드
python3 auto_sports_notifier.py --basketball --test

# 실제 텔레그램 전송
python3 auto_sports_notifier.py --basketball
```

### 전체 분석 (축구 + 농구)

```bash
python3 auto_sports_notifier.py
```

---

## 3. 출력 예시

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

📝 *단식 정답*
`1:1 2:1 3:2 4:1 5:X 6:1 7:2`
`8:1 9:2 10:1 11:1 12:2 13:1 14:1`

🎰 *복수 4경기* (총 16조합)
02번 노리치C vs 찰턴 → 1,X
05번 스토크C vs 프레스턴 → X,1
```

---

## 4. 데이터 수집 확인

### 현재 수집 데이터 확인

```bash
# 축구 승무패 데이터 확인
cat .state/betman_soccer_wdl.json | python3 -m json.tool | head -50

# 농구 승5패 데이터 확인
cat .state/betman_basketball_w5l.json | python3 -m json.tool | head -50
```

### 데이터 검증

```bash
# 크롤러 vs API 데이터 비교
python3 test_data_validation.py --soccer
```

---

## 5. 문제 해결

### Playwright 오류

```bash
# Playwright 재설치
pip install --upgrade playwright
playwright install chromium
```

### 경기 수가 14개가 아닐 때

```bash
# 크롤러 캐시 삭제 후 재실행
rm .state/betman_soccer_wdl.json
python3 auto_sports_notifier.py --soccer --test
```

### 텔레그램 전송 실패

```bash
# 봇 토큰 확인
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

---

## 6. 주요 파일 위치

| 파일 | 설명 |
|------|------|
| `auto_sports_notifier.py` | 메인 실행 스크립트 |
| `src/services/round_manager.py` | 데이터 수집 관리 |
| `src/services/betman_crawler.py` | 베트맨 웹 크롤러 |
| `.state/` | 캐시 데이터 저장 |
| `CLAUDE.md` | 전체 프로젝트 가이드 |

---

## 7. 다음 단계

1. **CLAUDE.md** 전체 읽기 - 프로젝트 아키텍처 이해
2. **docs/DATA_VALIDATION.md** - 데이터 검증 시스템 이해
3. **5개 AI 모델** 커스터마이징 - `src/services/ai/` 폴더

---

**버전**: 3.0.0
**최종 업데이트**: 2025-12-25
