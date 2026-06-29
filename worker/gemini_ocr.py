"""Gemini Vision fallback para extracción cuando Tesseract falla o tiene baja confianza.

Usa gemini-1.5-flash (multimodal) para extraer el JSON completo de la boleta.
Devuelve el mismo dict que extract_from_bytes para ser drop-in replacement.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re

from normalize import parse_date
from validate import validate


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
"""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def gemini_extract(raw: bytes, source_image_path: str | None = None) -> dict:
    """Extrae datos de boleta usando Gemini Vision. Misma firma que extract_from_bytes."""
    import google.generativeai as genai
    import PIL.Image

    from config import settings

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    img = PIL.Image.open(io.BytesIO(raw))
    response = model.generate_content([_PROMPT, img])

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
        "ocr_engine":        "gemini-1.5-flash",
        "ocr_confidence":    95.0,
        "ocr_raw_text":      raw_json,
        "line_items":        items,
        "validation_status": status,
        "problems":          problems,
        "ted_decoded":       False,
    }


def _to_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
