#!/bin/bash
#
# 빠른 스케줄러 설정 스크립트
# 서버에 직접 SSH 접속 후 실행
#
# 사용법: bash quick_setup.sh

echo "=========================================="
echo "스케줄러 빠른 설정"
echo "=========================================="
echo ""

cd /opt/sports-analysis || exit 1

echo "1. 서비스 파일 설치"
echo "=========================================="
sudo cp sports-scheduler.service /etc/systemd/system/sports-scheduler.service
sudo systemctl daemon-reload
echo "✅ 완료"
echo ""

echo "2. 서비스 활성화"
echo "=========================================="
sudo systemctl enable sports-scheduler
echo "✅ 완료"
echo ""

echo "3. 서비스 재시작"
echo "=========================================="
sudo systemctl restart sports-scheduler
sleep 3
echo "✅ 완료"
echo ""

echo "4. 서비스 상태 확인"
echo "=========================================="
systemctl status sports-scheduler --no-pager | head -15
echo ""

echo "5. 스케줄러 상태 확인"
echo "=========================================="
source venv/bin/activate 2>/dev/null
python3 scheduler_main.py --status 2>&1 || echo "상태 확인 실패"
echo ""

echo "6. 최근 로그 확인"
echo "=========================================="
journalctl -u sports-scheduler -n 20 --no-pager
echo ""

echo "=========================================="
echo "설정 완료!"
echo "=========================================="
echo ""
echo "실시간 로그 확인: journalctl -u sports-scheduler -f"
echo "서비스 상태: systemctl status sports-scheduler"

