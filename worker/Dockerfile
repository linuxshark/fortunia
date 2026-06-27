# Containerized OCR worker. Debian slim = native arm64 wheels (avoid alpine/musl).
FROM python:3.12-slim-bookworm

# Tesseract + Spanish data; libGL/glib for OpenCV; zbar for optional QR
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-spa \
      libgl1 \
      libglib2.0-0 \
      libzbar0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV IMAGE_STORE=/app/data/images
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
