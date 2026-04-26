"""Tests for report endpoints."""

import pytest
from httpx import AsyncClient
from app.main import app
from datetime import datetime

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_today_report(client):
    """Test daily report endpoint."""
    response = await client.get(
        "/reports/today",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "total_amount" in data
    assert "count" in data
    assert "top_category" in data or data["count"] == 0

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
    assert "total_amount" in data
    assert "count" in data
    assert "avg_expense" in data

@pytest.mark.asyncio
async def test_categories_report(client):
    """Test category report endpoint."""
    response = await client.get(
        "/reports/categories",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    if len(data) > 0:
        item = data[0]
        assert "category" in item
        assert "count" in item
        assert "total_amount" in item
        assert "percentage" in item

@pytest.mark.asyncio
async def test_trend_report(client):
    """Test trend report endpoint."""
    response = await client.get(
        "/reports/trend?days=30",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    if len(data) > 0:
        item = data[0]
        assert "date" in item
        assert "total" in item

@pytest.mark.asyncio
async def test_trend_report_custom_days(client):
    """Test trend report with custom days."""
    response = await client.get(
        "/reports/trend?days=7",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_top_merchants(client):
    """Test top merchants endpoint."""
    response = await client.get(
        "/reports/top-merchants?limit=10",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    if len(data) > 0:
        item = data[0]
        assert "merchant" in item or item.get("merchant") is None
        assert "count" in item
        assert "total_amount" in item

@pytest.mark.asyncio
async def test_top_merchants_custom_limit(client):
    """Test top merchants with custom limit."""
    response = await client.get(
        "/reports/top-merchants?limit=5",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5

@pytest.mark.asyncio
async def test_health_check(client):
    """Test health endpoint."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
