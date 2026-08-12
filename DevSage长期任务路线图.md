# DevSage 长期任务路线图

> 主项目：DevSage
>
> 第一阶段产品：DevMind MVP
>
> 路线状态：持续推进中
>
> 建立时间：2026-07-30

## 总体目标

把当前的 DevSage 阶段 0 骨架推进成一个可运行、可验证、可演示的 Agentic RAG 研发知识库与故障排查系统。

开发顺序遵循：

```text
真实样例数据
    ↓
可测试的数据接入
    ↓
可追溯的检索结果
    ↓
带来源的问答 API
    ↓
人工确认的知识写回
    ↓
多工具 Agent
    ↓
评估、部署与 MCP
```

## 长程任务清单

### 阶段 0：项目边界与样例数据（已完成）

- [x] 合并 DevSage 与 DevMind 项目规划；
- [x] 建立后端、前端、评估和部署骨架；
- [x] 准备脱敏 Spring Boot、Laravel 样例数据；
- [x] 建立第一批 20 条评估问题；
- [x] 建立 JSON、目录和 Python 结构校验。

### 阶段 1：DevMind 数据接入核心（进行中）

- [x] 实现允许扩展名和目录范围控制；
- [x] 实现 Markdown、代码和配置文件加载器；
- [x] 实现 UTF-8 读取和内容 Hash；
- [x] 实现 Markdown 标题结构切分；
- [x] 实现代码类、方法和函数边界切分；
- [x] 为每个 Chunk 保留来源路径、类型和起止行号；
- [x] 实现基础关键词检索；
- [x] 为索引和检索编写无第三方依赖测试；
- [x] 形成可重复运行的本地索引快照，并支持内容 Hash 增量统计。

### 阶段 2：DevMind 可用 MVP

- [x] 接入可选的 OpenAI-compatible Embedding Provider，并保留仅用于离线测试的 Hash Provider；
- [x] 写入 PostgreSQL + pgvector 初始迁移和可选持久化适配器；
- [x] 启动真实 PostgreSQL/pgvector，完成迁移、索引写入和数据库检索 API smoke；
- [x] 实现离线向量检索边界；
- [x] 实现关键词与离线向量的 RRF 融合基线；
- [x] 实现来源引用模型；
- [x] 实现索引 API 和索引变化统计；
- [x] 实现证据约束的问答 API 和 SSE 流式响应；
- [x] 让 PostgreSQL 模式的答案路由读取已持久化 Chunk，普通回答的混合检索走 pgvector 适配器；
- [x] 前端接入基础索引、查询和来源证据展示页；
- [x] 实现项目总结生成；
- [x] 实现知识笔记预览和人工确认后写入项目暂存目录；
- [x] 用第一批测试集验证关键词和混合检索基线。

### 阶段 3：DevSage Agent 工作流

- [x] 使用 LangGraph 定义显式 Agent State；
- [x] 提供可选 LangGraph 适配入口，未安装依赖时显式失败；
- [x] 抽象本地 Agent Graph 节点、状态快照和有限终止契约；
- [x] 实现初版问题分类和有限状态任务流程；
- [x] 实现文档检索、代码检索和安全文件读取工具链；
- [x] 实现初版证据充分性判断和不足时终止；
- [x] 记录 Agent 工具调用与执行步骤；
- [x] 实现透明查询改写和单次有限重试；
- [x] 接入本地 Git 历史查询；
- [x] 接入脱敏 Issue 查询；
- [x] 接入本地 Git Commit Diff 只读查询；
- [x] 接入可选 GitHub-compatible 外部 Issue 只读适配器（真实平台 smoke 待配置）；
- [x] 生成结构化故障排查报告；
- [x] 展示 Agent 节点和工具调用过程；
- [x] 前端展示 Agent 分类、工具链、执行步骤、引用证据和结构化排查报告；
- [x] 增加最大调用次数、图步骤上限和失败终止机制；
- [x] 增加 Git/远程 Embedding 工具超时边界；
- [x] 增加 Agent 全局任务超时；
- [x] 增加 Agent 来源级 grounding 评估，并记录缺失来源案例；
- [x] 增加 Git/Issue 工具的一次有界失败重试策略；

### 阶段 4：工程化与安全审批

- [ ] 实现用户、项目和权限模型；
- [x] 建立本地项目注册与 viewer/editor/operator 能力矩阵边界（正式用户身份认证仍待接入）；
- [x] 让带 `project_id` 的索引、检索、Agent 和知识写回 API 执行本地 actor/action 能力检查；
- [x] 用独立 HTTP smoke 验证 viewer/editor/operator 能力边界和 preview 不写盘；
- [x] 让索引、搜索、问答和 Agent API 支持通过 `project_id` 进入注册项目边界；
- [x] 实现任务状态持久化；
- [x] 将持久化 Agent 任务的 `project_id` 纳入读取/恢复能力检查，并由独立 HTTP smoke 验证成功与拒绝路径；
- [x] 实现受限任务暂停与恢复；
- [x] 实现文件内容 Hash 的增量索引（进程内复用、默认文件快照跨进程恢复、变化统计和 API 回归测试）；
- [x] 实现知识笔记写操作 Diff 预览，并在审批时阻止目标文件的过期覆盖；
- [x] 实现项目内代码文件的 Diff 预览、Hash 防过期覆盖和 operator 批准写入；
- [ ] 实现外部 Issue 写操作审批与真实平台写入；
- [x] 增加不含查询正文的 Agent 完成日志和离线 Token 使用估算（真实 Provider 账单仍待接入）；
- [x] 增加 Redis 缓存，并完成真实命中、TTL 和失效边界 smoke；
- [x] 完善 unittest、接口权限、审批和参数错误场景测试；
- [x] 引入并完善 Pytest 测试运行入口（`pytest.ini`，backend/evaluation 共 129 项：127 passed、2 skipped）；
- [x] 增加默认只读的 Compose 配置校验和显式执行 smoke 脚本；
- [x] 增加只读环境预检入口，报告本地工具、依赖和 Docker daemon 状态；
- [x] 增加只读交付合同审计，校验关键文件、50 条数据集、报告 schema 和数据集 Hash；
- [x] 硬化 Compose 镜像构建边界并声明后端容器健康检查；
- [x] 完善 Docker Compose 本地部署，并完成 Backend、PostgreSQL、Redis 健康检查；在线部署仍待后续。

