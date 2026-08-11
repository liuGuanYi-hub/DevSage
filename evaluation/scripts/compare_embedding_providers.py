"""Compare the deterministic Hash baseline with a real local BGE/E5 model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = PROJECT_ROOT / "evaluation/reports/local-embedding-comparison"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.retrieval.embeddings import (
    EmbeddingProvider,
    HashEmbeddingProvider,
    LocalSentenceTransformerEmbeddingProvider,
)
from backend.app.retrieval.keyword_search import search_keyword
from backend.app.retrieval.models import SearchResult
from backend.app.retrieval.rrf import reciprocal_rank_fusion, select_source_diverse
from backend.app.retrieval.vector_search import search_vector
from evaluation.scripts.evaluate_retrieval_strategies import (
    evaluate_strategy,
    load_cases_and_chunks,
)


def _hybrid_candidates(
    chunks: tuple,
    query: str,
    top_k: int,
    provider: EmbeddingProvider,
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
        weights=(1.25, 0.75),
    )


def _provider_metrics(
    label: str,
    provider: EmbeddingProvider,
    cases: list[dict],
    chunks: tuple,
    top_k: int,
) -> dict[str, dict[str, float | int]]:
    def vector(items: tuple, query: str, limit: int) -> list[SearchResult]:
        return search_vector(items, query, top_k=limit, provider=provider)

    def hybrid(items: tuple, query: str, limit: int) -> list[SearchResult]:
        candidates = _hybrid_candidates(items, query, limit, provider)
        return select_source_diverse(candidates, top_k=limit, max_per_source=1)

    return {
        f"{label}_vector": evaluate_strategy(vector, cases, chunks, top_k),
        f"{label}_hybrid_source_diverse": evaluate_strategy(
            hybrid, cases, chunks, top_k
        ),
    }


def compare(
    model_name: str = "BAAI/bge-small-zh-v1.5",
    cache_folder: str | None = "data/models",
    top_k: int = 5,
) -> dict[str, object]:
    """Run both providers against the same fixed 75-question dataset."""

    cases, chunks = load_cases_and_chunks()

    def keyword(items: tuple, query: str, limit: int) -> list[SearchResult]:
        return search_keyword(items, query, top_k=limit)

    metrics: dict[str, dict[str, float | int]] = {
        "keyword": evaluate_strategy(keyword, cases, chunks, top_k)
    }
    metrics.update(
        _provider_metrics(
            "hash",
            HashEmbeddingProvider(dimension=1024), cases, chunks, top_k
        )
    )
    local_provider = LocalSentenceTransformerEmbeddingProvider(
        model_name=model_name,
        cache_folder=cache_folder,
    )
    metrics.update(_provider_metrics("local_bge", local_provider, cases, chunks, top_k))
    return {
        "model": model_name,
        "questions": len(cases),
        "chunk_count": len(chunks),
        "top_k": top_k,
        "local_dimension": local_provider.dimension,
        "metrics": metrics,
    }


def _metric_names(metrics: dict[str, dict[str, float | int]]) -> list[str]:
    names = ["case_recall_at_5", "source_recall_at_5", "mrr"]
    if any("expected_alias_recall_at_5" in values for values in metrics.values()):
        names.append("expected_alias_recall_at_5")
    return names


def _render_table(report: dict[str, object]) -> str:
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    names = _metric_names(metrics)
    lines = [
        "# 本地 Embedding 与 Hash 基线召回对比",
        "",
        f"- 评测问题：{report['questions']} 道",
        f"- Chunk：{report['chunk_count']} 个",
        f"- Top-K：{report['top_k']}",
        f"- 本地模型：`{report['model']}`",
        f"- 本地向量维度：`{report['local_dimension']}`",
        "",
        "| 策略 | " + " | ".join(names) + " |",
        "| --- | " + " | ".join("---:" for _ in names) + " |",
    ]
    for strategy, values in metrics.items():
        assert isinstance(values, dict)
        rendered = [f"{float(values[name]):.4f}" for name in names]
        lines.append(f"| {strategy} | " + " | ".join(rendered) + " |")
    lines.extend(
        [
            "",
            "说明：Hash 是离线确定性基线；local_* 使用真实本地 SentenceTransformer 模型。",
            "当前 PostgreSQL pgvector 表为 1024 维，本报告先在内存检索上比较本地模型；",
            "若本地模型维度不是 1024，不会自动写入现有 PostgreSQL 索引。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="BAAI/bge-small-zh-v1.5",
        help="Hugging Face model name or local model directory",
    )
    parser.add_argument("--cache-folder", default="data/models")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_REPORT.with_suffix(".json"))
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=DEFAULT_REPORT.with_suffix(".md"),
    )
    args = parser.parse_args()
    if not 1 <= args.top_k <= 20:
        parser.error("--top-k must be between 1 and 20")

    report = compare(
        model_name=args.model,
        cache_folder=args.cache_folder,
        top_k=args.top_k,
    )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(_render_table(report), encoding="utf-8")

    print(_render_table(report))


if __name__ == "__main__":
    main()
