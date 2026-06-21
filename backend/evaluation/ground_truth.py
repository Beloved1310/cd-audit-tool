"""Expert ground-truth label schema for scoring accuracy validation.

A label file records how a human expert scored each criterion for each of the
four Consumer Duty outcomes, reading the *same* frozen crawl content the pipeline
sees.  Comparing pipeline scores against these labels gives a real accuracy number.

Label file format (JSON):
{
  "site_id": "example-mortgage-firm",
  "url": "https://example.co.uk",
  "labelled_by": "expert_name",
  "labelled_at": "2026-05-10",
  "notes": "General observations about the site.",
  "outcomes": {
    "Products & Services": {
      "notes": "...",
      "criteria": {
        "1": {"awarded": 1, "note": "Product features clearly listed."},
        "2": {"awarded": 0, "note": "No explicit target market statement."},
        ...
        "10": {"awarded": 1, "note": "No obvious info buried behind clicks."}
      }
    },
    "Price & Value": { ... },
    "Consumer Understanding": { ... },
    "Consumer Support": { ... }
  }
}

Criterion IDs 1–10 map directly to the definitions in backend/pipeline/scorer.py.
Each criterion is binary: awarded=1 (met) or awarded=0 (not met).
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


_REQUIRED_OUTCOMES = (
    "Products & Services",
    "Price & Value",
    "Consumer Understanding",
    "Consumer Support",
)


class CriterionLabel(BaseModel):
    awarded: int = Field(ge=0, le=1, description="1 = criterion met, 0 = not met.")
    note: str = Field(default="", description="Optional expert note explaining the decision.")


class OutcomeLabel(BaseModel):
    notes: str = Field(default="")
    criteria: dict[str, CriterionLabel] = Field(
        description="Keyed by criterion_id as string ('1'–'10')."
    )

    @model_validator(mode="after")
    def _validate_criterion_ids(self):
        for k in self.criteria:
            try:
                n = int(k)
            except ValueError:
                raise ValueError(f"Criterion key must be an integer string, got {k!r}")
            if n < 1 or n > 10:
                raise ValueError(f"Criterion id must be 1–10, got {n}")
        missing = [str(i) for i in range(1, 11) if str(i) not in self.criteria]
        if missing:
            raise ValueError(f"Outcome label must include criteria 1–10; missing {missing}")
        return self

    @property
    def score(self) -> int:
        """Sum of awarded points — mirrors how pipeline computes outcome scores."""
        return sum(c.awarded for c in self.criteria.values())


class GroundTruthLabel(BaseModel):
    site_id: str
    url: str
    labelled_by: str = ""
    labelled_at: str = ""
    frozen_at: str = Field(
        default="",
        description="ISO timestamp copied from the paired frozen crawl file at label time.",
    )
    pipeline_version: str = Field(
        default="",
        description="Pipeline version active when labels were created (optional but recommended).",
    )
    notes: str = ""
    outcomes: dict[str, OutcomeLabel]

    @model_validator(mode="after")
    def _all_required_outcomes_present(self):
        missing = [o for o in _REQUIRED_OUTCOMES if o not in self.outcomes]
        if missing:
            raise ValueError(f"Ground truth label missing outcomes: {missing}")
        return self

    def outcome_score(self, outcome_name: str) -> int:
        return self.outcomes[outcome_name].score

    def overall_score(self) -> int:
        scores = [self.outcomes[o].score for o in _REQUIRED_OUTCOMES]
        return round(sum(scores) / len(scores))


def save_ground_truth(label: GroundTruthLabel, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(label.model_dump_json(indent=2), encoding="utf-8")


def load_ground_truth(path: Path | str) -> GroundTruthLabel:
    raw = Path(path).read_text(encoding="utf-8")
    return GroundTruthLabel.model_validate_json(raw)


def is_synthetic_expert_label(label: GroundTruthLabel) -> bool:
    """True when labels are fixture-generated, not independent expert review."""
    by = (label.labelled_by or "").strip().lower()
    if not by:
        return True
    if by.startswith("synthetic") or by.startswith("draft_from"):
        return True
    return by in ("fixture", "auto", "test", "your_site_id", "expert_name_or_team")


def validate_label_matches_frozen(
    label: GroundTruthLabel,
    frozen: dict,
    *,
    require_frozen_at: bool = False,
) -> list[str]:
    """Return human-readable errors if label metadata does not match frozen crawl."""
    from backend.util.url_norm import canonical_url

    errors: list[str] = []
    frozen_site = (frozen.get("site_id") or "").strip()
    if frozen_site and label.site_id != frozen_site:
        errors.append(f"site_id mismatch: label={label.site_id!r} frozen={frozen_site!r}")

    frozen_url = canonical_url(str(frozen.get("url") or ""))
    label_url = canonical_url(label.url)
    if frozen_url and label_url and frozen_url != label_url:
        errors.append(f"url mismatch: label={label_url!r} frozen={frozen_url!r}")

    frozen_at = (frozen.get("frozen_at") or "").strip()
    if require_frozen_at and not (label.frozen_at or "").strip():
        errors.append("label missing frozen_at — copy from the paired frozen crawl file")
    elif frozen_at and (label.frozen_at or "").strip() and label.frozen_at.strip() != frozen_at:
        errors.append(
            f"frozen_at mismatch: label={label.frozen_at!r} frozen={frozen_at!r} "
            "(re-label or update frozen_at if crawl was re-frozen)",
        )
    return errors


def load_all_ground_truth(directory: Path | str) -> dict[str, GroundTruthLabel]:
    """Load all *.json label files from a directory, keyed by site_id."""
    out: dict[str, GroundTruthLabel] = {}
    for p in sorted(Path(directory).glob("*.json")):
        if p.name.startswith("_"):
            continue
        label = load_ground_truth(p)
        out[label.site_id] = label
    return out
