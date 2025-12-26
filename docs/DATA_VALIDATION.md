# 데이터 검증 시스템 가이드

## 개요

프로토 14경기 AI 분석 시스템에서는 두 가지 데이터 소스를 사용합니다:

1. **베트맨 크롤러** (Playwright 기반)
   - 장점: 베트맨 공식 웹사이트에서 직접 수집하므로 정확함
   - 단점: Playwright 필요, 실행 속도가 느림

2. **KSPO API** (공공데이터포털)
   - 장점: 빠르고 안정적
   - 단점: `turn_no` 누락, 경기 누락, 데이터 지연 등의 문제 발생 가능

**데이터 검증 시스템은 이 두 소스의 데이터를 비교하여 불일치를 감지하고, 어떤 소스를 사용할지 권장합니다.**

---

## 주요 기능

### 1. 데이터 비교 검증

두 소스에서 수집한 데이터를 다음 항목으로 비교합니다:

- **회차 정보**: 회차 번호, 경기 수, 경기 날짜
- **경기 정보**: 홈팀명, 원정팀명, 경기 시간
- **일치율 계산**: 전체 경기 중 일치하는 경기의 비율

### 2. 팀명 정규화

팀명은 다양한 형태로 표기될 수 있으므로, 정규화 로직을 통해 유사도를 계산합니다.

```python
# 예시
"레스터시티" == "레스터C" == "레스터"  # 동일 팀으로 인식
"맨체스터유나이티드" == "맨유" == "맨체스U"  # 동일 팀
```

**지원 방식**:
- 사전 정의된 매핑 테이블 (TEAM_NAME_MAPPINGS)
- difflib 기반 유사도 계산 (SequenceMatcher)
- 부분 문자열 매칭

### 3. 불일치 유형 분류

검증 시스템은 불일치를 다음 6가지 유형으로 분류합니다:

| 유형 | 설명 | 예시 |
|------|------|------|
| `TEAM_NAME_MISMATCH` | 팀명 불일치 | 크롤러: "레스터C" vs API: "스토크시티" |
| `GAME_COUNT_MISMATCH` | 경기 수 불일치 | 크롤러: 14경기 vs API: 12경기 |
| `ORDER_MISMATCH` | 경기 순서 불일치 | 1번 경기가 서로 다름 |
| `DATE_TIME_MISMATCH` | 날짜/시간 불일치 | 크롤러: 20251225 vs API: 20251227 |
| `ROUND_MISMATCH` | 회차 번호 불일치 | 크롤러: 152회 vs API: 84회 |
| `MISSING_GAME` | 경기 누락 | API에 13, 14번 경기 없음 |

### 4. 자동 수정 제안

각 불일치 항목에 대해 다음 중 하나를 권장합니다:

- **use_crawler**: 베트맨 크롤러 데이터 사용 권장
- **use_api**: KSPO API 데이터 사용 권장
- **manual_review**: 수동 검토 필요 (판단 불가)

**결정 로직**:
```python
if 유사도 >= 70%:
    return "use_crawler"  # 크롤러가 더 정확함
elif 유사도 >= 30%:
    return "manual_review"  # 수동 검토 필요
else:
    return "manual_review"  # 완전히 다름
```

### 5. 검증 보고서 생성

마크다운 형식의 상세 보고서를 자동 생성합니다.

**보고서 구성**:
1. 검증 개요 (일치율, 검증 시각)
2. 데이터 소스 정보 비교 테이블
3. 불일치 항목 상세 (유형별 그룹화)
4. 권장 사항 (어떤 소스를 사용할지)
5. 경기 목록 상세 비교 (처음 5경기)

---

## 사용 방법

### 기본 사용

```python
import asyncio
from src.services.data_validator import DataValidator

async def main():
    validator = DataValidator()

    # 축구 승무패 검증
    result = await validator.compare_sources("soccer_wdl")

    print(f"검증 결과: {result}")
    print(f"일치율: {result.match_rate:.1%}")
    print(f"불일치 항목 수: {len(result.mismatches)}")

asyncio.run(main())
```

### 보고서 생성

```python
async def main():
    validator = DataValidator()

    # 마크다운 보고서 생성
    report = await validator.generate_report("soccer_wdl")
    print(report)

    # 파일로 저장
    with open("validation_report.md", "w", encoding="utf-8") as f:
        f.write(report)
```

### JSON 요약 정보

