#!/bin/bash
# 01-server-init.sh - 서버 초기 설정 (Hetzner Ubuntu 24.04)

set -e

echo ">>> 서버 패키지 업데이트..."
apt-get update && apt-get upgrade -y

echo ">>> 필수 패키지 설치..."
apt-get install -y apt-transport-https ca-certificates curl software-properties-common gnupg lsb-release rsync ufw fail2ban

echo ">>> Docker 설치..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl enable docker
    systemctl start docker
fi

echo ">>> Docker Compose 설치..."
if ! docker compose version &> /dev/null; then
    apt-get install -y docker-compose-plugin
fi

echo ">>> Swap 설정 (2GB)..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "vm.swappiness=10" >> /etc/sysctl.conf
    sysctl -p
fi

echo ">>> 방화벽(UFW) 설정..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Group A: Freqtrade
ufw allow 8080:8083/tcp comment 'Freqtrade WebUI'

# Group B: Automation
ufw allow 5001:5003/tcp comment 'Automation Services'

# Group C: AI Platform
ufw allow 8090/tcp comment 'AI Trading Platform'

echo "y" | ufw enable

echo ">>> 서버 초기 설정 완료!"
