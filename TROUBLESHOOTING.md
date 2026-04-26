# Fortunia Troubleshooting Guide

## Common Issues & Solutions

### 1. API Not Starting

**Symptom**: `docker-compose up api` fails or API container exits immediately

**Solutions**:

```bash
# Check logs
docker logs fortunia_api

# Common causes:
# 1. Database not ready
docker-compose up db -d && sleep 5 && docker-compose up api

# 2. Missing environment variables
# Check .env file exists and contains:
# - DATABASE_URL=postgresql://...
# - INTERNAL_API_KEY=...
# - FORTUNA_API_URL=http://localhost:8000

# 3. Port conflict (8000 already in use)
lsof -i :8000  # Find what's using port 8000
# Change docker-compose.yml port mapping if needed
```

### 2. Database Connection Errors

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Solutions**:

```bash
# Verify PostgreSQL is running
docker-compose ps db

# Check PostgreSQL logs
docker logs fortunia_db

# Verify credentials in .env
grep DATABASE_URL .env

# Reset database (caution: destroys data)
docker-compose down -v  # Remove volumes
docker-compose up db    # Recreate database

# Check if port 5432 is accessible
psql -h localhost -U postgres -d fortunia -c "SELECT 1;"
```

### 3. Intent Detection Returning Wrong Results

**Symptom**: Text marked as non-finance when it should be finance (or vice versa)

**Solutions**:

```bash
# Test intent detector directly
cd kraken-integration
python3 finance_detector.py "gasté 15 lucas"
# Expected: IS_FINANCE=true

# Check confidence threshold
# Low confidence (<0.5) should trigger LLM fallback
# Edit: app/classifiers/intent_detector.py
#   - Add/remove finance_verbs
#   - Adjust negative_context_patterns
#   - Tune confidence_score calculation

# Common issues:
# 1. Verb not in list: add to finance_verbs
# 2. False positive: add negative pattern (e.g., "película" → non-finance)
# 3. Low confidence: increase weights in scoring logic
```

### 4. Amount Parsing Fails

**Symptom**: `400 Bad Request: Invalid amount` when sending valid amount

**Solutions**:

```bash
# Test normalizer directly
cd api
python -c "from app.parsers.normalizer import normalize_amount; print(normalize_amount('15 lucas'))"

# Common format issues:
# 1. "15lucas" (no space) → Add \s* in regex
# 2. "15,000" (comma decimal) → Chilean format uses . not ,
# 3. "15.000,50" (European format) → Normalize first
# 4. "15 L" → Edit app/parsers/normalizer.py, add "L" alias

# Verify all formats:
pytest api/tests/test_normalizer.py -v
```

### 5. OCR Not Working

**Symptom**: `GET /ocr` returns empty text or errors

**Solutions**:

```bash
# Check OCR service is running
docker-compose ps ocr-service
curl http://localhost:8001/ocr -F "file=@receipt.jpg"

# Verify Tesseract is installed
docker exec fortunia_ocr_service tesseract --version

# Image preprocessing issues:
# 1. Image too small: needs >100x100 pixels
# 2. Text blurry: Tesseract confidence drops below 50%
# 3. Non-Spanish text: Set lang=spa in request

# Test with sample image:
# Place receipt image in /tmp/test.jpg
curl -F "file=@/tmp/test.jpg" http://localhost:8001/ocr

# If confidence <0.5, image quality is poor
# Try: rotate, increase contrast, reduce shadows
```

### 6. Whisper Service Timeout

**Symptom**: `timeout: 60s` when sending audio

**Solutions**:

```bash
# Check Whisper service connectivity
curl http://localhost:8002/asr \
  -F "file=@audio.wav" \
  -F "task=transcribe" \
  -F "language=es" \
  -F "output=txt"

# Audio file requirements:
# - Format: WAV, MP3, OGG, or FLAC
# - Duration: <30 minutes
# - Sample rate: 16kHz recommended
# - Language: Spanish (es)

# Common issues:
# 1. Audio too long: Whisper times out
#    Solution: Chunk audio into <10m segments
# 2. Service unresponsive: Restart container
#    docker restart fortunia_whisper_service
# 3. CPU throttling: Increase docker memory limit
#    Edit docker-compose.yml: mem_limit: 2g
```

### 7. Dashboard Won't Load

**Symptom**: `http://localhost:3000` shows blank page or errors

**Solutions**:

```bash
# Check dashboard service
docker-compose ps dashboard
docker logs fortunia_dashboard

# Verify API connection from dashboard
# Check browser console (F12 → Console tab)
# Look for: "Failed to fetch from http://localhost:8000"

# Fix API URL
# Edit dashboard/.env.local:
NEXT_PUBLIC_API_URL=http://localhost:8000

# Rebuild dashboard
docker-compose down dashboard
docker-compose up dashboard --build

# Dashboard build errors:
# "Module not found" → Run npm install in dashboard/
# "TypeScript errors" → Check app/*.tsx for syntax errors
npm run type-check
```

### 8. API Key Validation Failing

**Symptom**: `403 Forbidden: Invalid X-Internal-Key` on all requests

**Solutions**:

