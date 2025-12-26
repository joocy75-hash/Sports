#!/bin/bash
# ============================================
# 스포츠 분석 시스템 - Hetzner 서버 배포 스크립트
# ============================================
# 사용법: ./scripts/deploy-to-server.sh [옵션]
# 옵션:
#   --init    : 첫 배포 (서버 초기 설정 포함)
#   --update  : 코드만 업데이트 (기본값)
#   --restart : 서비스 재시작만
#   --logs    : 로그 확인
# ============================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 서버 정보
SERVER_IP="5.161.112.248"
SERVER_USER="root"
REMOTE_DIR="/root/sports-analysis"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# 로깅 함수
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# SSH 명령 실행
run_ssh() {
    ssh -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" "$@"
}

# 서버 초기 설정 (첫 배포 시)
init_server() {
    log_info "서버 초기 설정 시작..."

    run_ssh 'apt-get update && apt-get upgrade -y'

    # Docker 설치
    run_ssh 'command -v docker || (curl -fsSL https://get.docker.com | sh && systemctl enable docker && systemctl start docker)'

    # Docker Compose 플러그인
    run_ssh 'docker compose version || apt-get install -y docker-compose-plugin'

    # Swap 2GB
    run_ssh 'test -f /swapfile || (fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo "/swapfile none swap sw 0 0" >> /etc/fstab)'

    # 방화벽
    run_ssh 'ufw allow 22/tcp && ufw allow 5001/tcp && ufw --force enable'

    # 디렉토리 생성
    run_ssh "mkdir -p ${REMOTE_DIR}"

    log_info "서버 초기 설정 완료"
}

# 코드 업로드
upload_code() {
    log_info "코드 업로드 중..."

    rsync -avz --progress \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.state' \
        --exclude='logs' \
        --exclude='*.log' \
        --exclude='.env' \
        --exclude='node_modules' \
        --exclude='frontend' \
        --exclude='deployment' \
        --exclude='deepseek_env' \
        --exclude='.DS_Store' \
        --exclude='Users' \
        --exclude='archive' \
        --exclude='*.json.bak' \
        "${LOCAL_DIR}/" \
        "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/"

    log_info "코드 업로드 완료"
}

# 환경 변수 업로드
upload_env() {
    log_info ".env 파일 확인 중..."

    if [ ! -f "${LOCAL_DIR}/.env" ]; then
        log_error "로컬 .env 파일이 없습니다!"
        return 1
    fi

    if ! run_ssh "test -f ${REMOTE_DIR}/.env"; then
        log_warn "서버에 .env 파일이 없습니다. 업로드합니다..."
        scp "${LOCAL_DIR}/.env" "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/.env"
        log_info ".env 업로드 완료"
    else
        log_info "서버에 .env 파일 존재 (덮어쓰지 않음)"
    fi
}

# 서비스 빌드 및 시작
start_service() {
    log_info "서비스 빌드 및 시작..."

    run_ssh "cd ${REMOTE_DIR} && docker compose build --no-cache"
    run_ssh "cd ${REMOTE_DIR} && docker compose down" || true
    run_ssh "cd ${REMOTE_DIR} && docker compose up -d"

    sleep 5
    run_ssh "cd ${REMOTE_DIR} && docker compose ps"
    run_ssh "cd ${REMOTE_DIR} && docker compose logs --tail=20"

    log_info "서비스 시작 완료"
}

# 서비스 재시작
restart_service() {
    log_info "서비스 재시작..."
    run_ssh "cd ${REMOTE_DIR} && docker compose restart"
    sleep 3
    run_ssh "cd ${REMOTE_DIR} && docker compose ps"
    log_info "재시작 완료"
}

# 로그 확인
show_logs() {
    run_ssh "cd ${REMOTE_DIR} && docker compose logs --tail=100 -f"
}

# 상태 확인
show_status() {
    run_ssh "cd ${REMOTE_DIR} && docker compose ps"
    run_ssh "docker stats --no-stream"
    run_ssh "df -h /"
}

# 메인 로직
case "${1:-update}" in
    --init)
        log_info "=== 첫 배포 시작 ==="
        init_server
        upload_code
        upload_env
        start_service
        show_status
        ;;
    --update)
        log_info "=== 코드 업데이트 ==="
        upload_code
        start_service
        ;;
    --restart)
        restart_service
        ;;
    --logs)
        show_logs
        ;;
    --status)
        show_status
        ;;
    *)
        echo "사용법: $0 [--init|--update|--restart|--logs|--status]"
        echo ""
        echo "옵션:"
        echo "  --init    : 첫 배포 (서버 초기 설정 + 코드 업로드 + 시작)"
        echo "  --update  : 코드 업데이트 및 재시작 (기본값)"
        echo "  --restart : 서비스 재시작만"
        echo "  --logs    : 실시간 로그 확인"
        echo "  --status  : 서버 상태 확인"
        ;;
esac

log_info "=== 완료 ==="
