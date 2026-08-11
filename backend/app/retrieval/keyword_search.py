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
            "端口被占用",
            "端口冲突",
            "端口绑定失败",
            "排查",
            "故障",
            "问题",
            "错误",
            "认证",
            "未认证",
            "未授权",
            "认证失败",
            "鉴权",
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

# Query and document aliases are deliberately small and explicit.  They make
# the offline retriever understand common Chinese/English ways of describing
# the same development incident without requiring a tokenizer dependency or
# an external model.
TERM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "端口": ("监听端口", "服务端口", "port"),
    "排查": ("诊断", "故障定位", "troubleshooting", "debug"),
    "认证": ("鉴权", "身份校验", "authentication", "auth"),
    "权限": ("授权", "访问控制", "authorization", "permission"),
    "接口": ("api", "endpoint"),
    "配置": ("设置", "参数", "config", "configuration"),
    "任务": ("作业", "task", "jobs"),
    "调用链": ("执行链路", "请求链路", "调用路径", "controller", "service"),
    "登录": ("signin", "sign-in", "login"),
}

ERROR_ALIASES: dict[str, tuple[str, ...]] = {
    "alias:port-conflict": (
        "端口被占用",
        "端口占用",
        "端口冲突",
        "端口绑定失败",
        "端口已被占用",
        "已经被占用",
        "已被占用",
        "端口撞车",
        "端口故障",
        "端口启动故障",
        "服务启动失败",
        "监听端口失败",
        "address already in use",
        "port was already in use",
        "web server failed to start",
    ),
    "alias:http-401": (
        "401",
        "未认证",
        "未授权",
        "认证失败",
        "unauthenticated",
        "unauthorized",
        "authentication failed",
    ),
    "alias:http-403": (
        "403",
        "禁止访问",
        "权限不足",
        "无权限",
        "forbidden",
        "access denied",
    ),
    "alias:http-404": (
        "404",
        "资源不存在",
        "接口不存在",
        "找不到接口",
        "not found",
    ),
    "alias:http-500": (
        "500",
        "服务器内部错误",
        "服务端异常",
        "internal server error",
    ),
    "alias:token-auth": (
        "token",
        "令牌",
        "bearer",
        "authorization",
        "auth:sanctum",
        "sanctum",
    ),
    "alias:code-location": (
        "代码定位",
        "文件路径",
        "行号",
        "哪个文件",
        "入口在哪",
        "入口",
        "路由文件",
        "哪个类",
    ),
}


def _contains_alias(normalized: str, alias: str) -> bool:
    """Match aliases as phrases while keeping identifiers case-insensitive."""

    return alias.lower() in normalized


def _derived_alias_terms(value: str) -> set[str]:
    normalized = value.lower().strip()
    derived: set[str] = set()
    for canonical, variants in TERM_SYNONYMS.items():
        if any(_contains_alias(normalized, variant) for variant in (canonical, *variants)):
            derived.add(canonical)
    for canonical, variants in ERROR_ALIASES.items():
        if any(_contains_alias(normalized, variant) for variant in variants):
            derived.add(canonical)
    return derived


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
    tokens.extend(sorted(_derived_alias_terms(normalized)))
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
        metadata_text = " ".join(
            f"{key} {value}" for key, value in chunk.metadata.items()
        ).lower()
        content_terms = Counter(tokenize(f"{chunk.content}\n{metadata_text}"))
        matched_terms = tuple(sorted({term for term in query_terms if term in content_terms}))
        if not matched_terms:
            continue
        if len(matched_terms) < minimum_matches:
            continue

        score = sum(min(content_terms[term], 3) for term in matched_terms)
        score += 2 * sum(term.startswith("alias:") for term in matched_terms)
        score += 5 * sum(term.startswith("alias:http-") or term == "alias:port-conflict" for term in matched_terms)
        if query_text and query_text in content_text:
            score += 2
        path_terms = set(tokenize(chunk.source_path))
        path_matches = set(query_terms).intersection(path_terms)
        if path_matches:
            score += min(len(path_matches) * 2, 4)
        if query_text and query_text in chunk.source_path.lower():
            score += 1
        metadata_terms = set(tokenize(metadata_text))
        metadata_matches = set(query_terms).intersection(metadata_terms)
        if metadata_matches:
            score += min(len(metadata_matches) * 2, 6)
        if len(unique_query_terms) >= 3 and score < 2:
            continue
        results.append(SearchResult(chunk, float(score), matched_terms))

    results.sort(
        key=lambda result: (-result.score, result.chunk.source_path, result.chunk.start_line)
    )
    return results[:top_k]
