"""File-based JSON cache for audit reports (MD5 URL key)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import re

from dotenv import load_dotenv

from backend.schemas.audit import AuditReport, InsufficientDataReport

load_dotenv()

logger = logging.getLogger(__name__)

CACHE_DIR = Path(
    os.environ.get("AUDIT_CACHE_DIR", "./audit_cache"),
).resolve()

_MD5_HEX = re.compile(r"^[0-9a-f]{32}$")


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _path_for_hash(h: str) -> Path:
    # Defensive: only allow hex MD5 filenames.
    if not _MD5_HEX.fullmatch(h):
        raise ValueError("Invalid cache key hash format")
    p = (CACHE_DIR / f"{h}.json").resolve()
    # Defensive: ensure the path is within CACHE_DIR even if CACHE_DIR is a symlink.
    if p.parent != CACHE_DIR:
        raise ValueError("Resolved cache path is outside CACHE_DIR")
    return p


def get_cached_report(url: str) -> AuditReport | InsufficientDataReport | None:
    h = _url_hash(url)
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
    h = _url_hash(url)
    path = _path_for_hash(h)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Cached report for %s", url)


def clear_cache(url: str | None = None) -> int:
    if url is not None:
        try:
            path = _path_for_hash(_url_hash(url))
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
