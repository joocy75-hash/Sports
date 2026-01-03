# 프로토 14경기 AI 분석 시스템 - 배포 가이드

**버전**: 3.3.0 (Phase 3 완료)
**최종 업데이트**: 2026-01-03

---

## 📋 목차

1. [시스템 요구사항](#시스템-요구사항)
2. [로컬 개발 환경](#로컬-개발-환경)
3. [Docker 배포](#docker-배포)
4. [Systemd 서비스 배포](#systemd-서비스-배포)
5. [모니터링 및 로그](#모니터링-및-로그)
6. [문제 해결](#문제-해결)

---

## 시스템 요구사항

### 최소 사양
- **OS**: Ubuntu 20.04+ / Debian 11+ / macOS
- **RAM**: 2GB 이상
- **디스크**: 10GB 이상
- **Python**: 3.11+
- **PostgreSQL**: 15+ (선택사항)

### 필수 패키지
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip python3-venv

# macOS
brew install python@3.11
```

---

## 로컬 개발 환경

### 1. 프로젝트 클론
```bash
cd ~/Desktop
git clone <repository-url> 스포츠분석
cd 스포츠분석
```

### 2. 가상환경 설정
```bash
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt

# Playwright 브라우저 설치 (베트맨 크롤러용)
playwright install chromium
```

### 4. 환경 변수 설정
```bash
cp .env.example .env
nano .env
```

**필수 환경 변수**:
```bash
# 텔레그램 (필수)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# AI API 키 (최소 1개)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
DEEPSEEK_API_KEY=...
KIMI_API_KEY=...

# KSPO API
KSPO_TODZ_API_KEY=...

# 데이터베이스 (선택)
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost/sports_analysis
```

### 5. 테스트 실행
```bash
# 통합 테스트
python3 test_hit_rate_system.py

# 예측 생성 테스트
python3 auto_sports_notifier.py --test

# 스케줄러 상태 확인
python3 scheduler_main.py --status
```

---

## Docker 배포

### 1. Dockerfile 확인
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 설치
RUN playwright install chromium
RUN playwright install-deps chromium

# 프로젝트 복사
COPY . .

# 상태 디렉토리 생성
RUN mkdir -p .state/predictions/soccer_wdl .state/predictions/basketball_w5l .state/results

# 기본 명령어
CMD ["python", "scheduler_main.py"]
```

### 2. Docker Compose로 실행
```bash
# 스케줄러 + DB 실행
docker-compose -f docker-compose.scheduler.yml up -d

# 로그 확인
docker-compose -f docker-compose.scheduler.yml logs -f scheduler

# 중지
docker-compose -f docker-compose.scheduler.yml down
```

### 3. Docker 명령어
```bash
# 빌드
docker build -t sports-scheduler .

# 실행
docker run -d \
  --name sports-scheduler \
  --env-file .env \
  -v $(pwd)/.state:/app/.state \
  -v $(pwd)/scheduler.log:/app/scheduler.log \
  sports-scheduler

# 상태 확인
docker exec sports-scheduler python scheduler_main.py --status

# 특정 작업 실행
docker exec sports-scheduler python scheduler_main.py --run-now daily

# 로그 확인
docker logs -f sports-scheduler

# 중지 및 삭제
docker stop sports-scheduler
docker rm sports-scheduler
```

---

## Systemd 서비스 배포

### 1. 서버에 프로젝트 배포
```bash
# 로컬에서 서버로 전송
rsync -avz --exclude 'venv' --exclude '.git' \
  ~/Desktop/스포츠분석/ \
  root@YOUR_SERVER_IP:/opt/sports-analysis/

# 또는 Git 사용
ssh root@YOUR_SERVER_IP
cd /opt
git clone <repository-url> sports-analysis
cd sports-analysis
```

### 2. 서버 환경 설정
```bash
# SSH 접속
ssh root@YOUR_SERVER_IP

# Python 가상환경 생성
cd /opt/sports-analysis
python3.11 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium

# 환경 변수 설정
nano .env
# (필수 환경 변수 입력)
```

### 3. Systemd 서비스 등록
```bash
# 서비스 파일 복사
sudo cp sports-scheduler.service /etc/systemd/system/

# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable sports-scheduler
sudo systemctl start sports-scheduler

# 상태 확인
sudo systemctl status sports-scheduler

# 로그 확인
sudo journalctl -u sports-scheduler -f
```

### 4. 서비스 관리 명령어
```bash
# 시작
sudo systemctl start sports-scheduler

# 중지
sudo systemctl stop sports-scheduler

# 재시작
sudo systemctl restart sports-scheduler

# 상태 확인
sudo systemctl status sports-scheduler

# 실시간 로그
sudo journalctl -u sports-scheduler -f

# 최근 100줄 로그
sudo journalctl -u sports-scheduler -n 100

# 오늘 로그만
sudo journalctl -u sports-scheduler --since today
```

---

## 모니터링 및 로그

### 1. 로그 파일 위치
```
로컬/Docker:
  - scheduler.log (메인 로그)
  - .state/ (상태 파일)

Systemd:
  - /var/log/sports-scheduler.log (표준 출력)
  - /var/log/sports-scheduler-error.log (에러 로그)
  - journalctl -u sports-scheduler (시스템 로그)
```

### 2. 스케줄러 상태 확인
```bash
# 로컬
python3 scheduler_main.py --status

# Docker
docker exec sports-scheduler python scheduler_main.py --status

# Systemd
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status
```

**출력 예시**:
```
============================================================
📊 스케줄러 상태
============================================================

상태: 🟢 실행 중

📋 등록된 작업:
  • 새 회차 체크 및 분석
    다음 실행: 2026-01-04 02:00:00
  • 결과 수집 및 리포트
    다음 실행: 2026-01-04 06:00:00
  • 주간 요약 리포트
    다음 실행: 2026-01-06 09:00:00
  • 일일 상태 리포트
    다음 실행: 2026-01-03 21:00:00

📊 마지막 처리:
  • 축구: 152회차
  • 농구: 47회차
  • 마지막 결과 수집: 2026-01-03 06:00:00

============================================================
```

### 3. 수동 작업 실행
```bash
# 새 회차 체크
python3 scheduler_main.py --run-now check

# 결과 수집
python3 scheduler_main.py --run-now results

# 주간 요약
python3 scheduler_main.py --run-now weekly

# 일일 상태
python3 scheduler_main.py --run-now daily

# 모든 작업 테스트
python3 scheduler_main.py --test-jobs
```

---

## 문제 해결

### 1. 스케줄러가 시작하지 않을 때

**증상**: `systemctl status` 실행 시 failed 상태

**해결 방법**:
```bash
# 1. 로그 확인
sudo journalctl -u sports-scheduler -n 50

# 2. 환경 변수 확인
cat /opt/sports-analysis/.env | grep TELEGRAM

# 3. Python 경로 확인
which python3

# 4. 수동 실행 테스트
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status
```

### 2. 텔레그램 알림이 오지 않을 때

**확인 사항**:
```bash
# 1. 봇 토큰 확인
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# 2. Chat ID 확인
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates

# 3. 수동 메시지 전송 테스트
python3 -c "
import asyncio
from src.services.telegram_notifier import TelegramNotifier
async def test():
    notifier = TelegramNotifier()
    await notifier.send_message('테스트 메시지')
asyncio.run(test())
"
```

### 3. 베트맨 크롤러 오류

**증상**: `Playwright` 관련 오류

**해결 방법**:
```bash
# Playwright 재설치
pip install --upgrade playwright
playwright install chromium
playwright install-deps chromium

# 또는 Docker에서
docker exec sports-scheduler playwright install chromium
```

### 4. 메모리 부족

**증상**: 시스템이 느려지거나 크래시

**해결 방법**:
```bash
# 1. 메모리 사용량 확인
free -h

# 2. 스왑 메모리 추가 (2GB)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 5. 로그 파일이 너무 클 때

**해결 방법**:
```bash
# 로그 로테이션 설정
sudo nano /etc/logrotate.d/sports-scheduler

# 내용:
/var/log/sports-scheduler*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}

# 수동 로테이션
sudo logrotate -f /etc/logrotate.d/sports-scheduler
```

---

## 스케줄 작업 상세

### 1. 새 회차 체크 및 분석
- **스케줄**: 6시간마다
- **기능**:
  - 베트맨 크롤러로 새 회차 확인
  - AI 앙상블 분석
  - 예측 자동 저장
  - 텔레그램 예측 알림

### 2. 결과 수집 및 리포트
- **스케줄**: 매일 06:00
- **기능**:
  - 미수집 회차 자동 검색
  - KSPO API 결과 수집
  - 적중률 계산
  - 리포트 생성 및 전송

### 3. 주간 요약 리포트
- **스케줄**: 매주 월요일 09:00
- **기능**:
  - 주간 누적 통계
  - 평균 적중률
  - 전체 적중 횟수

### 4. 일일 상태 리포트
- **스케줄**: 매일 21:00
- **기능**:
  - 시스템 가동 상태
  - 오늘 처리 작업
  - 예측 회차 수

---

## 업그레이드

### 로컬/Systemd
```bash
cd /opt/sports-analysis
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart sports-scheduler
```

### Docker
```bash
docker-compose -f docker-compose.scheduler.yml down
docker-compose -f docker-compose.scheduler.yml build
docker-compose -f docker-compose.scheduler.yml up -d
```

---

## 백업

### 중요 파일
```bash
# 상태 파일 백업
tar -czf state-backup-$(date +%Y%m%d).tar.gz .state/

# 환경 변수 백업 (주의: 비밀 정보 포함)
cp .env .env.backup

# 데이터베이스 백업 (PostgreSQL 사용 시)
pg_dump -U postgres sports_analysis > backup-$(date +%Y%m%d).sql
```

### 복원
```bash
# 상태 파일 복원
tar -xzf state-backup-20260103.tar.gz

# 데이터베이스 복원
psql -U postgres sports_analysis < backup-20260103.sql
```

---

**문의 및 이슈 리포트**: GitHub Issues 또는 텔레그램으로 연락

**버전**: 3.3.0
**작성일**: 2026-01-03
