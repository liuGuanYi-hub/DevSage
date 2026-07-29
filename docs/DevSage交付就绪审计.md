# DevSage 交付就绪审计

- 审计时间：2026-07-30 05:05
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
| 知识写回预览与审批 | 已完成 | Diff、Hash 防过期覆盖、写回测试和 HTTP smoke |
| 项目代码变更审批 | 已完成（本地文件） | 已有文件限定、Diff、Hash 防过期覆盖、operator API 合同；未接入远程补丁/提交 |
| 多工具 Agent | 已完成 | Agent grounding、tool accuracy、LangGraph smoke |
| Git/Issue 故障排查 | 已完成（本地/脱敏） | Git 工具、脱敏 Issue、结构化报告和 MCP smoke |
| PostgreSQL 应用层持久化链路 | 已完成合同验证 | fake connection、迁移、保存、持久化 Chunk 读取和 pgvector 调用合同 |
| MCP stdio 展示 | 已完成 | 5 个工具的 JSON-RPC smoke |
| 离线交付门禁 | 已完成 | `scripts/verify-offline.ps1`，14 步通过 |

## 尚未达到最终交付条件

| 能力 | 状态 | 缺失的直接证据 |
|---|---|---|
| PostgreSQL/pgvector 真实部署 | 待授权 | Docker 镜像、容器、迁移、真实查询和卷恢复尚未执行 |
| 真实 Embedding Provider | 未完成 | 尚未配置非 Hash Provider 并完成真实请求质量评估 |
| 外部 Issue 平台 | 未完成 | 适配器和 fake transport 已通过，但没有配置真实平台做只读 smoke |
| 正式用户/组织/权限模型 | 部分完成 | `project_id` API 已检查本地 actor/action；仍缺正式身份认证、成员持久化和组织权限 |
| Redis 缓存 | 未完成 | 尚未接入或验证缓存一致性与失效策略 |
| 在线部署体验 | 未完成 | 尚未部署到可访问环境并完成外部链路验证 |
| 3～5 分钟演示视频 | 未完成 | 尚未录制和审核最终演示材料 |
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

1. 获得 C 盘存储影响授权后，执行 `scripts/smoke-docker.ps1 -Execute`，记录真实 Docker/pgvector 证据。
2. 配置脱敏的真实 Embedding Provider，重新记录检索和答案质量，不覆盖 Hash 基线。
3. 配置外部 Issue 测试仓库，执行只读平台 smoke；Token 只从环境变量读取，不写入日志。
4. 设计正式用户、项目成员关系和权限校验，再把当前 capability boundary 迁移为真实授权层。
5. 接入 Redis、在线部署和最终演示材料，并逐项重新审计。

## 安全与资源边界

- 本次审计没有启动 Docker、安装依赖或发起外部网络请求。
- 不读取、输出或提交真实密码、Token、`.env` 文件或用户数据。
- 真实 Docker smoke 可能拉取 pgvector/Python 镜像并创建卷；在获得明确磁盘授权前只允许 Compose dry-run。
