# DevSage 离线 MVP 评估基线

> 本文件由 `evaluation/scripts/generate_offline_report.py` 生成；指标来自固定脱敏数据集和离线 Hash Embedding，不代表生产模型质量。

## 数据集

- 文件：`evaluation/datasets/devmind_mvp_questions.json`
- 问题数：`75`
- SHA-256：`4ab682d0712389900dc17f851a3a351a4ace6b95b8a456f6b71f078add0e9916`

## 核心指标

| 指标 | 当前值 |
|---|---:|
| Agent Source Recall@5 | `0.9667` |
| Agent 完整来源案例率 | `0.9467` |
| Expected Tool Coverage | `0.9089` |
| Fully Covered Case Rate | `0.7600` |
| Context Precision@5 | `0.3703` |
| Context Recall@5 | `0.9533` |
| Answer Relevance Proxy F1 | `0.1628` |
| Faithfulness Proxy Precision | `0.5271` |

## 检索策略

| 策略 | Case Recall@5 | Source Recall@5 | MRR | Alias Recall@5 |
|---|---:|---:|---:|---:|
| keyword | `0.8800` | `0.7200` | `0.7589` | `1.0000` |
| vector | `0.8800` | `0.6833` | `0.7364` | `0.0000` |
| hybrid_raw_rrf | `0.8800` | `0.7078` | `0.7789` | `0.8750` |
| hybrid_source_diverse | `0.9600` | `0.8800` | `0.8049` | `1.0000` |

## 边界与失败样例

- Agent grounding failure count：`4`
- Context quality failure count：`52`

### Agent grounding failure samples

- `mvp-012`：缺失来源 `docs/springboot-errors.md`
- `mvp-018`：缺失来源 `repositories/springboot-demo/README.md`
- `mvp-020`：缺失来源 `.env.example`
- `mvp-047`：缺失来源 `.env.example`

### Context quality failure samples

- `mvp-002`：Context Recall=`1.0000`，Reference Term Recall=`0.0000`
- `mvp-004`：Context Recall=`1.0000`，Reference Term Recall=`0.4444`
- `mvp-007`：Context Recall=`1.0000`，Reference Term Recall=`0.3000`
- `mvp-008`：Context Recall=`1.0000`，Reference Term Recall=`0.0000`
- `mvp-009`：Context Recall=`1.0000`，Reference Term Recall=`0.1429`
- `mvp-010`：Context Recall=`1.0000`，Reference Term Recall=`0.1538`
- `mvp-011`：Context Recall=`1.0000`，Reference Term Recall=`0.0000`
- `mvp-012`：Context Recall=`1.0000`，Reference Term Recall=`0.2308`
- `mvp-014`：Context Recall=`1.0000`，Reference Term Recall=`0.1379`
- `mvp-016`：Context Recall=`1.0000`，Reference Term Recall=`0.4000`

## 解释边界

- Embedding：offline Hash baseline。
- Faithfulness：lexical proxy, not human or LLM evaluation。
- 外部服务：not used。
