# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Fortunia** is a specialized financial sub-agent for personal expense tracking. It integrates with **Kraken** (the main personal agent) running in OpenClaw on a Mac Mini M1. Fortunia runs as a Docker Compose stack and processes expenses from text, images (receipts/boletas), and audio via deterministic parsing—**not LLM-first**.

**Key Philosophy**: The LLM is optional, not the engine. Goal: <10% of messages touch an LLM; the rest resolve via regex, lookup tables, and fuzzy matching.

## Architecture

```
User Message (Telegram)
      ↓
   Kraken (OpenClaw)
      ↓
   Pre-filter (regex, zero tokens)
      ↓
   /intent/check endpoint
      ↓
   [If is_finance=true] → Fortunia API (FastAPI)
                              ↓
      ┌─────────────┬──────────┬──────────┐
      ↓             ↓          ↓          ↓
   Parser    Category      Merchant    Confidence
  (normalizer) (rules)     (fuzzy DB)   (score)
      ↓
   PostgreSQL (16-alpine)
      ↓
   Dashboard (Next.js 14, LAN)
```

- **API**: FastAPI on `127.0.0.1:8000` (localhost only).
- **Dashboard**: Next.js on `0.0.0.0:3000` (LAN accessible).
- **DB**: PostgreSQL with pg_trgm for fuzzy merchant search.
- **OCR**: Tesseract in container (`ocr-service:8001`), Spanish support.
- **STT**: Whisper `small` model in container (`whisper-service:9000`).
- **Orchestration**: Docker Compose with healthchecks and persistent volumes in `data/`.

## Critical Assumptions

These are **constants** for this project:

| Setting | Value | Reason |
|---------|-------|--------|
| **Timezone** | `America/Santiago` (CLP) | User in Chile |
| **Default currency** | CLP | Chile |
| **Language** | Spanish (es-CL) | User + receipt/audio context |
| **OS** | macOS + Apple Silicon (M1) | Whisper model selection (small, faster-whisper) |
| **Network** | localhost only for API (0.0.0.0 for dashboard) | Security boundary; dashboard accessed from LAN |
| **DB init** | Automatic via docker-entrypoint, includes seeds | 7 base categories + keywords |

## Common Development Commands

### Initial Setup

```bash
# First time: copy env template and generate secrets
cp .env.example .env
# Edit .env, generate: openssl rand -hex 24 (DB_PASSWORD), openssl rand -hex 32 (API_KEY)

# Install and start all services
./install.sh
# Or manually: docker compose up -d

# Verify services are running
docker compose ps

# View logs (all services)
docker compose logs -f
# Single service: docker compose logs -f fortunia-api
```

### API Development

```bash
# Run inside container or venv
cd api

# Lint + type check
ruff check . && mypy app --strict

# Run tests (requires Postgres running)
pytest --cov=app --cov-report=term-missing -v

# Single test file
pytest tests/test_intent_detector.py -v

# Single test
pytest tests/test_intent_detector.py::test_finance_verb_with_amount -v

# OpenAPI docs
# Open http://localhost:8000/docs in browser after `docker compose up -d`

# Check intent detection (curl)
curl -X POST http://localhost:8000/intent/check \
  -H "X-Internal-Key: $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"gasté 15 lucas en ropa"}'

# Test text ingest
curl -X POST http://localhost:8000/ingest/text \
  -H "X-Internal-Key: $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"pagué uber 6500","user_id":"test"}'
```

### Database

```bash
# Access Postgres directly
docker exec -it fortunia-db psql -U fortunia -d fortunia

# Common queries
SELECT COUNT(*) FROM expenses;
SELECT * FROM categories;
SELECT * FROM monthly_summaries;

# Manual migration (if Alembic)
docker exec fortunia-api alembic upgrade head

# Dump backup
docker exec fortunia-db pg_dump -U fortunia fortunia > backup.sql

# Restore
docker exec -i fortunia-db psql -U fortunia fortunia < backup.sql

# Reset (for testing)
docker compose down -v && docker compose up -d db
```

### Dashboard

```bash
cd dashboard

# Install deps
npm install

# Dev server (locally)
npm run dev
# Access http://localhost:3000

# Build
npm run build

# Production (in container)
docker compose up -d --build dashboard
```

### Docker

```bash
# Rebuild specific service
docker compose up -d --build fortunia-api

# View resource usage
docker stats

# Stop all
docker compose down

# Full reset (DATA LOSS!)
docker compose down -v && rm -rf data/

# Healthcheck status
docker compose ps  # HEALTHY / UNHEALTHY / STARTING

# Check service logs for errors
docker compose logs ocr-service --tail 50
```

