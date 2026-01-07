#!/bin/bash
# 02-create-dirs.sh - 서비스 디렉토리 구조 생성

set -e

BASE_DIR="/root"

echo ">>> 디렉토리 구조 생성 중..."

# Group A
mkdir -p $BASE_DIR/service_a/user_data/bot1
mkdir -p $BASE_DIR/service_a/user_data/bot2
mkdir -p $BASE_DIR/service_a/user_data/bot3
mkdir -p $BASE_DIR/service_a/user_data/bot4

# Group B
mkdir -p $BASE_DIR/service_b/sports_analysis/logs
mkdir -p $BASE_DIR/service_b/naver_blog/logs
mkdir -p $BASE_DIR/service_b/tradingview/logs
mkdir -p $BASE_DIR/service_b/tradingview/strategies

# Group C
mkdir -p $BASE_DIR/service_c/ai_platform/logs
mkdir -p $BASE_DIR/service_c/ai_platform/data
mkdir -p $BASE_DIR/service_c/ai_platform/models

# Shared
mkdir -p $BASE_DIR/shared/nginx/conf.d
mkdir -p $BASE_DIR/shared/nginx/certs
mkdir -p $BASE_DIR/shared/nginx/html

echo ">>> 권한 설정..."
chmod -R 755 $BASE_DIR/service_a
chmod -R 755 $BASE_DIR/service_b
chmod -R 755 $BASE_DIR/service_c
chmod -R 755 $BASE_DIR/shared

echo ">>> 디렉토리 생성 완료!"
ls -R $BASE_DIR/service_*
