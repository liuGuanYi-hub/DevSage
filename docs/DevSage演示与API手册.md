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

也可以使用一键本地演示入口：

```powershell
.\scripts\start-demo.ps1
```

该脚本默认使用内存存储，启动后端和 Vite 前端并检查两个地址就绪；按 `Ctrl+C` 会只停止本次启动的两个进程，不启动 Docker 或创建数据库卷。`-DurationSeconds 5` 可用于自动化启动/清理检查。

启动前可运行只读环境预检：

```powershell
.\scripts\preflight.ps1
```

预检只报告 Python、Node、pytest、前端依赖、Docker daemon 和 C/D 盘可用空间，不安装依赖、不启动 Docker。

前端启动后会先加载 `/api/projects`，项目选择器默认使用 `sample-data`；切换项目会清理上一项目的答案、引用和待审批 Diff，重新索引当前注册项目，并将 `project_id` 传给 Agent 查询。

打开 Vite 提供的地址，点击“重新索引样例数据”，再输入“8080 端口被占用，应该怎么排查？”或“Laravel 登录逻辑在哪个控制器方法中？”。页面会展示答案、工具链、执行步骤和结构化故障排查报告。

如需把个人 Obsidian Vault 作为额外的只读项目接入，可在启动前设置：

```powershell
$env:DEVSAGE_OBSIDIAN_VAULT_PATH = "D:\zzd_project\cursor\life\Obsidian Vault"
.\scripts\start-demo.ps1
```

注册后的项目 ID 为 `obsidian-vault`，角色为 `vault_viewer`。该角色允许刷新 DevSage 自己的索引快照、检索和运行 Agent，但不拥有任何写回审批能力。引用保持 Vault 内相对路径并附带 `Lx-Ly` 行号，`.obsidian` 和缓存目录不会进入索引；DevSage 快照位于项目自身的 `data/index-snapshots/`。

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
| POST | `/api/code-changes/preview` | 生成项目内已有代码文件的待审批 Diff，不写盘 |
| POST | `/api/code-changes/{preview_id}/approve` | 通过 operator 能力检查并重新校验 Hash 后写入代码文件 |
| GET/POST | `/api/agent/tasks/*` | 查询、恢复和持久化 Agent 状态；绑定 `project_id` 的任务按 actor 能力检查 |

FastAPI 运行后也可通过 `/docs` 查看当前 OpenAPI 页面；接口响应不会返回环境变量内容或真实凭据。

`/health` 还会返回 `storage`、`embedding_provider` 和 `external_issue_configured` 三个非敏感运行模式字段；它们用于诊断当前配置，不代表真实数据库、远程 Provider 或外部 Issue 已完成端到端验证。

项目注册默认包含 `sample-data` 脱敏项目，也可通过 `DEVSAGE_PROJECT_MANIFEST` 指向项目根目录内的相对 JSON manifest。manifest 可用 `members` 对象把 actor ID 映射到 viewer/editor/operator；项目列表会返回非敏感的成员能力元数据，前端可切换本地 actor，并把 `X-DevSage-Actor` 传给索引、Agent 和审批接口。带 `project_id` 的 API 会检查 action。当前这是本地 capability boundary，不是身份认证；正式用户身份和组织权限仍需后续接入。

`/api/index`、`/api/search`、`/api/answer`、`/api/answer/stream` 和 `/api/agent/run` 都支持可选 `project_id`。传入后由项目注册器解析 source root；未传入时继续兼容原有 `source_root` 参数。

`/api/answer` 和 `/api/answer/stream` 使用分类答案检索路由：代码定位问题优先代码来源并按需合并支持文档；项目总结问题使用更宽的多来源证据预算，并按文档/配置和代码分组组织回答；其他问题继续使用混合检索。离线上下文质量评估调用同一套路由，避免评估脚本与生产回答路径分叉。

