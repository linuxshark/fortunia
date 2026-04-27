"""Tests for report endpoints."""

import pytest
from fastapi import Header
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.deps import verify_internal_key
from datetime import datetime

TEST_API_KEY = "test_internal_key"


@pytest.fixture
async def client():
    async def override_verify_key(x_internal_key: str = Header(None)) -> str:
        return TEST_API_KEY

    app.dependency_overrides[verify_internal_key] = override_verify_key
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_today_report(client):
    """Test daily report endpoint."""
    response = await client.get(
        "/reports/today",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    # Response may use "total" or "total_amount" depending on endpoint version
    assert "count" in data or "date" in data

@pytest.mark.asyncio
async def test_today_report_custom_date(client):
    """Test daily report for specific date."""
    date = datetime.now().strftime("%Y-%m-%d")
    response = await client.get(
        f"/reports/today?date={date}",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

@pytest.mark.asyncio
async def test_month_report(client):
    """Test monthly report endpoint."""
    month = datetime.now().strftime("%Y-%m")
    response = await client.get(
        f"/reports/month?month={month}",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

@pytest.mark.asyncio
async def test_categories_report(client):
    """Test category report endpoint."""
    response = await client.get(
        "/reports/categories",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    # May be a list or dict with categories key
    if isinstance(data, list):
        if len(data) > 0:
            item = data[0]
            assert "category" in item or "name" in item
    else:
        assert isinstance(data, dict)

@pytest.mark.asyncio
async def test_trend_report(client):
    """Test trend report endpoint."""
    response = await client.get(
        "/reports/trend?days=30",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    # Response may be a list or a dict with a 'trend' key
    if isinstance(data, list):
        if len(data) > 0:
            item = data[0]
            assert "date" in item or "month" in item
    else:
        assert isinstance(data, dict)

@pytest.mark.asyncio
async def test_trend_report_custom_days(client):
    """Test trend report with custom days."""
    response = await client.get(
        "/reports/trend?days=7",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, (list, dict))

@pytest.mark.asyncio
async def test_top_merchants(client):
    """Test top merchants endpoint."""
    response = await client.get(
        "/reports/top-merchants?limit=10",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    # Response may be a list or dict with 'merchants' key
    merchants = data if isinstance(data, list) else data.get("merchants", [])
    assert isinstance(merchants, list)

@pytest.mark.asyncio
async def test_top_merchants_custom_limit(client):
    """Test top merchants with custom limit."""
    response = await client.get(
        "/reports/top-merchants?limit=5",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    merchants = data if isinstance(data, list) else data.get("merchants", [])
    assert isinstance(merchants, list)
    assert len(merchants) <= 5

@pytest.mark.asyncio
async def test_health_check(client):
    """Test health endpoint."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
