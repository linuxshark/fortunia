# 03 — Recommended Architecture

> **Build decision (2026-06-27):** the whole repo runs in **docker-compose** on the Mac mini, so the worker is **containerized** and OCR uses **Tesseract (`-l spa`)**, not Apple Vision (which is macOS-host-only). PaddleOCR remains the optional accuracy upgrade. The sections below describe the original recommendation; where they say "Apple Vision / host process", the shipped MVP substitutes containerized Tesseract. See `docker-compose.yml` (service `worker`), `worker/Dockerfile`, and [07-openclaw-integration.md](07-openclaw-integration.md).

End-to-end **token-free** pipeline. Barcode-first; OCR fills the line-item gap; everything rule-based/local.

## Pipeline overview

```
Telegram photo
   │  (openclaw bot, python-telegram-bot: photo[-1].get_file().download_to_memory())
   ▼
POST /ocr (FastAPI worker, macOS host process)   ── compute image_sha256 (idempotency key)
   │
   ├─ Stage 1  Preprocess (OpenCV + Pillow + scikit-image): geometry → photometry
   │           ├─ grayscale/sharpened copy  ─────────────┐  (for barcode)
   │           └─ Sauvola-binarized copy  ───────────┐    │  (for OCR)
   │                                                  │    │
   ├─ Stage 2  Barcode-first (zxing-cpp PDF417) ◄─────┼────┘
   │           parse <TED>/<DD> → verified header (RUT, folio, type, date, total, merchant)
   │                                                  │
   ├─ Stage 3  OCR (Apple Vision → PaddleOCR → Tesseract) ◄─┘  text + word boxes
   │
   ├─ Stage 4  Extract: regex header anchors + positional bbox line-items + invoice2data templates
   │
   ├─ Stage 5  Normalize (price-parser, dateparser) + categorize (item_aliases dict, ILIKE/regex)
   │
   └─ Stage 6  Validate (arithmetic + SII checksums + TED MNT cross-check) → idempotent UPSERT into Postgres
                   │ fail → manual-review queue back through the bot
                   ▼
              Postgres (docker-compose)
```

## Stage detail

### Stage 0 — Telegram intake
- openclaw receives the photo; grab highest-res variant; download bytes to memory.
- **Ingestion pattern: REST** (bot → `httpx.post("http://localhost:8000/ocr", files=...)`), called in an `asyncio` task so slow OCR never blocks the bot handler.
- **Why REST** over shared-volume or Redis for single-node personal use: synchronous, trivially debuggable, no filesystem-as-queue races, no extra moving parts. Redis/RQ is the *upgrade path* only when durable retries / burst handling are needed.

