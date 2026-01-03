# 토토 14경기 AI 분석 + 언더독 감지 시스템 구현 완료

> **날짜**: 2026-01-03  
> **버전**: 4.0.0  
> **목표**: 텔레그램 알림 + 14경기 정확 분석 + 언더독/이변 감지

---

## 🎯 구현 완료!

### ✅ 1. 데이터 수집 (14경기 보장)
- RoundManager + 베트맨 크롤러
- 축구 승무패 2회차: **14경기 정상 수집**
- 농구 승5패 152회차: **14경기 정상 수집**

### ✅ 2. AI 앙상블 분석
- **5개 AI 모델**: GPT-4o, Claude, Gemini, DeepSeek, Kimi
- **경기별 다른 확률** (기존: 모두 동일 확률)
- **컨센서스 기반 예측**

### ✅ 3. 언더독/이변 감지 ⚠️
**4가지 신호**:
1. 확률 분포 애매함 (35%)
2. AI 모델 간 불일치 (30%)
3. 폼-예측 상충 (20%)
4. 랭킹 불일치 (15%)

**이변 확률 >= 55% → 복수 베팅 추천**

### ✅ 4. 텔레그램 알림
```
⚽ *축구 승무패 2회차*
📋 14경기 전체 예측
📝 단식 정답 (1:1 2:1 3:X ...)
🎰 복수 4경기 (총 16조합)
```

---

## 📊 API 엔드포인트

```bash
# 축구 승무패 분석
GET /api/v1/toto/soccer

# 농구 승5패 분석  
GET /api/v1/toto/basketball

# 텔레그램 알림 전송
POST /api/v1/toto/notify-telegram?game_type=soccer
```

---

## 🚀 사용 방법

```bash
# 1. 서버 실행
python3 -m uvicorn src.api.unified_server:app --reload --port 8000

# 2. 축구 분석
curl http://localhost:8000/api/v1/toto/soccer

# 3. 텔레그램 전송
curl -X POST "http://localhost:8000/api/v1/toto/notify-telegram?game_type=soccer"
```

---

## 💡 핵심 원칙

```
프로토 14경기는 ALL or NOTHING
→ 13개 맞추고 1개 틀리면 전액 손실
→ 이변 감지가 핵심!

전략:
- 고신뢰 경기 10개 → 단일 베팅
- 이변 가능 경기 4개 → 복수 베팅
- 총 2^4 = 16조합
```

---

**🎉 모든 시스템 구현 완료!**
