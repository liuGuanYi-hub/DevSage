"""Evidence-grounded project summary composition."""

from __future__ import annotations

from ..retrieval.models import SearchResult
from .answer_service import AnswerDraft


def compose_project_summary(
    query: str,
    results: list[SearchResult],
    max_sources: int = 8,
) -> AnswerDraft:
    """Build a structured summary from directly matched project evidence."""

    direct_results = [result for result in results if result.matched_terms][:max_sources]
    if not direct_results:
        return AnswerDraft(
            answer=(
                "当前没有足够的项目直接证据生成总结，暂不输出确定性架构结论。"
                "请补充项目名、模块名、技术栈或关键入口。"
            ),
            citations=(),
            evidence=tuple(results[:max_sources]),
            evidence_sufficient=False,
            warning="项目总结需要至少一条带关键词命中的来源。",
        )

    document_lines = _render_group(
        "文档与配置证据",
        [result for result in direct_results if result.chunk.file_type != "code"],
    )
    code_lines = _render_group(
        "代码证据",
        [result for result in direct_results if result.chunk.file_type == "code"],
    )
    sections = [section for section in (document_lines, code_lines) if section]
    answer = (
        f"项目总结（基于查询“{query}”的当前索引证据）\n\n"
        + "\n\n".join(sections)
        + "\n\n边界：以上是来源驱动的检索摘要，不代表完整架构审计；请按引用路径和行号继续核对。"
    )
    citations = tuple(result.citation for result in direct_results)
    warning = None
    if len(direct_results) < 2:
        warning = "当前项目总结来源较少，建议补充更具体的模块或技术关键词。"
    return AnswerDraft(
        answer=answer,
        citations=citations,
        evidence=tuple(results[:max_sources]),
        evidence_sufficient=True,
        warning=warning,
    )


def _render_group(title: str, results: list[SearchResult]) -> str:
    if not results:
        return ""
    lines = [f"{title}："]
    for result in results:
        snippet = " ".join(result.chunk.content.split())
        if len(snippet) > 320:
            snippet = snippet[:319].rstrip() + "…"
        lines.append(f"- {result.citation}：{snippet}")
    return "\n".join(lines)
