"""Transparent, bounded query rewrites for the offline Agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryRewrite:
    original_query: str
    rewritten_query: str
    added_terms: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return self.rewritten_query != self.original_query


REWRITE_TERMS = {
    "用户": "user UserController UserService",
    "接口": "controller Controller endpoint",
    "登录": "login auth",
    "认证": "auth middleware",
    "令牌": "token bearer",
    "路由": "route routes",
    "端口": "port 8080",
    "占用": "process PID",
}


def rewrite_query(query: str, category: str) -> QueryRewrite:
    """Add a small, explainable vocabulary expansion for one retry."""

    if category not in {"knowledge_qa", "code_location", "project_summary"}:
        return QueryRewrite(query, query, ())
    additions: list[str] = []
    for term, expansion in REWRITE_TERMS.items():
        if term in query:
            additions.extend(expansion.split())
    unique_additions = tuple(dict.fromkeys(additions))
    if not unique_additions:
        return QueryRewrite(query, query, ())
    return QueryRewrite(
        original_query=query,
        rewritten_query=f"{query} {' '.join(unique_additions)}",
        added_terms=unique_additions,
    )
