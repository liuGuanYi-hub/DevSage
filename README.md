# DevSage

DevSage 是基于 Agentic RAG 的研发知识库与故障排查系统。当前处于阶段 3 的离线可验证基线：已完成本地数据接入、内容 Hash、结构化 Chunk、关键词/离线向量检索基线、来源查询 API、知识写回审批边界和有限图 Agent。

## 当前版本范围

- `DevMind`：个人模式，优先连接 Obsidian 笔记和个人项目代码；
- `DevSage`：后续扩展到 Git、Issue、多项目和团队协作；
- 当前仍未接入 PostgreSQL/pgvector 持久化、真实 Embedding 服务、LangGraph 运行时和外部 Issue 平台。

## 目录结构

```text
DevSage/
├── backend/                 # FastAPI 后端和未来的核心服务
├── frontend/                # Vue 3 前端骨架
├── evaluation/              # 测试问题、评估脚本和报告
├── sample-data/             # 脱敏文档、代码和配置样例
├── docs/                    # 项目设计文档
├── DevSage长期任务路线图.md  # 持续推进的阶段任务
├── docker-compose.yml       # PostgreSQL + pgvector 本地服务骨架
└── .env.example             # 非敏感配置模板
```

## 当前验证命令

无需安装额外依赖即可运行当前阶段的校验：

```powershell
python evaluation/scripts/validate_mvp_dataset.py
python -m unittest discover -s backend/tests -p "test_*.py"
python -m compileall -q backend evaluation/scripts
```

后续实现 FastAPI 和 Vue 依赖后，可以分别启动：

```powershell
uvicorn app.main:app --reload --app-dir backend
npm install --prefix frontend
npm run dev --prefix frontend
```

执行 Docker Compose 前必须先准备本地环境变量，并确认数据库数据目录和端口范围。不要把真实密码、Token 或 `.env` 文件提交到仓库。

## 当前正在做

当前 API 已支持索引 `sample-data`、关键词/混合证据查询、证据约束回答、SSE 流式输出、有限图多工具 Agent、脱敏 Issue 查询、本地 Git 历史和 Commit Diff 只读查询、结构化故障排查报告、来源行号、索引变化统计，以及知识笔记预览和审批写入项目暂存目录。Agent 状态可生成 JSON 快照，工具调用和图步骤有硬上限。Embedding 默认使用离线 Hash；显式配置远程 Provider 后才会发起请求。

## 下一步

1. 在当前 Graph 契约之上接入真实 LangGraph，并保持离线测试路径；
2. 接入 PostgreSQL 全文检索和 pgvector 持久化；
3. 选择真实 Embedding Provider 并替换 Hash 测试替身；
4. 增加任务状态持久化、工具超时和有限重试；
5. 用 `evaluation/datasets/devmind_mvp_questions.json` 持续比较检索策略，再进入项目总结流程。
