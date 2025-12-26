import random
from typing import Any, Dict

from src.clients.base import BaseAPIClient

BASE_URL = "https://api.sofascore.com/api/v1"
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class SofascoreClient(BaseAPIClient):
    """Unofficial lineup fetcher; UA rotation to mitigate blocking."""

    def __init__(self, rate_limit_per_sec: float = 2.0):
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        super().__init__(
            base_url=BASE_URL,
            headers=headers,
            rate_limit_per_sec=rate_limit_per_sec,
        )

    async def event_lineups(self, event_id: int) -> Dict[str, Any]:
        # API shape: /event/{id}/lineups
        return await self.http.get(f"event/{event_id}/lineups")
