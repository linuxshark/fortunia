# 05 — Roadmap & Risks

## Phased build order (MVP first)

Front-loads the cheapest, highest-certainty wins (barcode header data); defers the expensive, uncertain line-item work until plumbing + header path are solid. Every stage stays offline and token-free.

### Phase 0 — Plumbing (no extraction yet)
Stand up docker-compose (postgres + pgadmin + backup), create the schema, wire openclaw → FastAPI `/ocr` → store raw image + `image_sha256` + stub row. Prove round trip and idempotency.
**Deliverable:** photos land in the DB with dedup working.

### Phase 1 — MVP extraction: header only, barcode-first
Add preprocessing (geometry→photometry) + `zxing-cpp` PDF417 decode → parse TED → verified header (RUT, folio, date, total, merchant) + RUT mod-11 validation.
**Deliverable:** every receipt with a readable barcode gets accurate header data for free, no OCR yet.

### Phase 2 — OCR + header reconciliation
Add Apple Vision (`ocrmac`) + regex header extraction; reconcile vs TED; fall back to pure OCR header when the barcode fails. Add `price-parser` / `dateparser` normalization.
**Deliverable:** headers work even without a barcode.

### Phase 3 — Line items (the hard part)
Positional bbox reconstruction for line items; arithmetic validation (`sum(lines)+IVA==total`, cross-checked vs TED `MNT`); manual-review queue via the bot for failures; `invoice2data` templates for top 3–5 merchants.
**Deliverable:** itemized data behind a validation gate.

### Phase 4 — Categorization & analytics
Seed `categories` + `item_aliases` Chilean retail dictionary; deterministic `ILIKE`/regex categorization at ingest; build analytical views (monthly spend, price history, uncategorized queue).
**Deliverable:** queryable spend insights.

### Phase 5 — (optional) fine-tuned Donut
Only if Phase 3 line-item accuracy is insufficient. Label a few hundred boletas, fine-tune Donut locally (PyTorch MPS), run behind the same validation gate. Keep extraction modular so the engine swaps without touching bot or DB. PaddleOCR fallback + PDF-factura branch (`invoice2data` / `cl-sii`) can land here too.

## Risks (stated honestly)

1. **Line items are the genuinely hard part.** No OSS tool does reliable generic grocery line-item extraction. Expect real tuning: positional clustering thresholds + per-merchant templates. Most likely to disappoint early.
2. **PDF417 from a phone photo may not decode** if blurry/warped/low-res. Strategy degrades gracefully (fall back to OCR) but loses the free checksum. Mitigate: prompt retake when barcode region unreadable.
3. **Apple Vision lock-in to macOS.** Primary path assumes the Mac mini host. Portability requires the PaddleOCR/Tesseract container path as a documented escape hatch.
4. **Thermal-receipt fade + crumpling** breaks y-clustering and binarization. Preprocessing mitigates but won't fully solve worst-case photos. Manual-review queue is the safety net.
5. **Generative-model temptation.** Donut/Ollama inherit hallucination risk on financial data. Always validate arithmetically; never insert unvalidated generative output.
6. **PaddleOCR install friction on macOS ARM** (paddlepaddle wheels) — a reason Apple Vision is primary, Paddle is fallback.
7. **License footnotes:** LayoutLMv3 = CC-BY-NC-SA NonCommercial (avoid if commercial); `pdf417decoder` = CPOL (review); OCRmyPDF = MPL file-level copyleft (fine as a dependency). Core stack (OpenCV, scikit-image, Pillow, zxing-cpp, invoice2data, price-parser, dateparser, ocrmac, PaddleOCR, Tesseract, cl-sii) is all MIT/Apache/BSD — clean.

## Definition of done (per phase)

- Phase 0: send a photo → row appears once even if sent twice.
- Phase 1: barcode receipts show correct RUT/folio/total without OCR.
- Phase 2: non-barcode receipts get headers; totals reconcile.
- Phase 3: line items sum to total (within tolerance) or land in review.
- Phase 4: `v_monthly_spend_by_category` returns sensible numbers.
