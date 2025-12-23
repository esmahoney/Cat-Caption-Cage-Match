"""
Application configuration via environment variables.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App settings
    app_name: str = "Cat Caption Cage Match API"
    app_secret: str = "dev-secret-change-in-production"
    debug: bool = False
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]
    
    # Storage backend: "memory" for in-memory, "sql" for database
    storage_type: Literal["memory", "sql"] = "memory"
    
    # Database (only used when storage_type="sql")
    database_url: str = "sqlite+aiosqlite:///./dev.db"  # Default for dev
    
    # LLM Provider
    llm_provider: Literal["groq", "gemini", "fake"] = "fake"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    
    # TheCatAPI
    thecatapi_key: str = ""
    
    # Game settings
    default_rounds: int = 3
    max_caption_words: int = 15
    session_expiry_hours: int = 2
    # Note: round timers are a non-goal for v2
    
    # Rate limiting
    rate_limit_joins_per_minute: int = 10
    rate_limit_captions_per_minute: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

