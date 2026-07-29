# DevSage 总体规划与 DevMind MVP 开发计划

> 文档版本：v1.0
>
> 建立时间：2026-07-30
>
> 项目主名称：DevSage
>
> 第一阶段个人版：DevMind

---

## 1. 文档定位

本文档合并并统一原有的《DevMind：程序员个人知识库 Agent 项目规划》和《DevSage 项目规划》，作为项目后续设计、开发、测试、演示和简历整理的统一基线。

本项目不拆成两个互相独立的系统，而是采用“一套核心能力、两个使用场景”的规划方式：

- **DevSage**：面向研发团队的研发知识库与故障排查平台，是项目的总体产品定位和最终展示名称。
- **DevMind**：面向个人开发者的知识库模式，是 DevSage 的第一阶段 MVP，也是最先真正落地和使用的版本。

项目原则：

1. 先完成个人真实可用的最小闭环，再逐步扩展到团队研发场景。
2. 先验证检索质量和来源可信度，再增加复杂 Agent 能力。
3. 所有高风险写操作默认需要人工确认。
4. 所有简历中的效果数据必须来自真实测试，不提前虚构。
5. 保持数据源适配器、检索服务和 Agent 工具之间的边界，避免个人版与团队版重复开发。

---

## 2. 项目总览

### 2.1 一句话介绍

> DevSage 是一个基于 Agentic RAG 的研发知识库与故障排查系统，能够统一检索个人笔记、项目文档、源代码、Git 记录和历史 Issue，生成带证据来源的技术回答、代码定位结果和故障排查方案。

### 2.2 个人版介绍

> DevMind 是 DevSage 的个人知识模式，连接 Obsidian 笔记与个人项目代码，帮助开发者找回过去解决过的问题、总结项目知识，并在人工确认后把新的解决方案沉淀回知识库。

### 2.3 产品关系

```text
                         DevSage
        研发知识库与故障排查平台（总体产品）
                              │
              ┌───────────────┴───────────────┐
              │                               │
       DevMind 个人模式                 DevSage 团队模式
       Obsidian + 个人项目               文档 + 代码 + Git + Issue
       单用户、快速落地                   多项目、协作、故障排查
```

### 2.4 为什么共用一个项目

两个规划的核心链路完全一致：

```text
数据源接入
   ↓
文档解析、代码切分、元数据提取
   ↓
关键词检索 + 向量检索
   ↓
结果融合、重排、证据判断
   ↓
带来源回答或 Agent 多步任务
   ↓
人工确认
   ↓
知识库写回、报告生成或后续扩展操作
```

差异主要是数据源、用户范围和业务复杂度，而不是底层技术路线。因此，重复维护两个仓库会导致检索、索引、Agent 工具和评估系统重复实现，不利于持续迭代。

---

## 3. 项目定位与用户范围

### 3.1 DevMind 个人模式

目标用户是个人开发者、软件工程学生和需要长期沉淀技术经验的程序员。

主要解决：

- 过去记录过的解决方案难以找回；
- 学过的技术分散在 Obsidian、Markdown、代码和项目 README 中；
- AI 生成的内容没有沉淀为自己的长期知识；
- 做完项目后难以快速总结技术点和面试材料。

### 3.2 DevSage 团队模式

目标用户是研发团队中的开发者、测试人员和运维人员。

主要解决：

- 项目文档、代码、Git、Issue 和故障记录分散；
- 开发者需要在多个仓库和系统之间反复搜索；
- 代码定位和故障排查依赖少数熟悉项目的成员；
- 团队知识难以形成可复用、可追溯的资产。

### 3.3 核心竞争力

项目最终围绕以下四项能力建立差异化：

1. **混合检索**：关键词检索负责精确命中，向量检索负责语义召回。
2. **带来源回答**：回答中的关键结论必须能追溯到文件、代码行或历史记录。
3. **多工具 Agent**：根据问题类型选择文档、代码、Git 和 Issue 等工具完成多步任务。
4. **量化评估**：使用真实测试集验证检索质量、回答忠实度和工具调用准确率。

---

## 4. 产品范围与边界

