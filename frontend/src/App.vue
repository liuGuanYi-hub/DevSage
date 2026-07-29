<script setup lang="ts">
import { onMounted, ref } from "vue";

import { indexSource, runAgent, type AgentResponse, type IndexResponse, type SearchHit } from "./api/client";

const query = ref("");
const results = ref<SearchHit[]>([]);
const answer = ref<AgentResponse | null>(null);
const indexInfo = ref<IndexResponse | null>(null);
const status = ref("等待连接后端");
const isLoading = ref(false);

async function refreshIndex() {
  status.value = "正在建立样例索引…";
  try {
    indexInfo.value = await indexSource();
    status.value = `已索引 ${indexInfo.value.document_count} 个文件和 ${indexInfo.value.chunk_count} 个 Chunk`;
  } catch (error) {
    status.value = `后端未连接：${error instanceof Error ? error.message : "未知错误"}`;
  }
}

async function search() {
  if (!query.value.trim()) return;
  isLoading.value = true;
  status.value = "正在检索证据…";
  try {
    const response = await runAgent(query.value);
    answer.value = response;
    results.value = response.evidence;
    status.value = response.evidence_sufficient
      ? `找到 ${response.evidence.length} 条直接证据`
      : "证据不足，未生成确定性结论";
  } catch (error) {
    status.value = `检索失败：${error instanceof Error ? error.message : "未知错误"}`;
  } finally {
    isLoading.value = false;
  }
}

onMounted(refreshIndex);
</script>

<template>
  <main class="page-shell">
    <section class="hero-card">
      <p class="eyebrow">DevSage / DevMind MVP</p>
      <h1>研发知识库与故障排查助手</h1>
      <p class="summary">
        当前页面已接入阶段 1 的索引和关键词查询 API，结果会保留文件路径、行号和匹配词。
      </p>
      <div class="toolbar">
        <button type="button" @click="refreshIndex">重新索引样例数据</button>
        <span>{{ status }}</span>
      </div>
      <form class="search-box" @submit.prevent="search">
        <input v-model="query" placeholder="例如：8080 端口被占用怎么排查？" />
        <button type="submit" :disabled="isLoading">{{ isLoading ? "检索中…" : "开始检索" }}</button>
      </form>
      <section v-if="answer" class="results">
        <article v-if="answer" class="answer-card">
          <div class="result-meta">
            <strong>证据约束回答</strong>
            <span>{{ answer.evidence_sufficient ? "证据充分" : "证据不足" }}</span>
          </div>
          <p>{{ answer.answer }}</p>
          <small v-if="answer.warning">{{ answer.warning }}</small>
          <small>工具：{{ answer.tool_calls.join("、") }}</small>
          <ol class="agent-steps">
            <li v-for="step in answer.steps" :key="`${step.name}-${step.status}`">
              {{ step.name }} · {{ step.status }} · {{ step.detail }}
            </li>
          </ol>
        </article>
        <article v-for="result in results" :key="result.citation" class="result-card">
          <div class="result-meta">
            <strong>{{ result.source_path }}</strong>
            <span>{{ result.citation }} · {{ result.score.toFixed(4) }}</span>
          </div>
          <p>{{ result.content }}</p>
          <small>匹配：{{ result.matched_terms.join("、") || "向量候选" }}</small>
        </article>
      </section>
      <p v-else class="empty-state">输入问题后查看带来源的检索证据。</p>
    </section>
  </main>
</template>

<style>
:root {
  color: #172033;
  background: #eef3f8;
  font-family: Inter, system-ui, sans-serif;
}

body {
  margin: 0;
}

.page-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.hero-card {
  width: min(720px, 100%);
  padding: 48px;
  border: 1px solid #d7e0ea;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 20px 60px rgba(42, 67, 101, 0.12);
}

.eyebrow {
  color: #4674a8;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1 {
  margin: 12px 0;
  font-size: clamp(2rem, 5vw, 3.6rem);
  line-height: 1.05;
}

.summary {
  color: #526176;
  font-size: 1.08rem;
  line-height: 1.7;
}

.toolbar,
.search-box,
.result-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.toolbar {
  margin: 28px 0 16px;
  color: #526176;
  font-size: 0.9rem;
}

button {
  border: 0;
  border-radius: 10px;
  padding: 10px 14px;
  color: #ffffff;
  background: #326aa5;
  cursor: pointer;
}

button:disabled {
  cursor: wait;
  opacity: 0.6;
}

input {
  flex: 1;
  min-width: 0;
  border: 1px solid #cbd6e2;
  border-radius: 10px;
  padding: 12px 14px;
  font: inherit;
}

.results {
  display: grid;
  gap: 12px;
  margin-top: 24px;
}

.result-card {
  padding: 16px;
  border: 1px solid #d7e0ea;
  border-radius: 14px;
  background: #f8fbfd;
}

.answer-card {
  padding: 18px;
  border: 1px solid #8bb5d8;
  border-radius: 14px;
  background: #eef7ff;
}

.result-meta {
  justify-content: space-between;
  flex-wrap: wrap;
  color: #416b98;
  font-size: 0.85rem;
}

.result-card p {
  white-space: pre-wrap;
  line-height: 1.6;
}

.agent-steps {
  margin: 14px 0 0;
  padding-left: 20px;
  color: #526176;
  font-size: 0.88rem;
  line-height: 1.7;
}

.empty-state {
  color: #6c7b8f;
  text-align: center;
}

li {
  margin: 12px 0;
  line-height: 1.5;
}
</style>
