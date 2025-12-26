# 스포츠 분석 시스템 배포 가이드

## 서버 정보

| 항목 | 값 |
|------|-----|
| IP | 5.161.112.248 |
| 이름 | deep-server |
| 위치 | Ashburn, VA (USA) |
| 사양 | 4 vCPU / 8 GB RAM / 160 GB SSD |
| OS | Ubuntu 24.04 LTS |

---

## 빠른 시작

### 1. 첫 배포 (서버 초기 설정 포함)

```bash
./scripts/deploy-to-server.sh --init
```

이 명령은 다음을 수행합니다:
- Docker 설치
- 2GB Swap 설정
- 방화벽(UFW) 설정
- 코드 업로드
- .env 파일 업로드
- 서비스 시작

### 2. 코드 업데이트

```bash
./scripts/deploy-to-server.sh --update
```

또는 GitHub에 push하면 자동 배포됩니다.

### 3. 기타 명령

```bash
# 서비스 재시작만
./scripts/deploy-to-server.sh --restart

# 실시간 로그 확인
./scripts/deploy-to-server.sh --logs

# 서버 상태 확인
./scripts/deploy-to-server.sh --status
```

---

## GitHub Actions 자동 배포

### 필요한 Secrets 설정

GitHub 저장소 → Settings → Secrets and variables → Actions에서 추가:

| Secret Name | 값 | 설명 |
|-------------|-----|------|
| `HETZNER_SSH_KEY` | 개인키 전체 | SSH 접속용 개인키 |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` | 배포 알림용 |
| `TELEGRAM_CHAT_ID` | `987654321` | 알림 받을 채팅방 |

### SSH 키 생성 및 등록

```bash
# 1. 키 생성 (로컬)
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/hetzner_deploy

# 2. 공개키를 서버에 등록
ssh-copy-id -i ~/.ssh/hetzner_deploy.pub root@5.161.112.248

# 3. 개인키를 GitHub Secrets에 등록
cat ~/.ssh/hetzner_deploy
# 출력된 전체 내용을 HETZNER_SSH_KEY에 저장
```

### 배포 트리거

- **자동**: `main` 브랜치에 push 시
- **수동**: GitHub Actions → Deploy Sports Analysis → Run workflow

---

## 수동 배포 (서버에서 직접)

```bash
# 1. 서버 접속
ssh root@5.161.112.248

# 2. 프로젝트 디렉토리로 이동
cd /root/sports-analysis

# 3. 코드 업데이트 (Git 사용 시)
git pull origin main

# 4. 이미지 빌드 및 재시작
docker compose build
docker compose down
docker compose up -d

# 5. 로그 확인
docker compose logs -f
```

---

## 서비스 구조

```
/root/sports-analysis/
├── docker-compose.yml      # 컨테이너 설정
├── Dockerfile              # 이미지 빌드 설정
├── .env                    # 환경 변수 (비공개)
├── auto_sports_notifier.py # 메인 실행 파일
├── src/                    # 소스 코드
│   └── services/           # 핵심 서비스
└── .state/                 # 상태 저장 (볼륨)
```

### 컨테이너 정보

| 항목 | 값 |
|------|-----|
| 컨테이너명 | `sports_analysis` |
| 포트 | `5001:8000` |
| 메모리 제한 | 1GB |
| CPU 제한 | 0.5 vCPU |
| 실행 모드 | 스케줄러 (6시간 간격) |

---

## 환경 변수 (.env)

서버의 `/root/sports-analysis/.env` 파일에 설정:

```bash
# AI API Keys (최소 1개 필수)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
KIMI_API_KEY=...

# Telegram (필수)
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_CHAT_ID=987654321

# KSPO API (베트맨 데이터)
KSPO_TODZ_API_KEY=...
```

---

## 모니터링

### 컨테이너 상태 확인

```bash
# 컨테이너 상태
docker compose ps

# 리소스 사용량
docker stats sports_analysis

# 실시간 로그
docker compose logs -f --tail=100
```

### 헬스체크

```bash
# 컨테이너 헬스 상태
docker inspect sports_analysis --format='{{.State.Health.Status}}'
```

---

## 문제 해결

### 1. 컨테이너가 시작되지 않음

```bash
# 로그 확인
docker compose logs sports_analysis

# 일반적인 원인:
# - .env 파일 누락
# - API 키 오류
# - 포트 충돌
```

### 2. Playwright 브라우저 오류

```bash
# 컨테이너 내부에서 Playwright 재설치
docker compose exec sports_analysis playwright install chromium
docker compose restart
```

### 3. 메모리 부족

```bash
# Swap 확인
free -h

# Swap이 없으면 추가
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
```

### 4. 볼륨 데이터 백업

```bash
# 상태 데이터 백업
docker run --rm -v sports-analysis_sports_state:/data -v $(pwd):/backup alpine tar czf /backup/state-backup.tar.gz /data
```

---

## 롤백

```bash
# 이전 커밋으로 롤백
cd /root/sports-analysis
git checkout HEAD~1

# 재빌드 및 재시작
docker compose build
docker compose down
docker compose up -d
```

---

## 보안 설정

### 방화벽 (UFW)

```bash
# 현재 규칙 확인
ufw status

# 필요한 포트만 열기
ufw allow 22/tcp    # SSH
ufw allow 5001/tcp  # 스포츠 분석 API
```

### Fail2Ban (선택)

```bash
# 설치
apt install fail2ban -y

# SSH 보호 활성화
systemctl enable fail2ban
systemctl start fail2ban
```

---

**작성일**: 2025-12-27
**버전**: 1.0.0