| 能力 | DevMind MVP | DevSage 完整方向 |
|---|---|---|
| 用户范围 | 单用户、本地使用 | 多用户、团队使用 |
| 知识源 | Obsidian Markdown、个人项目代码、README | Markdown、PDF、代码、Git、Issue、故障记录、团队文档 |
| 检索 | 关键词 + 向量检索 | 混合检索、RRF、Reranker、元数据过滤 |
| 回答 | 技术问答、项目总结、来源引用 | 技术问答、代码定位、历史故障排查、研发总结 |
| Agent | 文档检索、代码检索、文件读取 | 文档、代码、文件、Git、Issue、报告、写入等多工具 |
| 写操作 | 确认后写入 Obsidian | 文件修改、知识写入、Issue 创建、补丁应用均需审批 |
| 索引 | 手动索引或简单增量索引 | 内容 Hash、文件变化检测、任务状态和增量索引 |
| 前端 | 简单聊天页、来源卡片 | 项目管理、聊天、任务中心、审批中心、评估面板 |
| 部署 | 本地开发环境 | Docker Compose、一键部署、可选在线演示 |
| 扩展协议 | 预留 MCP 接口 | MCP Server、供 Codex、VS Code 等客户端调用 |

### 4.1 明确不属于 MVP 的内容

第一版不同时开发以下内容：

- 完整多租户权限系统；
- GitHub、GitLab、Jira 等外部平台的正式 OAuth 集成；
- 自动修改代码、自动提交 Git Commit 或自动关闭 Issue；
- 复杂的实时协作和组织管理；
- 在没有评估数据的情况下加入大量模型和 Reranker 对比；
- 为了展示页面而提前建设完整运营后台。

---

## 5. 典型使用场景

### 5.1 DevMind 场景

#### 技术问题回忆

用户提问：

> Spring Boot 8080 端口占用怎么解决？

系统从历史笔记中检索出曾经记录的命令、处理过程和来源文件，并给出带路径引用的回答。

#### 项目知识总结

用户提问：

> 总结我的 Laravel 任务管理系统使用到的后端知识。

系统检索项目 README、代码结构和相关笔记，生成项目知识总结；用户确认后写入 Obsidian 的项目目录。

#### 知识沉淀

用户提问：

> 把这次故障排查过程整理成一篇笔记。

系统生成 Markdown 草稿，展示目标路径和内容预览，用户确认后再写入知识库。

### 5.2 DevSage 场景

#### 代码定位

- 用户登录接口在哪里实现？
- Token 校验逻辑位于哪个类和方法？
- 哪些模块调用了订单服务？

#### 历史故障排查

- 这个报错之前是否出现过？
- 最近一次修改数据库连接配置的提交是什么？
- 当前故障可能与哪些代码变更有关？

#### 研发知识问答

- 当前项目使用了什么认证方式？
- 项目的数据库表关系怎样？
- 项目中使用了哪些设计模式？

#### 团队知识沉淀

- 根据本次故障生成排查报告；
- 根据 Git 提交记录生成开发周报；
- 根据代码和文档生成模块说明；
- 将解决方案整理为团队知识库条目。

---

## 6. 总体技术架构

```text
┌────────────────────────────────────────────┐
│ Vue 3 前端                                  │
│ 聊天 / 来源卡片 / 文件预览 / 任务状态 / 审批  │
└──────────────────┬─────────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼─────────────────────────┐
│ FastAPI 应用层                               │
│ 项目 / 对话 / 索引 / 来源 / 审批 / 评估 API    │
└──────────────────┬─────────────────────────┘
                   │
┌──────────────────▼─────────────────────────┐
│ Agent 编排层                                 │
│ 问题分类 / 任务规划 / 工具调用 / 重试 / 审批    │
└──────────────┬──────────────────┬───────────┘
               │                  │
┌──────────────▼─────────┐  ┌────▼─────────────┐
│ 检索服务                │  │ 工具服务          │
│ 全文 / 向量 / RRF / 重排 │  │ 文档 / 代码 / Git │
│ 过滤 / 证据评分          │  │ Issue / 写回      │
└──────────────┬─────────┘  └────┬─────────────┘
               │                  │
┌──────────────▼──────────────────▼───────────┐
│ PostgreSQL + pgvector + 可选 Redis            │
│ 项目 / 文档 / Chunk / 向量 / 对话 / 任务 / 审批 │
└─────────────────────────────────────────────┘
```

### 6.1 核心模块

