#!/bin/bash
#
# 텔레그램 알림 문제 자동 점검/복구 스크립트
# - 서비스 상태, 스케줄러 상태, .env 텔레그램 설정, 텔레그램 전송 테스트까지 한 번에 수행
# - 6시간마다 정상적으로 분석 결과가 텔레그램으로 전송되는지 확인/복구를 돕는다.
#
# 사용법 (로컬에서 실행):
#   chmod +x fix_telegram_notifications.sh
#   ./fix_telegram_notifications.sh <server-ip>
# 예시:
#   ./fix_telegram_notifications.sh 141.164.55.245
#

if [ -z "$1" ]; then
    echo "사용법: $0 <server-ip>"
    echo "예시: $0 141.164.55.245"
    exit 1
fi

SERVER_IP="$1"
SERVER_USER="root"
SERVER="${SERVER_USER}@${SERVER_IP}"
SERVER_PATH="/opt/sports-analysis"
SERVICE_NAME="sports-scheduler"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE} 텔레그램 알림 자동 점검/복구 시작: ${SERVER_IP}${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

echo -e "${YELLOW}1) 서버 기본 상태 및 서비스/스케줄러 점검 (setup_scheduler + fix_scheduler)${NC}"
echo "----------------------------------------------------------------"

# 1-1. 스케줄러 설정/서비스 상태 정리 (기존 스크립트 재사용)
if [ -f "setup_scheduler.sh" ]; then
    echo -e "${BLUE}▶ setup_scheduler.sh 실행...${NC}"
    ./setup_scheduler.sh "${SERVER_IP}"
else
    echo -e "${YELLOW}⚠ setup_scheduler.sh 파일이 없어 이 단계는 건너뜁니다.${NC}"
fi

echo ""
echo -e "${BLUE}▶ fix_scheduler.sh 서버 내 실행...${NC}"
ssh "${SERVER}" 'bash -s' < fix_scheduler.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ fix_scheduler.sh 실행 중 오류가 발생했습니다. SSH 접속 또는 권한을 확인하세요.${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}2) 서버 상태 상세 점검 (check_server_status.sh)${NC}"
echo "----------------------------------------------------------------"

if [ -f "check_server_status.sh" ]; then
    ssh "${SERVER}" 'bash -s' < check_server_status.sh
else
    echo -e "${YELLOW}⚠ check_server_status.sh 파일이 없어 이 단계는 건너뜁니다.${NC}"
fi

echo ""
echo -e "${YELLOW}3) .env 텔레그램 설정 및 Python 환경 점검${NC}"
echo "----------------------------------------------------------------"

ssh "${SERVER}" bash << 'ENDSSH'
SERVER_PATH="/opt/sports-analysis"
cd "${SERVER_PATH}" 2>/dev/null || { echo "❌ 디렉토리 없음: ${SERVER_PATH}"; exit 1; }

echo ""
echo "▶ .env 파일 내 TELEGRAM 설정 확인"
echo "--------------------------------"
if [ -f ".env" ]; then
    grep -E "TELEGRAM" .env || echo "⚠ TELEGRAM 관련 설정이 .env에 없습니다."
else
    echo "❌ .env 파일이 없습니다."
fi

echo ""
echo "▶ Python / venv 확인"
echo "--------------------------------"
if [ -d "venv" ]; then
    echo "✅ venv 디렉토리 존재"
    source venv/bin/activate 2>/dev/null
    echo "Python 버전:"
    python -V || python3 -V || echo "⚠ Python 실행 불가"
else
    echo "⚠ venv 디렉토리가 없습니다. (python3 -m venv venv 후 requirements 설치 필요)"
fi
ENDSSH

echo ""
echo -e "${YELLOW}4) 텔레그램 전송 단일 테스트 (TelegramNotifier 직접 호출)${NC}"
echo "----------------------------------------------------------------"

ssh "${SERVER}" bash << 'ENDSSH'
SERVER_PATH="/opt/sports-analysis"
cd "${SERVER_PATH}" 2>/dev/null || { echo "❌ 디렉토리 없음: ${SERVER_PATH}"; exit 1; }

if [ ! -d "venv" ]; then
    echo "❌ venv 없음: 텔레그램 테스트를 실행할 수 없습니다."
    exit 1
fi

source venv/bin/activate 2>/dev/null

echo "▶ 텔레그램 테스트 메시지 전송 시도..."
python - << 'PYCODE'
import asyncio
from src.services.telegram_notifier import TelegramNotifier

async def main():
    notifier = TelegramNotifier()
    try:
        ok = await notifier.send_message("🔧 텔레그램 테스트 메시지 (fix_telegram_notifications.sh)")
        print("텔레그램 전송 결과:", ok)
    except Exception as e:
        print("❌ 텔레그램 전송 중 예외 발생:", e)

asyncio.run(main())
PYCODE
ENDSSH

echo ""
echo -e "${YELLOW}5) 스케줄러 작업 상태 확인 (6시간 주기 등록 여부)${NC}"
echo "----------------------------------------------------------------"

ssh "${SERVER}" bash << 'ENDSSH'
SERVER_PATH="/opt/sports-analysis"
cd "${SERVER_PATH}" 2>/dev/null || { echo "❌ 디렉토리 없음: ${SERVER_PATH}"; exit 1; }

if [ ! -d "venv" ]; then
    echo "❌ venv 없음: 스케줄러 상태 확인 불가"
    exit 1
fi

source venv/bin/activate 2>/dev/null

echo "▶ scheduler_main.py --status 실행"
python scheduler_main.py --status 2>&1 || echo "⚠ scheduler_main.py --status 실행 실패"
ENDSSH

echo ""
echo -e "${YELLOW}6) 필요 시, 수동 분석/전송 1회 실행 (옵션)${NC}"
echo "----------------------------------------------------------------"
echo "원하면 다음 명령으로 수동으로 1회 분석+텔레그램 전송을 확인하세요:"
echo "  ssh ${SERVER} 'cd ${SERVER_PATH} && source venv/bin/activate && python auto_sports_notifier.py --soccer'"
echo "  ssh ${SERVER} 'cd ${SERVER_PATH} && source venv/bin/activate && python auto_sports_notifier.py --basketball'"
echo ""

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN} 텔레그램 알림 점검 스크립트 실행 완료${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "정상 상태 체크리스트:"
echo "  - sports-scheduler 서비스가 active (running)"
echo "  - scheduler_main.py --status 에서 '새 회차 체크: 6시간마다'와 다음 실행 시간이 표시"
echo "  - 위 텔레그램 테스트 메시지가 실제 텔레그램에 도착"
echo "  - 수동 실행 (auto_sports_notifier.py) 시 에러 없이 완료"

