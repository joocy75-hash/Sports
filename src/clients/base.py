"""Base API Client for all external API clients."""

from typing import Optional, Dict
from src.services.http_client import HttpClient


class BaseAPIClient:
    """
    Base class for all API clients.
    Provides common HTTP client initialization and cleanup.
    """

    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        rate_limit_per_sec: float = 5.0,
    ):
        """
        Initialize the base API client.

        Args:
            base_url: Base URL for the API
            headers: Optional HTTP headers
            rate_limit_per_sec: Rate limit in requests per second
        """
        self.http = HttpClient(
            base_url=base_url,
            headers=headers,
            rate_limit_per_sec=rate_limit_per_sec,
        )

    async def close(self) -> None:
        """Close the HTTP client session."""
        await self.http.close()
