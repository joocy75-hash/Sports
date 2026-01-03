# 팀 통계 변환 로직 구현 가이드

## 개요

실시간 팀 통계 시스템이 구축되었으나, **API 응답 데이터를 어떻게 점수화할지**는 사용자의 전략적 결정이 필요합니다.

## 현재 상태

### ✅ 완료된 작업 (Phase 1)

1. **3-tier 캐싱 시스템** - 메모리 → 파일 → API 순서로 폴백
2. **Multi-provider 구조** - API-Football (축구) + BallDontLie (농구)
3. **Fallback 메커니즘** - API 실패 시 기본값으로 안전하게 폴백
4. **TotoService 통합** - 실시간 통계를 사용하도록 연결 완료
5. **성능 최적화** - 14경기 처리 시간 0.00초 (캐시 적중 시)

### ⚠️ 구현 필요한 작업

**파일**: `src/services/stats_providers/api_football_provider.py`
**메서드**: `_convert_to_team_stats()`

```python
def _convert_to_team_stats(
    self,
    team_name: str,
    league: str,
    stats_data: Dict[str, Any],  # ← API-Football 응답
    is_home: bool
) -> TeamStats:
    """
    API-Football 응답을 TeamStats로 변환

    현재 상태: 모든 팀이 기본값 (50.0) 반환
    목표: stats_data를 분석하여 실제 레이팅 계산
    """
```

## API 응답 구조 분석

### API-Football 응답 예시

```json
{
  "team": {
    "id": 33,
    "name": "Manchester United",
    "logo": "https://..."
  },
  "league": {
    "id": 39,
    "name": "Premier League",
    "season": 2025
  },
  "form": "WWDLL",  // 최근 5경기 폼
  "fixtures": {
    "played": {
      "home": 19,
      "away": 19,
      "total": 38
    },
    "wins": {
      "home": 12,
      "away": 8,
      "total": 20
    },
    "draws": {
      "home": 4,
      "away": 6,
      "total": 10
    },
    "loses": {
      "home": 3,
      "away": 5,
      "total": 8
    }
  },
  "goals": {
    "for": {
      "total": {
        "home": 42,
        "away": 31,
        "total": 73
      },
      "average": {
        "home": "2.2",
        "away": "1.6",
        "total": "1.9"
      }
    },
    "against": {
      "total": {
        "home": 18,
        "away": 24,
        "total": 42
      },
      "average": {
        "home": "0.9",
        "away": "1.3",
        "total": "1.1"
      }
    }
  },
  "clean_sheet": {
    "home": 8,
    "away": 5,
    "total": 13
  },
  "failed_to_score": {
    "home": 2,
    "away": 4,
    "total": 6
  }
}
```

## 구현 가이드

### 1. attack_rating 계산 (0-100점)

**고려할 지표**:
- `goals.for.average.total` - 경기당 평균 득점
- `form` - 최근 폼 (W=승리, D=무승부, L=패배)
- `clean_sheet` vs `failed_to_score` 비율

**예시 공식 (자유롭게 수정 가능)**:
```python
avg_goals_scored = float(stats_data["goals"]["for"]["average"]["total"])

# 득점력 점수화 (0-100)
# 리그 평균 1.5골 기준, 2.0골 이상이면 80점 이상
attack_rating = min(100, (avg_goals_scored / 2.0) * 80 + 20)

# 폼 보정 (최근 5경기 승리 많으면 +10점)
form = stats_data.get("form", "")
win_count = form.count("W")
attack_rating += (win_count / 5) * 10
```

### 2. defense_rating 계산 (0-100점)

**고려할 지표**:
- `goals.against.average.total` - 경기당 평균 실점
- `clean_sheet.total` - 무실점 경기 수
- `fixtures.played.total` - 총 경기 수

**예시 공식**:
```python
avg_goals_conceded = float(stats_data["goals"]["against"]["average"]["total"])

# 수비력 점수화 (실점 적을수록 높은 점수)
# 0.5골 이하 실점이면 90점 이상, 2.0골 이상이면 20점 이하
defense_rating = max(20, 100 - (avg_goals_conceded / 2.0) * 80)

# 클린시트 보정
clean_sheet_rate = stats_data["clean_sheet"]["total"] / stats_data["fixtures"]["played"]["total"]
defense_rating += clean_sheet_rate * 20
defense_rating = min(100, defense_rating)
```

### 3. recent_form 계산 (0-100점)

**고려할 지표**:
- `form` - 최근 5경기 결과
- 가중치: 승리=3점, 무승부=1점, 패배=0점

**예시 공식**:
```python
form = stats_data.get("form", "")
form_points = 0

# 최근 5경기 점수 계산
for i, result in enumerate(reversed(form)):
    weight = (i + 1) / 5  # 최근 경기일수록 가중치 높음
    if result == "W":
        form_points += 3 * weight
    elif result == "D":
        form_points += 1 * weight

# 0-100 정규화 (최대 3 * 5 = 15점)
recent_form = (form_points / 15) * 100
```

### 4. win_rate 계산 (0.0-1.0)

```python
wins = stats_data["fixtures"]["wins"]["total"]
played = stats_data["fixtures"]["played"]["total"]
win_rate = wins / played if played > 0 else 0.5
```

### 5. home_advantage 계산

**옵션 A: 고정값**
```python
home_advantage = 5.0 if is_home else 0.0
```

