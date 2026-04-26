"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("INTERNAL_API_KEY", "test-key-12345")
    monkeypatch.setenv("DEFAULT_CURRENCY", "CLP")
    monkeypatch.setenv("DEFAULT_USER_ID", "test_user")
