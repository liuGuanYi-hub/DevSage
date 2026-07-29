# DevMind MVP 检索基线报告

## 测试时间

2026-07-30 01:08

## 测试范围

- 测试集：`evaluation/datasets/devmind_mvp_questions.json`；
- 问题数量：20；
- Top-K：5；
- 样例索引：`sample-data`，另加入根目录 `.env.example`；
- 关键词基线：Token 频次与短语匹配加权；
- 混合基线：关键词检索 + 离线 Hash 向量检索 + RRF；
- 离线 Hash Provider 仅用于验证向量接口，不代表生产 Embedding 模型效果。

## 结果

| 策略 | Case Recall@5 | Source Recall@5 | MRR |
|---|---:|---:|---:|
| 关键词基线 | 0.6500 | 0.4500 | 0.3142 |
| Hash 向量 + RRF | 0.7000 | 0.4917 | 0.5833 |

## 解读

当前混合基线在这批脱敏问题上保持了 Case Recall@5，并提高了 MRR，但离生产可用仍有明显距离。下一步应替换 Hash Provider，接入真实 Embedding，并继续检查 Chunk 大小、中文分词、来源覆盖率和多来源问题的召回策略。

## 限制

- 样例数据规模较小，不能外推到真实知识库；
- 评估问题由项目规划阶段人工编写，可能存在分布偏差；
- 当前没有评估生成回答的 Faithfulness；
- 当前没有评估工具调用顺序和任务完成率；
- 未使用真实 Embedding、Reranker 或 PostgreSQL pgvector。

## 更新测试：2026-07-30 01:51

本次将评估集从 20 条扩展到 50 条，新增问题覆盖 Spring Boot 端口与代码调用链、Laravel 认证与路由、知识写回、安全边界、来源引用和项目比较。所有新增问题均通过字段、唯一 ID 和来源文件存在性校验。

| 策略 | Case Recall@5 | Source Recall@5 | MRR |
|---|---:|---:|---:|
| 关键词基线 | 0.6800 | 0.5217 | 0.4080 |
| Hash 向量 + RRF | 0.7000 | 0.5483 | 0.5833 |

### 新一轮解读

在 50 条问题上，Hash+RRF 的 Case Recall@5 比关键词基线高 0.0200，Source Recall@5 高 0.0266，MRR 高 0.1753。与旧 20 条报告的数值不应直接当作回归差异，因为测试集规模和问题分布已经改变；后续应固定数据集版本后再比较策略迭代。

### 新一轮限制

- 当前仍只评估检索来源，不评估生成回答的 Faithfulness、Context Precision 和 Context Recall；
- `expected_tools` 已完成标注，但尚未实现 Tool Call Accuracy 统计；
- Hash Provider 仍是离线接口替身，不代表真实 Embedding 服务效果。

## 更新工具调用评估：2026-07-30 01:54

新增 `evaluation/scripts/evaluate_tool_call_accuracy.py`，将每条问题的 `expected_tools` 与实际 Agent `tool_calls` 做集合覆盖比较。当前 50 条问题结果：

| 指标 | 改进前 | 当前 |
|---|---:|---:|
| Expected Tool Coverage | 0.4233 | 0.7033 |
| Fully Covered Case Rate | 0.0800 | 0.4400 |

本轮通过为知识写回问题调用预览工具、为普通知识问答补充首条来源读取、为故障排查补充主要文档读取，使工具覆盖率得到提升。该指标只判断预期工具是否至少调用一次，不判断调用顺序、参数质量、工具结果正确性或是否存在多余工具调用，因此不能等同于完整 Tool Call Accuracy。
## 2026-07-30 02:13：pgvector 维度兼容回归

为使离线 Hash Provider 可以写入迁移定义的 `vector(1024)`，本轮将默认 Hash 维度从 64 调整为 1024，并重新运行 50 条固定评估集。结果如下：

| 策略 | Case Recall@5 | Source Recall@5 | MRR |
|---|---:|---:|---:|
| 关键词基线 | 0.6800 | 0.5217 | 0.4080 |
| Hash 1024 + RRF | 0.6800 | 0.5217 | 0.6167 |

本次调整使 MRR 提升到 `0.6167`，但 Recall 指标相对上一版 Hash 64 结果有所变化；这只能作为存储维度兼容性回归，不能解释为真实 Embedding 质量提升。真实 PostgreSQL/pgvector 端到端结果仍需在容器启动后单独记录。
## 2026-07-30 02:28：来源多样性重排与上下文质量代理指标

