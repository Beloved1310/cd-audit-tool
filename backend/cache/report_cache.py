"""File-based JSON cache for audit reports (versioned key)."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import re

from backend.config import get_settings
from backend.schemas.audit import AuditReport, InsufficientDataReport
from backend.util.url_norm import canonical_url

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()
CACHE_DIR = _SETTINGS.audit_cache_dir.resolve()

_MD5_HEX = re.compile(r"^[0-9a-f]{32}$")


def _cache_key(url: str, *, pipeline_version: str) -> str:
    """Return a deterministic cache key for (url, pipeline_version).

    The cache is versioned to avoid serving stale reports when prompts/criteria change.
    """
    base = f"{_SETTINGS.cache_key_version}|{pipeline_version}|{url}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def _path_for_hash(h: str) -> Path:
    # Defensive: only allow hex MD5 filenames.
    if not _MD5_HEX.fullmatch(h):
        raise ValueError("Invalid cache key hash format")
    p = (CACHE_DIR / f"{h}.json").resolve()
    # Defensive: ensure the path is within CACHE_DIR even if CACHE_DIR is a symlink.
    if p.parent != CACHE_DIR:
        raise ValueError("Resolved cache path is outside CACHE_DIR")
    return p


def get_cached_report(url: str, *, pipeline_version: str) -> AuditReport | InsufficientDataReport | None:
    h = _cache_key(canonical_url(url), pipeline_version=pipeline_version)
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
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pipeline_version = getattr(report, "pipeline_version", "") or "unknown"
    h = _cache_key(canonical_url(url), pipeline_version=pipeline_version)
    path = _path_for_hash(h)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Cached report for %s", url)


def clear_cache(url: str | None = None, *, pipeline_version: str | None = None) -> int:
    if url is not None:
        try:
            pv = pipeline_version or "unknown"
            path = _path_for_hash(_cache_key(canonical_url(url), pipeline_version=pv))
        except ValueError:
            return 0
        if path.is_file():
            path.unlink()
            return 1
        return 0
    if not CACHE_DIR.is_dir():
        return 0
    n = 0
    for p in CACHE_DIR.glob("*.json"):
        try:
            rp = p.resolve()
            if rp.parent != CACHE_DIR:
                continue
            p.unlink()
            n += 1
        except OSError:
            continue
    return n
