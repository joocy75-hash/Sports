# 데이터 검증 시스템 (Data Validation System)

프로토 14경기 AI 분석 시스템의 데이터 소스 검증 도구입니다.

## 빠른 시작

### 1. 기본 검증 실행

```bash
# 축구 승무패 + 농구 승5패 모두 검증
python3 test_data_validation.py

# 축구 승무패만 검증
python3 test_data_validation.py --soccer

# 농구 승5패만 검증
python3 test_data_validation.py --basketball

# 보고서를 파일로 저장
python3 test_data_validation.py --save-report
```

### 2. Python 코드에서 사용

```python
import asyncio
from src.services.data_validator import DataValidator

async def main():
    validator = DataValidator()

    # 축구 승무패 검증
    result = await validator.compare_sources("soccer_wdl")

    print(f"검증 결과: {result}")
    print(f"일치율: {result.match_rate:.1%}")

    # 마크다운 보고서 생성
    report = await validator.generate_report("soccer_wdl")
    print(report)

asyncio.run(main())
```

## 주요 기능

### 1. 데이터 소스 비교

두 가지 데이터 소스를 비교하여 불일치를 감지합니다:

- **베트맨 크롤러** (정확하지만 느림)
- **KSPO API** (빠르지만 부정확할 수 있음)

### 2. 불일치 유형 분류

| 유형 | 설명 |
|------|------|
| 팀명 불일치 | 팀명 표기가 다름 (예: "레스터C" vs "레스터시티") |
| 경기 수 불일치 | 14경기가 아님 |
| 회차 번호 불일치 | 크롤러와 API의 회차 번호가 다름 |
| 날짜/시간 불일치 | 경기 일정이 다름 |
| 경기 누락 | 한쪽 소스에 경기가 없음 |

### 3. 자동 수정 제안

각 불일치에 대해 다음을 제안합니다:

- **크롤러 사용 권장**: 크롤러 데이터가 더 정확함
- **API 사용 권장**: API 데이터가 더 정확함
- **수동 검토 필요**: 판단 불가, 직접 확인 필요

### 4. 검증 보고서 생성

마크다운 형식의 상세 보고서를 자동 생성합니다:

- 검증 개요 (일치율, 검증 시각)
- 데이터 소스 정보 비교
- 불일치 항목 상세 (유형별 그룹화)
- 권장 사항
- 경기 목록 상세 비교

## 실행 결과 예시

```
================================================================================
⚽ 축구 승무패 데이터 검증
================================================================================

# 데이터 검증 보고서
## 축구 승무패

**검증 시각**: 2025-12-25 17:16:31
**검증 결과**: ⚠️ 불일치
**일치율**: 0.0% (0/14경기)

---

## 데이터 소스 정보

| 항목 | 베트맨 크롤러 | KSPO API |
|------|--------------|----------|
| 회차 번호 | 152회 | 84회 |
| 경기 수 | 14경기 | 12경기 |
| 경기 날짜 | 20251225 | 20251227 |
| 상태 | open | open |

---

## 불일치 항목 (46건)

### 회차 번호 불일치 (1건)
- 크롤러: 152회 vs API: 84회
- 권장 조치: 크롤러 사용

### 경기 수 불일치 (1건)
- 크롤러: 14경기 vs API: 12경기
- 권장 조치: 크롤러 사용

### 팀명 불일치 (24건)
...

---

## 권장 사항

**결론**: 베트맨 크롤러 데이터 사용을 권장합니다.

이유:
- 크롤러는 베트맨 공식 웹사이트에서 직접 수집하므로 더 정확합니다.
- KSPO API는 turn_no 누락, 경기 누락 등의 문제가 있습니다.
```

## 파일 구조

```
스포츠분석/
│
├── src/services/
│   └── data_validator.py          # 검증 시스템 메인 모듈
│
├── test_data_validation.py        # 테스트 실행 스크립트
│
├── docs/
│   └── DATA_VALIDATION.md         # 상세 가이드 문서
│
└── .state/validation_reports/     # 검증 보고서 저장 경로
    ├── soccer_wdl_20251225_171631.md
    └── basketball_w5l_20251225_171702.md
```

## API 참조

### DataValidator 클래스

```python
class DataValidator:
    async def compare_sources(
        game_type: str,
        use_cache: bool = False
    ) -> ValidationResult:
        """두 소스 비교"""

    async def generate_report(
        game_type: str,
        use_cache: bool = False
    ) -> str:
        """마크다운 보고서 생성"""

    async def get_validation_summary(
        game_type: str
    ) -> Dict:
        """JSON 요약 정보"""
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    is_valid: bool           # 100% 일치 여부
    match_rate: float        # 일치율 (0~1)
    total_games: int         # 총 경기 수
    matched_games: int       # 일치하는 경기 수
    mismatches: List[Mismatch]  # 불일치 항목들
    crawler_data: Tuple      # 크롤러 데이터
    api_data: Tuple          # API 데이터
```

## 팀명 정규화

팀명은 다양한 형태로 표기될 수 있으므로, 정규화 로직을 사용합니다:

```python
TEAM_NAME_MAPPINGS = {
    "레스터시티": ["레스터C", "레스터", "레스터 시티"],
    "맨체스터유나이티드": ["맨체스U", "맨유", "맨체스터U"],
    "맨체스터시티": ["맨시티", "맨체스터C"],
    # ...
}
```

새로운 팀명 매핑을 추가하려면 `src/services/data_validator.py`의 `TEAM_NAME_MAPPINGS`를 수정하세요.

## 통합 사용 예시

### RoundManager와 함께 사용

```python
from src.services.round_manager import RoundManager
from src.services.data_validator import DataValidator

async def smart_data_collection():
    validator = DataValidator()
    manager = RoundManager()

    # 1. 검증 실행
    result = await validator.compare_sources("soccer_wdl")

    # 2. 일치율에 따라 소스 선택
    if result.match_rate >= 0.9:
        # 일치율 90% 이상: API 사용 (빠름)
        info, games = await manager.get_soccer_wdl_round(source="api")
    else:
        # 불일치 발생: 크롤러 사용 (정확함)
        info, games = await manager.get_soccer_wdl_round(source="crawler")

    return info, games
```

## 문제 해결

### Q: 검증이 너무 오래 걸립니다

**A**: 크롤러가 Playwright를 사용하므로 시간이 걸립니다. `use_cache=True`를 사용하면 5분 이내 캐시된 결과를 재사용합니다.

```python
result = await validator.compare_sources("soccer_wdl", use_cache=True)
```

### Q: 팀명 불일치가 계속 나타납니다

**A**: `TEAM_NAME_MAPPINGS`에 해당 팀명 매핑을 추가하세요.

```python
TEAM_NAME_MAPPINGS = {
    # 새로운 매핑 추가
    "새로운팀": ["새팀", "새로운 팀", "새로운팀FC"],
}
```

### Q: 항상 크롤러를 사용하면 되지 않나요?

**A**: 크롤러는 정확하지만 느리고 Playwright가 필요합니다. 프로덕션에서는 API 우선 사용 후 불일치 발생 시에만 크롤러로 fallback하는 것이 효율적입니다.

## 상세 문서

더 자세한 내용은 다음 문서를 참고하세요:

- [상세 가이드](docs/DATA_VALIDATION.md)
- [CLAUDE.md](CLAUDE.md) - 프로젝트 전체 가이드

## 라이선스

MIT License

---

**버전**: 1.0.0
**최종 업데이트**: 2025-12-25
