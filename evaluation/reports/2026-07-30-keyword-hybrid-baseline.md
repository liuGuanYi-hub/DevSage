# DevMind MVP 检索基线报告

## 测试时间

2026-07-30 01:03

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
| 关键词基线 | 0.7000 | 0.4750 | 0.4642 |
| Hash 向量 + RRF | 0.7000 | 0.4917 | 0.6000 |

## 解读

当前混合基线在这批脱敏问题上保持了 Case Recall@5，并提高了 MRR，但离生产可用仍有明显距离。下一步应替换 Hash Provider，接入真实 Embedding，并继续检查 Chunk 大小、中文分词、来源覆盖率和多来源问题的召回策略。

## 限制

- 样例数据规模较小，不能外推到真实知识库；
- 评估问题由项目规划阶段人工编写，可能存在分布偏差；
- 当前没有评估生成回答的 Faithfulness；
- 当前没有评估工具调用顺序和任务完成率；
- 未使用真实 Embedding、Reranker 或 PostgreSQL pgvector。
