import asyncio
from typing import Any, Dict, Optional

import aiohttp
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.logging import get_logger
from src.core.rate_limiter import RateLimiter

logger = get_logger(__name__)


class HttpError(Exception):
    pass


class HttpClient:
    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None, rate_limit_per_sec: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter(rate_limit_per_sec)
        self._session_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session and not self.session.closed:
            return self.session
        async with self._session_lock:
            if self.session and not self.session.closed:
                return self.session
            self.session = aiohttp.ClientSession(headers=self.headers, raise_for_status=False)
            return self.session

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(HttpError),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            stop=stop_after_attempt(3),
            reraise=True,
        ):
            with attempt:
                async with self.rate_limiter.limit():
                    session = await self._get_session()
                    resp = await session.request(method=method.upper(), url=url, **kwargs)
                    if resp.status >= 500:
                        logger.warning("Server error %s %s -> %s", method, url, resp.status)
                        raise HttpError(f"Server error {resp.status}")
                    if resp.status >= 400:
                        text = await resp.text()
                        logger.error("Client error %s %s -> %s | %s", method, url, resp.status, text)
                        raise HttpError(f"Client error {resp.status}: {text}")
                    data = await resp.json()
                    return data
        raise HttpError("Unreachable code")

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._request("POST", path, json=json)
