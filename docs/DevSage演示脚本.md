# DevSage / DevMind 3–5 分钟演示脚本

## 演示目标

用脱敏 `sample-data` 完成一条可复现链路：项目发现 → 内容 Hash 索引 → Agent 分类与多工具检索 → 来源引用与故障报告 → 知识/代码变更预览 → MCP smoke。演示默认使用内存存储，不启动 Docker，不读取真实密码、Token 或用户数据。

## 演示前准备

在项目根目录执行：

```powershell
.\scripts\start-demo.ps1
```

脚本会启动 FastAPI 和 Vite，确认 `http://127.0.0.1:8000/health` 与 `http://127.0.0.1:5173` 就绪，然后保持运行。前端依赖需要已经存在于 `frontend/node_modules/`；脚本不会自动安装依赖。

打开 `http://127.0.0.1:5173`，页面顶部应显示项目选择器、索引按钮、后端在线状态和 Agentic RAG 标识。

## 按时间演示

### 0:00–0:30：介绍边界

说明 DevMind 是 DevSage 的第一阶段：把研发文档、代码和配置切成带行号的 Chunk，再由有限 Agent 选择检索工具，回答必须带来源。当前默认是离线 Hash Embedding，外部 Issue 和远程 Embedding 都是可选能力。

### 0:30–1:00：项目发现与增量索引

1. 展示项目选择器中的 `sample-data`。
2. 点击“重新索引当前项目”。
3. 观察文件数、Chunk 数和在线状态。
4. 再点一次索引，说明内容 Hash 会识别未变化文档，返回 `unchanged_documents` 统计。

可用 API 作为无浏览器备用演示：

```powershell
$body = @{ project_id = "sample-data" } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/index -Method Post `
  -ContentType "application/json" -Body $body
```

### 1:00–2:00：故障排查 Agent

在输入框提交：

```text
8080 端口被占用，应该怎么排查？
```

重点展示：

- `troubleshooting` 分类；
- `search_documents`、`search_issues`、`get_git_history` 等工具调用；
- Agent steps、工具重试次数和离线 Token 估算；
- 带来源行号的证据卡片；
- 结构化故障报告、findings 和 next steps。

### 2:00–2:40：代码定位与项目总结

依次提交：

```text
示例 Spring Boot 项目的用户接口入口在哪个类？
示例 Spring Boot 项目包含哪些与用户查询相关的文件？
```

说明代码定位会优先返回 `UserController.java` 等代码证据，项目总结会扩大来源预算并同时组织文档与代码；普通代码问题不会无条件读取根目录 `.env.example`。

### 2:40–3:30：知识笔记审批

1. 在回答下方检查可编辑的标题、目标路径和草稿内容。
2. 点击 `Generate preview`。
3. 展示 `create/update/noop`、增删行和 unified Diff。
4. 解释预览阶段不写盘，审批阶段会重新校验目标 Hash。
5. 如需展示写入，点击 `Approve and write`；只使用 `data/approved-notes/projects/sample-data/` 下的演示目标，结束后删除本次明确创建的文件。

### 3:30–4:10：代码变更审批

在代码变更面板中指定已有样例文件，并粘贴完整的拟议文件内容：

```text
repositories/springboot-demo/README.md
```

点击 `Generate code preview`，展示代码 Diff。说明只有 operator 能力可以批准，目标文件必须已存在且位于项目 source root 内；批准前再次比较 Hash，预览期间文件被修改则拒绝覆盖。

### 4:10–4:40：MCP 与交付门禁

停止前端演示或另开终端运行：

```powershell
python evaluation/scripts/smoke_mcp.py
```

最后展示离线交付门禁：

```powershell
.\scripts\verify-offline.ps1
```

门禁会验证数据集、50 条评测、后端测试、MCP、可选 LangGraph、前端构建、本地 HTTP smoke 和 Compose dry-run；不会执行 Docker `-Execute`。

## 演示结束与边界声明

在运行 `start-demo.ps1` 的终端按 `Ctrl+C`，脚本只停止本次启动的后端和前端进程。当前已验证的是本地离线演示；真实 PostgreSQL/pgvector、真实 Embedding Provider、真实外部 Issue 平台、正式身份认证和浏览器视觉回归仍需独立配置与授权验证。

## 备用 API 演示

若浏览器工具不可用，可直接调用 Agent API：

```powershell
$body = @{
  project_id = "sample-data"
  query = "8080 端口被占用，应该怎么排查？"
  top_k = 5
  persist = $false
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:8000/api/agent/run `
  -Method Post -ContentType "application/json" -Body $body
```

该响应包含 `category`、`tool_calls`、`steps`、`citations`、`report` 和 `usage`，可以完整证明 Agent 链路而不依赖视觉自动化工具。
