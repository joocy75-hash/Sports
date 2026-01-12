# 6시간마다 텔레그램 알림 설정 가이드

## 빠른 설정 (3분 완성)

서버에 SSH 접속 후 다음 명령어를 순서대로 실행하세요:

```bash
# 1. 서버 접속
ssh root@141.164.55.245

# 2. 작업 디렉토리로 이동
cd /opt/sports-analysis

# 3. 서비스 파일 확인 및 설치
sudo cp sports-scheduler.service /etc/systemd/system/sports-scheduler.service
sudo systemctl daemon-reload

# 4. 서비스 활성화
sudo systemctl enable sports-scheduler

# 5. 서비스 재시작
sudo systemctl restart sports-scheduler

# 6. 상태 확인
systemctl status sports-scheduler
```

## 자동 설정 스크립트 사용 (추천)

로컬에서 실행:

```bash
# 방법 1: 자동 설정 스크립트 실행
./setup_scheduler.sh 141.164.55.245

# 방법 2: 서버에서 직접 실행 (서버에 접속 후)
# 먼저 스크립트를 서버로 전송
scp fix_scheduler.sh root@141.164.55.245:/tmp/
ssh root@141.164.55.245 'bash /tmp/fix_scheduler.sh'
```

## 단계별 상세 설정

### 1단계: 서버 접속
```bash
ssh root@141.164.55.245
```

### 2단계: 작업 디렉토리로 이동
```bash
cd /opt/sports-analysis
```

### 3단계: 필수 파일 확인
```bash
# scheduler_main.py 확인
ls -la scheduler_main.py

# .env 파일 확인 (텔레그램 설정)
grep TELEGRAM .env

# sports-scheduler.service 확인
cat sports-scheduler.service
```

### 4단계: Systemd 서비스 파일 설치
```bash
# 서비스 파일 복사
sudo cp sports-scheduler.service /etc/systemd/system/sports-scheduler.service

# Systemd 데몬 리로드
sudo systemctl daemon-reload
```

### 5단계: 서비스 활성화 및 시작
```bash
# 서비스 활성화 (부팅 시 자동 시작)
sudo systemctl enable sports-scheduler

# 서비스 시작
sudo systemctl start sports-scheduler

# 서비스 상태 확인
systemctl status sports-scheduler
```

### 6단계: 스케줄러 상태 확인
```bash
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status
```

**확인 사항**:
- "새 회차 체크: 6시간마다" 작업이 등록되어 있는지
- 다음 실행 시간이 표시되는지

### 7단계: 로그 확인
```bash
# 최근 로그 확인 (50줄)
journalctl -u sports-scheduler -n 50

# 실시간 로그 확인
journalctl -u sports-scheduler -f
```

## 문제 해결

### 문제 1: 서비스가 시작되지 않음

```bash
# 에러 로그 확인
journalctl -u sports-scheduler -n 100 -p err

# 수동 실행 테스트
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status
```

**일반적인 원인**:
- `.env` 파일 없음 → `.env` 파일 생성 필요
- Python 가상환경 없음 → `python3 -m venv venv` 실행 필요
- 의존성 패키지 없음 → `pip install -r requirements.txt` 실행 필요

### 문제 2: 텔레그램 알림이 오지 않음

```bash
# 텔레그램 설정 확인
cd /opt/sports-analysis
grep TELEGRAM .env

# 텔레그램 테스트
cd /opt/sports-analysis
source venv/bin/activate
python -c "
from src.services.telegram_notifier import TelegramNotifier
import asyncio
async def test():
    notifier = TelegramNotifier()
    await notifier.send_message('테스트 메시지')
asyncio.run(test())
"
```

### 문제 3: 서비스가 계속 재시작됨

```bash
# 상세 로그 확인
journalctl -u sports-scheduler -n 100

# 서비스 파일 확인
cat /etc/systemd/system/sports-scheduler.service

# Python 경로 확인
which python3
```

### 문제 4: 스케줄러가 6시간마다 실행되지 않음

```bash
# 스케줄러 상태 확인
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status

# 서비스 재시작
sudo systemctl restart sports-scheduler

# 재시작 후 로그 확인
journalctl -u sports-scheduler -n 50 -f
```

## 정상 작동 확인 체크리스트

- [ ] `systemctl status sports-scheduler` → `Active: active (running)`
- [ ] `ps aux | grep scheduler_main` → 프로세스 실행 중
- [ ] `python scheduler_main.py --status` → "새 회차 체크: 6시간마다" 표시
- [ ] 다음 실행 시간이 표시됨
- [ ] `journalctl -u sports-scheduler -n 50` → 에러 없음
- [ ] `.env` 파일에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 설정됨
- [ ] 텔레그램 테스트 메시지 전송 성공

## 자동 재시작 설정 (이미 포함됨)

`sports-scheduler.service` 파일에 다음 설정이 포함되어 있습니다:

```
Restart=always
RestartSec=10
```

서비스가 비정상 종료되면 10초 후 자동으로 재시작됩니다.

## 모니터링 명령어

### 실시간 로그 확인
```bash
journalctl -u sports-scheduler -f
```

### 최근 100줄 로그
```bash
journalctl -u sports-scheduler -n 100
```

### 오늘 로그만 확인
```bash
journalctl -u sports-scheduler --since today
```

### 에러 로그만 확인
```bash
journalctl -u sports-scheduler -p err -n 50
```

### 스케줄러 상태 확인
```bash
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status
```

## 예상 결과

설정이 완료되면:

1. **서비스 상태**: `Active: active (running)`
2. **스케줄러 상태**: 다음 실행 시간이 표시됨
   - 새 회차 체크: 6시간마다 (예: 다음 실행: 2026-01-XX 15:00:00)
   - 결과 수집: 매일 06:00
   - 일일 상태: 매일 21:00
3. **로그**: "✅ 스케줄러 가동 중..." 메시지 확인
4. **텔레그램 알림**: 6시간마다 새 회차 체크 후 알림 전송

## 추가 도움말

문제가 계속되면 다음 정보를 확인하세요:

1. 서비스 상태: `systemctl status sports-scheduler`
2. 최근 로그: `journalctl -u sports-scheduler -n 100`
3. 스케줄러 상태: `python scheduler_main.py --status`
4. 텔레그램 설정: `grep TELEGRAM .env`

