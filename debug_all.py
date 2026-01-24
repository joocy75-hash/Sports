#!/usr/bin/env python3
"""
전체 코드 디버깅 통합 도구

이 스크립트는 프로젝트 전체를 체계적으로 디버깅합니다:
1. 코드 품질 검사 (syntax, imports, type hints)
2. 설정 파일 검증
3. 데이터베이스 연결 테스트
4. API 엔드포인트 검증
5. 로깅 시스템 테스트
6. 종합 리포트 생성
"""

import asyncio
import ast
import importlib
import inspect
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_report.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class CodeDebugger:
    """전체 코드 디버깅 클래스"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = {
            'syntax_errors': [],
            'import_errors': [],
            'type_errors': [],
            'config_errors': [],
            'db_errors': [],
            'api_errors': [],
            'warnings': [],
            'statistics': {}
        }
        self.stats = defaultdict(int)
    
    def find_python_files(self) -> List[Path]:
        """모든 Python 파일 찾기"""
        python_files = []
        exclude_dirs = {'__pycache__', '.git', 'node_modules', '.venv', 'venv', 'env'}
        
        for root, dirs, files in os.walk(self.project_root):
            # 제외할 디렉토리 필터링
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        
        return python_files
    
    def check_syntax(self, file_path: Path) -> Tuple[bool, str]:
        """파일 구문 검사"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            ast.parse(source, filename=str(file_path))
            return True, ""
        except SyntaxError as e:
            error_msg = f"라인 {e.lineno}: {e.msg}"
            return False, error_msg
        except Exception as e:
            return False, str(e)
    
    def check_imports(self, file_path: Path) -> List[str]:
        """임포트 오류 검사"""
        errors = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        try:
                            importlib.import_module(alias.name.split('.')[0])
                        except ImportError as e:
                            errors.append(f"{alias.name}: {str(e)}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        try:
                            importlib.import_module(node.module.split('.')[0])
                        except ImportError as e:
                            errors.append(f"{node.module}: {str(e)}")
        except Exception as e:
            errors.append(f"파일 파싱 오류: {str(e)}")
        
        return errors
    
    def analyze_code_quality(self, file_path: Path) -> Dict[str, Any]:
        """코드 품질 분석"""
        quality = {
            'lines': 0,
            'functions': 0,
            'classes': 0,
            'async_functions': 0,
            'type_hints': 0,
            'docstrings': 0,
            'complexity_warnings': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
                lines = source.split('\n')
                quality['lines'] = len(lines)
            
            tree = ast.parse(source)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    quality['functions'] += 1
                    if any(isinstance(n, ast.AsyncFunctionDef) for n in [node]):
                        quality['async_functions'] += 1
                    
                    # 타입 힌트 확인
                    if node.returns:
                        quality['type_hints'] += 1
                    if any(arg.annotation for arg in node.args.args):
                        quality['type_hints'] += 1
                    
                    # docstring 확인
                    if ast.get_docstring(node):
                        quality['docstrings'] += 1
                
                elif isinstance(node, ast.ClassDef):
                    quality['classes'] += 1
                    if ast.get_docstring(node):
                        quality['docstrings'] += 1
                
                # 복잡도 경고 (매우 긴 함수)
                if isinstance(node, ast.FunctionDef):
                    func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    if func_lines > 100:
                        quality['complexity_warnings'].append(
                            f"{node.name}: {func_lines}줄 (너무 긴 함수)"
                        )
        
        except Exception as e:
            logger.warning(f"{file_path}: 코드 분석 중 오류 - {e}")
        
        return quality
    
    def check_config_files(self) -> List[str]:
        """설정 파일 검증"""
        errors = []
        
        # .env 파일 확인
        env_file = self.project_root / '.env'
        if not env_file.exists():
            errors.append(".env 파일이 없습니다")
        else:
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
                
                # 필수 환경 변수 확인
                required_vars = [
                    'DATABASE_URL', 'postgres_dsn', 'redis_url'
                ]
                for var in required_vars:
                    if not os.getenv(var):
                        errors.append(f"환경 변수 {var}가 설정되지 않았습니다")
            except Exception as e:
                errors.append(f".env 파일 로드 오류: {e}")
        
        # settings.py 확인
        settings_file = self.project_root / 'src' / 'config' / 'settings.py'
        if settings_file.exists():
            try:
                sys.path.insert(0, str(self.project_root))
                from src.config.settings import Settings
                settings = Settings()
                logger.info("설정 파일 로드 성공")
            except Exception as e:
                errors.append(f"설정 파일 로드 오류: {e}")
        
        return errors
    
    async def test_database_connection(self) -> Tuple[bool, str]:
        """데이터베이스 연결 테스트"""
        try:
            from src.db.session import get_db_session
            from sqlalchemy import text
            
            async with get_db_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.fetchone()
            return True, "데이터베이스 연결 성공"
        except Exception as e:
            return False, f"데이터베이스 연결 실패: {str(e)}"
    
    def test_api_endpoints(self) -> List[Dict[str, Any]]:
        """API 엔드포인트 검증"""
        errors = []
        
        try:
            api_file = self.project_root / 'src' / 'api' / 'unified_server.py'
            if not api_file.exists():
                return [{"error": "API 서버 파일을 찾을 수 없습니다"}]
            
            with open(api_file, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            endpoints = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # FastAPI 데코레이터 찾기
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call):
                            if isinstance(decorator.func, ast.Attribute):
                                if decorator.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                                    # 경로 추출
                                    if decorator.args:
                                        path = decorator.args[0].value if isinstance(decorator.args[0], ast.Constant) else "unknown"
                                        endpoints.append({
                                            'method': decorator.func.attr.upper(),
                                            'path': path,
                                            'function': node.name
                                        })
            
            logger.info(f"발견된 API 엔드포인트: {len(endpoints)}개")
            return endpoints
            
        except Exception as e:
            return [{"error": f"API 엔드포인트 분석 오류: {str(e)}"}]
    
    def run_full_debug(self) -> Dict[str, Any]:
        """전체 디버깅 실행"""
        logger.info("=" * 80)
        logger.info("전체 코드 디버깅 시작")
        logger.info("=" * 80)
        
        # 1. Python 파일 찾기
        logger.info("\n[1단계] Python 파일 검색 중...")
        python_files = self.find_python_files()
        logger.info(f"발견된 Python 파일: {len(python_files)}개")
        self.stats['total_files'] = len(python_files)
        
        # 2. 구문 검사
        logger.info("\n[2단계] 구문 검사 중...")
        for file_path in python_files:
            is_valid, error = self.check_syntax(file_path)
            if not is_valid:
                self.results['syntax_errors'].append({
                    'file': str(file_path.relative_to(self.project_root)),
                    'error': error
                })
                self.stats['syntax_errors'] += 1
            else:
                self.stats['valid_files'] += 1
        
        # 3. 임포트 검사
        logger.info("\n[3단계] 임포트 검사 중...")
        for file_path in python_files:
            import_errors = self.check_imports(file_path)
            if import_errors:
                self.results['import_errors'].append({
                    'file': str(file_path.relative_to(self.project_root)),
                    'errors': import_errors
                })
                self.stats['import_errors'] += len(import_errors)
        
        # 4. 코드 품질 분석
        logger.info("\n[4단계] 코드 품질 분석 중...")
        total_lines = 0
        total_functions = 0
        total_classes = 0
        
        for file_path in python_files:
            quality = self.analyze_code_quality(file_path)
            total_lines += quality['lines']
            total_functions += quality['functions']
            total_classes += quality['classes']
            
            if quality['complexity_warnings']:
                self.results['warnings'].append({
                    'file': str(file_path.relative_to(self.project_root)),
                    'warnings': quality['complexity_warnings']
                })
        
        self.stats['total_lines'] = total_lines
        self.stats['total_functions'] = total_functions
        self.stats['total_classes'] = total_classes
        
        # 5. 설정 파일 검증
        logger.info("\n[5단계] 설정 파일 검증 중...")
        config_errors = self.check_config_files()
        if config_errors:
            self.results['config_errors'] = config_errors
            self.stats['config_errors'] = len(config_errors)
        
        # 6. 데이터베이스 연결 테스트
        logger.info("\n[6단계] 데이터베이스 연결 테스트 중...")
        try:
            success, message = asyncio.run(self.test_database_connection())
            if not success:
                self.results['db_errors'].append(message)
                self.stats['db_errors'] += 1
            else:
                logger.info(message)
        except Exception as e:
            self.results['db_errors'].append(f"DB 테스트 오류: {str(e)}")
            self.stats['db_errors'] += 1
        
        # 7. API 엔드포인트 검증
        logger.info("\n[7단계] API 엔드포인트 검증 중...")
        api_endpoints = self.test_api_endpoints()
        self.stats['api_endpoints'] = len(api_endpoints)
        
        # 통계 저장
        self.results['statistics'] = dict(self.stats)
        self.results['api_endpoints'] = api_endpoints
        
        return self.results
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """디버깅 리포트 생성"""
        report = []
        report.append("=" * 80)
        report.append("전체 코드 디버깅 리포트")
        report.append(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        # 통계
        report.append("\n📊 통계")
        report.append("-" * 80)
        stats = results.get('statistics', {})
        report.append(f"전체 파일 수: {stats.get('total_files', 0)}")
        report.append(f"유효한 파일 수: {stats.get('valid_files', 0)}")
        report.append(f"전체 코드 라인: {stats.get('total_lines', 0):,}")
        report.append(f"전체 함수 수: {stats.get('total_functions', 0)}")
        report.append(f"전체 클래스 수: {stats.get('total_classes', 0)}")
        report.append(f"API 엔드포인트 수: {stats.get('api_endpoints', 0)}")
        
        # 오류 요약
        report.append("\n❌ 오류 요약")
        report.append("-" * 80)
        report.append(f"구문 오류: {len(results.get('syntax_errors', []))}개")
        report.append(f"임포트 오류: {len(results.get('import_errors', []))}개")
        report.append(f"설정 오류: {len(results.get('config_errors', []))}개")
        report.append(f"데이터베이스 오류: {len(results.get('db_errors', []))}개")
        report.append(f"경고: {len(results.get('warnings', []))}개")
        
        # 상세 오류
        if results.get('syntax_errors'):
            report.append("\n🔴 구문 오류 상세")
            report.append("-" * 80)
            for error in results['syntax_errors'][:10]:  # 최대 10개만 표시
                report.append(f"  • {error['file']}: {error['error']}")
            if len(results['syntax_errors']) > 10:
                report.append(f"  ... 외 {len(results['syntax_errors']) - 10}개")
        
        if results.get('import_errors'):
            report.append("\n🔴 임포트 오류 상세")
            report.append("-" * 80)
            for error in results['import_errors'][:10]:
                report.append(f"  • {error['file']}:")
                for err in error['errors'][:3]:
                    report.append(f"    - {err}")
        
        if results.get('config_errors'):
            report.append("\n🔴 설정 오류 상세")
            report.append("-" * 80)
            for error in results['config_errors']:
                report.append(f"  • {error}")
        
        if results.get('db_errors'):
            report.append("\n🔴 데이터베이스 오류 상세")
            report.append("-" * 80)
            for error in results['db_errors']:
                report.append(f"  • {error}")
        
        if results.get('warnings'):
            report.append("\n⚠️ 경고 상세")
            report.append("-" * 80)
            for warning in results['warnings'][:10]:
                report.append(f"  • {warning['file']}:")
                for w in warning['warnings']:
                    report.append(f"    - {w}")
        
        # API 엔드포인트
        if results.get('api_endpoints'):
            report.append("\n🌐 API 엔드포인트")
            report.append("-" * 80)
            for endpoint in results['api_endpoints'][:20]:
                if 'error' not in endpoint:
                    report.append(f"  • {endpoint['method']} {endpoint['path']} -> {endpoint['function']}")
        
        report.append("\n" + "=" * 80)
        report.append("디버깅 완료")
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """메인 함수"""
    project_root = Path(__file__).parent
    debugger = CodeDebugger(project_root)
    
    try:
        results = debugger.run_full_debug()
        report = debugger.generate_report(results)
        
        # 콘솔 출력
        print("\n" + report)
        
        # 파일 저장
        report_file = project_root / 'debug_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # JSON 저장
        json_file = project_root / 'debug_report.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n리포트 저장 완료:")
        logger.info(f"  - 텍스트: {report_file}")
        logger.info(f"  - JSON: {json_file}")
        
        # 종료 코드
        total_errors = (
            len(results.get('syntax_errors', [])) +
            len(results.get('import_errors', [])) +
            len(results.get('config_errors', [])) +
            len(results.get('db_errors', []))
        )
        
        if total_errors > 0:
            logger.warning(f"\n⚠️ 총 {total_errors}개의 오류가 발견되었습니다.")
            sys.exit(1)
        else:
            logger.info("\n✅ 오류가 발견되지 않았습니다.")
            sys.exit(0)
    
    except KeyboardInterrupt:
        logger.info("\n\n디버깅이 중단되었습니다.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n치명적 오류 발생: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
