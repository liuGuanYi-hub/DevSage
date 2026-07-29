# DevSage——基于 Agentic RAG 的研发知识库与故障排查系统

> 面向软件研发团队的智能知识检索与故障排查平台。系统统一接入项目文档、源代码、Git 提交记录、Issue、历史报错及运维知识，通过混合检索、Agent 多步推理和人工审核机制，为开发者提供带证据来源的技术问答、代码定位与故障排查能力。

---

## 1. 项目定位

### 1.1 项目背景

传统研发团队的知识通常分散在以下位置：

- 项目 README 和开发文档
- API 接口文档
- Java、PHP、Python 等项目源代码
- Git 提交记录
- Issue、Bug 记录和历史报错
- 运维故障处理文档
- 团队成员个人笔记

开发者遇到问题时，往往需要在多个仓库、文档和记录中反复搜索，排查效率较低。普通的 PDF 问答系统只能进行单一文档检索，难以完成代码、Issue、Git 记录之间的多步关联分析。

DevSage 将这些异构研发知识统一索引，通过 Agentic RAG 完成问题识别、工具选择、多轮检索、证据判断和故障报告生成。

### 1.2 项目目标

DevSage 需要实现以下核心目标：

1. 统一接入研发文档、代码、Git、Issue 和故障记录。
2. 支持关键词检索与向量语义检索相结合。
3. 回答必须附带文件路径、代码位置或文档来源。
4. Agent 能够根据问题选择不同工具并执行多步任务。
5. 在证据不足时自动改写查询并重新检索。
6. 对修改文件、创建 Issue、生成补丁等操作进行人工确认。
7. 使用测试集量化评估检索与 Agent 效果。
8. 通过 Docker Compose 实现一键部署。

### 1.3 项目一句话介绍

> DevSage 是一个基于 Agentic RAG 的研发知识库与故障排查系统，能够从项目文档、代码、Git 和历史 Issue 中检索证据，生成带来源引用的回答与排查方案。

---

## 2. 典型使用场景

用户可以向系统提出以下问题：

### 2.1 技术知识问答

- Spring Boot 8080 端口被占用应该怎么处理？
- Laravel 项目使用了什么认证方式？
- 当前项目的数据库表关系是怎样的？
- 项目中使用了哪些设计模式？

### 2.2 代码定位

- 用户登录接口在哪些文件中实现？
- Token 校验逻辑位于哪个类？
- 哪些模块调用了订单服务？
- `BeanCreationException` 可能与哪些配置文件有关？

### 2.3 历史故障排查

- 这个报错之前是否出现过？
- 根据历史 Issue 给出排查步骤。
- 最近一次修改数据库连接配置的提交是什么？
- 当前故障可能与哪些代码变更有关？

### 2.4 知识沉淀

- 根据本次故障生成排查报告。
- 将解决方案整理成知识库笔记。
- 根据 Git 提交记录生成本周开发总结。
- 根据代码和文档生成模块说明。

---

## 3. 核心功能规划

## 3.1 多数据源接入

第一阶段支持以下文件类型：

- Markdown：`.md`
- PDF：`.pdf`
- Java：`.java`
- Python：`.py`
- PHP：`.php`
- JavaScript、TypeScript：`.js`、`.ts`
- 配置文件：`.yml`、`.yaml`、`.json`、`.properties`
- Git 提交记录
- 本地导出的 Issue 数据

后期可以扩展：

- GitHub API
- GitLab API
- Jira
- Confluence
- Obsidian Vault
- MCP 客户端

## 3.2 文档解析与切分

不同内容需要采用不同的切分策略。

### Markdown 文档

按照以下结构切分：

- 一级标题
- 二级标题
- 三级标题
- 段落
- 代码块

保留元数据：

- 文件路径
- 标题层级
- 所属项目
- 技术栈
- 更新时间
- 行号范围

### 源代码

优先按照代码结构切分：

- 类
- 方法
- 函数
- 接口
- 配置块

每个代码块保留：

- 仓库名称
- 文件路径
- 编程语言
- 类名
- 方法名
- 起止行号
- Git Commit Hash

### Issue 与故障记录

按照以下字段建立索引：