```bash
# Verify API key in request header
curl -H "X-Internal-Key: your_key" http://localhost:8000/health

# Check .env file
grep INTERNAL_API_KEY .env

# Key must match in:
# 1. .env (INTERNAL_API_KEY=...)
# 2. Request header (X-Internal-Key: ...)
# 3. OpenClaw config (if using delegation)

# Reset/rotate key
# 1. Generate new: openssl rand -hex 32
# 2. Update .env
# 3. Restart API: docker-compose restart api
# 4. Update Kraken OpenClaw config with new key
```

### 9. High LLM Usage (Unexpected Costs)

**Symptom**: Intent detector calling LLM fallback too often

**Solutions**:

```bash
# Check intent detection logs
docker logs fortunia_api | grep "needs_llm=true"

# If >10% need LLM fallback, adjust detection rules:
# Edit: app/classifiers/intent_detector.py

# 1. Add missing finance verbs
finance_verbs = {
    "gastar", "pagar", "comprar", "costar",
    "invertir", "trasnferir", ...
}

# 2. Expand negative context patterns
negative_patterns = {
    r"película", r"video", r"streaming",
    r"libro", r"artículo", ...
}

# 3. Lower confidence thresholds
# Change: if confidence < 0.5 → needs_llm=true
# To: if confidence < 0.3 → needs_llm=true

# Test changes:
pytest api/tests/test_intent_detector.py -v
```

### 10. Duplicate Expenses Created

**Symptom**: Same expense recorded multiple times

**Solutions**:

```bash
# Check for duplicate message_ids
psql -h localhost -d fortunia -c "
  SELECT message_id, COUNT(*) 
  FROM raw_messages 
  GROUP BY message_id 
  HAVING COUNT(*) > 1;
"

# Root cause:
# 1. Kraken retrying failed messages
# 2. Duplicate message_id in OpenClaw

# Fix:
# 1. Add unique constraint to raw_messages(message_id)
# 2. Implement idempotent POST (return same expense_id for same message_id)
# 3. Ensure Kraken doesn't retry successful requests

# Query duplicates for user
SELECT * FROM expenses 
WHERE user_id = 'user_123' 
  AND created_at > NOW() - INTERVAL '1 day'
ORDER BY created_at DESC;
```

### 11. Slow Expense Queries

**Symptom**: `GET /expenses` takes >1s for large datasets

**Solutions**:

```bash
# Check index effectiveness
# Connect to PostgreSQL:
psql -h localhost -d fortunia

# View query plan
EXPLAIN ANALYZE
SELECT * FROM expenses 
WHERE user_id = 'user_123' 
  AND spent_at BETWEEN '2026-01-01' AND '2026-12-31'
LIMIT 50;

# Expected: should use index on (user_id, spent_at)
# If not, rebuild indexes:
REINDEX TABLE expenses;

# Monitor slow queries:
# Edit postgresql.conf:
log_min_duration_statement = 100  # Log queries >100ms
SELECT query, mean_time FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;
```

### 12. Docker Compose Services Won't Start

**Symptom**: `docker-compose up` fails immediately

**Solutions**:

```bash
# Check Docker daemon is running
docker ps

# Validate docker-compose.yml syntax
docker-compose config

# Check resource limits
docker stats  # View CPU/memory usage

# Common errors:
# 1. "Port X already in use"
#    → Change port in docker-compose.yml
# 2. "No such file or directory"
#    → Verify all paths exist: .env, docker-compose.yml, Dockerfile
# 3. "Service creation failed"
#    → Check logs: docker logs fortunia_<service>

# Full reset (caution: loses all data)
docker-compose down -v
docker system prune -a
docker-compose up --build
```

## Debugging Tips

### Enable Verbose Logging

```bash
# API logs
docker logs -f fortunia_api

# Database logs
docker logs -f fortunia_db

# Dashboard logs (if running locally)
npm run dev  # See console output

# All docker logs at once
docker-compose logs -f
```

### Test Individual Components

```bash
# Test intent detection
python -m app.classifiers.intent_detector "gasté 15 lucas"

# Test parser
python -c "from app.parsers.text_parser import parse_expense_text; print(parse_expense_text('uber 8500'))"

# Test database connection
python -c "from app.db import SessionLocal; db = SessionLocal(); print(db.execute('SELECT 1'))"

# Test API endpoint
curl -H "X-Internal-Key: test" http://localhost:8000/health
```

### Database Inspection

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d fortunia

# View schema
\dt                    # List tables
\d expenses            # Describe expenses table
\di                    # List indexes

# Query data
SELECT COUNT(*) FROM expenses;
SELECT user_id, COUNT(*) FROM expenses GROUP BY user_id;
SELECT category, SUM(amount) FROM expenses GROUP BY category;
```

## Performance Monitoring

```bash
# Monitor API response times
docker exec fortunia_api tail -f /tmp/api.log | grep "response_time"

# Monitor database connections
psql -c "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"

# Monitor disk space
du -sh /var/lib/docker/volumes/fortunia_*

# Monitor container resource usage
docker stats fortunia_api fortunia_db fortunia_ocr_service
```

## Getting Help

1. **Check logs first**: 99% of issues appear in Docker logs
2. **Test in isolation**: Use curl to test endpoints directly
3. **Verify credentials**: .env, API keys, database URLs
4. **Check versions**: Ensure Python 3.11+, PostgreSQL 14+, Node 18+
5. **Read ARCHITECTURE.md**: Understand the data flow

For bugs or questions, check the issues in GitHub or contact the team.
