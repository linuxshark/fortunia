"""Category classification rules."""

from typing import Optional, Tuple


# Category keywords cache (in real app, load from DB)
CATEGORY_KEYWORDS = {
    "Alimentación": [
        "supermercado", "super", "jumbo", "lider", "líder", "tottus", "unimarc",
        "santa isabel", "almuerzo", "cena", "desayuno", "sushi", "pizza",
        "restaurant", "restaurante", "café", "cafe", "panadería", "panaderia", "feria"
    ],
    "Transporte": [
        "uber", "didi", "cabify", "taxi", "metro", "bencina", "combustible",
        "peaje", "tag", "bip", "copec", "shell", "enex"
    ],
    "Salud": [
        "farmacia", "farmacias ahumada", "cruz verde", "salcobrand", "remedio",
        "medicamento", "doctor", "médico", "medico", "clínica", "clinica",
        "dental", "isapre", "fonasa"
    ],
    "Hogar": [
        "arriendo", "dividendo", "luz", "enel", "cge", "agua", "aguas andinas",
        "gas", "lipigas", "internet", "vtr", "movistar", "entel", "condominio",
        "gastos comunes"
    ],
    "Entretenimiento": [
        "netflix", "spotify", "disney", "hbo", "prime video", "cine", "cinemark",
        "hoyts", "concierto", "teatro", "steam", "playstation"
    ],
    "Ropa": [
        "ropa", "zapatos", "zapatillas", "camisa", "vestido", "h&m", "zara",
        "falabella", "paris", "ripley", "hites"
    ],
}


def classify_category(text: str) -> Tuple[Optional[str], float]:
    """
    Classify expense category from text.

    Returns:
        (category_name, confidence) or (None, 0.0) if no match
    """
    if not text:
        return None, 0.0

    text_lower = text.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                # Confidence based on keyword specificity
                confidence = min(0.5 + (len(keyword) / 50), 0.95)
                return category, confidence

    return None, 0.0
