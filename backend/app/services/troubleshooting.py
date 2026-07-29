"""Evidence-grouped troubleshooting reports for the offline Agent MVP."""

from __future__ import annotations

from dataclasses import dataclass

from ..retrieval.models import SearchResult


@dataclass(frozen=True)
class TroubleshootingFinding:
    source_type: str
    citations: tuple[str, ...]
    snippets: tuple[str, ...]


@dataclass(frozen=True)
class TroubleshootingReport:
    query: str
    summary: str
    findings: tuple[TroubleshootingFinding, ...]
    next_steps: tuple[str, ...]
    citations: tuple[str, ...]
    evidence_sufficient: bool


def build_troubleshooting_report(
    query: str,
    results: list[SearchResult],
    max_findings_per_source: int = 3,
) -> TroubleshootingReport:
    """Group multi-source evidence without claiming an unsupported root cause."""

    grouped: dict[str, list[SearchResult]] = {}
    for result in results:
        source_type = _source_type(result)
        grouped.setdefault(source_type, []).append(result)

    findings: list[TroubleshootingFinding] = []
    citations: list[str] = []
    for source_type, source_results in grouped.items():
        selected = source_results[:max_findings_per_source]
        finding_citations = tuple(result.citation for result in selected)
        snippets = tuple(_compact(result.chunk.content) for result in selected)
        findings.append(
            TroubleshootingFinding(
                source_type=source_type,
                citations=finding_citations,
                snippets=snippets,
            )
        )
        citations.extend(finding_citations)

    direct_evidence = [result for result in results if result.matched_terms]
    if direct_evidence:
        summary = (
            f"围绕“{query}”整理了 {len(findings)} 类来源证据；"
            "报告不会把检索结果直接等同于唯一根因。"
        )
    else:
        summary = "当前没有足够的直接证据确认故障原因，以下结果只能作为排查线索。"

    next_steps = [
        "逐条核对引用中的文件路径和行号，并与当前运行环境对照。",
        "补充完整错误堆栈、复现步骤和发生时间后再次检索。",
    ]
    if "issue" in grouped:
        next_steps.append("对照历史 Issue 的解决方案，确认当前版本是否仍满足同样前提。")
    if "git_history" in grouped or "git_diff" in grouped:
        next_steps.append("检查相关提交的实际差异，确认变更是否覆盖故障出现前后的配置或代码。")

    return TroubleshootingReport(
        query=query,
        summary=summary,
        findings=tuple(findings),
        next_steps=tuple(next_steps),
        citations=tuple(dict.fromkeys(citations)),
        evidence_sufficient=bool(direct_evidence),
    )


def _source_type(result: SearchResult) -> str:
    if result.chunk.file_type == "issue":
        return "issue"
    if result.chunk.file_type == "git_diff":
        return "git_diff"
    if result.chunk.file_type == "git":
        return "git_history"
    return "knowledge"


def _compact(content: str, limit: int = 280) -> str:
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"
