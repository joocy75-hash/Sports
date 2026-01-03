#!/bin/bash
#
# 배포 상태 확인 스크립트
#
# 사용법: ./check_deployment.sh <server-ip>
#

if [ -z "$1" ]; then
    echo "사용법: $0 <server-ip>"
    echo "예시: $0 5.161.112.248"
    exit 1
fi

SERVER_IP=$1
SERVER_USER="root"
SERVER_PATH="/opt/sports-analysis"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}배포 상태 확인: $SERVER_IP${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

ssh $SERVER_USER@$SERVER_IP << ENDSSH
echo "1. 서비스 상태"
echo "=================================="
systemctl status sports-scheduler --no-pager | head -10
echo ""

echo "2. 프로세스 확인"
echo "=================================="
ps aux | grep scheduler_main | grep -v grep || echo "프로세스 없음"
echo ""

echo "3. 최근 로그 (10줄)"
echo "=================================="
journalctl -u sports-scheduler -n 10 --no-pager
echo ""

echo "4. 스케줄러 상태"
echo "=================================="
cd $SERVER_PATH
source venv/bin/activate
python scheduler_main.py --status
echo ""

echo "5. 디스크 사용량"
echo "=================================="
du -sh $SERVER_PATH
du -sh $SERVER_PATH/.state
echo ""

echo "6. 마지막 수정 파일"
echo "=================================="
ls -lt $SERVER_PATH/ | head -10
echo ""
ENDSSH

echo ""
echo -e "${GREEN}확인 완료!${NC}"
echo ""
echo "더 많은 로그를 보려면:"
echo "  ssh $SERVER_USER@$SERVER_IP 'journalctl -u sports-scheduler -f'"
