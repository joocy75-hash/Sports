# 서버 상태 확인 가이드

## 서버 정보
- **IP 주소**: `141.164.55.245` (한국 서울)
- **사용자**: `root`
- **서비스명**: `sports-scheduler`
- **경로**: `/opt/sports-analysis`

## 빠른 확인 방법

### 방법 1: 원격 실행 (추천)
로컬 터미널에서 실행:
```bash
# 서버 상태 확인 스크립트 실행
ssh root@141.164.55.245 'bash -s' < check_server_status.sh

# 또는 직접 명령어 실행
./check_deployment.sh 141.164.55.245
```

### 방법 2: 서버에 직접 접속
```bash
# 서버 접속
ssh root@141.164.55.245

# 서버에 접속한 후 아래 명령어 실행
cd /opt/sports-analysis
bash check_server_status.sh
```

## 주요 확인 항목

### 1. 서비스 상태 확인
```bash
systemctl status sports-scheduler
```

**정상 상태**: `Active: active (running)`
**문제 상태**: `Active: inactive (dead)` 또는 `Active: failed`

### 2. 최근 로그 확인 (50줄)
```bash
journalctl -u sports-scheduler -n 50 --no-pager
```

### 3. 실시간 로그 확인
```bash
journalctl -u sports-scheduler -f
```

### 4. 스케줄러 상태 확인
```bash
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status
```

**확인 사항**:
- 다음 실행 시간이 표시되는지
- "새 회차 체크" 작업이 6시간 간격으로 설정되어 있는지

### 5. 스케줄러 프로세스 확인
```bash
ps aux | grep scheduler_main | grep -v grep
```

프로세스가 없으면 서비스가 실행되지 않는 것입니다.

### 6. 텔레그램 설정 확인
```bash
cd /opt/sports-analysis
grep TELEGRAM .env
```

`TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID`가 설정되어 있어야 합니다.

### 7. 스케줄러 로그 파일 확인
```bash
cd /opt/sports-analysis
tail -50 scheduler.log
```

## 문제 해결

### 문제 1: 서비스가 실행되지 않음

```bash
# 서비스 시작
systemctl start sports-scheduler

# 서비스 상태 확인
systemctl status sports-scheduler

# 에러 로그 확인
journalctl -u sports-scheduler -n 100 -p err
```

### 문제 2: 서비스가 시작되지 않음

```bash
# 상세 로그 확인
journalctl -u sports-scheduler -n 100

# 수동 실행 테스트
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status

# 환경 변수 확인
cat .env | grep -E "TELEGRAM|DATABASE"
```

### 문제 3: 텔레그램 알림이 오지 않음

```bash
# 텔레그램 설정 확인
cd /opt/sports-analysis
grep TELEGRAM .env

# 텔레그램 테스트 (서버에서 직접 실행)
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

### 문제 4: 스케줄러가 6시간마다 실행되지 않음

```bash
# 스케줄러 상태 확인
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status

# 서비스 재시작
systemctl restart sports-scheduler

# 재시작 후 상태 확인
systemctl status sports-scheduler
journalctl -u sports-scheduler -n 30
```

### 문제 5: 서비스 재시작

```bash
# 서비스 재시작
systemctl restart sports-scheduler

# 재시작 후 로그 확인
journalctl -u sports-scheduler -n 50 -f
```

## 전체 확인 스크립트 (서버에 접속한 후)

서버에 접속한 후 다음 명령어를 실행하면 모든 상태를 한번에 확인할 수 있습니다:

```bash
cd /opt/sports-analysis && bash check_server_status.sh
```

또는 로컬에서:
```bash
scp check_server_status.sh root@141.164.55.245:/tmp/
ssh root@141.164.55.245 'bash /tmp/check_server_status.sh'
```

## 예상되는 정상 상태

1. **서비스 상태**: `Active: active (running)`
2. **프로세스**: `scheduler_main.py` 프로세스가 실행 중
3. **스케줄러 상태**: 다음 실행 시간이 표시됨
   - 새 회차 체크: 6시간마다
   - 결과 수집: 매일 06:00
   - 일일 상태: 매일 21:00
4. **로그**: 에러 없이 정상 실행 메시지

## 6시간마다 텔레그램 알림이 안 오는 경우 체크리스트

- [ ] `systemctl status sports-scheduler` → active (running)
- [ ] `ps aux | grep scheduler_main` → 프로세스 실행 중
- [ ] `python scheduler_main.py --status` → 다음 실행 시간 표시
- [ ] `journalctl -u sports-scheduler -n 50` → 에러 없음
- [ ] `.env` 파일에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 설정됨
- [ ] 텔레그램 테스트 메시지 전송 성공
- [ ] 마지막 실행 시간이 6시간 이내인지 확인

