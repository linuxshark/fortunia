# fortunia — boleta scanner

Foto de boleta chilena → Telegram (openclaw) → Postgres con detalle completo de ítems y gastos. Worker containerizado con Tesseract + fallback automático a Gemini Vision cuando la confianza OCR es baja.

## Estado actual (2026-06-28)

| Phase | Estado |
|---|---|
| 0 — Plumbing (docker-compose + schema + POST /ocr) | ✅ Completo |
| 1 — TED barcode (zxing-cpp PDF417) | ✅ Completo |
| 2 — OCR + regex header (folio, fecha, total) | ✅ Completo |
| 3 — Line items extracción | ✅ Completo (Tesseract regex + Gemini fallback) |
| 4 — Categorización (`item_aliases`) | ✅ Estructurado (diccionario vacío, poblar con datos) |
| 5 — Gemini Vision fallback automático | ✅ Completo |

## Layout

```
docker-compose.yml        worker + postgres (infra)
db/01_schema.sql          schema + analytical views
db/02_seed.sql            categorías chilenas + item_aliases
worker/
  app.py                  POST /ocr, GET /health
  extractor.py            orquestador: Tesseract → Gemini fallback
  gemini_ocr.py           Gemini 1.5 Flash Vision (escalación automática)
  extract.py              regex header + line items
  ocr.py                  Tesseract (PSM 4, OEM 1, spa)
  preprocess.py           EXIF → grayscale → CLAHE → Sauvola binarize
  barcode.py              zxing-cpp PDF417 → TED parse
  normalize.py            RUT mod-11, CLP amounts, fechas
  categorize.py           item_aliases ILIKE/regex
  validate.py             aritmética SII + cross-check TED
  db.py                   psycopg3 upsert idempotente
  config.py               pydantic-settings (.env)
docs/                     arquitectura y decisiones de diseño
```

## Quickstart

```bash
cp .env.example .env
# Editar .env: agregar GEMINI_API_KEY (https://aistudio.google.com/app/apikey)
docker compose up -d --build worker postgres
curl http://localhost:8002/health          # {"ok":true,"db":true}
curl -X POST http://localhost:8002/ocr -F "image=@/ruta/boleta.jpg"
```

## Cómo funciona el fallback Gemini

```
foto recibida
    │
    ▼
Tesseract OCR (gratis, offline, rápido)
    │
    ├─ confianza ≥ 65% Y ítems ≥ 20 → resultado Tesseract
    │
    └─ confianza < 65% O (ítems < 20 Y validación fallida)
           │
           ▼
       Gemini 1.5 Flash Vision (~$0.0002/foto)
       prompt estructurado → JSON completo con TODOS los ítems
           │
           ▼
       resultado Gemini (ocr_engine: "gemini-1.5-flash")
```

Si `GEMINI_API_KEY` está vacío en `.env`, el fallback se salta silenciosamente y se usa el resultado de Tesseract.

## openclaw integration

openclaw ya hace `POST http://localhost:8002/ocr` con la foto. No requiere cambios. El worker devuelve:

```json
{
  "status": "stored",
  "receipt_id": 12,
  "ocr_engine": "gemini-1.5-flash",
  "merchant": "UNIMARC",
  "rut_emisor": "76.123.456-7",
  "folio": "1804603542430",
  "issued_date": "2026-06-27",
  "total": 163303,
  "items": 38,
  "validation_status": "ok",
  "problems": []
}
```

Ver [`docs/07-openclaw-integration.md`](docs/07-openclaw-integration.md) para el handler completo.

## Análisis de gastos (SQL directo)

```sql
-- Todos los ítems de todas las boletas
SELECT r.issued_date, r.total AS total_boleta,
       li.normalized_name AS producto, li.unit_price, li.line_total
FROM receipts r JOIN line_items li ON li.receipt_id = r.id
ORDER BY r.issued_date DESC, li.line_no;

-- Gasto mensual por categoría
SELECT * FROM v_monthly_spend_by_category;

-- Items sin categorizar (para poblar item_aliases)
SELECT * FROM v_uncategorized_items LIMIT 50;
```
