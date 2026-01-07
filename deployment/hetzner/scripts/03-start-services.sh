#!/bin/bash
# 03-start-services.sh - Docker Compose 서비스 시작

set -e

BASE_DIR="/root"

echo ">>> 서비스 시작 중..."

# Group A
echo "Starting Group A (Freqtrade)..."
cd $BASE_DIR/service_a
docker compose up -d

# Group B
echo "Starting Group B (Automation)..."
cd $BASE_DIR/service_b
docker compose up -d

# Group C
echo "Starting Group C (AI Trading)..."
cd $BASE_DIR/service_c
docker compose up -d

echo ">>> 모든 서비스가 시작되었습니다!"
docker compose ps