1. **数据源适配层**：负责读取 Obsidian、Markdown、代码、Git 和 Issue 数据。
2. **解析与切分层**：根据内容类型提取结构和行号信息。
3. **索引层**：生成 Embedding、保存全文索引和向量索引。
4. **检索层**：执行关键词召回、向量召回、结果融合、重排和元数据过滤。
5. **Agent 层**：判断问题类型、选择工具、检查证据并控制任务终止。
6. **应用层**：提供项目、对话、来源、审批和评估接口。
7. **知识写回层**：在用户确认后生成或更新 Markdown 知识条目。
8. **评估层**：使用固定测试集比较检索和 Agent 的实际效果。

---

## 7. 数据接入与索引设计

### 7.1 数据源优先级

#### DevMind MVP

第一批只接入：

- Obsidian Markdown：`.md`；
- 项目 README 和开发文档；
- Java、PHP、Python、JavaScript、TypeScript 代码；
- 常见配置文件：`.yml`、`.yaml`、`.json`、`.properties`。

#### DevSage 后续

扩展：

- PDF；
- Git 提交记录和 Commit Diff；
- 本地导出的 Issue；
- GitHub、GitLab、Jira、Confluence；
- MCP 客户端提供的外部知识源。

### 7.2 切分原则

不同内容不能强制使用同一种 Chunk 策略。

| 内容类型 | 优先切分单位 | 必须保留的元数据 |
|---|---|---|
| Markdown | 标题层级、段落、代码块 | 文件路径、标题层级、行号、更新时间 |
| 源代码 | 类、方法、函数、接口、配置块 | 仓库、路径、语言、类名、方法名、起止行号 |
| 配置文件 | 配置段、键值块 | 文件路径、配置键、环境标识、行号 |
| Git | Commit、文件 Diff、提交说明 | Commit Hash、作者、时间、文件路径 |
| Issue | 标题、描述、报错、解决方案 | Issue 编号、标签、状态、关联提交 |

### 7.3 增量索引

索引流程：

```text
扫描文件
   ↓
计算 content_hash
   ↓
与 documents 记录比较
   ├── 未变化：跳过
   ├── 新文件：解析、切分、生成向量
   └── 已变化：只删除旧 Chunk 并重建该文件
```

增量索引必须以文件路径和内容 Hash 为基础，避免每次修改一个文件都重新处理整个知识库。

---

## 8. RAG 检索设计

### 8.1 混合检索流程

```text
用户问题
   ↓
问题预处理与关键词提取
   ↓
元数据过滤
   ↓
PostgreSQL 全文/关键词召回 + pgvector 向量召回
   ↓
RRF 结果融合
   ↓
可选 Reranker 重排
   ↓
Top-K 证据与来源信息
```

关键词检索适合报错名称、端口号、类名、方法名、配置项和 Commit Hash；向量检索适合自然语言问题、相似故障描述和不同表述下的语义匹配。

### 8.2 RRF

```text
RRF Score = Σ 1 / (k + rank)
```

其中 `rank` 是结果在某个检索列表中的排名，`k` 是平滑参数。第一版使用固定参数，待评估数据稳定后再调整。

### 8.3 查询改写

当原始问题过于模糊时，Agent 可以生成多个检索表达：

```text
原始问题：登录功能在哪里？

检索表达：
- 用户登录接口实现文件
- authentication login controller
- Sanctum Token 登录逻辑
- login method user authentication
```

### 8.4 证据充分性

回答前至少检查：

- 是否检索到与问题直接相关的文件；
- 是否存在明确的类名、方法名、错误信息或配置项；
- 多条证据是否相互支持；
- 结果之间是否存在冲突；
- 证据评分是否达到当前任务阈值。

证据不足时，系统最多重新改写和检索若干次；仍不足时必须明确告诉用户，不能用猜测填补来源空缺。

### 8.5 来源展示

每个关键结论至少关联以下一种来源：

- 文件路径；
- Markdown 标题或行号范围；
- 代码文件、类名、方法名和起止行号；
- Issue 编号；
- Git Commit Hash 和 Diff 文件。

前端应支持点击来源查看原文，并在代码预览中高亮引用行。

---

## 9. Agent 工作流设计

### 9.1 工作流

```text
问题分类
   ↓
任务规划
   ↓
选择工具
   ↓
执行检索或读取
   ↓
证据充分性判断
   ├── 不充分：查询改写并重新检索
   └── 充分：生成带来源回答
                    ↓
              是否需要写操作
                 ├── 否：返回结果
                 └── 是：生成操作预览并等待确认
```

### 9.2 问题分类

- 文档知识问答；
- 代码定位；
- 故障排查；
- Git 历史查询；
- Issue 查询；
- 项目总结；
- 知识库写入；
- 代码修改建议。

### 9.3 工具分阶段接入

#### DevMind MVP 工具

```python
search_documents(query, filters)
search_code(query, repository, language)
read_file(path, start_line, end_line)
generate_project_summary(context)
create_knowledge_note_preview(title, content, path)
```

#### DevSage 扩展工具

```python
search_issues(query, status, labels)
get_git_history(path, keyword, time_range)
get_commit_diff(commit_hash)
generate_troubleshooting_report(context)
create_knowledge_note(title, content, path)
create_issue_preview(title, description, labels)
generate_code_patch_preview(file_path, requirement)
```

### 9.4 Agent 安全边界

第一版建议限制：

```text
最大工具调用次数：8
最大重新检索次数：2
最大连续失败次数：2
```

同时增加重复查询检测、超时控制、路径白名单和工具参数校验，避免 Agent 无限循环或访问知识库范围之外的文件。

---

## 10. Human-in-the-loop

### 10.1 可自动执行的只读操作

- 检索文档；
- 检索代码；
- 读取文件；
- 查询 Issue；
- 查询 Git 提交；
- 生成回答、总结和排查方案。

### 10.2 必须确认的写操作

- 创建或修改 Obsidian 笔记；
- 修改项目文件；
- 创建 Issue；
- 应用代码补丁；
- 提交 Git Commit；
- 批量更新知识库内容。

### 10.3 审批界面要求

确认前必须展示：

- 即将执行的操作；
- 目标文件、目标仓库或目标 Issue；
- 修改前后 Diff；
- 操作风险；
- 确认和拒绝按钮。

系统不能把“生成建议”和“真正写入”混为一个动作。DevMind 的第一版也必须保持这个边界。

---

## 11. 推荐技术栈

| 模块 | DevMind MVP | DevSage 完整方向 |
|---|---|---|
| 后端 | Python + FastAPI | Python + FastAPI |
| Agent 编排 | 简单任务路由，预留 State | LangGraph |
| 数据库 | PostgreSQL + pgvector | PostgreSQL + pgvector |
| 关键词检索 | PostgreSQL Full Text Search | PostgreSQL Full Text Search + 优化策略 |
| 缓存 | 暂不强制 | Redis |
| 前端 | Vue 3 + TypeScript | Vue 3 + TypeScript + Element Plus |
| Embedding | 可配置的云端 API 或本地模型 | BGE-M3 或可替换 Embedding 服务 |
| Reranker | 后续加入 | BGE Reranker 或同类模型 |
| 评估 | 自定义固定测试脚本 | Ragas + 自定义评估脚本 |
| 部署 | 本地运行 | Docker Compose |
| 扩展协议 | 预留接口 | MCP Server |
| 测试 | Pytest + 检索断言 | Pytest + Agent、接口和评估测试 |

模型服务、数据库连接和第三方平台密钥只能通过环境变量配置；仓库中只提交 `.env.example`，不提交真实密钥、Token 或密码。

---

## 12. 数据模型

### 12.1 MVP 最小数据表

```text
projects
documents
chunks
conversations
messages
evaluation_cases
evaluation_results
```

核心字段：

- `projects`：项目名称、描述、根目录或仓库路径；
- `documents`：项目 ID、文件路径、文件类型、内容 Hash、更新时间；
- `chunks`：文档 ID、内容、Embedding、起止行号、结构化元数据；
- `conversations`：会话、用户和项目范围；
- `messages`：用户问题、回答、来源和 Token 使用量；
- `evaluation_cases`：问题、正确来源、参考答案和预期工具；
- `evaluation_results`：Recall@K、MRR、Faithfulness 等测试结果。

### 12.2 DevSage 扩展数据表

```text
users
agent_tasks
tool_calls
approvals
issues
commits
projects_members
```

其中 `agent_tasks` 保存任务状态和当前节点，`tool_calls` 保存工具名、参数、结果、耗时和成功状态，`approvals` 保存待确认操作和 Diff。日志中不得写入密码、Token 或其他敏感内容。

---

## 13. API 规划

### 13.1 DevMind MVP API

