#!/bin/bash
# Manual Deployment Script for Group B (Sports Analysis)
# Usage: ./manual_deploy_group_b.sh

SERVER_IP="141.164.55.245"
SERVER_USER="root"
REMOTE_DIR="/root/service_b"

echo ">>> Starting Manual Deployment to $SERVER_IP..."

# 1. Sync Docker Compose
echo ">>> Syncing docker-compose.yml..."
rsync -avz deployment/hetzner/group_b_automation/docker-compose.yml $SERVER_USER@$SERVER_IP:$REMOTE_DIR/docker-compose.yml

# 2. Sync Backend
echo ">>> Syncing Backend..."
rsync -avz --delete \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.state' \
  --exclude='logs' \
  --exclude='.env' \
  --exclude='node_modules' \
  --exclude='.git' \
  ./src \
  ./auto_sports_notifier.py \
  ./auto_telegram_bot.py \
  ./basketball_w5l_analyzer.py \
  ./basketball_w5l_notifier.py \
  ./collect_and_notify.py \
  ./requirements.txt \
  $SERVER_USER@$SERVER_IP:$REMOTE_DIR/sports_analysis/

# 3. Sync Frontend
echo ">>> Syncing Frontend..."
rsync -avz --delete \
  --exclude='node_modules' \
  --exclude='dist' \
  --exclude='.git' \
  ./frontend/ \
  $SERVER_USER@$SERVER_IP:$REMOTE_DIR/frontend/

# 4. Restart Services
echo ">>> Rebuilding and Restarting Services..."
ssh $SERVER_USER@$SERVER_IP "cd $REMOTE_DIR && docker compose up -d --build --remove-orphans"

echo ">>> Deployment Complete!"