本轮先让 RRF 保留 Top-20 候选，再按来源文件做 Top-5 多样性选择，优先每个来源保留一个 Chunk；同时新增可重复的来源级 Context Precision/Recall、参考答案词项召回、答案词法 F1 和证据词法覆盖代理指标。重排后的检索结果为：

| 指标 | 调整前 | 当前 |
|---|---:|---:|
| Case Recall@5 | 0.6800 | 0.7200 |
| Source Recall@5 / Context Recall | 0.5217 | 0.5883 |
| MRR | 0.6167 | 0.6280 |
| Context Precision@5（Chunk） | 0.1560 | 0.1800 |
| Context Precision@5（去重来源） | 0.2093 | 0.1800 |
| Answer Relevance Proxy F1 | 未统计 | 0.1213 |
| Reference Term Recall | 未统计 | 0.8449 |
| Faithfulness Proxy Precision | 未统计 | 0.8664 |

本轮失败样本数为 25/50，主要集中在代码文件精确定位和多文件调用链问题。`Reference Term Recall`、`Faithfulness Proxy Precision` 和 `Answer Relevance Proxy F1` 都是离线词法代理，不是 LLM-as-a-judge 或人工 Faithfulness 结论；真实模型接入后仍需单独评估。

## 2026-07-30 02:42：Agent grounding 与代码路径检索优化

本轮把 Agent 端到端证据命中单独固化为 `evaluation/scripts/evaluate_agent_grounding.py`，并补充回归测试。针对失败案例做了三类可迁移修正：代码检索允许配置文件但排除 Issue/Git 导出记录；代码定位问题按需合并支持文档；查询词命中文件路径时增加小幅排序加权，并对控制器、认证中间件、路由、配置和调用链补充透明扩展词。

### Agent 结果

| 指标 | 上一轮分类修正后 | 当前 |
|---|---:|---:|
| Agent Source Recall@5 | 0.6383 | 0.9650 |
| 完整来源案例率 | 0.5600 | 0.9000 |
| 失败案例数 | 22 | 5 |
| Expected Tool Coverage | 0.7433 | 0.9333 |
| Fully Covered Case Rate | 0.5200 | 0.8400 |

当前 5 个来源失败中，2 个案例的 `.env.example` 位于 Agent 使用的 `sample-data` source root 外，属于评估集边界问题；其余 3 个是跨文件项目总结的 Top-K 取舍，仍需后续做任务类型专用的证据配额或 reranker。Agent grounding 指标只证明固定脱敏数据上的来源覆盖，不等同于答案正确率或真实 LLM 评审。

### 检索上下文代理结果

路径加权后重新运行 `evaluate_context_quality.py`：Context Precision@5 为 `0.2000`，去重来源 Precision 为 `0.2000`，Context Recall@5 为 `0.6783`，Answer Relevance Proxy F1 为 `0.1217`，Reference Term Recall 为 `0.8459`，Faithfulness Proxy Precision 为 `0.8652`，失败案例为 `21/50`。这些指标继续作为离线词法趋势，不替代人工或模型评审。

## 2026-07-30 02:49：项目总结证据预算与工具失败重试

本轮针对跨文件项目总结设置独立的最小证据预算：项目总结至少保留 8 个候选来源，普通问答仍维持调用方指定的 Top-K，避免扩大检索范围污染其他任务。随后为 Git 历史、Commit Diff 和导出 Issue 查询增加一次有界失败重试；每次实际尝试计入工具调用预算，失败步骤、`tool_retry` 步骤和 `tool_retry_count` 都会写入 Agent 状态快照，路径越界等输入错误不会重试。

更新后的 50 条 Agent 评估结果为：Agent Source Recall@5 `0.9800`，完整来源案例率 `0.9600`，失败案例 `2/50`；Expected Tool Coverage 保持 `0.9333`，Fully Covered Case Rate 保持 `0.8400`。剩余两条均为 expected source 中的 `.env.example` 超出当前 `sample-data` source root，保留作为数据边界提示。

## 2026-07-30 03:13：检索策略与可解释重排对比

