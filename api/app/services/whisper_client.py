"""Client for Whisper STT service."""

import httpx

from app.config import Settings


class WhisperClient:
    """HTTP client for whisper-service."""

    def __init__(self, url: str = None):
        """Initialize Whisper client."""
        self.url = url or Settings().whisper_url
        self.timeout = 60
        self.retries = 2

    async def transcribe(
        self, audio_bytes: bytes, language: str = "es", task: str = "transcribe"
    ) -> dict:
        """
        Transcribe audio via whisper-service.

        Args:
            audio_bytes: Audio file content
            language: Language code (default: es for Spanish)
            task: 'transcribe' or 'translate' (default: transcribe)

        Returns:
            {
                "text": "transcribed text",
                "language": "es",
                ...
            }
        """
        for attempt in range(self.retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.url}/asr",
                        params={
                            "task": task,
                            "language": language,
                            "output": "txt",
                        },
                        files={"audio_file": ("audio.mp3", audio_bytes, "audio/mpeg")},
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPError as e:
                if attempt == self.retries - 1:
                    raise
                continue
            except Exception as e:
                raise ValueError(f"Whisper service error: {str(e)}")

        raise ValueError("Whisper service failed after retries")
