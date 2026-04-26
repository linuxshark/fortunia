"""HTTP client for Fortunia API (for Kraken integration)."""

import os
from typing import Optional

import httpx


class FortunaClient:
    """HTTP client to communicate with Fortunia API."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 10,
    ):
        """
        Initialize Fortunia client.

        Args:
            api_url: Base URL of Fortunia API (default: from FORTUNA_API_URL env)
            api_key: API key for authentication (default: from FORTUNA_API_KEY env)
            timeout: Request timeout in seconds (default: 10)
        """
        self.api_url = api_url or os.environ.get("FORTUNA_API_URL", "http://localhost:8000")
        self.api_key = api_key or os.environ.get("FORTUNA_API_KEY", "")
        self.timeout = timeout

    async def check_intent(self, text: str) -> dict:
        """
        Check if text contains financial intent.

        Args:
            text: Message to analyze

        Returns:
            {
                "is_finance": bool,
                "confidence": float,
                "needs_llm": bool,
                "reason": str
            }
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_url}/ingest/intent/check",
                json={"text": text},
                headers={"X-Internal-Key": self.api_key},
            )
            response.raise_for_status()
            return response.json()

    async def ingest_text(
        self,
        text: str,
        user_id: str = "user",
        msg_id: Optional[str] = None,
    ) -> dict:
        """
        Ingest expense from text.

        Args:
            text: Expense text
            user_id: User identifier (default: "user")
            msg_id: Telegram message ID (optional)

        Returns:
            IngestResponse
        """
        data = {
            "text": text,
            "user_id": user_id,
        }
        if msg_id:
            data["msg_id"] = msg_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_url}/ingest/text",
                data=data,
                headers={"X-Internal-Key": self.api_key},
            )
            response.raise_for_status()
            return response.json()

    async def ingest_image(
        self,
        image_bytes: bytes,
        user_id: str = "user",
        caption: Optional[str] = None,
    ) -> dict:
        """
        Ingest expense from receipt image.

        Args:
            image_bytes: Image file content
            user_id: User identifier (default: "user")
            caption: Image caption (optional)

        Returns:
            IngestResponse
        """
        data = {
            "user_id": user_id,
        }
        if caption:
            data["caption"] = caption

        files = {
            "file": ("receipt.jpg", image_bytes, "image/jpeg"),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_url}/ingest/image",
                data=data,
                files=files,
                headers={"X-Internal-Key": self.api_key},
            )
            response.raise_for_status()
            return response.json()

    async def ingest_audio(
        self,
        audio_bytes: bytes,
        user_id: str = "user",
    ) -> dict:
        """
        Ingest expense from audio.

        Args:
            audio_bytes: Audio file content
            user_id: User identifier (default: "user")

        Returns:
            IngestResponse
        """
        files = {
            "file": ("audio.mp3", audio_bytes, "audio/mpeg"),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_url}/ingest/audio",
                data={"user_id": user_id},
                files=files,
                headers={"X-Internal-Key": self.api_key},
            )
            response.raise_for_status()
            return response.json()


# Convenience async functions for direct use
async def check_intent(text: str) -> dict:
    """Check intent using default client."""
    client = FortunaClient()
    return await client.check_intent(text)


async def ingest_text(text: str, user_id: str = "user") -> dict:
    """Ingest text using default client."""
    client = FortunaClient()
    return await client.ingest_text(text, user_id)
