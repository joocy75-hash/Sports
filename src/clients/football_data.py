from datetime import date
from typing import Any, Dict, Optional

from src.config.settings import Settings
from src.clients.base import BaseAPIClient

BASE_URL = "https://api.football-data.org/v4"


class FootballDataClient(BaseAPIClient):
    """Free tier: fixtures/results/standings; odds limited."""

    def __init__(self, settings: Settings):
        headers = {}
        if settings.football_data_token:
            headers["X-Auth-Token"] = settings.football_data_token
        super().__init__(
            base_url=BASE_URL,
            headers=headers,
            rate_limit_per_sec=settings.rate_limit_per_sec,
        )

    async def matches_by_date(self, target_date: date, competition_code: Optional[str] = None) -> Dict[str, Any]:
        params = {"dateFrom": target_date.isoformat(), "dateTo": target_date.isoformat()}
        path = "matches"
        if competition_code:
            path = f"competitions/{competition_code}/matches"
        return await self.http.get(path, params=params)
