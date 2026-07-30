# DevSage 离线 MVP 评估基线

> 本文件由 `evaluation/scripts/generate_offline_report.py` 生成；指标来自固定脱敏数据集和离线 Hash Embedding，不代表生产模型质量。

## 数据集

- 文件：`evaluation/datasets/devmind_mvp_questions.json`
- 问题数：`50`
- SHA-256：`373098066a7811288aa694ad91a90e95020aec0b88c4756139ecc1f6bb21a6ad`

## 核心指标

| 指标 | 当前值 |
|---|---:|
| Agent Source Recall@5 | `0.9800` |
| Agent 完整来源案例率 | `0.9600` |
| Expected Tool Coverage | `0.9333` |
| Fully Covered Case Rate | `0.8400` |
| Context Precision@5 | `0.3095` |
| Context Recall@5 | `1.0000` |
| Answer Relevance Proxy F1 | `0.1404` |
| Faithfulness Proxy Precision | `0.7611` |

## 检索策略

| 策略 | Case Recall@5 | Source Recall@5 | MRR |
|---|---:|---:|---:|
| keyword | `0.7200` | `0.5450` | `0.4347` |
| vector | `0.7800` | `0.6283` | `0.6807` |
| hybrid_raw_rrf | `0.7400` | `0.5717` | `0.6540` |
| hybrid_source_diverse | `0.8200` | `0.6783` | `0.6753` |

## 边界与失败样例

- Agent grounding failure count：`2`
- Context quality failure count：`0`

### Agent grounding failure samples

- `mvp-020`：缺失来源 `.env.example`
- `mvp-047`：缺失来源 `.env.example`

### Context quality failure samples

- 无

## 解释边界

- Embedding：offline Hash baseline。
- Faithfulness：lexical proxy, not human or LLM evaluation。
- 外部服务：not used。
