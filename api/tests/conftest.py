"""Pytest configuration and fixtures."""

import pytest
import asyncio
from httpx import AsyncClient


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("INTERNAL_API_KEY", "test_internal_key")
    monkeypatch.setenv("DEFAULT_CURRENCY", "CLP")
    monkeypatch.setenv("DEFAULT_USER_ID", "test_user")
    monkeypatch.setenv("FORTUNA_API_URL", "http://localhost:8000")


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client():
    """Provide AsyncClient for HTTP tests."""
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def api_headers():
    """Provide headers with API key for testing."""
    return {"X-Internal-Key": "test_internal_key"}
