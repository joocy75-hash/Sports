#!/bin/bash
# 빠른 디버깅 스크립트

set -e

echo "=========================================="
echo "전체 코드 빠른 디버깅"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 프로젝트 루트
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo -e "\n${GREEN}[1/6] Python 구문 검사${NC}"
echo "----------------------------------------"
if python3 -m py_compile $(find . -name "*.py" -not -path "./.venv/*" -not -path "./venv/*" -not -path "./__pycache__/*" | head -20) 2>&1; then
    echo -e "${GREEN}✓ 구문 검사 통과${NC}"
else
    echo -e "${RED}✗ 구문 오류 발견${NC}"
fi

echo -e "\n${GREEN}[2/6] Import 검사${NC}"
echo "----------------------------------------"
python3 -c "
import sys
import importlib.util
from pathlib import Path

errors = []
for py_file in Path('.').rglob('*.py'):
    if '.venv' in str(py_file) or 'venv' in str(py_file) or '__pycache__' in str(py_file):
        continue
    try:
        spec = importlib.util.spec_from_file_location('test', py_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
    except Exception as e:
        errors.append(f'{py_file}: {e}')

if errors:
    print('Import 오류:')
    for err in errors[:10]:
        print(f'  - {err}')
    sys.exit(1)
else:
    print('✓ Import 검사 통과')
" || echo -e "${YELLOW}⚠ 일부 Import 오류 (정상일 수 있음)${NC}"

echo -e "\n${GREEN}[3/6] 환경 변수 검사${NC}"
echo "----------------------------------------"
if [ -f .env ]; then
    echo "✓ .env 파일 존재"
    source .env
    REQUIRED_VARS=("DATABASE_URL" "postgres_dsn" "redis_url")
    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ]; then
            echo -e "${YELLOW}⚠ $var 설정되지 않음${NC}"
        else
            echo -e "${GREEN}✓ $var 설정됨${NC}"
        fi
    done
else
    echo -e "${YELLOW}⚠ .env 파일 없음${NC}"
fi

echo -e "\n${GREEN}[4/6] 데이터베이스 연결 테스트${NC}"
echo "----------------------------------------"
python3 -c "
import asyncio
import sys
from dotenv import load_dotenv
load_dotenv()

async def test_db():
    try:
        from src.db.session import get_db_session
        from sqlalchemy import text
        async with get_db_session() as session:
            await session.execute(text('SELECT 1'))
        print('✓ 데이터베이스 연결 성공')
        return True
    except Exception as e:
        print(f'✗ 데이터베이스 연결 실패: {e}')
        return False

if asyncio.run(test_db()):
    sys.exit(0)
else:
    sys.exit(1)
" || echo -e "${YELLOW}⚠ 데이터베이스 연결 실패 (서버가 실행 중이 아닐 수 있음)${NC}"

echo -e "\n${GREEN}[5/6] 코드 품질 검사${NC}"
echo "----------------------------------------"
if command -v pylint &> /dev/null; then
    echo "Pylint 실행 중..."
    pylint --disable=all --enable=E,F $(find src -name "*.py" | head -10) 2>/dev/null || true
else
    echo -e "${YELLOW}⚠ Pylint가 설치되지 않음 (선택사항)${NC}"
fi

echo -e "\n${GREEN}[6/6] 통합 디버깅 실행${NC}"
echo "----------------------------------------"
if [ -f debug_all.py ]; then
    python3 debug_all.py
else
    echo -e "${YELLOW}⚠ debug_all.py가 없습니다${NC}"
fi

echo -e "\n${GREEN}=========================================="
echo "디버깅 완료"
echo "==========================================${NC}"
