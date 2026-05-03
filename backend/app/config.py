"""
Centralized configuration loaded from environment variables / .env file.

Avoids hardcoding any LLM keys, paths, or runtime parameters. Every module
imports `settings` from here instead of touching `os.environ` directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ---
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    # --- App ---
    app_env: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    # --- Storage ---
    database_url: str = Field(default="sqlite:///./data/db/analyst.db")
    upload_dir: str = Field(default="./data/uploads")
    vector_store_dir: str = Field(default="./data/vector_store")

    # --- Agent ---
    agent_max_iterations: int = Field(default=6)
    agent_max_fix_attempts: int = Field(default=3)

    # --- CORS ---
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    @field_validator("cors_origins")
    @classmethod
    def _strip_cors(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        """Create runtime directories if they do not exist."""
        for p in (self.upload_dir, self.vector_store_dir):
            Path(p).mkdir(parents=True, exist_ok=True)
        # SQLite file directory
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.replace("sqlite:///", "", 1))
            db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Use this everywhere instead of constructing Settings()."""
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()
