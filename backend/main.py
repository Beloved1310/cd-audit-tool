"""FastAPI entry: audit, compare, cache, health."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.cache.report_cache import cache_report, clear_cache, get_cached_report
from backend.ingestion.fca_loader import get_retriever, load_fca_docs
from backend.pipeline.graph import run_audit
from backend.pipeline.journey_runner import JOURNEY_MAX_STEPS, JOURNEY_MIN_STEPS, run_journey
from backend.security.url_safety import validate_public_url
from backend.schemas.audit import AuditReport, ComparisonReport, InsufficientDataReport
from backend.schemas.journey import JourneyReport, JourneyStepInput

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env contract (python-dotenv): GROQ_API_KEY, FIRECRAWL_API_KEY, CHROMA_PERSIST_DIR,
# FCA_DOCS_DIR, AUDIT_CACHE_DIR — consumed by ingestion, crawler, cache, Groq client.


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on missing secrets/config.
    # GROQ is required for scoring; Firecrawl is optional (crawler has fallback paths).
    missing: list[str] = []
    if not (os.environ.get("GROQ_API_KEY") or "").strip():
        missing.append("GROQ_API_KEY")
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Copy .env.example to .env and set your API keys.",
        )
    if not (os.environ.get("FIRECRAWL_API_KEY") or "").strip():
        logger.warning(
            "FIRECRAWL_API_KEY is not set; crawler will use WebBaseLoader fallback paths.",
        )

    docs_dir = os.environ.get("FCA_DOCS_DIR", "./fca_docs")
    chroma_db = load_fca_docs(docs_dir)
    retriever = get_retriever(chroma_db, k=4)
    app.state.retriever = retriever

    coll = getattr(chroma_db, "_collection", None)
    if coll is not None and hasattr(coll, "count"):
        n = int(coll.count())
    else:
        data = chroma_db.get(include=[])
        n = len(data.get("ids") or [])
    app.state.fca_chunk_count = n

    logger.info("FCA knowledge base ready. %s chunks loaded.", n)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Consumer Duty Sludge Audit API",
    version="0.1.0",
    description="FCA Consumer Duty (FG22/5) crawl + RAG audit backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    url: str


class CompareRequest(BaseModel):
    url_a: str
    url_b: str


class JourneyRequest(BaseModel):
    """Ordered user journey: 2–10 steps, each an absolute URL and optional label."""

    steps: list[JourneyStepInput]


class CacheDeleteResponse(BaseModel):
    deleted: int


def validate_url(url: str) -> bool:
    ok, _ = validate_public_url(url)
    return ok


@app.get("/health")
def health():
    return {
        "status": "ok",
        "fca_chunks_loaded": getattr(app.state, "fca_chunk_count", 0),
        "groq_model": "llama-3.3-70b-versatile",
    }


@app.post("/audit")
def audit(req: AuditRequest):
    url = req.url.strip()
    ok, reason = validate_public_url(url)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid URL: {url}. {reason}",
        )

    cached = get_cached_report(url)
    if cached is not None:
        logger.info("Cache HIT for %s", url)
        return JSONResponse(
            content=cached.model_dump(mode="json"),
            headers={"X-Cache": "HIT"},
        )

    logger.info("Starting audit for %s", url)
    t0 = time.perf_counter()
    try:
        report = run_audit(url, app.state.retriever)
    except Exception as e:  # noqa: BLE001
        logger.exception("Audit failed for %s", url)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "url": url},
        ) from e

    duration = time.perf_counter() - t0
    cache_report(url, report)
    logger.info("Audit complete for %s in %.1fs", url, duration)
    return JSONResponse(
        content=report.model_dump(mode="json"),
        headers={"X-Cache": "MISS"},
    )


@app.post("/audit/compare", response_model=ComparisonReport)
async def audit_compare(req: CompareRequest):
    url_a, url_b = sorted([req.url_a.strip(), req.url_b.strip()])
    ok, reason = validate_public_url(url_a)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid URL: {url_a}. {reason}",
        )
    ok, reason = validate_public_url(url_b)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid URL: {url_b}. {reason}",
        )

    async def run_single(u: str) -> AuditReport | InsufficientDataReport:
        cached = get_cached_report(u)
        if cached is not None:
            return cached
        report = await asyncio.to_thread(run_audit, u, app.state.retriever)
        cache_report(u, report)
        return report

    report_a, report_b = await asyncio.gather(
        run_single(url_a),
        run_single(url_b),
    )

    comparison = ComparisonReport(
        url_a=url_a,
        url_b=url_b,
        hash_a=hashlib.md5(url_a.encode()).hexdigest(),
        hash_b=hashlib.md5(url_b.encode()).hexdigest(),
        report_a=report_a,
        report_b=report_b,
        generated_at_iso=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    )
    return comparison


@app.post("/audit/journey", response_model=JourneyReport)
def audit_journey(req: JourneyRequest):
    """Analyse a defined path step-by-step: friction flags and dark patterns per URL."""
    if len(req.steps) < JOURNEY_MIN_STEPS:
        raise HTTPException(
            status_code=422,
            detail=f"Journey must include at least {JOURNEY_MIN_STEPS} steps",
        )
    if len(req.steps) > JOURNEY_MAX_STEPS:
        raise HTTPException(
            status_code=422,
            detail=f"Journey cannot exceed {JOURNEY_MAX_STEPS} steps",
        )
    for s in req.steps:
        ok, reason = validate_public_url(s.url)
        if not ok:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid step URL: {s.url}. {reason}",
            )
    try:
        return run_journey(req.steps, app.state.retriever)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.exception("Journey audit failed")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e)},
        ) from e


@app.delete("/audit/cache", response_model=CacheDeleteResponse)
def delete_audit_cache(url: str | None = Query(None)):
    n = clear_cache(url)
    return CacheDeleteResponse(deleted=n)
