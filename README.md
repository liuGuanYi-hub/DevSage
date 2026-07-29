# DevSage

DevSage 是基于 Agentic RAG 的研发知识库与故障排查系统。当前处于阶段 3 的离线可验证基线：已完成本地数据接入、内容 Hash、结构化 Chunk、关键词/离线向量检索基线、来源查询 API、知识写回审批边界和有限图 Agent。

## 当前版本范围

- 混合检索已增加来源多样性重排，并提供离线上下文质量代理评估；代理指标不等同于真实 LLM 评审。
- Agent 已增加来源级 grounding 评估、配置文件检索、代码路径加权、项目总结证据预算和有界工具重试；50 条问题当前 Agent Source Recall@5 为 0.9800，完整来源案例率为 0.9600。指标仍是固定脱敏数据集上的离线结果。

- `DevMind`：个人模式，优先连接 Obsidian 笔记和个人项目代码；
- `DevSage`：后续扩展到 Git、Issue、多项目和团队协作；
- 固定 50 条问题上的当前实测：纯关键词 Case Recall@5 `0.7200` / Source Recall@5 `0.5450` / MRR `0.4347`，纯 Hash 向量 `0.7800` / `0.6283` / `0.6807`，原始 RRF `0.7400` / `0.5717` / `0.6540`，混合加来源多样性重排 `0.8200` / `0.6783` / `0.6753`；Hash 向量和当前 reranker 都是离线可解释基线，不代表生产 Embedding 或神经 Reranker 效果。
- 已接入可选 PostgreSQL/pgvector 索引与 Agent task state 持久化、迁移和数据库检索路径；真实容器迁移与端到端 smoke 仍待启动验证。外部 Issue 已提供可选 GitHub-compatible 只读适配器，真实平台请求仍需用户配置地址、仓库和可选 Token 环境变量；LangGraph 已在项目本地虚拟环境完成可选适配 smoke。

## 目录结构

```text
DevSage/
├── backend/                 # FastAPI 后端和未来的核心服务
├── frontend/                # Vue 3 前端骨架
├── evaluation/              # 50 条测试问题、评估脚本和报告
├── sample-data/             # 脱敏文档、代码和配置样例
├── docs/                    # 项目设计文档
├── DevSage长期任务路线图.md  # 持续推进的阶段任务
├── docker-compose.yml       # PostgreSQL + pgvector 本地服务骨架
└── .env.example             # 非敏感配置模板
```

项目展示入口：[演示与 API 手册](docs/DevSage演示与API手册.md)、[系统架构图](docs/diagrams/devsage-architecture.html)、[Agent 流程图](docs/diagrams/devsage-agent.html)。

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
python -m compileall -q backend evaluation/scripts
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-http.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke-docker.ps1
```

也可以运行统一离线验证入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-offline.ps1
```

该入口会串行执行数据集、评估、后端、MCP、可选 LangGraph、前端构建、本地 HTTP smoke 和 Compose dry-run；不会安装依赖，也不会执行 Docker `-Execute`。

FastAPI 和 Vue 依赖可分别启动：

```powershell
uvicorn app.main:app --reload --app-dir backend
npm install --prefix frontend
npm run dev --prefix frontend
```

前端默认使用 Vite 代理把 `/api` 和 `/health` 转发到 `127.0.0.1:8000`；如需连接其他后端地址，可设置 `VITE_API_BASE_URL`。页面启动时读取 `/api/projects`，支持选择注册项目并把 `project_id` 传给索引和 Agent 查询；同时展示 Agent 分类、工具调用、执行步骤、引用证据和结构化故障排查报告。
检索得到答案后，页面还提供可编辑的知识笔记草稿、Diff 预览和显式审批写入按钮；写回请求沿用当前项目 ID，服务端负责最终路径隔离和过期 Hash 校验。

执行 Docker Compose 前必须先准备本地环境变量，并确认数据库数据目录和端口范围。不要把真实密码、Token 或 `.env` 文件提交到仓库。

外部 Issue 默认不联网。需要启用时，在当前 PowerShell 会话设置 `DEVSAGE_EXTERNAL_ISSUE_URL`、`DEVSAGE_EXTERNAL_ISSUE_REPOSITORY`，并可通过 `DEVSAGE_EXTERNAL_ISSUE_TOKEN_ENV` 指定 Token 环境变量；适配器只执行查询，不执行创建、修改或关闭 Issue。

`scripts/smoke-docker.ps1` 默认只运行 `docker compose config --quiet`，不会创建镜像、容器或卷；确认 C 盘占用并获得许可后，才可在当前 PowerShell 会话设置 `POSTGRES_PASSWORD`、`DATABASE_URL`，再使用 `-Execute` 运行健康检查、索引写入和 Agent 查询 smoke。

## 当前正在做

当前 API 已支持项目注册发现、索引 `sample-data`、关键词/混合证据查询、证据约束回答、SSE 流式输出、有限图多工具 Agent、脱敏或可选外部 Issue 查询、本地 Git 历史和 Commit Diff 只读查询、结构化故障排查报告、来源行号、索引变化统计，以及知识笔记预览和审批写入项目暂存目录。离线模式默认把索引快照写入被忽略的 `data/index-snapshots/`，服务重启后仍可按内容 Hash 复用未变化文档；PostgreSQL 模式使用数据库持久化。Agent 状态可生成 JSON 快照，API 还返回不含查询正文的完成 usage：离线 token 估算、工具调用/重试次数和运行时；这些 token 不是供应商账单。工具调用、图步骤和总运行时有硬上限。Embedding 默认使用离线 Hash；显式配置远程 Provider 后才会发起请求。另提供无第三方依赖的 MCP-compatible stdio Server。

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
