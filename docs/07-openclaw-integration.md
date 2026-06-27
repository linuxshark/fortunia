# 07 — openclaw → Telegram → worker integration

openclaw already runs on the Mac mini and receives Telegram messages. When a
photo arrives, it downloads the bytes and POSTs them to the worker's `/ocr`
endpoint. The worker extracts + stores; openclaw replies with a summary.

```
Telegram user ──photo──▶ openclaw (Mac mini)
                              │  download photo bytes
                              ▼
                    POST http://worker:8000/ocr   (multipart "image")
                              │  preprocess → TED barcode → Tesseract → regex
                              ▼  persist to Postgres
                    JSON summary ──reply──▶ Telegram user
```

- Inside compose, the worker is reachable at `http://worker:8000`. If openclaw runs as a host process, use `http://localhost:8000`.
- The worker is idempotent: same photo → `status: "duplicate"`.

## Handler snippet (python-telegram-bot style)

```python
import httpx

WORKER_URL = "http://worker:8000/ocr"   # or http://localhost:8000/ocr from host

async def on_photo(update, context):
    tg_file = await update.message.photo[-1].get_file()      # highest resolution
    buf = await tg_file.download_to_memory()                 # BytesIO
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            WORKER_URL,
            files={"image": ("receipt.jpg", buf.getvalue(), "image/jpeg")},
        )
    d = r.json()

    if d["status"] == "duplicate":
        await update.message.reply_text("Ya tenía esa boleta 👍")
        return

    lines = [
        f"🧾 {d.get('merchant') or 'Boleta'}  (folio {d.get('folio') or '?'})",
        f"📅 {d.get('issued_date') or '?'}   💰 ${d.get('total') or '?'}",
        f"📦 {d['items']} ítems   ✓ {d['validation_status']}",
    ]
    if d["validation_status"] != "ok":
        lines.append("⚠️ revisar: " + "; ".join(d["problems"]))
    await update.message.reply_text("\n".join(lines))
```

## Response shape (`POST /ocr`)

```json
{
  "status": "stored",
  "receipt_id": 12,
  "sha256": "…",
  "header_source": "ted",
  "ted_decoded": true,
  "merchant": "SUPERMERCADO X",
  "rut_emisor": "76.123.456-7",
  "folio": "1234",
  "issued_date": "2026-06-12",
  "total": 19990,
  "items": 7,
  "validation_status": "ok",
  "problems": []
}
```

## Manual-review loop (Phase 3)

When `validation_status` is `review` (e.g. line items don't sum to the total, or
OCR total ≠ TED `MNT`), openclaw should ask the user to confirm/correct or
retake the photo, rather than trusting the row. The receipt is still stored with
`validation_status='review'` so nothing is lost.

## Without Telegram (test the extraction directly)

```bash
# CLI, inside the worker container:
docker compose exec worker python scan.py data/images/<sha>.bin
# or POST a file from the host:
curl -F image=@/tmp/boleta.jpg http://localhost:8000/ocr
```
