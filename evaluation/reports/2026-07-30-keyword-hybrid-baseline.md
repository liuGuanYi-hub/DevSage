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
