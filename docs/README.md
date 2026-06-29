# Boleta Scanner — Discovery & Design Docs

Token-free pipeline that turns **photos of Chilean retail receipts (boletas/facturas)** sent to a Telegram bot (openclaw) into **itemized rows in a local Postgres** for personal-finance analysis. No cloud / LLM API tokens are spent — all extraction is rule-based / classic OCR / local barcode decode running on a Mac mini server via docker-compose.

## Goal

1. User photographs a boleta and sends it to the existing openclaw Telegram bot.
2. A Python worker decomposes the receipt: **per-item** (name, qty, unit price, line total) + grand total + date + merchant + tax.
3. Data is inserted into a local Postgres designed for spend analysis.
4. **Hard constraint:** zero AI/LLM API tokens. Offline, deterministic, auditable.

## The two key findings from discovery

1. **Barcode-first beats OCR-first in Chile.** Every SII electronic document (DTE) prints a **PDF417 "Timbre Electrónico" (TED)** barcode containing signature-verified header XML: RUT, folio, doc type, date, grand total, merchant. Decode it before OCR — it's free, has zero OCR error, and gives a *checksum* to validate the OCR'd line items. Caveat: the TED does **not** carry per-line items, so OCR is still required for the itemized table.
2. **No OSS tool does generic grocery line-item extraction out of the box.** The realistic architecture is two layers: an OCR engine → a custom rule/positional extractor. Line items are the genuinely hard part and need positional reconstruction + per-merchant templates for top stores.

## Document index

| Doc | Contents |
|-----|----------|
| [01-discovery-prior-art.md](01-discovery-prior-art.md) | Prior art survey: parsing libraries, OCR engines, extraction techniques, preprocessing, local models. All license/maintenance status verified. |
| [02-chile-sii-dte.md](02-chile-sii-dte.md) | Chilean SII DTE format, the TED PDF417 barcode, what it does/doesn't contain, and how to decode it locally. |
| [03-architecture.md](03-architecture.md) | Recommended end-to-end pipeline (stage by stage), OCR engine choice with justification, docker-compose topology. |
| [04-database-schema.md](04-database-schema.md) | Postgres schema (merchants / receipts / line_items / categories / dictionaries), dedup strategy, analytical views. |
| [05-roadmap-and-risks.md](05-roadmap-and-risks.md) | Honest risks + phased build order (MVP first). |
| [06-references.md](06-references.md) | All sources gathered during discovery. |

## Recommended stack (TL;DR)

- **Intake:** openclaw bot → POST image bytes → FastAPI `/ocr` (host process).
- **Preprocess:** OpenCV + Pillow + scikit-image (geometry → photometry; Sauvola binarization).
- **Barcode:** `zxing-cpp` for PDF417 (NOT pyzbar — zbar can't read PDF417) → parse TED XML.
- **OCR:** Apple Vision via `ocrmac` (primary, Mac-native) → PaddleOCR (fallback) → Tesseract (last resort).
- **Extract:** regex header anchors + positional bbox line-item reconstruction + `invoice2data` templates for top merchants.
- **Normalize:** `price-parser` (CLP) + `dateparser` (es, DMY).
- **Store:** Postgres 16 in docker-compose; deterministic `ILIKE`/regex categorization; idempotent UPSERT.

> Status: **Discovery complete.** Next step: `/plan` the implementation, starting with Phase 0 (plumbing).