### Stage 1 — Preprocessing
Order: geometry first (EXIF fix → quad detect → 4-point warp → deskew), photometry second (upscale → CLAHE → denoise → **Sauvola** binarize → white border → DPI tag). See [01 §4](01-discovery-prior-art.md#4-image-preprocessing-the-single-biggest-accuracy-driver). If no clean quad is found, process the whole frame rather than aborting.

### Stage 2 — Barcode-first (the Chilean key move)
`zxing-cpp` PDF417 decode → parse TED → verified header fields, OCR-error-free, flagged `header_source='ted'`. See [02](02-chile-sii-dte.md). **Never use pyzbar for PDF417.**

### Stage 3 — OCR
- **Primary: Apple Vision via `ocrmac`**, `recognition_languages=['es-ES']`, accurate mode. Fastest, most robust on phone photos, zero install/model friction.
- **Fallback: PaddleOCR** (classic PP-OCRv5/v6 + PP-Structure for table cells) for low-confidence images and portability. **Avoid PaddleOCR "VL" vision-LLM variants.**
- Run on the binarized copy to recover the line-item table the TED omits.

### Stage 4 — Extraction (hybrid)
- **Header regex anchors:** RUT (`\d{1,2}\.\d{3}\.\d{3}-[\dkK]` + mod-11), folio, fecha, `IVA 19%`, neto, TOTAL — reconciled against TED.
- **Line items via positional reconstruction** from word boxes (Apple Vision boxes, or `pytesseract image_to_data` on the fallback path): filter `conf>60` → cluster rows by *y* → infer column *x*-bands → map `name | qty | unit_price | line_total`.
- **Per-merchant `invoice2data` templates** for the top 3–5 stores (Líder, Jumbo, Santa Isabel, farmacias) using its field-based `lines` parser.
- **PDF-factura branch:** emailed digital PDF → `invoice2data`; full DTE XML available → `cl-sii` (lossless, no OCR).

### Stage 5 — Normalization & categorization
- `price-parser` (`decimal_separator=','`), `dateparser` (`languages=['es']`, `DATE_ORDER='DMY'`, `STRICT_PARSING=True`).
- Deterministic categorization via `item_aliases` dictionary matched with `ILIKE`/regex, first-match-by-priority. No LLM. See [04](04-database-schema.md).

### Stage 6 — Validation & insert
- Checks: `qty*unit_price==line_total` (±rounding), `sum(line_totals)+IVA==total`, `neto*1.19≈total`, RUT mod-11, **OCR total == TED `MNT`**.
- Fail/low-confidence → manual-review queue via bot (never silently insert bad financial rows).
- `INSERT ... ON CONFLICT (image_sha256) DO NOTHING`; secondary unique `(rut_emisor, folio, doc_type)`; insert `line_items` only when the receipt row is newly created → fully retryable.

## OCR engine recommendation (justified)

**Apple Vision (primary) + PaddleOCR (fallback), Tesseract last resort.** Given the Mac mini Apple Silicon constraint:

- **Apple Vision** — already in macOS (no downloads), ~130–210 ms/img on the Neural Engine, most robust on crumpled/noisy photos (it backs Live Text), good `es-ES`, returns boxes, fully offline. *Consequence: worker must be a **host process**, not a Linux container.*
- **PaddleOCR** — Apache-2.0, Apple-Silicon optimized, strong table/cell extraction; portable escape hatch. Install friction on ARM is the reason it's fallback, not primary.
- **Tesseract** (`-l spa`, `--psm 4/6`) — lightest/most portable, but most noise-sensitive; the floor, and the engine for a fully-containerized path if ever needed.
- **Local models (Donut/LayoutLMv3/Ollama VLM)** — token-free but wrong for MVP. Donut is the best escalation (Phase 5); LayoutLMv3 is NonCommercial-licensed; VLMs are heavy, slow, non-deterministic.

## docker-compose topology

```
HOST (macOS, Apple Silicon)
├── openclaw Telegram bot ........ existing; POSTs photo bytes over HTTP
└── ocr-worker (FastAPI + uvicorn)  HOST PROCESS (NOT containerized)
        Apple Vision (ocrmac) + OpenCV + zxing-cpp + invoice2data
        + price-parser + dateparser + psycopg → connects to localhost:5432

docker-compose.yml  (all native linux/arm64)
├── postgres ...... postgres:16, named volume pgdata, pg_isready healthcheck,
│                   port 5432 published so the host worker can connect
├── pgadmin ....... pgAdmin 4 (light, arm64) for ad-hoc SQL  (pick this OR metabase)
└── db-backup ..... cron sidecar: nightly pg_dump | gzip -> ./backups; prune >30d
```

Notes:
- **Worker = host process** because Apple Vision is unreachable from Linux containers. A fully-containerized alternative uses `python:3.12-slim-bookworm` (Debian, native arm64 wheels — **avoid alpine**, musl breaks OpenCV/numpy wheels) with `apt-get install tesseract-ocr tesseract-ocr-spa libzbar0 libgl1 libglib2.0-0` + `opencv-python-headless` — but loses Apple Vision.
- Bot reaches worker at `host.docker.internal:8000` (if bot containerized) or `localhost:8000` (host process).
- Healthcheck: `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`, interval 10s, retries 5, start_period 30s. Worker should retry-connect on startup.
- Analysis UI: pgAdmin (light) to start; add Metabase only if you want dashboards and have ~1 GB+ RAM. Pick one.
- Sizing: stack idles under ~1.5 GB RAM; OCR is CPU-bursty per photo; one worker handles daily personal volume.
