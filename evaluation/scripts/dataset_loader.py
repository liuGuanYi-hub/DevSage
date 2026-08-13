"""Load the base evaluation set plus human-approved feedback cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DATASET_PATH = PROJECT_ROOT / "evaluation/datasets/devmind_mvp_questions.json"
CONFIRMED_FEEDBACK_PATH = PROJECT_ROOT / "data/feedback/confirmed-evaluation.jsonl"


def load_evaluation_cases() -> list[dict[str, Any]]:
    """Return stable base cases followed by human-approved feedback cases."""

    raw = json.loads(BASE_DATASET_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("base evaluation dataset must be a list")
    cases = [item for item in raw if isinstance(item, dict)]
    if CONFIRMED_FEEDBACK_PATH.is_file():
        for line_number, line in enumerate(
            CONFIRMED_FEEDBACK_PATH.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"confirmed feedback line {line_number} is invalid") from exc
            if not isinstance(item, dict):
                raise ValueError(f"confirmed feedback line {line_number} must be an object")
            cases.append(item)
    return cases
