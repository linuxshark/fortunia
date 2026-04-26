# Fortunia Architecture

## Overview

Fortunia is a financial sub-agent for OpenClaw/Kraken that ingests and parses multi-modal expense data (text, images, audio) with zero-LLM core logic.

**Stack:**
- FastAPI (async Python) for REST API
- PostgreSQL + SQLAlchemy 2.x for persistence
- Tesseract + Whisper for OCR/ASR
- Docker Compose for local dev, Kubernetes-ready design
- Next.js 14 dashboard for visualization

## High-Level Architecture

```
Kraken (Telegram)
      ↓
OpenClaw (Delegation)
      ↓
Fortunia API (FastAPI)
├── Intent Detection (finance_detector.py)
├── Text Parser (text_parser.py)
├── Normalizer (normalizer.py)
├── Category Classifier (category_rules.py)
├── Receipt Parser (receipt_parser.py)
├── Audio Parser (audio_parser.py)
└── Database (PostgreSQL)

External Services:
├── OCR Service (Tesseract)
├── Whisper Service (ASR)
└── Dashboard (Next.js)
```

## Component Breakdown

### 1. Intent Detection (`app/classifiers/intent_detector.py`)

**Purpose**: Pre-filter messages as finance-related before parsing

**Input**: Raw text message
**Output**: `IntentResult(is_finance, confidence, needs_llm, reason)`

**Logic**:
- Finance verb matching (gastar, pagar, comprar, etc.)
- Negative context filtering (película, video, libro → non-finance)
- Confidence scoring (0.0–1.0)
- Returns `needs_llm=false` for core flow

**Example**:
```
Input: "gasté 15 lucas en ropa"
Output: is_finance=true, confidence=0.95

Input: "vi una película que costó 20 millones"
Output: is_finance=false, confidence=0.0
```

### 2. Amount Normalizer (`app/parsers/normalizer.py`)

**Purpose**: Convert Spanish currency shorthand to Decimal amounts

**Input**: Text snippet (e.g., "15 lucas", "5k", "1.5 millones")
**Output**: `Optional[Decimal]` (always in minor units for CLP)

**Formats Handled**:
- lucas (÷1000) → 1.000
- k, mil → ÷1000
- millones, m → ÷1,000,000
- Chilean format (15.000 = 15,000) → parse as int
- Decimals (1.5 lucas) → 1500

**Example**:
```python
normalize_amount("15 lucas") → Decimal(15000)
normalize_amount("5k") → Decimal(5000)
normalize_amount("1.5 millones") → Decimal(1500000)
```

### 3. Text Parser (`app/parsers/text_parser.py`)

**Purpose**: Extract structured fields from free-form text

**Input**: Raw text (e.g., "gasté 15 lucas en ropa")
**Output**: `ParsedExpense(amount, currency, category_hint, merchant_hint, confidence, parse_method)`

**Flow**:
1. Extract amount via regex + normalizer
2. Infer category via keyword matching (uber → transport, jumbo → food)
3. Infer merchant via keyword detection
4. Calculate confidence based on match strength

**Example**:
```python
parse_expense_text("uber 8500")
→ ParsedExpense(
    amount=8500,
    currency="CLP",
    category_hint="transport",
    merchant_hint="uber",
    confidence=0.95,
    parse_method="text_regex"
  )
```

### 4. Category Classifier (`app/classifiers/category_rules.py`)

**Purpose**: Classify expense into predefined categories

**Categories**: food, transport, entertainment, utilities, health, shopping, other

**Input**: Amount, merchant, category_hint
**Output**: Category string

**Logic**:
- Keyword matching on merchant (uber → transport, starbucks → food)
- Category hint validation
- Fallback to "other" if no match

### 5. Receipt Parser (`app/parsers/receipt_parser.py`)

**Purpose**: Extract fields from OCR'd receipt text

**Input**: OCR text from image (Spanish receipts)
**Output**: Structured fields (total, date, RUT, merchant, category)

**Extraction Rules**:
- **Total**: Regex for "TOTAL A PAGAR", "TOTAL:", "MONTO TOTAL"
- **Date**: DD/MM/YYYY, DD-MM-YYYY, DD/MM/YY
- **RUT**: XX.XXX.XXX-K (Chilean business ID)
- **Merchant**: First 3 non-empty lines of receipt
- **Confidence**: 0.5–0.95 based on match quality

**Example**:
```
Input OCR:
"""
JUMBO
RUT: 76.123.456-K
...
TOTAL A PAGAR: $25.500
12/04/2026
"""

Output: {
  "merchant": "JUMBO",
  "total": 25500,
  "date": "2026-04-12",
  "rut": "76.123.456-K",
  "category": "food",
  "confidence": 0.85
}
```

### 6. Audio Parser (`app/parsers/audio_parser.py`)

**Purpose**: Parse expense from speech-to-text transcript

**Input**: Whisper transcript (Spanish audio)
**Output**: ParsedExpense (reuses text_parser logic)

**Flow**:
1. Transcribe audio via Whisper service
2. Reuse text_parser on transcript
3. Flag low-confidence (<0.6) for manual review

### 7. Database Models (`app/models/`)

