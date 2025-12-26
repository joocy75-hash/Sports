import logging
from typing import Dict, Optional, Any
from src.clients.base import BaseAPIClient
from src.config.settings import Settings

logger = logging.getLogger(__name__)


class TheSportsDBClient(BaseAPIClient):
    """
    TheSportsDB API Client (Free Tier)
    Uses '3' as the test API key if not provided.
    """

    BASE_URL = "https://www.thesportsdb.com/api/v1/json"

    def __init__(self, settings: Settings):
        self.api_key = "3"  # Default test key
        super().__init__(base_url=f"{self.BASE_URL}/{self.api_key}")

    async def search_team(self, team_name: str) -> Optional[Dict[str, Any]]:
        """Search for a team by name."""
        try:
            data = await self.http.get("/searchteams.php", params={"t": team_name})
            teams = data.get("teams")
            if teams:
                return teams[0]
            return None
        except Exception as e:
            logger.error(f"TheSportsDB search_team failed: {e}")
            return None

    async def get_live_scores(
        self, league_id: str = None, sport: str = "Soccer"
    ) -> Dict[str, Any]:
        """
        Get live scores.
        Note: TheSportsDB free tier live scores might be limited.
        """
        try:
            params = {"s": sport}
            if league_id:
                params["l"] = league_id

            data = await self.http.get("/livescore.php", params=params)
            return data
        except Exception as e:
            logger.error(f"TheSportsDB get_live_scores failed: {e}")
            return {}

    async def get_next_events(self, league_id: str) -> Dict[str, Any]:
        """Get next 15 events for a league."""
        try:
            data = await self.http.get(
                "/eventsnextleague.php", params={"id": league_id}
            )
            return data
        except Exception as e:
            logger.error(f"TheSportsDB get_next_events failed: {e}")
            return {}
