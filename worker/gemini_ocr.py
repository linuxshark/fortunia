"""Gemini Vision fallback para extracción cuando Tesseract falla o tiene baja confianza.

Usa Gemini (multimodal) para extraer el JSON completo de la boleta.
Devuelve el mismo dict que extract_from_bytes para ser drop-in replacement.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import date

from normalize import parse_date
from validate import validate

# gemini-2.5-flash y gemini-2.5-flash-lite fueron retirados por Google para cuentas
# nuevas (404 "no longer available to new users") — verificado en vivo 2026-07-14.
# Mismo orden que agents.defaults.model en openclaw.json para consistencia.
_MODEL_CANDIDATES = (
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
)


_PROMPT = """\
Eres un parser experto de boletas electrónicas chilenas (SII). Analiza esta imagen de boleta \
y extrae TODOS los datos.

Devuelve ÚNICAMENTE JSON válido con esta estructura exacta. \
Sin texto adicional, sin bloques de código markdown, solo el JSON:

{
  "merchant_name": "nombre del comercio o null",
  "rut_emisor": "XX.XXX.XXX-X o null",
  "folio": "número de folio como string o null",
  "issued_date": "YYYY-MM-DD o null",
  "total": número entero en CLP o null,
  "net": número entero en CLP o null,
  "tax": número entero en CLP o null,
  "household_category": "una de la lista de abajo, o null",
  "items": [
    {
      "name": "nombre del producto",
      "qty": cantidad como número,
      "unit_price": precio unitario como entero CLP,
      "line_total": total de línea como entero CLP
    }
  ]
}

Reglas críticas:
- Precios en pesos chilenos CLP, SIEMPRE enteros sin decimales
- El PUNTO es separador de miles: 1.990 = 1990 pesos, 12.500 = 12500 pesos
- Extrae ABSOLUTAMENTE TODOS los ítems visibles, incluso si el texto está parcialmente ilegible
- Para ítems con cantidad: ej "2X1.850 MANTEQUILLA 3.700" → qty=2, unit_price=1850, line_total=3700
- Si qty > 1 y solo ves el total, calcula unit_price = line_total / qty
- Ignora líneas de TOTAL, SUBTOTAL, IVA, NETO, VUELTO — esas NO son ítems
- Si un campo no es legible usa null, pero intenta extraer todos los ítems igual

household_category — clasifica el GASTO COMPARTIDO del hogar que representa esta boleta.
Devuelve EXACTAMENTE uno de estos nombres, o null si no encaja en ninguno:
  "Alimentos"     — supermercado, almacén, feria, compra de comida para la casa
  "Restaurantes"  — restaurant, comida rápida, delivery, café, bar
  "Gasolina"      — bencina, combustible, estación de servicio (Copec, Shell, etc.)
  "Agua", "Electricidad", "Internet", "GGCC" — cuentas/servicios del hogar
  "Arriendo", "Jardin", "Auto (cuota)", "Remesas", "TAG"
Regla: elige por el RUBRO del comercio, no por un ítem suelto. Una farmacia, ropa,
electrónica u otra compra que NO sea del hogar compartido → null.
"""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def gemini_extract(raw: bytes, source_image_path: str | None = None) -> dict:
    """Extrae datos de boleta usando Gemini Vision. Misma firma que extract_from_bytes."""
    from google import genai
    import PIL.Image

    from config import settings

    client = genai.Client(api_key=settings.gemini_api_key)
    img = PIL.Image.open(io.BytesIO(raw))

    used_model = None
    response = None
    last_error: Exception | None = None
    for model_name in _MODEL_CANDIDATES:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[_PROMPT, img],
            )
            used_model = model_name
            break
        except Exception as exc:  # noqa: BLE001 - probing candidates, next one may work
            last_error = exc
            continue

    if response is None:
        raise RuntimeError(
            f"All Gemini fallback candidates failed: {_MODEL_CANDIDATES}"
        ) from last_error

    raw_json = _strip_markdown(response.text)
    data = json.loads(raw_json)

    sha = hashlib.sha256(raw).hexdigest()

    # Normalizar ítems
    items: list[dict] = []
    for i, it in enumerate(data.get("items") or [], start=1):
        name = (it.get("name") or "").strip()
        if not name:
            continue
        unit_price = _to_int(it.get("unit_price"))
        line_total = _to_int(it.get("line_total")) or unit_price
        qty = max(1, int(it.get("qty") or 1))
        if not unit_price or unit_price <= 0:
            continue
        items.append({
            "line_no": i,
            "raw_text": name,
            "normalized_name": name,
            "category_id": None,
            "category_source": "unmatched",
            "qty": qty,
            "unit_price": unit_price,
            "line_total": line_total,
        })

    raw_total = _to_int(data.get("total"))
    raw_net   = _to_int(data.get("net"))
    raw_tax   = _to_int(data.get("tax"))

    issued = None
    if data.get("issued_date"):
        issued = parse_date(str(data["issued_date"]))
    if issued is None:
        issued = date.today()

    header = {
        "rut_emisor":    data.get("rut_emisor"),
        "rut_receptor":  None,
        "tipo_dte":      None,
        "doc_type":      "boleta",
        "folio":         str(data["folio"]) if data.get("folio") else None,
        "issued_date":   issued,
        "merchant_name": data.get("merchant_name"),
        "net":           raw_net,
        "tax":           raw_tax,
        "total":         raw_total,
        "ted_total":     None,
        "header_source": "gemini",
    }

    status, problems = validate(header, items)

    return {
        **header,
        "image_sha256":      sha,
        "source_image_path": source_image_path,
        "ocr_engine":        used_model,
        "ocr_confidence":    95.0,
        "ocr_raw_text":      raw_json,
        "line_items":        items,
        "validation_status": status,
        "problems":          problems,
        "ted_decoded":       False,
        "fund_category":     (data.get("household_category") or None),
    }


def _to_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
