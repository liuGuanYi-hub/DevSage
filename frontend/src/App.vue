<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  indexSource,
  runAgent,
  type AgentResponse,
  type IndexResponse,
  type SearchHit,
} from "./api/client";

const query = ref("");
const results = ref<SearchHit[]>([]);
const answer = ref<AgentResponse | null>(null);
const indexInfo = ref<IndexResponse | null>(null);
const status = ref("等待连接后端");
const isLoading = ref(false);

function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    troubleshooting: "故障排查",
    code_location: "代码定位",
    knowledge: "知识问答",
    git_diff: "Git 变更分析",
    unknown: "待分类",
  };
  return labels[category] ?? category;
}

async function refreshIndex() {
  status.value = "正在建立样例索引…";
  try {
    indexInfo.value = await indexSource();
    status.value = `已索引 ${indexInfo.value.document_count} 个文件、${indexInfo.value.chunk_count} 个 Chunk`;
  } catch (error) {
    status.value = `后端未连接：${error instanceof Error ? error.message : "未知错误"}`;
  }
}

async function search() {
  if (!query.value.trim()) return;
  isLoading.value = true;
  status.value = "Agent 正在分类、检索并组织证据…";
  try {
    const response = await runAgent(query.value);
    answer.value = response;
    results.value = response.evidence;
    status.value = response.evidence_sufficient
      ? `找到 ${response.evidence.length} 条直接证据`
      : "证据不足，页面保留排查线索";
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
      <div class="brand-row">
        <p class="eyebrow">DevSage / DevMind MVP</p>
        <span class="phase-badge">Agentic RAG</span>
      </div>
      <h1>研发知识库与故障排查助手</h1>
      <p class="summary">
        输入一个研发问题，DevMind 会先判断问题类型，再调用受限工具检索样例代码、Git 历史与 Issue，最后返回带引用的答案和可执行的排查报告。
      </p>

      <div class="toolbar">
        <button type="button" @click="refreshIndex">重新索引样例数据</button>
        <span>{{ status }}</span>
        <span v-if="indexInfo" class="index-count">{{ indexInfo.document_count }} files / {{ indexInfo.chunk_count }} chunks</span>
      </div>

      <form class="search-box" @submit.prevent="search">
        <input
          v-model="query"
          placeholder="例如：8080 端口被占用，应该怎么排查？"
          aria-label="研发问题"
        />
        <button type="submit" :disabled="isLoading">
          {{ isLoading ? "检索中…" : "开始排查" }}
        </button>
      </form>

      <section v-if="answer" class="results" aria-live="polite">
        <article class="answer-card">
          <div class="result-meta">
            <strong>证据约束回答</strong>
            <span>{{ categoryLabel(answer.category) }} · {{ answer.status }}</span>
          </div>
          <p class="answer-text">{{ answer.answer }}</p>
          <small v-if="answer.warning" class="warning">{{ answer.warning }}</small>
          <small>工具链：{{ answer.tool_calls.join(" · ") || "未调用工具" }}</small>
          <ol class="agent-steps">
            <li v-for="step in answer.steps" :key="`${step.name}-${step.status}`">
              <strong>{{ step.name }}</strong> · {{ step.status }} · {{ step.detail }}
            </li>
          </ol>
        </article>

        <article v-if="answer.report" class="report-card">
          <div class="result-meta">
            <strong>结构化排查报告</strong>
            <span>{{ answer.report.findings.length }} 类来源</span>
          </div>
          <p>{{ answer.report.summary }}</p>
          <div v-for="finding in answer.report.findings" :key="finding.source_type" class="finding">
            <strong>{{ finding.source_type }}</strong>
            <ul>
              <li v-for="(snippet, index) in finding.snippets" :key="`${finding.source_type}-${index}`">
                {{ snippet }}
              </li>
            </ul>
          </div>
          <div class="next-steps">
            <strong>建议下一步</strong>
            <ol>
              <li v-for="step in answer.report.next_steps" :key="step">{{ step }}</li>
            </ol>
          </div>
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
      <p v-else class="empty-state">输入问题后查看带来源引用的检索证据。</p>
    </section>
  </main>
</template>

<style>
:root {
  color: #172033;
  background: #eef3f8;
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

body { margin: 0; }

.page-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  box-sizing: border-box;
}

.hero-card {
  width: min(860px, 100%);
  padding: clamp(24px, 5vw, 48px);
  border: 1px solid #d7e0ea;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 20px 60px rgba(42, 67, 101, 0.12);
}

.brand-row, .toolbar, .search-box, .result-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.brand-row { justify-content: space-between; }
.eyebrow { color: #4674a8; font-size: 0.85rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }
.phase-badge { color: #276749; background: #e8f7ee; border-radius: 999px; padding: 6px 10px; font-size: 0.78rem; font-weight: 700; }
h1 { margin: 12px 0; font-size: clamp(2rem, 5vw, 3.6rem); line-height: 1.05; }
.summary { color: #526176; font-size: 1.08rem; line-height: 1.7; }

.toolbar { margin: 28px 0 16px; color: #526176; font-size: 0.9rem; flex-wrap: wrap; }
.index-count { margin-left: auto; color: #7890aa; }
button { border: 0; border-radius: 10px; padding: 10px 14px; color: #ffffff; background: #326aa5; cursor: pointer; font: inherit; font-weight: 600; }
button:disabled { cursor: wait; opacity: 0.6; }
input { flex: 1; min-width: 0; border: 1px solid #cbd6e2; border-radius: 10px; padding: 12px 14px; font: inherit; }
.results { display: grid; gap: 12px; margin-top: 24px; }
.result-card, .answer-card, .report-card { padding: 18px; border-radius: 14px; }
.result-card { border: 1px solid #d7e0ea; background: #f8fbfd; }
.answer-card { border: 1px solid #8bb5d8; background: #eef7ff; }
.report-card { border: 1px solid #b9d8c5; background: #f3fbf5; }
.result-meta { justify-content: space-between; flex-wrap: wrap; color: #416b98; font-size: 0.85rem; }
.result-card p, .report-card p { white-space: pre-wrap; line-height: 1.6; }
.answer-text { white-space: pre-wrap; line-height: 1.7; font-size: 1.05rem; }
.warning { display: block; color: #9a6700; margin-bottom: 8px; }
.agent-steps { margin: 14px 0 0; padding-left: 20px; color: #526176; font-size: 0.88rem; line-height: 1.7; }
.finding { margin-top: 14px; padding-top: 10px; border-top: 1px solid #d6eadb; }
.finding ul, .next-steps ol { margin-bottom: 0; padding-left: 20px; line-height: 1.6; }
.next-steps { margin-top: 16px; }
.empty-state { color: #6c7b8f; text-align: center; }
li { margin: 8px 0; line-height: 1.5; }

@media (max-width: 640px) {
  .search-box { align-items: stretch; flex-direction: column; }
  .search-box button { width: 100%; }
  .index-count { margin-left: 0; width: 100%; }
}
</style>
