# 03 — Architecture

Pipeline foto → boleta → Postgres. Containerizado, offline-first; Gemini como escalación de pago cuando Tesseract no alcanza.

## Pipeline overview

```
Telegram photo
   │  (openclaw bot: photo[-1].get_file().download_to_memory())
   ▼
POST /ocr (FastAPI worker, docker-compose service)  ── compute image_sha256 (idempotency key)
   │
   ├─ Stage 1  Preprocess (OpenCV + Pillow + scikit-image): geometry → photometry
   │           ├─ grayscale/sharpened copy  ─────────────┐  (for barcode)
   │           └─ Sauvola-binarized copy  ───────────┐    │  (for OCR)
   │                                                  │    │
   ├─ Stage 2  Barcode-first (zxing-cpp PDF417) ◄─────┼────┘
   │           parse <TED>/<DD> → verified header (RUT, folio, type, date, total, merchant)
   │                                                  │
   ├─ Stage 3  OCR (Tesseract PSM 4, OEM 1, spa) ◄───┘   text + confidence
   │           └─ auto-escalación a Gemini 1.5 Flash si confianza < 65% o ítems < 20
   │
   ├─ Stage 4  Extract: regex header anchors + ITEM_SEARCH_RE line-items
   │
   ├─ Stage 5  Normalize (price-parser, dateparser) + categorize (item_aliases, ILIKE/regex)
   │
   └─ Stage 6  Validate (aritmética + TED MNT cross-check) → idempotent UPSERT Postgres
                   │ fail → manual-review queue via bot
                   ▼
              Postgres (docker-compose)
```

## Stage detail

### Stage 0 — Telegram intake
openclaw recibe la foto; download bytes a memoria; POST a `http://localhost:8002/ocr` en task asyncio para no bloquear el handler.

### Stage 1 — Preprocessing
Orden: geometry (EXIF fix → deskew) → photometry (upscale → CLAHE → denoise → Sauvola binarize → white border → DPI tag). Si no hay quad limpio, procesar frame completo.

### Stage 2 — Barcode-first
`zxing-cpp` PDF417 decode → parse TED → header verificado (RUT, folio, tipo, fecha, total, merchant), libre de errores OCR, `header_source='ted'`. **No usar pyzbar para PDF417.**

### Stage 3 — OCR
- **Primario: Tesseract** (`--psm 4 --oem 1 -l spa`). PSM 4 = columna única; OEM 1 = LSTM. ~60% confidence en fotos WhatsApp comprimidas.
- **Escalación automática: Gemini 1.5 Flash Vision** cuando `conf < 65` OR `(items < 20 AND validation != "ok")`. Prompt estructurado → JSON completo. ~$0.0002/foto. `ocr_engine` en respuesta indica cuál se usó.
- Si `GEMINI_API_KEY` vacío → Tesseract result siempre (fallback silencioso).

### Stage 4 — Extraction
- **Header regex anchors:** RUT (`\d{1,2}\.\d{3}\.\d{3}-[\dkK]` + mod-11), folio, fecha, IVA 19%, neto, TOTAL — reconciliado vs TED.
- **Line items:** `ITEM_SEARCH_RE` (search, no match) sobre líneas preprocesadas; filtra barcodes, ratio letras ≥35%, ≥3 letras consecutivas; SKIP_WORDS para header/footer.
- **Gemini path:** devuelve JSON estructurado con todos los ítems, misma forma que Tesseract path.

### Stage 5 — Normalización & categorización
`price-parser` (separador miles `.`, decimales `,`), `dateparser` (`languages=['es']`, `DATE_ORDER='DMY'`). Categorización determinista via `item_aliases` con `ILIKE`/regex, primer match por prioridad.

### Stage 6 — Validación & insert
- Checks: `qty*unit_price==line_total` (±redondeo), `sum(line_totals)+IVA==total`, `neto*1.19≈total`, RUT mod-11, **OCR total == TED MNT**.
- Fallo → manual-review queue via bot (nunca insertar filas financieras sin validar).
- `INSERT ... ON CONFLICT (image_sha256) DO NOTHING`; secundario unique `(rut_emisor, folio, doc_type)`.

## OCR engine summary

| Engine | Velocidad | Costo | Accuracy boletas | Uso |
|---|---|---|---|---|
| Tesseract PSM 4 OEM 1 | ~1s | gratis | ~60% conf | siempre primero |
| Gemini 1.5 Flash | ~5-10s | ~$0.0002/foto | ~95% | escalación automática |

Tesseract primero. Gemini sólo cuando necesario. Costo mensual esperado < $1 USD para uso personal.

## docker-compose topology

```
HOST (macOS, Apple Silicon)
├── openclaw Telegram bot ........ existing; POST photo bytes → localhost:8002
│
docker-compose.yml
├── worker ........ python:3.12-slim + tesseract-ocr-spa + zxing-cpp
│                   FastAPI + uvicorn + Gemini SDK
│                   port 8000 published; IMAGE_STORE=./data/images
├── postgres ...... postgres:16, named volume pgdata, pg_isready healthcheck
│                   port 5432 published
├── pgadmin ....... pgAdmin 4 (arm64) para SQL ad-hoc  port 5050
└── db-backup ..... cron: nightly pg_dump | gzip → ./backups; prunar >30d
```

Notas:
- Worker containerizado (linux/arm64). Apple Vision no disponible — reemplazado por Tesseract + Gemini.
- Bot alcanza worker en `localhost:8002` (mismo host).
- `GEMINI_API_KEY` en `.env`; si vacío, worker funciona offline-only con Tesseract.
- Stack idle < 1.5 GB RAM; OCR es CPU-bursty por foto; un worker cubre volumen personal diario.
