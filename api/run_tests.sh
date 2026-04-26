#!/bin/bash
# Run all tests with coverage reporting

set -e

echo "🧪 Running Fortunia Test Suite"
echo "================================"

# Install test dependencies
echo "📦 Installing test dependencies..."
pip install pytest pytest-asyncio pytest-cov httpx >/dev/null 2>&1

# Run tests with coverage
echo ""
echo "🔍 Running unit tests..."
pytest tests/ \
    --cov=app \
    --cov-report=html \
    --cov-report=term-missing \
    -v \
    --tb=short

echo ""
echo "✅ Test suite complete!"
echo "📊 Coverage report: htmlcov/index.html"
