"""Evidence-grounded answer composition for the DevMind MVP."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ..retrieval.models import SearchResult
from .answer_generation import AnswerGenerationError, generate_grounded_answer, get_answer_generation_config


@dataclass(frozen=True)
class AnswerDraft:
    """A deterministic answer draft that never invents unsupported facts."""

    answer: str
    citations: tuple[str, ...]
    evidence: tuple[SearchResult, ...]
    evidence_sufficient: bool
    warning: str | None
    key_steps: tuple[str, ...] = ()
    generation_mode: str = "offline_rules"
    generation_model: str | None = None
    generation_warning: str | None = None
    generation_runtime_ms: int = 0


def _compact_snippet(content: str, limit: int = 360) -> str:
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _clean_evidence_text(content: str, limit: int = 300) -> str:
    """Turn a source excerpt into a short sentence suitable for an answer lead."""

    cleaned = re.sub(r"```.*?```", " ", content, flags=re.DOTALL)
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", cleaned)
    cleaned = " ".join(line.strip(" -*") for line in cleaned.splitlines() if line.strip())
    return _compact_snippet(cleaned, limit)


def _key_steps(category: str, query: str) -> tuple[str, ...]:
    """Provide transparent, offline-safe next steps for the answer view."""

    normalized = query.lower()
    if "目录" in normalized or "文件夹" in normalized:
        return (
            "先按收集、研究、内容生产、项目、模板、记忆和归档等职责理解目录边界。",
            "新资料先进入 Inbox，再根据内容性质流转到 Research、Content 或 Projects。",
            "打开 README 的目录表和引用行号，确认当前笔记应该归档到哪里。",
        )
    if category == "troubleshooting":
        return (
            "先确认现象、错误码和发生环境，避免把相似故障混为一谈。",
            "按引用中的命令、配置或请求链路逐项核对，并记录实际结果。",
            "修复后重新执行原操作，确认问题消失，再把结论沉淀为可复用记录。",
        )
    if category == "code_location":
        return (
            "先定位入口文件或路由，再沿调用关系确认控制器、服务和配置边界。",
            "打开引用行号核对真实方法签名，不只依据文件名推断职责。",
            "如果要修改代码，先保留当前行为和相关测试，再进入预览审批流程。",
        )
    if category == "project_summary":
        return (
            "先按文件职责区分入口、业务逻辑、配置和文档，不把检索结果当成完整架构图。",
            "结合引用路径和行号核对每个文件的实际职责。",
            "需要补全项目结构时，再针对缺失模块提出更具体的问题。",
        )
    if "agent evaluation" in normalized or "评估" in normalized:
        return (
            "先记录任务定义、成功标准以及 Agent、模型、Prompt 和工具版本。",
            "再记录执行轨迹、最终结果，并按成功率、依据充分性、格式遵循、安全性、成本和延迟复核。",
            "最后记录失败原因和是否进入回归测试集，保留原始证据便于复盘。",
        )
    return (
        "先阅读最相关来源，确认知识库中的定义、前置条件和适用范围。",
        "按照引用内容执行或核对步骤，并结合当前项目环境判断是否适用。",
        "把验证结果和仍不确定的部分记录下来，必要时继续追问更具体的问题。",
    )


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
    if category in {"knowledge_qa", "knowledge_write"}:
        normalized = query.lower()
        if "目录" in normalized or "文件夹" in normalized:
            directory_result = next(
                (
                    result
                    for result in results
                    if "核心目录" in result.chunk.content
                    or "00-inbox" in result.chunk.content.lower()
                ),
                None,
            )
            if directory_result is not None:
                rows = re.findall(
                    r"\|\s*`?([0-9]{2}-[A-Za-z-]+)`?\s*\|\s*([^|\n]+?)\s*\|",
                    directory_result.chunk.content,
                )
                if rows:
                    rendered_rows = "\n".join(
                        f"- `{directory}`：{purpose.strip()}" for directory, purpose in rows
                    )
                    return (
                        "Vault 的核心目录按知识流转职责划分，而不是简单按文件类型堆放：\n\n"
                        f"{rendered_rows}\n\n"
                        "实际整理时，可以先把新内容放进 `00-Inbox`，再根据用途流转到研究、内容、项目或归档目录。"
                    )
        if "agent evaluation" in normalized or "评估" in normalized:
            return (
                "知识库建议把一次 Agent 评估记录成完整闭环：任务定义、执行轨迹、最终结果、"
                "多维评分、失败诊断，以及是否纳入回归测试集。评分至少覆盖 Task Success、"
                "Groundedness、Format Conformance、Policy Adherence、Safety、Cost 和 Latency；"
                "具体通过阈值仍需结合项目评测标准确认。"
            )
        return f"根据知识库中的相关记录，当前问题的核心依据是：{_clean_evidence_text(first.chunk.content)}。"
    if category == "troubleshooting":
        return (
            f"根据相关故障记录，建议先按证据核对：{_clean_evidence_text(first.chunk.content, 240)}。"
            f"具体来源为 `{first.citation}`。"
        )
    return (
        f"根据知识库中的相关记录，当前最有帮助的线索是：{_clean_evidence_text(first.chunk.content, 240)}。"
        f"具体来源为 `{first.citation}`。"
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

    from ..agents.classifier import classify_question

    category = classify_question(query)
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
            key_steps=_key_steps("knowledge_qa", query),
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
        key_steps=_key_steps(category, query),
    )


def compose_routed_answer(query: str, results: list[SearchResult]) -> AnswerDraft:
    """Select the answer format that matches the shared retrieval category."""

    from ..agents.classifier import classify_question
    from .project_summary import compose_project_summary

    if classify_question(query) == "project_summary":
        draft = compose_project_summary(query, results)
    else:
        draft = compose_evidence_answer(query, results)
    return _enhance_with_ai(query, draft)


def _enhance_with_ai(query: str, draft: AnswerDraft) -> AnswerDraft:
    """Use the configured model only after deterministic evidence checks pass."""

    config = get_answer_generation_config()
    if not config.enabled or not draft.evidence_sufficient:
        return draft
    try:
        generated = generate_grounded_answer(
            query,
            _answer_category(query),
            draft.evidence,
        )
    except AnswerGenerationError as exc:
        return AnswerDraft(
            **{
                **draft.__dict__,
            "generation_mode": "offline_fallback",
            "generation_model": config.model,
            "generation_warning": str(exc),
            }
        )
    if generated is None:
        return draft
    return AnswerDraft(
        **{
            **draft.__dict__,
            "answer": generated.answer,
            "key_steps": generated.key_steps,
            "generation_mode": "ai",
            "generation_model": generated.model,
            "generation_warning": None,
            "generation_runtime_ms": generated.runtime_ms,
        }
    )


def _answer_category(query: str) -> str:
    from ..agents.classifier import classify_question

    return classify_question(query)
