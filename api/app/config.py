"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    database_url: str
    internal_api_key: str
    default_currency: str = "CLP"
    default_user_id: str = "user"
    log_level: str = "INFO"
    ocr_url: str = "http://ocr-service:8001"
    whisper_url: str = "http://whisper-service:9000"

    class Config:
        env_file = ".env"
        case_sensitive = False
