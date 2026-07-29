"""Evaluate deterministic context and answer-quality proxies for the MVP."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "evaluation/datasets/devmind_mvp_questions.json"
SAMPLE_ROOT = PROJECT_ROOT / "sample-data"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.ingestion.chunkers import split_document
from backend.app.ingestion.indexer import build_index
from backend.app.ingestion.loaders import load_document
from backend.app.retrieval.hybrid_search import search_hybrid
from backend.app.retrieval.keyword_search import tokenize
from backend.app.services.answer_service import compose_evidence_answer
from backend.app.services.index_service import _expand_code_query


def _terms(value: str) -> set[str]:
    return set(tokenize(value))


def lexical_precision(candidate: str, reference: str) -> float:
    """Return the fraction of candidate terms found in the reference."""

    candidate_terms = _terms(candidate)
    reference_terms = _terms(reference)
    if not candidate_terms:
        return 0.0
    return len(candidate_terms & reference_terms) / len(candidate_terms)


def lexical_recall(candidate: str, reference: str) -> float:
    """Return the fraction of reference terms found in the candidate."""

    candidate_terms = _terms(candidate)
    reference_terms = _terms(reference)
    if not reference_terms:
        return 0.0
    return len(candidate_terms & reference_terms) / len(reference_terms)


def lexical_f1(candidate: str, reference: str) -> float:
    """Return a transparent lexical F1 proxy, not an LLM quality score."""

    candidate_terms = _terms(candidate)
    reference_terms = _terms(reference)
    if not candidate_terms or not reference_terms:
        return 0.0
    overlap = len(candidate_terms & reference_terms)
    precision = overlap / len(candidate_terms)
    recall = overlap / len(reference_terms)
    if not precision + recall:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _normalise_source(source: str) -> str:
    return source.removeprefix("sample-data/")


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def evaluate(top_k: int = 5) -> dict[str, object]:
    """Evaluate source-level context quality and deterministic answer proxies."""

    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    sample_snapshot = build_index(SAMPLE_ROOT)
    config_document = load_document(PROJECT_ROOT / ".env.example", PROJECT_ROOT)
    chunks = (*sample_snapshot.chunks, *split_document(config_document))

    context_precisions: list[float] = []
    unique_source_precisions: list[float] = []
    context_recalls: list[float] = []
    answer_relevances: list[float] = []
    reference_recalls: list[float] = []
    faithfulness_proxies: list[float] = []
    evidence_sufficient = 0
    failures: list[dict[str, object]] = []

    for case in cases:
        expected = {_normalise_source(source) for source in case["expected_sources"]}
        # Mirror IndexService.search_hybrid so the quality report measures the
        # production query preprocessing rather than the raw low-level baseline.
        results = search_hybrid(
            chunks,
            _expand_code_query(case["question"]),
            top_k=top_k,
        )
        retrieved = [result.chunk.source_path for result in results]
        relevant_count = len(expected.intersection(retrieved))
        precision = relevant_count / len(retrieved) if retrieved else 0.0
        unique_retrieved = list(dict.fromkeys(retrieved))
        unique_precision = (
            relevant_count / len(unique_retrieved) if unique_retrieved else 0.0
        )
        recall = relevant_count / len(expected) if expected else 0.0

        draft = compose_evidence_answer(case["question"], results)
        evidence_text = "\n".join(result.chunk.content for result in draft.evidence)
        relevance = lexical_f1(draft.answer, case["reference_answer"])
        reference_recall = lexical_recall(draft.answer, case["reference_answer"])
        faithfulness = lexical_precision(draft.answer, evidence_text)

        context_precisions.append(precision)
        unique_source_precisions.append(unique_precision)
        context_recalls.append(recall)
        answer_relevances.append(relevance)
        reference_recalls.append(reference_recall)
        faithfulness_proxies.append(faithfulness)
        evidence_sufficient += int(draft.evidence_sufficient)

        if recall < 1.0 or reference_recall < 0.5:
            failures.append(
                {
                    "id": case["id"],
                    "context_recall": round(recall, 4),
                    "answer_relevance_proxy": round(relevance, 4),
                    "reference_term_recall": round(reference_recall, 4),
                    "expected_sources": sorted(expected),
                    "retrieved_sources": retrieved,
                }
            )

    count = len(cases)
    return {
        "questions": count,
        "context_precision_at_5": _mean(context_precisions),
        "unique_source_precision_at_5": _mean(unique_source_precisions),
        "context_recall_at_5": _mean(context_recalls),
        "answer_relevance_proxy_f1": _mean(answer_relevances),
        "reference_term_recall": _mean(reference_recalls),
        "faithfulness_proxy_precision": _mean(faithfulness_proxies),
        "evidence_sufficient_rate": evidence_sufficient / count if count else 0.0,
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> None:
    metrics = evaluate()
    print("context_quality_metrics")
    for name, value in metrics.items():
        if isinstance(value, float):
            print(f"{name}: {value:.4f}")
        elif name == "failures":
            print(json.dumps(value[:10], ensure_ascii=False))
        else:
            print(f"{name}: {value}")


if __name__ == "__main__":
    main()
