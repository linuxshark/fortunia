# 02 — Chilean SII DTE & the TED PDF417 Barcode

This is the most important domain-specific insight of the whole project.

## DTE document types

Chilean tax documents are **DTEs** (Documentos Tributarios Electrónicos):

| Tipo | Document | Use |
|------|----------|-----|
| 39 | Boleta electrónica afecta | Consumer receipt (with IVA) |
| 41 | Boleta electrónica exenta | Consumer receipt (tax-exempt) |
| 33 | Factura electrónica afecta | B2B invoice (with IVA) |
| 34 | Factura electrónica exenta | B2B invoice (tax-exempt) |

Header fields (SII standard): RUT emisor + giro, RUT receptor, folio, fecha, `MntNeto`, `IVA` (tasa 19%), `MntExento`, `MntTotal`. Line items live in the `<Detalle>` block: `NmbItem`, `QtyItem`, `UnmdItem`, `PrcItem`, `MontoItem`.

## The TED (Timbre Electrónico DTE) — PDF417 barcode

Every printed DTE carries a **PDF417 2D barcode** ("timbre"). Its payload is a compact XML:

```xml
<TED version="1.0">
  <DD>
    <RE>76.xxx.xxx-x</RE>   <!-- RUT emisor -->
    <TD>39</TD>             <!-- tipo DTE -->
    <F>123456</F>          <!-- folio -->
    <FE>2026-06-12</FE>     <!-- fecha emisión -->
    <RR>66.666.666-6</RR>  <!-- RUT receptor -->
    <RSR>NOMBRE EMISOR</RSR><!-- razón social receptor (≤40 chars) -->
    <MNT>19990</MNT>        <!-- monto total (CLP integer) -->
    <IT1>PRIMER ITEM</IT1>  <!-- 1st item description (≤40 chars) -->
    <CAF>...</CAF>          <!-- SII folio authorization + public key -->
    <TSTED>...</TSTED>      <!-- stamping timestamp -->
  </DD>
  <FRMT algoritmo="SHA1withRSA">...base64 signature...</FRMT>
</TED>
```

### What the TED gives you — for free, OCR-error-free, RSA-signed
- RUT emisor (`RE`), RUT receptor (`RR`), doc type (`TD`), **folio (`F`)**, fecha (`FE`), merchant (`RSR`), **grand total (`MNT`)**, first item only (`IT1`).
- `folio + RUT emisor` = the **SII-guaranteed unique identity** of the document → perfect dedup key.
- `MNT` = a **ground-truth checksum** to validate OCR line items.

### What the TED does NOT contain — the hard limit
- **No per-line items.** No qty, no unit prices, no per-line totals, no IVA/neto split. Only `IT1` (one item description) + `MNT` (total).

> Therefore: **barcode and OCR are complementary, never alternatives.** Barcode → verified header + total. OCR → the itemized table.

## Decoding the barcode locally (token-free)

| Library | Decodes PDF417? | License | Verdict |
|---------|-----------------|---------|---------|
| **zxing-cpp** (`import zxingcpp`) | **Yes** (+ Compact/Micro) | Apache-2.0 | **Use this.** Native Apple-Silicon wheels |
| pdf417decoder (pure Python) | Yes | **CPOL** (review) | Fallback cross-check on hard photos |
| **pyzbar / zbar** | **NO** | MIT / LGPL | ⚠️ Cannot read PDF417 — only QR/EAN/Code128/etc. Use **only** for a bonus QR verification code |

```python
import cv2, zxingcpp
results = zxingcpp.read_barcodes(cv2.imread(path))
for r in results:
    if r.format == zxingcpp.BarcodeFormat.PDF417:
        ted_xml = r.text   # parse <TED>/<DD> with lxml/ElementTree
```

## If you ever have the full DTE XML

If the user forwards the SII email attachment or downloads the XML from sii.cl, parse it with **`cl-sii`** (MIT, v0.78.0 2026-06): `parse_dte_xml()` for the header + the `<Detalle>` block for **lossless line items with no OCR at all**. Note: `cl-sii` parses the *full* DTE XML, not the compact TED-from-barcode — parse the TED yourself with `lxml`.

## Practical decode flow

1. Keep a lightly-processed grayscale/sharpened copy (PDF417 decoders dislike hard-binarized input).
2. Locate + crop the PDF417 region, decode with `zxing-cpp`.
3. On success → parse `<DD>` → populate verified header, flag `header_source='ted'`.
4. On failure (blurry/warped/low-res photo) → degrade gracefully to pure OCR header; optionally prompt the user via the bot to retake.
5. Always cross-check OCR'd total vs TED `MNT`.

## RUT validation (free, deterministic)

RUT format `XX.XXX.XXX-D` with a **mod-11 check digit**. Validate it locally to reject OCR garbling:

```
body reversed, multiply by cycle 2,3,4,5,6,7; sum; dv = 11 - (sum % 11)
11 -> '0', 10 -> 'K', else str(dv)
```
