# 本地 Embedding 与 Hash 基线召回对比

- 评测问题：75 道
- Chunk：36 个
- Top-K：5
- 本地模型：`intfloat/multilingual-e5-large (ONNX qint8)`
- 本地向量维度：`1024`

| 策略 | case_recall_at_5 | source_recall_at_5 | mrr | expected_alias_recall_at_5 |
| --- | ---: | ---: | ---: | ---: |
| keyword | 0.8800 | 0.7200 | 0.7589 | 1.0000 |
| hash_vector | 0.8800 | 0.6833 | 0.7364 | 0.0000 |
| hash_hybrid_source_diverse | 0.9600 | 0.8800 | 0.8049 | 1.0000 |
| local_e5_vector | 0.8000 | 0.6078 | 0.7431 | 0.0000 |
| local_e5_hybrid_source_diverse | 0.9600 | 0.8489 | 0.7724 | 1.0000 |

说明：Hash 是离线确定性基线；local_* 使用真实本地 SentenceTransformer 模型。
本地模型返回 1024 维，与 PostgreSQL/pgvector 的 `vector(1024)` 兼容；索引写入使用 `passage:`，查询使用 `query:`。
