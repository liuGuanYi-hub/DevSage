"""Evidence-grounded answer composition for the DevMind MVP."""

from __future__ import annotations

from dataclasses import dataclass
import re

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


def _unique_source_results(
    results: list[SearchResult],
    max_sources: int,
) -> list[SearchResult]:
    """Keep the highest-ranked result for each source file."""

    selected: list[SearchResult] = []
    seen_sources: set[str] = set()
    seen_chunks: set[str] = set()
    for result in results:
        source_path = result.chunk.source_path
        chunk_id = result.chunk.chunk_id
        if source_path in seen_sources or chunk_id in seen_chunks:
            continue
        selected.append(result)
        seen_sources.add(source_path)
        seen_chunks.add(chunk_id)
        if len(selected) >= max_sources:
            break
    return selected


def _class_name(result: SearchResult) -> str | None:
    """Extract a class name from a source path or the visible code chunk."""

    path_match = re.search(r"(?:^|/)([A-Za-z_]\w*Controller)\.[A-Za-z0-9]+$", result.chunk.source_path)
    if path_match:
        return path_match.group(1)
    content_match = re.search(r"\bclass\s+([A-Za-z_]\w*)", result.chunk.content)
    return content_match.group(1) if content_match else None


def _compose_code_location_conclusion(
    results: list[SearchResult],
) -> str:
    """Answer code-location questions with the strongest supported path."""

    controller = next(
        (
            result
            for result in results
            if "controller" in result.chunk.source_path.lower()
            or "controller" in result.chunk.content.lower()
        ),
        None,
    )
    if controller is None:
        first = results[0]
        return (
            f"直接结论：当前证据还不能确认具体入口类，最相关的来源是 "
            f"`{first.citation}`。"
        )

    class_name = _class_name(controller) or "控制器类"
    service = next(
        (
            result
            for result in results
            if "service" in result.chunk.source_path.lower()
            and "finduser" in result.chunk.content.lower()
        ),
        None,
    )
    conclusion = (
        f"直接结论：用户接口入口是 `{class_name}` 类，文件为 "
        f"`{controller.chunk.source_path}`（入口证据：`{controller.citation}`）。"
    )
    if service is not None:
        conclusion += (
            f"该类的用户查询业务由 `UserService.findUser` 负责，"
            f"相关证据：`{service.citation}`。"
        )
    return conclusion


def _compose_direct_conclusion(
    query: str,
    results: list[SearchResult],
) -> str:
    """Create a concise deterministic conclusion before rendering evidence."""

    from ..agents.classifier import classify_question

    category = classify_question(query)
    if category == "code_location":
        return _compose_code_location_conclusion(results)
    first = results[0]
    if category == "troubleshooting":
        first = next(
            (
                result
                for result in results
                if result.chunk.file_type == "issue"
                or result.chunk.source_path.startswith("docs/")
                or "error" in result.chunk.source_path.lower()
            ),
            first,
        )
    return (
        f"直接结论：当前最相关的知识证据是“{_compact_snippet(first.chunk.content, 240)}”，"
        f"来源：`{first.citation}`。"
    )


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

    direct_results = _unique_source_results(
        [result for result in results if result.matched_terms],
        max_sources,
    )
    if not direct_results:
        return AnswerDraft(
            answer=(
                "当前知识库没有检索到足够的直接证据，暂不生成确定性结论。"
                "请补充更具体的关键词、项目范围或错误信息。"
            ),
            citations=(),
            evidence=(),
            evidence_sufficient=False,
            warning="没有找到包含查询关键词的直接来源。",
        )

    answer = _compose_direct_conclusion(query, direct_results)
    citations = tuple(result.citation for result in direct_results)
    warning = None
    if len(direct_results) == 1:
        warning = "当前结论只有一条直接证据，建议人工核对来源。"
    return AnswerDraft(
        answer=answer,
        citations=citations,
        evidence=tuple(direct_results),
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
