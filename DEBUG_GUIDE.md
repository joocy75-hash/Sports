# 전체 코드 디버깅 가이드

이 가이드는 프로젝트 전체를 체계적으로 디버깅하는 최고의 방법을 제공합니다.

## 🚀 빠른 시작

### 1. 통합 디버깅 실행 (권장)

```bash
# 전체 코드 자동 디버깅
python debug_all.py

# 또는 빠른 디버깅 스크립트
./quick_debug.sh
```

이 명령어는 다음을 자동으로 수행합니다:
- ✅ 구문 오류 검사
- ✅ Import 오류 검사
- ✅ 코드 품질 분석
- ✅ 설정 파일 검증
- ✅ 데이터베이스 연결 테스트
- ✅ API 엔드포인트 검증
- ✅ 종합 리포트 생성

### 2. 결과 확인

디버깅 후 다음 파일들이 생성됩니다:
- `debug_report.txt` - 읽기 쉬운 텍스트 리포트
- `debug_report.json` - 상세 JSON 리포트
- `debug_report.log` - 로그 파일
- `logs/debug_YYYYMMDD.log` - 날짜별 상세 로그

## 📋 단계별 디버깅 방법

### 1단계: 구문 오류 검사

```bash
# Python 구문 검사
python3 -m py_compile $(find . -name "*.py" -not -path "./.venv/*")
```

### 2단계: Import 오류 검사

```bash
# 개별 모듈 테스트
python3 -c "from src.config.settings import Settings; print('OK')"
python3 -c "from src.db.session import get_db_session; print('OK')"
```

### 3단계: 로깅 활성화

```python
# enhanced_logging.py 사용
from enhanced_logging import setup_enhanced_logging, trace_function

# 로깅 설정
setup_enhanced_logging(level="DEBUG", log_to_file=True)

# 함수 추적
@trace_function
async def my_function():
    ...
```

### 4단계: 데이터베이스 연결 테스트

```python
# 직접 테스트
python3 -c "
import asyncio
from src.db.session import get_db_session
from sqlalchemy import text

async def test():
    async with get_db_session() as session:
        result = await session.execute(text('SELECT 1'))
        print('DB 연결 성공')

asyncio.run(test())
"
```

### 5단계: API 엔드포인트 테스트

```bash
# 서버 실행
python -m uvicorn src.api.unified_server:app --reload

# 다른 터미널에서 테스트
curl http://localhost:8000/health
```

## 🔧 고급 디버깅 기법

### 1. 함수 호출 추적

```python
from enhanced_logging import trace_function, DebugContext

@trace_function(log_args=True, log_result=True)
async def analyze_match(match_id: int):
    # 모든 호출과 결과가 자동으로 로깅됩니다
    ...
```

### 2. 성능 프로파일링

```python
from enhanced_logging import log_performance

@log_performance(threshold=1.0)  # 1초 초과 시 경고
async def slow_operation():
    ...
```

### 3. 컨텍스트 매니저 사용

```python
from enhanced_logging import DebugContext

with DebugContext("데이터 수집"):
    # 이 블록의 실행 시간과 오류가 자동 로깅됩니다
    collect_data()
```

### 4. 에러 핸들링 데코레이터

```python
from src.core.error_handling import async_error_handler, retry_async

@async_error_handler(func_name="크롤러", default_return=None)
@retry_async(max_retries=3, delay=1.0)
async def crawl_data():
    ...
```

## 📊 디버깅 리포트 해석

### 리포트 구조

```
📊 통계
  - 전체 파일 수
  - 유효한 파일 수
  - 전체 코드 라인
  - 전체 함수/클래스 수

❌ 오류 요약
  - 구문 오류
  - 임포트 오류
  - 설정 오류
  - 데이터베이스 오류

⚠️ 경고
  - 복잡한 함수
  - 타입 힌트 누락
  - 문서화 부족
```

### 오류 우선순위

1. **치명적 오류** (즉시 수정 필요)
   - 구문 오류
   - 필수 설정 누락
   - 데이터베이스 연결 실패

2. **중요 오류** (빠른 수정 권장)
   - Import 오류
   - 타입 오류
   - API 엔드포인트 오류

3. **경고** (개선 권장)
   - 복잡한 함수
   - 타입 힌트 누락
   - 문서화 부족

## 🛠️ 특정 모듈 디버깅

### 특정 파일만 디버깅

```python
# debug_all.py 수정하여 특정 파일만 검사
python3 -c "
from pathlib import Path
from debug_all import CodeDebugger

debugger = CodeDebugger(Path('.'))
files = [Path('src/services/toto_analyzer.py')]
# 특정 파일만 검사
"
```

### 특정 서비스 테스트

```bash
# 토토 분석기 테스트
python3 -c "
import asyncio
from src.services.toto_analyzer import TotoAnalyzer

async def test():
    analyzer = TotoAnalyzer()
    result = await analyzer.analyze_round(1)
    print(result)

asyncio.run(test())
"
```

## 📝 로그 파일 활용

### 로그 파일 위치

- `logs/debug_YYYYMMDD.log` - 날짜별 상세 로그
- `debug_report.log` - 디버깅 리포트 로그
- `scheduler.log` - 스케줄러 로그 (있는 경우)

### 로그 검색

```bash
# 에러만 찾기
grep -i "error\|exception\|fail" logs/debug_*.log

# 특정 함수 호출 추적
grep "my_function" logs/debug_*.log

# 성능 문제 찾기 (1초 이상)
grep -E "[0-9]+\.[0-9]+초" logs/debug_*.log | grep -E "[1-9][0-9]*\.[0-9]+초"
```

## 🎯 디버깅 체크리스트

디버깅 전에 다음을 확인하세요:

- [ ] `.env` 파일이 존재하고 필수 변수가 설정되어 있는가?
- [ ] 데이터베이스가 실행 중인가?
- [ ] 필요한 Python 패키지가 설치되어 있는가? (`pip install -r requirements.txt`)
- [ ] 가상 환경이 활성화되어 있는가?

## 🔍 일반적인 문제 해결

### Import 오류

```bash
# Python 경로 확인
python3 -c "import sys; print('\n'.join(sys.path))"

# 모듈 경로 추가
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### 데이터베이스 연결 오류

```bash
# 연결 문자열 확인
python3 -c "from src.config.settings import get_settings; print(get_settings().postgres_dsn)"

# 직접 연결 테스트
psql $DATABASE_URL -c "SELECT 1"
```

### 비동기 함수 디버깅

```python
# asyncio 디버그 모드 활성화
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # Windows용

# 디버그 모드로 실행
PYTHONASYNCIODEBUG=1 python your_script.py
```

## 📚 추가 리소스

- [Python 디버깅 가이드](https://docs.python.org/3/library/pdb.html)
- [FastAPI 디버깅](https://fastapi.tiangolo.com/tutorial/debugging/)
- [SQLAlchemy 로깅](https://docs.sqlalchemy.org/en/20/core/engines.html#configuring-logging)

## 💡 팁

1. **점진적 디버깅**: 한 번에 전체를 디버깅하지 말고, 모듈별로 나눠서 진행
2. **로그 레벨 조정**: 프로덕션에서는 INFO, 개발 중에는 DEBUG
3. **에러 컨텍스트**: 에러 발생 시 가능한 많은 컨텍스트 정보 수집
4. **자동화**: 정기적으로 `debug_all.py`를 실행하여 문제를 조기에 발견

---

**마지막 업데이트**: 2026-01-05
**버전**: 1.0.0
