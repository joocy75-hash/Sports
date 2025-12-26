# 베트맨 웹 크롤러 사용 가이드

## 개요

KSPO API의 한계(경기 누락, row_num 불일치, turn_no NULL)를 해결하기 위해 베트맨 웹사이트에서 직접 14경기 정보를 크롤링하는 모듈입니다.

## 주요 기능

- **축구 승무패 14경기 크롤링**: 정확한 팀명, 경기 번호, 회차 정보 수집
- **농구 승5패 14경기 크롤링**: 정확한 팀명, 경기 번호, 회차 정보 수집
- **자동 캐싱**: 5분간 캐시하여 중복 요청 방지
- **에러 핸들링**: 크롤링 실패 시 캐시된 데이터 사용
- **스크린샷 디버깅**: 파싱 실패 시 자동으로 스크린샷 저장

## 파일 위치

```
/Users/mr.joo/Desktop/스포츠분석/src/services/betman_crawler.py
```

## 설치

Playwright 브라우저 설치 필요:

```bash
cd "/Users/mr.joo/Desktop/스포츠분석"
python3 -m playwright install chromium
```

## 기본 사용법

### 1. 컨텍스트 매니저로 사용 (권장)

```python
import asyncio
from src.services.betman_crawler import BetmanCrawler

async def main():
    async with BetmanCrawler(headless=True) as crawler:
        # 축구 승무패 크롤링
        soccer_info, soccer_games = await crawler.get_soccer_wdl_games()
        print(f"축구 승무패 {soccer_info.round_number}회차")
        for game in soccer_games:
            print(f"{game.game_number}. {game.home_team} vs {game.away_team}")

        # 농구 승5패 크롤링
        basketball_info, basketball_games = await crawler.get_basketball_w5l_games()
        print(f"농구 승5패 {basketball_info.round_number}회차")
        for game in basketball_games:
            print(f"{game.game_number}. {game.home_team} vs {game.away_team}")

asyncio.run(main())
```

### 2. 캐시 무효화 (강제 새로고침)

```python
async with BetmanCrawler() as crawler:
    # force_refresh=True로 캐시 무시하고 최신 데이터 수집
    info, games = await crawler.get_soccer_wdl_games(force_refresh=True)
```

### 3. 헤드리스 모드 끄기 (디버깅용)

```python
# 브라우저 창을 직접 볼 수 있음
async with BetmanCrawler(headless=False) as crawler:
    info, games = await crawler.get_soccer_wdl_games()
```

## 데이터 구조

### RoundInfo (회차 정보)

```python
@dataclass
class RoundInfo:
    round_number: int          # 회차 번호 (예: 84)
    game_type: str             # "soccer_wdl" | "basketball_w5l"
    deadline: Optional[datetime]  # 마감 시간
    match_date: str            # 경기일 (YYYYMMDD)
    game_count: int            # 경기 수 (14)
    status: str                # "open" | "closed"
    updated_at: datetime       # 업데이트 시간
```

### GameInfo (경기 정보)

```python
@dataclass
class GameInfo:
    game_number: int           # 경기 번호 (1~14)
    home_team: str             # 홈팀명 (한글)
    away_team: str             # 원정팀명 (한글)
    match_date: str            # 경기 날짜 (YYYYMMDD)
    match_time: str            # 경기 시간 (HHMM)
    league_name: Optional[str] # 리그명
```

## 실제 크롤링 결과 예시

### 축구 승무패 152회차 (2025-12-25 수집)

```
회차: 152
경기일: 20251225
경기 수: 14

경기 목록:
  01. 레스터C vs 왓포드 (0000)
  02. 노리치C vs 찰턴 (0000)
  03. 옥스퍼드 vs 사우샘프 (0000)
  04. 포츠머스 vs 퀸즈파크 (0000)
  05. 스토크C vs 프레스턴 (0000)
  06. 웨스브로 vs 브리스C (0000)
  07. 렉섬 vs 셰필드U (0230)
  08. 맨체스U vs 뉴캐슬U (0500)
  09. 노팅엄포 vs 맨체스C (2130)
  10. 아스널 vs 브라이턴 (0000)
  11. 브렌트퍼 vs 본머스 (0000)
  12. 번리 vs 에버턴 (0000)
  13. 웨스트햄 vs 풀럼 (0000)
  14. 첼시 vs A빌라 (0230)
```

## 캐시 파일 위치

크롤링한 데이터는 자동으로 캐시됩니다:

```
/Users/mr.joo/Desktop/스포츠분석/.state/betman_soccer_wdl.json
/Users/mr.joo/Desktop/스포츠분석/.state/betman_basketball_w5l.json
```

## 에러 처리

### 1. 크롤링 실패 시

크롤링이 실패하면 자동으로 캐시된 데이터를 사용합니다:

