"""Simple API-key authentication.

Clients send the header:   X-API-Key: <the key>

* The real key lives in the ANALYTICS_API_KEY environment variable.
* It is never hard-coded in source, never returned in responses, never logged.
* If ANALYTICS_API_KEY is empty/unset, the engine runs in DEVELOPMENT MODE
  (auth disabled) and prints a warning. This makes first-time setup easy.
"""
from fastapi import Depends, Header, HTTPException

from .config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency that protects the analytics endpoints."""
    settings = get_settings()

    if not settings.analytics_api_key:
        # Development mode: no key configured -> allow access.
        return

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Send it in the 'X-API-Key' header.",
        )

    # Constant-time comparison to avoid timing attacks.
    import hmac

    if not hmac.compare_digest(x_api_key, settings.analytics_api_key):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )
