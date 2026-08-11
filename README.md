# DevSage

DevSage 是基于 Agentic RAG 的研发知识库与故障排查系统。当前处于阶段 6 的离线可验证演示基线：已完成本地数据接入、内容 Hash、带文件职责元数据的结构化 Chunk、中文同义词与错误码匹配、关键词/离线向量混合排序、来源查询 API、知识写回审批边界、有限图 Agent、MCP 展示和可复现演示脚本。

## 当前版本范围

- 混合检索已增加来源多样性重排，并提供离线上下文质量代理评估；代理指标不等同于真实 LLM 评审。
- Agent 已增加来源级 grounding 评估、配置文件检索、代码路径加权、项目总结证据预算和有界工具重试；50 条问题当前 Agent Source Recall@5 为 0.9800，完整来源案例率为 0.9600。指标仍是固定脱敏数据集上的离线结果。
- 答案 API 与上下文评估已共享分类检索路由：代码定位优先代码证据，项目总结使用多来源预算和结构化摘要，安全边界问题保留策略文档与配置模板双来源；当前上下文质量代理为 Precision@5 `0.3095`、Recall@5 `1.0000`、失败 `0/50`。Agent grounding 仍为 Source Recall@5 `0.9800`、完整来源案例率 `0.9600`，其中 2 个 `.env.example` 案例位于 `sample-data` source root 之外，Agent 会保持不越界读取。

- `DevMind`：个人模式，优先连接 Obsidian 笔记和个人项目代码；
- `DevSage`：后续扩展到 Git、Issue、多项目和团队协作；
- 固定 75 条问题上的当前实测：纯关键词 Case Recall@5 `0.8800` / Source Recall@5 `0.7200` / MRR `0.7589`，纯 Hash 向量 `0.8933` / `0.6900` / `0.7431`，加权混合 RRF `0.8933` / `0.7144` / `0.7833`，混合加来源多样性重排 `0.9733` / `0.8867` / `0.8116`；新增口语化同义词/错误码题的期望匹配率为 `1.0000`。Hash 向量和当前 reranker 都是离线可解释基线，不代表生产 Embedding 或神经 Reranker 效果。
- 已接入可选 PostgreSQL/pgvector 索引与 Agent task state 持久化、迁移和数据库检索路径；真实 Docker 已验证 PostgreSQL/Redis 健康、索引写入、重启恢复和并发检索，数据绑定到项目 `data/docker/`。外部 Issue 已提供可选 GitHub-compatible 只读适配器，真实平台请求仍需用户配置地址、仓库和可选 Token 环境变量；LangGraph 已在项目本地虚拟环境完成可选适配 smoke。

## 目录结构

```text
DevSage/
├── backend/                 # FastAPI 后端和未来的核心服务
├── frontend/                # Vue 3 前端骨架
├── evaluation/              # 75 条测试问题、评估脚本和报告
├── sample-data/             # 脱敏文档、代码和配置样例
├── docs/                    # 项目设计文档
├── DevSage长期任务路线图.md  # 持续推进的阶段任务
├── docker-compose.yml       # PostgreSQL + pgvector 本地服务骨架与健康检查
└── .env.example             # 非敏感配置模板
```

项目展示入口：[演示与 API 手册](docs/DevSage演示与API手册.md)、[3–5 分钟演示脚本](docs/DevSage演示脚本.md)、[系统架构图](docs/diagrams/devsage-architecture.html)、[Agent 流程图](docs/diagrams/devsage-agent.html)、[交付就绪审计](docs/DevSage交付就绪审计.md)。

## 当前验证命令

离线校验无需新增依赖即可运行：

```powershell
python evaluation/scripts/validate_mvp_dataset.py
python evaluation/scripts/evaluate_agent_grounding.py
python evaluation/scripts/evaluate_tool_call_accuracy.py
python evaluation/scripts/evaluate_context_quality.py
python evaluation/scripts/evaluate_retrieval_strategies.py
python evaluation/scripts/smoke_mcp.py
python -m unittest backend.tests.test_postgres_repository
python -m unittest discover -s backend/tests -p "test_*.py"
python -m pytest -q
python -m compileall -q backend evaluation/scripts
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-http.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-docker.ps1
```

