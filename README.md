# boleta-scanner

Token-free pipeline: photo of a Chilean boleta/factura → Telegram (openclaw) → local Postgres for personal-finance analysis. No AI/LLM API tokens — classic OCR + SII barcode decode + rule-based extraction, offline, on a Mac mini.

Full design in [`docs/`](docs/). Start with [`docs/README.md`](docs/README.md).

## Layout

```
docker-compose.yml     postgres + pgadmin + nightly backup (infra only)
db/01_schema.sql       schema + analytical views
db/02_seed.sql         Chilean category taxonomy + categorization dictionary
worker/                FastAPI OCR worker — runs as a macOS HOST process
  app.py               POST /ocr  (Phase 0 functional)
  config.py db.py      settings + Postgres (Phase 0)
  preprocess.py barcode.py ocr.py extract.py normalize.py categorize.py validate.py
docs/                  discovery + architecture (read these first)
```

> The OCR worker is **not** containerized: Apple Vision (primary OCR) only works on the macOS host. Only Postgres/pgAdmin/backup run in docker-compose. See [`docs/03-architecture.md`](docs/03-architecture.md).

## Quickstart (Phase 0 — plumbing)

```bash
cp .env.example .env          # edit passwords
docker compose up -d          # postgres + pgadmin + backup; schema/seed auto-load

cd worker
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app:app --host 0.0.0.0 --port 8000

# smoke test (separate shell)
curl -F image=@../Boletas/some.jpg http://localhost:8000/ocr   # -> stored
curl -F image=@../Boletas/some.jpg http://localhost:8000/ocr   # -> duplicate (dedup works)
```

## openclaw integration (bot side)

In the photo handler:

```python
import httpx
file = await update.message.photo[-1].get_file()
buf = await file.download_to_memory()
async with httpx.AsyncClient() as c:
    r = await c.post("http://localhost:8000/ocr",
                     files={"image": ("receipt.jpg", buf.getvalue(), "image/jpeg")})
# reply with r.json() summary; route 'review' status back to user
```

## Build order

Phase 0 plumbing → Phase 1 barcode header → Phase 2 OCR + reconcile → Phase 3 line items → Phase 4 categorization/analytics → Phase 5 (optional) Donut. See [`docs/05-roadmap-and-risks.md`](docs/05-roadmap-and-risks.md).