**Schema**:
```
categories (7 base: food, transport, entertainment, utilities, health, shopping, other)
merchants (indexed for fuzzy search)
expenses (user_id, amount, currency, category, spent_at)
raw_messages (audit trail: original text, user_id, msg_id)
attachments (OCR/audio metadata)
intent_feedback (user corrections for ML v2)
```

**Key Indexes**:
- `expenses(user_id, spent_at)` for range queries
- `merchants(name)` with pg_trgm for fuzzy matching

### 8. API Routes

**Ingest** (`/ingest/`):
- `POST /ingest/intent/check` — Pre-filter with intent detector
- `POST /ingest/text` — Full parsing pipeline (text → expense)
- `POST /ingest/image` — OCR receipt (image → expense)
- `POST /ingest/audio` — Transcribe audio (audio → expense)

**Query** (`/expenses/`):
- `GET /expenses` — List with filters (category, date range)
- `GET /expenses/{id}` — Fetch single expense
- `PATCH /expenses/{id}` — Correct/update expense
- `DELETE /expenses/{id}` — Remove expense

**Reports** (`/reports/`):
- `GET /reports/today` — Today's summary
- `GET /reports/month` — Monthly breakdown
- `GET /reports/categories` — Category totals + percentages
- `GET /reports/trend` — 30-day trend
- `GET /reports/top-merchants` — Top 10 merchants

**Admin** (`/admin/`):
- `POST /admin/feedback` — Intent correction feedback
- `GET /health` — Health check

### 9. External Services

**OCR Service** (`ocr-service/app.py`):
- Runs Tesseract with Spanish language pack
- Preprocessing: grayscale, auto-rotate, Otsu threshold
- Returns: `{text, confidence, raw_data}`

**Whisper Service** (external, via client):
- Transcribes Spanish audio to text
- Returns: `{text, language}`

### 10. OpenClaw Integration

**Kraken → Fortunia Flow**:
```
1. User sends Telegram message to Kraken
2. Kraken calls OpenClaw agent_send
3. OpenClaw routes to Fortunia sub-agent
4. Fortunia.finance_detector() → is_finance
5. If true: Fortunia.ingest_text() → expense record
6. Return status + expense_id to Kraken
7. Kraken sends confirmation to user
```

**Tools Exposed to OpenClaw**:
- `fortunia_ingest_text(text, user_id, msg_id)`
- `fortunia_ingest_image(image_bytes, user_id, caption)`
- `fortunia_ingest_audio(audio_bytes, user_id)`
- `fortunia_health()` — Check API status

## Data Flow Examples

### Example 1: Text Ingest
```
User: "gasté 15 lucas en ropa"
↓
Intent Detection: is_finance=true, confidence=0.95
↓
Text Parser:
  - amount: 15000
  - currency: CLP
  - category: shopping
  - merchant: (none)
↓
Create RawMessage audit record
Create Expense record
Return: { status: "registered", expense_id: "exp_001", ... }
```

### Example 2: Receipt Ingest
```
User sends receipt image
↓
OCR Service: Extracts "JUMBO", "TOTAL A PAGAR: $25.500", "12/04/2026"
↓
Receipt Parser:
  - total: 25500
  - category: food
  - merchant: JUMBO
  - confidence: 0.85
↓
Create Attachment record
Create Expense record
Return: { status: "registered", ... }
```

## Performance Considerations

**Parsing Speed**:
- Text parsing: <10ms (regex only)
- Intent detection: <5ms (keyword matching)
- Receipt parsing: 100–200ms (OCR is bottleneck)
- Audio transcription: 2–5s (Whisper service)

**Database**:
- pg_trgm index for merchant fuzzy search
- Monthly materialized view for fast reports
- Connection pooling (5–20 connections)

**Scaling**:
- Stateless API (horizontal scaling)
- Async handlers (handle 100+ concurrent requests)
- Database indexes optimize for user_id + date range queries

## Security

**Auth**: X-Internal-Key header validation on all endpoints
**Validation**: Pydantic models enforce types + ranges
**Audit**: RawMessage table logs all ingest attempts
**Secrets**: Database credentials, API keys in environment variables

## Testing Strategy

- **Unit**: Parsers/classifiers (52 test cases, ~90% coverage)
- **Integration**: Endpoints (31 test cases, ~75% coverage)
- **E2E**: Kraken integration (8 test cases via OpenClaw)

## Monitoring

**Key Metrics**:
- API response time (p50, p95, p99)
- Intent detection accuracy (% finance vs non-finance)
- Parser confidence distribution
- Failed ingest attempts (invalid amounts, auth errors)
- Database query latency

**Logging**:
- Each ingest attempt logged as RawMessage
- Parse errors logged to stderr + application logs
- API errors include request_id for tracing

## Future Enhancements

### v2.0
- LLM fallback for ambiguous cases (via `llm_fallback.py` stub)
- Merchant deduplication + fuzzy matching improvements
- Category ML classifier (if intent feedback accumulates)
- Recurring expense detection
- Budget alerts + notifications

### Scaling
- Migrate to Kubernetes for multi-region deployment
- Add Redis for caching popular merchants
- Shard database by user_id for multi-tenant scale
- Background job queue for long-running tasks (OCR batching)
