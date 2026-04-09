"""Typed application configuration.

Centralises environment variable parsing and defaults so modules do not read
process environment directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    firecrawl_api_key: str = Field(default="", alias="FIRECRAWL_API_KEY")

    fca_docs_dir: Path = Field(default=Path("./fca_docs"), alias="FCA_DOCS_DIR")
    chroma_persist_dir: Path = Field(default=Path("./chroma_db"), alias="CHROMA_PERSIST_DIR")
    audit_cache_dir: Path = Field(default=Path("./audit_cache"), alias="AUDIT_CACHE_DIR")
    audit_cache_db_url: str = Field(
        default="",
        alias="AUDIT_CACHE_DB_URL",
        description=(
            "Optional database URL for audit report cache. "
            "If set (e.g. sqlite:////absolute/path/to/cache.sqlite), "
            "the cache uses SQLite instead of the file-based JSON cache."
        ),
    )

    crawl_page_limit: int = Field(default=15, ge=1, le=100, alias="CRAWL_PAGE_LIMIT")
    max_page_chars: int = Field(default=40_000, ge=1_000, le=500_000, alias="MAX_PAGE_CHARS")
    max_total_words: int = Field(default=60_000, ge=2_000, le=2_000_000, alias="MAX_TOTAL_WORDS")

    allow_private_urls: bool = Field(default=False, alias="ALLOW_PRIVATE_URLS")

    cache_key_version: str = Field(default="v2", alias="CACHE_KEY_VERSION")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

