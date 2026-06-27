"""Image preprocessing (OpenCV + Pillow). geometry-light -> photometry.

MVP: EXIF fix -> grayscale -> upscale-if-small -> CLAHE -> denoise ->
Sauvola binarize (adaptive-Otsu fallback). Returns (gray_for_barcode,
binary_for_ocr) as numpy uint8. 4-point warp / deskew are TODO Phase 1.5.
All CPU, offline, token-free. See docs/01 §4.
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image, ImageOps


def _load_gray(raw: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)          # fix phone orientation FIRST
    img = img.convert("L")                       # grayscale
    return np.array(img)


def preprocess(raw: bytes) -> tuple[np.ndarray, np.ndarray]:
    gray = _load_gray(raw)

    # upscale small captures toward Tesseract's ~300 DPI sweet spot
    h, w = gray.shape[:2]
    if max(h, w) < 1600:
        scale = 1600 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # flatten lighting + denoise
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    eq = cv2.fastNlMeansDenoising(eq, h=10)

    # local binarization (Sauvola); fallback adaptive Otsu
    try:
        from skimage.filters import threshold_sauvola  # type: ignore
        t = threshold_sauvola(eq, window_size=25, k=0.2)
        binary = (eq > t).astype(np.uint8) * 255
    except Exception:
        binary = cv2.adaptiveThreshold(
            eq, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
        )

    binary = cv2.copyMakeBorder(binary, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    return eq, binary
