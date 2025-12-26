"""API Key Authentication Middleware.

This module implements secure API key authentication using Bearer tokens.
Keys are stored as SHA256 hashes in environment variables for security.
"""

from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import hashlib
import hmac
from typing import Optional

security = HTTPBearer()


class APIKeyAuth:
    """API Key authentication handler.

    Uses SHA256 hashing and constant-time comparison to prevent:
    - Timing attacks
    - Plain-text key storage
    - Key leakage through logs
    """

    def __init__(self):
        """Initialize with API key hash from environment."""
        self.valid_key_hash: Optional[str] = None

    def _load_key_hash(self):
        """Lazy load API key hash from environment."""
        if self.valid_key_hash is None:
            self.valid_key_hash = os.getenv('API_SECRET_KEY_HASH')
            if not self.valid_key_hash:
                raise ValueError(
                    "API_SECRET_KEY_HASH not set in environment. "
                    "Run generate_api_key.py to create one."
                )

    def verify_key(self, api_key: str) -> bool:
        """Verify API key against stored hash.

        Args:
            api_key: The API key to verify

        Returns:
            True if key is valid, False otherwise
        """
        # Lazy load hash on first use
        self._load_key_hash()

        if not api_key:
            return False

        # Hash the provided key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(key_hash, self.valid_key_hash)


# Global instance
api_key_auth = APIKeyAuth()


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """FastAPI dependency for API key verification.

    Usage:
        @router.post("/endpoint")
        async def endpoint(api_key: str = Depends(verify_api_key)):
            # Protected endpoint logic
            pass

    Args:
        credentials: HTTP Bearer token from Authorization header

    Returns:
        The validated API key

    Raises:
        HTTPException: 401 if key is invalid or missing
    """
    if not api_key_auth.verify_key(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
