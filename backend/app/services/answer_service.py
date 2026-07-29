"""Evidence-grounded answer composition for the DevMind MVP."""

from __future__ import annotations

from dataclasses import dataclass

from ..retrieval.models import SearchResult


@dataclass(frozen=True)
class AnswerDraft:
    """A deterministic answer draft that never invents unsupported facts."""

    answer: str
    citations: tuple[str, ...]
    evidence: tuple[SearchResult, ...]
    evidence_sufficient: bool
    warning: str | None


def _compact_snippet(content: str, limit: int = 360) -> str:
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def compose_evidence_answer(
    query: str,
    results: list[SearchResult],
    max_sources: int = 5,
) -> AnswerDraft:
    """Compose a source-backed response from direct keyword evidence.

    Vector-only candidates are retained as context but are not treated as
    sufficient evidence until a production embedding and answer model are
    configured.
    """

    direct_results = [result for result in results if result.matched_terms][:max_sources]
    if not direct_results:
        return AnswerDraft(
            answer=(
                "当前知识库没有检索到足够的直接证据，暂不生成确定性结论。"
                "请补充更具体的关键词、项目范围或错误信息。"
            ),
            citations=(),
            evidence=tuple(results[:max_sources]),
            evidence_sufficient=False,
            warning="没有找到包含查询关键词的直接来源。",
        )

    evidence_lines = [
        f"- {result.citation}：{_compact_snippet(result.chunk.content)}"
        for result in direct_results
    ]
    answer = (
        f"针对“{query}”，当前知识库检索到以下直接证据：\n\n"
        + "\n".join(evidence_lines)
        + "\n\n以上内容均来自当前索引文件，请结合来源位置进行最终判断。"
    )
    citations = tuple(result.citation for result in direct_results)
    warning = None
    if len(direct_results) == 1:
        warning = "当前结论只有一条直接证据，建议人工核对来源。"
    return AnswerDraft(
        answer=answer,
        citations=citations,
        evidence=tuple(results[:max_sources]),
        evidence_sufficient=True,
        warning=warning,
    )


def compose_routed_answer(query: str, results: list[SearchResult]) -> AnswerDraft:
    """Select the answer format that matches the shared retrieval category."""

    from ..agents.classifier import classify_question
    from .project_summary import compose_project_summary

    if classify_question(query) == "project_summary":
        return compose_project_summary(query, results)
    return compose_evidence_answer(query, results)
