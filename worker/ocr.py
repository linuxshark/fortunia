"""OCR via Tesseract (container-friendly, token-free).

Returns (raw_text, words, mean_conf). `words` carry bounding boxes for
positional line-item reconstruction (Phase 3). Apple Vision/PaddleOCR can be
plugged here later behind the same signature. See docs/03 Stage 3.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import settings


@dataclass
class Word:
    text: str
    conf: float
    x: int
    y: int
    w: int
    h: int
    line: int


def run_ocr(binary_image) -> tuple[str, list[Word], float]:
    import pytesseract
    from pytesseract import Output

    cfg = "--psm 4 --oem 1"
    lang = settings.tesseract_lang

    raw_text = pytesseract.image_to_string(binary_image, lang=lang, config=cfg)
    data = pytesseract.image_to_data(binary_image, lang=lang, config=cfg, output_type=Output.DICT)

    words: list[Word] = []
    confs: list[float] = []
    for i, txt in enumerate(data["text"]):
        if not txt or not txt.strip():
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf < 0:
            continue
        words.append(Word(
            text=txt.strip(), conf=conf,
            x=data["left"][i], y=data["top"][i],
            w=data["width"][i], h=data["height"][i],
            line=data["line_num"][i],
        ))
        confs.append(conf)

    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return raw_text, words, mean_conf
