#!/bin/bash
#
# 프로토 14경기 AI 분석 시스템 - 자동 배포 스크립트
#
# 사용법:
#   ./deploy.sh <server-ip>
#
# 예시:
#   ./deploy.sh 5.161.112.248
#

set -e  # 에러 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수 정의
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 서버 IP 확인
if [ -z "$1" ]; then
    log_error "서버 IP를 입력하세요"
    echo "사용법: $0 <server-ip>"
    echo "예시: $0 5.161.112.248"
    exit 1
fi

SERVER_IP=$1
SERVER_PATH="/opt/sports-analysis"
SERVER_USER="root"

log_info "배포 시작: $SERVER_IP"
echo ""

# 1. 서버 연결 테스트
log_info "서버 연결 테스트 중..."
if ssh -o ConnectTimeout=10 -o BatchMode=yes $SERVER_USER@$SERVER_IP "echo '연결 성공'" 2>/dev/null; then
    log_success "서버 연결 성공"
else
    log_error "서버 연결 실패. SSH 키를 확인하세요."
    log_warning "SSH 키 등록: ssh-copy-id $SERVER_USER@$SERVER_IP"
    exit 1
fi
echo ""

# 2. 프로젝트 파일 전송
log_info "프로젝트 파일 전송 중..."

# 제외할 파일/디렉토리
EXCLUDES=(
    --exclude 'venv'
    --exclude '__pycache__'
    --exclude '*.pyc'
    --exclude '.git'
    --exclude '.state/predictions'
    --exclude '.state/results'
    --exclude 'node_modules'
    --exclude 'frontend/node_modules'
    --exclude 'frontend/build'
    --exclude 'scheduler.log'
    --exclude '*.log'
    --exclude '.DS_Store'
    --exclude 'test_*.py'
)

rsync -avz --progress "${EXCLUDES[@]}" \
    --exclude '.env' \
    ./ $SERVER_USER@$SERVER_IP:$SERVER_PATH/

log_success "파일 전송 완료"
echo ""

# 3. 환경 변수 전송 (별도 확인)
log_warning ".env 파일은 보안상 자동 전송하지 않습니다."
echo "수동으로 전송하려면:"
echo "  scp .env $SERVER_USER@$SERVER_IP:$SERVER_PATH/.env"
echo ""
read -p "계속하시겠습니까? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "배포 중단"
    exit 0
fi
echo ""

# 4. 서버에서 설정 실행
log_info "서버 환경 설정 중..."

ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
set -e

cd /opt/sports-analysis

# 색상 정의 (서버)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[서버]${NC} $1"; }
log_success() { echo -e "${GREEN}[서버]${NC} $1"; }
log_error() { echo -e "${RED}[서버]${NC} $1"; }

# Python 버전 확인
log_info "Python 버전 확인..."
if ! command -v python3.11 &> /dev/null; then
    log_error "Python 3.11이 설치되어 있지 않습니다."
    log_info "설치 중..."
    apt-get update
    apt-get install -y python3.11 python3.11-venv python3-pip
fi

PYTHON_VERSION=$(python3.11 --version)
log_success "Python 버전: $PYTHON_VERSION"

# 가상환경 생성
log_info "가상환경 생성/업데이트 중..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
    log_success "가상환경 생성 완료"
else
    log_info "기존 가상환경 사용"
fi

# 가상환경 활성화 및 의존성 설치
source venv/bin/activate
log_info "의존성 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt

# Playwright 설치
log_info "Playwright 브라우저 설치 중..."
playwright install chromium
playwright install-deps chromium

log_success "의존성 설치 완료"

# 상태 디렉토리 생성
log_info "상태 디렉토리 생성 중..."
mkdir -p .state/predictions/soccer_wdl
mkdir -p .state/predictions/basketball_w5l
mkdir -p .state/results
log_success "디렉토리 생성 완료"

# .env 파일 확인
if [ ! -f ".env" ]; then
    log_error ".env 파일이 없습니다!"
    log_error "배포를 계속하려면 .env 파일을 업로드하세요:"
    log_error "  scp .env root@$(hostname -I | awk '{print $1}'):/opt/sports-analysis/.env"
    exit 1
fi

log_success "서버 환경 설정 완료"
ENDSSH

log_success "서버 설정 완료"
echo ""

# 5. Systemd 서비스 등록
log_info "Systemd 서비스 등록 중..."

ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
set -e

cd /opt/sports-analysis

log_info() { echo -e "\033[0;34m[서버]\033[0m $1"; }
log_success() { echo -e "\033[0;32m[서버]\033[0m $1"; }

# 서비스 파일 복사
log_info "서비스 파일 설치 중..."
cp sports-scheduler.service /etc/systemd/system/

# systemd 리로드
systemctl daemon-reload

# 서비스 활성화
systemctl enable sports-scheduler

log_success "Systemd 서비스 등록 완료"
ENDSSH

log_success "서비스 등록 완료"
echo ""

# 6. 서비스 시작
log_info "스케줄러 시작 중..."

ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
set -e

log_info() { echo -e "\033[0;34m[서버]\033[0m $1"; }
log_success() { echo -e "\033[0;32m[서버]\033[0m $1"; }
log_warning() { echo -e "\033[1;33m[서버]\033[0m $1"; }

# 기존 서비스 중지 (실행 중이면)
if systemctl is-active --quiet sports-scheduler; then
    log_info "기존 스케줄러 중지 중..."
    systemctl stop sports-scheduler
    sleep 2
fi

# 서비스 시작
log_info "스케줄러 시작 중..."
systemctl start sports-scheduler

# 상태 확인
sleep 3
if systemctl is-active --quiet sports-scheduler; then
    log_success "스케줄러 시작 성공!"
else
    log_warning "스케줄러 시작 실패. 로그를 확인하세요:"
    log_warning "  journalctl -u sports-scheduler -n 50"
    exit 1
fi
ENDSSH

log_success "스케줄러 시작 완료"
echo ""

# 7. 상태 확인
log_info "최종 상태 확인 중..."
echo ""

ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
echo "=========================================="
echo "서비스 상태:"
echo "=========================================="
systemctl status sports-scheduler --no-pager | head -15

echo ""
echo "=========================================="
echo "최근 로그:"
echo "=========================================="
journalctl -u sports-scheduler -n 20 --no-pager

echo ""
echo "=========================================="
echo "스케줄러 상태:"
echo "=========================================="
cd /opt/sports-analysis
source venv/bin/activate
python scheduler_main.py --status
ENDSSH

echo ""
log_success "=========================================="
log_success "배포 완료!"
log_success "=========================================="
echo ""
log_info "유용한 명령어:"
echo ""
echo "  # 서비스 상태 확인"
echo "  ssh $SERVER_USER@$SERVER_IP 'systemctl status sports-scheduler'"
echo ""
echo "  # 실시간 로그 확인"
echo "  ssh $SERVER_USER@$SERVER_IP 'journalctl -u sports-scheduler -f'"
echo ""
echo "  # 스케줄러 상태 확인"
echo "  ssh $SERVER_USER@$SERVER_IP 'cd $SERVER_PATH && source venv/bin/activate && python scheduler_main.py --status'"
echo ""
echo "  # 서비스 재시작"
echo "  ssh $SERVER_USER@$SERVER_IP 'systemctl restart sports-scheduler'"
echo ""
echo "  # 서비스 중지"
echo "  ssh $SERVER_USER@$SERVER_IP 'systemctl stop sports-scheduler'"
echo ""
log_info "텔레그램으로 시작 알림이 전송되었는지 확인하세요!"
echo ""
