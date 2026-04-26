"""Integration tests for Kraken ↔ Fortunia communication."""

import asyncio
import sys

sys.path.insert(0, "intent")
sys.path.insert(0, "delegators")

from finance_detector import is_finance_intent
from fortunia_client import FortunaClient


async def test_intent_detection():
    """Test finance_detector.py with various inputs."""
    print("=== Testing Intent Detection ===\n")

    test_cases = [
        ("gasté 15 lucas en ropa", True, 0.95),
        ("pagué uber 6500", True, 0.95),
        ("vi una película que costó 20 millones", False, 0.0),
        ("leí que iPhone cuesta 1.5 millones", False, 0.0),
        ("supermercado 35 mil", True, 0.85),
    ]

    for text, expected_is_finance, expected_confidence in test_cases:
        result = is_finance_intent(text)
        status = "✓" if result.is_finance == expected_is_finance else "✗"
        print(f"{status} '{text}'")
        print(f"  is_finance={result.is_finance}, confidence={result.confidence:.2f}")
        print(f"  reason={result.reason}\n")


async def test_api_connectivity():
    """Test HTTP connectivity to Fortunia API."""
    print("=== Testing API Connectivity ===\n")

    client = FortunaClient()

    try:
        # Test /health endpoint
        async with __import__("httpx").AsyncClient() as http_client:
            response = await http_client.get(
                f"{client.api_url}/health",
                timeout=5.0
            )
            if response.status_code == 200:
                print("✓ Fortunia API is healthy")
                print(f"  Response: {response.json()}\n")
            else:
                print(f"✗ API responded with {response.status_code}\n")
    except Exception as e:
        print(f"✗ Cannot connect to {client.api_url}")
        print(f"  Error: {str(e)}\n")


async def test_ingest_flow():
    """Test full ingest flow (requires running API)."""
    print("=== Testing Ingest Flow ===\n")

    client = FortunaClient()

    try:
        # Test /ingest/text endpoint
        result = await client.ingest_text(
            "gasté 15 lucas en ropa",
            user_id="test_user",
        )

        if result.get("status") == "registered":
            print("✓ Text ingest successful")
            print(f"  Expense ID: {result.get('expense_id')}")
            print(f"  Amount: {result.get('amount')} {result.get('currency')}")
            print(f"  Category: {result.get('category')}")
            print(f"  User message: {result.get('user_message')}\n")
        else:
            print(f"✗ Ingest returned: {result.get('status')}")
            print(f"  Message: {result.get('user_message')}\n")

    except Exception as e:
        print(f"✗ Ingest test failed: {str(e)}\n")


async def main():
    """Run all integration tests."""
    print("Fortunia ↔ Kraken Integration Tests\n")
    print("=" * 50 + "\n")

    await test_intent_detection()
    await test_api_connectivity()
    await test_ingest_flow()

    print("=" * 50)
    print("\nIntegration test suite completed.")
    print("For full end-to-end testing, send messages to Kraken in Telegram.")


if __name__ == "__main__":
    asyncio.run(main())
