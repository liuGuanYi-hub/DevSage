"""Evaluate Agent evidence grounding against expected source files."""

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


def normalize_expected_source(source_path: str) -> str:
    """Compare dataset paths with paths relative to the requested source root."""

    return source_path.removeprefix("sample-data/")


def evaluate() -> dict[str, object]:
    """Run all MVP cases and return aggregate metrics plus bounded failures."""

    cases = load_evaluation_cases()
    runner = AgentRunner(IndexService())
    source_recall_total = 0.0
    fully_grounded = 0
    failures: list[dict[str, object]] = []

    for case in cases:
        state = runner.run(str(case["question"]), "sample-data")
        expected = {
            normalize_expected_source(str(source))
            for source in case.get(
                "agent_expected_sources",
                case.get("expected_sources", []),
            )
        }
        actual = {result.chunk.source_path for result in state.evidence}
        recall = len(expected.intersection(actual)) / len(expected) if expected else 1.0
        source_recall_total += recall
        if expected.issubset(actual):
            fully_grounded += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "category": state.category,
                    "source_recall": round(recall, 4),
                    "missing_sources": sorted(expected - actual),
                    "retrieved_sources": sorted(actual),
                }
            )

    count = len(cases)
    return {
        "questions": count,
        "source_recall_at_5": source_recall_total / count,
        "full_source_case_rate": fully_grounded / count,
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> None:
    metrics = evaluate()
    print("agent_grounding_metrics")
    for name in (
        "questions",
        "source_recall_at_5",
        "full_source_case_rate",
        "failure_count",
    ):
        value = metrics[name]
        if isinstance(value, float):
            print(f"{name}: {value:.4f}")
        else:
            print(f"{name}: {value}")
    print("failure_samples:")
    print(json.dumps(metrics["failures"][:10], ensure_ascii=False))


if __name__ == "__main__":
    main()
