# Fortunia — Personal Financial Sub-Agent

**Fortunia** is a financial expense tracking sub-agent for OpenClaw/Kraken that ingests and parses multi-modal expense data (text, images, audio) with zero-LLM core logic and deterministic parsing.

**Stack**: FastAPI + PostgreSQL + Next.js 14 + Docker Compose + Tesseract OCR + Whisper ASR

## Features

✅ **Multi-modal Ingest**: Text messages, receipt photos (OCR), voice notes (Whisper)
✅ **Deterministic Parsing**: Regex + keyword matching, <10% LLM fallback
✅ **Category Classification**: Automatic expense categorization (food, transport, etc.)
✅ **Financial Dashboard**: Real-time spending visualization, trends, reports
✅ **Kraken Integration**: Seamless delegation from main personal agent
✅ **Local Processing**: All data stays on-device, no cloud APIs except Kraken
✅ **Audit Trail**: Complete request logging for compliance
✅ **Production-Ready**: Kubernetes-compatible, backup/restore, monitoring

## Quick Start

```bash
# 1. Clone and setup
git clone <repo> && cd fortunia
cp .env.example .env

# 2. Generate secrets (edit .env after)
openssl rand -hex 32  # INTERNAL_API_KEY
openssl rand -hex 16  # PostgreSQL password

# 3. Start services
docker-compose up -d

# 4. Verify
curl http://localhost:8000/health
open http://localhost:3000  # Dashboard
```

## Documentation

### Getting Started
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — High-level design, component breakdown, data flows
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Production deployment (K8s, AWS ECS, Docker)
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — Common issues + solutions

### Operations
- **[BACKUP_RESTORE.md](BACKUP_RESTORE.md)** — Database backup strategy, disaster recovery
- **[TESTING.md](TESTING.md)** — Test suite overview, 83 test cases, coverage metrics
- **[kraken-integration/README.md](kraken-integration/README.md)** — Kraken integration, setup, tools

## Architecture

```
Kraken (Telegram)
      ↓
OpenClaw (Agent Delegation)
      ↓
Fortunia API (FastAPI)
├── Intent Detection (finance_detector.py)
├── Text Parser (text_parser.py)
├── Category Classifier (category_rules.py)
├── Receipt Parser (receipt_parser.py)
├── Audio Parser (audio_parser.py)
└── PostgreSQL Database
      ├── Expenses
      ├── Merchants
      ├── Categories
      ├── Raw Messages (audit)
      └── Attachments

External Services:
├── OCR Service (Tesseract + Spanish)
├── Whisper Service (Audio Transcription)
└── Dashboard (Next.js 14)
```

## API Endpoints

### Ingest
- `POST /ingest/intent/check` — Pre-filter messages for finance
- `POST /ingest/text` — Parse text expense ("gasté 15 lucas")
- `POST /ingest/image` — OCR receipt image
- `POST /ingest/audio` — Transcribe & parse audio

### Query
- `GET /expenses` — List expenses with filters
- `GET /expenses/{id}` — Fetch single expense
- `PATCH /expenses/{id}` — Correct/update expense
- `DELETE /expenses/{id}` — Delete expense

### Reports
- `GET /reports/today` — Daily summary
- `GET /reports/month` — Monthly breakdown
- `GET /reports/categories` — Category totals
- `GET /reports/trend` — 30-day trend
- `GET /reports/top-merchants` — Top 10 merchants

### Admin
- `POST /admin/feedback` — Intent correction feedback
- `GET /health` — Health check

## Development

### Commands

```bash
# Run all tests
cd api && pytest tests/ -v --cov=app

# Run specific test module
pytest tests/test_normalizer.py -v

# Start development server
docker-compose up -d
docker logs -f fortunia_api

# Database access
psql -h localhost -U postgres -d fortunia
```

### Project Structure

