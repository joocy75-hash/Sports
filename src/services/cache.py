"""
I-01: Redis 캐싱 레이어
API 응답과 분석 결과를 캐싱하여 성능을 향상시킵니다.
Redis가 없으면 인메모리 캐시로 폴백합니다.
"""

import json
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, Callable, TypeVar, Union
from functools import wraps

T = TypeVar('T')


class InMemoryCache:
    """인메모리 캐시 (Redis 폴백용)"""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._access_times: Dict[str, float] = {}

    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if entry["expires_at"] and datetime.now().timestamp() > entry["expires_at"]:
            del self._cache[key]
            del self._access_times[key]
            return None

        self._access_times[key] = datetime.now().timestamp()
        return entry["value"]

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """캐시에 값 저장"""
        # 캐시 사이즈 제한
        if len(self._cache) >= self._max_size:
            self._evict_lru()

        expires_at = datetime.now().timestamp() + ttl if ttl > 0 else None
        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.now().timestamp()
        }
        self._access_times[key] = datetime.now().timestamp()
        return True

    async def delete(self, key: str) -> bool:
        """캐시에서 키 삭제"""
        if key in self._cache:
            del self._cache[key]
            if key in self._access_times:
                del self._access_times[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        return await self.get(key) is not None

    async def clear(self) -> bool:
        """전체 캐시 클리어"""
        self._cache.clear()
        self._access_times.clear()
        return True

    async def keys(self, pattern: str = "*") -> list:
        """패턴에 맞는 키 목록 반환"""
        import fnmatch
        return [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]

    def _evict_lru(self):
        """LRU 방식으로 오래된 항목 제거"""
        if not self._access_times:
            return

        # 가장 오래전에 접근한 키 찾기
        oldest_key = min(self._access_times, key=self._access_times.get)
        if oldest_key in self._cache:
            del self._cache[oldest_key]
        if oldest_key in self._access_times:
            del self._access_times[oldest_key]

    def stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return {
            "type": "in_memory",
            "size": len(self._cache),
            "max_size": self._max_size,
            "memory_usage_approx": sum(
                len(str(v)) for v in self._cache.values()
            )
        }


class RedisCache:
    """Redis 캐시 래퍼"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._client = None
        self._connected = False
        self._fallback = InMemoryCache()

    async def connect(self) -> bool:
        """Redis 연결"""
        try:
            import redis.asyncio as redis
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._client.ping()
            self._connected = True
            print("[Cache] Redis 연결 성공")
            return True
        except ImportError:
            print("[Cache] redis 패키지가 없습니다. 인메모리 캐시 사용")
            self._connected = False
            return False
        except Exception as e:
            print(f"[Cache] Redis 연결 실패: {e}. 인메모리 캐시 사용")
            self._connected = False
            return False

    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        if not self._connected:
            return await self._fallback.get(key)

        try:
            data = await self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"[Cache] Redis get 오류: {e}")
            return await self._fallback.get(key)

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """캐시에 값 저장"""
        if not self._connected:
            return await self._fallback.set(key, value, ttl)

        try:
            data = json.dumps(value, ensure_ascii=False, default=str)
            if ttl > 0:
                await self._client.setex(key, ttl, data)
            else:
                await self._client.set(key, data)
            return True
        except Exception as e:
            print(f"[Cache] Redis set 오류: {e}")
            return await self._fallback.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """캐시에서 키 삭제"""
        if not self._connected:
            return await self._fallback.delete(key)

        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            print(f"[Cache] Redis delete 오류: {e}")
            return await self._fallback.delete(key)

    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        if not self._connected:
            return await self._fallback.exists(key)

        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            return await self._fallback.exists(key)

    async def clear(self, pattern: str = "*") -> bool:
        """패턴에 맞는 캐시 클리어"""
        if not self._connected:
            return await self._fallback.clear()

        try:
            keys = await self._client.keys(pattern)
            if keys:
                await self._client.delete(*keys)
            return True
        except Exception as e:
            print(f"[Cache] Redis clear 오류: {e}")
            return False

    async def keys(self, pattern: str = "*") -> list:
        """패턴에 맞는 키 목록 반환"""
        if not self._connected:
            return await self._fallback.keys(pattern)

        try:
            return await self._client.keys(pattern)
        except Exception as e:
            return await self._fallback.keys(pattern)

    def stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        if not self._connected:
            return self._fallback.stats()

        return {
            "type": "redis",
            "connected": self._connected,
            "url": self.redis_url
        }


class CacheManager:
    """캐시 매니저 - 여러 캐시 계층 관리"""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or "redis://localhost:6379"
        self._cache: Optional[Union[RedisCache, InMemoryCache]] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """캐시 초기화"""
        if self._initialized:
            return True

        # Redis 시도
        redis_cache = RedisCache(self.redis_url)
        if await redis_cache.connect():
            self._cache = redis_cache
        else:
            self._cache = InMemoryCache()

        self._initialized = True
        return True

    def _ensure_initialized(self):
        """초기화 확인"""
        if not self._initialized:
            # 동기 폴백
            self._cache = InMemoryCache()
            self._initialized = True

    async def get(self, key: str) -> Optional[Any]:
        """캐시 조회"""
        self._ensure_initialized()
        return await self._cache.get(key)

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """캐시 저장"""
        self._ensure_initialized()
        return await self._cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """캐시 삭제"""
        self._ensure_initialized()
        return await self._cache.delete(key)

    async def clear(self, pattern: str = "*") -> bool:
        """캐시 클리어"""
        self._ensure_initialized()
        if isinstance(self._cache, RedisCache):
            return await self._cache.clear(pattern)
        return await self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        self._ensure_initialized()
        return self._cache.stats()

    def make_key(self, *parts: Any) -> str:
        """캐시 키 생성"""
        key_str = ":".join(str(p) for p in parts)
        return f"sports:{key_str}"

    def make_hash_key(self, prefix: str, data: Dict[str, Any]) -> str:
        """데이터 해시 기반 캐시 키 생성"""
        data_str = json.dumps(data, sort_keys=True, default=str)
        hash_val = hashlib.md5(data_str.encode()).hexdigest()[:12]
        return f"sports:{prefix}:{hash_val}"


# 싱글톤 인스턴스
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(redis_url: Optional[str] = None) -> CacheManager:
    """싱글톤 캐시 매니저 반환"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(redis_url)
    return _cache_manager


# 데코레이터
def cached(
    ttl: int = 3600,
    key_prefix: str = "",
    key_builder: Optional[Callable[..., str]] = None
):
    """캐시 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            cache = get_cache_manager()
            await cache.initialize()

            # 캐시 키 생성
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                func_name = func.__name__
                arg_str = "_".join(str(a) for a in args[1:])  # self 제외
                kwarg_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = cache.make_key(key_prefix or func_name, arg_str, kwarg_str)

            # 캐시 조회
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 함수 실행
            result = await func(*args, **kwargs)

            # 캐시 저장
            if result is not None:
                await cache.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


# TTL 상수
class CacheTTL:
    """캐시 TTL 상수"""
    MINUTE = 60
    FIVE_MINUTES = 300
    FIFTEEN_MINUTES = 900
    HOUR = 3600
    SIX_HOURS = 21600
    DAY = 86400
    WEEK = 604800

    # 데이터 유형별 권장 TTL
    ODDS = FIFTEEN_MINUTES  # 배당률 - 15분
    MATCH_LIST = FIVE_MINUTES  # 경기 목록 - 5분
    ANALYSIS = HOUR  # 분석 결과 - 1시간
    TEAM_STATS = SIX_HOURS  # 팀 통계 - 6시간
    H2H = DAY  # 상대전적 - 1일
    PREDICTIONS = HOUR  # 예측 결과 - 1시간


# 테스트
if __name__ == "__main__":
    async def test():
        cache = get_cache_manager()
        await cache.initialize()

        print("\n[캐시 테스트]")
        print(f"캐시 타입: {cache.stats()['type']}")

        # 저장
        await cache.set("test:key1", {"value": 123, "name": "테스트"}, ttl=60)
        print("저장 완료")

        # 조회
        result = await cache.get("test:key1")
        print(f"조회 결과: {result}")

        # 키 생성
        key = cache.make_key("match", 12345, "analysis")
        print(f"생성된 키: {key}")

        hash_key = cache.make_hash_key("prediction", {"home": "Liverpool", "away": "ManUtd"})
        print(f"해시 키: {hash_key}")

        # 삭제
        await cache.delete("test:key1")
        result = await cache.get("test:key1")
        print(f"삭제 후 조회: {result}")

        print("\n[통계]")
        print(cache.stats())

    asyncio.run(test())