```text
POST /api/projects
GET  /api/projects
POST /api/projects/{id}/index
GET  /api/projects/{id}/index-status

POST /api/conversations
GET  /api/conversations/{id}
POST /api/conversations/{id}/messages
GET  /api/conversations/{id}/stream

GET  /api/sources/{chunk_id}
GET  /api/files/content
POST /api/knowledge-notes/preview
POST /api/knowledge-notes/{id}/approve
```

### 13.2 DevSage 扩展 API

```text
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/profile

GET  /api/tasks
GET  /api/tasks/{id}
GET  /api/tasks/{id}/tool-calls

GET  /api/approvals
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/reject

POST /api/evaluations/run
GET  /api/evaluations/results
GET  /api/evaluations/compare
```

接口设计应优先支持单项目、单用户的 MVP，后续再增加用户权限和多项目隔离，避免一开始就把认证系统变成主要工作量。

---

## 14. 前端页面规划

### 14.1 DevMind MVP 页面

1. **知识库配置页**：选择 Obsidian 目录和项目目录，查看文件与 Chunk 数量。
2. **索引状态页**：显示索引进度、成功数量、失败文件和最近更新时间。
3. **智能问答页**：项目选择、流式回答、来源卡片和代码行号。
4. **知识写回预览页**：展示生成的 Markdown、目标路径和确认按钮。

### 14.2 DevSage 扩展页面

1. 登录与注册页；
2. 项目管理页；
3. 对话与来源页；
4. Agent 任务中心；
5. 工具调用详情页；
6. 审批中心；
7. 评估面板。

---

## 15. 分阶段开发计划

### 阶段 0：项目边界和样例数据

目标：建立可以持续开发的最小工程骨架。

任务：

- 创建后端和前端基础目录；
- 选取自己的 Obsidian 笔记和 1～2 个真实项目作为样例数据；
- 明确允许索引的目录范围；
- 创建 `.env.example`，不放入真实密钥；
- 编写最小数据结构和索引接口；
- 先准备 20～30 条真实测试问题。

交付物：

- 可启动的项目骨架；
- 脱敏样例数据；
- 第一版测试问题集；
- 数据源和安全边界说明。

### 阶段 1：DevMind MVP

目标：完成个人知识库问答和知识写回闭环。

必须完成：

- 支持 Markdown、README 和至少三种编程语言代码导入；
- 按内容类型切分并保留文件路径、标题和行号；
- 生成 Embedding 并保存到 pgvector；
- 实现 PostgreSQL 关键词检索；
- 实现向量检索和基础 RRF 融合；
- 实现带来源的问答；
- 实现文档检索、代码检索和文件读取工具；
- 实现项目知识总结；
- 实现知识笔记预览和人工确认写回 Obsidian；
- 完成基础聊天页面；
- 用固定测试集验证检索结果。

交付物：

- 可本地运行的 DevMind；
- 一个真实个人知识库；
- 一个真实项目知识库；
- 带文件路径和代码行号的回答；
- 通过确认后写回的 Markdown 笔记；
- MVP 测试记录。

### 阶段 2：DevSage Agent 工作流

目标：从知识问答升级为多步研发任务助手。

任务：

- 使用 LangGraph 定义 Agent State；
- 实现问题分类和任务规划节点；
- 接入 Git 历史和 Issue 检索工具；
- 实现查询改写、证据判断和有限重试；
- 实现代码定位和历史故障排查；
- 生成结构化故障排查报告；
- 展示 Agent 执行步骤和工具调用结果；
- 为每个任务设置调用次数、超时和失败终止条件。

交付物：

- 多工具 Agent；
- 可追溯的执行过程；
- 故障排查报告；
- Agent 失败和重试记录。

### 阶段 3：工程化与人工审批

目标：提高系统安全性、可维护性和可部署性。

任务：

- 增加用户、项目和权限模型；
- 持久化 Agent 任务状态；
- 实现任务暂停和恢复；
- 实现写操作审批和 Diff 展示；
- 实现文件 Hash 去重和增量索引；
- 增加 Redis 缓存；
- 增加日志、Token 统计和异常处理；
- 完善 Pytest 自动化测试；
- 使用 Docker Compose 组织服务。

交付物：

- 审批中心；
- 增量索引；
- 系统日志和统计；
- 自动化测试报告；
- Docker Compose 部署配置。

### 阶段 4：量化评估

目标：用数据证明系统的检索和 Agent 效果。

任务：

