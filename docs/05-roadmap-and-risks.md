# 05 — Roadmap & Risks

## Phased build order

### Phase 0 — Plumbing ✅ Completo
docker-compose (postgres + pgadmin + backup), schema, openclaw → FastAPI `/ocr` → store raw image + `image_sha256` + stub row. Round trip e idempotencia probados.

### Phase 1 — Barcode-first header ✅ Completo
Preprocessing (geometry→photometry) + `zxing-cpp` PDF417 decode → parse TED → header verificado (RUT, folio, fecha, total, merchant) + validación RUT mod-11.

### Phase 2 — OCR + header reconciliation ✅ Completo
Tesseract (`--psm 4 --oem 1 -l spa`) + regex header; reconcilia vs TED; fallback a header OCR cuando barcode falla. `price-parser` / `dateparser` normalización.

### Phase 3 — Line items ✅ Completo
`ITEM_SEARCH_RE` (search no match), barcode stripping, filtros ratio letras + SKIP_WORDS. Validación aritmética (`sum(lines)+IVA==total`, cross-check vs TED MNT). Queue manual-review via bot para fallos.

### Phase 4 — Categorización & analytics ✅ Estructurado
Seed `categories` + `item_aliases` (diccionario vacío, poblar con datos reales). Vistas analíticas: `v_monthly_spend_by_category`, `v_spend_by_merchant`, `v_item_price_history`, `v_uncategorized_items`, `v_tax_reconciliation`.
**Próximo paso:** poblar `item_aliases` con los ítems de `v_uncategorized_items`.

### Phase 5 — Gemini Vision fallback ✅ Completo
Escalación automática cuando Tesseract confianza < 65% o ítems < 20 y validación falla. Gemini 1.5 Flash Vision, prompt estructurado, ~$0.0002/foto. `GEMINI_API_KEY` vacío = offline-only. Reemplaza el plan original de fine-tune Donut.

## Risks

1. **Line items son la parte difícil.** ✅ Mitigado con Gemini fallback. Tesseract captura ~60% en fotos comprimidas; Gemini sube a ~95%. Riesgo residual: fotos muy borrosas o boletas no estándar.

2. **PDF417 puede no decodificar** si la foto es borrosa/torcida/baja resolución. La pipeline degrada graciosamente a OCR-only. Mitigación: prompt de retake cuando región barcode ilegible.

3. **Apple Vision lock-in** ✅ Resuelto. Worker containerizado usa Tesseract + Gemini; no depende de macOS host. Portabilidad completa: funciona en cualquier Linux arm64 o amd64.

4. **Thermal-receipt fade + crumpling** rompe binarización y clustering. Preprocessing mitiga pero no resuelve worst-case. Manual-review queue es el safety net; Gemini maneja mejor fotos ruidosas que Tesseract.

5. **Gemini temptation / alucinación.** Gemini output pasa por el mismo validate() que Tesseract: `qty*unit_price==line_total`, `sum(lines)==total`. Inserción bloqueada si no cuadra. Nunca insertar filas financieras sin validación aritmética.

6. **Costo Gemini.** ~$0.0002/foto. 100 boletas/mes = $0.02. No es riesgo económico; sí es riesgo de fuga si `GEMINI_API_KEY` se expone. La key nunca va al repo (`.gitignore` + `.env`).

7. **License footnotes.** Core stack (OpenCV, scikit-image, Pillow, zxing-cpp, Tesseract, price-parser, dateparser, psycopg, google-generativeai) = MIT/Apache/BSD — limpio. LayoutLMv3 = CC-BY-NC-SA NonCommercial (no usar). `pdf417decoder` = CPOL (revisar).

## Definition of done

- Phase 0: foto → row aparece una vez aunque se envíe dos veces. ✅
- Phase 1: boletas con barcode → RUT/folio/total correcto sin OCR. ✅
- Phase 2: boletas sin barcode → headers OK; totales reconcilian. ✅
- Phase 3: ítems suman al total (dentro de tolerancia) o van a review. ✅
- Phase 4: `v_monthly_spend_by_category` devuelve números razonables. ✅ (vistas listas; aliases vacíos)
- Phase 5: boletas de baja confianza Tesseract → Gemini extrae todos los ítems. ✅
