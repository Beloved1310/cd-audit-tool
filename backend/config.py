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
    admin_api_key: str = Field(default="", alias="ADMIN_API_KEY")

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

    rag_retrieval_k: int = Field(
        default=8,
        ge=1,
        le=20,
        alias="RAG_RETRIEVAL_K",
        description="Top-k FCA chunks retrieved per query string in outcome nodes.",
    )
    rag_max_chunks: int = Field(
        default=8,
        ge=1,
        le=24,
        alias="RAG_MAX_CHUNKS",
        description="Maximum deduplicated FCA chunks passed into a single prompt.",
    )
    rag_context_max_chars: int = Field(
        default=10_000,
        ge=2_000,
        le=32_000,
        alias="RAG_CONTEXT_MAX_CHARS",
        description="Character cap on concatenated FCA excerpt text per node.",
    )
    rag_hybrid_enabled: bool = Field(
        default=True,
        alias="RAG_HYBRID_ENABLED",
        description="Fuse BM25 keyword search with vector similarity for FCA retrieval.",
    )
    rag_hybrid_candidate_k: int = Field(
        default=16,
        ge=4,
        le=40,
        alias="RAG_HYBRID_CANDIDATE_K",
        description="Per-channel candidate pool size before RRF fusion.",
    )
    rag_hybrid_rrf_k: int = Field(
        default=60,
        ge=1,
        le=200,
        alias="RAG_HYBRID_RRF_K",
        description="RRF rank constant (higher = flatter fusion weights).",
    )
    rag_per_criterion_enabled: bool = Field(
        default=True,
        alias="RAG_PER_CRITERION_ENABLED",
        description="Run one FCA retrieval query per checklist criterion (10 per outcome).",
    )
    rag_per_criterion_k: int = Field(
        default=2,
        ge=1,
        le=6,
        alias="RAG_PER_CRITERION_K",
        description="Top-k chunks retrieved per criterion query.",
    )
    rag_per_criterion_max_chunks: int = Field(
        default=16,
        ge=4,
        le=32,
        alias="RAG_PER_CRITERION_MAX_CHUNKS",
        description="Max deduplicated chunks when using per-criterion retrieval.",
    )

    crawl_page_limit: int = Field(default=15, ge=1, le=100, alias="CRAWL_PAGE_LIMIT")
    max_page_chars: int = Field(default=40_000, ge=1_000, le=500_000, alias="MAX_PAGE_CHARS")
    max_total_words: int = Field(default=60_000, ge=2_000, le=2_000_000, alias="MAX_TOTAL_WORDS")

    allow_private_urls: bool = Field(default=False, alias="ALLOW_PRIVATE_URLS")

    cors_allow_origins: str = Field(
        default="http://localhost:3000",
        alias="CORS_ALLOW_ORIGINS",
    )
    hsts_max_age_seconds: int = Field(
        default=0,
        ge=0,
        le=63072000,
        alias="HSTS_MAX_AGE_SECONDS",
    )

    cache_key_version: str = Field(default="v2", alias="CACHE_KEY_VERSION")

    def cors_origin_list(self) -> list[str]:
        parts = [x.strip() for x in (self.cors_allow_origins or "").split(",") if x.strip()]
        return parts if parts else ["http://localhost:3000"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

