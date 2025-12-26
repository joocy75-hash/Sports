#!/bin/bash
# 농구 승5패 자동 분석 실행 스크립트
#
# 사용법:
#   ./scripts/run_basketball_w5l.sh          # 즉시 실행
#   ./scripts/run_basketball_w5l.sh test     # 테스트 모드
#   ./scripts/run_basketball_w5l.sh schedule # 스케줄러 모드
#
# Cron 설정 예시:
#   # 매일 오전 7시, 12시, 18시에 분석 실행
#   0 7,12,18 * * * /Users/mr.joo/Desktop/스포츠분석/scripts/run_basketball_w5l.sh >> /Users/mr.joo/Desktop/스포츠분석/logs/basketball_w5l.log 2>&1

# 스크립트 디렉토리로 이동
cd "$(dirname "$0")/.."

# 환경 변수 로드
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Python 경로 설정 (필요시 수정)
PYTHON_PATH="/usr/bin/python3"
if command -v python3 &> /dev/null; then
    PYTHON_PATH=$(which python3)
fi

# 로그 디렉토리 생성
mkdir -p logs

# 실행 모드에 따라 분기
case "$1" in
    test)
        echo "[$(date)] 테스트 모드 실행"
        $PYTHON_PATH basketball_w5l_notifier.py --test
        ;;
    schedule)
        echo "[$(date)] 스케줄러 모드 실행"
        $PYTHON_PATH basketball_w5l_notifier.py --schedule --interval 6
        ;;
    *)
        echo "[$(date)] 즉시 분석 실행"
        $PYTHON_PATH basketball_w5l_notifier.py
        ;;
esac

echo "[$(date)] 실행 완료"
