#!/usr/bin/env python3
"""
향상된 로깅 시스템

디버깅을 위한 상세한 로깅 기능 제공:
- 함수 호출 추적
- 성능 프로파일링
- 에러 스택 트레이스
- 컨텍스트 정보
"""

import functools
import logging
import time
import traceback
from datetime import datetime
from typing import Callable, Any, Optional
from pathlib import Path

# 로깅 설정
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 로거 설정
def setup_enhanced_logging(level: str = "DEBUG", log_to_file: bool = True):
    """향상된 로깅 설정"""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    handlers = [logging.StreamHandler()]
    
    if log_to_file:
        # 날짜별 로그 파일
        log_file = LOG_DIR / f"debug_{datetime.now().strftime('%Y%m%d')}.log"
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )
    
    # SQLAlchemy 로깅 (쿼리 추적)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


def trace_function(func: Callable = None, *, log_args: bool = True, log_result: bool = True):
    """함수 호출 추적 데코레이터"""
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        async def async_wrapper(*args, **kwargs):
            logger = logging.getLogger(f.__module__)
            func_name = f"{f.__module__}.{f.__name__}"
            
            # 시작 로깅
            if log_args:
                logger.debug(f"▶ {func_name} 호출 시작")
                if args:
                    logger.debug(f"  인자: {args}")
                if kwargs:
                    logger.debug(f"  키워드 인자: {kwargs}")
            else:
                logger.debug(f"▶ {func_name} 호출 시작")
            
            start_time = time.time()
            try:
                result = await f(*args, **kwargs)
                elapsed = time.time() - start_time
                
                if log_result:
                    logger.debug(f"✓ {func_name} 완료 ({elapsed:.3f}초)")
                    if result is not None:
                        logger.debug(f"  결과: {result}")
                else:
                    logger.debug(f"✓ {func_name} 완료 ({elapsed:.3f}초)")
                
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"✗ {func_name} 실패 ({elapsed:.3f}초): {type(e).__name__}: {e}")
                logger.debug(f"스택 트레이스:\n{traceback.format_exc()}")
                raise
        
        @functools.wraps(f)
        def sync_wrapper(*args, **kwargs):
            logger = logging.getLogger(f.__module__)
            func_name = f"{f.__module__}.{f.__name__}"
            
            if log_args:
                logger.debug(f"▶ {func_name} 호출 시작")
                if args:
                    logger.debug(f"  인자: {args}")
                if kwargs:
                    logger.debug(f"  키워드 인자: {kwargs}")
            else:
                logger.debug(f"▶ {func_name} 호출 시작")
            
            start_time = time.time()
            try:
                result = f(*args, **kwargs)
                elapsed = time.time() - start_time
                
                if log_result:
                    logger.debug(f"✓ {func_name} 완료 ({elapsed:.3f}초)")
                    if result is not None:
                        logger.debug(f"  결과: {result}")
                else:
                    logger.debug(f"✓ {func_name} 완료 ({elapsed:.3f}초)")
                
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"✗ {func_name} 실패 ({elapsed:.3f}초): {type(e).__name__}: {e}")
                logger.debug(f"스택 트레이스:\n{traceback.format_exc()}")
                raise
        
        if inspect.iscoroutinefunction(f):
            return async_wrapper
        else:
            return sync_wrapper
    
    if func is None:
        return decorator
    else:
        return decorator(func)


def log_performance(threshold: float = 1.0):
    """성능 프로파일링 데코레이터 (지정 시간 초과 시 경고)"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                if elapsed > threshold:
                    logger.warning(
                        f"⚠ {func.__name__} 실행 시간이 {threshold}초를 초과했습니다: {elapsed:.3f}초"
                    )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"{func.__name__} 실패 ({elapsed:.3f}초): {e}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                if elapsed > threshold:
                    logger.warning(
                        f"⚠ {func.__name__} 실행 시간이 {threshold}초를 초과했습니다: {elapsed:.3f}초"
                    )
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"{func.__name__} 실패 ({elapsed:.3f}초): {e}")
                raise
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class DebugContext:
    """디버깅 컨텍스트 매니저"""
    
    def __init__(self, name: str, log_level: str = "DEBUG"):
        self.name = name
        self.log_level = log_level
        self.logger = logging.getLogger(__name__)
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        log_func = getattr(self.logger, self.log_level.lower(), self.logger.debug)
        log_func(f"▶▶ {self.name} 시작")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        log_func = getattr(self.logger, self.log_level.lower(), self.logger.debug)
        
        if exc_type is None:
            log_func(f"✓✓ {self.name} 완료 ({elapsed:.3f}초)")
        else:
            log_func(f"✗✗ {self.name} 실패 ({elapsed:.3f}초): {exc_type.__name__}: {exc_val}")
            log_func(f"스택 트레이스:\n{''.join(traceback.format_tb(exc_tb))}")
        
        return False  # 예외를 다시 발생시킴


# 사용 예시
if __name__ == "__main__":
    setup_enhanced_logging(level="DEBUG")
    logger = logging.getLogger(__name__)
    
    @trace_function
    async def test_async_function(x: int, y: int) -> int:
        await asyncio.sleep(0.1)
        return x + y
    
    @trace_function
    def test_sync_function(x: int, y: int) -> int:
        return x * y
    
    @log_performance(threshold=0.5)
    async def slow_function():
        await asyncio.sleep(0.6)
        return "완료"
    
    async def main():
        result1 = await test_async_function(1, 2)
        result2 = test_sync_function(3, 4)
        result3 = await slow_function()
        
        logger.info(f"결과: {result1}, {result2}, {result3}")
        
        with DebugContext("테스트 블록"):
            time.sleep(0.1)
            logger.info("테스트 블록 내부")
    
    import asyncio
    asyncio.run(main())