- Issue 标题
- 问题描述
- 报错信息
- 解决方案
- 相关文件
- 关联提交
- 标签
- 创建时间

---

## 4. RAG 检索设计

## 4.1 混合检索

DevSage 不只依赖向量检索，而是使用以下组合：

1. PostgreSQL 全文检索或 BM25 关键词检索
2. pgvector 向量语义检索
3. 元数据过滤
4. RRF 结果融合
5. Reranker 重排

### 为什么需要混合检索

关键词检索适合：

- 报错名称
- 端口号
- 类名
- 方法名
- 配置项
- Commit Hash

向量检索适合：

- 自然语言问题
- 相似故障描述
- 含义相近但表述不同的文档
- 跨文档语义关联

## 4.2 检索流程

```text
用户问题
   ↓
问题预处理
   ↓
关键词提取与查询改写
   ↓
元数据过滤
   ↓
关键词召回 + 向量召回
   ↓
RRF 融合
   ↓
Reranker 重排
   ↓
返回 Top-K 证据
```

## 4.3 RRF 融合

RRF 用于融合关键词检索和向量检索的排序结果。

计算思路：

```text
RRF Score = Σ 1 / (k + rank)
```

其中：

- `rank` 为文档在某个检索结果中的排名
- `k` 为平滑参数

第一版可以先使用固定参数，后续通过评估测试调整。

## 4.4 查询改写

系统需要将模糊问题改写为更适合检索的查询。

示例：

```text
原始问题：登录功能在哪里？

改写结果：
- 用户登录接口实现文件
- authentication login controller
- Sanctum Token 登录逻辑
- login method user authentication
```

## 4.5 证据充分性判断

Agent 根据以下条件判断证据是否足够：

- 是否检索到与问题直接相关的文件
- 是否存在明确的方法名、类名或错误信息
- 多条证据是否相互支持
- 检索结果是否存在冲突
- 证据评分是否达到阈值

证据不足时：

1. 重新生成检索关键词；
2. 调整数据源；
3. 扩大 Top-K；
4. 检索 Git 或 Issue；
5. 明确告诉用户当前证据不足。

---

## 5. Agent 工作流设计

## 5.1 Agent 节点

建议使用 LangGraph 实现以下节点：

```text
问题分类
   ↓
任务规划
   ↓
工具选择
   ↓
执行检索
   ↓
证据充分性判断
   ├── 不充分：查询改写并重新检索
   └── 充分：生成回答
                 ↓
           是否需要执行写操作
                 ├── 否：返回结果
                 └── 是：等待人工确认
```

## 5.2 问题分类

问题可以分为：

- 文档知识问答
- 代码定位
- 故障排查
- Git 历史查询
- Issue 查询
- 项目总结
- 知识库写入
- 代码修改建议

## 5.3 Agent 工具

```python
search_documents(query, filters)
search_code(query, repository, language)
read_file(path, start_line, end_line)
search_issues(query, status, labels)
get_git_history(path, keyword, time_range)
get_commit_diff(commit_hash)
generate_troubleshooting_report(context)
create_knowledge_note(title, content, path)
create_issue(title, description, labels)
generate_code_patch(file_path, requirement)
```

## 5.4 Agent 终止条件

为了避免 Agent 无限循环，需要设置：

- 最大工具调用次数
- 最大重新检索次数
- 最大 Token 消耗
- 最长执行时间
- 证据评分阈值
- 重复查询检测

建议第一版设置：

```text
最大工具调用次数：8
最大重新检索次数：2
最大连续失败次数：2
```

---

## 6. 带来源回答设计

回答中的重要结论必须附带来源。

示例：

```text
结论：Spring Boot 启动失败是因为 8080 端口已被 PID 24956 占用。

建议排查步骤：
1. 使用 netstat 查询端口占用进程。
2. 根据 PID 查找对应程序。
3. 结束进程或修改 Spring Boot 端口。

依据：
- docs/springboot-errors.md，第 28～36 行
- issues/issue-014.md
- backend/src/main/resources/application.yml，第 2～4 行
```

前端需要支持：

- 展示文件路径
- 展示代码行号
- 展示相似度或证据评分
- 点击来源查看原文
- 高亮引用片段

---

## 7. Human-in-the-loop 设计

以下只读操作可以自动执行：

