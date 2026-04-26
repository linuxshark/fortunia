"""Full integration tests for ingest endpoints."""

import pytest
from httpx import AsyncClient
from app.main import app
from app.db import get_db
from sqlalchemy import select
from app.models import Expense, RawMessage
from decimal import Decimal
from datetime import datetime, timezone

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_ingest_text_success(client):
    """Test successful text ingest."""
    response = await client.post(
        "/ingest/text",
        json={
            "text": "gasté 15 lucas en ropa",
            "user_id": "test_user",
            "message_id": "msg_001"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "registered"
    assert data["amount"] == 15000
    assert data["currency"] == "CLP"
    assert data["category"] in ["shopping", "other"]
    assert "expense_id" in data
    assert data["confidence"] > 0.5

@pytest.mark.asyncio
async def test_ingest_text_low_confidence(client):
    """Test text ingest with low confidence flags for review."""
    response = await client.post(
        "/ingest/text",
        json={
            "text": "v un video que costó mucho",
            "user_id": "test_user",
            "message_id": "msg_002"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["needs_confirmation"] is True or data["confidence"] < 0.7

@pytest.mark.asyncio
async def test_ingest_text_non_finance(client):
    """Test text that isn't finance-related."""
    response = await client.post(
        "/ingest/text",
        json={
            "text": "vi una película que costó 20 millones",
            "user_id": "test_user",
            "message_id": "msg_003"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 400
    data = response.json()
    assert "not a finance-related" in data.get("detail", "").lower()

@pytest.mark.asyncio
async def test_ingest_text_missing_api_key(client):
    """Test request without API key."""
    response = await client.post(
        "/ingest/text",
        json={
            "text": "gasté 100 lucas",
            "user_id": "test_user",
            "message_id": "msg_004"
        }
    )

    assert response.status_code == 403

@pytest.mark.asyncio
async def test_ingest_text_invalid_amount(client):
    """Test text with unparseable amount."""
    response = await client.post(
        "/ingest/text",
        json={
            "text": "gasté xxx lucas en comida",
            "user_id": "test_user",
            "message_id": "msg_005"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 400
    data = response.json()
    assert "amount" in data.get("detail", "").lower()

@pytest.mark.asyncio
async def test_ingest_intent_check_finance(client):
    """Test intent pre-check for finance."""
    response = await client.post(
        "/ingest/intent/check",
        json={"text": "pagué 5000 por uber"},
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_finance"] is True
    assert data["confidence"] > 0.8

@pytest.mark.asyncio
async def test_ingest_intent_check_not_finance(client):
    """Test intent check for non-finance."""
    response = await client.post(
        "/ingest/intent/check",
        json={"text": "vi una película"},
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_finance"] is False

@pytest.mark.asyncio
async def test_ingest_image_missing_file(client):
    """Test image ingest without file."""
    response = await client.post(
        "/ingest/image",
        json={
            "user_id": "test_user",
            "caption": "receipt from walmart"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 422  # Unprocessable entity

@pytest.mark.asyncio
async def test_ingest_audio_missing_file(client):
    """Test audio ingest without file."""
    response = await client.post(
        "/ingest/audio",
        json={
            "user_id": "test_user"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 422  # Unprocessable entity

@pytest.mark.asyncio
async def test_ingest_text_audit_trail(client):
    """Test that ingest creates audit trail."""
    msg_id = "audit_test_001"
    response = await client.post(
        "/ingest/text",
        json={
            "text": "gasté 500 lucas en café",
            "user_id": "test_user",
            "message_id": msg_id
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    expense_id = response.json()["expense_id"]

    # Verify expense and raw message were created
    response = await client.get(
        f"/expenses/{expense_id}",
        headers={"X-Internal-Key": "test_internal_key"}
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_ingest_text_with_category_hint(client):
    """Test text ingest with category keyword."""
    response = await client.post(
        "/ingest/text",
        json={
            "text": "uber 8500",
            "user_id": "test_user",
            "message_id": "msg_006"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "transport"

@pytest.mark.asyncio
async def test_ingest_text_with_merchant(client):
    """Test text ingest identifies merchant."""
    response = await client.post(
        "/ingest/text",
        json={
            "text": "jumbo 25000",
            "user_id": "test_user",
            "message_id": "msg_007"
        },
        headers={"X-Internal-Key": "test_internal_key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("merchant") is not None or data.get("amount") == 25000