```
fortunia/
├── api/
│   ├── app/
│   │   ├── parsers/       # Text, receipt, audio parsing
│   │   ├── classifiers/   # Intent detection, category rules
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── routers/       # API routes (ingest, expenses, reports)
│   │   └── services/      # OCR, Whisper clients
│   ├── tests/             # 83 test cases, 75%+ coverage
│   └── Dockerfile
├── dashboard/
│   ├── app/               # Next.js 14 App Router
│   ├── lib/               # API client, utilities
│   └── Dockerfile
├── ocr-service/           # Tesseract OCR service
├── kraken-integration/    # Kraken agent tools & client
├── docker-compose.yml     # 6 services: db, api, ocr, whisper, dashboard, backup
├── ARCHITECTURE.md        # Detailed architecture
├── DEPLOYMENT.md          # Production deployment
├── TROUBLESHOOTING.md     # Common issues & fixes
├── BACKUP_RESTORE.md      # Database operations
└── TESTING.md             # Test strategy & coverage
```

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:password@db:5432/fortunia

# Security
INTERNAL_API_KEY=<generated: openssl rand -hex 32>

# External Services
OCR_SERVICE_URL=http://ocr-service:8001
WHISPER_SERVICE_URL=http://whisper-service:8002

# Locale
DEFAULT_CURRENCY=CLP
DEFAULT_TIMEZONE=America/Santiago

# Optional
LOG_LEVEL=INFO
```

## Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| Text parsing | <10ms | Regex only |
| Intent detection | <5ms | Keyword matching |
| Receipt parsing | 100-200ms | OCR bottleneck |
| Audio transcription | 2-5s | Whisper service |
| DB query (p95) | <100ms | With indexes |

## Monitoring

**Key Metrics**:
- API response time (p95, p99)
- Intent detection accuracy (>95% target)
- Ingest success rate (>99% target)
- Database latency (p95 <100ms)
- Error rate (<0.1% target)

**Health Checks**:
```bash
curl http://localhost:8000/health
# → {"status": "ok", "timestamp": "2026-04-26T..."}
```

## Testing

**Test Coverage**: 83 test cases across 3 suites

- **Unit Tests** (52 cases): Parsers, classifiers, normalizer (~90% coverage)
- **Integration Tests** (31 cases): API endpoints (~75% coverage)
- **E2E Tests** (8 cases): Kraken integration via OpenClaw

**Run Tests**:
```bash
cd api
pytest tests/ -v --cov=app --cov-report=html
open htmlcov/index.html
```

See [TESTING.md](TESTING.md) for full details.

## Security

- **Authentication**: X-Internal-Key header validation
- **Validation**: Pydantic models enforce types + ranges
- **Audit**: All ingest attempts logged as RawMessage records
- **Encryption**: Backups can be encrypted (GPG)
- **Network**: Kubernetes NetworkPolicy isolation available

## Backup & Recovery

**Automated Backups**: Daily 2 AM (America/Santiago), 7-day retention

**Recovery**:
```bash
# Restore from backup
zcat backups/fortunia_db_backup_YYYYMMDD.sql.gz | \
  docker-compose exec -T db psql -U postgres fortunia
```

See [BACKUP_RESTORE.md](BACKUP_RESTORE.md) for full strategy.

## Deployment

### Development (Docker Compose)
```bash
docker-compose up -d
```

### Production (Kubernetes)
See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Kubernetes manifests
- AWS ECS deployment
- Performance tuning
- Security best practices
- Monitoring setup
- Rollback procedures

## Troubleshooting

Common issues & solutions in [TROUBLESHOOTING.md](TROUBLESHOOTING.md):
- API not starting
- Database connection errors
- Intent detection wrong results
- Amount parsing fails
- OCR/Whisper timeouts
- Dashboard issues
- And 6 more...

## Future Roadmap

### v2.0
- [ ] LLM fallback for ambiguous cases (GPT-3.5, Claude)
- [ ] Merchant deduplication & fuzzy matching
- [ ] ML category classifier (if feedback accumulates)
- [ ] Recurring expense detection
- [ ] Budget alerts & notifications
- [ ] Export to CSV/Excel
- [ ] Multi-user support

### Scaling
- [ ] Redis caching for merchants
- [ ] Database sharding by user_id
- [ ] Background job queue (Celery)
- [ ] Multi-region replication

## License

MIT © 2026 Raúl E. Linares N.

---

**Questions?** Check [ARCHITECTURE.md](ARCHITECTURE.md) or [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**Ready to deploy?** See [DEPLOYMENT.md](DEPLOYMENT.md).
