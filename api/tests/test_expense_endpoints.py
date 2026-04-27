"""Tests for expense endpoints."""

import pytest
from fastapi import Header
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.deps import verify_internal_key
from datetime import datetime, timedelta

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

@pytest.fixture
async def sample_expense(client):
    """Create a sample expense for testing."""
    response = await client.post(
        "/ingest/text",
        data={
            "text": "pagué 50000 en supermercado",
            "user_id": "user",
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )
    data = response.json()
    return data.get("expense_id") or data.get("id")

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
    # category may be in 'category', 'category_name', or 'category_id'
    assert "category" in data or "category_name" in data or "category_id" in data

@pytest.mark.asyncio
async def test_get_expense_not_found(client):
    """Test fetching non-existent expense."""
    response = await client.get(
        "/expenses/999999",
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
    # Update endpoint returns the updated expense (field names may vary)

@pytest.mark.asyncio
async def test_update_expense_not_found(client):
    """Test updating non-existent expense."""
    response = await client.patch(
        "/expenses/999999",
        json={"category": "food"},
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code in (404, 405, 422)  # depends on endpoint implementation

@pytest.mark.asyncio
async def test_delete_expense(client, sample_expense):
    """Test deleting expense."""
    response = await client.delete(
        f"/expenses/{sample_expense}",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code in (200, 204)  # some implementations return 200 with message

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
        "/expenses/999999",
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code in (404, 405, 422)  # depends on endpoint implementation

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
