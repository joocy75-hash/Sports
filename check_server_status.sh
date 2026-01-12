#!/bin/bash
#
# 서버 상태 확인 스크립트
# 서버에 직접 SSH 접속 후 실행하여 상태를 확인합니다
#
# 사용법:
#   ssh root@141.164.55.245 'bash -s' < check_server_status.sh
#   또는 서버에 접속한 후 직접 실행:
#   bash check_server_status.sh

SERVER_PATH="/opt/sports-analysis"

echo "=========================================="
echo "스포츠 분석 서버 상태 확인"
echo "=========================================="
echo ""

echo "1. Systemd 서비스 상태 (sports-scheduler)"
echo "=========================================="
systemctl status sports-scheduler --no-pager | head -15
echo ""

echo "2. 스케줄러 프로세스 확인"
echo "=========================================="
ps aux | grep -E "scheduler_main|python.*scheduler" | grep -v grep || echo "프로세스 없음"
echo ""

echo "3. 최근 시스템 로그 (20줄)"
echo "=========================================="
journalctl -u sports-scheduler -n 20 --no-pager 2>/dev/null || echo "로그 없음"
echo ""

echo "4. 스케줄러 상태 확인"
echo "=========================================="
if [ -d "$SERVER_PATH" ]; then
    cd "$SERVER_PATH" || exit 1
    
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        if [ -f "scheduler_main.py" ]; then
            python scheduler_main.py --status 2>&1 || echo "스케줄러 상태 확인 실패"
        else
            echo "scheduler_main.py 파일이 없습니다"
        fi
    else
        echo "venv가 없습니다"
    fi
else
    echo "서버 경로가 없습니다: $SERVER_PATH"
fi
echo ""

echo "5. 최근 스케줄러 로그 파일 (마지막 30줄)"
echo "=========================================="
if [ -f "$SERVER_PATH/scheduler.log" ]; then
    tail -30 "$SERVER_PATH/scheduler.log" 2>/dev/null || echo "로그 파일 읽기 실패"
else
    echo "scheduler.log 파일이 없습니다"
fi
echo ""

echo "6. 텔레그램 설정 확인 (.env 파일)"
echo "=========================================="
if [ -f "$SERVER_PATH/.env" ]; then
    grep -E "TELEGRAM" "$SERVER_PATH/.env" 2>/dev/null | sed 's/=.*/=***/' || echo "TELEGRAM 설정 없음"
else
    echo ".env 파일이 없습니다"
fi
echo ""

echo "7. 디스크 사용량"
echo "=========================================="
df -h / 2>/dev/null | tail -1
if [ -d "$SERVER_PATH" ]; then
    du -sh "$SERVER_PATH" 2>/dev/null
    if [ -d "$SERVER_PATH/.state" ]; then
        du -sh "$SERVER_PATH/.state" 2>/dev/null
    fi
fi
echo ""

echo "8. 마지막 작업 시간 확인 (.state 디렉토리)"
echo "=========================================="
if [ -d "$SERVER_PATH/.state" ]; then
    ls -lht "$SERVER_PATH/.state" 2>/dev/null | head -10 || echo ".state 디렉토리 읽기 실패"
else
    echo ".state 디렉토리가 없습니다"
fi
echo ""

echo "9. 시스템 시간 및 타임존"
echo "=========================================="
date
timedatectl 2>/dev/null | grep "Time zone" || echo "타임존 확인 불가"
echo ""

echo "=========================================="
echo "상태 확인 완료"
echo "=========================================="
echo ""
echo "추가 확인 사항:"
echo "  - 실시간 로그: journalctl -u sports-scheduler -f"
echo "  - 서비스 재시작: systemctl restart sports-scheduler"
echo "  - 서비스 시작: systemctl start sports-scheduler"
echo "  - 서비스 상태: systemctl status sports-scheduler"

