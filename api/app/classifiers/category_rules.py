"""Category classification rules."""

from typing import Optional, Tuple


CATEGORY_KEYWORDS: dict[str, dict] = {
    "Comida": {
        "applicable_to": "expense",
        "keywords": [
            "supermercado", "jumbo", "lider", "líder", "tottus", "unimarc",
            "santa isabel", "almacén", "feria", "minimarket",
        ],
    },
    "Restaurantes": {
        "applicable_to": "expense",
        "keywords": [
            "restaurant", "restaurante", "sushi", "pizza", "café", "cafe",
            "almuerzo", "cena", "panadería", "panaderia", "mcdonalds",
            "burger", "sandwichería",
        ],
    },
    "Transporte": {
        "applicable_to": "expense",
        "keywords": ["uber", "didi", "cabify", "taxi", "metro", "bip", "tag", "peaje"],
    },
    "Combustible": {
        "applicable_to": "expense",
        "keywords": ["bencina", "combustible", "copec", "shell", "enex", "petróleo", "petroleo"],
    },
    "Salud": {
        "applicable_to": "expense",
        "keywords": [
            "farmacia", "farmacias ahumada", "cruz verde", "salcobrand", "remedio",
            "medicamento", "doctor", "médico", "medico", "clínica", "clinica",
            "dental", "isapre", "fonasa",
        ],
    },
    "Hogar": {
        "applicable_to": "expense",
        "keywords": [
            "arriendo", "dividendo", "luz", "enel", "cge", "agua", "aguas andinas",
            "gas", "lipigas", "internet", "vtr", "movistar", "entel", "condominio",
            "gastos comunes",
        ],
    },
    "Entretenimiento": {
        "applicable_to": "expense",
        "keywords": [
            "netflix", "spotify", "disney", "hbo", "prime video", "cine", "cinemark",
            "hoyts", "concierto", "teatro", "steam", "playstation",
        ],
    },
    "Ropa": {
        "applicable_to": "expense",
        "keywords": [
            "ropa", "zapatos", "zapatillas", "camisa", "vestido",
            "h&m", "zara", "falabella", "paris", "ripley", "hites",
        ],
    },
    "Sueldo": {
        "applicable_to": "income",
        "keywords": ["sueldo", "salario", "remuneración", "remuneracion"],
    },
    "Otros Ingresos": {
        "applicable_to": "income",
        "keywords": ["freelance", "honorario", "transferencia recibida", "ingreso", "pago recibido"],
    },
    "Otros": {
        "applicable_to": "both",
        "keywords": [],
    },
}


def classify_category(
    text: str,
    transaction_type: str = "expense",
) -> Tuple[Optional[str], float]:
    """
    Classify category from text, filtered by transaction_type.

    Args:
        text: Raw user text
        transaction_type: "expense" or "income"

    Returns:
        (category_name, confidence) or (None, 0.0) if no match
    """
    if not text:
        return None, 0.0

    text_lower = text.lower()

    for category, meta in CATEGORY_KEYWORDS.items():
        applicable = meta["applicable_to"]
        if applicable != "both" and applicable != transaction_type:
            continue
        for keyword in meta["keywords"]:
            if keyword in text_lower:
                confidence = min(0.5 + (len(keyword) / 50), 0.95)
                return category, confidence

    return None, 0.0
