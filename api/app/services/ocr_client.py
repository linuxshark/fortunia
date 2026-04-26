"""Client for OCR service."""

from typing import Optional

import httpx

from app.config import Settings


class OCRClient:
    """HTTP client for ocr-service."""

    def __init__(self, url: str = None):
        """Initialize OCR client."""
        self.url = url or Settings().ocr_url
        self.timeout = 30
        self.retries = 2

    async def extract_text(self, image_bytes: bytes) -> dict:
        """
        Extract text from image via ocr-service.

        Args:
            image_bytes: Image file content

        Returns:
            {
                "text": "extracted text",
                "confidence": 0.85,
                "raw_data": "..."
            }
        """
        for attempt in range(self.retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.url}/ocr",
                        files={"file": ("receipt.jpg", image_bytes, "image/jpeg")},
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPError as e:
                if attempt == self.retries - 1:
                    raise
                continue
            except Exception as e:
                raise ValueError(f"OCR service error: {str(e)}")

        raise ValueError("OCR service failed after retries")
