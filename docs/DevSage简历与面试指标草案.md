# DevSage 简历与面试指标草案

> 状态：基于当前仓库、离线测试和交付审计整理的初稿；正式投递前应结合个人实际职责、项目周期和目标岗位人工定稿。
>
> 数据更新时间：2026-07-30

## 一句话项目介绍

DevSage 是一个面向研发知识库和故障排查的 Agentic RAG 平台，第一阶段 DevMind MVP 负责把 Markdown、代码和配置文档切分为带来源行号的 Chunk，使用关键词与离线向量的 RRF 混合检索生成可引用答案，再通过有限状态 Agent 串联文档、代码、Git、Issue 和审批写回能力。

## 简历短版

负责设计并实现 DevSage/DevMind 研发知识库 MVP：完成 Markdown/代码/配置接入、内容 Hash 增量索引、关键词+Hash 向量 RRF 检索、带引用问答 API、SSE 流式响应和 Vue/Vite 工作台；进一步加入有限状态 Agent、Git/Issue 故障排查、知识与代码 Diff 审批写回、MCP stdio 工具和离线交付门禁，形成可运行、可测试、可演示的本地研发辅助系统。

## 可核验实测指标

| 维度 | 当前结果 | 证据边界 |
|---|---:|---|
| Pytest | `126 passed, 2 skipped` | 当前本地环境；2 项为未安装 LangGraph 的可选测试 |
| Agent Source Recall@5 | `0.9800` | 固定 50 条脱敏评估集 |
| Agent 完整来源案例率 | `0.9600` | 固定 50 条脱敏评估集 |
| Expected Tool Coverage | `0.9333` | 预期工具覆盖率，不是人工判断准确率 |
| Context Recall@5 | `1.0000` | Chunk 级离线代理指标 |
| Context Precision@5 | `0.3095` | 仍需继续优化排序和证据裁剪 |
| MCP 工具 | 5 个 | 已通过本地 JSON-RPC stdio smoke |
| 离线交付门禁 | 17 步 | 包含数据集、评估、测试、MCP、HTTP、一键演示启动、actor capability smoke、前端构建和 Compose dry-run |

## 技术亮点表述

### 检索与问答

- 用统一的答案路由区分普通问答、代码定位、项目总结和知识写回，避免评估脚本与线上 API 使用两套逻辑。
- 为 Chunk 保存来源路径、文件类型和起止行号；答案只引用检索到的证据，并在证据不足时终止或提示边界。
- 对安全配置问题单独保留策略文档与配置模板双来源证据，同时让普通代码定位排除 `.env.example` 等配置模板噪声。

### Agent 与工程化

- 用显式状态、工具调用记录、步骤上限、重试上限和全局超时约束 Agent，避免循环调用和无证据回答。
- 将 Git 历史、Commit Diff、脱敏 Issue 和故障排查报告接入同一套可观测结果，前端展示分类、工具链、步骤、引用和 usage。
- 知识和代码写回均采用 Preview → Diff → Hash 校验 → 显式批准流程；代码写回限制在项目 source root 内的已有文件，审批权限限定为 operator。

### 验证与交付

- 使用固定 50 条问题集对关键词、Hash 向量、RRF 和来源多样性重排做可重复比较，保留 Recall、MRR、上下文质量、工具覆盖率和失败案例。
- 提供 `scripts/verify-offline.ps1`、`scripts/start-demo.ps1` 和 `scripts/preflight.ps1`，分别覆盖离线门禁、一键本地演示和无副作用环境预检。
- 用 fake connection 验证 PostgreSQL/pgvector 应用层合同，用 Compose dry-run 验证配置结构；不把合同测试写成真实基础设施已部署的结论。

## 面试时必须主动说明的边界

- 当前已验证的是内存/文件快照和 PostgreSQL 应用层合同；真实 Docker PostgreSQL/pgvector 容器、迁移、卷恢复和真实查询尚未执行。
- Embedding 默认使用离线 Hash Provider；真实 Embedding Provider 的请求和质量评估尚未配置。
- GitHub-compatible Issue 适配器和 fake transport 已通过合同验证，但真实外部平台只读 smoke 尚未配置。
- `X-DevSage-Actor` 是本地 capability boundary，不等同于正式身份认证；正式用户、组织成员持久化和 Redis 尚未接入。
- 前端已完成 Vite 构建和 HTTP 冒烟，浏览器视觉回归因当前环境缺少浏览器工具仍待执行。

## 面试追问回答要点

### 为什么没有直接宣称“完成 PostgreSQL 部署”？

因为 fake connection 和 Compose dry-run 只能证明应用层调用合同与配置结构，不能证明镜像、容器、迁移、网络、卷恢复和真实 pgvector 查询。交付审计把这两类证据分开记录，真实 Docker smoke 需要明确的资源授权。

### 如何避免 AI 直接修改项目文件？

先生成可审阅的 Diff，再在批准阶段重新读取目标文件并比较 current Hash；目标必须是 source root 内已有文件，路径拒绝绝对路径、`..`、隐藏文件和空内容，最终由 operator action 才允许写入。

### 如何证明 Agent 没有只返回一段看似合理的文字？

响应中保留分类、工具调用、执行步骤、引用证据、结构化故障排查报告和 usage；固定数据集同时评估来源召回、工具覆盖、上下文质量和失败案例，并对越过 `sample-data` 边界的预期案例保留失败记录。

## 证据入口

- [交付就绪审计](./DevSage交付就绪审计.md)
- [长期任务路线图](../DevSage长期任务路线图.md)
- [演示脚本](./DevSage演示脚本.md)
- [演示与 API 手册](./DevSage演示与API手册.md)
- `scripts/verify-offline.ps1`
- `scripts/start-demo.ps1`
- `scripts/preflight.ps1`