- 检索文档
- 检索代码
- 读取文件
- 查询 Issue
- 查询 Git 提交
- 生成排查方案

以下写操作必须经过用户确认：

- 修改知识库文件
- 修改项目代码
- 创建 Issue
- 关闭 Issue
- 生成并应用代码补丁
- 提交 Git Commit

确认界面需要展示：

- 即将执行的操作
- 目标文件或目标仓库
- 修改前后差异
- 操作风险
- 确认和拒绝按钮

---

## 8. 系统技术架构

```text
┌──────────────────────────────┐
│          Vue 3 前端           │
│ 聊天 / 来源展示 / 任务状态 / 审批 │
└──────────────┬───────────────┘
               │ HTTP / SSE
┌──────────────▼───────────────┐
│         FastAPI 后端          │
│ 用户、知识库、会话、任务、评估接口 │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│        LangGraph Agent        │
│ 路由 / 工具调用 / 重试 / 人工审批 │
└───────┬──────────┬───────────┘
        │          │
┌───────▼──────┐  ┌▼────────────────┐
│ 检索服务      │  │ 工具服务          │
│ 向量/全文/重排 │  │ Git/Issue/文件读取 │
└───────┬──────┘  └┬────────────────┘
        │           │
┌───────▼───────────▼───────────────┐
│ PostgreSQL + pgvector + Redis     │
│ 文档、向量、用户、会话、任务、缓存     │
└───────────────────────────────────┘
```

---

## 9. 推荐技术栈

| 模块 | 技术选择 |
|---|---|
| 后端 | Python + FastAPI |
| Agent 编排 | LangGraph |
| 关系数据库 | PostgreSQL |
| 向量数据库 | pgvector |
| 关键词检索 | PostgreSQL Full Text Search |
| 缓存 | Redis |
| 前端 | Vue 3 + TypeScript |
| UI 组件 | Element Plus |
| Embedding | BGE-M3 或云端 Embedding API |
| Reranker | BGE Reranker |
| 模型接口 | OpenAI 兼容 API 或国产模型 API |
| 评估 | Ragas + 自定义测试脚本 |
| 部署 | Docker Compose |
| 测试 | Pytest |
| 扩展协议 | MCP Server |

---

## 10. 数据库设计建议

## 10.1 核心数据表

### users

- id
- username
- password_hash
- created_at

### projects

- id
- name
- description
- repository_path
- created_at

### documents

- id
- project_id
- file_path
- file_type
- content_hash
- updated_at

### chunks

- id
- document_id
- content
- embedding
- start_line
- end_line
- metadata

### conversations

- id
- user_id
- project_id
- title
- created_at

### messages

- id
- conversation_id
- role
- content
- token_usage
- created_at

### agent_tasks

- id
- conversation_id
- task_type
- status
- current_node
- retry_count
- started_at
- finished_at

### tool_calls

- id
- task_id
- tool_name
- arguments
- result
- duration_ms
- success

### approvals

- id
- task_id
- operation_type
- target
- diff_content
- status
- reviewed_at

### evaluation_cases

- id
- question
- expected_sources
- reference_answer
- expected_tools

### evaluation_results

- id
- case_id
- recall_at_5
- mrr
- faithfulness
- tool_call_accuracy
- created_at

---

## 11. API 规划

### 用户接口

```text
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/profile
```

### 项目接口

```text
POST /api/projects
GET  /api/projects
GET  /api/projects/{id}
POST /api/projects/{id}/index
GET  /api/projects/{id}/index-status
```

### 对话接口

```text
POST /api/conversations
GET  /api/conversations
GET  /api/conversations/{id}
POST /api/conversations/{id}/messages
GET  /api/conversations/{id}/stream
```

### 来源接口

```text
GET /api/sources/{chunk_id}
GET /api/files/content
```

### 审批接口

```text
GET  /api/approvals
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/reject
```

### 评估接口

```text
POST /api/evaluations/run
GET  /api/evaluations/results
GET  /api/evaluations/compare
```

---

## 12. 前端页面规划

### 12.1 登录页

- 用户登录
- 用户注册

### 12.2 项目管理页

- 创建项目
- 配置项目目录
- 查看索引状态
- 手动触发索引
- 查看文件数量和 Chunk 数量

