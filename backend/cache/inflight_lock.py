"""In-flight lock to prevent concurrent overlapping audits for same key.

This is best-effort. With SQLite enabled (AUDIT_CACHE_DB_URL), the lock is shared
across processes using a DB table. Without SQLite, a filesystem lock file is used.
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from backend.config import get_settings

_SETTINGS = get_settings()

_LOCK_TTL_SECONDS_DEFAULT: Final[int] = 15 * 60


def _lock_ttl_seconds() -> int:
    raw = (os.getenv("AUDIT_INFLIGHT_LOCK_TTL_SECONDS") or "").strip()
    if not raw:
        return _LOCK_TTL_SECONDS_DEFAULT
    try:
        v = int(raw)
    except ValueError:
        return _LOCK_TTL_SECONDS_DEFAULT
    return max(5, min(v, 24 * 60 * 60))


def _sqlite_path_from_url(db_url: str) -> Path:
    u = (db_url or "").strip()
    if not u.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// supported for in-flight locks")
    path_str = u[len("sqlite:///") :]
    p = Path(path_str)
    if not p.is_absolute():
        raise ValueError("sqlite DB path must be absolute")
    return p


_LOCKS_DDL: Final[str] = """
CREATE TABLE IF NOT EXISTS audit_inflight_locks (
  lock_key TEXT PRIMARY KEY,
  expires_at REAL NOT NULL
);
"""


def _connect_sqlite(db_url: str) -> sqlite3.Connection:
    path = _sqlite_path_from_url(db_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=1.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_LOCKS_DDL)
    return conn


@dataclass(frozen=True)
class InflightLock:
    key: str
    backend: str  # "sqlite" | "file"
    token: str


def acquire_inflight_lock(*, key: str) -> InflightLock | None:
    db_url = (os.getenv("AUDIT_CACHE_DB_URL") or "").strip() or (_SETTINGS.audit_cache_db_url or "").strip()
    ttl = _lock_ttl_seconds()
    now = time.time()
    expires_at = now + ttl

    if db_url:
        try:
            with _connect_sqlite(db_url) as conn:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute("DELETE FROM audit_inflight_locks WHERE expires_at <= ?", (now,))
                cur = conn.execute(
                    "INSERT OR IGNORE INTO audit_inflight_locks(lock_key, expires_at) VALUES(?, ?)",
                    (key, expires_at),
                )
                conn.execute("COMMIT;")
                if int(cur.rowcount or 0) == 1:
                    return InflightLock(key=key, backend="sqlite", token=db_url)
                return None
        except Exception:
            return None

    cache_dir = (
        Path((os.getenv("AUDIT_CACHE_DIR") or "").strip())
        if (os.getenv("AUDIT_CACHE_DIR") or "").strip()
        else _SETTINGS.audit_cache_dir
    ).resolve()
    lock_dir = (cache_dir / "_locks").resolve()
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = (lock_dir / f"{key}.lock").resolve()
    if lock_path.parent != lock_dir:
        return None

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, str(expires_at).encode("utf-8"))
        finally:
            os.close(fd)
        return InflightLock(key=key, backend="file", token=str(lock_path))
    except FileExistsError:
        try:
            txt = lock_path.read_text(encoding="utf-8").strip()
            old_exp = float(txt) if txt else 0.0
            if old_exp <= now:
                lock_path.unlink(missing_ok=True)
                return acquire_inflight_lock(key=key)
        except Exception:
            return None
        return None


def release_inflight_lock(lock: InflightLock) -> None:
    if lock.backend == "sqlite":
        db_url = lock.token
        try:
            with _connect_sqlite(db_url) as conn:
                conn.execute("DELETE FROM audit_inflight_locks WHERE lock_key = ?", (lock.key,))
                conn.commit()
        except Exception:
            return
        return

    if lock.backend == "file":
        try:
            Path(lock.token).unlink(missing_ok=True)
        except Exception:
            return

