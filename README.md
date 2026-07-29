# DevSage

DevSage 是基于 Agentic RAG 的研发知识库与故障排查系统。当前处于阶段 3 的离线可验证基线：已完成本地数据接入、内容 Hash、结构化 Chunk、关键词/离线向量检索基线、来源查询 API、知识写回审批边界和有限图 Agent。

## 当前版本范围

- 混合检索已增加来源多样性重排，并提供离线上下文质量代理评估；代理指标不等同于真实 LLM 评审。

- `DevMind`：个人模式，优先连接 Obsidian 笔记和个人项目代码；
- `DevSage`：后续扩展到 Git、Issue、多项目和团队协作；
- 已接入可选 PostgreSQL/pgvector 索引与 Agent task state 持久化、迁移和数据库检索路径；真实容器迁移与端到端 smoke 仍待启动验证。真实 Embedding 服务和外部 Issue 平台仍未接入；LangGraph 已在项目本地虚拟环境完成可选适配 smoke。

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

## 当前验证命令

离线校验无需新增依赖即可运行：

```powershell
python evaluation/scripts/validate_mvp_dataset.py
python evaluation/scripts/evaluate_context_quality.py
python -m unittest discover -s backend/tests -p "test_*.py"
python -m compileall -q backend evaluation/scripts
```

FastAPI 和 Vue 依赖可分别启动：

```powershell
uvicorn app.main:app --reload --app-dir backend
npm install --prefix frontend
npm run dev --prefix frontend
```

前端默认使用 Vite 代理把 `/api` 和 `/health` 转发到 `127.0.0.1:8000`；如需连接其他后端地址，可设置 `VITE_API_BASE_URL`。页面已展示 Agent 分类、工具调用、执行步骤、引用证据和结构化故障排查报告。

执行 Docker Compose 前必须先准备本地环境变量，并确认数据库数据目录和端口范围。不要把真实密码、Token 或 `.env` 文件提交到仓库。

## 当前正在做

当前 API 已支持索引 `sample-data`、关键词/混合证据查询、证据约束回答、SSE 流式输出、有限图多工具 Agent、脱敏 Issue 查询、本地 Git 历史和 Commit Diff 只读查询、结构化故障排查报告、来源行号、索引变化统计，以及知识笔记预览和审批写入项目暂存目录。Agent 状态可生成 JSON 快照，工具调用、图步骤和总运行时有硬上限。Embedding 默认使用离线 Hash；显式配置远程 Provider 后才会发起请求。另提供无第三方依赖的 MCP-compatible stdio Server。

## MCP 演示

从项目根目录运行：

```powershell
python -m backend.app.mcp.server
```

服务按标准输入逐行读取 JSON-RPC 请求、按标准输出逐行返回响应，暴露 `search_documents`、`search_code`、`read_file`、`get_git_history` 和 `generate_troubleshooting_report`。默认不会启动网络端口，也不会修改 Git 仓库。

## 下一步

1. 在 LangGraph 适配之上接入 checkpoint 和 Agent API；
2. 启动 PostgreSQL/pgvector，完成迁移、索引写入和数据库检索端到端 smoke；
3. 选择真实 Embedding Provider 并替换 Hash 测试替身；
4. 接入外部 Issue 和正式 MCP 宿主；
5. 扩充评估集并持续比较检索策略。
