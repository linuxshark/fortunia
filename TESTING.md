# Fortunia Test Strategy

## Test Coverage Overview

**Target Coverage**: 80%+ on critical modules
**Critical Modules**: parsers, classifiers, routers, services

### Test Suite Breakdown

#### 1. Unit Tests — Parsers & Classifiers (52 cases)

| Module | Tests | Focus |
|--------|-------|-------|
| `normalizer.py` | 14 | Currency normalization (lucas, k, mil, millones, format) |
| `intent_detector.py` | 23 | Finance intent detection, confidence scoring |
| `text_parser.py` | 15 | Expense text parsing, category/merchant inference |
| `receipt_parser.py` | 8 | OCR receipt parsing, total/date/RUT extraction |
| `audio_parser.py` | 9 | Audio transcript parsing, confidence handling |

**Coverage**: ~90% on core parsing logic (deterministic, no LLM)

#### 2. Integration Tests — Endpoints (31 cases)

| Module | Tests | Focus |
|--------|-------|-------|
| Ingest | 11 | Text, image, audio ingestion; auth; validation |
| Expenses | 10 | CRUD operations, filtering, pagination |
| Reports | 10 | Daily, monthly, trending, category, merchants |

**Coverage**: ~75% on API routes

#### 3. E2E Tests — Kraken Integration

| Module | Tests | Focus |
|--------|-------|-------|
| `finance_detector.py` | 5 | Intent detection consistency |
| `fortunia_client.py` | 3 | API connectivity, ingest flow, retries |

**Coverage**: ~70% on integration flows

## Running Tests

### All Tests
```bash
cd api && python -m pytest tests/ -v --cov=app --cov-report=html
```

### By Category
```bash
# Unit tests only
pytest tests/test_normalizer.py tests/test_intent_detector.py tests/test_text_parser.py -v

# Integration tests only
pytest tests/test_ingest_endpoints_full.py tests/test_expense_endpoints.py tests/test_report_endpoints.py -v

# Kraken integration tests
cd kraken-integration && python test_integration.py
```

### With Coverage
```bash
pytest tests/ --cov=app --cov-report=term-missing --cov-report=html
```

## Test Structure

### Unit Tests
Location: `api/tests/`
- Each parser/classifier has dedicated test file
- 100+ assertions covering happy path + edge cases
- Uses deterministic test data

### Integration Tests
Location: `api/tests/`
- Test full request/response cycles
- Mock external services (OCR, Whisper)
- Verify side effects (database audit trails)

### E2E Tests
Location: `kraken-integration/`
- test_intent_detection(): 5 cases
- test_api_connectivity(): Health check
- test_ingest_flow(): Full flow validation

## Critical Paths

**Always test these scenarios:**
1. Amount parsing: lucas, k, mil, millones, decimals, Chilean format
2. Intent detection: Finance vs non-finance, confidence scoring
3. Category classification: Keyword matching, merchant hints
4. API auth: X-Internal-Key validation
5. Audit trails: RawMessage creation on ingest
6. Error handling: Invalid amounts, non-finance text, missing auth

## Coverage Standards

| Module | Target | Status |
|--------|--------|--------|
| Parsers | 90%+ | ✓ High coverage |
| Intent | 85%+ | ✓ 23 test cases |
| Routers | 75%+ | ✓ 31 endpoint tests |
| Services | 70%+ | ✓ OCR/Whisper mocked |

## Debugging Tests

```bash
# Run single test
pytest tests/test_normalizer.py::test_lucas_normalization -v

# Run with print statements
pytest tests/ -v -s

# Run with debugger
pytest tests/ --pdb

# Run only failed tests from last run
pytest --lf
```

## CI/CD Integration

Tests should run:
- On every PR
- Before deployment
- On merge to main

Target: All tests pass in <60s

## Known Limitations

- OCR/Whisper services mocked in tests (use live testing for integration)
- Database tests use SQLite in-memory (PostgreSQL should be tested in staging)
- Telegram/Kraken integration tested via manual verification

## Future Improvements

1. Add load testing for API under concurrent requests
2. Add chaos testing for network failures
3. Add property-based testing for parsers (Hypothesis)
4. Add visual regression testing for dashboard
5. Add performance benchmarks for slow operations
