# 빠른 배포 가이드 (5분 완성)

**버전**: 3.3.0
**최종 업데이트**: 2026-01-03

---

## 🚀 원클릭 배포 (자동화 스크립트)

### 준비사항

1. **서버 정보**
   - IP 주소: `5.161.112.248` (예시)
   - SSH 접근 권한
   - Ubuntu 20.04+ / Debian 11+

2. **SSH 키 등록** (처음 1회만)
   ```bash
   ssh-copy-id root@5.161.112.248
   ```

### 배포 실행

```bash
# 1. 배포 스크립트 실행
./deploy.sh 5.161.112.248

# 2. .env 파일 업로드 (자동 전송 안됨 - 보안)
scp .env root@5.161.112.248:/opt/sports-analysis/.env

# 3. 서비스 재시작
ssh root@5.161.112.248 'systemctl restart sports-scheduler'
```

**완료!** 🎉

텔레그램으로 "🚀 스케줄러 시작" 메시지가 오면 성공입니다.

---

## 📊 상태 확인

### 방법 1: 자동 스크립트
```bash
./check_deployment.sh 5.161.112.248
```

### 방법 2: 수동 확인
```bash
# 서비스 상태
ssh root@5.161.112.248 'systemctl status sports-scheduler'

# 실시간 로그
ssh root@5.161.112.248 'journalctl -u sports-scheduler -f'

# 스케줄러 상태
ssh root@5.161.112.248 'cd /opt/sports-analysis && source venv/bin/activate && python scheduler_main.py --status'
```

---

## 🔧 자주 사용하는 명령어

### 서비스 제어
```bash
SERVER="root@5.161.112.248"

# 시작
ssh $SERVER 'systemctl start sports-scheduler'

# 중지
ssh $SERVER 'systemctl stop sports-scheduler'

# 재시작
ssh $SERVER 'systemctl restart sports-scheduler'

# 상태 확인
ssh $SERVER 'systemctl status sports-scheduler'
```

### 수동 작업 실행
```bash
SERVER="root@5.161.112.248"
PATH="/opt/sports-analysis"

# 새 회차 체크
ssh $SERVER "cd $PATH && source venv/bin/activate && python scheduler_main.py --run-now check"

# 결과 수집
ssh $SERVER "cd $PATH && source venv/bin/activate && python scheduler_main.py --run-now results"

# 주간 요약
ssh $SERVER "cd $PATH && source venv/bin/activate && python scheduler_main.py --run-now weekly"

# 일일 상태
ssh $SERVER "cd $PATH && source venv/bin/activate && python scheduler_main.py --run-now daily"

# 모든 작업 테스트
ssh $SERVER "cd $PATH && source venv/bin/activate && python scheduler_main.py --test-jobs"
```

### 로그 확인
```bash
SERVER="root@5.161.112.248"

# 최근 50줄
ssh $SERVER 'journalctl -u sports-scheduler -n 50'

# 실시간 로그
ssh $SERVER 'journalctl -u sports-scheduler -f'

# 오늘 로그만
ssh $SERVER 'journalctl -u sports-scheduler --since today'

# 에러 로그만
ssh $SERVER 'journalctl -u sports-scheduler -p err'
```

---

## 🐛 문제 해결

### 1. 서비스가 시작하지 않을 때

```bash
SERVER="root@5.161.112.248"

# 1. 로그 확인
ssh $SERVER 'journalctl -u sports-scheduler -n 50'

# 2. .env 파일 확인
ssh $SERVER 'cat /opt/sports-analysis/.env | grep TELEGRAM'

# 3. 수동 실행 테스트
ssh $SERVER 'cd /opt/sports-analysis && source venv/bin/activate && python scheduler_main.py --status'
```

**자주 발생하는 원인**:
- `.env` 파일이 없음 → `scp .env root@...:/opt/sports-analysis/.env`
- Playwright 미설치 → `ssh root@... 'cd /opt/sports-analysis && source venv/bin/activate && playwright install chromium'`
- 권한 문제 → `ssh root@... 'chmod +x /opt/sports-analysis/scheduler_main.py'`

### 2. 텔레그램 알림이 오지 않을 때

