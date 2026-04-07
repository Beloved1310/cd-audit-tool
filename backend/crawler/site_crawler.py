"""Site crawl via Firecrawl with WebBaseLoader fallback — returns structured CrawlResult."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_community.document_loaders import FireCrawlLoader

from backend.config import get_settings
from backend.security.url_safety import validate_public_url

_SETTINGS = get_settings()

FALLBACK_PATHS: list[str] = [
    "",
    "/products",
    "/services",
    "/pricing",
    "/fees",
    "/help",
    "/support",
    "/faq",
    "/complaints",
    "/contact",
    "/accessibility",
    "/vulnerable-customers",
    "/financial-difficulty",
    "/about",
]

_FIRST_URL_KEYWORDS = (
    "support",
    "complaints",
    "accessibility",
    "vulnerable",
    "difficulty",
    "help",
    "faq",
)
_SECOND_URL_KEYWORDS = ("pricing", "fees", "charges")
_THIRD_URL_KEYWORDS = ("products", "services")


@dataclass
class CrawledPage:
    """Single page text extracted during a crawl."""

    url: str
    title: str
    content: str
    word_count: int
    crawled_at: datetime


@dataclass
class CrawlResult:
    """Aggregated outcome of a site crawl."""

    pages: list[CrawledPage] = field(default_factory=list)
    total_words: int = 0
    duration_seconds: float = 0.0
    crawl_method: str = "firecrawl"
    errors: list[str] = field(default_factory=list)


def _normalize_url(url: str) -> str:
    u = url.strip()
    if not u:
        return u
    parsed = urlparse(u)
    if not parsed.scheme:
        u = "https://" + u
    return u


def _doc_url(meta: dict) -> str:
    return (
        (meta.get("sourceURL") or meta.get("url") or meta.get("source") or "")
        if isinstance(meta, dict)
        else ""
    )


def _doc_title(meta: dict) -> str:
    if not isinstance(meta, dict):
        return ""
    t = meta.get("title")
    return str(t).strip() if t is not None else ""


def _to_crawled_page(url: str, title: str, content: str) -> CrawledPage | None:
    text = (content or "").strip()
    if len(text) > _SETTINGS.max_page_chars:
        text = text[: _SETTINGS.max_page_chars]
    wc = len(text.split())
    if wc < 100:
        return None
    return CrawledPage(
        url=url or "unknown",
        title=title or "",
        content=text,
        word_count=wc,
        crawled_at=datetime.utcnow(),
    )


def _full_url(base: str, path: str) -> str:
    base = _normalize_url(base).rstrip("/")
    if path in ("", "/"):
        return base + "/"
    if path.startswith("/"):
        return base + path
    return base + "/" + path


def _priority_key(page: CrawledPage) -> tuple[int, str]:
    u = page.url.lower()
    path = urlparse(page.url).path or ""
    is_home = path in ("", "/")

    if any(k in u for k in _FIRST_URL_KEYWORDS):
        return (0, page.url)
    if any(k in u for k in _SECOND_URL_KEYWORDS):
        return (1, page.url)
    if any(k in u for k in _THIRD_URL_KEYWORDS):
        return (2, page.url)
    if is_home:
        return (3, page.url)
    return (4, page.url)


def _run_firecrawl(target: str) -> list[CrawledPage]:
    loader = FireCrawlLoader(
        api_key=_SETTINGS.firecrawl_api_key or None,
        url=target,
        mode="crawl",
        params={"limit": _SETTINGS.crawl_page_limit},
    )
    docs = loader.load()
    out: list[CrawledPage] = []
    for d in docs:
        meta = dict(d.metadata or {})
        url = _doc_url(meta) or target
        title = _doc_title(meta)
        content = d.page_content or ""
        cp = _to_crawled_page(url, title, content)
        if cp is not None:
            out.append(cp)
    return out


def _run_webbase_fallback(
    base_url: str,
    errors: list[str],
    *,
    client: httpx.Client,
) -> list[CrawledPage]:
    out: list[CrawledPage] = []
    seen: set[str] = set()
    for path in FALLBACK_PATHS:
        full = _full_url(base_url, path)
        if full in seen:
            continue
        seen.add(full)
        try:
            resp = client.get(full)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text("\n", strip=True)
            docs = [{"url": full, "title": soup.title.string.strip() if soup.title and soup.title.string else "", "content": text}]
        except Exception as e:  
            errors.append(f"{full}: {e!s}")
            continue
        for d in docs:
            url = d.get("url") or full
            title = d.get("title") or ""
            content = d.get("content") or ""
            cp = _to_crawled_page(url, title, content)
            if cp is not None:
                out.append(cp)
    return out


def crawl_website(url: str, *, http_client: httpx.Client | None = None) -> CrawlResult:
    """
    Crawl a website using Firecrawl, or WebBaseLoader on listed paths if Firecrawl fails.

    Never raises; all failures are recorded in ``CrawlResult.errors``.
    """
    t0 = time.perf_counter()
    errors: list[str] = []
    pages: list[CrawledPage] = []
    method = "firecrawl"

    target = _normalize_url(url)
    if not target:
        return CrawlResult(
            pages=[],
            total_words=0,
            duration_seconds=time.perf_counter() - t0,
            crawl_method=method,
            errors=["Empty URL after normalisation"],
        )

    ok, reason = validate_public_url(target)
    if not ok:
        return CrawlResult(
            pages=[],
            total_words=0,
            duration_seconds=time.perf_counter() - t0,
            crawl_method=method,
            errors=[f"Blocked unsafe URL: {reason}"],
        )

    client = http_client or httpx.Client(
        timeout=httpx.Timeout(10.0, connect=5.0),
        follow_redirects=True,
        headers={"User-Agent": os.environ.get("USER_AGENT", "cd-audit-tool/0.1")},
    )
    try:
        pages = _run_firecrawl(target)
    except Exception as e:  # noqa: BLE001
        errors.append(f"FirecrawlLoader: {e!s}")
        method = "fallback_webbase"
        pages = _run_webbase_fallback(target, errors, client=client)

    # Dedupe by URL, keep first occurrence (higher priority after sort will reorder)
    by_url: dict[str, CrawledPage] = {}
    for p in pages:
        if p.url not in by_url:
            by_url[p.url] = p
    pages = list(by_url.values())

    pages.sort(key=_priority_key)

    total_words = sum(p.word_count for p in pages)
    if total_words > _SETTINGS.max_total_words:
        kept: list[CrawledPage] = []
        running = 0
        for p in pages:
            if running + p.word_count > _SETTINGS.max_total_words:
                continue
            kept.append(p)
            running += p.word_count
        pages = kept
        total_words = running
    duration = time.perf_counter() - t0

    return CrawlResult(
        pages=pages,
        total_words=total_words,
        duration_seconds=duration,
        crawl_method=method,
        errors=errors,
    )


def _to_crawled_page_journey(url: str, title: str, content: str, *, min_words: int = 12) -> CrawledPage | None:
    """Single-page fetch for journey mode — lower word floor than site-wide crawl."""
    text = (content or "").strip()
    wc = len(text.split())
    if wc < min_words:
        return None
    return CrawledPage(
        url=url or "unknown",
        title=title or "",
        content=text,
        word_count=wc,
        crawled_at=datetime.utcnow(),
    )


def fetch_single_page(url: str, *, http_client: httpx.Client | None = None) -> tuple[CrawledPage | None, str | None]:
    """
    Load exactly one URL (journey step). Returns ``(page, error)``.
    Uses WebBaseLoader for a predictable single-page scrape.
    """
    target = _normalize_url(url)
    if not target:
        return None, "Empty or invalid URL"
    ok, reason = validate_public_url(target)
    if not ok:
        return None, f"Blocked unsafe URL: {reason}"
    try:
        client = http_client or httpx.Client(
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=True,
            headers={"User-Agent": os.environ.get("USER_AGENT", "cd-audit-tool/0.1")},
        )
        resp = client.get(target)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text("\n", strip=True)
        docs = [{"url": target, "title": soup.title.string.strip() if soup.title and soup.title.string else "", "content": text}]
    except Exception as e: 
        return None, str(e)
    if not docs:
        return None, "No content returned"
    d = docs[0]
    resolved = d.get("url") or target
    title = d.get("title") or ""
    content = d.get("content") or ""
    cp = _to_crawled_page_journey(resolved, title, content)
    if cp is None:
        return None, "Insufficient extractable text on page (try a different URL or check blocking)"
    return cp, None


def assess_crawl_quality(result: CrawlResult) -> tuple[bool, str]:
    """
    Return ``(is_sufficient, reason)`` where sufficient means
    at least 3 pages and at least 2,000 words.
    """
    n = len(result.pages)
    w = result.total_words
    if n >= 3 and w >= 2000:
        return True, ""
    if n < 3 and w < 2000:
        return (
            False,
            f"Only {n} pages crawled (minimum 3) and only {w} words extracted (minimum 2,000)",
        )
    if n < 3:
        return False, f"Only {n} pages crawled (minimum 3 required)"
    return False, f"Only {w:,} words extracted (minimum 2,000 required)"


def crawled_pages_to_docs(pages: list[CrawledPage]) -> list[dict]:
    """Shape used by prompt builders: ``page_content`` + ``metadata`` for URL/title."""
    out: list[dict] = []
    for p in pages:
        out.append(
            {
                "page_content": p.content,
                "metadata": {
                    "sourceURL": p.url,
                    "url": p.url,
                    "title": p.title,
                },
            }
        )
    return out
