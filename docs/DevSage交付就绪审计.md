# DevSage 交付就绪审计

- 审计时间：2026-08-09 20:29
- 审计范围：DevMind MVP、DevSage Agent、工程化部署、量化评估、MCP 展示
- 审计原则：只把当前文件、测试、运行输出或远端状态能直接证明的内容标记为已完成。

## 已有直接证据

| 能力 | 当前状态 | 证据 |
|---|---|---|
| Markdown/代码/配置导入 | 已完成 | `backend/app/ingestion/`、索引测试、50 条数据集验证 |
| 内容 Hash 与增量索引 | 已完成 | `IndexSnapshot`、文件快照恢复测试、HTTP index 统计 |
| 结构化 Chunk 与来源行号 | 已完成 | Chunk 模型、检索测试、API citations |
| 关键词/Hash 向量/RRF 检索 | 已完成 | `evaluate_retrieval_strategies.py` 实测报告 |
| 分类答案检索与项目总结 | 已完成 | `answer_search.py`、API 回归测试、上下文质量评估 |
| 问答 API 与 SSE | 已完成 | `test_api.py`、`scripts/smoke-http.ps1` |
| 知识写回预览与审批 | 已完成 | Diff、Hash 防过期覆盖、写回测试、HTTP smoke 和不记录正文的结构化审批日志 |
| 项目代码变更审批 | 已完成（本地文件） | 已有文件限定、Diff、Hash 防过期覆盖、operator API 合同；未接入远程补丁/提交 |
| 多工具 Agent | 已完成 | Agent grounding、tool accuracy、LangGraph smoke |
| Git/Issue 故障排查 | 已完成（本地/脱敏） | Git 工具、脱敏 Issue、结构化报告和 MCP smoke |
| PostgreSQL 应用层持久化链路 | 已完成合同验证 | fake connection、迁移、保存、持久化 Chunk 读取和 pgvector 调用合同 |
| MCP stdio 展示 | 已完成 | 5 个工具的 JSON-RPC smoke |
| 离线评估报告 | 已完成 | `evaluation/reports/offline-baseline.json`、`offline-baseline.md`；固定数据集 SHA-256 和四组离线指标可复现生成 |
| 只读交付合同审计 | 已完成 | `scripts/check-delivery-contract.ps1`；16 个关键文件、50 条问题、报告 schema 和数据集 Hash 均匹配 |
| 离线交付门禁 | 已完成 | `scripts/verify-offline.ps1`，当前环境 19 步通过（含交付合同、评估报告、pytest、一键演示启动和 actor capability smoke） |
| Actor 能力 HTTP smoke | 已完成 | `scripts/smoke-actors.ps1`；viewer/editor/operator 的允许、拒绝动作、任务读取作用域和 preview 不写盘均已由独立进程验证 |
| 一键本地演示与演示脚本 | 已完成（未做视觉回归） | `scripts/start-demo.ps1`、`docs/DevSage演示脚本.md`；启动/健康/HTML 入口标记/清理已验证 |
| 只读环境预检 | 已完成 | `scripts/preflight.ps1`；报告 Python、Node、npm、pytest、前端依赖、Docker daemon 和浏览器工具状态；未安装依赖或创建资源 |
| Compose 构建边界与后端健康检查 | 已完成 | `backend/.dockerignore`、Dockerfile `HEALTHCHECK`、Compose backend healthcheck；已完成镜像构建和容器启动 |

## 尚未达到最终交付条件

| 能力 | 状态 | 缺失的直接证据 |
|---|---|---|
| PostgreSQL/pgvector 真实部署 | 已完成本地 smoke | Docker Backend、PostgreSQL/pgvector、迁移、真实检索已运行；数据库核验 1024 维向量且空向量为 0 |
| 真实 Embedding Provider | 未完成 | 尚未配置非 Hash Provider 并完成真实请求质量评估 |
| 外部 Issue 平台 | 未完成 | 适配器和 fake transport 已通过，但没有配置真实平台做只读 smoke |
| 正式用户/组织/权限模型 | 部分完成 | `project_id` API 已检查本地 actor/action；仍缺正式身份认证、成员持久化和组织权限 |
| Redis 缓存 | 已完成本地 smoke | Redis 容器健康；检索第二次请求约 8ms，键 TTL 约 59 秒，健康接口返回 `cache=redis` |
| 在线部署体验 | 未完成 | 尚未部署到可访问环境并完成外部链路验证 |
| 3～5 分钟演示视频 | 未完成 | 演示脚本已完成，尚未录制和审核视频 |
| Faithfulness 人工或 LLM 评审 | 未完成 | 当前只有可解释的词法代理，不能替代人工/模型评审 |

## 当前量化结果

- Agent Source Recall@5：`0.9800`
- Agent 完整来源案例率：`0.9600`
- Agent grounding 边界失败：`2/50`；两例预期的 `.env.example` 位于 `sample-data` source root 之外，Agent 未越界读取
- Expected Tool Coverage：`0.9333`
- 上下文 Context Precision@5：`0.3095`
- 上下文 Context Recall@5：`1.0000`
- 上下文失败案例：`0/50`；安全边界问题已增加配置模板证据路由，普通代码定位仍排除 `.env.example`

## 下一步执行顺序

1. 配置脱敏的真实 Embedding Provider，重新记录检索和答案质量，不覆盖 Hash 基线。
2. 配置外部 Issue 测试仓库，执行只读平台 smoke；Token 只从环境变量读取，不写入日志。
3. 设计正式用户、项目成员关系和权限校验，再把当前 capability boundary 迁移为真实授权层。
4. 完成像素级视觉差异比较、在线部署和最终演示材料，并逐项重新审计。

## 安全与资源边界

- 本轮已在 D 盘项目目录执行 Docker、Qwen 远程 smoke 和浏览器回归；未读取、输出或提交真实密钥。浏览器截图与临时验证文件位于被忽略的 `output/playwright/`。
- 不读取、输出或提交真实密码、Token、`.env` 文件或用户数据。
- Docker 数据继续绑定项目 `data/docker/`，模型目录只读挂载；Vault 仍以只读方式挂载，未在 Vault 内写入文件。
