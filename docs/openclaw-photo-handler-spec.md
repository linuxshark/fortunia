# Spec: agregar handler de fotos de boletas en openclaw

**Objetivo:** cuando el bot de Telegram recibe una foto, POST de los bytes al worker fortunia (`http://localhost:8002/ocr`) y responde al usuario con el resumen de la boleta.

Este documento es una especificación de implementación. Ejecútalo en una sesión de Claude apuntando al repo de openclaw.

---

## Contexto del worker

- Worker fortunia corre en `http://localhost:8002` (mismo Mac mini, docker-compose)
- Endpoint: `POST /ocr` — multipart form-data, campo `"image"`, cualquier imagen JPEG/PNG
- Respuesta JSON:

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

- `status: "duplicate"` si la misma foto ya fue procesada antes
- `validation_status: "ok"` o `"review"` (aritmética no cuadra)
- `ocr_engine`: `"tesseract"` o `"gemini-1.5-flash"`
- Timeout recomendado: **90 segundos** (Gemini puede tardar)

---

## Tarea de implementación

### 1. Verificar dependencia `httpx`

El handler usa `httpx` para el POST async. Verificar que openclaw ya lo tiene:

```bash
pip show httpx   # o: grep httpx requirements.txt
```

Si no está: `pip install httpx` y agregar a `requirements.txt`.

---

### 2. Agregar el handler de fotos

En el archivo principal del bot (buscar donde están los otros handlers, típicamente `main.py`, `bot.py`, o `handlers.py`), agregar:

```python
import httpx

FORTUNIA_URL = "http://localhost:8002/ocr"

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe foto de Telegram, la manda al worker de boletas, responde resumen."""
    # Descargar la foto en la resolución más alta
    tg_file = await update.message.photo[-1].get_file()
    buf = await tg_file.download_as_bytearray()

    await update.message.reply_text("Procesando boleta...")

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                FORTUNIA_URL,
                files={"image": ("receipt.jpg", bytes(buf), "image/jpeg")},
            )
        r.raise_for_status()
        d = r.json()
    except httpx.TimeoutException:
        await update.message.reply_text("El worker tardó demasiado. Intenta de nuevo.")
        return
    except Exception as exc:
        await update.message.reply_text(f"Error contactando worker: {exc}")
        return

    if d["status"] == "duplicate":
        await update.message.reply_text("Ya tenía esa boleta registrada.")
        return

    engine_tag = " (Gemini)" if d.get("ocr_engine") == "gemini-1.5-flash" else ""
    merchant = d.get("merchant") or "Comercio desconocido"
    total = d.get("total")
    items = d.get("items", 0)
    date = d.get("issued_date") or "?"
    v_status = d.get("validation_status", "?")
    problems = d.get("problems", [])

    lines = [
        f"Boleta registrada{engine_tag}",
        f"Comercio: {merchant}",
        f"Fecha: {date}",
        f"Total: ${total:,}" if total else "Total: ?",
        f"Ítems: {items}",
        f"Validación: {v_status}",
    ]
    if problems:
        lines.append("Revisar: " + "; ".join(problems[:3]))

    await update.message.reply_text("\n".join(lines))
```

---

### 3. Registrar el handler

En el bloque donde se registran los handlers (buscar `application.add_handler`):

```python
from telegram.ext import MessageHandler, filters

# Agregar junto a los otros handlers:
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
```

**Nota sobre filtros:** `filters.PHOTO` captura TODAS las fotos. Si openclaw ya maneja fotos para otros propósitos, usar un filtro más específico o agregar lógica dentro del handler para distinguir (por ejemplo, verificar que el usuario haya enviado un caption como "boleta").

---

### 4. Verificar que el worker esté corriendo

Antes de reiniciar openclaw, confirmar que fortunia está up:

```bash
curl http://localhost:8002/health
# esperado: {"ok":true,"db":true}
```

Si no responde: ir al repo `fortunia` y ejecutar `make deploy`.

---

### 5. Test end-to-end

1. Reiniciar openclaw con el nuevo handler
2. Abrir Telegram → enviar una foto de boleta al bot
3. El bot debería responder con el resumen en ~5-10 segundos (Tesseract) o ~15-30 segundos (Gemini)
4. Verificar en la DB:

```bash
cd ~/fortunia   # o donde esté el repo
make receipts   # muestra las últimas 20 boletas
make items      # muestra ítems de la última boleta
```

---

## Troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| `Connection refused localhost:8002` | docker-compose no levantado | `make deploy` en repo fortunia |
| Timeout 90s | Gemini tardando o sin clave | Verificar `GEMINI_API_KEY` en `.env` |
| `status: "review"` | OCR perdió ítems, aritmética no cuadra | Normal en fotos borrosas; datos guardados igual |
| Bot no responde a fotos | Handler no registrado | Verificar `application.add_handler` |
| `status: "duplicate"` | Foto ya enviada antes | OK, es idempotencia por diseño |
