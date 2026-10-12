"""Application configuration with fail-fast validation using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for NUST LMS Helper."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    APP_ENV: Literal["development", "production", "testing"] = "development"
    APP_SECRET: str = Field(
        default="change-me-to-a-32-byte-hex-or-base64-random-secret",
        description="Secret key used for HMAC session tokens and signing",
    )
    FERNET_KEY: str = Field(
        default="",
        description="Fernet URL-safe base64-encoded 32-byte key for encrypting LMS credentials",
    )
    SESSION_COOKIE_NAME: str = "__Host-session"
    CSRF_COOKIE_NAME: str = "__Host-csrf"
    SECURE_COOKIES: bool = False

    # Database & Cache
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nust_lms_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM Engine (Groq Cloud)
    GROQ_API_KEY: str = Field(
        default="",
        description="API key for Groq Cloud (replaces Anthropic Claude)",
    )
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_PARSER_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MAX_TOKENS_PER_JOB: int = 100000

    # NUST LMS Configuration (Moodle)
    LMS_BASE_URL: str = "https://lms.nust.edu.pk"
    LMS_LOGIN_URL: str = "https://lms.nust.edu.pk/login/index.php"
    LMS_RATE_LIMIT_DELAY_SECONDS: float = 2.0

    # Sandbox execution limits
    SANDBOX_TIMEOUT_SECONDS: int = 60
    SANDBOX_MAX_MEMORY_MB: int = 512

    @field_validator("GROQ_API_KEY")
    @classmethod
    def validate_groq_key(cls, v: str, info) -> str:
        """Validate Groq API Key formatting when in production."""
        values = info.data
        if values.get("APP_ENV") == "production" and not v:
            raise ValueError("GROQ_API_KEY must be provided in production mode")
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
