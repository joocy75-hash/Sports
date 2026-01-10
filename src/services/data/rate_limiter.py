"""
API Rate Limiting 모듈

각 외부 API의 요청 제한을 관리하고, 제한 초과 시 자동으로 대기합니다.

Usage:
    from src.services.data.rate_limiter import rate_limited, RATE_LIMITERS

    @rate_limited("football_data")
    async def fetch_football_data():
        # API 호출
        pass

    # 또는 직접 사용
    limiter = RATE_LIMITERS["football_data"]
    await limiter.acquire()
    # API 호출
"""

import asyncio
import logging
import time
from collections import deque
from functools import wraps
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token Bucket 기반 Rate Limiter

    특정 시간 윈도우 내에서 최대 요청 수를 제한합니다.
    제한 초과 시 자동으로 대기 후 재시도합니다.

    Attributes:
        max_requests: 시간 윈도우 내 최대 요청 수
        time_window: 시간 윈도우 (초)
        requests: 요청 시간 기록 (deque)
        lock: 동시성 제어를 위한 asyncio.Lock
    """

    def __init__(self, max_requests: int, time_window: int, name: str = "unnamed"):
        """
        Rate Limiter 초기화

        Args:
            max_requests: 시간 윈도우 내 최대 요청 수
            time_window: 시간 윈도우 (초)
            name: Rate Limiter 이름 (로깅용)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.name = name
        self.requests: deque = deque()
        self.lock = asyncio.Lock()

        # 통계
        self._total_requests = 0
        self._total_waits = 0
        self._total_wait_time = 0.0

        logger.debug(f"RateLimiter '{name}' initialized: {max_requests} requests per {time_window} seconds")

    def _clean_old_requests(self) -> None:
        """시간 윈도우를 벗어난 오래된 요청 기록 제거"""
        current_time = time.time()
        cutoff_time = current_time - self.time_window

        while self.requests and self.requests[0] < cutoff_time:
            self.requests.popleft()

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        요청 권한 획득

        Rate limit에 도달한 경우 자동으로 대기 후 재시도합니다.

        Args:
            timeout: 최대 대기 시간 (초). None이면 무제한 대기

        Returns:
            bool: 권한 획득 성공 여부

        Raises:
            asyncio.TimeoutError: timeout 초과 시
        """
        start_time = time.time()

        async with self.lock:
            while True:
                self._clean_old_requests()
                current_count = len(self.requests)

                # Rate limit 체크
                if current_count < self.max_requests:
                    # 요청 가능
                    self.requests.append(time.time())
                    self._total_requests += 1

                    remaining = self.max_requests - current_count - 1
                    if remaining <= self.max_requests * 0.2:  # 20% 이하 남음
                        logger.warning(
                            f"RateLimiter '{self.name}': {remaining}/{self.max_requests} requests remaining"
                        )

                    return True

                # Rate limit 초과 - 대기 필요
                oldest_request = self.requests[0]
                wait_time = oldest_request + self.time_window - time.time()

                if wait_time <= 0:
                    # 바로 재시도 가능
                    continue

                # timeout 체크
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed + wait_time > timeout:
                        logger.warning(
                            f"RateLimiter '{self.name}': timeout exceeded "
                            f"(elapsed: {elapsed:.1f}s, wait_needed: {wait_time:.1f}s, timeout: {timeout:.1f}s)"
                        )
                        raise asyncio.TimeoutError(
                            f"Rate limiter '{self.name}' timeout: {timeout}s exceeded"
                        )

                # 대기
                logger.info(
                    f"RateLimiter '{self.name}': rate limit reached, waiting {wait_time:.1f}s "
                    f"(current: {current_count}/{self.max_requests})"
                )

                self._total_waits += 1
                self._total_wait_time += wait_time

                # Lock을 해제하고 대기 (다른 코루틴이 사용할 수 있도록)
                self.lock.release()
                try:
                    await asyncio.sleep(wait_time + 0.1)  # 여유분 추가
                finally:
                    await self.lock.acquire()

    def get_remaining(self) -> int:
        """
        남은 요청 수 반환

        Returns:
            int: 현재 시간 윈도우 내에서 사용 가능한 남은 요청 수
        """
        self._clean_old_requests()
        return max(0, self.max_requests - len(self.requests))

    def get_reset_time(self) -> float:
        """
        리셋까지 남은 시간 (초) 반환

        Returns:
            float: 가장 오래된 요청이 만료되기까지 남은 시간 (초)
                   요청이 없으면 0 반환
        """
        self._clean_old_requests()

        if not self.requests:
            return 0.0

        oldest_request = self.requests[0]
        reset_time = oldest_request + self.time_window - time.time()
        return max(0.0, reset_time)

    def get_usage_ratio(self) -> float:
        """
        현재 사용률 반환

        Returns:
            float: 0.0 ~ 1.0 사이의 사용률
        """
        self._clean_old_requests()
        return len(self.requests) / self.max_requests

    def get_stats(self) -> Dict[str, Any]:
        """
        Rate Limiter 통계 반환

        Returns:
            dict: {
                "name": str,
                "max_requests": int,
                "time_window": int,
                "current_requests": int,
                "remaining": int,
                "reset_time": float,
                "usage_ratio": float,
                "total_requests": int,
                "total_waits": int,
                "total_wait_time": float,
                "avg_wait_time": float
            }
        """
        self._clean_old_requests()

        return {
            "name": self.name,
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "current_requests": len(self.requests),
            "remaining": self.get_remaining(),
            "reset_time": self.get_reset_time(),
            "usage_ratio": self.get_usage_ratio(),
            "total_requests": self._total_requests,
            "total_waits": self._total_waits,
            "total_wait_time": self._total_wait_time,
            "avg_wait_time": self._total_wait_time / self._total_waits if self._total_waits > 0 else 0.0
        }

    def reset(self) -> None:
        """Rate Limiter 상태 초기화 (테스트용)"""
        self.requests.clear()
        logger.debug(f"RateLimiter '{self.name}' reset")

    def __repr__(self) -> str:
        return (
            f"RateLimiter(name='{self.name}', "
            f"max_requests={self.max_requests}, "
            f"time_window={self.time_window}, "
            f"remaining={self.get_remaining()})"
        )


# ============================================================================
# 글로벌 Rate Limiter 인스턴스
# ============================================================================

RATE_LIMITERS: Dict[str, RateLimiter] = {
    # Football-Data.org: 10 requests/minute (Free tier)
    "football_data": RateLimiter(
        max_requests=10,
        time_window=60,
        name="football_data"
    ),

    # API-Football: 100 requests/day (Free tier)
    "api_football": RateLimiter(
        max_requests=100,
        time_window=86400,  # 24 hours
        name="api_football"
    ),

    # API-Basketball: 100 requests/day (Free tier)
    "api_basketball": RateLimiter(
        max_requests=100,
        time_window=86400,  # 24 hours
        name="api_basketball"
    ),

    # The Odds API: 500 requests/month (Free tier)
    "odds_api": RateLimiter(
        max_requests=500,
        time_window=2592000,  # 30 days
        name="odds_api"
    ),

    # KSPO API: 1000 requests/day (공공데이터포털 기본)
    "kspo_api": RateLimiter(
        max_requests=1000,
        time_window=86400,  # 24 hours
        name="kspo_api"
    ),

    # 베트맨/젠토토 크롤러: 자체 제한 (서버 부하 방지)
    "crawler": RateLimiter(
        max_requests=30,
        time_window=60,  # 분당 30회
        name="crawler"
    ),

    # AI API들 (일반적인 제한)
    "openai": RateLimiter(
        max_requests=60,
        time_window=60,  # 분당 60회
        name="openai"
    ),

    "anthropic": RateLimiter(
        max_requests=60,
        time_window=60,  # 분당 60회
        name="anthropic"
    ),

    "google": RateLimiter(
        max_requests=60,
        time_window=60,  # 분당 60회
        name="google"
    ),

    "deepseek": RateLimiter(
        max_requests=60,
        time_window=60,  # 분당 60회
        name="deepseek"
    ),

    "kimi": RateLimiter(
        max_requests=30,
        time_window=60,  # 분당 30회 (보수적)
        name="kimi"
    ),
}


def get_rate_limiter(name: str) -> RateLimiter:
    """
    이름으로 Rate Limiter 가져오기

    Args:
        name: Rate Limiter 이름

    Returns:
        RateLimiter: 해당 Rate Limiter 인스턴스

    Raises:
        KeyError: 존재하지 않는 Rate Limiter 이름
    """
    if name not in RATE_LIMITERS:
        available = ", ".join(RATE_LIMITERS.keys())
        raise KeyError(f"Unknown rate limiter: '{name}'. Available: {available}")
    return RATE_LIMITERS[name]


def register_rate_limiter(
    name: str,
    max_requests: int,
    time_window: int,
    overwrite: bool = False
) -> RateLimiter:
    """
    새 Rate Limiter 등록

    Args:
        name: Rate Limiter 이름
        max_requests: 시간 윈도우 내 최대 요청 수
        time_window: 시간 윈도우 (초)
        overwrite: 기존 Rate Limiter 덮어쓰기 허용

    Returns:
        RateLimiter: 생성된 Rate Limiter 인스턴스

    Raises:
        ValueError: 이미 존재하는 이름이고 overwrite=False인 경우
    """
    if name in RATE_LIMITERS and not overwrite:
        raise ValueError(f"Rate limiter '{name}' already exists. Use overwrite=True to replace.")

    limiter = RateLimiter(max_requests=max_requests, time_window=time_window, name=name)
    RATE_LIMITERS[name] = limiter
    logger.info(f"Registered rate limiter: {limiter}")
    return limiter


# ============================================================================
# rate_limited 데코레이터
# ============================================================================

def rate_limited(
    limiter_name: str,
    timeout: Optional[float] = None
) -> Callable:
    """
    Rate Limiting 데코레이터

    API 함수에 적용하여 자동으로 rate limit을 관리합니다.

    Args:
        limiter_name: 사용할 Rate Limiter 이름 (RATE_LIMITERS 키)
        timeout: 최대 대기 시간 (초). None이면 무제한 대기

    Returns:
        Callable: 데코레이터 함수

    Usage:
        @rate_limited("football_data")
        async def fetch_matches():
            return await api.get_matches()

        @rate_limited("api_football", timeout=30.0)
        async def fetch_standings():
            return await api.get_standings()

    Raises:
        KeyError: 존재하지 않는 Rate Limiter 이름
        asyncio.TimeoutError: timeout 초과 시
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            limiter = get_rate_limiter(limiter_name)

            # 요청 권한 획득 (필요시 대기)
            await limiter.acquire(timeout=timeout)

            # 함수 실행
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in rate-limited function '{func.__name__}': {e}")
                raise

        # 메타데이터 추가
        wrapper._rate_limiter_name = limiter_name
        wrapper._rate_limiter = get_rate_limiter(limiter_name)

        return wrapper
    return decorator


