"""Small file caches for derived reports (compare/journey)."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import re
from typing import TypeVar

from pydantic import BaseModel

from backend.config import get_settings

logger = logging.getLogger(__name__)
_SETTINGS = get_settings()

_MD5_HEX = re.compile(r"^[0-9a-f]{32}$")
T = TypeVar("T", bound=BaseModel)


def _dir(name: str) -> Path:
    return (_SETTINGS.audit_cache_dir / name).resolve()


def _hash_key(prefix: str, payload: str) -> str:
    base = f"{prefix}|{payload}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def _path(d: Path, h: str) -> Path:
    if not _MD5_HEX.fullmatch(h):
        raise ValueError("Invalid cache key hash format")
    p = (d / f"{h}.json").resolve()
    if p.parent != d:
        raise ValueError("Resolved cache path is outside cache dir")
    return p


def get_cached_model(cache_name: str, key_hash: str, model: type[T]) -> T | None:
    d = _dir(cache_name)
    try:
        path = _path(d, key_hash)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return model.model_validate(data)
    except Exception:  # noqa: BLE001
        logger.warning("Aux cache parse failed cache=%s key=%s", cache_name, key_hash)
        return None


def put_cached_model(cache_name: str, key_hash: str, obj: BaseModel) -> None:
    d = _dir(cache_name)
    d.mkdir(parents=True, exist_ok=True)
    path = _path(d, key_hash)
    path.write_text(obj.model_dump_json(indent=2), encoding="utf-8")