### 12.3 智能问答页

- 项目选择
- 对话列表
- 流式回答
- Agent 执行步骤
- 来源卡片
- 文件预览
- 代码高亮

### 12.4 任务中心

- Agent 任务状态
- 工具调用记录
- 执行耗时
- 失败原因
- 重试按钮

### 12.5 审批中心

- 待审批操作
- 修改 Diff
- 风险提示
- 批准或拒绝

### 12.6 评估面板

- Recall@K
- MRR
- Faithfulness
- Tool Call Accuracy
- 不同检索策略对比
- 失败案例分析

---

## 13. 项目目录结构建议

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

---

## 14. 分阶段开发计划

# 第一阶段：基础 RAG

目标：完成一个可以稳定运行和演示的研发知识库问答系统。

### 开发任务

- [ ] 创建 FastAPI 项目
- [ ] 创建 Vue 3 前端项目
- [ ] 搭建 PostgreSQL、pgvector、Redis
- [ ] 完成用户注册和登录
- [ ] 完成项目管理功能
- [ ] 支持 Markdown、PDF 和代码文件导入
- [ ] 实现文档切分
- [ ] 实现 Embedding 生成
- [ ] 实现向量检索
- [ ] 实现全文关键词检索
- [ ] 实现 RRF 融合
- [ ] 实现带来源回答
- [ ] 实现基础聊天页面
- [ ] 使用 Docker Compose 部署

### 阶段交付物

- 可运行的 Web 系统
- 至少一个示例研发项目知识库
- 支持来源引用的问答
- Docker Compose 一键启动
- 第一版 README

---

# 第二阶段：Agent 工作流

目标：将普通 RAG 升级为可以多步执行任务的 Agent。

### 开发任务

- [ ] 使用 LangGraph 定义 Agent State
- [ ] 实现问题分类节点
- [ ] 实现任务规划节点
- [ ] 接入文档检索工具
- [ ] 接入代码检索工具
- [ ] 接入文件读取工具
- [ ] 接入 Issue 检索工具
- [ ] 接入 Git 历史查询工具
- [ ] 实现证据充分性判断
- [ ] 实现查询改写和重新检索
- [ ] 实现最大循环次数限制
- [ ] 实现故障排查报告生成
- [ ] 实现 Agent 执行过程展示

### 阶段交付物

- 多工具 Agent
- 可视化执行步骤
- 故障排查报告
- Agent 失败重试与终止机制

---

# 第三阶段：人工审批与工程化

目标：完善系统安全性和工程能力。

### 开发任务

- [ ] 实现 Agent 状态持久化
- [ ] 实现任务暂停与恢复
- [ ] 实现写操作审批流程
- [ ] 实现文件 Diff 展示
- [ ] 实现日志记录
- [ ] 实现 Token 使用统计
- [ ] 实现接口异常处理
- [ ] 实现 Redis 缓存
- [ ] 实现增量索引
- [ ] 实现文件内容 Hash 去重
- [ ] 编写 Pytest 自动化测试
- [ ] 完善 Docker 部署配置

### 阶段交付物

- Human-in-the-loop 审批中心
- 增量索引
- 系统日志与统计
- 自动化测试报告

---

# 第四阶段：量化评估

目标：使用真实数据证明系统效果，而不是只展示页面。

### 开发任务

- [ ] 创建 50～100 条测试问题
- [ ] 为每个问题标注正确来源
- [ ] 为每个问题编写参考答案
- [ ] 标注预期调用工具
- [ ] 测试纯向量检索
- [ ] 测试关键词检索
- [ ] 测试混合检索
- [ ] 测试加入 Reranker 后的效果
- [ ] 计算 Recall@5
- [ ] 计算 MRR
- [ ] 计算 Context Precision
- [ ] 计算 Context Recall
- [ ] 计算 Faithfulness
- [ ] 计算 Tool Call Accuracy
- [ ] 分析失败案例

### 阶段交付物

- 自建测试集
- 检索效果对比报告
- Agent 工具调用评估报告
- 真实优化数据

---

# 第五阶段：MCP 与项目展示

目标：增强项目创新性和简历展示效果。

### 开发任务

