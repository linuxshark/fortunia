# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: fortunia — Receipt OCR Scanner

Chilean receipt scanner: Telegram → openclaw → worker OCR → Postgres → dashboard web UI. Uses Tesseract for local OCR with automatic Gemini Vision fallback when confidence is low.

## Architecture

**Two-service architecture:**

1. **Worker** (`:8002`) — OCR API, receives images, persists to DB
   - FastAPI server (`worker/app.py`)
   - Image preprocessing pipeline (`worker/preprocess.py`)
   - Tesseract OCR with regex extraction (`worker/ocr.py`, `worker/extract.py`)
   - Automatic Gemini 1.5 Flash fallback if confidence < 65% (`worker/gemini_ocr.py`)
   - Line item extraction, categorization, barcode parsing (TED/PDF417)
   - Validation via SII checksum and arithmetic checks
   - Idempotent by image hash (SHA256)

2. **Dashboard** (`:8001`) — Read-only web UI, visualization only
   - FastAPI + Jinja2 + HTMX templates (`dashboard/app.py`, `dashboard/templates/`)
   - Chart.js visualizations
   - Connects via read-only DB role (`fortunia_ro`) — never writes
   - Views: monthly KPIs, category breakdown, receipt detail, expense list

**Database layer:**
- PostgreSQL 16 with analytical views
- Schema: `receipts`, `line_items`, `merchants`, `categories`, `item_aliases`
- Upsert-by-hash logic in `worker/db.py` (idempotent image storage)
- Read-only role for dashboard security (`db/03_ro_role.sh`)

**Config:**
- All settings via `.env` (Pydantic Settings in `config.py`)
- Image store: `./data/images/` (binary format with SHA256 filename)
- Docker Compose orchestration with health checks, backup, pgAdmin

## Common Commands

### Setup & Lifecycle

```bash
# First time: create .env from template, fill in secrets
make

# Build and start all services (Postgres first, waits for health)
make deploy

# Start without rebuilding
make up

# Stop (keep data)
make stop

# Stop and remove containers (keep DB volume)
make down

# Destroy everything and start fresh
make destroy
```

### Testing & Integration

```bash
# Health check worker and dashboard
make health
make health-dashboard

# Test OCR endpoint with a receipt image
make scan FILE=/path/to/receipt.jpg

# Test with bundled test image (if available)
make scan-test
```

### Logs & Debugging

```bash
# All service logs (last 50 lines, follow)
make logs

# Individual service logs
make logs-worker       # OCR worker (100 lines)
make logs-dashboard    # Web UI (100 lines)
make logs-db           # Postgres (50 lines)

# Service status
make status
```

### Database Access

```bash
# Interactive psql console
make psql

# Common queries (via Makefile shortcuts)
make receipts         # Last 20 scanned receipts
make items            # Line items from latest receipt
make spend            # Monthly spend by category
make uncategorized    # Items without category (for populating item_aliases)

# Manual backup (immediate pg_dump)
make backup           # Creates backups/manual-YYYYMMDD-HHMMSS.sql.gz

make fund              # Aplica el DDL del Fondo Común a la DB en marcha (idempotente)
```

### Dashboard Setup

```bash
# Create/update read-only DB role (idempotent, required before first dashboard startup)
make ro-role

# Build and start dashboard service only
make dashboard

# Watch dashboard logs
make logs-dashboard
```

### Worker Maintenance

```bash
# Rebuild worker image (with cache)
make build

# Full clean rebuild (no cache, then start)
make rebuild

# Restart worker process (without rebuild)
make restart
```

## Environment Setup

Copy `.env.example` to `.env` and fill:
- `POSTGRES_PASSWORD` — DB password for `boleta` user
- `POSTGRES_RO_PASSWORD` — Read-only role password (for dashboard)
- `GEMINI_API_KEY` — Google API key (optional; Tesseract fallback if empty)
- `PGADMIN_DEFAULT_PASSWORD` — Web-based DB admin (optional)
- `OCR_PORT` / `DASHBOARD_PORT` — Override defaults if port conflicts

## Key Files

- `docker-compose.yml` — Service orchestration, volumes, health checks
- `worker/app.py` — OCR endpoint handler (`POST /ocr`)
- `worker/extractor.py` — Orchestration: preprocess → OCR → validate → categorize
- `worker/db.py` — Postgres connection, upsert-by-hash idempotency
- `dashboard/app.py` — Web routes and data views
- `dashboard/queries.py` — SQL queries for dashboard (read-only)
- `db/01_schema.sql` — Table definitions and analytical views
- `db/02_seed.sql` — Category and item alias seed data
- `db/03_ro_role.sh` — Read-only role creation (idempotent)
- `db/06_fund.sql` — Fondo Común: categorías shared, `fund_monthly`, vista `v_fund_monthly`
- `dashboard/writes.py` — única escritura del dashboard (presupuesto, acotada a `fund_monthly`)
- `dashboard/templates/_fund.html` — barra de progreso + tarjetas de categoría compartida
- `Makefile` — All operational commands

## Data Flow

```
Telegram photo
    ↓
openclaw (mac mini)
    ↓ POST http://localhost:8002/ocr
worker/app.py:ocr()
    ↓
extractor.py (orchestrates pipeline)
    ├─ preprocess: EXIF → grayscale → CLAHE → Sauvola binarize
    ├─ extract_text: regex patterns for header (folio, date, total)
    ├─ extract_items: line item parsing (description, qty, price)
    ├─ barcode: TED/PDF417 decoding
    ├─ categorize: item_aliases ILIKE/regex matching
    ├─ validate: SII checksum + arithmetic
    └─ fallback (if confidence < 65%): Gemini 1.5 Flash Vision
    ↓
db.py:persist() — upsert-by-hash, return receipt_id
    ↓
JSON response → openclaw → Telegram user
    ↓
dashboard: read from receipts/line_items via read-only role
```

## OCR Confidence & Fallback Logic

- **Tesseract runs first** (local, fast, free)
- **Uses result if:**
  - Confidence ≥ 65% AND items found ≥ 20
  - OR validation passes (SII checksum + arithmetic match)
- **Falls back to Gemini 1.5 Flash if:**
  - Confidence < 65% OR (items < 20 AND validation failed)
  - Cost: ~$0.0002/fallback (free if `GEMINI_API_KEY` empty, just uses Tesseract)
- Response includes `ocr_engine` field: `"tesseract"` or `"gemini-1.5-flash"`

## Testing Notes

- Worker API is idempotent by image SHA256: same receipt → `status: "duplicate"`
- Dashboard connects read-only; any write attempt raises an error
- `make ro-role` is idempotent — safe to run multiple times
- Backup runs nightly in container; `make backup` forces immediate dump

## Known Patterns

- **Pydantic Settings** for config: worker and dashboard each have `config.py` reading `.env`
- **Psycopg 3 (binary)** for async-ready DB connections
- **Jinja2 for templating** (dashboard); HTMX for AJAX interactions
- **Chart.js for visualizations** (revenue/spend charts, category breakdown)
- **Item aliases** (dict in `db/02_seed.sql`) — regex patterns for categorizing line items

## Debugging OCR Issues

1. Check confidence/validation in response: `validation_status` and `problems` array
2. View stored image and metadata: `make receipts` + `make items`
3. Inspect Tesseract extraction: `worker/extract.py` regex patterns
4. Verify Gemini fallback: check logs (`make logs-worker`) for `"engine": "gemini-1.5-flash"`
5. Test categorization: `make uncategorized` to see items without category, update `db/02_seed.sql`
