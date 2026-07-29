"""Deterministic question classification for the first Agent milestone."""

from __future__ import annotations


QUESTION_CATEGORIES = (
    "troubleshooting",
    "code_location",
    "project_summary",
    "knowledge_write",
    "knowledge_qa",
)


def classify_question(query: str) -> str:
    """Classify a question using transparent keyword rules."""

    text = query.lower()
    if any(word in text for word in ("写入", "整理成", "笔记", "沉淀")):
        return "knowledge_write"
    if any(word in text for word in ("总结", "项目知识", "技术点", "调用链")):
        return "project_summary"
    if any(word in text for word in ("报错", "故障", "端口", "占用", "排查", "异常")):
        return "troubleshooting"
    if any(word in text for word in ("在哪里", "哪个类", "哪个方法", "接口", "路由", "代码")):
        return "code_location"
    return "knowledge_qa"

