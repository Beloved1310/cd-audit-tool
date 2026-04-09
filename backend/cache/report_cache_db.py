"""SQLite-backed JSON cache for audit reports (versioned key).

This is an optional persistence layer used when AUDIT_CACHE_DB_URL is set.
Only SQLite URLs are supported: sqlite:////absolute/path/to/file.sqlite
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from backend.schemas.audit import AuditReport, InsufficientDataReport

logger = logging.getLogger(__name__)

_DDL: Final[str] = """
CREATE TABLE IF NOT EXISTS audit_reports (
  cache_key TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  pipeline_version TEXT NOT NULL,
  insufficient_data INTEGER NOT NULL,
  report_json TEXT NOT NULL,
  created_at_iso TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_reports_url_pv
  ON audit_reports(url, pipeline_version);
"""


def _sqlite_path_from_url(db_url: str) -> Path:
    u = (db_url or "").strip()
    if not u:
        raise ValueError("Empty db url")
    if not u.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// URLs are supported for AUDIT_CACHE_DB_URL")
    # sqlite:////abs/path -> path string begins with /
    path_str = u[len("sqlite:///") :]
    p = Path(path_str)
    if not p.is_absolute():
        raise ValueError("sqlite DB path must be absolute (use sqlite:////abs/path)")
    return p


def _connect(db_url: str) -> sqlite3.Connection:
    path = _sqlite_path_from_url(db_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(_DDL)
    return conn


def get_cached_report_sqlite(
    *,
    db_url: str,
    cache_key: str,
) -> AuditReport | InsufficientDataReport | None:
    try:
        with _connect(db_url) as conn:
            row = conn.execute(
                "SELECT insufficient_data, report_json FROM audit_reports WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
    except Exception:  # noqa: BLE001
        logger.warning("SQLite cache read failed for key=%s", cache_key)
        return None
    if row is None:
        return None
    insufficient, report_json = int(row[0]), str(row[1])
    try:
        if insufficient == 1:
            return InsufficientDataReport.model_validate_json(report_json)
        return AuditReport.model_validate_json(report_json)
    except Exception:  # noqa: BLE001
        logger.warning("SQLite cache JSON parse failed for key=%s", cache_key)
        return None


def cache_report_sqlite(
    *,
    db_url: str,
    cache_key: str,
    url: str,
    pipeline_version: str,
    report: AuditReport | InsufficientDataReport,
) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    insufficient = 1 if getattr(report, "insufficient_data", False) else 0
    payload = report.model_dump_json(indent=2)
    with _connect(db_url) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO audit_reports
              (cache_key, url, pipeline_version, insufficient_data, report_json, created_at_iso)
            VALUES
              (?, ?, ?, ?, ?, ?)
            """,
            (cache_key, url, pipeline_version, insufficient, payload, created_at),
        )
        conn.commit()


def clear_cache_sqlite(
    *,
    db_url: str,
    cache_key: str | None,
) -> int:
    with _connect(db_url) as conn:
        if cache_key is not None:
            cur = conn.execute("DELETE FROM audit_reports WHERE cache_key = ?", (cache_key,))
        else:
            cur = conn.execute("DELETE FROM audit_reports")
        conn.commit()
        return int(cur.rowcount or 0)

