"""Pipeline versioning helpers.

Used to make caching and report metadata reproducible when prompts/criteria change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def _hash_bytes(parts: list[bytes]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
        h.update(b"\n")
    return h.hexdigest()


def compute_pipeline_version() -> str:
    """Return a short, stable version string for the current pipeline logic."""
    root = Path(__file__).resolve().parents[1]
    prompts_dir = root / "prompts"
    scorer_path = root / "pipeline" / "scorer.py"

    parts: list[bytes] = [b"cd-audit-pipeline:v1"]

    if scorer_path.is_file():
        parts.append(scorer_path.read_bytes())

    if prompts_dir.is_dir():
        for p in sorted(prompts_dir.glob("*.txt")):
            parts.append(p.name.encode("utf-8"))
            parts.append(p.read_bytes())

    digest = _hash_bytes(parts)
    return f"p_{digest[:12]}"