知识写回预览默认不落盘。预览响应中的 `diff.operation` 为 `create`、`update` 或 `noop`，并包含 `current_content_hash`、`proposed_content_hash`、`additions`、`deletions` 和 `unified_diff`。审批会再次读取目标文件并校验预览时的 Hash；如果目标在预览后发生变化，接口返回 400，必须重新生成预览。
知识写回请求也支持可选 `project_id`；传入已注册项目时，目标会自动隔离到 `data/approved-notes/projects/<project_id>/` 下，避免不同项目的同名笔记互相覆盖。未传入时保留旧的兼容目标路径。

代码变更预览只接受 source root 内已存在的文件，预览阶段不会写盘；批准阶段会重新读取目标文件并比较 current Hash，内容发生变化时拒绝覆盖。带 `project_id` 的代码变更需要 operator actor 的 `code_write_preview` / `code_write_approve` 能力；当前不执行远程 Issue 写入。

`/api/agent/run` 和任务恢复响应中的 `usage` 包含 `query_tokens`、`evidence_tokens`、`answer_tokens`、`total_token_estimate`、`tool_calls`、`tool_retries` 和 `runtime_ms`。其中 token 字段是基于离线 tokenizer 的可解释估算，不等同于远程模型供应商计费 Token；完成日志只记录任务 ID、分类、状态和计数，不记录查询正文。

持久化 Agent 状态会保存可选的 `project_id`。绑定项目的任务读取需要该项目的 `read` 能力，任务恢复需要 `agent` 能力；请求通过 `X-DevSage-Actor` 传递本地 actor。没有 `project_id` 的旧版任务保持兼容，但不代表已经接入正式身份认证。

知识和代码审批还会通过 `devsage.approval` 记录动作、preview ID、actor、项目、相对目标路径和状态，不记录笔记正文或代码内容。

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

MCP 的文档检索、代码检索、文件读取和故障报告工具也支持可选 `project_id`。例如将 `search_code` 的 arguments 写成 `{"query":"UserController getUser","project_id":"sample-data","top_k":5}`；`project_id` 会由项目注册器解析并优先于 `source_root`，未知项目会被拒绝。`get_git_history` 不接受项目 ID，继续要求调用方显式提供只读 `repository_path`。

通用 hybrid 查询会先应用中文同义词、错误码归一化和确定性代码词扩展，再进入关键词与本地向量融合；关键词信号使用更高的加权 RRF 权重，向量输入同时包含文件路径、文件职责、标题、符号和行号元数据。这样可以让“端口撞车”“未认证”“用户接口”等自然语言问题更容易命中类名、控制器、路由和配置文件。raw RRF 仍保留在策略评估中作为不带业务扩展的基线。

本地语义 Embedding 通过可选的 `SentenceTransformers` Provider 接入。安装 `backend/requirements-local-embedding.txt` 后，设置 `EMBEDDING_PROVIDER=local` 即可加载 BGE/E5 类模型，模型缓存建议放在 DevSage 的 `data/models/`；不设置时仍使用确定性的 Hash Provider。`evaluation/scripts/compare_embedding_providers.py` 会对同一批 75 道问题同时计算关键词、Hash 向量/混合和本地模型向量/混合的 Case Recall@5、Source Recall@5、MRR 与错误码别名召回率。

当前正式接入候选为 `intfloat/multilingual-e5-large` 的 ONNX qint8 版本。它输出 1024 维，和 PostgreSQL/pgvector 迁移的 `embedding vector(1024)` 兼容；写入 Chunk 向量时使用 `passage: `，查询时使用 `query: `。推荐配置如下：

```powershell
$env:EMBEDDING_PROVIDER = "local"
$env:LOCAL_EMBEDDING_MODEL = "data/manual-models/multilingual-e5-large-qint8"
$env:LOCAL_EMBEDDING_BACKEND = "onnx"
$env:LOCAL_EMBEDDING_FILE_NAME = "model_qint8_avx512_vnni.onnx"
$env:LOCAL_EMBEDDING_CACHE = "D:\zzd_project\cursor\hanshi  senior\DevSage\data\models"
$env:DEVSAGE_STORAGE = "postgres"
$env:DATABASE_URL = "postgresql://devsage:YOUR_PASSWORD@127.0.0.1:5433/devsage"
```

