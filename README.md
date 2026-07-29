# DevSage

DevSage 是基于 Agentic RAG 的研发知识库与故障排查系统。当前处于阶段 1：已完成本地数据接入、内容 Hash、结构化 Chunk、关键词/离线向量检索基线、来源查询 API 和知识写回审批边界。

## 当前版本范围

- `DevMind`：个人模式，优先连接 Obsidian 笔记和个人项目代码；
- `DevSage`：后续扩展到 Git、Issue、多项目和团队协作；
- 当前仍未接入 PostgreSQL/pgvector 持久化、真实 Embedding 服务和完整 Agent 编排。

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

当前 API 已支持索引 `sample-data`、关键词/混合证据查询、证据约束回答、SSE 流式输出、有限状态多工具 Agent、来源行号、索引变化统计，以及知识笔记预览和审批写入项目暂存目录。下一步是替换离线 Hash Provider，并接入 PostgreSQL + pgvector 持久化。

## 下一步

1. 接入 PostgreSQL 全文检索和 pgvector 持久化；
2. 选择真实 Embedding Provider 并替换 Hash 测试替身；
3. 把前端占位页接入索引、查询和来源接口；
4. 用 `evaluation/datasets/devmind_mvp_questions.json` 持续比较检索策略；
5. 再进入 LangGraph Agent 和项目总结流程。