### 阶段 5：量化评估

- [x] 将测试集扩充到 50 条，继续向 50～100 条范围扩展；
- [x] 为 50 条问题标注正确来源、参考答案和预期工具；
- [x] 对比纯关键词、纯离线 Hash 向量和混合检索，并记录固定 50 条数据集实测结果；
- [x] 对比加入来源多样性 Reranker 前后的效果（仍待真实神经 Reranker）；
- [x] 统计 Recall@5、MRR；
- [x] 统计 Context Precision、Context Recall 的 Chunk 级和来源级代理指标；
- [x] 统计 Faithfulness、Answer Relevance 的离线词法代理，并明确不等同于 LLM 评审；
- [x] 统计 Tool Call Accuracy 的预期工具覆盖率；
- [x] 统计 Agent Source Recall@5 和完整来源案例率；
- [x] 为安全边界问题保留策略文档与配置模板的双来源证据；
- [x] 记录失败案例和每次优化结果；
- [x] 使用实测数据更新 README；
- [x] 形成基于实测数据的简历与面试表述草案（最终简历仍待人工定稿）。

### 阶段 6：MCP 与项目展示

- [x] 封装无第三方依赖的 MCP-compatible stdio Server；
- [x] 暴露 `search_documents`、`search_code`、`read_file`；
- [x] 暴露 `get_git_history` 和 `generate_troubleshooting_report`；
- [x] 提供可重复的 MCP stdio JSON-RPC smoke；
- [x] 完成本地前后端 HTTP 冒烟验证：索引、Agent 查询和结构化报告链路均返回 200；
- [x] 完成浏览器页面加载、样例切换、Vault 切换、答案展示和控制台/网络请求回归；
- [x] 完善架构图、Agent 流程图和 API 文档；
- [x] 编写 3～5 分钟可复现演示脚本；
- [x] 准备脱敏演示数据；
- [ ] 录制 3～5 分钟演示视频；
- [ ] 部署可选在线体验；
- [ ] 整理最终简历和面试材料。

## 当前执行规则

1. 每次只推进一个可验证的小里程碑。
2. 每完成一个模块，立即补测试和知识沉淀。
3. 不安装全局依赖；依赖只进入项目本地配置或容器构建。
4. 不读取、输出或提交真实密码、Token、`.env` 或用户敏感数据。
5. 不因为页面好看而跳过检索来源和评估数据。
6. 不修改原始规划文档，统一规划写入合并文档和本路线图。

## 当前执行项

> 在不破坏离线模式的前提下，准备真实 LangGraph 运行时和 PostgreSQL/pgvector 的可控集成；先保持当前本地 Graph 契约、显式任务快照、测试和离线运行路径不变。

## 2026-08-09 长程集成增量

- [x] 增加可选 Memory/Redis 缓存边界、TTL 和检索响应失效策略；
- [x] 增加 PBKDF2 密码哈希、HMAC Bearer Token、登录和认证依赖；
- [x] 增加远程 Embedding 的批量、超时、维度和响应结构校验；
- [x] 增加外部 Issue 创建预览与 operator 审批写入适配器，默认关闭远程写入；
- [x] 启动真实 Docker PostgreSQL/pgvector/Redis，完成迁移、索引和缓存端到端 smoke；
- [x] 使用浏览器自动化完成页面加载、交互和截图基线回归；像素级差异比较仍作为后续视觉质量增强项；
- [x] 使用用户配置的 Qwen Provider 完成真实远程 smoke；外部 Issue 仓库仍未配置，暂不执行远程写入。

## 2026-08-12 Qwen 与 Vault 闭环增量

- [x] 接入证据约束的 Qwen 答案生成，并保留离线规则答案作为失败回退；
- [x] 默认关闭 Qwen 思考输出，模型上下文限制为 3 条高排名证据摘要、最多 480 个输出 Token；
- [x] 前端增加“判断问题 → 检索证据 → 检查证据 → 生成答案”的长请求阶段提示，并展示 Agent/模型耗时；
- [x] Vault 示例自动切换 `obsidian-vault` 和 `obsidian-viewer`，验证只读页面、相对路径引用和 AI 答案；
- [x] 验证 Redis 检索缓存命中与 TTL：第二次查询约 8ms，缓存 TTL 约 59 秒；
- [x] 固化 `scripts/verify-browser.ps1`，覆盖样例项目和 Vault 项目的浏览器 smoke 与截图输出。