评测报告为 [local-embedding-1024-comparison.md](../evaluation/reports/local-embedding-1024-comparison.md)。`BAAI/bge-m3` 也是 1024 维候选，但本轮未完成其 PyTorch 权重下载，因此没有把 BGE-M3 作为已验证生产模型；Hash 仍保留为离线降级路径。

真实 PostgreSQL 可用后，在当前 PowerShell 会话配置 `DATABASE_URL`，再运行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-local-embedding-postgres.ps1`。该 smoke 会加载 D 盘 E5 ONNX qint8 模型，调用现有迁移、写入 1024 维 Chunk 向量，再通过 pgvector 执行混合查询；脚本不会打印数据库连接串，也不会修改 Vault。

LangGraph 适配是可选运行时，离线默认环境不安装也不影响本地 Agent。若使用项目自带虚拟环境，可运行 `.\\backend\\.venv\\Scripts\\python.exe evaluation/scripts/smoke_langgraph.py`；该 smoke 会验证四节点图完成、返回来源引用，并通过 `MemorySaver + thread_id` 读取已保存状态。未安装时脚本只报告 skipped，不会自动下载依赖。

在启动真实数据库前，可以运行无外部服务的 PostgreSQL/pgvector 合同测试：

```powershell
python -m unittest backend.tests.test_postgres_repository
```

该测试使用内存 fake connection 验证迁移 SQL、事务提交、项目快照写入、关键词查询、向量查询和混合检索返回结构；它不代表真实 PostgreSQL 已启动，也不会拉取 Docker 镜像。

启用 PostgreSQL 存储后，答案路由会读取已持久化 Chunk；普通问答的混合检索通过仓储适配器进入 pgvector，代码定位和项目总结会在数据库候选上继续执行来源类型过滤。当前真实 Docker smoke 已验证网络、pgvector 扩展、索引写入、D 盘绑定数据目录、重启恢复和并发检索。

## 5. Docker / PostgreSQL smoke 边界

在不启动 Docker 的情况下，可以先用真实本地 HTTP 服务验证项目发现、索引、Agent 和知识写回审批链路：

```powershell
.\scripts\smoke-http.ps1
```

该脚本使用临时端口启动 FastAPI，验证项目索引、Agent、代码变更预览（确认预览不写盘）和知识审批，再清理本次创建的测试笔记并关闭服务；它不会验证 PostgreSQL、Docker 卷或浏览器视觉渲染。

如果需要一次性执行当前离线验证集合，可运行：

```powershell
.\scripts\verify-offline.ps1
```

该入口会串行执行交付合同审计、评估、离线 JSON/Markdown 评估报告、backend unittest、pytest、MCP、可选 LangGraph、前端构建、一键演示启动、本地 HTTP smoke、actor capability smoke 和 Compose dry-run；当前环境输出 `steps=19`。报告写入 `evaluation/reports/offline-baseline.json` 和 `evaluation/reports/offline-baseline.md`。真实 Docker、外部 Issue 和远程 Embedding 仍保持显式配置/授权边界。

默认只校验 Compose 配置，不会创建镜像、容器或卷：

```powershell
.\scripts\smoke-docker.ps1
```

真实 smoke 需要用户先确认磁盘影响，并在当前 PowerShell 会话提供 `POSTGRES_PASSWORD` 与 `DATABASE_URL`，再显式执行：

```powershell
.\scripts\smoke-docker.ps1 -Execute
```

脚本会依次检查后端健康、项目注册发现、使用 `project_id` 的 PostgreSQL 迁移/索引写入和 Agent 证据返回；默认结束时停止服务但保留 D 盘绑定目录和命名卷，不使用 `docker compose down -v`。
Compose 会将 PostgreSQL 数据写入项目内 `data/docker/postgres/`，Redis AOF 数据写入 `data/docker/redis/`；已审批知识笔记仍挂载到命名卷 `devsage-approved-notes`，容器重建不会清空审批后的暂存内容。

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
