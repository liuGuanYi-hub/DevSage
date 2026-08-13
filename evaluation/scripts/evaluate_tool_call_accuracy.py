"""Evaluate whether the offline Agent calls each expected tool at least once."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "evaluation/datasets/devmind_mvp_questions.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agents.runner import AgentRunner
from backend.app.services.index_service import IndexService
from evaluation.scripts.dataset_loader import load_evaluation_cases


def evaluate() -> dict[str, float | int]:
    cases = load_evaluation_cases()
    runner = AgentRunner(IndexService())
    coverage_total = 0.0
    fully_covered = 0
    for case in cases:
        state = runner.run(str(case["question"]), "sample-data")
        expected = set(case["expected_tools"])
        actual = set(state.tool_calls)
        coverage = len(expected.intersection(actual)) / len(expected)
        coverage_total += coverage
        if expected.issubset(actual):
            fully_covered += 1

    count = len(cases)
    return {
        "questions": count,
        "expected_tool_coverage": coverage_total / count,
        "fully_covered_case_rate": fully_covered / count,
    }


def main() -> None:
    metrics = evaluate()
    print("tool_call_accuracy_metrics")
    for name, value in metrics.items():
        if isinstance(value, float):
            print(f"{name}: {value:.4f}")
        else:
            print(f"{name}: {value}")


if __name__ == "__main__":
    main()