- [ ] 将检索能力封装为 MCP Server
- [ ] 暴露 `search_documents`
- [ ] 暴露 `search_code`
- [ ] 暴露 `read_file`
- [ ] 暴露 `get_git_history`
- [ ] 暴露 `generate_troubleshooting_report`
- [ ] 编写完整项目 README
- [ ] 绘制系统架构图
- [ ] 绘制 Agent 工作流图
- [ ] 准备演示数据
- [ ] 录制 3～5 分钟演示视频
- [ ] 部署在线体验地址

### 阶段交付物

- MCP Server
- GitHub 仓库
- 在线演示地址
- 项目演示视频
- 完整技术文档

---

## 15. 建议开发周期

可以按照 6～8 周安排：

| 周次 | 主要任务 |
|---|---|
| 第 1 周 | 项目搭建、数据库、登录、项目管理 |
| 第 2 周 | 文档解析、代码切分、向量索引 |
| 第 3 周 | 关键词检索、RRF、Reranker、来源引用 |
| 第 4 周 | LangGraph Agent、多工具调用、重新检索 |
| 第 5 周 | Human-in-the-loop、任务状态、增量索引 |
| 第 6 周 | 评估测试集、指标统计、优化对比 |
| 第 7 周 | MCP Server、自动化测试、Docker 部署 |
| 第 8 周 | README、架构图、演示视频、简历整理 |

开发时不要追求一次性做完所有功能。每一阶段都应保持系统可运行、可演示。

---

## 16. 测试数据设计

建议使用自己已有的项目构建测试知识库：

- Spring Boot 项目
- Laravel 任务管理系统
- Python 小项目
- 项目 README
- 开发过程中记录的错误
- Git 提交历史
- 手动创建的 Issue 数据

示例测试问题：

```json
{
  "question": "Spring Boot 8080 端口被占用怎么处理？",
  "expected_sources": [
    "docs/springboot-errors.md"
  ],
  "reference_answer": "使用 netstat 查询占用端口的 PID，并结束对应进程或修改服务端口。",
  "expected_tools": [
    "search_documents",
    "read_file"
  ]
}
```

```json
{
  "question": "Laravel 项目使用了什么认证方式？",
  "expected_sources": [
    "README.md",
    "app/Http/Controllers/AuthController.php"
  ],
  "reference_answer": "项目使用 Laravel Sanctum 和 Bearer Token 认证。",
  "expected_tools": [
    "search_documents",
    "search_code"
  ]
}
```

---

## 17. 评估指标

### 17.1 检索指标

#### Recall@5

正确来源是否出现在前 5 条检索结果中。

#### MRR

正确来源在检索结果中的平均排名。

#### Context Precision

检索到的上下文中，有多少内容与问题相关。

#### Context Recall

回答问题所需的信息，有多少被检索出来。

### 17.2 生成指标

#### Faithfulness

回答是否完全基于检索证据，是否存在脱离上下文的内容。

#### Answer Relevance

回答是否直接回应用户问题。

### 17.3 Agent 指标

#### Tool Call Accuracy

Agent 是否调用了正确工具。

#### Tool Call Order Accuracy

Agent 是否按照合理顺序调用工具。

#### Agent Goal Accuracy

Agent 是否最终完成用户目标。

#### Task Completion Rate

Agent 完成任务的比例。

### 17.4 工程指标

- 平均响应时间
- 首 Token 响应时间
- 单次任务 Token 消耗
- 工具调用成功率
- 索引构建时间
- 增量索引耗时

---

## 18. 简历项目描述

### 基础版本

**DevSage——基于 Agentic RAG 的研发知识库与故障排查系统**

基于 FastAPI、LangGraph、PostgreSQL 和 pgvector 开发面向研发团队的智能知识库系统，支持项目文档、源代码、Git 提交记录及历史 Issue 的统一索引与检索。实现关键词与向量混合召回、RRF 结果融合、Reranker 重排、查询改写和带来源回答，并构建问题分类、代码检索、Issue 检索、证据判断及故障报告生成等多节点 Agent 工作流。针对文件修改等高风险操作引入人工确认机制，使用 Docker Compose 完成服务部署，并通过 Recall@K、MRR、Faithfulness 及 Tool Call Accuracy 对检索和 Agent 效果进行评估。

