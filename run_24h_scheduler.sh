#!/bin/bash
# 프로토 14경기 24시간 자동화 스크립트
#
# 사용법:
#   chmod +x run_24h_scheduler.sh
#   ./run_24h_scheduler.sh
#
# 백그라운드 실행:
#   nohup ./run_24h_scheduler.sh > scheduler.log 2>&1 &
#
# 중단:
#   pkill -f "python.*auto_sports_notifier.py --schedule"

cd "$(dirname "$0")"

echo "=========================================="
echo "🎯 프로토 14경기 24시간 자동화 시작"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""
echo "✅ 설정:"
echo "   - 체크 간격: 6시간"
echo "   - 새 회차 감지 시 자동 분석 및 텔레그램 전송"
echo "   - 로그: scheduler.log"
echo ""
echo "⚠️  중단: Ctrl+C 또는 pkill -f 'python.*auto_sports_notifier.py --schedule'"
echo ""
echo "=========================================="
echo ""

# Python 가상환경이 있다면 활성화
if [ -d "deepseek_env" ]; then
    echo "가상환경 활성화..."
    source deepseek_env/bin/activate
fi

# 스케줄러 실행
python3 auto_sports_notifier.py --schedule --interval 6

echo ""
echo "=========================================="
echo "스케줄러 종료"
echo "=========================================="
