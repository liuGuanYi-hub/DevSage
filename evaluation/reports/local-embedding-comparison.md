# 本地 Embedding 与 Hash 基线召回对比

- 评测问题：75 道
- Chunk：36 个
- Top-K：5
- 本地模型：`BAAI/bge-small-zh-v1.5`
- 本地向量维度：`512`

| 策略 | case_recall_at_5 | source_recall_at_5 | mrr | expected_alias_recall_at_5 |
| --- | ---: | ---: | ---: | ---: |
| keyword | 0.8800 | 0.7200 | 0.7589 | 1.0000 |
| hash_vector | 0.8800 | 0.6833 | 0.7364 | 0.0000 |
| hash_hybrid_source_diverse | 0.9600 | 0.8800 | 0.8049 | 1.0000 |
| local_bge_vector | 0.8400 | 0.7167 | 0.7544 | 0.0000 |
| local_bge_hybrid_source_diverse | 0.9600 | 0.8867 | 0.7960 | 1.0000 |

说明：Hash 是离线确定性基线；local_* 使用真实本地 SentenceTransformer 模型。
当前 PostgreSQL pgvector 表为 1024 维，本报告先在内存检索上比较本地模型；
若本地模型维度不是 1024，不会自动写入现有 PostgreSQL 索引。