## File Structure & Key Modules

```
fortunia/
├── IMPLEMENTATION_PLAN.md      ← Detailed 8-stage implementation roadmap
├── api/                        ← FastAPI app + parsers + tests
│   ├── app/
│   │   ├── parsers/            ← CORE: text_parser, normalizer, receipt_parser
│   │   ├── classifiers/        ← intent_detector (decides if msg is financial)
│   │   ├── routers/            ← /ingest/*, /reports/*, /health
│   │   ├── models/             ← SQLAlchemy ORM (Expense, Category, Merchant, etc)
│   │   ├── schemas/            ← Pydantic request/response models
│   │   ├── services/           ← ocr_client, whisper_client
│   │   └── main.py             ← FastAPI app setup, CORS, middleware
│   └── tests/                  ← pytest suite (target: 80%+ coverage, 100+ intent cases)
│
├── ocr-service/                ← Tesseract container (POST /ocr → text)
├── dashboard/                  ← Next.js 14 (App Router, Tailwind, Recharts)
├── kraken-integration/         ← Integration files for Kraken/OpenClaw
│   ├── intent/finance_detector.py  ← Standalone intent detector (mirror of API version)
│   ├── delegators/fortunia_client.py ← HTTP client to Fortunia API
│   └── openclaw-config-snippet.json5
│
├── .claude/agents/             ← Sub-agent definitions (Haiku/Sonnet)
│   ├── fortunia-scaffolder.md
│   ├── fortunia-docker.md
│   ├── fortunia-db.md
│   ├── fortunia-parser.md       ← Core parser logic design
│   ├── fortunia-api.md
│   ├── fortunia-multimodal.md
│   ├── fortunia-router.md       ← Kraken integration
│   ├── fortunia-dashboard.md
│   ├── fortunia-tester.md       ← Test strategy
│   └── fortunia-docs.md
│
├── docker-compose.yml          ← Defines: db, fortunia-api, ocr-service, whisper-service, dashboard, backup-service
└── data/                       ← [GITIGNORED] postgres/, uploads/, backups/
```

## Critical Modules (Read First)

1. **`api/app/parsers/intent_detector.py`** — Decides if a message is financial (zero-LLM). Quality here determines system reliability. Must pass 100+ test cases before production.

2. **`api/app/parsers/text_parser.py`** — Extracts amount, category, merchant from free text. Uses `normalizer.py` (handles "15 lucas" → 15000) and `category_rules.py` (keyword matching).

3. **`api/app/models/expense.py`** — SQLAlchemy ORM. Schema includes: `amount`, `currency`, `category_id`, `merchant_id`, `spent_at`, `source` (text/image/audio/manual), `confidence`.

4. **`api/app/routers/ingest.py`** — Entry points for Kraken:
   - `POST /ingest/text` — Main API for text expenses.
   - `POST /intent/check` — Kraken pre-filters here before delegating.
   - `POST /ingest/image`, `POST /ingest/audio` — Multimodal support.

5. **`kraken-integration/openclaw-config-snippet.json5`** — User must merge this into `~/.openclaw/openclaw.json` manually. Defines Fortunia as a sub-agent.

## Testing Strategy

- **Unit tests**: Parsers, normalizer, intent detector (via `pytest api/tests/`).
- **Intent detector test cases**: Minimum 100 (50 positive, 50 negative), including Chilean-specific phrases:
  - Positives: "gasté 15 lucas", "pagué uber 6500", "compré sushi 18 mil"
  - Negatives: "vi una película que costó 20 millones", "iPhone cuesta 1.5 millones", "cuánto cuesta una pizza?"
  
- **Integration tests**: Spin up ephemeral Postgres, test full ingest flow.
- **Target coverage**: >80% in `app/parsers/` and `app/classifiers/`.
- **Run all tests**: `pytest api/tests/ --cov=app -v`

## Typical Development Flow

1. **Check IMPLEMENTATION_PLAN** for current stage (stages 1-8).
2. **Invoke the stage's sub-agent** from `.claude/agents/` (e.g., `fortunia-parser` for stage 4).
3. **Sub-agent writes code**, tests, or infrastructure.
4. **Run validation** (tests, type check, lint) before declaring a stage done.
5. **Wait for "ok continúa"** before starting next stage.

## Deployment Context