**옵션 B: 통계 기반**
```python
if is_home:
    home_win_rate = stats_data["fixtures"]["wins"]["home"] / stats_data["fixtures"]["played"]["home"]
    away_win_rate = stats_data["fixtures"]["wins"]["away"] / stats_data["fixtures"]["played"]["away"]
    home_advantage = (home_win_rate - away_win_rate) * 50  # 0-10점 범위
else:
    home_advantage = 0.0
```

## 구현 위치

### 축구 (api_football_provider.py)

```python
def _convert_to_team_stats(
    self,
    team_name: str,
    league: str,
    stats_data: Dict[str, Any],
    is_home: bool
) -> TeamStats:
    """API-Football 응답 → TeamStats 변환"""

    # ========== 여기에 사용자 로직 구현 ==========

    # 1. 기본 통계 추출
    avg_goals_scored = float(stats_data["goals"]["for"]["average"]["total"])
    avg_goals_conceded = float(stats_data["goals"]["against"]["average"]["total"])
    form = stats_data.get("form", "")

    # 2. 레이팅 계산
    attack_rating = ...  # 사용자 구현
    defense_rating = ...  # 사용자 구현
    recent_form = ...  # 사용자 구현

    # 3. 승률 계산
    wins = stats_data["fixtures"]["wins"]["total"]
    played = stats_data["fixtures"]["played"]["total"]
    win_rate = wins / played if played > 0 else 0.5

    # 4. 홈 어드밴티지
    home_advantage = ...  # 사용자 선택

    # ============================================

    return TeamStats(
        team_name=team_name,
        league=league,
        attack_rating=attack_rating,
        defense_rating=defense_rating,
        recent_form=recent_form,
        win_rate=win_rate,
        home_advantage=home_advantage,
        avg_goals_scored=avg_goals_scored,
        avg_goals_conceded=avg_goals_conceded,
        last_updated=datetime.now(),
        source=self.provider_name,
    )
```

### 농구 (balldontlie_provider.py)

```python
def _convert_to_team_stats(
    self,
    team_name: str,
    league: str,
    stats_data: Dict[str, Any],
    is_home: bool
) -> TeamStats:
    """BallDontLie 응답 → TeamStats 변환"""

    # BallDontLie API 응답 예시:
    # {
    #     "games_played": 40,
    #     "min": "33.5",
    #     "fgm": "8.2",    # Field Goals Made
    #     "fga": "18.1",   # Field Goals Attempted
    #     "fg_pct": "0.453",
    #     "fg3m": "2.5",   # 3-Pointers Made
    #     "fg3a": "6.8",
    #     "fg3_pct": "0.368",
    #     "ftm": "3.2",    # Free Throws Made
    #     "fta": "4.1",
    #     "ft_pct": "0.780",
    #     "oreb": "1.2",   # Offensive Rebounds
    #     "dreb": "4.5",   # Defensive Rebounds
    #     "reb": "5.7",    # Total Rebounds
    #     "ast": "5.1",    # Assists
    #     "stl": "1.2",    # Steals
    #     "blk": "0.6",    # Blocks
    #     "turnover": "2.1",
    #     "pf": "2.5",     # Personal Fouls
    #     "pts": "22.1"    # Points
    # }

    # ========== 여기에 사용자 로직 구현 ==========

    # 농구는 득점/실점 외에도 FG%, 리바운드, 어시스트 등 고려
    avg_points_scored = float(stats_data.get("pts", 105.0))

    # 공격 레이팅: 득점 + FG% + 어시스트
    fg_pct = float(stats_data.get("fg_pct", 0.45))
    assists = float(stats_data.get("ast", 20.0))
    attack_rating = ...  # 사용자 구현

    # 수비 레이팅: 리바운드 + 스틸 + 블록
    rebounds = float(stats_data.get("reb", 40.0))
    steals = float(stats_data.get("stl", 7.0))
    blocks = float(stats_data.get("blk", 4.0))
    defense_rating = ...  # 사용자 구현

    # ============================================

    return TeamStats(
        team_name=team_name,
        league=league,
        attack_rating=attack_rating,
        defense_rating=defense_rating,
        recent_form=recent_form,
        win_rate=win_rate,
        home_advantage=3.0 if is_home else 0.0,  # 농구는 보통 2-3점
        avg_points_scored=avg_points_scored,
        avg_points_conceded=105.0,  # TODO: 상대팀 평균 조회 필요
        last_updated=datetime.now(),
        source=self.provider_name,
    )
```

## 테스트 방법

1. 위 로직 구현 후 테스트 실행:
```bash
python3 test_team_stats.py
```

2. 결과 확인:
```
팀명: 맨체스U
공격 레이팅: 75.3  ← 기본값 50.0에서 변경됨!
수비 레이팅: 68.2  ← 실제 통계 반영
데이터 소스: api_football  ← 성공!
```

3. 캐시 효율 확인:
```
캐시 적중률: 85.7%  ← 목표 80% 달성!
총 API 호출: 2회   ← Free tier 충분
```

## 다음 단계

이 작업 완료 후:
- ✅ Phase 1 완료: 실시간 팀 통계 연동
- ⏭️ Phase 2 시작: 과거 적중률 추적 자동화
- ⏭️ Phase 3 시작: 자동 스케줄러 (6시간 간격)

---

**구현 우선순위**:
1. **간단한 공식으로 시작** - 위 예시 공식 사용
2. **실제 데이터로 검증** - 몇 경기 예측해보고 정확도 확인
3. **점진적 개선** - 정확도 낮으면 가중치 조정

**핵심 원칙**:
> 완벽한 공식은 없다. 시작하고, 측정하고, 개선하라!