### 完成评估后的版本

在项目完成后，将真实评估数据补充到简历：

> 相比纯向量检索，混合检索将 Recall@5 从 **XX% 提升至 XX%**；在自建的 **80 条研发问题测试集**上，工具调用准确率达到 **XX%**，平均故障排查任务完成率达到 **XX%**。

注意：所有数据必须通过实际测试获得，不能提前虚构。

---

## 19. 面试重点

面试时可以围绕以下问题展开：

### 检索相关

- 为什么代码检索不能只使用向量数据库？
- 为什么报错名称、端口号和方法名更适合关键词检索？
- RRF 如何融合两种检索结果？
- Reranker 放在检索流程的哪个位置？
- Chunk 大小和重叠长度如何选择？
- Markdown 和代码为什么不能使用同一种切分方式？

### Agent 相关

- Agent 如何判断应该调用哪个工具？
- 如何判断当前证据是否充分？
- 如何避免 Agent 无限循环？
- Agent 失败后如何恢复？
- 为什么写操作必须经过人工确认？
- LangGraph State 中保存了哪些信息？

### 工程相关

- 文件修改后如何实现增量索引？
- 如何避免重复生成向量？
- 如何记录工具调用日志？
- 如何统计 Token 消耗？
- Redis 在系统中承担什么作用？
- Docker Compose 如何组织多个服务？

### 评估相关

- Recall@5 和 MRR 有什么区别？
- 如何构建 RAG 测试集？
- 如何验证混合检索确实优于纯向量检索？
- 如何评估 Agent 是否调用了正确工具？
- 如何分析失败案例？

---

## 20. 项目展示建议

演示视频可以按照以下流程录制：

1. 展示项目首页和技术架构。
2. 导入一个 Spring Boot 或 Laravel 项目。
3. 展示索引过程和文件统计。
4. 提问一个技术知识问题。
5. 展示关键词与向量混合检索结果。
6. 点击查看来源文件和代码行号。
7. 提问一个历史故障问题。
8. 展示 Agent 调用文档、代码、Issue 和 Git 工具。
9. 生成故障排查报告。
10. 演示知识库写入审批。
11. 展示评估面板和优化数据。
12. 展示 MCP 调用效果。

---

## 21. 最小可行版本范围

第一版不要同时开发全部功能。最小可行版本只需要完成：

- 一个用户系统
- 一个项目知识库
- Markdown、Java、PHP、Python 文件导入
- 向量检索
- 关键词检索
- RRF 融合
- 带文件路径和行号的回答
- 文档检索与代码检索两个 Agent 工具
- 简单的故障排查流程
- Docker Compose 部署

完成上述内容后，DevSage 已经具备写入简历的基本条件。

后续优先增加：

1. Reranker；
2. 证据判断；
3. Issue 与 Git 工具；
4. Human-in-the-loop；
5. 量化评估；
6. MCP Server。

---

## 22. 项目完成标准

当满足以下条件时，可以认为项目达到较好的简历展示水平：

- [ ] 支持至少 3 种编程语言的代码索引
- [ ] 支持文档、代码、Issue 和 Git 数据检索
- [ ] 实现关键词与向量混合检索
- [ ] 实现 RRF 和 Reranker
- [ ] 回答能够显示文件路径和代码行号
- [ ] Agent 至少拥有 5 个可用工具
- [ ] Agent 可以完成多步故障排查
- [ ] 写操作支持人工确认
- [ ] 支持任务暂停和恢复
- [ ] 建立至少 50 条评估数据
- [ ] 输出真实 Recall@5、MRR 和工具调用准确率
- [ ] 使用 Docker Compose 一键启动
- [ ] 拥有完整 README 和架构图
- [ ] 拥有 3～5 分钟项目演示视频
- [ ] GitHub 提交记录清晰、Commit 信息规范

---

## 23. 最终项目定位

不要将项目描述为：

> AI 知识库聊天机器人

建议统一使用：

> **DevSage——基于 Agentic RAG 的研发知识库与故障排查系统**

项目的四个核心竞争力是：

> **混合检索 + 带来源回答 + 多工具 Agent + 量化评估**

开发过程中应优先保证这四项真实可用，再增加界面美化和扩展功能。
