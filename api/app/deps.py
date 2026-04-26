"""FastAPI dependencies."""

from fastapi import Header, HTTPException

from .config import Settings


async def verify_internal_key(x_internal_key: str = Header(None)) -> str:
    """Verify internal API key."""
    settings = Settings()
    if x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_internal_key
