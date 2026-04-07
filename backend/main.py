"""FastAPI entry: audit, compare, cache, health."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
import httpx
from backend.config import get_settings
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.cache.report_cache import cache_report, clear_cache, get_cached_report
from backend.pipeline.versioning import compute_pipeline_version
from backend.ingestion.fca_loader import get_retriever, load_fca_docs
from backend.observability import (
    configure_logging,
    inc_metric,
    metrics_snapshot,
    request_id_ctx,
)
from backend.pipeline.graph import run_audit
from backend.pipeline.journey_runner import JOURNEY_MAX_STEPS, JOURNEY_MIN_STEPS, run_journey
from backend.security.url_safety import validate_public_url
from backend.schemas.audit import AuditReport, ComparisonReport, InsufficientDataReport
from backend.schemas.audit import DarkPattern, Finding, VulnerabilityGap
from backend.schemas.pagination import Page
from backend.schemas.journey import JourneyReport, JourneyStepInput
from backend.util.url_norm import canonical_url
from backend.app.services.audit_service import (
    get_or_run_audit,
    get_or_run_compare,
    get_or_run_journey,
)

load_dotenv()
_SETTINGS = get_settings()

configure_logging()
logger = logging.getLogger(__name__)

# Environment variables consumed by configuration/pipeline:
# GROQ_API_KEY, FIRECRAWL_API_KEY, FCA_DOCS_DIR, CHROMA_PERSIST_DIR, AUDIT_CACHE_DIR,
# CRAWL_PAGE_LIMIT, MAX_PAGE_CHARS, MAX_TOTAL_WORDS, ALLOW_PRIVATE_URLS, USER_AGENT.

_RATE_LIMIT_PER_MINUTE = 5
_rate_limit_hits: dict[str, list[float]] = {}


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return str(rid) if rid else "unknown"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign request ID, propagate to logs, emit one access line per request."""

    async def dispatch(self, request: Request, call_next):
        inbound = (request.headers.get("X-Request-ID") or "").strip()
        rid = inbound if inbound else uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_ctx.set(rid)
        t0 = time.perf_counter()
        status_code = 500
        try:
            resp: Response = await call_next(request)
            status_code = resp.status_code
            resp.headers.setdefault("X-Request-ID", rid)
            return resp
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            logger.info(
                "http_request method=%s path=%s status=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )
            request_id_ctx.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp: Response = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        return resp


class AuditRateLimitMiddleware(BaseHTTPMiddleware):
    """Very small in-memory rate limiter for POST /audit only."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path == "/audit":
            ip = (request.client.host if request.client else "unknown") or "unknown"
            now = time.time()
            window_start = now - 60.0
            hits = _rate_limit_hits.get(ip) or []
            hits = [t for t in hits if t >= window_start]
            if len(hits) >= _RATE_LIMIT_PER_MINUTE:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "type": "rate_limited",
                            "message": (
                                f"Rate limit exceeded: max {_RATE_LIMIT_PER_MINUTE} "
                                "requests per minute for /audit"
                            ),
                        },
                        "request_id": _request_id(request),
                    },
                    headers={"X-Request-ID": _request_id(request)},
                )
            hits.append(now)
            _rate_limit_hits[ip] = hits
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on missing required configuration.
    # Groq is required for scoring; Firecrawl is optional (crawler has fallback paths).
    missing: list[str] = []
    if not _SETTINGS.groq_api_key.strip():
        missing.append("GROQ_API_KEY")
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". See .env.example for required configuration keys.",
        )
    if not _SETTINGS.firecrawl_api_key.strip():
        logger.warning(
            "FIRECRAWL_API_KEY is not set; crawler will use WebBaseLoader fallback paths.",
        )

    docs_dir = str(_SETTINGS.fca_docs_dir)
    chroma_db = load_fca_docs(docs_dir)
    retriever = get_retriever(chroma_db, k=4)
    app.state.retriever = retriever
    app.state.pipeline_version = compute_pipeline_version()
    app.state.http_client = httpx.Client(
        timeout=httpx.Timeout(10.0, connect=5.0),
        follow_redirects=True,
        headers={"User-Agent": os.environ.get("USER_AGENT", "cd-audit-tool/0.1")},
    )

    coll = getattr(chroma_db, "_collection", None)
    if coll is not None and hasattr(coll, "count"):
        n = int(coll.count())
    else:
        data = chroma_db.get(include=[])
        n = len(data.get("ids") or [])
    app.state.fca_chunk_count = n

    logger.info("FCA knowledge base ready. %s chunks loaded.", n)
    yield
    try:
        app.state.http_client.close()
    except Exception:  # noqa: BLE001
        pass
    logger.info("Shutting down.")


app = FastAPI(
    title="Consumer Duty Sludge Audit API",
    version="0.1.0",
    description="FCA Consumer Duty (FG22/5) crawl + RAG audit backend",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditRateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    msg = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"type": "http_error", "message": msg, "detail": exc.detail},
            "request_id": _request_id(request),
        },
        headers={"X-Request-ID": _request_id(request)},
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    msg = str(exc.detail) if exc.detail is not None else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"type": "http_error", "message": msg, "detail": exc.detail},
            "request_id": _request_id(request),
        },
        headers={"X-Request-ID": _request_id(request)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):  # noqa: BLE001
    logger.exception("Unhandled error request_id=%s", _request_id(request))
    return JSONResponse(
        status_code=500,
        content={
            "error": {"type": "internal_error", "message": "Internal server error"},
            "request_id": _request_id(request),
        },
        headers={"X-Request-ID": _request_id(request)},
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


def _build_comparison_report(
    url_a: str,
    url_b: str,
    report_a: AuditReport | InsufficientDataReport,
    report_b: AuditReport | InsufficientDataReport,
) -> ComparisonReport:
    from backend.app.services.audit_service import build_comparison_report

    return build_comparison_report(
        url_a=url_a,
        url_b=url_b,
        report_a=report_a,
        report_b=report_b,
    )


@app.get("/health")
def health():
    n = int(getattr(app.state, "fca_chunk_count", 0) or 0)
    git_sha = (os.getenv("GIT_SHA") or "").strip()
    return {
        "status": "ok",
        "app_version": app.version,
        "environment": (os.getenv("ENV") or "development").strip(),
        "git_sha": git_sha or None,
        "pipeline_version": getattr(app.state, "pipeline_version", None),
        "fca_chunks_loaded": n,
        "fca_ready": n > 0,
        "groq_model": "llama-3.3-70b-versatile",
    }


@app.get("/metrics")
def metrics():
    """Lightweight in-process counters (JSON); suitable for dashboards or smoke checks."""
    return metrics_snapshot()


@app.get("/audit/report")
def get_audit_report(url: str = Query(..., description="Audited site URL (must match cache key).")):
    u = url.strip()
    ok, reason = validate_public_url(u)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid URL: {u}. {reason}",
        )
    cached = get_cached_report(u, pipeline_version=app.state.pipeline_version)
    if cached is None:
        inc_metric("audit_report_get_miss")
        raise HTTPException(
            status_code=404,
            detail="No cached report for this URL. Run POST /audit first.",
        )
    inc_metric("audit_report_get_hit")
    return JSONResponse(
        content=cached.model_dump(mode="json"),
        headers={"X-Cache": "HIT"},
    )


def _paginate(items: list, page: int, page_size: int) -> tuple[list, int]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


@app.get("/audit/report/findings", response_model=Page[Finding])
def get_report_findings(
    url: str = Query(..., description="Audited site URL (must match cache key)."),
    outcome: str = Query(..., description="Outcome name, e.g. 'Consumer Support'."),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    u = url.strip()
    ok, reason = validate_public_url(u)
    if not ok:
        raise HTTPException(status_code=422, detail=f"Invalid URL: {u}. {reason}")
    cached = get_cached_report(u, pipeline_version=app.state.pipeline_version)
    if cached is None:
        raise HTTPException(status_code=404, detail="No cached report for this URL. Run POST /audit first.")
    if isinstance(cached, InsufficientDataReport):
        raise HTTPException(status_code=409, detail="Report is insufficient_data; no findings are available.")
    report = cached
    o = next((x for x in report.outcomes if x.outcome_name == outcome), None)
    if o is None:
        raise HTTPException(status_code=404, detail=f"Outcome not found: {outcome}")
    sliced, total = _paginate(list(o.findings or []), page, page_size)
    return Page[Finding](items=sliced, page=page, page_size=page_size, total=total)


@app.get("/audit/report/dark-patterns", response_model=Page[DarkPattern])
def get_report_dark_patterns(
    url: str = Query(..., description="Audited site URL (must match cache key)."),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    u = url.strip()
    ok, reason = validate_public_url(u)
    if not ok:
        raise HTTPException(status_code=422, detail=f"Invalid URL: {u}. {reason}")
    cached = get_cached_report(u, pipeline_version=app.state.pipeline_version)
    if cached is None:
        raise HTTPException(status_code=404, detail="No cached report for this URL. Run POST /audit first.")
    if isinstance(cached, InsufficientDataReport):
        raise HTTPException(status_code=409, detail="Report is insufficient_data; dark patterns are unavailable.")
    report = cached
    sliced, total = _paginate(list(report.dark_patterns or []), page, page_size)
    return Page[DarkPattern](items=sliced, page=page, page_size=page_size, total=total)


@app.get("/audit/report/vulnerability-gaps", response_model=Page[VulnerabilityGap])
def get_report_vulnerability_gaps(
    url: str = Query(..., description="Audited site URL (must match cache key)."),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    u = url.strip()
    ok, reason = validate_public_url(u)
    if not ok:
        raise HTTPException(status_code=422, detail=f"Invalid URL: {u}. {reason}")
    cached = get_cached_report(u, pipeline_version=app.state.pipeline_version)
    if cached is None:
        raise HTTPException(status_code=404, detail="No cached report for this URL. Run POST /audit first.")
    if isinstance(cached, InsufficientDataReport):
        raise HTTPException(status_code=409, detail="Report is insufficient_data; vulnerability gaps are unavailable.")
    report = cached
    sliced, total = _paginate(list(report.vulnerability_gaps or []), page, page_size)
    return Page[VulnerabilityGap](items=sliced, page=page, page_size=page_size, total=total)


@app.get("/audit/compare/report", response_model=ComparisonReport)
def get_compare_report(
    url_a: str = Query(..., description="First site URL (sorted pair with url_b)."),
    url_b: str = Query(..., description="Second site URL."),
):
    ua, ub = sorted([url_a.strip(), url_b.strip()])
    ok, reason = validate_public_url(ua)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid URL: {ua}. {reason}",
        )
    ok, reason = validate_public_url(ub)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid URL: {ub}. {reason}",
        )
    ra = get_cached_report(ua, pipeline_version=app.state.pipeline_version)
    rb = get_cached_report(ub, pipeline_version=app.state.pipeline_version)
    if ra is None or rb is None:
        inc_metric("compare_report_get_miss")
        raise HTTPException(
            status_code=404,
            detail="One or both audits are not in cache. Run POST /audit/compare first.",
        )
    inc_metric("compare_report_get_hit")
    return _build_comparison_report(ua, ub, ra, rb)


@app.post("/audit")
def audit(req: AuditRequest):
    url = req.url.strip()
    ok, reason = validate_public_url(url)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid URL: {url}. {reason}",
        )

    cached = get_cached_report(url, pipeline_version=app.state.pipeline_version)
    if cached is not None:
        inc_metric("audit_post_total")
        inc_metric("audit_post_cache_hit")
        logger.info("Cache HIT for %s", url)
        return JSONResponse(
            content=cached.model_dump(mode="json"),
            headers={"X-Cache": "HIT"},
        )

    logger.info("Starting audit for %s", url)
    t0 = time.perf_counter()
    try:
        report = get_or_run_audit(
            url=url,
            retriever=app.state.retriever,
            pipeline_version=app.state.pipeline_version,
            http_client=app.state.http_client,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Audit failed for %s", url)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "url": url},
        ) from e

    duration = time.perf_counter() - t0
    inc_metric("audit_post_total")
    inc_metric("audit_post_cache_miss")
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

    return await get_or_run_compare(
        url_a=url_a,
        url_b=url_b,
        retriever=app.state.retriever,
        pipeline_version=app.state.pipeline_version,
        http_client=app.state.http_client,
    )


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
        return get_or_run_journey(
            steps=req.steps,
            retriever=app.state.retriever,
            pipeline_version=app.state.pipeline_version,
            http_client=app.state.http_client,
        )
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
    if url is None:
        n = clear_cache(None)
    else:
        n = clear_cache(url, pipeline_version=app.state.pipeline_version)
    return CacheDeleteResponse(deleted=n)