def rate_limited_sync(
    limiter_name: str,
    timeout: Optional[float] = None
) -> Callable:
    """
    동기 함수용 Rate Limiting 데코레이터

    Note: 동기 함수에서는 대기가 블로킹됩니다.
    가능하면 async 버전을 사용하세요.

    Args:
        limiter_name: 사용할 Rate Limiter 이름
        timeout: 최대 대기 시간 (초)

    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_rate_limiter(limiter_name)

            # 동기 버전의 rate limit 체크
            import time as sync_time
            start = sync_time.time()

            while True:
                limiter._clean_old_requests()

                if len(limiter.requests) < limiter.max_requests:
                    limiter.requests.append(sync_time.time())
                    limiter._total_requests += 1
                    break

                # 대기 시간 계산
                oldest = limiter.requests[0]
                wait_time = oldest + limiter.time_window - sync_time.time()

                if timeout is not None and sync_time.time() - start + wait_time > timeout:
                    raise TimeoutError(f"Rate limiter '{limiter_name}' timeout")

                if wait_time > 0:
                    logger.info(f"RateLimiter '{limiter_name}': waiting {wait_time:.1f}s (sync)")
                    limiter._total_waits += 1
                    limiter._total_wait_time += wait_time
                    sync_time.sleep(wait_time + 0.1)

            return func(*args, **kwargs)

        wrapper._rate_limiter_name = limiter_name
        return wrapper
    return decorator


# ============================================================================
# 유틸리티 함수
# ============================================================================

def get_all_stats() -> Dict[str, Dict[str, Any]]:
    """
    모든 Rate Limiter의 통계 반환

    Returns:
        dict: {limiter_name: stats_dict, ...}
    """
    return {name: limiter.get_stats() for name, limiter in RATE_LIMITERS.items()}


def reset_all_limiters() -> None:
    """모든 Rate Limiter 초기화 (테스트용)"""
    for limiter in RATE_LIMITERS.values():
        limiter.reset()
    logger.info("All rate limiters reset")


def get_critical_limiters() -> Dict[str, RateLimiter]:
    """
    사용률이 높은 Rate Limiter 목록 반환 (80% 이상 사용)

    Returns:
        dict: {limiter_name: limiter, ...}
    """
    return {
        name: limiter
        for name, limiter in RATE_LIMITERS.items()
        if limiter.get_usage_ratio() >= 0.8
    }


async def wait_for_all_limiters(timeout: float = 300.0) -> bool:
    """
    모든 Rate Limiter가 최소 1개 요청 가능할 때까지 대기

    Args:
        timeout: 최대 대기 시간 (초)

    Returns:
        bool: 모든 limiter가 사용 가능해지면 True
    """
    start = time.time()

    while time.time() - start < timeout:
        all_available = True
        max_wait = 0.0

        for name, limiter in RATE_LIMITERS.items():
            if limiter.get_remaining() == 0:
                all_available = False
                reset_time = limiter.get_reset_time()
                max_wait = max(max_wait, reset_time)

        if all_available:
            return True

        # 가장 긴 대기 시간만큼 대기 (최대 10초씩)
        wait = min(max_wait, 10.0)
        logger.info(f"Waiting {wait:.1f}s for rate limiters...")
        await asyncio.sleep(wait)

    return False


# ============================================================================
# __init__.py 호환용 export
# ============================================================================

__all__ = [
    "RateLimiter",
    "RATE_LIMITERS",
    "rate_limited",
    "rate_limited_sync",
    "get_rate_limiter",
    "register_rate_limiter",
    "get_all_stats",
    "reset_all_limiters",
    "get_critical_limiters",
    "wait_for_all_limiters",
]