- User's OpenClaw instance runs on Mac Mini M1 with `sandbox-mode: "off"`.
- Fortunia runs in Docker Compose locally alongside Kraken.
- Kraken listens on Telegram; receives messages → pre-filters → delegates to Fortunia if financial.
- Fortunia returns structured `IngestResponse` with `user_message` field ready to send back to Telegram.
- Dashboard accessible from LAN devices at `http://<mac-ip>:3000`.

## Database Schema Notes

Seven default categories pre-seeded:
- Alimentación (food/grocery keywords)
- Transporte (uber, metro, bencina, peaje)
- Salud (pharmacy, doctor, clinic)
- Hogar (rent, utilities, internet)
- Entretenimiento (netflix, steam, cine)
- Ropa (clothing, shoes)
- Otros (catch-all)

Key tables:
- `expenses` — Main facts; indexed on `spent_at`, `user_month`, `category_id`.
- `merchants` — Fuzzy searchable via pg_trgm on normalized name.
- `raw_messages` — Audit trail; tracks Telegram ID, intent detected, whether LLM was used.
- `intent_feedback` — Optional: user corrections for model retraining.
- `monthly_summaries` — Materialized view for fast dashboard queries.

## Troubleshooting Checklist

| Issue | Check | Fix |
|-------|-------|-----|
| Services won't start | `docker compose logs` | Usually missing `.env` or secrets. Run `./install.sh`. |
| intent_detector slow | Regex or category lookup inefficient | Cache categories in memory at app startup. |
| Intent has false positives | Test dataset inadequate | Add more negative cases to test suite. |
| OCR text quality poor | Tesseract config or image preprocessing | Try `psm=6`, grayscale + threshold pre-processing. |
| Whisper slow on M1 | Using wrong model or engine | Ensure `ASR_MODEL=small` and `ASR_ENGINE=faster_whisper`. |
| Dashboard blank | Proxy route misconfigured or API key missing | Check `app/api/proxy/[...path]/route.ts` passes `X-Internal-Key`. |
| Kraken can't reach Fortunia API | Network or `FORTUNA_API_URL` wrong | Verify `localhost:8000` accessible from Kraken container; check env var. |

## Key Constraints & Non-Goals

- **No multi-user in v1**: All expenses assume `user_id="user"`. Multi-tenancy is v2.
- **Spanish-only parsing rules**: English/other languages not supported by regexes. LLM fallback optional.
- **No real-time sync**: Dashboard updates on refresh, not push. Acceptable for personal expense tracking.
- **No cloud**: Everything local/self-hosted. No external APIs except optional LLM fallback.
- **Chile-specific defaults**: Assumes CLP, Chilean receipt formats, Santiago timezone.

## Integration with Kraken (OpenClaw)

Kraken → Fortunia flow:

1. User sends message to Kraken via Telegram.
2. Kraken calls `finance_detector.py` (local, <1ms, zero tokens).
3. If `is_finance=false`, Kraken responds normally.
4. If `is_finance=true` or `ambiguous`, Kraken calls `/intent/check` (HTTP POST).
5. If confirmed financial, Kraken delegates via `agent_send(agentId="fortunia", message)`.
6. Fortunia's sub-agent system prompt tells it to invoke `fortunia_ingest_text` tool.
7. Tool returns `IngestResponse.user_message` (ready for Telegram, no LLM rewrite).
8. Kraken sends response back to user as-is.

See `kraken-integration/README.md` for step-by-step setup.

## Sub-Agent Model Selection

When invoking agents from `.claude/agents/`, use:

| Agent | Model | When | Example Task |
|-------|-------|------|--------------|
| fortunia-scaffolder | haiku | Stage 1 | Create directory structure, `.gitignore` |
| fortunia-docker | haiku | Stage 2 | Write `docker-compose.yml`, `install.sh` |
| fortunia-db | sonnet | Stage 3 | Schema design, ORM models, migrations |
| fortunia-parser | sonnet | Stage 4 | Intent detector, text parser, regex rules |
| fortunia-api | sonnet | Stage 5 | FastAPI endpoints, request validation |
| fortunia-multimodal | sonnet | Stage 6 | OCR, Whisper integration, preprocessing |
| fortunia-router | sonnet | Stage 7 | Kraken integration, client, config snippet |
| fortunia-dashboard | sonnet | Stage 8a | Next.js UI, charts, proxy route |
| fortunia-tester | sonnet | Stage 8b | Test suites, coverage, CI workflows |
| fortunia-docs | haiku | Stage 8c | README, architecture docs, troubleshooting |

---

**For detailed implementation roadmap, see `IMPLEMENTATION_PLAN.md`.**