```bash
SERVER="root@5.161.112.248"

# 텔레그램 설정 확인
ssh $SERVER 'cd /opt/sports-analysis && source venv/bin/activate && python -c "
from src.services.telegram_notifier import TelegramNotifier
import asyncio
async def test():
    notifier = TelegramNotifier()
    await notifier.send_message(\"테스트 메시지\")
asyncio.run(test())
"'
```

### 3. 메모리 부족

```bash
SERVER="root@5.161.112.248"

# 메모리 확인
ssh $SERVER 'free -h'

# 스왑 메모리 추가 (2GB)
ssh $SERVER '
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab
'
```

---

## 🔄 업데이트 (코드 수정 후)

```bash
# 1. 로컬에서 변경사항 커밋
git add .
git commit -m "Update feature"
git push

# 2. 서버에서 Pull
ssh root@5.161.112.248 'cd /opt/sports-analysis && git pull'

# 3. 의존성 업데이트 (필요 시)
ssh root@5.161.112.248 'cd /opt/sports-analysis && source venv/bin/activate && pip install -r requirements.txt'

# 4. 서비스 재시작
ssh root@5.161.112.248 'systemctl restart sports-scheduler'

# 5. 상태 확인
./check_deployment.sh 5.161.112.248
```

**또는 자동 스크립트 재실행**:
```bash
./deploy.sh 5.161.112.248
```

---

## 📱 텔레그램 알림 확인

배포 후 받게 될 알림:

### 1. 시작 알림
```
🚀 스케줄러 시작

📅 2026-01-03 15:00:00

📋 등록된 작업:
• 새 회차 체크: 6시간마다
• 결과 수집: 매일 06:00
• 주간 요약: 월요일 09:00
• 일일 상태: 매일 21:00

✅ 시스템 가동 중
```

### 2. 일일 상태 (매일 21:00)
```
📊 일일 상태 리포트
📅 2026-01-03

⚽ 축구: 5회차 예측
🏀 농구: 3회차 예측

✅ 시스템 정상 가동 중
```

### 3. 에러 알림 (문제 발생 시)
```
⚠️ 스케줄러 오류

작업: 새 회차 체크
시간: 2026-01-03 14:00
오류: Connection timeout
```

---

## 💾 백업

```bash
SERVER="root@5.161.112.248"

# 상태 파일 백업
ssh $SERVER 'cd /opt/sports-analysis && tar -czf state-backup-$(date +%Y%m%d).tar.gz .state/'

# 로컬로 다운로드
scp $SERVER:/opt/sports-analysis/state-backup-*.tar.gz ./backups/

# 복원
scp ./backups/state-backup-20260103.tar.gz $SERVER:/opt/sports-analysis/
ssh $SERVER 'cd /opt/sports-analysis && tar -xzf state-backup-20260103.tar.gz'
```

---

## 📊 모니터링

### 방법 1: 텔레그램 (추천)
- 일일 상태 리포트 (매일 21:00)
- 에러 알림 (실시간)
- 예측/결과 알림 (자동)

### 방법 2: 서버 로그
```bash
# 실시간 로그 (별도 터미널)
ssh root@5.161.112.248 'journalctl -u sports-scheduler -f'
```

### 방법 3: 주기적 체크
```bash
# cron으로 매시간 상태 확인
0 * * * * /path/to/check_deployment.sh 5.161.112.248 >> /var/log/scheduler-check.log 2>&1
```

---

## 🎯 배포 체크리스트

배포 후 확인사항:

- [ ] 서비스 상태: `systemctl status sports-scheduler` → active (running)
- [ ] 텔레그램 시작 알림 수신
- [ ] 로그 확인: 에러 없음
- [ ] 스케줄러 상태: `python scheduler_main.py --status` → 다음 실행 시간 표시
- [ ] .state 디렉토리 생성: `ls -la .state/`
- [ ] 메모리/CPU 정상: `free -h && top`

모두 체크되면 배포 완료! ✅

---

## 📞 문의

배포 중 문제가 발생하면:
1. `./check_deployment.sh 5.161.112.248` 실행
2. 로그 확인: `journalctl -u sports-scheduler -n 100`
3. 상세 가이드: `DEPLOYMENT_GUIDE.md` 참고

---

**버전**: 3.3.0
**작성일**: 2026-01-03
