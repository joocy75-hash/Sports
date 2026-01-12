#!/bin/bash
#
# 스케줄러 설정 스크립트
# 6시간마다 텔레그램 알림이 정상 작동하도록 설정
#
# 사용법: ./setup_scheduler.sh <server-ip>
#

if [ -z "$1" ]; then
    echo "사용법: $0 <server-ip>"
    echo "예시: $0 141.164.55.245"
    exit 1
fi

SERVER_IP=$1
SERVER_USER="root"
SERVER_PATH="/opt/sports-analysis"
SERVICE_NAME="sports-scheduler"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}스케줄러 설정: ${SERVER_IP}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 스크립트를 서버로 전송하고 실행
ssh ${SERVER_USER}@${SERVER_IP} << ENDSSH

echo "1. 서비스 파일 확인 및 설치"
echo "=========================================="
cd ${SERVER_PATH} || exit 1

if [ -f "sports-scheduler.service" ]; then
    echo "✅ 서비스 파일 존재"
    sudo cp sports-scheduler.service /etc/systemd/system/${SERVICE_NAME}.service
    sudo systemctl daemon-reload
    echo "✅ 서비스 파일 설치 완료"
else
    echo "⚠️ 서비스 파일 없음"
fi
echo ""

echo "2. 서비스 활성화"
echo "=========================================="
if systemctl is-enabled ${SERVICE_NAME} >/dev/null 2>&1; then
    echo "✅ 서비스 이미 활성화됨"
else
    sudo systemctl enable ${SERVICE_NAME}
    echo "✅ 서비스 활성화 완료"
fi
echo ""

echo "3. 필수 파일 확인"
echo "=========================================="
if [ -f "scheduler_main.py" ]; then
    echo "✅ scheduler_main.py 존재"
else
    echo "❌ scheduler_main.py 없음"
    exit 1
fi

if [ -f ".env" ]; then
    echo "✅ .env 파일 존재"
    if grep -q "TELEGRAM_BOT_TOKEN" .env && grep -q "TELEGRAM_CHAT_ID" .env; then
        echo "✅ 텔레그램 설정 확인됨"
    else
        echo "⚠️ 텔레그램 설정 누락 - 확인 필요"
    fi
else
    echo "⚠️ .env 파일 없음 - 확인 필요"
fi
echo ""

echo "4. 서비스 중지"
echo "=========================================="
sudo systemctl stop ${SERVICE_NAME} 2>/dev/null
sleep 2
echo "✅ 서비스 중지 완료"
echo ""

echo "5. 서비스 시작"
echo "=========================================="
sudo systemctl start ${SERVICE_NAME}
sleep 3
echo "✅ 서비스 시작 완료"
echo ""

echo "6. 서비스 상태 확인"
echo "=========================================="
systemctl status ${SERVICE_NAME} --no-pager | head -15
echo ""

echo "7. 프로세스 확인"
echo "=========================================="
ps aux | grep -E "scheduler_main|python.*scheduler" | grep -v grep || echo "프로세스 확인 중..."
echo ""

echo "8. 최근 로그 확인 (20줄)"
echo "=========================================="
journalctl -u ${SERVICE_NAME} -n 20 --no-pager
echo ""

echo "9. 스케줄러 상태 확인"
echo "=========================================="
cd ${SERVER_PATH} || exit 1
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null
    if command -v python3 >/dev/null 2>&1; then
        python3 scheduler_main.py --status 2>&1 || echo "상태 확인 실패 (서비스 시작 중일 수 있음)"
    fi
fi
echo ""

ENDSSH

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}설정 완료!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "추가 확인 명령어:"
    echo "  ssh ${SERVER_USER}@${SERVER_IP} 'systemctl status ${SERVICE_NAME}'"
    echo "  ssh ${SERVER_USER}@${SERVER_IP} 'journalctl -u ${SERVICE_NAME} -f'"
    echo "  ssh ${SERVER_USER}@${SERVER_IP} 'cd ${SERVER_PATH} && source venv/bin/activate && python scheduler_main.py --status'"
else
    echo ""
    echo -e "${RED}설정 실패 - 서버 접속 확인 필요${NC}"
    exit 1
fi

