"""Load prompt templates from ``backend/prompts/``."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt_text(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
