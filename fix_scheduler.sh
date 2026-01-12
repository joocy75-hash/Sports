#!/bin/bash
#
# 스케줄러 설정 및 수정 스크립트
# 6시간마다 텔레그램 알림이 정상 작동하도록 설정
#
# 사용법:
#   ssh root@141.164.55.245 'bash -s' < fix_scheduler.sh
#   또는 서버에 접속한 후: bash fix_scheduler.sh

SERVER_PATH="/opt/sports-analysis"
SERVICE_NAME="sports-scheduler"

echo "=========================================="
echo "스케줄러 설정 및 수정"
echo "=========================================="
echo ""

# 1. 서비스 파일 확인
echo "1. Systemd 서비스 파일 확인"
echo "=========================================="
if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
    echo "✅ 서비스 파일 존재"
    cat /etc/systemd/system/${SERVICE_NAME}.service
else
    echo "❌ 서비스 파일 없음 - 생성 필요"
    if [ -f "${SERVER_PATH}/sports-scheduler.service" ]; then
        echo "로컬 서비스 파일 복사 중..."
        cp "${SERVER_PATH}/sports-scheduler.service" "/etc/systemd/system/${SERVICE_NAME}.service"
        systemctl daemon-reload
        echo "✅ 서비스 파일 생성 완료"
    fi
fi
echo ""

# 2. 서비스 활성화 확인
echo "2. 서비스 활성화 상태"
echo "=========================================="
if systemctl is-enabled "${SERVICE_NAME}" >/dev/null 2>&1; then
    echo "✅ 서비스 활성화됨"
else
    echo "⚠️ 서비스 미활성화 - 활성화 중..."
    systemctl enable "${SERVICE_NAME}"
    echo "✅ 서비스 활성화 완료"
fi
echo ""

# 3. 서비스 상태 확인
echo "3. 서비스 실행 상태"
echo "=========================================="
systemctl status "${SERVICE_NAME}" --no-pager | head -15
echo ""

# 4. 작업 디렉토리 확인
echo "4. 작업 디렉토리 확인"
echo "=========================================="
if [ -d "${SERVER_PATH}" ]; then
    echo "✅ 디렉토리 존재: ${SERVER_PATH}"
    cd "${SERVER_PATH}" || exit 1
    
    # 필수 파일 확인
    if [ -f "scheduler_main.py" ]; then
        echo "✅ scheduler_main.py 존재"
    else
        echo "❌ scheduler_main.py 없음"
        exit 1
    fi
    
    if [ -f ".env" ]; then
        echo "✅ .env 파일 존재"
        # 텔레그램 설정 확인
        if grep -q "TELEGRAM_BOT_TOKEN" .env && grep -q "TELEGRAM_CHAT_ID" .env; then
            echo "✅ 텔레그램 설정 확인됨"
        else
            echo "⚠️ 텔레그램 설정 누락"
        fi
    else
        echo "⚠️ .env 파일 없음"
    fi
    
    if [ -d "venv" ]; then
        echo "✅ venv 존재"
    else
        echo "⚠️ venv 없음"
    fi
else
    echo "❌ 디렉토리 없음: ${SERVER_PATH}"
    exit 1
fi
echo ""

# 5. Python 경로 확인
echo "5. Python 경로 확인"
echo "=========================================="
PYTHON3_PATH=$(which python3)
echo "Python3 경로: ${PYTHON3_PATH}"
if [ -z "${PYTHON3_PATH}" ]; then
    echo "❌ Python3 없음"
    exit 1
fi
echo ""

# 6. 서비스 재시작
echo "6. 서비스 재시작"
echo "=========================================="
echo "서비스를 재시작합니다..."
systemctl restart "${SERVICE_NAME}"
sleep 3
echo ""

# 7. 재시작 후 상태 확인
echo "7. 재시작 후 상태 확인"
echo "=========================================="
systemctl status "${SERVICE_NAME}" --no-pager | head -15
echo ""

# 8. 프로세스 확인
echo "8. 스케줄러 프로세스 확인"
echo "=========================================="
ps aux | grep -E "scheduler_main|python.*scheduler" | grep -v grep || echo "프로세스 없음"
echo ""

# 9. 최근 로그 확인
echo "9. 최근 로그 확인 (20줄)"
echo "=========================================="
journalctl -u "${SERVICE_NAME}" -n 20 --no-pager
echo ""

# 10. 스케줄러 상태 확인 (옵션)
echo "10. 스케줄러 상세 상태 확인"
echo "=========================================="
if [ -d "${SERVER_PATH}/venv" ]; then
    cd "${SERVER_PATH}" || exit 1
    source venv/bin/activate 2>/dev/null
    if [ -f "scheduler_main.py" ]; then
        python3 scheduler_main.py --status 2>&1 || echo "상태 확인 실패 (서비스가 시작 중일 수 있음)"
    fi
else
    echo "venv 없음 - 스케줄러 상태 확인 건너뜀"
fi
echo ""

echo "=========================================="
echo "설정 완료!"
echo "=========================================="
echo ""
echo "추가 확인 명령어:"
echo "  - 실시간 로그: journalctl -u ${SERVICE_NAME} -f"
echo "  - 서비스 상태: systemctl status ${SERVICE_NAME}"
echo "  - 서비스 재시작: systemctl restart ${SERVICE_NAME}"
echo "  - 스케줄러 상태: cd ${SERVER_PATH} && source venv/bin/activate && python scheduler_main.py --status"

