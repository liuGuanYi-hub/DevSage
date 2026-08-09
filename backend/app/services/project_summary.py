"""Evidence-grounded project summary composition."""

from __future__ import annotations

import re

from ..retrieval.models import SearchResult
from .answer_service import AnswerDraft


def compose_project_summary(
    query: str,
    results: list[SearchResult],
    max_sources: int = 8,
) -> AnswerDraft:
    """Build a structured summary from directly matched project evidence."""

    direct_results = _unique_source_results(
        [result for result in results if result.matched_terms],
        max_sources,
    )
    if not direct_results:
        return AnswerDraft(
            answer=(
                "当前没有足够的项目直接证据生成总结，暂不输出确定性架构结论。"
                "请补充项目名、模块名、技术栈或关键入口。"
            ),
            citations=(),
            evidence=tuple(_unique_source_results(results, max_sources)),
            evidence_sufficient=False,
            warning="项目总结需要至少一条带关键词命中的来源。",
        )

    responsibility_lines = _render_responsibilities(direct_results)
    answer = (
        f"项目总结：文件职责（基于查询“{query}”的当前索引证据）\n\n"
        + responsibility_lines
        + "\n\n边界：以上是来源驱动的检索摘要，不代表完整架构审计；请按引用路径和行号继续核对。"
    )
    citations = tuple(result.citation for result in direct_results)
    warning = None
    if len(direct_results) < 2:
        warning = "当前项目总结来源较少，建议补充更具体的模块或技术关键词。"
    return AnswerDraft(
        answer=answer,
        citations=citations,
        evidence=tuple(direct_results),
        evidence_sufficient=True,
        warning=warning,
    )


def _unique_source_results(
    results: list[SearchResult],
    max_sources: int,
) -> list[SearchResult]:
    selected: list[SearchResult] = []
    seen_sources: set[str] = set()
    for result in results:
        if result.chunk.source_path in seen_sources:
            continue
        selected.append(result)
        seen_sources.add(result.chunk.source_path)
        if len(selected) >= max_sources:
            break
    return selected


def _render_responsibilities(results: list[SearchResult]) -> str:
    lines = ["已确认的文件职责："]
    for result in results:
        lines.append(
            f"- `{result.chunk.source_path}`：{_infer_file_role(result)} "
            f"（来源：`{result.citation}`）"
        )
    return "\n".join(lines)


def _infer_file_role(result: SearchResult) -> str:
    """Infer a conservative responsibility from path and visible evidence."""

    path = result.chunk.source_path.replace("\\", "/")
    normalized_path = path.lower()
    content = result.chunk.content.lower()

    if normalized_path.endswith("readme.md"):
        return "项目结构、运行方式和示例接口说明"
    if "service" in normalized_path or re.search(r"\bclass\s+\w*service\b", content):
        if "finduser" in content:
            return "用户查询业务逻辑，构造用户返回对象"
        return "业务服务逻辑"
    if "controller" in normalized_path or "controller" in content:
        if "getuser" in content or "userservice" in content:
            return "用户接口入口，接收用户请求并调用 UserService"
        return "用户接口入口和请求处理"
    if normalized_path.endswith((".yml", ".yaml", ".env.example")):
        return "应用运行配置，例如服务端口和环境变量"
    if "/routes/" in normalized_path or normalized_path.endswith("routes.php"):
        return "HTTP 路由入口和接口访问边界"
    if "middleware" in normalized_path:
        return "认证或权限中间件"
    if normalized_path.endswith("project_scaffold.py"):
        return "项目脚手架创建和项目状态文件初始化"
    if normalized_path.endswith("migrate_legacy.py"):
        return "旧目录内容迁移和归档"
    if normalized_path.endswith("kb_audit.py"):
        return "知识库文件扫描、引用检查和审计报告生成"
    if "/scripts/" in normalized_path:
        return "知识库或项目维护辅助脚本"
    if result.chunk.file_type == "markdown":
        heading = re.search(r"^#{1,3}\s+(.+)$", result.chunk.content, flags=re.MULTILINE)
        if heading:
            return f"知识文档：{heading.group(1).strip()[:80]}"
        return "知识说明文档"
    return "相关配置或实现证据"
