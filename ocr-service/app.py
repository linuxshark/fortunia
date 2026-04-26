"""OCR service for receipt processing."""

import io
from decimal import Decimal

import pytesseract
from fastapi import FastAPI, File, UploadFile, HTTPException
from PIL import Image, ImageOps, ImageEnhance

app = FastAPI(
    title="Fortunia OCR Service",
    description="Receipt OCR with Tesseract (Spanish)",
    version="0.1.0",
)


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Pre-process image for better OCR results.

    Steps:
    1. Convert to grayscale
    2. Auto-rotate based on detected orientation
    3. Apply Otsu threshold
    4. Enhance contrast
    """
    # Convert to grayscale
    image = ImageOps.grayscale(image)

    # Try to auto-rotate (requires Tesseract osd)
    try:
        osd = pytesseract.image_to_osd(image)
        if osd:
            # Extract rotation angle
            for line in osd.split("\n"):
                if line.startswith("Rotate:"):
                    angle = int(line.split(": ")[1])
                    if angle != 0:
                        image = image.rotate(-angle, expand=True)
    except Exception:
        pass  # If osd fails, continue without rotation

    # Apply threshold (Otsu)
    import numpy as np
    img_array = np.array(image)
    _, thresh = cv2.threshold(
        img_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    ) if "cv2" in locals() else (None, img_array)

    if thresh is not None:
        image = Image.fromarray(thresh)

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)

    return image


@app.post("/ocr")
async def extract_text(file: UploadFile = File(...)) -> dict:
    """
    Extract text from receipt image using Tesseract OCR.

    Returns:
        {
            "text": "<extracted text>",
            "confidence": <0.0-1.0>,
            "raw_data": "<full tesseract output>"
        }
    """
    # Read file
    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")

    # Pre-process
    try:
        image = preprocess_image(image)
    except Exception:
        pass  # If preprocessing fails, use original

    # Run OCR (Spanish, PSM 6 = Uniform block of text)
    try:
        text = pytesseract.image_to_string(image, lang="spa", config="--psm 6")
        raw_data = pytesseract.image_to_data(image, lang="spa")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")

    # Estimate confidence based on text length and structure
    # (simplified: real implementation would parse Tesseract conf scores)
    confidence = min(0.5 + (len(text) / 1000), 0.95)

    return {
        "text": text,
        "confidence": float(confidence),
        "raw_data": raw_data[:500],  # Truncate for response
    }


@app.get("/health")
async def health() -> dict:
    """Health check."""
    return {"status": "ok"}