也可以运行统一离线验证入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-offline.ps1
```

该入口会串行执行交付合同审计、数据集、评估、离线 JSON/Markdown 评估报告、backend unittest、pytest、MCP、可选 LangGraph、前端构建、一键演示启动、本地 HTTP smoke、actor capability smoke 和 Compose dry-run；当前环境输出 `steps=19`，不会安装依赖，也不会执行 Docker `-Execute`。

每次门禁也会确定性更新 [evaluation/reports/offline-baseline.md](evaluation/reports/offline-baseline.md) 和对应 JSON，记录数据集 SHA-256、检索策略对比、Agent grounding、工具覆盖和上下文质量代理指标。

FastAPI 和 Vue 依赖可分别启动：

```powershell
uvicorn app.main:app --reload --app-dir backend
npm install --prefix frontend
npm run dev --prefix frontend
```

也可以用一条命令启动本地演示（默认内存存储，不启动 Docker；按 `Ctrl+C` 会只清理本次启动的后端和前端进程）：

```powershell
.\scripts\start-demo.ps1
```

仅用于自动检查启动和清理时，可传入短暂运行时间：

```powershell
.\scripts\start-demo.ps1 -DurationSeconds 5
```

如需先检查本机环境而不改变任何外部状态，可运行只读预检：

```powershell
.\scripts\preflight.ps1
```

预检还会报告 `agent-browser`、`playwright-cli` 和系统浏览器是否可用；缺少浏览器工具时只保留 HTTP/HTML smoke，不会自动安装依赖。

前端默认使用 Vite 代理把 `/api` 和 `/health` 转发到 `127.0.0.1:8000`；`/health` 只额外报告当前 storage、embedding 模式和外部 Issue 是否配置，不返回密钥或 URL。如需连接其他后端地址，可设置 `VITE_API_BASE_URL`。页面启动时读取 `/api/projects`，支持选择注册项目和本地 actor，并把 `project_id` 与 `X-DevSage-Actor` 传给索引、Agent 和审批接口；切换项目或 actor 时会清理旧答案、引用和待审批 Diff，避免跨项目或跨角色误读；同时展示 Agent 分类、工具调用、执行步骤、引用证据和结构化故障排查报告。
检索得到答案后，页面还提供可编辑的知识笔记草稿、代码变更草稿、Diff 预览和显式审批写入按钮；写回请求沿用当前项目 ID，服务端负责最终路径隔离、角色能力检查和过期 Hash 校验。
首页输入框下方按“故障排查 / 代码定位 / 认证与权限 / Vault 知识库”展示可点击案例；Vault 案例来自当前外部知识库的真实目录、研究摄入、插件、Agent 评估、个人 AI 工作流和审计流程，点击后会自动切换到 `obsidian-vault` 只读项目并填入问题。

### 外部 Obsidian Vault 只读接入

DevSage 支持把外部 Obsidian Vault 注册为逻辑项目 `obsidian-vault`。只需要在启动 DevSage 的 PowerShell 会话中设置 Vault 路径：

```powershell
$env:DEVSAGE_OBSIDIAN_VAULT_PATH = "D:\zzd_project\cursor\life\Obsidian Vault"
.scripts\start-demo.ps1
```

也可以直接传参：

```powershell
.\scripts\start-demo.ps1 -ObsidianVaultPath "D:\zzd_project\cursor\life\Obsidian Vault"
```

该项目只提供 `vault_viewer` 角色：可以读取、检索、运行 Agent 和刷新 DevSage 索引，但不能审批知识笔记、代码变更或外部 Issue 写回。前端和 API 只返回逻辑项目名、Vault 内相对路径及 `Lx-Ly` 行号引用，不暴露绝对磁盘路径。

索引器会排除 `.obsidian`、`.git`、缓存目录、构建产物和 `node_modules` 等运行时内容；快照仍写入 DevSage 自己的 `data/index-snapshots/`，不会在 Obsidian Vault 内新增注册文件、索引文件或其他写入内容。

执行 Docker Compose 前必须先准备本地环境变量，并确认数据库数据目录和端口范围。不要把真实密码、Token 或 `.env` 文件提交到仓库。

当前 Compose 会把 DevSage 的 PostgreSQL 和 Redis 数据绑定到项目 D 盘目录：`data/docker/postgres/` 和 `data/docker/redis/`；Docker Desktop 自身的镜像缓存仍由 Docker Desktop 管理，不会迁移或覆盖已有数据。

外部 Issue 默认不联网。需要启用时，在当前 PowerShell 会话设置 `DEVSAGE_EXTERNAL_ISSUE_URL`、`DEVSAGE_EXTERNAL_ISSUE_REPOSITORY`，并可通过 `DEVSAGE_EXTERNAL_ISSUE_TOKEN_ENV` 指定 Token 环境变量；适配器只执行查询，不执行创建、修改或关闭 Issue。

`scripts/smoke-docker.ps1` 默认只运行 `docker compose config --quiet`，不会创建镜像、容器或卷；后端镜像已声明 `/health` 健康检查，构建上下文会排除测试、缓存、数据目录和环境文件。确认 C 盘占用并获得许可后，才可在当前 PowerShell 会话设置 `POSTGRES_PASSWORD`、`DATABASE_URL`，再使用 `-Execute` 运行健康检查、索引写入和 Agent 查询 smoke。

## 当前正在做

当前 API 已支持项目注册发现、索引 `sample-data`、关键词/混合证据查询、分类答案检索路由、项目总结结构化回答、证据约束回答、SSE 流式输出、有限图多工具 Agent、脱敏或可选外部 Issue 查询、本地 Git 历史和 Commit Diff 只读查询、结构化故障排查报告、来源行号、索引变化统计、知识笔记审批写回，以及项目内代码变更的 Diff 预览和 operator 批准写入。离线模式默认把索引快照写入被忽略的 `data/index-snapshots/`，服务重启后仍可按内容 Hash 复用未变化文档；PostgreSQL 模式使用数据库持久化。Agent 状态可生成 JSON 快照，API 还返回不含查询正文的完成 usage：离线 token 估算、工具调用/重试次数和运行时；这些 token 不是供应商账单。工具调用、图步骤和总运行时有硬上限。Embedding 默认使用离线 Hash；显式配置远程 Provider 后才会发起请求。另提供无第三方依赖的 MCP-compatible stdio Server。

## MCP 演示

从项目根目录运行：

```powershell
python -m backend.app.mcp.server
```

服务按标准输入逐行读取 JSON-RPC 请求、按标准输出逐行返回响应，暴露 `search_documents`、`search_code`、`read_file`、`get_git_history` 和 `generate_troubleshooting_report`。默认不会启动网络端口，也不会修改 Git 仓库。

MCP 的 `search_documents`、`search_code`、`read_file` 和 `generate_troubleshooting_report` 支持可选 `project_id`；传入后由同一项目注册器解析 source root，并覆盖兼容保留的 `source_root`。`get_git_history` 仍使用显式只读的 `repository_path`。

## 下一步

1. 在获得磁盘授权后启动 PostgreSQL/pgvector，完成迁移、索引写入和数据库检索端到端 smoke；
2. 选择真实 Embedding Provider 并替换 Hash 测试替身；
3. 在配置测试仓库后完成外部 Issue 真实平台 smoke，并接入正式 MCP 宿主；
4. 接入正式用户、项目和权限模型，继续保留当前本地 capability boundary；
5. 扩充评估集并持续比较检索策略，补齐部署演示与最终交付材料。

## 本轮长程集成状态

- Redis：已提供 Memory/Redis 统一缓存边界，检索响应支持 TTL、命名空间失效和 Redis 故障降级；Compose 已加入 Redis 7 服务，但真实容器 smoke 仍需单独执行。
- 正式认证：已提供 PBKDF2-SHA256 密码哈希、签名 Bearer Token、登录和 `/api/auth/me`；默认关闭，启用时使用项目外或被忽略的用户文件，不把明文密码写入仓库。
- 远程 Embedding：已提供 OpenAI-compatible 批量请求、超时、批大小、维度、索引连续性和有限浮点校验；只有显式选择 `EMBEDDING_PROVIDER=remote` 才会联网。
- 外部 Issue 写入：已提供 Issue 创建预览与 operator 审批接口；预览不联网，审批前必须显式开启写入、配置仓库和 Token，当前未执行真实远程写入。

### 本轮启用配置示例

```powershell
# Redis 真实服务模式；默认离线开发仍可保持 memory
$env:DEVSAGE_CACHE = "redis"
$env:DEVSAGE_REDIS_URL = "redis://127.0.0.1:6379/0"

# 正式认证只使用环境变量中的签名密钥和被忽略的用户文件
$env:DEVSAGE_AUTH_ENABLED = "true"
$env:DEVSAGE_AUTH_SECRET = "YOUR_RANDOM_SECRET_AT_LEAST_32_CHARS"
$env:DEVSAGE_AUTH_USERS_FILE = "config/auth-users.json"
python scripts/create-auth-users.py --username alice --actor-id local-demo

# 远程 Embedding 仅在用户已配置 Provider 和密钥环境变量后启用
$env:EMBEDDING_PROVIDER = "remote"
$env:EMBEDDING_API_URL = "https://YOUR_EMBEDDING_HOST/v1"
$env:EMBEDDING_MODEL = "YOUR_EMBEDDING_MODEL"
$env:EMBEDDING_API_KEY_ENV = "YOUR_EMBEDDING_KEY_ENV"

# 外部 Issue 写入必须在预览后由 operator 显式审批
$env:DEVSAGE_EXTERNAL_ISSUE_WRITE_ENABLED = "true"
```

真实 Docker/PostgreSQL/Redis 和浏览器视觉回归不会由离线验证脚本自动启动；它们属于有额外磁盘和浏览器运行时成本的独立验证阶段。
