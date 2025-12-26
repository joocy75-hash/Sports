#!/bin/bash
set -e

echo "=========================================="
echo "스포츠 분석 AI - 데이터베이스 초기화"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# PostgreSQL 상태 확인
echo -e "\n${YELLOW}[1/5] PostgreSQL 상태 확인...${NC}"
if ! command -v psql &> /dev/null; then
    echo -e "${RED}❌ PostgreSQL이 설치되지 않았습니다.${NC}"
    echo "설치 방법:"
    echo "  brew install postgresql"
    exit 1
fi

if ! brew services list | grep postgresql | grep started > /dev/null; then
    echo -e "${YELLOW}PostgreSQL 시작 중...${NC}"
    brew services start postgresql
    sleep 3
fi

echo -e "${GREEN}✅ PostgreSQL 실행 중${NC}"

# 데이터베이스 생성
echo -e "\n${YELLOW}[2/5] 데이터베이스 생성...${NC}"
DB_NAME="sports_betting_db"

if psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo -e "${GREEN}✅ 데이터베이스 '$DB_NAME'가 이미 존재합니다${NC}"
else
    createdb $DB_NAME
    echo -e "${GREEN}✅ 데이터베이스 '$DB_NAME' 생성 완료${NC}"
fi

# 마이그레이션 실행
echo -e "\n${YELLOW}[3/5] 마이그레이션 실행...${NC}"
cd "$(dirname "$0")/.."

if [ ! -f "alembic.ini" ]; then
    echo -e "${RED}❌ alembic.ini 파일이 없습니다${NC}"
    exit 1
fi

alembic upgrade head
echo -e "${GREEN}✅ 마이그레이션 완료${NC}"

# 연결 테스트
echo -e "\n${YELLOW}[4/5] 연결 테스트...${NC}"
python3 << 'EOF'
import asyncio
import sys
from src.db.session import get_session

async def test():
    try:
        async with get_session() as session:
            result = await session.execute("SELECT 1")
            print("✅ 데이터베이스 연결 성공")
            return True
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False

success = asyncio.run(test())
sys.exit(0 if success else 1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 연결 테스트 통과${NC}"
else
    echo -e "${RED}❌ 연결 테스트 실패${NC}"
    echo "다음을 확인하세요:"
    echo "  1. .env 파일의 POSTGRES_DSN 설정"
    echo "  2. PostgreSQL 서버 실행 여부"
    exit 1
fi

# Redis 확인 (선택사항)
echo -e "\n${YELLOW}[5/5] Redis 상태 확인 (선택사항)...${NC}"
if command -v redis-cli &> /dev/null; then
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis 실행 중${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis가 설치되어 있지만 실행되지 않았습니다${NC}"
        echo "Redis 시작: brew services start redis"
    fi
else
    echo -e "${YELLOW}⚠️  Redis가 설치되지 않았습니다 (캐싱 기능 비활성화)${NC}"
    echo "설치 방법: brew install redis"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ 데이터베이스 초기화 완료!${NC}"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "  1. API 키 설정: vim .env"
echo "  2. 서버 실행: python src/api/unified_server.py"
echo "  3. 데이터 수집: python main_enhanced.py"
echo ""
