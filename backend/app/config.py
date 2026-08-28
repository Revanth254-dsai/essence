"""Central configuration. This is the fix for the v2 bug where .env was never loaded."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- database ---
    database_url: str = "postgresql+asyncpg://summarizer:summarizer@localhost:5432/summarizer"

    # --- llm ---
    llm_backend: Literal["groq", "ollama", "openai"] = "groq"

    groq_api_key: str = ""
    # llama-3.3-70b-versatile was deprecated by Groq on 2026-06-17 and is now
    # decommissioned (404 model_not_found). openai/gpt-oss-120b is the
    # recommended replacement; openai/gpt-oss-20b is the cheaper option.
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3"

    # --- ingestion limits ---
    max_download_bytes: int = 10 * 1024 * 1024   # 10 MB hard cap
    request_timeout_s: float = 20.0
    llm_timeout_s: float = 120.0
    max_source_chars: int = 60_000               # cap before chunking
    allow_private_hosts: bool = False            # SSRF guard; True only for local dev

    # --- app ---
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()