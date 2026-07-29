"""Evaluate the hybrid baseline with the deterministic offline embedding provider."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "evaluation/datasets/devmind_mvp_questions.json"
SAMPLE_ROOT = PROJECT_ROOT / "sample-data"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.ingestion.chunkers import split_document
from backend.app.ingestion.indexer import build_index
from backend.app.ingestion.loaders import load_document
from backend.app.retrieval.hybrid_search import search_hybrid


def evaluate(top_k: int = 5) -> dict[str, float | int]:
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    sample_snapshot = build_index(SAMPLE_ROOT)
    config_document = load_document(PROJECT_ROOT / ".env.example", PROJECT_ROOT)
    chunks = (*sample_snapshot.chunks, *split_document(config_document))
    case_hits = 0
    source_recall_total = 0.0
    reciprocal_rank_total = 0.0

    for case in cases:
        expected = {
            source.removeprefix("sample-data/")
            for source in case["expected_sources"]
        }
        results = search_hybrid(chunks, case["question"], top_k=top_k)
        retrieved = [result.chunk.source_path for result in results]
        hits = [index + 1 for index, source in enumerate(retrieved) if source in expected]
        if hits:
            case_hits += 1
            reciprocal_rank_total += 1 / min(hits)
        source_recall_total += len(expected.intersection(retrieved)) / len(expected)

    count = len(cases)
    return {
        "questions": count,
        "case_recall_at_5": case_hits / count,
        "source_recall_at_5": source_recall_total / count,
        "mrr": reciprocal_rank_total / count,
    }


def main() -> None:
    metrics = evaluate()
    print("hash_embedding_hybrid_baseline_metrics")
    for name, value in metrics.items():
        if isinstance(value, float):
            print(f"{name}: {value:.4f}")
        else:
            print(f"{name}: {value}")


if __name__ == "__main__":
    main()

