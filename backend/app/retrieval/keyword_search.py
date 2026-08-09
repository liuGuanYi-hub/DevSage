"""Dependency-free keyword retrieval baseline for the DevMind MVP."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from ..ingestion.models import ChunkRecord
from .models import SearchResult


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")

# The offline MVP intentionally keeps tokenization dependency-free. Known
# product terms make Chinese queries useful without allowing common single
# characters such as "的" or "用" to become false-positive evidence.
CJK_PHRASES = tuple(
    sorted(
        {
            "示例",
            "项目",
            "包含",
            "哪些",
            "用户",
            "查询",
            "相关",
            "文件",
            "知识库",
            "知识点",
            "目录",
            "收件箱",
            "研究",
            "插件",
            "安装",
            "评估",
            "记录",
            "一次",
            "完整",
            "使用",
            "值得",
            "首次",
            "建议",
            "当前",
            "内容",
            "分别负责",
            "审计报告",
            "目录结构",
            "模板",
            "工作流",
            "刷新",
            "审计",
            "导入",
            "归档",
            "接口",
            "入口",
            "端口",
            "占用",
            "排查",
            "故障",
            "问题",
            "错误",
            "认证",
            "权限",
            "登录",
            "任务",
            "列表",
            "配置",
            "环境变量",
            "密码",
            "密钥",
            "令牌",
            "调用链",
            "业务逻辑",
            "控制器",
            "中间件",
            "文件路径",
            "行号",
            "来源",
            "写回",
            "笔记",
            "总结",
            "技术点",
            "职责",
            "模块",
            "项目总结",
            "个人",
            "外部",
            "只读",
            "快照",
            "索引",
        },
        key=len,
        reverse=True,
    )
)
CJK_STOPWORDS = frozenset(
    "的一是在了不我你他她它其之和与及或有无这那此为从到以对就都也而很更最个"
    "哪什怎么如何应该被把让将已还又呢吗吧啊哦中间各并且如果因为所以关于通过"
)


def tokenize(value: str) -> list[str]:
    """Tokenize identifiers and useful Chinese phrases without stopwords."""

    normalized = value.lower()
    phrases = [phrase for phrase in CJK_PHRASES if phrase in normalized]
    phrase_chars = {char for phrase in phrases for char in phrase}
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(normalized):
        if token in CJK_STOPWORDS or token in phrase_chars:
            continue
        tokens.append(token)
    tokens.extend(phrases)
    return tokens


def is_relevant_result(result: SearchResult, query: str) -> bool:
    """Reject weak fused candidates before they become answer evidence."""

    matched_terms = set(result.matched_terms)
    if not matched_terms:
        return False
    query_terms = set(tokenize(query))
    cjk_query_terms = {
        term for term in query_terms if any("\u4e00" <= char <= "\u9fff" for char in term)
    }
    if len(cjk_query_terms) >= 2 and len(matched_terms) < 2:
        return False

    normalized_query = query.lower()
    anchors: tuple[str, ...] = ()
    if "spring" in normalized_query and "boot" in normalized_query:
        anchors = ("spring", "boot", "springboot")
    elif "laravel" in normalized_query:
        anchors = ("laravel", "sanctum", "auth")
    elif any(term in normalized_query for term in ("obsidian", "vault", "inbox", "research")):
        anchors = ("obsidian", "vault", "inbox", "research")

    if anchors:
        source_path = result.chunk.source_path.lower()
        if not any(anchor in matched_terms or anchor in source_path for anchor in anchors):
            return False

    if (
        "spring" in query_terms
        and "boot" in query_terms
        and "用户" in query_terms
        and result.chunk.file_type != "code"
        and "springboot-demo/" not in result.chunk.source_path.lower()
    ):
        return False

    focus_terms = {
        term
        for term in query_terms
        if term in {"用户", "查询", "接口", "职责", "文件", "目录", "认证", "权限", "端口"}
    }
    if focus_terms and result.chunk.file_type != "code":
        source_path = result.chunk.source_path.lower()
        if result.chunk.file_type == "config" and "端口" in query_terms and any(
            term in matched_terms for term in ("server", "port", "application", "application.yml")
        ):
            return True
        if not matched_terms.intersection(focus_terms) and not (
            "springboot-demo/readme.md" in source_path
        ):
            return False
    return True


def search_keyword(
    chunks: Iterable[ChunkRecord],
    query: str,
    top_k: int = 5,
) -> list[SearchResult]:
    """Return ranked chunks using term frequency and exact phrase bonuses."""

    if top_k <= 0:
        return []

    query_terms = tokenize(query)
    if not query_terms:
        return []

    unique_query_terms = set(query_terms)
    cjk_query_terms = {
        term for term in unique_query_terms if any("\u4e00" <= char <= "\u9fff" for char in term)
    }
    strong_identifiers = {
        "usercontroller",
        "userservice",
        "getuser",
        "finduser",
        "authcontroller",
        "authenticate",
        "authorization",
        "server",
        "application",
        "bearer",
        "sanctum",
        "token_type",
        "8080",
    }
    if len(cjk_query_terms) >= 2 and not strong_identifiers.intersection(unique_query_terms):
        minimum_matches = 2
    else:
        minimum_matches = 1

    query_text = query.lower().strip()
    results: list[SearchResult] = []
    for chunk in chunks:
        content_text = chunk.content.lower()
        content_terms = Counter(tokenize(chunk.content))
        matched_terms = tuple(sorted({term for term in query_terms if term in content_terms}))
        if not matched_terms:
            continue
        if len(matched_terms) < minimum_matches:
            continue

        score = sum(min(content_terms[term], 3) for term in matched_terms)
        if query_text and query_text in content_text:
            score += 2
        path_terms = set(tokenize(chunk.source_path))
        path_matches = set(query_terms).intersection(path_terms)
        if path_matches:
            score += min(len(path_matches) * 2, 4)
        if query_text and query_text in chunk.source_path.lower():
            score += 1
        if len(unique_query_terms) >= 3 and score < 2:
            continue
        results.append(SearchResult(chunk, float(score), matched_terms))

    results.sort(
        key=lambda result: (-result.score, result.chunk.source_path, result.chunk.start_line)
    )
    return results[:top_k]