- 将测试集扩展到 50～100 条问题；
- 标注每个问题的正确来源和参考答案；
- 标注预期工具和合理调用顺序；
- 对比纯向量、纯关键词和混合检索；
- 对比加入 Reranker 前后的效果；
- 统计 Recall@5、MRR、Context Precision、Context Recall；
- 统计 Faithfulness、Answer Relevance、Tool Call Accuracy；
- 分析失败案例并记录优化结论。

交付物：

- 自建评估数据集；
- 检索策略对比报告；
- Agent 工具调用评估报告；
- 真实优化数据。

### 阶段 5：MCP 与项目展示

目标：提高项目的可复用性和简历展示效果。

任务：

- 将检索和代码理解能力封装为 MCP Server；
- 暴露 `search_documents`、`search_code`、`read_file` 等工具；
- 完善 README、架构图和 Agent 流程图；
- 准备脱敏演示数据；
- 录制 3～5 分钟演示视频；
- 根据真实测试结果更新简历描述；
- 如确有需要，再部署在线体验地址。

交付物：

- MCP Server；
- 完整 GitHub 项目；
- 项目演示视频；
- 技术文档和评估报告；
- 真实数据支撑的简历项目描述。

---

## 16. 建议目录结构

```text
DevSage/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   │   ├── graph.py
│   │   │   ├── nodes.py
│   │   │   ├── state.py
│   │   │   └── prompts.py
│   │   ├── tools/
│   │   │   ├── document_tools.py
│   │   │   ├── code_tools.py
│   │   │   ├── git_tools.py
│   │   │   └── issue_tools.py
│   │   ├── retrieval/
│   │   │   ├── vector_search.py
│   │   │   ├── keyword_search.py
│   │   │   ├── rrf.py
│   │   │   └── reranker.py
│   │   ├── ingestion/
│   │   │   ├── loaders.py
│   │   │   ├── markdown_splitter.py
│   │   │   ├── code_splitter.py
│   │   │   └── indexer.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── core/
│   │   └── main.py
│   ├── tests/
│   ├── migrations/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   └── router/
│   ├── package.json
│   └── Dockerfile
├── evaluation/
│   ├── datasets/
│   ├── scripts/
│   └── reports/
├── sample-data/
│   ├── docs/
│   ├── repositories/
│   └── issues/
├── mcp-server/
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── retrieval-design.md
│   └── agent-design.md
├── docker-compose.yml
├── .env.example
├── README.md
└── LICENSE
```

MVP 可以先只创建 `backend`、`frontend`、`evaluation` 和 `docs`，不要为了目录完整而提前实现所有扩展模块。

---

## 17. 测试与评估方案

### 17.1 测试问题示例

```json
{
  "question": "Spring Boot 8080 端口被占用怎么处理？",
  "expected_sources": ["docs/springboot-errors.md"],
  "reference_answer": "使用 netstat 查询占用端口的 PID，并结束对应进程或修改服务端口。",
  "expected_tools": ["search_documents", "read_file"]
}
```

```json
{
  "question": "Laravel 项目使用了什么认证方式？",
  "expected_sources": ["README.md", "app/Http/Controllers/AuthController.php"],
  "reference_answer": "项目使用 Laravel Sanctum 和 Bearer Token 认证。",
  "expected_tools": ["search_documents", "search_code"]
}
```

### 17.2 最低验证要求

每次修改检索逻辑后至少验证：

- 正确来源是否进入 Top-K；
- 文件路径和行号是否准确；
- 回答是否引用了实际检索到的证据；
- 无证据时是否明确拒答或说明不足；
- Agent 是否在达到上限后正常终止；
- 写操作是否始终停在确认界面。

### 17.3 指标

#### 检索指标

- Recall@5：正确来源是否出现在前 5 条结果中；
- MRR：正确来源的平均排名；
- Context Precision：召回上下文中相关内容的比例；
- Context Recall：问题所需信息被召回的比例。

#### 生成指标

- Faithfulness：回答是否基于证据；
- Answer Relevance：回答是否直接回应问题。

#### Agent 指标

- Tool Call Accuracy；
- Tool Call Order Accuracy；
- Agent Goal Accuracy；
- Task Completion Rate。

#### 工程指标

- 平均响应时间；
- 首 Token 响应时间；
- 工具调用成功率；
- 全量索引时间；
- 增量索引时间；
- 单次任务 Token 消耗。

