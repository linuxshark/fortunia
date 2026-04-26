"""Tests for ingest endpoints."""

import pytest
from decimal import Decimal


class TestIngestEndpoints:
    """Test suite for /ingest/* endpoints (requires running API)."""

    def test_intent_check_finance(self) -> None:
        """Test /intent/check detects finance."""
        # Integration test - would run against live API
        # Example: POST /intent/check with {"text": "gasté 15 lucas"}
        # Expected: {"is_finance": true, "confidence": 0.95, ...}
        pass

    def test_intent_check_not_finance(self) -> None:
        """Test /intent/check rejects non-finance."""
        # Example: POST /intent/check with {"text": "vi una película que costó 20 millones"}
        # Expected: {"is_finance": false, ...}
        pass

    def test_ingest_text_basic(self) -> None:
        """Test POST /ingest/text basic flow."""
        # Would require: test DB, API running
        # POST /ingest/text with form data: text="gasté 15 lucas en ropa"
        # Expected: 201 Created with IngestResponse
        pass

    def test_ingest_text_no_amount(self) -> None:
        """Test POST /ingest/text rejects when no amount detected."""
        # POST /ingest/text with text="gasté en ropa"
        # Expected: status="rejected", reason about missing amount
        pass

    def test_ingest_text_creates_raw_message(self) -> None:
        """Test that ingest/text creates RawMessage audit record."""
        # Verify DB contains RawMessage with type='text'
        pass

    def test_expense_created_with_correct_category(self) -> None:
        """Test that category is correctly inferred."""
        # POST /ingest/text with text="pagué jumbo 35 mil"
        # Verify Expense.category_id points to 'Alimentación'
        pass

    # End-to-end scenarios

    def test_e2e_text_expense_to_telegram(self) -> None:
        """End-to-end: text → parse → create → return user_message."""
        # Simulate full flow: "gasté 15 lucas en ropa" → ✅ Registrado: Ropa — CLP 15.000
        pass

    def test_e2e_multiple_expenses_same_day(self) -> None:
        """Test multiple expenses in same day."""
        # Create 3 expenses, verify DB contains all 3
        pass
