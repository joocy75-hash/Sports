# AI 작업자 핸드오프 가이드

> **버전**: 1.0.0
> **작성일**: 2026-01-10
> **목적**: 다중 AI 계정 사용 시 작업 연속성 보장

---

## 핸드오프 개요

이 프로젝트는 여러 AI 계정(GPT, Claude 등)을 사용하여 개발됩니다.
각 작업자가 작업을 완료할 때마다 다음 작업자가 원활하게 이어받을 수 있도록 이 가이드를 따르세요.

---

## 작업 시작 전 체크리스트

### 1. 필수 문서 읽기

```bash
# 반드시 이 순서로 읽으세요!
1. CLAUDE.md                    # 프로젝트 전체 가이드 (필수!)
2. docs/REALTIME_DATA_INTEGRATION_PLAN.md  # 현재 진행 중인 대규모 작업
3. .claude/skills/*.md          # 활성 스킬 파일들
```

### 2. 현재 상태 확인

```bash
# Git 상태
git status
git log --oneline -5

# 프로덕션 서버 상태
ssh root@141.164.55.245 "docker ps"
ssh root@141.164.55.245 "docker logs sports_analysis --tail=20"

# 현재 버전
cat CLAUDE.md | grep -E "^버전|버전:"
```

### 3. 이전 작업자 메모 확인

`.claude/skills/` 디렉토리의 스킬 파일에서 **"마지막 완료 작업"** 섹션을 확인하세요.

---

## 작업 완료 시 체크리스트

### 1. 코드 테스트

```bash
# 통합 테스트 (필수!)
python3 auto_sports_notifier.py --soccer --test
python3 auto_sports_notifier.py --basketball --test

# 특정 모듈 테스트 (해당하는 경우)
python3 -m pytest tests/ -v
```

### 2. Git Commit (상세 메시지 필수!)

```bash
git add .
git commit -m "feat/fix/docs: 작업 제목

- 구현 내용 1
- 구현 내용 2
- 테스트 결과

Phase: X.Y (해당하는 경우)
완료된 체크리스트 항목: 항목명

Co-Authored-By: Claude [Model] <noreply@anthropic.com>"
```

### 3. Git Push (자동 배포)

```bash
git push origin main

# GitHub Actions 확인
# https://github.com/joocy75-hash/Sports/actions
```

### 4. 배포 확인

```bash
# 서버 Git 커밋 확인
ssh root@141.164.55.245 "cd /opt/sports-analysis && git log --oneline -1"

# 컨테이너 재시작 확인
ssh root@141.164.55.245 "docker ps"

# 에러 로그 확인
ssh root@141.164.55.245 "docker logs sports_analysis --tail=30 2>&1 | grep -E 'ERROR|실패'"
```

### 5. 스킬 파일 업데이트 (매우 중요!)

해당 스킬 파일(`.claude/skills/*.md`)의 체크리스트를 업데이트하세요:

```markdown
### 마지막 완료 작업

Phase: 1.1
작업 내용: TeamStats 데이터클래스 정의
완료일: 2026-01-10
담당 AI: Claude Opus 4.5
커밋: abc1234

### 다음 작업 추천

Phase: 1.1
작업 내용: Football-Data.org API 연동
예상 난이도: 중간
선행 조건: TeamStats 데이터클래스 완료 ✅
```

### 6. CLAUDE.md 업데이트 (대규모 변경 시)

대규모 변경이나 버전 업데이트 시 CLAUDE.md의 다음 섹션을 업데이트하세요:

- 섹션 10: 현재 구현 상태
- 섹션 12-3: 현재 프로덕션 배포 상태
- 섹션 13: 변경 이력

---

## 핸드오프 템플릿

작업 완료 시 다음 템플릿을 사용하여 메시지를 남기세요:

```
## 작업 완료 보고

### 완료된 작업
- [Phase X.Y] 작업명
- 구현 내용 요약

### 커밋 정보
- 커밋 해시: abc1234
- 브랜치: main
- 배포 상태: ✅ 완료

### 테스트 결과
- python3 auto_sports_notifier.py --test: ✅ 성공
- 에러: 없음

### 다음 작업자에게
- 다음 작업: [Phase X.Y] 작업명
- 주의사항: (있으면)
- 참고 파일: (관련 파일 경로)

### 발견된 이슈
- (있으면 기록)
```

---

## 긴급 상황 대응

### 배포 실패 시

```bash
# 1. GitHub Actions 로그 확인
# https://github.com/joocy75-hash/Sports/actions

# 2. 서버에서 수동 배포 (긴급 시에만!)
ssh root@141.164.55.245
cd /opt/sports-analysis
git pull origin main
docker-compose down && docker-compose up -d --build
docker logs sports_analysis --tail=50
```

### 시스템 오류 시

```bash
# 1. 컨테이너 재시작
ssh root@141.164.55.245 "docker restart sports_analysis"

# 2. 로그 확인
ssh root@141.164.55.245 "docker logs sports_analysis --tail=100"

# 3. 이전 커밋으로 롤백 (필요시)
git revert HEAD
git push origin main
```

---

## 금지 사항

### 절대 하지 말 것

1. ❌ 원격 서버에서 직접 코드 수정
2. ❌ `git push --force` 사용
3. ❌ 테스트 없이 배포
4. ❌ 스킬 파일 체크리스트 업데이트 없이 완료
5. ❌ 이변 감지 로직 약화
6. ❌ 14경기 검증 로직 제거

### 반드시 할 것

1. ✅ CLAUDE.md 먼저 읽기
2. ✅ 테스트 후 배포
3. ✅ 상세한 커밋 메시지
4. ✅ 스킬 파일 체크리스트 업데이트
5. ✅ 다음 작업자를 위한 인수인계 메모

---

## 프로젝트 핵심 규칙

```
⭐ 최우선: 이변 감지 = 시스템의 핵심 가치

1. 배당 없이 AI가 직접 확률 계산
2. 5개 AI 앙상블 → AI 불일치 = 이변 신호
3. 14경기 전체 마킹 + 복수 4경기 (반드시!)
4. 젠토토 → 베트맨 → KSPO API 순서
5. 로컬 개발 → Git Push → GitHub Actions 배포
```

---

## 연락처 및 리소스

- **GitHub**: https://github.com/joocy75-hash/Sports
- **프로덕션 서버**: `ssh root@141.164.55.245`
- **프로젝트 경로**: `/opt/sports-analysis`
- **Docker 컨테이너**: `sports_analysis`

---

**가이드 버전**: 1.0.0
**최종 수정**: 2026-01-10
