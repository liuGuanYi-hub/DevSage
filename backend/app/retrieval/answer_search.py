"""Category-aware retrieval for evidence-grounded answers."""

from __future__ import annotations

from collections.abc import Iterable

from ..agents.classifier import classify_question
from ..ingestion.models import ChunkRecord
from .embeddings import EmbeddingProvider
from .hybrid_search import search_hybrid
from .keyword_search import search_keyword
from .models import SearchResult
from .rrf import reciprocal_rank_fusion, select_source_diverse


def search_answer_chunks(
    chunks: Iterable[ChunkRecord],
    query: str,
    top_k: int = 5,
    provider: EmbeddingProvider | None = None,
) -> tuple[str, list[SearchResult]]:
    """Route answer retrieval by question type using the Agent's evidence rules.

    The low-level hybrid search remains available as a measurement baseline. This
    function is the shared answer path: code-location questions prioritize code,
    project summaries use a wider multi-source budget, and other questions retain
    the general hybrid strategy.
    """

    if top_k <= 0:
        return classify_question(query), []

    chunk_list = list(chunks)
    category = classify_question(query)
    if category == "code_location":
        return category, _search_code_location(chunk_list, query, top_k, provider)
    if category == "project_summary":
        return category, _search_project_summary(chunk_list, query, max(top_k, 8), provider)
    return category, search_hybrid(
        chunk_list,
        _expand_code_query(query),
        top_k=top_k,
        provider=provider,
    )


def _search_code_location(
    chunks: list[ChunkRecord],
    query: str,
    top_k: int,
    provider: EmbeddingProvider | None,
) -> list[SearchResult]:
    code_chunks = [
        chunk
        for chunk in chunks
        if _is_code_chunk(chunk, query)
    ]
    code_results = select_source_diverse(
        search_keyword(
            code_chunks,
            _expand_code_query(query),
            top_k=max(top_k * 4, 10),
        ),
        top_k=top_k,
        max_per_source=1,
    )

    document_results: list[SearchResult] = []
    if _code_location_needs_documents(query):
        document_chunks = [chunk for chunk in chunks if _is_document_chunk(chunk, query)]
        document_results = [
            result
            for result in search_hybrid(
                document_chunks,
                _expand_supporting_document_query(query),
                top_k=top_k * 2,
                provider=provider,
            )
            if _is_document_chunk(result.chunk, query)
        ][:top_k]

    if document_results:
        return reciprocal_rank_fusion(
            [code_results, document_results],
            top_k=top_k,
        )
    return code_results


def _search_project_summary(
    chunks: list[ChunkRecord],
    query: str,
    top_k: int,
    provider: EmbeddingProvider | None,
) -> list[SearchResult]:
    document_chunks = [chunk for chunk in chunks if _is_document_chunk(chunk, query)]
    document_results = search_hybrid(
        document_chunks,
        query,
        top_k=top_k * 2,
        provider=provider,
    )
    code_chunks = [
        chunk
        for chunk in chunks
        if _is_code_chunk(chunk, query)
    ]
    code_results = search_keyword(
        code_chunks,
        _expand_code_query(query),
        top_k=top_k * 2,
    )
    fused = reciprocal_rank_fusion(
        [document_results, code_results],
        top_k=top_k * 4,
    )
    return select_source_diverse(fused, top_k=top_k, max_per_source=1)


def _is_document_chunk(chunk: ChunkRecord, query: str = "") -> bool:
    """Keep project docs and config while excluding exported operational records."""

    if chunk.file_type == "markdown":
        return True
    return (
        chunk.file_type == "config"
        and not chunk.source_path.startswith(("issues/", "git/"))
        and _is_sensitive_config_query(query, chunk)
    )


def _is_code_chunk(chunk: ChunkRecord, query: str) -> bool:
    """Avoid ranking a root environment template for unrelated code questions."""

    return (
        chunk.file_type in {"code", "config"}
        and not chunk.source_path.startswith(("issues/", "git/"))
        and (not chunk.source_path.startswith(".") or _is_sensitive_config_query(query, chunk))
    )


def _is_sensitive_config_query(query: str, chunk: ChunkRecord) -> bool:
    """Allow dot-prefixed config only when the question explicitly targets it."""

    if not chunk.source_path.startswith("."):
        return True
    normalized = query.lower()
    return any(
        term in normalized
        for term in (".env", "环境变量", "密码", "密钥", "token", "secret", "凭据")
    )


def _code_location_needs_documents(query: str) -> bool:
    """Identify code-location questions that need README or policy evidence."""

    return any(
        term in query.lower()
        for term in (
            "来源",
            "文件路径",
            "行号",
            "接口路径",
            "路由",
            "中间件",
            "authorization",
            "token",
            "配置",
            "端口",
            "下游",
        )
    )


def _expand_supporting_document_query(query: str) -> str:
    """Add stable vocabulary used by the sample documentation."""

    expansions = {
        "中间件": "Authenticate auth:sanctum 任务列表",
        "任务列表": "Authenticate auth:sanctum routes",
        "token": "Bearer token_type Authorization",
        "来源": "文件路径 行号 引用",
        "代码定位": "文件路径 行号 引用",
        "端口": "server.port application.yml",
        "下游": "客户端 反向代理 部署",
    }
    normalized_query = query.lower()
    added_terms = " ".join(
        value for term, value in expansions.items() if term.lower() in normalized_query
    )
    return f"{query} {added_terms}".strip()


def _expand_code_query(query: str) -> str:
    """Add deterministic code vocabulary without making network calls."""

    expansions = {
        "用户": "user UserController UserService",
        "接口": "controller Controller endpoint",
        "登录": "login AuthController",
        "认证": "auth Authenticate middleware",
        "令牌": "token Bearer Sanctum",
        "路由": "route Route routes",
        "方法": "method function",
        "调用链": "Controller Service",
        "调用": "Controller Service",
        "中间件": "middleware Authenticate auth:sanctum",
        "任务列表": "task tasks api.php auth:sanctum",
        "登录路由": "api.php AuthController login",
        "token 类型": "token_type Bearer AuthController",
        "返回什么类型": "UserDto UserController getUser",
        "配置": "application.yml server.port",
        "端口": "application.yml server.port",
        "getuser": "UserController UserDto UserService",
    }
    normalized_query = query.lower()
    added_terms = " ".join(
        value for term, value in expansions.items() if term.lower() in normalized_query
    )
    return f"{query} {added_terms}".strip()
