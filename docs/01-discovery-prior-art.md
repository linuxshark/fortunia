# 01 — Discovery: Prior Art & Tool Survey

Survey of existing open-source work for **token-free, offline** receipt/invoice parsing in Python, targeting Chilean SII boletas on a Mac mini (Apple Silicon). Every tool's **license and maintenance status was adversarially verified** against PyPI + GitHub (verification date 2026-06-27); all 12 high-relevance claims came back **confirmed**.

> Bottom line: there is **no** off-the-shelf OSS tool that reliably extracts grocery line items (item, qty, unit price, line total) from arbitrary boleta photos. The proven architecture is **OCR engine → custom rule/positional extractor**, optionally augmented with per-merchant templates and (later) a fine-tuned local model.

---

## 1. Receipt/invoice parsing libraries

| Tool | What | License | Maintained | Relevance | Verdict |
|------|------|---------|-----------|-----------|---------|
| **invoice2data** (invoice-x) | Template-based (YAML) field + line-item extraction; pluggable text backends; outputs JSON/CSV/XML | MIT | **Active** — v1.0.0 (2026-06-23) | **High** | ✅ confirmed |
| receipt-parser (mre) + forks | Fuzzy supermarket-receipt parser (Tesseract); shop/date/total only | Apache-2.0 | Stale (2015 origin) | Medium | reference only |
| Donut (clovaai) | OCR-free transformer → JSON incl. line items; CORD-pretrained | MIT | Model active on HF; core repo stale (2022) | Medium | Phase 5 candidate |
| docTR (mindee) | Two-stage OCR → hierarchical doc (word boxes) + KIE | Apache-2.0 | **Active** — v1.0.1 (2026-02) | High | ✅ confirmed |
| PaddleOCR | Full OCR toolkit; PP-OCRv6 + PP-Structure (tables/cells) | Apache-2.0 | **Active** — v3.7.0 (2026-06), Apple-Silicon optimized | High | ✅ confirmed |
| EasyOCR | Ready-to-use OCR, 80+ langs; OCR only | Apache-2.0 | Moderately active | Medium | fallback OCR |
| OCRmyPDF | Adds OCR text layer to PDFs/images (Tesseract) | MPL-2.0 | Active — v17.4.1 (2026-04) | Medium | optional preproc |
| Camelot | PDF table extraction → DataFrame | MIT | Active — v2.0.0 (2026-06) | Medium | digital-PDF branch |
| Tabula / tabula-py | PDF table extraction (needs Java) | MIT | Active | Low | skip (JVM dep) |

**Key takeaways**
- `invoice2data` is the most mature **template** extractor — great for recurring fixed-layout merchants, weak on arbitrary photos. Keep its optional "AI fallback" **disabled** to honor the no-token rule.
- Camelot/Tabula only help on **digital text PDFs** (emailed facturas), useless on photos without a prior OCR-to-PDF step.
- receipt-parser is the closest in *intent* (supermarket receipts) but does **not** do line items and is stale — borrow ideas (fuzzy store-name matching, total detection), don't depend on it.

---

## 2. OCR engines (local, offline, Apple Silicon)

| Engine | Spanish | Noisy-photo robustness | Speed (M-series) | Install friction | License | Relevance |
|--------|---------|------------------------|------------------|------------------|---------|-----------|
| **Apple Vision** via `ocrmac` | es-ES/es-CL | **Best** (Live Text engine) | ~130–210 ms/img (Neural Engine) | **Near-zero** (`pip install ocrmac`) | MIT wrapper / proprietary OS | **High (primary)** |
| **PaddleOCR** (PP-OCRv5/v6) | 46 Latin incl. es | Strong; angle-robust | Fast (M4 optimized) | **High** (paddlepaddle wheels on ARM) | Apache-2.0 | **High (fallback)** |
| EasyOCR | es | Medium | Slower on CPU | Low (pulls torch) | Apache-2.0 | Medium |
| **Tesseract** (`-l spa`) | spa pack | **Most sensitive** to noise/skew | Light/fast | Low (`brew`) | Apache-2.0 | Medium (last resort / container path) |
| docTR | Latin charset | Worst on crumpled photos | PyTorch CPU/MPS | Medium | Apache-2.0 | Low |

**Recommendation:** Apple Vision (primary) → PaddleOCR (fallback) → Tesseract (ultra-light last resort, usable inside a Linux container). All are 100% offline / token-free.

