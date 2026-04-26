"""Tests for expense endpoints."""

import pytest
from httpx import AsyncClient
from app.main import app
from datetime import datetime, timedelta

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def sample_expense(client):
    """Create a sample expense for testing."""
    response = await client.post(
        "/ingest/text",
        json={
            "text": "pagué 50000 en supermercado",
            "user_id": "test_user",
            "message_id": "sample_001"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )
    return response.json()["expense_id"]

@pytest.mark.asyncio
async def test_get_expenses(client):
    """Test fetching expenses list."""
    response = await client.get(
        "/expenses?limit=10&offset=0",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_expenses_with_filter(client):
    """Test fetching expenses with category filter."""
    response = await client.get(
        "/expenses?category=food&limit=10",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_expenses_with_date_range(client):
    """Test fetching expenses with date range."""
    today = datetime.now().date()
    month_ago = today - timedelta(days=30)

    response = await client.get(
        f"/expenses?from={month_ago}&to={today}",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_expense_by_id(client, sample_expense):
    """Test fetching specific expense."""
    response = await client.get(
        f"/expenses/{sample_expense}",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_expense
    assert "amount" in data
    assert "category" in data

@pytest.mark.asyncio
async def test_get_expense_not_found(client):
    """Test fetching non-existent expense."""
    response = await client.get(
        "/expenses/nonexistent",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_update_expense(client, sample_expense):
    """Test updating expense."""
    response = await client.patch(
        f"/expenses/{sample_expense}",
        json={
            "category": "shopping",
            "merchant": "Walmart"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "shopping"
    assert data["merchant"] == "Walmart"

@pytest.mark.asyncio
async def test_update_expense_not_found(client):
    """Test updating non-existent expense."""
    response = await client.patch(
        "/expenses/nonexistent",
        json={"category": "food"},
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_delete_expense(client, sample_expense):
    """Test deleting expense."""
    response = await client.delete(
        f"/expenses/{sample_expense}",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 204

    # Verify it's deleted
    response = await client.get(
        f"/expenses/{sample_expense}",
        headers={"X-Internal-Key": "test_internal_key"}
    )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_delete_expense_not_found(client):
    """Test deleting non-existent expense."""
    response = await client.delete(
        "/expenses/nonexistent",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_expenses_pagination(client):
    """Test expenses pagination."""
    response = await client.get(
        "/expenses?limit=5&offset=0",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 5
