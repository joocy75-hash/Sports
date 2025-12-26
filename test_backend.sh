#!/bin/bash
# 백엔드 서버 실행 테스트 스크립트

cd /Users/mr.joo/Desktop/스포츠분석
source deepseek_env/bin/activate

export PYTHONPATH=/Users/mr.joo/Desktop/스포츠분석

echo "========================================="
echo "백엔드 서버 실행 테스트"
echo "========================================="

# 서버 시작
python -m uvicorn src.api.unified_server:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

echo "서버 PID: $SERVER_PID"
echo "서버 시작 대기 중 (10초)..."
sleep 10

# API 테스트
echo ""
echo "========================================="
echo "1. Health Check"
echo "========================================="
curl -s http://localhost:8000/health | python3 -m json.tool

echo ""
echo "========================================="
echo "2. Dashboard API"
echo "========================================="
curl -s http://localhost:8000/api/v1/dashboard | python3 -m json.tool | head -30

echo ""
echo "========================================="
echo "3. Proto Matches List"
echo "========================================="
curl -s http://localhost:8000/api/v1/proto/list | python3 -m json.tool | head -30

echo ""
echo "========================================="
echo "4. 구매 가능 게임 조회"
echo "========================================="
curl -s http://localhost:8000/api/v1/games/active-rounds | python3 -m json.tool | head -30

echo ""
echo "========================================="
echo "서버 종료 중..."
echo "========================================="
kill $SERVER_PID
wait $SERVER_PID 2>/dev/null

echo "✅ 테스트 완료!"