> Architectural consequence: Apple Vision is **macOS-only**, so the OCR worker must run as a **host process**, not inside a Linux container. Only structured rows cross into the containerized Postgres.

---

## 3. Structured extraction (rule-based, no LLM)

| Technique / lib | Role | License | Notes |
|-----------------|------|---------|-------|
| **invoice2data `lines` parser** | Declarative line-item extraction (start/end block, first_line/line/last_line for wrapped items, skip_line, type coercion) | MIT | Per-merchant templates; regex over linearized text — loses column geometry |
| **Positional / bbox reconstruction** (`pytesseract image_to_data` or Apple Vision boxes) | Cluster words into rows by *y*, infer column *x*-bands → map name\|qty\|unit_price\|line_total | Apache-2.0 / MIT | **The robust path for photos** — survives wrapped names + column drift |
| **price-parser** | `Price.fromstring("$1.234,56", decimal_separator=",")` → Decimal | BSD-3-Clause | Pin separator for CLP (dot=thousands, usually no decimals) |
| **dateparser** | Spanish month names + DMY order | BSD-3-Clause | Pin `languages=['es']`, `DATE_ORDER='DMY'`, `STRICT_PARSING=True` |
| Per-merchant templates vs generic heuristics | Design pattern | N/A | **Hybrid wins**: generic SII-field heuristics + a few templates for top stores |

**Core insight:** Do **not** rely on single-line regex over linearized OCR text for line items — column misalignment and wrapped item names are the main failure mode. Use **positional reconstruction** from word bounding boxes. Header fields (RUT, folio, IVA 19%, TOTAL) *are* regex-friendly because SII format is highly regular.

---

## 4. Image preprocessing (the single biggest accuracy driver)

Order matters: **geometry first, photometry second.**

| Step | Library | Call |
|------|---------|------|
| Fix EXIF orientation | Pillow | `ImageOps.exif_transpose` (before any CV op) |
| Detect receipt quad | OpenCV | grayscale → `GaussianBlur` → `Canny` → `findContours` → `approxPolyDP` |
| Perspective warp | OpenCV | `getPerspectiveTransform` + `warpPerspective` (4-point) |
| Deskew residual | `sbrunner/deskew` (MIT, v1.6.x 2026) or `jdeskew` (FFT, ~0.07° err) | `determine_skew` / `get_angle` |
| Upscale to ~300 DPI | OpenCV | `resize(INTER_CUBIC)` — capitals ~30–33 px |
| Flatten lighting | OpenCV | `createCLAHE(clipLimit=2.0, tileGridSize=(8,8))` |
| Denoise | OpenCV | `fastNlMeansDenoising` / `medianBlur(3)` |
| **Binarize (LOCAL)** | scikit-image | `threshold_sauvola(window~25, k~0.2)` — **NOT global Otsu** |
| White border + DPI tag | OpenCV / Pillow | `copyMakeBorder(~10px)`; `save(dpi=(300,300))` |

**Highest-leverage choices:** local/adaptive thresholding (Sauvola) + CLAHE before binarization. Keep a *lightly-processed grayscale copy* for barcode decode and the *binarized copy* for OCR.

---

## 5. Local OCR-free / layout models (token-free, deferred)

All run from **local weights** = token-free in the API-billing sense; cost is local CPU/GPU/RAM.

| Model | What | License | MVP fit |
|-------|------|---------|---------|
| **Donut** (CORD-v2) | OCR-free → line-item JSON end-to-end (~200M) | MIT | **Phase 5** — best "beats regex" candidate; needs fine-tuning on ~hundreds of Chilean boletas; generative ⇒ must validate arithmetically |
| LayoutLMv3 | Token tagging over OCR words+boxes | **CC-BY-NC-SA (NonCommercial)** | ❌ license blocker if commercial |
| Table Transformer | Detects table rows/cols (no text) | MIT | Optional helper only |
| Ollama VLMs (Qwen2.5-VL, deepseek-ocr, MiniCPM-V…) | Prompt-driven local VLM | Varies | Heaviest/slowest on Mac mini, non-deterministic — overkill for fixed SII format; at most bootstrap Donut training labels |

**Decision:** Start deterministic (Apple Vision + positional/regex + barcode checksum). Escalate to a fine-tuned **Donut** only if line-item accuracy demands it. Keep extraction modular so the engine swaps without touching the bot or DB.
