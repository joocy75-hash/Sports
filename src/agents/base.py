import asyncio
import contextlib
from abc import ABC, abstractmethod
from typing import Optional

try:
    from redis.asyncio import Redis
except ImportError:  # Redis optional for init/db tasks
    Redis = None  # type: ignore

from src.config.settings import Settings
from src.core.logging import get_logger


class BaseAgent(ABC):
    def __init__(self, settings: Settings, redis_client: Optional[Redis] = None):
        self.settings = settings
        self.redis = redis_client
        self.logger = get_logger(self.__class__.__name__)
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self.run())
        self.logger.info("Agent started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self.logger.info("Agent stopped")

    @abstractmethod
    async def run(self) -> None:
        ...
