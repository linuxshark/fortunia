# 07 — openclaw → Telegram → worker integration

openclaw corre en el Mac mini, recibe fotos de Telegram y hace POST al worker `/ocr`. El worker extrae, persiste y devuelve el JSON resumen. **No hay que cambiar openclaw** — el fallback a Gemini es transparente dentro del worker.

```
Telegram user ──foto──▶ openclaw (Mac mini)
                              │  descarga bytes de la foto
                              ▼
                    POST http://localhost:8002/ocr   (multipart "image")
                              │
                              ├─ Tesseract (siempre primero, gratis, offline)
                              │
                              └─ si confianza < 65% o ítems < 20:
                                    Gemini 1.5 Flash Vision (~$0.0002)
                              │
                              ▼  persiste en Postgres
                    JSON summary ──reply──▶ Telegram user
```

- El worker es idempotente: misma foto → `status: "duplicate"`.
- `ocr_engine` en la respuesta indica qué motor se usó: `"tesseract"` o `"gemini-2.5-flash"`.
- La API key de Gemini del worker (`GEMINI_API_KEY` en `.env`) es la misma que openclaw ya tiene configurada — son independientes, cada proceso la carga por su cuenta.

## Handler snippet (python-telegram-bot)

```python
import httpx

WORKER_URL = "http://localhost:8002/ocr"   # worker en el mismo host

async def on_photo(update, context):
    tg_file = await update.message.photo[-1].get_file()   # mayor resolución
    buf = await tg_file.download_to_memory()
    async with httpx.AsyncClient(timeout=90) as client:   # 90s: Gemini puede tardar
        r = await client.post(
            WORKER_URL,
            files={"image": ("receipt.jpg", buf.getvalue(), "image/jpeg")},
        )
    d = r.json()

    if d["status"] == "duplicate":
        await update.message.reply_text("Ya tenía esa boleta 👍")
        return

    engine_tag = " 🤖" if d.get("ocr_engine") == "gemini-2.5-flash" else ""
    lines = [
        f"🧾 {d.get('merchant') or 'Boleta'}{engine_tag}  (folio {d.get('folio') or '?'})",
        f"📅 {d.get('issued_date') or '?'}   💰 ${d.get('total') or '?':,}",
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
  "sha256": "a446e3…",
  "header_source": "ocr",
  "ted_decoded": false,
  "ocr_engine": "gemini-2.5-flash",
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

Campos clave:

| Campo | Valor | Significado |
|---|---|---|
| `status` | `"stored"` / `"duplicate"` | primera vez o repetida |
| `ocr_engine` | `"tesseract"` / `"gemini-2.5-flash"` | qué motor extrajo |
| `items` | entero | ítems de línea persistidos en `line_items` |
| `validation_status` | `"ok"` / `"review"` | si la aritmética cuadra |
| `problems` | lista de strings | qué falló en validación |

## Cuándo pide revisión (`validation_status: "review"`)

El worker guarda SIEMPRE la boleta (nada se pierde). `review` significa:
- `sum(line_totals) ≠ total` (OCR perdió algún ítem)
- `neto + IVA ≠ total`
- OCR total ≠ TED MNT (barcode vs texto difieren)

En estos casos openclaw puede pedir al usuario que reenvíe la foto o confirme manualmente.

## Test sin Telegram

```bash
# desde el host
curl -X POST http://localhost:8002/ocr -F "image=@/ruta/boleta.jpg"

# dentro del container
docker compose exec worker python scan.py data/images/<sha>.bin
```
