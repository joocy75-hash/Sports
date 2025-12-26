import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator


class RateLimiter:
    """Simple token bucket limiter: allows `rate` operations per second."""

    def __init__(self, rate: float):
        self._rate = max(rate, 0.1)
        self._tokens = self._rate
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            if self._tokens < 1:
                await asyncio.sleep((1 - self._tokens) / self._rate)
                self._tokens = 0
            else:
                self._tokens -= 1
            self._last = time.monotonic()

    @asynccontextmanager
    async def limit(self) -> AsyncIterator[None]:
        await self.acquire()
        yield
