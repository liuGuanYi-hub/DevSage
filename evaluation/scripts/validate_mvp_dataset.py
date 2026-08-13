"""Validate the DevMind MVP evaluation dataset without third-party packages."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.scripts.dataset_loader import load_evaluation_cases


DATASET_PATH = PROJECT_ROOT / "evaluation/datasets/devmind_mvp_questions.json"
REQUIRED_FIELDS = {
    "id",
    "category",
    "difficulty",
    "question",
    "expected_sources",
    "reference_answer",
    "expected_tools",
}


def validate_dataset() -> list[dict[str, object]]:
    """Load and validate every question and referenced sample file."""

    raw = load_evaluation_cases()
    if not isinstance(raw, list) or len(raw) < 15:
        raise ValueError("dataset must be a list containing at least 15 questions")

    seen_ids: set[str] = set()
    for index, case in enumerate(raw, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"case {index} must be an object")

        missing = REQUIRED_FIELDS - case.keys()
        if missing:
            raise ValueError(f"case {index} is missing fields: {sorted(missing)}")

        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"case {index} has an invalid id")
        if case_id in seen_ids:
            raise ValueError(f"duplicate question id: {case_id}")
        seen_ids.add(case_id)

        for field in ("question", "reference_answer"):
            if not isinstance(case[field], str) or not case[field].strip():
                raise ValueError(f"case {case_id} has an empty {field}")

        for field in ("expected_sources", "expected_tools", "agent_expected_sources"):
            if field == "agent_expected_sources" and field not in case:
                continue
            values = case[field]
            if not isinstance(values, list) or not values:
                raise ValueError(f"case {case_id} must have a non-empty {field} list")
            if not all(isinstance(value, str) and value for value in values):
                raise ValueError(f"case {case_id} has invalid values in {field}")

        expected_aliases = case.get("expected_aliases", [])
        if not isinstance(expected_aliases, list) or not all(
            isinstance(value, str) and value for value in expected_aliases
        ):
            raise ValueError(f"case {case_id} has invalid expected_aliases")

        for source in case["expected_sources"]:
            source_path = PROJECT_ROOT / source
            if Path(source).is_absolute() or not source_path.is_file():
                raise ValueError(
                    f"case {case_id} references missing or absolute source: {source}"
                )

    return raw


def main() -> None:
    cases = validate_dataset()
    categories = sorted({str(case["category"]) for case in cases})
    print(f"PASS: {DATASET_PATH}")
    print(f"questions: {len(cases)}")
    print(f"categories: {', '.join(categories)}")


if __name__ == "__main__":
    main()
