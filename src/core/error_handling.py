"""
표준 에러 핸들링 모듈

시스템 전반의 에러 핸들링을 표준화합니다.
- 비동기 함수용 데코레이터
- 커스텀 예외 클래스
- 에러 로깅 표준화
"""

import asyncio
import functools
import logging
from typing import Callable, Any, Optional, Type, TypeVar
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ==================== 커스텀 예외 클래스 ====================

class SportsAnalysisError(Exception):
    """스포츠 분석 시스템 기본 예외"""
    
    def __init__(self, message: str, code: str = "UNKNOWN", details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class DataCollectionError(SportsAnalysisError):
    """데이터 수집 관련 예외"""
    
    def __init__(self, message: str, source: str = "unknown", details: dict = None):
        super().__init__(message, "DATA_COLLECTION_ERROR", details)
        self.source = source


class CrawlerError(DataCollectionError):
    """크롤러 예외"""
    
    def __init__(self, message: str, url: str = None, details: dict = None):
        super().__init__(message, "crawler", details)
        self.url = url
        self.details["url"] = url


class APIError(DataCollectionError):
    """외부 API 예외"""
    
    def __init__(self, message: str, api_name: str = "unknown", status_code: int = None, details: dict = None):
        super().__init__(message, api_name, details)
        self.status_code = status_code
        self.details["status_code"] = status_code


class AIAnalysisError(SportsAnalysisError):
    """AI 분석 관련 예외"""
    
    def __init__(self, message: str, provider: str = "unknown", details: dict = None):
        super().__init__(message, "AI_ANALYSIS_ERROR", details)
        self.provider = provider
        self.details["provider"] = provider


class ValidationError(SportsAnalysisError):
    """데이터 검증 예외"""
    
    def __init__(self, message: str, field: str = None, details: dict = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field
        self.details["field"] = field


class ConfigurationError(SportsAnalysisError):
    """설정 관련 예외"""
    
    def __init__(self, message: str, config_key: str = None, details: dict = None):
        super().__init__(message, "CONFIGURATION_ERROR", details)
        self.config_key = config_key
        self.details["config_key"] = config_key


# ==================== 에러 핸들링 데코레이터 ====================

def async_error_handler(
    func_name: str = None,
    default_return: Any = None,
    reraise: bool = True,
    log_level: str = "error",
    exceptions: tuple = (Exception,)
):
    """
    비동기 함수용 표준 에러 핸들링 데코레이터
    
    Args:
        func_name: 로깅에 사용할 함수 이름 (None이면 실제 함수명 사용)
        default_return: 예외 발생 시 반환할 기본값
        reraise: 예외를 다시 발생시킬지 여부
        log_level: 로깅 레벨 ("error", "warning", "info")
        exceptions: 처리할 예외 튜플
    
    Usage:
        @async_error_handler(func_name="크롤러", default_return=None)
        async def crawl_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            name = func_name or func.__name__
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                # 로깅
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"[{name}] 오류 발생: {type(e).__name__}: {e}")
                
                # 상세 정보 로깅 (디버그 모드)
                if logger.isEnabledFor(logging.DEBUG):
                    import traceback
                    logger.debug(f"[{name}] 스택 트레이스:\n{traceback.format_exc()}")
                
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def sync_error_handler(
    func_name: str = None,
    default_return: Any = None,
    reraise: bool = True,
    log_level: str = "error",
    exceptions: tuple = (Exception,)
):
    """
    동기 함수용 표준 에러 핸들링 데코레이터
    
    Usage:
        @sync_error_handler(func_name="파서", default_return={})
        def parse_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            name = func_name or func.__name__
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"[{name}] 오류 발생: {type(e).__name__}: {e}")
                
                if logger.isEnabledFor(logging.DEBUG):
                    import traceback
                    logger.debug(f"[{name}] 스택 트레이스:\n{traceback.format_exc()}")
                
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    func_name: str = None
):
    """
    비동기 함수 재시도 데코레이터
    
    Args:
        max_retries: 최대 재시도 횟수
        delay: 초기 대기 시간 (초)
        backoff: 대기 시간 증가 배율
        exceptions: 재시도할 예외 튜플
        func_name: 로깅에 사용할 함수 이름
    
    Usage:
        @retry_async(max_retries=3, delay=1.0)
        async def flaky_api_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            name = func_name or func.__name__
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"[{name}] 시도 {attempt + 1}/{max_retries + 1} 실패: {e}, "
                            f"{current_delay:.1f}초 후 재시도"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"[{name}] 최대 재시도 횟수 초과: {e}")
            
            raise last_exception
        return wrapper
    return decorator


# ==================== 유틸리티 함수 ====================

@dataclass
class ErrorContext:
    """에러 컨텍스트 정보"""
    function_name: str
    error_type: str
    error_message: str
    timestamp: str
    additional_info: dict = None


def create_error_context(
    func_name: str,
    exception: Exception,
    **additional_info
) -> ErrorContext:
    """에러 컨텍스트 생성"""
    return ErrorContext(
        function_name=func_name,
        error_type=type(exception).__name__,
        error_message=str(exception),
        timestamp=datetime.now().isoformat(),
        additional_info=additional_info or None
    )


def log_error_with_context(
    exception: Exception,
    context: dict = None,
    level: str = "error"
):
    """컨텍스트와 함께 에러 로깅"""
    log_func = getattr(logger, level, logger.error)
    
    error_info = {
        "error_type": type(exception).__name__,
        "error_message": str(exception),
        "timestamp": datetime.now().isoformat(),
    }
    
    if context:
        error_info["context"] = context
    
    if isinstance(exception, SportsAnalysisError):
        error_info["error_code"] = exception.code
        error_info["details"] = exception.details
    
    log_func(f"에러 발생: {error_info}")


# ==================== 테스트 ====================

async def _test_decorators():
    """데코레이터 테스트"""
    
    @async_error_handler(func_name="테스트함수", default_return="기본값", reraise=False)
    async def failing_func():
        raise ValueError("테스트 에러")
    
    @retry_async(max_retries=2, delay=0.1, func_name="재시도테스트")
    async def flaky_func():
        import random
        if random.random() < 0.7:
            raise ConnectionError("연결 실패")
        return "성공"
    
    # 테스트 실행
    result1 = await failing_func()
    print(f"failing_func 결과: {result1}")
    
    try:
        result2 = await flaky_func()
        print(f"flaky_func 결과: {result2}")
    except ConnectionError as e:
        print(f"flaky_func 최종 실패: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(_test_decorators())
