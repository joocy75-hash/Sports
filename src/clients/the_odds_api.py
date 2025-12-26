from typing import Any, Dict, Optional

from src.config.settings import Settings
from src.clients.base import BaseAPIClient

BASE_URL = "https://api.the-odds-api.com/v4"


class TheOddsApiClient(BaseAPIClient):
    """Free tier covers Pinnacle odds; limited objects/month."""

    def __init__(self, settings: Settings):
        self.settings = settings
        super().__init__(
            base_url=BASE_URL,
            rate_limit_per_sec=settings.rate_limit_per_sec,
        )

    def _params(
        self, sport_key: str, regions: str = "eu", markets: str = "h2h"
    ) -> Dict[str, Any]:
        return {
            "apiKey": self.settings.the_odds_api_key,
            "regions": regions,  # 'eu' includes Pinnacle
            "markets": markets,
            "oddsFormat": "decimal",
            "sport": sport_key,
        }

    async def odds(
        self,
        sport_key: str,
        date_filter: Optional[str] = None,
        regions: str = "eu",
        markets: str = "h2h",
    ) -> Dict[str, Any]:
        params = self._params(sport_key, regions=regions, markets=markets)
        if date_filter:
            params["date"] = date_filter
        return await self.http.get(f"sports/{sport_key}/odds", params=params)
