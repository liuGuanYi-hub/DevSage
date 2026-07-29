# DevSage / DevMind 演示与 API 手册

本文档基于当前仓库代码整理，目标是用最少步骤演示“索引 → Agent 检索 → 来源引用 → MCP 工具”完整链路。样例数据位于 `sample-data/`，不包含真实密码、Token 或第三方密钥。

## 1. 展示资产

- [DevSage 系统架构图](diagrams/devsage-architecture.html)：Vue、FastAPI、Agent Graph、混合检索、Git/Issue、PostgreSQL/pgvector 和 MCP 边界。
- [DevSage Agent 流程图](diagrams/devsage-agent.html)：问题分类、工具检索、证据判断、单次改写重试、答案组织和知识写回预览。
- 图源 JSON：`docs/diagrams/*.architecture.json`、`docs/diagrams/*.workflow.json`。

两个 HTML 均为独立文件，包含主题切换和导出工具；图源修改后可用 `dynamic-archify` 渲染器重新生成，不需要修改 SVG。

## 2. 离线 HTTP 演示

在项目根目录启动后端：

```powershell
uvicorn app.main:app --reload --app-dir backend
```

建立样例索引：

```powershell
$indexBody = @{ source_root = "sample-data" } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/index `
  -Method Post -ContentType "application/json" -Body $indexBody
```

运行一个代码/配置定位问题：

```powershell
$agentBody = @{
  query = "Spring Boot server.port"
  source_root = "sample-data"
  top_k = 5
  persist = $false
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/agent/run `
  -Method Post -ContentType "application/json" -Body $agentBody
```

重点观察返回值中的：

- `category`：问题分类；
- `tool_calls`：实际调用的工具及有界重试尝试；
- `tool_retry_count`：工具失败后的实际重试次数；
- `steps`：分类、检索、证据判断和答案组织过程；
- `citations` / `evidence`：来源路径、起止行号和匹配词；
- `warning`：证据不足或来源较少时的边界提示。

前端演示：

```powershell
npm run dev --prefix frontend
```

打开 Vite 提供的地址，点击“重新索引样例数据”，再输入“8080 端口被占用，应该怎么排查？”或“Laravel 登录逻辑在哪个控制器方法中？”。页面会展示答案、工具链、执行步骤和结构化故障排查报告。

## 3. HTTP API 目录

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 后端存活检查 |
| GET | `/api/projects` | 列出项目相对路径和本地角色能力矩阵 |
| GET | `/api/projects/{project_id}` | 查询单个注册项目 |
| POST | `/api/index` | 构建或增量更新本地索引并返回 Hash 统计；离线快照默认保存到 `data/index-snapshots/` |
| POST | `/api/search` | 关键词证据查询 |
| POST | `/api/answer` | 混合检索与证据约束回答 |
| POST | `/api/answer/stream` | SSE 流式回答 |
| POST | `/api/agent/run` | 运行有限图多工具 Agent，并返回工具、运行时和离线 Token usage |
| POST | `/api/knowledge-notes/preview` | 生成待审批知识笔记预览，返回 Diff、Hash 和增删行 |
| POST | `/api/knowledge-notes/{preview_id}/approve` | 审批后写入项目暂存目录；目标文件变更时拒绝过期覆盖 |
| GET/POST | `/api/agent/tasks/*` | 查询、恢复和持久化 Agent 状态 |

FastAPI 运行后也可通过 `/docs` 查看当前 OpenAPI 页面；接口响应不会返回环境变量内容或真实凭据。

项目注册默认包含 `sample-data` 脱敏项目，也可通过 `DEVSAGE_PROJECT_MANIFEST` 指向项目根目录内的相对 JSON manifest。返回的 viewer/editor/operator 是能力矩阵边界，不是身份认证；正式用户身份和组织权限仍需后续接入。

知识写回预览默认不落盘。预览响应中的 `diff.operation` 为 `create`、`update` 或 `noop`，并包含 `current_content_hash`、`proposed_content_hash`、`additions`、`deletions` 和 `unified_diff`。审批会再次读取目标文件并校验预览时的 Hash；如果目标在预览后发生变化，接口返回 400，必须重新生成预览。

`/api/agent/run` 和任务恢复响应中的 `usage` 包含 `query_tokens`、`evidence_tokens`、`answer_tokens`、`total_token_estimate`、`tool_calls`、`tool_retries` 和 `runtime_ms`。其中 token 字段是基于离线 tokenizer 的可解释估算，不等同于远程模型供应商计费 Token；完成日志只记录任务 ID、分类、状态和计数，不记录查询正文。

## 4. MCP stdio 演示

启动无网络端口的 MCP-compatible Server：

```powershell
python -m backend.app.mcp.server
```

也可以直接运行无依赖 smoke：

```powershell
python evaluation/scripts/smoke_mcp.py
```

它会自动验证 `initialize`、`tools/list` 和一次带来源引用的 `search_documents` 调用。

按行发送 JSON-RPC 请求，典型顺序如下：

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_code","arguments":{"query":"UserController getUser","source_root":"sample-data","top_k":5}}}
```

当前暴露的工具：`search_documents`、`search_code`、`read_file`、`get_git_history`、`generate_troubleshooting_report`。所有文件读取保持 source root 相对路径约束，Git 和 Issue 工具为只读。Issue 查询默认读取脱敏 `sample-data/issues/issues.json`；设置 `DEVSAGE_EXTERNAL_ISSUE_URL` 与 `DEVSAGE_EXTERNAL_ISSUE_REPOSITORY` 后，Agent 会切换到 GitHub-compatible `/search/issues` 只读接口，Token 只从指定环境变量读取且不会写入日志或错误信息。

## 5. Docker / PostgreSQL smoke 边界

默认只校验 Compose 配置，不会创建镜像、容器或卷：

```powershell
.\scripts\smoke-docker.ps1
```

真实 smoke 需要用户先确认磁盘影响，并在当前 PowerShell 会话提供 `POSTGRES_PASSWORD` 与 `DATABASE_URL`，再显式执行：

```powershell
.\scripts\smoke-docker.ps1 -Execute
```

脚本会依次检查后端健康、PostgreSQL 迁移/索引写入和 Agent 证据返回；默认结束时停止服务但保留命名卷，不使用 `docker compose down -v`。

## 6. 验证入口

```powershell
python evaluation/scripts/validate_mvp_dataset.py
python evaluation/scripts/evaluate_agent_grounding.py
python evaluation/scripts/evaluate_tool_call_accuracy.py
python evaluation/scripts/evaluate_context_quality.py
python -m unittest discover -s backend/tests -p "test_*.py"
python -m unittest discover -s evaluation/tests -p "test_*.py"
npm run build --prefix frontend
```

当前离线基线：Agent Source Recall@5 `0.9800`，完整来源案例率 `0.9600`，Expected Tool Coverage `0.9333`。这些是固定脱敏评估集上的工程指标，不等同于真实 LLM 评审或生产质量承诺。
