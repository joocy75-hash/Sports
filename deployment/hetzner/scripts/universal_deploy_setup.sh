#!/bin/bash
# Universal Deployment Setup Script
# 이 스크립트를 새로운 프로젝트의 루트 디렉토리로 복사해서 실행하세요.
# Usage: ./universal_deploy_setup.sh

# 기본 설정
DEFAULT_SERVER_IP="141.164.55.245"
DEFAULT_SERVER_USER="root"

echo "=========================================="
echo "🚀 AI Server Deployment Setup Assistant"
echo "=========================================="

# 1. 프로젝트 정보 입력
read -p "프로젝트 이름 (예: my-web-service): " PROJECT_NAME
read -p "서비스 포트 (예: 3000): " SERVICE_PORT
read -p "서버 IP [Enter for $DEFAULT_SERVER_IP]: " SERVER_IP
SERVER_IP=${SERVER_IP:-$DEFAULT_SERVER_IP}

if [ -z "$PROJECT_NAME" ] || [ -z "$SERVICE_PORT" ]; then
  echo "❌ 프로젝트 이름과 포트는 필수입니다."
  exit 1
fi

REMOTE_DIR="/root/$PROJECT_NAME"

echo ""
echo "📝 설정 확인:"
echo "- Project: $PROJECT_NAME"
echo "- Port: $SERVICE_PORT"
echo "- Server: $SERVER_IP ($REMOTE_DIR)"
echo "=========================================="

# 2. 서버 디렉토리 생성
echo ">>> 1. 서버 디렉토리 생성 중..."
ssh -o StrictHostKeyChecking=no $DEFAULT_SERVER_USER@$SERVER_IP "mkdir -p $REMOTE_DIR"
if [ $? -eq 0 ]; then
    echo "✅ 서버 디렉토리 생성 완료: $REMOTE_DIR"
else
    echo "❌ 서버 접속 실패. SSH 키가 등록되어 있는지 확인하세요."
    exit 1
fi

# 3. Docker Compose 생성
if [ ! -f "docker-compose.yml" ]; then
    echo ">>> 2. docker-compose.yml 생성 중..."
    cat > docker-compose.yml <<EOF
version: '3.8'

services:
  app:
    image: node:18-alpine  # 프로젝트에 맞게 수정 필요 (예: python:3.11, openjdk:17)
    container_name: ${PROJECT_NAME}
    restart: always
    working_dir: /app
    # build: .  # Dockerfile이 있는 경우 주석 해제
    ports:
      - "${SERVICE_PORT}:${SERVICE_PORT}"
    environment:
      - NODE_ENV=production
      - PORT=${SERVICE_PORT}
    volumes:
      - ./:/app
      - /app/node_modules
    command: npm start
EOF
    echo "✅ docker-compose.yml 생성 완료 (내용을 프로젝트에 맞게 수정하세요)"
else
    echo "ℹ️ docker-compose.yml이 이미 존재합니다. 건너뜁니다."
fi

# 4. GitHub Actions 워크플로우 생성
echo ">>> 3. GitHub Actions 워크플로우 생성 중..."
mkdir -p .github/workflows
cat > .github/workflows/deploy.yml <<EOF
name: Deploy $PROJECT_NAME

on:
  push:
    branches: [ "main", "master" ]
  workflow_dispatch:

env:
  SERVER_IP: $SERVER_IP
  SERVER_USER: $DEFAULT_SERVER_USER
  REMOTE_DIR: $REMOTE_DIR

jobs:
  deploy:
    runs-on: ubuntu-latest
    name: Deploy to Server

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup SSH Key
        run: |
          mkdir -p ~/.ssh
          echo "\${{ secrets.HETZNER_SSH_KEY }}" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh-keyscan -H \${{ env.SERVER_IP }} >> ~/.ssh/known_hosts

      - name: Sync Files
        run: |
          rsync -avz --delete \\
            --exclude='.git' \\
            --exclude='node_modules' \\
            --exclude='.env' \\
            ./ \${{ env.SERVER_USER }}@\${{ env.SERVER_IP }}:\${{ env.REMOTE_DIR }}/

      - name: Restart Service
        run: |
          ssh \${{ env.SERVER_USER }}@\${{ env.SERVER_IP }} "cd \${{ env.REMOTE_DIR }} && docker compose up -d --build"
EOF
echo "✅ .github/workflows/deploy.yml 생성 완료"

# 5. GitHub Secrets 설정
echo ">>> 4. GitHub Secrets 설정 (gh CLI 필요)..."
if command -v gh &> /dev/null; then
    if gh auth status &> /dev/null; then
        # SSH 키가 있는지 확인
        if [ -f ~/.ssh/id_rsa ]; then
            gh secret set HETZNER_SSH_KEY < ~/.ssh/id_rsa
            echo "✅ HETZNER_SSH_KEY 등록 완료"
        else
            echo "⚠️ ~/.ssh/id_rsa 파일을 찾을 수 없습니다. Secrets를 수동으로 등록해주세요."
        fi
    else
        echo "⚠️ GitHub CLI에 로그인되어 있지 않습니다. 'gh auth login'을 실행하세요."
    fi
else
    echo "⚠️ GitHub CLI(gh)가 설치되어 있지 않습니다. Secrets를 수동으로 등록해주세요."
fi

echo ""
echo "=========================================="
echo "🎉 설정이 완료되었습니다!"
echo "1. 'docker-compose.yml' 파일을 프로젝트에 맞게 수정하세요."
echo "2. 코드를 GitHub에 Push하면 배포가 시작됩니다."
echo "=========================================="
