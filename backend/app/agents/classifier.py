"""Deterministic question classification for the first Agent milestone."""

from __future__ import annotations


QUESTION_CATEGORIES = (
    "troubleshooting",
    "code_location",
    "project_summary",
    "knowledge_write",
    "knowledge_qa",
    "git_history",
    "git_diff",
    "issue_search",
)


def classify_question(query: str) -> str:
    """Classify a question using transparent keyword rules."""

    text = query.lower()
    if any(word in text for word in ("写入", "整理成", "笔记", "沉淀")):
        return "knowledge_write"
    if any(
        word in text
        for word in (
            "总结",
            "项目知识",
            "技术点",
            "调用链",
            "包含哪些",
            "哪些文件",
            "主要文件",
            "比较",
            "差异",
            "职责",
        )
    ):
        return "project_summary"
    if "端口" in text and "故障" in text:
        return "troubleshooting"
    if any(word in text for word in ("历史故障", "故障记录", "之前出现过", "是否出现过")):
        return "issue_search"
    if any(
        word in text
        for word in (
            "401",
            "403",
            "404",
            "500",
            "unauthenticated",
            "forbidden",
            "not found",
            "internal server error",
            "address already in use",
            "web server failed to start",
        )
    ):
        return "troubleshooting"
    if any(
        word in text
        for word in (
            "哪个控制器",
            "哪个方法",
            "业务方法",
            "调用了哪个",
            "控制器方法",
            "什么中间件",
            "哪个中间件",
            "中间件",
            "哪个凭据字段",
            "哪个请求头",
            "返回什么类型",
            "token 类型",
            "token_type",
            "bearer token",
            "接口路径",
            "配置文件",
            "server.port",
            "application.yml",
            "代码定位",
        )
    ) or ("配置" in text and "端口" in text):
        return "code_location"
    if any(word in text for word in ("报错", "故障", "端口", "占用", "排查", "异常")):
        return "troubleshooting"
    if any(word in text for word in ("issue", "问题单", "历史故障", "故障记录", "之前出现过", "是否出现过")):
        return "issue_search"
    if any(word in text for word in ("diff", "patch", "show", "差异", "变更", "提交内容", "改了什么", "修改了什么")):
        return "git_diff"
    if any(word in text for word in ("不应该提交", "真实数据库密码", "安全边界", "敏感内容")):
        return "knowledge_qa"
    if any(word in text for word in ("提交", "commit", "git", "修改记录")):
        return "git_history"
    if any(word in text for word in ("在哪里", "哪个类", "哪个方法", "接口", "路由", "代码")):
        return "code_location"
    return "knowledge_qa"