```python
async def main():
    validator = DataValidator()

    # JSON 형식 요약
    summary = await validator.get_validation_summary("soccer_wdl")

    import json
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    # {
    #   "is_valid": false,
    #   "match_rate": 0.0,
    #   "total_games": 14,
    #   "matched_games": 0,
    #   "mismatches_count": 46,
    #   "recommended_source": "crawler",
    #   "validated_at": "2025-12-25T17:16:44.342619"
    # }
```

### 커맨드라인 스크립트

```bash
# 축구 승무패만 검증
python3 test_data_validation.py --soccer

# 농구 승5패만 검증
python3 test_data_validation.py --basketball

# 보고서를 파일로 저장
python3 test_data_validation.py --save-report

# 상세 로그 출력
python3 test_data_validation.py --verbose
```

---

## 검증 결과 해석

### 예시 1: 완전 일치

```
검증 결과: ✅ 일치 - 일치율: 100.0% (14/14경기)
```

**해석**: 두 소스의 데이터가 완전히 일치합니다. 어떤 소스를 사용해도 무방합니다.

### 예시 2: 부분 불일치 (팀명 약어)

```
검증 결과: ⚠️ 불일치 - 일치율: 85.7% (12/14경기)

불일치 항목:
01번 경기 - home_team:
  크롤러: "레스터C"
  API: "레스터시티"
  유사도: 80.0%
  권장: 크롤러 사용
```

**해석**: 팀명 약어 차이로 인한 불일치입니다. 유사도가 80%이므로 크롤러 데이터를 사용하되, 팀명 매핑 테이블에 추가를 고려해야 합니다.

### 예시 3: 심각한 불일치 (회차 번호 다름)

```
검증 결과: ⚠️ 불일치 - 일치율: 0.0% (0/14경기)

불일치 항목:
- 회차 번호: 크롤러 152회 vs API 84회
- 경기 수: 크롤러 14경기 vs API 12경기
```

**해석**: 크롤러와 API가 서로 다른 회차의 데이터를 수집했습니다. 이 경우 **반드시 크롤러 데이터를 사용**해야 합니다.

---

## 팀명 매핑 테이블 관리

### 매핑 추가하기

`src/services/data_validator.py`의 `TEAM_NAME_MAPPINGS`에 새로운 팀명 매핑을 추가할 수 있습니다.

```python
TEAM_NAME_MAPPINGS = {
    # 기존 매핑
    "레스터시티": ["레스터C", "레스터", "레스터 시티"],

    # 새로운 매핑 추가
    "브라이턴": ["브라이튼앤드호브앨비언", "브라이튼&호브", "브라이튼"],
}
```

### 자동 매핑 학습 (향후 기능)

검증 보고서에서 `manual_review` 항목을 확인하고, 반복적으로 나타나는 패턴을 매핑 테이블에 추가하세요.

---

## 통합 워크플로우

### 1. 데이터 수집 전 검증

```python
from src.services.round_manager import RoundManager
from src.services.data_validator import DataValidator

async def collect_with_validation():
    validator = DataValidator()

    # 검증 실행
    result = await validator.compare_sources("soccer_wdl")

    # 일치율이 90% 이상이면 API 사용 (빠름)
    if result.match_rate >= 0.9:
        manager = RoundManager()
        info, games = await manager.get_soccer_wdl_round(source="api")
    else:
        # 불일치가 크면 크롤러 사용 (정확함)
        manager = RoundManager()
        info, games = await manager.get_soccer_wdl_round(source="crawler")

    return info, games
```

### 2. 주기적 검증 (모니터링)

```python
import asyncio
from datetime import datetime

async def periodic_validation():
    validator = DataValidator()

    while True:
        # 축구 승무패 검증
        soccer_result = await validator.compare_sources("soccer_wdl")

        if not soccer_result.is_valid:
            # 불일치 발견 시 알림
            print(f"⚠️ 축구 승무패 데이터 불일치 감지!")
            print(f"일치율: {soccer_result.match_rate:.1%}")

        # 1시간마다 검증
        await asyncio.sleep(3600)
```

---

## 자주 발생하는 불일치 패턴

### 1. 회차 번호 불일치

**원인**: KSPO API의 `turn_no` 필드가 NULL로 반환되어 추정 회차가 사용됨

**해결**:
- `round_manager.py`의 `_estimate_round_number()` 메서드에서 기준점 업데이트
- 베트맨 크롤러 데이터 사용 권장

### 2. 경기 수 불일치

**원인**:
- API에서 일부 경기가 아직 등록되지 않음 (발매 전)
- API에서 여러 날짜의 경기가 섞여서 반환됨

