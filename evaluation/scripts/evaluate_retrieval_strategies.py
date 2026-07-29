"""Compare keyword, offline vector and hybrid retrieval on the fixed MVP set."""

from __future__ import annotations

import json
from collections.abc import Callable
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
from backend.app.retrieval.embeddings import HashEmbeddingProvider
from backend.app.retrieval.keyword_search import search_keyword
from backend.app.retrieval.models import SearchResult
from backend.app.retrieval.rrf import reciprocal_rank_fusion, select_source_diverse
from backend.app.retrieval.vector_search import search_vector


SearchStrategy = Callable[[tuple, str, int], list[SearchResult]]


def _hybrid_candidates(
    chunks: tuple,
    query: str,
    top_k: int,
    provider: HashEmbeddingProvider,
) -> list[SearchResult]:
    candidate_k = max(top_k * 4, 10)
    keyword_results = search_keyword(chunks, query, top_k=candidate_k)
    vector_results = search_vector(
        chunks,
        query,
        top_k=candidate_k,
        provider=provider,
    )
    return reciprocal_rank_fusion(
        [keyword_results, vector_results],
        top_k=candidate_k,
    )


def load_cases_and_chunks() -> tuple[list[dict], tuple]:
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    sample_snapshot = build_index(SAMPLE_ROOT)
    config_document = load_document(PROJECT_ROOT / ".env.example", PROJECT_ROOT)
    chunks = (*sample_snapshot.chunks, *split_document(config_document))
    return cases, chunks


def evaluate_strategy(
    strategy: SearchStrategy,
    cases: list[dict],
    chunks: tuple,
    top_k: int = 5,
) -> dict[str, float | int]:
    case_hits = 0
    source_recall_total = 0.0
    reciprocal_rank_total = 0.0

    for case in cases:
        expected = {
            source.removeprefix("sample-data/")
            for source in case["expected_sources"]
        }
        results = strategy(chunks, case["question"], top_k)
        retrieved = [result.chunk.source_path for result in results]
        hits = [
            index + 1
            for index, source in enumerate(retrieved)
            if source in expected
        ]
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


def evaluate(top_k: int = 5) -> dict[str, dict[str, float | int]]:
    """Return comparable metrics for all three deterministic strategies."""

    cases, chunks = load_cases_and_chunks()
    provider = HashEmbeddingProvider(dimension=1024)

    def keyword(items: tuple, query: str, limit: int) -> list[SearchResult]:
        return search_keyword(items, query, top_k=limit)

    def vector(items: tuple, query: str, limit: int) -> list[SearchResult]:
        return search_vector(items, query, top_k=limit, provider=provider)

    def raw_rrf(items: tuple, query: str, limit: int) -> list[SearchResult]:
        return _hybrid_candidates(items, query, limit, provider)[:limit]

    def source_diverse_rerank(
        items: tuple, query: str, limit: int
    ) -> list[SearchResult]:
        candidates = _hybrid_candidates(items, query, limit, provider)
        return select_source_diverse(candidates, top_k=limit, max_per_source=1)

    return {
        name: evaluate_strategy(strategy, cases, chunks, top_k=top_k)
        for name, strategy in (
            ("keyword", keyword),
            ("vector", vector),
            ("hybrid_raw_rrf", raw_rrf),
            ("hybrid_source_diverse", source_diverse_rerank),
        )
    }


def main() -> None:
    metrics = evaluate()
    print("retrieval_strategy_metrics")
    print("strategy | case_recall_at_5 | source_recall_at_5 | mrr")
    for name, values in metrics.items():
        print(
            f"{name} | {values['case_recall_at_5']:.4f} | "
            f"{values['source_recall_at_5']:.4f} | {values['mrr']:.4f}"
        )


if __name__ == "__main__":
    main()
