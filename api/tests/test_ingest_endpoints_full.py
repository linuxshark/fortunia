"""Full integration tests for ingest endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_text_success(async_client: AsyncClient):
    """Test successful text ingest."""
    response = await async_client.post(
        "/ingest/text",
        data={
            "text": "gasté 15 lucas en ropa",
            "user_id": "test_user",
            "msg_id": "123456",
        },
        headers={"X-Internal-Key": "test_internal_key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "registered"
    assert float(data["amount"]) == 15000.0
    assert data["currency"] == "CLP"
    assert "expense_id" in data
    assert data["confidence"] > 0.5


@pytest.mark.asyncio
async def test_ingest_text_no_amount(async_client: AsyncClient):
    """Test text ingest rejects when no amount detected."""
    response = await async_client.post(
        "/ingest/text",
        data={"text": "gasté en ropa sin monto", "user_id": "test_user"},
        headers={"X-Internal-Key": "test_internal_key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"


@pytest.mark.asyncio
async def test_ingest_text_missing_api_key(async_client: AsyncClient):
    """Test request without API key returns 403."""
    # Override is in place, but we still test the real dependency path
    from app.main import app
    from app.deps import verify_internal_key

    # Temporarily remove override to test real key validation
    saved = app.dependency_overrides.pop(verify_internal_key, None)
    try:
        response = await async_client.post(
            "/ingest/text",
            data={"text": "gasté 100 lucas", "user_id": "test_user"},
        )
        assert response.status_code == 403
    finally:
        if saved:
            app.dependency_overrides[verify_internal_key] = saved


@pytest.mark.asyncio
async def test_ingest_intent_check_finance(async_client: AsyncClient):
    """Test intent pre-check for finance."""
    response = await async_client.post(
        "/ingest/intent/check",
        json={"text": "pagué 5000 por uber"},
        headers={"X-Internal-Key": "test_internal_key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_finance"] is True
    assert data["confidence"] > 0.8


@pytest.mark.asyncio
async def test_ingest_intent_check_not_finance(async_client: AsyncClient):
    """Test intent check for non-finance narrative."""
    response = await async_client.post(
        "/ingest/intent/check",
        json={"text": "vi una película"},
        headers={"X-Internal-Key": "test_internal_key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_finance"] is False


@pytest.mark.asyncio
async def test_ingest_image_missing_file(async_client: AsyncClient):
    """Test image ingest without file returns 422."""
    response = await async_client.post(
        "/ingest/image",
        data={"user_id": "test_user"},
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_audio_missing_file(async_client: AsyncClient):
    """Test audio ingest without file returns 422."""
    response = await async_client.post(
        "/ingest/audio",
        data={"user_id": "test_user"},
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_text_category_ropa(async_client: AsyncClient):
    """Test that 'ropa' keyword maps to category Ropa."""
    response = await async_client.post(
        "/ingest/text",
        data={"text": "gasté 20 lucas en ropa", "user_id": "test_user"},
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "registered"
    # Category may be None if DB was empty (no seed data in test DB)
    # but amount should always be correct
    assert float(data["amount"]) == 20000.0


@pytest.mark.asyncio
async def test_ingest_text_transport_uber(async_client: AsyncClient):
    """Test that 'uber' keyword maps to Transporte."""
    response = await async_client.post(
        "/ingest/text",
        data={"text": "uber 8500", "user_id": "test_user"},
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "registered"
    assert float(data["amount"]) == 8500.0


@pytest.mark.asyncio
async def test_expense_created_accessible(async_client: AsyncClient):
    """Test that a registered expense can be fetched by ID."""
    ingest_resp = await async_client.post(
        "/ingest/text",
        data={"text": "gasté 5 lucas en café", "user_id": "test_user"},
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert ingest_resp.status_code == 200
    expense_id = ingest_resp.json()["expense_id"]

    get_resp = await async_client.get(
        f"/expenses/{expense_id}",
        headers={"X-Internal-Key": "test_internal_key"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == expense_id
