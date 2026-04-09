"""Audit report cache (versioned key).

Default implementation is a file-based JSON cache.
If AUDIT_CACHE_DB_URL is set, uses SQLite instead.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import re

from backend.config import get_settings
from backend.cache.report_cache_db import (
    cache_report_sqlite,
    clear_cache_sqlite,
    get_cached_report_sqlite,
)
from backend.schemas.audit import AuditReport, InsufficientDataReport
from backend.util.url_norm import canonical_url

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()

_MD5_HEX = re.compile(r"^[0-9a-f]{32}$")


def _cache_key(url: str, *, pipeline_version: str) -> str:
    """Return a deterministic cache key for (url, pipeline_version).

    The cache is versioned to avoid serving stale reports when prompts/criteria change.
    """
    base = f"{_SETTINGS.cache_key_version}|{pipeline_version}|{url}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def _path_for_hash(h: str) -> Path:
    cache_dir = (
        Path((os.getenv("AUDIT_CACHE_DIR") or "").strip())
        if (os.getenv("AUDIT_CACHE_DIR") or "").strip()
        else _SETTINGS.audit_cache_dir
    ).resolve()
    # Defensive: only allow hex MD5 filenames.
    if not _MD5_HEX.fullmatch(h):
        raise ValueError("Invalid cache key hash format")
    p = (cache_dir / f"{h}.json").resolve()
    # Defensive: ensure the path is within cache_dir even if cache_dir is a symlink.
    if p.parent != cache_dir:
        raise ValueError("Resolved cache path is outside CACHE_DIR")
    return p


def get_cached_report(url: str, *, pipeline_version: str) -> AuditReport | InsufficientDataReport | None:
    h = _cache_key(canonical_url(url), pipeline_version=pipeline_version)
    db_url = (os.getenv("AUDIT_CACHE_DB_URL") or "").strip() or (_SETTINGS.audit_cache_db_url or "").strip()
    if db_url:
        return get_cached_report_sqlite(db_url=db_url, cache_key=h)
    try:
        path = _path_for_hash(h)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if data.get("insufficient_data") is True:
            return InsufficientDataReport.model_validate(data)
        return AuditReport.model_validate(data)
    except Exception:  # noqa: BLE001
        logger.warning("Cache parse failed for %s", url)
        return None


def cache_report(url: str, report: AuditReport | InsufficientDataReport) -> None:
    pipeline_version = getattr(report, "pipeline_version", "") or "unknown"
    h = _cache_key(canonical_url(url), pipeline_version=pipeline_version)
    db_url = (os.getenv("AUDIT_CACHE_DB_URL") or "").strip() or (_SETTINGS.audit_cache_db_url or "").strip()
    if db_url:
        cache_report_sqlite(
            db_url=db_url,
            cache_key=h,
            url=canonical_url(url),
            pipeline_version=pipeline_version,
            report=report,
        )
        logger.info("Cached report for %s (sqlite)", url)
        return
    cache_dir = (
        Path((os.getenv("AUDIT_CACHE_DIR") or "").strip())
        if (os.getenv("AUDIT_CACHE_DIR") or "").strip()
        else _SETTINGS.audit_cache_dir
    ).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _path_for_hash(h)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Cached report for %s", url)


def clear_cache(url: str | None = None, *, pipeline_version: str | None = None) -> int:
    db_url = (os.getenv("AUDIT_CACHE_DB_URL") or "").strip() or (_SETTINGS.audit_cache_db_url or "").strip()
    if url is not None:
        try:
            pv = pipeline_version or "unknown"
            key = _cache_key(canonical_url(url), pipeline_version=pv)
        except ValueError:
            return 0
        if db_url:
            return clear_cache_sqlite(db_url=db_url, cache_key=key)
        path = _path_for_hash(key)
        if path.is_file():
            path.unlink()
            return 1
        return 0
    if db_url:
        return clear_cache_sqlite(db_url=db_url, cache_key=None)
    cache_dir = (
        Path((os.getenv("AUDIT_CACHE_DIR") or "").strip())
        if (os.getenv("AUDIT_CACHE_DIR") or "").strip()
        else _SETTINGS.audit_cache_dir
    ).resolve()
    if not cache_dir.is_dir():
        return 0
    n = 0
    for p in cache_dir.glob("*.json"):
        try:
            rp = p.resolve()
            if rp.parent != cache_dir:
                continue
            p.unlink()
            n += 1
        except OSError:
            continue
    return n