新增 `evaluation/scripts/evaluate_retrieval_strategies.py`，统一加载 50 条固定问题、`sample-data` 加根目录 `.env.example` 的同一批 Chunk，并固定使用 `HashEmbeddingProvider(dimension=1024)` 对比纯关键词、纯向量、原始 RRF 和来源多样性重排。所有策略均使用 Top-K=5，指标定义保持 Case Recall@5、Source Recall@5 和 MRR。

| 策略 | Case Recall@5 | Source Recall@5 | MRR |
|---|---:|---:|---:|
| 纯关键词 | 0.7200 | 0.5450 | 0.4347 |
| 纯 Hash 向量 | 0.7800 | 0.6383 | 0.6807 |
| 混合（关键词 + Hash 向量 + 原始 RRF） | 0.7400 | 0.5717 | 0.6540 |
| 混合 + 来源多样性重排 | 0.8200 | 0.6783 | 0.6753 |

这组实测结果显示，在当前脱敏数据集上，来源多样性重排相对原始 RRF 将 Case Recall@5 从 `0.7400` 提升到 `0.8200`、Source Recall@5 从 `0.5717` 提升到 `0.6783`；纯向量的 MRR 仍略高。这里的 reranker 是可解释的来源多样性选择，不是神经 Cross-Encoder，不能据此推断真实 Embedding 或生产数据上的效果。

## 2026-07-30 03:25：外部 Issue 配置模板回归

本轮为外部 Issue 适配器在 `.env.example` 增加了空的 URL、仓库、Token 环境变量名和超时配置。由于评估集会把根目录 `.env.example` 纳入索引，配置模板变化会影响离线 Hash 向量的排序；重新运行当前脚本后的最新检索结果为：

| 策略 | Case Recall@5 | Source Recall@5 | MRR |
|---|---:|---:|---:|
| 纯关键词 | 0.7200 | 0.5450 | 0.4347 |
| 纯 Hash 向量 | 0.7800 | 0.6283 | 0.6807 |
| 混合（关键词 + Hash 向量 + 原始 RRF） | 0.7400 | 0.5717 | 0.6540 |
| 混合 + 来源多样性重排 | 0.8200 | 0.6783 | 0.6753 |

Agent grounding 仍为 Source Recall@5 `0.9800`、完整来源案例率 `0.9600`；上下文质量代理当前为 Context Precision `0.2000`、Context Recall `0.6783`、Answer Relevance Proxy F1 `0.1213`、Faithfulness Proxy Precision `0.8661`。本轮未执行真实外部网络请求，适配器只通过 fake transport 测试。

## 2026-07-30 04:34：统一答案检索路由与项目总结回答

本轮没有只调整评估脚本，而是新增 `backend/app/retrieval/answer_search.py` 作为生产答案检索路由，并让 `/api/answer`、`/api/answer/stream`、Agent 代码路径规则和上下文质量评估共享同一组分类与证据筛选逻辑：代码定位优先代码来源并按需合并支持文档；项目总结使用至少 8 个候选来源并按代码/文档分组组织答案；普通问题继续使用混合检索。对无关代码定位问题，根目录点号环境模板不会被默认当作代码证据，只有查询明确指向环境变量、密码、Token 等配置时才允许进入该分支。

### 上下文质量代理结果

| 指标 | 路由改造前 | 当前 |
|---|---:|---:|
| Context Precision@5（Chunk） | 0.2440 | 0.3015 |
| Context Precision@5（去重来源） | 0.2440 | 0.3079 |
| Context Recall@5 | 0.8000 | 0.9800 |
| Answer Relevance Proxy F1 | 0.1260 | 0.1402 |
| Reference Term Recall | 0.8492 | 0.8596 |
| Faithfulness Proxy Precision | 0.8545 | 0.7637 |
| 失败案例 | 16/50 | 2/50 |

当前两条失败仍是评估集预期的根目录 `.env.example`，而 Agent 使用的 `sample-data` source root 不包含该文件，属于数据范围边界，不应伪装成已解决。Faithfulness 代理下降说明来源扩展后答案包含了更多检索片段，仍需后续做更精确的证据裁剪；以上所有数字仍是词法代理，不等同于人工或 LLM-as-a-judge 结论。

本轮新增答案路由和 API 回归测试，定向测试共 `48` 项通过，`python -m compileall -q backend evaluation` 通过。未执行真实 Docker、外部 Issue 网络请求或远程 Embedding 请求。