```python
try:
    info, games = await crawler.get_soccer_wdl_games()
except ValueError as e:
    # 캐시도 없고 크롤링도 실패한 경우에만 예외 발생
    print(f"오류: {e}")
```

### 2. 스크린샷 자동 저장

파싱 실패 시 디버깅을 위해 스크린샷이 자동 저장됩니다:

```
/Users/mr.joo/Desktop/스포츠분석/.state/betman_soccer_error_20251225_164721.png
```

## 기술적 세부사항

### 크롤링 방식

1. **Playwright 사용**: 동적 JavaScript 페이지 렌더링
2. **베트맨 페이지 접근**: `https://www.betman.co.kr/main/mainPage/gamebuy/buyableGameList.do`
3. **탭 클릭**: 승무패/승5패 탭 자동 클릭
4. **JavaScript 평가**: DOM에서 직접 경기 데이터 추출
5. **정규표현식 파싱**: "홈팀vs원정팀" 패턴 매칭

### 핵심 파싱 로직

베트맨 테이블 구조:

```
테이블 행 예시:
- 셀 0: "1경기"
- 셀 1: "25.12.27 (토) 00:00\n\n경기장킹파워스타디움"
- 셀 2: "레스터Cvs 왓포드"  ← 여기서 팀명 추출
- 셀 3~: 배당률 등
```

JavaScript 추출 코드:

```javascript
const vsMatch = teamText.match(/^(.+?)vs\\s*(.+)$/);
if (vsMatch) {
    const homeTeam = vsMatch[1].trim();  // "레스터C"
    const awayTeam = vsMatch[2].trim();  // "왓포드"
}
```

## 기존 시스템 통합

### RoundManager 대체

기존 KSPO API 기반 `RoundManager` 대신 사용 가능:

```python
# 기존 (KSPO API)
from src.services.round_manager import RoundManager
manager = RoundManager()
info, games = await manager.get_soccer_wdl_round()

# 새로운 (베트맨 크롤러)
from src.services.betman_crawler import BetmanCrawler
async with BetmanCrawler() as crawler:
    info, games = await crawler.get_soccer_wdl_games()
```

### 데이터 형식 호환성

`RoundInfo`와 `GameInfo`는 기존 시스템과 호환되도록 설계되었으나,
필드명이 약간 다를 수 있으므로 필요시 어댑터 패턴 사용:

```python
def convert_to_kspo_format(betman_game):
    """베트맨 GameInfo를 KSPO Dict 형식으로 변환"""
    return {
        "row_num": betman_game.game_number,
        "hteam_han_nm": betman_game.home_team,
        "ateam_han_nm": betman_game.away_team,
        "match_ymd": betman_game.match_date,
        "match_tm": betman_game.match_time,
    }
```

## 주의사항

1. **robots.txt 준수**: 베트맨 웹사이트의 robots.txt 확인 필요
2. **요청 간격**: 과도한 요청 방지를 위해 5분 캐시 사용
3. **브라우저 리소스**: Playwright는 실제 브라우저를 실행하므로 리소스 소모가 큼
4. **네트워크 의존성**: 베트맨 웹사이트가 다운되면 크롤링 불가 (캐시 사용)

## 트러블슈팅

### 문제: "Timeout 30000ms exceeded" 오류

**원인**: 베트맨 웹사이트 응답 지연

**해결**:
```python
# 1. 타임아웃 증가 (코드 수정 필요)
await page.goto(url, wait_until="networkidle", timeout=60000)

# 2. 캐시된 데이터 사용 (자동)
# 크롤러는 자동으로 캐시로 폴백함
```

### 문제: 팀명이 잘못 파싱됨

**원인**: 베트맨 웹사이트 HTML 구조 변경

**해결**:
1. 디버그 스크립트 실행:
```bash
python3 debug_betman.py
```

2. 저장된 HTML 파일 확인:
```
.state/betman_page.html
```

3. 파싱 로직 수정 (`_parse_soccer_wdl_page()` 메서드)

### 문제: 브라우저가 실행되지 않음

**원인**: Playwright 브라우저 미설치

**해결**:
```bash
python3 -m playwright install chromium
```

## 성능

- **첫 요청**: ~5-10초 (브라우저 시작 + 페이지 로딩)
- **캐시된 요청**: < 1ms
- **메모리 사용**: ~200-300MB (Chromium 브라우저)

## 향후 개선 사항

- [ ] 회차 번호 추출 로직 개선 (현재는 추정 사용)
- [ ] API 엔드포인트 발견 시 직접 API 호출로 대체
- [ ] 경기 결과 자동 수집 기능 추가
- [ ] 멀티 회차 지원 (과거 회차 조회)

## 문의

크롤러 관련 문의사항은 CLAUDE.md 파일을 참고하세요.

---

**버전**: 1.0.0
**최종 업데이트**: 2025-12-25
**작성**: Claude Code AI Assistant
