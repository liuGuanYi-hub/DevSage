"""Deterministic question classification for the first Agent milestone."""

from __future__ import annotations


QUESTION_CATEGORIES = (
    "troubleshooting",
    "code_location",
    "project_summary",
    "knowledge_write",
    "knowledge_qa",
    "git_history",
    "issue_search",
)


def classify_question(query: str) -> str:
    """Classify a question using transparent keyword rules."""

    text = query.lower()
    if any(word in text for word in ("写入", "整理成", "笔记", "沉淀")):
        return "knowledge_write"
    if any(word in text for word in ("总结", "项目知识", "技术点", "调用链")):
        return "project_summary"
    if any(word in text for word in ("历史故障", "故障记录")):
        return "issue_search"
    if any(word in text for word in ("报错", "故障", "端口", "占用", "排查", "异常")):
        return "troubleshooting"
    if any(word in text for word in ("issue", "问题单", "历史故障", "故障记录", "之前出现过", "是否出现过")):
        return "issue_search"
    if any(word in text for word in ("提交", "commit", "git", "修改记录")):
        return "git_history"
    if any(word in text for word in ("在哪里", "哪个类", "哪个方法", "接口", "路由", "代码")):
        return "code_location"
    return "knowledge_qa"
