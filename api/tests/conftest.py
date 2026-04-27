"""Pytest configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator

import pytest
from fastapi import Header
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.models import Base
from app.db import get_db
from app.deps import verify_internal_key

# ──────────────────────────────────────────────────────────────────────────────
# In-memory SQLite engine for tests
# NOTE: ARRAY columns (Category.keywords, Merchant.aliases) are not supported
# by SQLite. Tests that touch those columns require a real PostgreSQL instance.
# For the full suite: DATABASE_URL=postgresql+psycopg://... pytest tests/ -v
# ──────────────────────────────────────────────────────────────────────────────

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")

_test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DB_URL else {},
    echo=False,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

TEST_API_KEY = "test_internal_key"


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables before the test session, drop after."""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture()
def test_db():
    """Provide a transactional DB session that rolls back after each test."""
    connection = _test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
async def async_client(test_db: Session) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient wired to the FastAPI app with DB and auth overridden.
    Dependency overrides ensure tests use the test DB and bypass real key check.
    """
    from app.main import app

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    async def override_verify_key(x_internal_key: str = Header(None)) -> str:
        return TEST_API_KEY

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_internal_key] = override_verify_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture()
def api_headers() -> dict:
    """Headers with API key for testing."""
    return {"X-Internal-Key": TEST_API_KEY}