任何“提升 XX%”的表述都必须在评估完成后填写，不能在项目尚未测试时写入简历。

---

## 18. 项目完成标准

### 18.1 DevMind MVP 完成标准

- [ ] 能索引 Obsidian Markdown 和至少一个真实项目；
- [x] 支持至少三种编程语言代码（Java、PHP、TypeScript 已有加载与切分回归测试）；
- [x] Markdown 与代码使用不同切分策略（标题元数据与代码结构元数据均有回归测试）；
- [x] 支持关键词和向量检索；
- [x] 回答显示文件路径和代码行号；
- [x] 支持文档检索、代码检索和文件读取；
- [x] 能生成项目知识总结；
- [ ] 写回 Obsidian 前有人工确认；
- [x] 建立至少 20～30 条基础测试问题（当前 50 条）；
- [x] 能记录基础检索结果和失败案例；
- [x] README 能说明启动方式、数据范围和安全边界。

### 18.2 DevSage 完整展示标准

- [x] 支持文档、代码、Git 和 Issue 数据检索；
- [x] 实现混合检索、RRF 和可选 Reranker（当前为可解释的来源多样性重排，神经 Cross-Encoder 待后续）；
- [x] Agent 至少拥有 5 个可用工具；
- [x] Agent 能完成多步代码定位或故障排查；
- [x] 支持证据判断、查询改写、重试和终止；
- [x] 写操作支持审批和 Diff 展示；
- [x] 支持增量索引和任务状态记录；
- [x] 建立至少 50 条评估数据；
- [x] 输出真实 Recall@5、MRR 和工具调用准确率（当前为固定脱敏数据和可解释代理指标）；
- [ ] 支持 Docker Compose 一键启动；
- [ ] 提供完整 README、架构图和演示视频；
- [x] 提供 MCP Server 或明确的扩展接口。

---

## 19. 简历与面试定位

### 19.1 DevMind MVP 阶段描述

> 开发基于 Agentic RAG 的个人程序员知识库助手 DevMind，接入 Obsidian Markdown、项目文档和多种编程语言代码，使用关键词与向量混合检索返回带文件路径和代码行号的技术回答；支持项目知识总结和人工确认后的 Markdown 知识写回，并通过自建测试集验证检索结果质量。

### 19.2 DevSage 完成后描述

> 基于 FastAPI、Vue 3、LangGraph、PostgreSQL 和 pgvector 开发面向研发团队的智能知识库与故障排查系统，统一索引项目文档、源代码、Git 提交记录和历史 Issue，实现关键词与向量混合召回、RRF 融合、Reranker 重排、查询改写、证据判断和多工具 Agent 工作流；针对文件修改、Issue 创建和代码补丁应用设计 Human-in-the-loop 审批机制，并通过 Recall@5、MRR、Faithfulness 和 Tool Call Accuracy 对系统效果进行量化评估。

### 19.3 面试重点

#### 检索

- 为什么代码检索不能只使用向量检索？
- 为什么报错名称、端口号和方法名适合关键词检索？
- RRF 如何融合不同检索结果？
- Markdown 和代码为什么需要不同切分策略？
- 如何实现增量索引和避免重复生成向量？

#### Agent

- Agent 如何判断调用哪个工具？
- 如何判断证据是否充分？
- 如何避免 Agent 无限循环？
- 写操作为什么必须人工确认？
- Agent 失败后如何恢复和记录？

#### 评估

- Recall@5 和 MRR 的区别是什么？
- 如何构建 RAG 测试集？
- 如何证明混合检索优于纯向量检索？
- 如何评估 Agent 是否选择了正确工具？

---

## 20. 最终决策

1. 项目只维护一个主项目：**DevSage**。
2. **DevMind** 作为 DevSage 的个人模式、第一阶段 MVP 和真实使用入口。
3. 第一阶段优先完成 Obsidian + 个人项目 + 混合检索 + 来源引用 + 确认写回。
4. 第二阶段再加入 LangGraph、多工具 Agent、Git、Issue 和故障排查。
5. 第三阶段完善审批、增量索引、任务持久化、评估和 Docker 部署。
6. 最后通过 MCP、演示视频和真实评估数据完成项目展示。

最终项目不应被描述为“普通 AI 聊天机器人”，而应统一定位为：

> **DevSage——基于 Agentic RAG 的研发知识库与故障排查系统；DevMind 是其面向个人开发者的知识沉淀模式。**