**해결**:
- 크롤러는 정확히 14경기만 수집하므로 크롤러 데이터 사용
- RoundManager의 날짜 필터링 로직 확인

### 3. 팀명 약어 불일치

**원인**: 베트맨 웹사이트는 짧은 약어 사용, API는 정식 명칭 사용

**해결**:
- `TEAM_NAME_MAPPINGS`에 매핑 추가
- 유사도 계산으로 자동 매칭 (70% 이상)

### 4. 날짜 불일치

**원인**: 크롤러는 실시간 데이터, API는 등록된 날짜 기준

**해결**:
- 크롤러 데이터 사용 권장 (실제 경기 날짜가 더 정확)

---

## API 참조

### DataValidator 클래스

```python
class DataValidator:
    """데이터 검증기"""

    async def compare_sources(
        self,
        game_type: str = "soccer_wdl",
        use_cache: bool = False
    ) -> ValidationResult:
        """
        크롤러 데이터와 API 데이터를 비교하여 불일치 항목 반환

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"
            use_cache: 캐시 사용 여부 (False면 강제 새로고침)

        Returns:
            ValidationResult: 검증 결과
        """

    async def generate_report(
        self,
        game_type: str = "soccer_wdl",
        use_cache: bool = False
    ) -> str:
        """
        마크다운 형식의 검증 보고서 생성

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"
            use_cache: 캐시 사용 여부

        Returns:
            마크다운 형식 보고서
        """

    async def get_validation_summary(
        self,
        game_type: str = "soccer_wdl"
    ) -> Dict:
        """
        검증 결과 요약 (JSON 형식)

        Returns:
            {
                "is_valid": bool,
                "match_rate": float,
                "total_games": int,
                "mismatches_count": int,
                "recommended_source": "crawler" | "api" | "manual",
            }
        """
```

### ValidationResult 데이터클래스

```python
@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool  # 100% 일치 여부
    match_rate: float  # 일치율 0~1
    total_games: int  # 총 경기 수
    matched_games: int  # 일치하는 경기 수
    mismatches: List[Mismatch]  # 불일치 항목들
    crawler_data: Optional[Tuple]  # (RoundInfo, List[Dict])
    api_data: Optional[Tuple]  # (RoundInfo, List[Dict])
    validated_at: datetime  # 검증 시각
```

### Mismatch 데이터클래스

```python
@dataclass
class Mismatch:
    """불일치 항목"""
    game_number: int
    mismatch_type: MismatchType
    field: str  # "home_team", "away_team", "date", "time", "round"
    crawler_value: str
    api_value: str
    similarity: float  # 0~1 유사도
    suggested_action: str  # "use_crawler", "use_api", "manual_review"
    description: str  # 추가 설명
```

---

## 문제 해결

### Q1. 검증이 너무 오래 걸립니다

**A**: 크롤러가 Playwright를 사용하므로 시간이 걸립니다. `use_cache=True`를 사용하면 5분 이내 캐시된 결과를 재사용합니다.

```python
# 빠른 검증 (캐시 사용)
result = await validator.compare_sources("soccer_wdl", use_cache=True)
```

### Q2. 항상 크롤러를 사용하면 되지 않나요?

**A**: 크롤러는 정확하지만 느리고, Playwright 환경이 필요합니다. 프로덕션 환경에서는 API를 우선 사용하고, 불일치 발생 시에만 크롤러로 fallback하는 것이 효율적입니다.

### Q3. 팀명 매핑을 자동으로 학습할 수 있나요?

**A**: 현재는 수동으로 `TEAM_NAME_MAPPINGS`에 추가해야 합니다. 향후 기능으로 검증 이력을 분석하여 자동 학습하는 기능을 추가할 수 있습니다.

---

## 향후 개선 방향

1. **검증 이력 DB 저장**
   - 검증 결과를 DB에 저장하여 추세 분석
   - 특정 경기/팀에서 반복적으로 불일치 발생 시 알림

2. **자동 매핑 학습**
   - 검증 이력에서 팀명 매핑 패턴 학습
   - 유사도 임계값 자동 조정

3. **실시간 모니터링 대시보드**
   - 웹 대시보드에서 검증 결과 시각화
   - 불일치 발생 시 실시간 알림

4. **멀티소스 검증**
   - 베트맨, KSPO API 외에 다른 소스 추가
   - 3개 이상 소스에서 다수결로 정확한 데이터 결정

---

**버전**: 1.0.0
**최종 업데이트**: 2025-12-25
**작성**: AI Assistant
