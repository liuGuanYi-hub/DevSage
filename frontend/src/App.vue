<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  approveCodeChange,
  approveKnowledgeNote,
  getHealth,
  getAuthToken,
  indexSource,
  login,
  listProjects,
  previewCodeChange,
  previewKnowledgeNote,
  runAgent,
  setAuthToken,
  type AgentResponse,
  type CodeChangePreview,
  type HealthResponse,
  type IndexResponse,
  type KnowledgeNotePreview,
  type Project,
  type SearchHit,
} from "./api/client";
import { renderMarkdown, type MarkdownBlock } from "./markdown";

const query = ref("");
const results = ref<SearchHit[]>([]);
const answer = ref<AgentResponse | null>(null);
const indexInfo = ref<IndexResponse | null>(null);
const projects = ref<Project[]>([]);
const selectedProjectId = ref("sample-data");
const selectedActorId = ref("local-demo");
const status = ref("等待连接后端");
const backendHealth = ref<"checking" | "online" | "offline">("checking");
const healthDetails = ref<HealthResponse | null>(null);
const isLoading = ref(false);
const noteTitle = ref("DevSage knowledge note");
const noteContent = ref("");
const noteTargetPath = ref("DevMind/answer.md");
const pendingPreview = ref<KnowledgeNotePreview | null>(null);
const writebackStatus = ref("");
const codeTargetPath = ref("repositories/springboot-demo/README.md");
const codeContent = ref("");
const pendingCodePreview = ref<CodeChangePreview | null>(null);
const codeWritebackStatus = ref("");
const authToken = ref(getAuthToken());
const loginUsername = ref("");
const loginPassword = ref("");
const loginStatus = ref("");
const showExecutionDetails = ref(false);

const requiresLogin = computed(() => Boolean(healthDetails.value?.auth_enabled && !authToken.value));

const currentProject = computed(() =>
  projects.value.find((project) => project.project_id === selectedProjectId.value),
);
const currentMember = computed(() =>
  currentProject.value?.members.find((member) => member.actor_id === selectedActorId.value),
);

const answerBlocks = computed<MarkdownBlock[]>(() =>
  answer.value ? renderMarkdown(answer.value.answer) : [],
);

const evidenceView = computed(() =>
  results.value.map((result) => ({
    ...result,
    kind: sourceKind(result.source_path),
    blocks: renderMarkdown(result.content),
  })),
);

function can(action: string): boolean {
  return currentMember.value?.actions.includes(action) ?? false;
}

function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    troubleshooting: "故障排查",
    code_location: "代码定位",
    knowledge: "知识问答",
    knowledge_qa: "知识问答",
    knowledge_write: "知识写回",
    project_summary: "项目总结",
    git_history: "Git 历史",
    git_diff: "Git 变更分析",
    issue_search: "Issue 检索",
    unknown: "待分类",
  };
  return labels[category] ?? category;
}

function sourceKind(sourcePath: string): string {
  if (sourcePath.startsWith("issues/") || sourcePath.startsWith("external-issues/")) return "Issue";
  if (sourcePath.startsWith("git/")) return "Git history";
  if (sourcePath.includes("/repositories/") || sourcePath.startsWith("repositories/")) return "Code";
  return "Document";
}

function buildKnowledgeNote(response: AgentResponse, title: string): string {
  const citations = response.citations.length
    ? response.citations.map((citation, index) => `${index + 1}. ${citation}`).join("\n")
    : "- No direct citation was returned.";
  const evidence = response.evidence.length
    ? response.evidence
        .slice(0, 5)
        .map((hit) => `### ${sourceKind(hit.source_path)} · ${hit.source_path}\n\n${hit.content.trim()}`)
        .join("\n\n")
    : "暂无证据摘要。";
  const warning = response.warning ?? "请结合来源位置进行最终判断。";
  return `# ${title}

## 结论

${response.answer.trim()}

## 证据来源

${citations}

## 证据摘要

${evidence}

## 复核提示

${warning}
`;
}

function toggleExecutionDetails(event: Event): void {
  showExecutionDetails.value = (event.target as HTMLDetailsElement).open;
}

async function refreshIndex() {
  status.value = "正在建立当前项目索引…";
  try {
    indexInfo.value = await indexSource(
      "sample-data",
      selectedProjectId.value || undefined,
      selectedActorId.value || undefined,
    );
    backendHealth.value = "online";
    status.value = `已索引 ${indexInfo.value.document_count} 个文件、${indexInfo.value.chunk_count} 个 Chunk`;
  } catch (error) {
    backendHealth.value = "offline";
    status.value = `后端未连接：${error instanceof Error ? error.message : "未知错误"}`;
  }
}

async function search() {
  if (!query.value.trim()) return;
  isLoading.value = true;
  status.value = "Agent 正在分类、检索并组织证据…";
  try {
    const response = await runAgent(
      query.value,
      "sample-data",
      5,
      selectedProjectId.value || undefined,
      selectedActorId.value || undefined,
    );
    backendHealth.value = "online";
    answer.value = response;
    results.value = response.evidence;
    noteTitle.value = query.value.trim().slice(0, 80) || "DevSage knowledge note";
    noteContent.value = buildKnowledgeNote(response, noteTitle.value);
    pendingPreview.value = null;
    pendingCodePreview.value = null;
    showExecutionDetails.value = false;
    status.value = response.evidence_sufficient
      ? `找到 ${response.evidence.length} 条直接证据`
      : "证据不足，页面保留排查线索";
  } catch (error) {
    backendHealth.value = "offline";
    status.value = `检索失败：${error instanceof Error ? error.message : "未知错误"}`;
  } finally {
    isLoading.value = false;
  }
}

async function createNotePreview() {
  if (!answer.value || !noteContent.value.trim() || !can("writeback_preview")) return;
  writebackStatus.value = "Generating a pending preview...";
  try {
    pendingPreview.value = await previewKnowledgeNote(
      noteTitle.value.trim() || "DevSage knowledge note",
      noteContent.value.trim(),
      noteTargetPath.value.trim(),
      answer.value.citations,
      selectedProjectId.value || undefined,
      selectedActorId.value || undefined,
    );
    writebackStatus.value = "Preview created. Review the diff before approval.";
  } catch (error) {
    writebackStatus.value = `Preview failed: ${error instanceof Error ? error.message : "unknown error"}`;
  }
}

async function approveNote() {
  if (!pendingPreview.value) return;
  writebackStatus.value = "Approving note...";
  try {
    pendingPreview.value = await approveKnowledgeNote(
      pendingPreview.value.preview_id,
      selectedActorId.value || undefined,
    );
    writebackStatus.value = "Approved and written to the staging directory.";
  } catch (error) {
    writebackStatus.value = `Approval failed: ${error instanceof Error ? error.message : "unknown error"}`;
  }
}

async function createCodePreview() {
  if (!codeContent.value.trim() || !can("code_write_preview")) return;
  codeWritebackStatus.value = "Generating a code change preview...";
  try {
    pendingCodePreview.value = await previewCodeChange(
      codeTargetPath.value.trim(),
      codeContent.value,
      answer.value?.citations ?? [],
      "sample-data",
      selectedProjectId.value || undefined,
      selectedActorId.value || undefined,
    );
    codeWritebackStatus.value = "Code preview created. Review the Diff before approval.";
  } catch (error) {
    codeWritebackStatus.value = `Code preview failed: ${error instanceof Error ? error.message : "unknown error"}`;
  }
}

async function approveCode() {
  if (!pendingCodePreview.value) return;
  codeWritebackStatus.value = "Approving code change...";
  try {
    pendingCodePreview.value = await approveCodeChange(
      pendingCodePreview.value.preview_id,
      selectedActorId.value || undefined,
    );
    codeWritebackStatus.value = "Code change approved and written.";
  } catch (error) {
    codeWritebackStatus.value = `Code approval failed: ${error instanceof Error ? error.message : "unknown error"}`;
  }
}

async function loadProjects() {
  try {
    const response = await listProjects();
    backendHealth.value = "online";
    projects.value = response.items;
    if (!projects.value.some((project) => project.project_id === selectedProjectId.value)) {
      selectedProjectId.value = projects.value[0]?.project_id ?? "sample-data";
    }
    const project = projects.value.find((item) => item.project_id === selectedProjectId.value);
    if (project && !project.members.some((member) => member.actor_id === selectedActorId.value)) {
      selectedActorId.value = project.members[0]?.actor_id ?? "local-demo";
    }
  } catch (error) {
    backendHealth.value = "offline";
    status.value = `项目列表未连接：${error instanceof Error ? error.message : "未知错误"}`;
  }
}

function resetScopeState() {
  answer.value = null;
  results.value = [];
  indexInfo.value = null;
  pendingPreview.value = null;
  pendingCodePreview.value = null;
  writebackStatus.value = "";
  codeWritebackStatus.value = "";
}

async function handleProjectChange() {
  const project = projects.value.find((item) => item.project_id === selectedProjectId.value);
  if (project && !project.members.some((member) => member.actor_id === selectedActorId.value)) {
    selectedActorId.value = project.members[0]?.actor_id ?? "local-demo";
  }
  resetScopeState();
  status.value = "正在切换项目并清理旧证据…";
  await refreshIndex();
}

async function handleActorChange() {
  resetScopeState();
  status.value = "正在切换本地角色并重新检查能力…";
  await refreshIndex();
}

async function checkBackendHealth() {
  try {
    const response = await getHealth();
    healthDetails.value = response;
    backendHealth.value = response.status === "ok" ? "online" : "offline";
  } catch {
    healthDetails.value = null;
    backendHealth.value = "offline";
  }
}

async function submitLogin() {
  loginStatus.value = "正在登录…";
  try {
    const response = await login(loginUsername.value.trim(), loginPassword.value);
    setAuthToken(response.access_token);
    authToken.value = response.access_token;
    selectedActorId.value = response.actor_id;
    loginPassword.value = "";
    loginStatus.value = `已登录 ${response.username}`;
    await loadProjects();
    await refreshIndex();
  } catch (error) {
    loginStatus.value = `登录失败：${error instanceof Error ? error.message : "未知错误"}`;
  }
}

onMounted(async () => {
  await checkBackendHealth();
  if (requiresLogin.value) {
    status.value = "后端已启用正式认证，请先登录";
    return;
  }
  await loadProjects();
  await refreshIndex();
});
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

      <form v-if="requiresLogin" class="login-card" @submit.prevent="submitLogin">
        <strong>Formal authentication</strong>
        <p>当前后端已开启 Bearer Token 认证，登录后才能访问项目和检索能力。</p>
        <label class="field-label">
          Username
          <input v-model="loginUsername" autocomplete="username" aria-label="Username" required />
        </label>
        <label class="field-label">
          Password
          <input v-model="loginPassword" type="password" autocomplete="current-password" aria-label="Password" required />
        </label>
        <button type="submit">Login</button>
        <small v-if="loginStatus" class="writeback-status">{{ loginStatus }}</small>
      </form>

      <div v-if="!requiresLogin" class="toolbar">
        <label class="project-picker">
          项目
          <select v-model="selectedProjectId" @change="handleProjectChange" aria-label="选择项目">
            <option v-for="project in projects" :key="project.project_id" :value="project.project_id">
              {{ project.name }}
            </option>
          </select>
        </label>
        <label v-if="currentProject?.members.length" class="actor-picker">
          角色
          <select v-model="selectedActorId" @change="handleActorChange" aria-label="选择本地角色" :disabled="Boolean(healthDetails?.auth_enabled)">
            <option v-for="member in currentProject.members" :key="member.actor_id" :value="member.actor_id">
              {{ member.actor_id }} · {{ member.role }}
            </option>
          </select>
        </label>
        <span v-if="currentMember" class="capability-badge">
          {{ currentMember.role }}：{{ currentMember.actions.length }} 项能力
        </span>
        <button type="button" @click="refreshIndex" :disabled="!can('manage_project')">重新索引当前项目</button>
        <span class="health-badge" :class="`health-${backendHealth}`" aria-live="polite">
          后端：{{ backendHealth === "checking" ? "检查中" : backendHealth === "online" ? "在线" : "离线" }}
        </span>
        <span v-if="healthDetails" class="health-details">
          {{ healthDetails.storage ?? "memory" }} · Embedding {{ healthDetails.embedding_provider ?? "unknown" }} · Issue {{ healthDetails.external_issue_configured ? "已配置" : "未配置" }}
        </span>
        <span>{{ status }}</span>
        <span v-if="indexInfo" class="index-count">{{ indexInfo.document_count }} files / {{ indexInfo.chunk_count }} chunks</span>
      </div>

      <form v-if="!requiresLogin" class="search-box" @submit.prevent="search">
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
            <span>{{ categoryLabel(answer.category) }} · {{ answer.status }} · 项目 {{ answer.project_id ?? "兼容 source_root" }}</span>
          </div>
          <div class="markdown-content answer-markdown">
            <template v-for="(block, index) in answerBlocks" :key="`answer-block-${index}`">
              <h3 v-if="block.type === 'heading'" v-html="block.html"></h3>
              <p v-else-if="block.type === 'paragraph'" v-html="block.html"></p>
              <blockquote v-else-if="block.type === 'quote'" v-html="block.html"></blockquote>
              <component v-else-if="block.type === 'list'" :is="block.ordered ? 'ol' : 'ul'">
                <li v-for="(item, itemIndex) in block.items" :key="`answer-item-${index}-${itemIndex}`" v-html="item"></li>
              </component>
              <pre v-else-if="block.type === 'code'"><code>{{ block.code }}</code></pre>
            </template>
          </div>
          <small v-if="answer.warning" class="warning">{{ answer.warning }}</small>
          <details class="execution-details" :open="showExecutionDetails" @toggle="toggleExecutionDetails">
            <summary>执行详情 · {{ answer.tool_calls.length }} 个工具 · {{ answer.steps.length }} 个步骤</summary>
            <div class="tool-tags">
              <span v-for="tool in answer.tool_calls" :key="tool" class="tool-tag">{{ tool }}</span>
            </div>
            <small>工具重试：{{ answer.tool_retry_count }} 次 · Token 估算：{{ answer.usage.total_token_estimate }} · {{ answer.usage.runtime_ms }}ms</small>
            <ol class="agent-steps">
              <li v-for="step in answer.steps" :key="`${step.name}-${step.status}`">
                <strong>{{ step.name }}</strong> · {{ step.status }} · {{ step.detail }}
              </li>
            </ol>
          </details>
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

        <article class="writeback-card">
          <div class="result-meta">
            <strong>Knowledge note preview and approval</strong>
            <span v-if="pendingPreview">{{ pendingPreview.status }}</span>
          </div>
          <p class="writeback-hint">已自动整理为“结论 → 来源 → 证据摘要 → 复核提示”，你可以在审批前继续编辑。</p>
          <label class="field-label">
            Title
            <input v-model="noteTitle" aria-label="Knowledge note title" />
          </label>
          <label class="field-label">
            Target path
            <input v-model="noteTargetPath" aria-label="Knowledge note target path" />
          </label>
          <label class="field-label">
            Content
            <textarea v-model="noteContent" rows="8" aria-label="Knowledge note content"></textarea>
          </label>
          <div class="writeback-actions">
            <button type="button" @click="createNotePreview" :disabled="!noteContent.trim() || !can('writeback_preview')">
              Generate preview
            </button>
            <button
              v-if="pendingPreview && pendingPreview.status === 'pending'"
              type="button"
              @click="approveNote"
              :disabled="!can('writeback_approve')"
            >
              Approve and write
            </button>
          </div>
          <small v-if="writebackStatus" class="writeback-status">{{ writebackStatus }}</small>
          <div v-if="pendingPreview" class="diff-summary">
            <small>
              {{ pendingPreview.diff.operation }} · +{{ pendingPreview.diff.additions }} / -{{ pendingPreview.diff.deletions }} · {{ pendingPreview.target_path }}
            </small>
            <pre>{{ pendingPreview.diff.unified_diff.join("\n") }}</pre>
          </div>
        </article>

        <article class="code-writeback-card">
          <div class="result-meta">
            <strong>Code change preview and approval</strong>
            <span v-if="pendingCodePreview">{{ pendingCodePreview.status }}</span>
          </div>
          <p class="approval-hint">
            只允许修改当前项目内已有文件；预览不会写盘，批准前会再次校验文件 Hash。
          </p>
          <label class="field-label">
            Target file
            <input v-model="codeTargetPath" aria-label="Code change target file" />
          </label>
          <label class="field-label">
            Complete proposed file content
            <textarea v-model="codeContent" rows="10" aria-label="Proposed code content"></textarea>
          </label>
          <div class="writeback-actions">
            <button type="button" @click="createCodePreview" :disabled="!codeContent.trim() || !can('code_write_preview')">
              Generate code preview
            </button>
            <button
              v-if="pendingCodePreview && pendingCodePreview.status === 'pending'"
              type="button"
              @click="approveCode"
              :disabled="!can('code_write_approve')"
            >
              Approve code change
            </button>
          </div>
          <small v-if="codeWritebackStatus" class="writeback-status">{{ codeWritebackStatus }}</small>
          <div v-if="pendingCodePreview" class="diff-summary">
            <small>
              {{ pendingCodePreview.diff.operation }} · +{{ pendingCodePreview.diff.additions }} / -{{ pendingCodePreview.diff.deletions }} · {{ pendingCodePreview.target_path }}
            </small>
            <pre>{{ pendingCodePreview.diff.unified_diff.join("\n") }}</pre>
          </div>
        </article>

        <section class="evidence-section" aria-labelledby="evidence-heading">
          <div class="section-heading">
            <div>
              <span class="eyebrow">Grounding</span>
              <h2 id="evidence-heading">证据来源</h2>
            </div>
            <span>{{ evidenceView.length }} 条直接证据</span>
          </div>
          <div class="evidence-grid">
            <article v-for="evidence in evidenceView" :key="evidence.citation" class="evidence-card">
              <div class="evidence-card-head">
                <span class="source-kind">{{ evidence.kind }}</span>
                <span class="evidence-score">{{ evidence.score.toFixed(3) }}</span>
              </div>
              <strong class="evidence-path">{{ evidence.source_path }}</strong>
              <small class="evidence-citation">{{ evidence.citation }}</small>
              <div class="markdown-content evidence-markdown">
                <template v-for="(block, index) in evidence.blocks" :key="`evidence-block-${index}`">
                  <h4 v-if="block.type === 'heading'" v-html="block.html"></h4>
                  <p v-else-if="block.type === 'paragraph'" v-html="block.html"></p>
                  <blockquote v-else-if="block.type === 'quote'" v-html="block.html"></blockquote>
                  <component v-else-if="block.type === 'list'" :is="block.ordered ? 'ol' : 'ul'">
                    <li v-for="(item, itemIndex) in block.items" :key="`evidence-item-${index}-${itemIndex}`" v-html="item"></li>
                  </component>
                  <pre v-else-if="block.type === 'code'"><code>{{ block.code }}</code></pre>
                </template>
              </div>
              <small class="matched-terms">匹配：{{ evidence.matched_terms.join("、") || "向量候选" }}</small>
            </article>
          </div>
        </section>
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
  width: min(1040px, 100%);
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
.login-card { margin: 24px 0; padding: 18px; border: 1px solid #c8d8ec; border-radius: 16px; background: #f5f9ff; }
.login-card p { color: #526176; line-height: 1.5; }

.toolbar { margin: 28px 0 16px; color: #526176; font-size: 0.9rem; flex-wrap: wrap; }
.project-picker, .actor-picker { display: flex; align-items: center; gap: 8px; font-weight: 600; }
select { border: 1px solid #cbd6e2; border-radius: 10px; padding: 10px 12px; color: #26384f; background: #ffffff; font: inherit; }
.index-count { margin-left: auto; color: #7890aa; }
.capability-badge { border-radius: 999px; padding: 5px 9px; color: #5b4b82; background: #f0ebff; font-weight: 700; }
.health-badge { border-radius: 999px; padding: 5px 9px; font-weight: 700; }
.health-checking { color: #765b00; background: #fff4c2; }
.health-online { color: #276749; background: #e8f7ee; }
.health-offline { color: #9b2c2c; background: #fff0f0; }
.health-details { color: #7890aa; font-size: 0.82rem; }
button { border: 0; border-radius: 10px; padding: 10px 14px; color: #ffffff; background: #326aa5; cursor: pointer; font: inherit; font-weight: 600; }
button:disabled { cursor: wait; opacity: 0.6; }
input { flex: 1; min-width: 0; border: 1px solid #cbd6e2; border-radius: 10px; padding: 12px 14px; font: inherit; }
.results { display: grid; gap: 12px; margin-top: 24px; }
.result-card, .answer-card, .report-card { padding: 18px; border-radius: 14px; }
.result-card { border: 1px solid #d7e0ea; background: #f8fbfd; }
.answer-card { border: 1px solid #8bb5d8; background: #eef7ff; }
.report-card { border: 1px solid #b9d8c5; background: #f3fbf5; }
.writeback-card { border: 1px solid #d6c38e; background: #fffaf0; }
.code-writeback-card { border: 1px solid #c5b6dd; background: #faf7ff; }
.result-meta { justify-content: space-between; flex-wrap: wrap; color: #416b98; font-size: 0.85rem; }
.result-card p, .report-card p { white-space: pre-wrap; line-height: 1.6; }
.markdown-content { color: #24354d; line-height: 1.75; }
.markdown-content p { margin: 10px 0; }
.markdown-content h3, .markdown-content h4 { margin: 16px 0 8px; color: #1d3555; }
.markdown-content h3:first-child, .markdown-content h4:first-child { margin-top: 0; }
.markdown-content ul, .markdown-content ol { margin: 10px 0; padding-left: 24px; }
.markdown-content li { margin: 5px 0; }
.markdown-content blockquote { margin: 12px 0; padding: 8px 14px; border-left: 3px solid #76a4cc; color: #526176; background: rgba(255,255,255,0.55); }
.markdown-content code { padding: 2px 5px; border-radius: 5px; color: #6e3c12; background: #fff0d5; font: 0.9em/1.4 "SFMono-Regular", Consolas, monospace; }
.markdown-content pre { margin: 14px 0; overflow-x: auto; padding: 14px 16px; border-radius: 10px; background: #172033; color: #edf4ff; white-space: pre; font: 0.86rem/1.6 "SFMono-Regular", Consolas, monospace; }
.markdown-content pre code { padding: 0; color: inherit; background: transparent; }
.markdown-content a { color: #1f65a6; }
.answer-markdown { font-size: 1.05rem; }
.warning { display: block; color: #9a6700; margin-bottom: 8px; }
.execution-details { margin-top: 16px; border-top: 1px solid #c8deef; padding-top: 12px; color: #526176; font-size: 0.88rem; }
.execution-details summary { cursor: pointer; color: #416b98; font-weight: 700; }
.tool-tags { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 8px; }
.tool-tag, .source-kind { display: inline-flex; width: fit-content; border-radius: 999px; padding: 4px 8px; color: #315e8c; background: #dcecf9; font-size: 0.78rem; font-weight: 700; }
.agent-steps { margin: 14px 0 0; padding-left: 20px; color: #526176; font-size: 0.88rem; line-height: 1.7; }
.finding { margin-top: 14px; padding-top: 10px; border-top: 1px solid #d6eadb; }
.finding ul, .next-steps ol { margin-bottom: 0; padding-left: 20px; line-height: 1.6; }
.next-steps { margin-top: 16px; }
.approval-hint { color: #665b7d; line-height: 1.5; }
.writeback-hint { margin: 10px 0; color: #76652b; font-size: 0.88rem; line-height: 1.5; }
.field-label { display: grid; gap: 6px; margin-top: 12px; color: #526176; font-size: 0.88rem; font-weight: 600; }
.field-label textarea { resize: vertical; border: 1px solid #cbd6e2; border-radius: 10px; padding: 12px 14px; font: inherit; line-height: 1.5; }
.writeback-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.writeback-actions button:last-child { background: #8a6421; }
.writeback-status { display: block; margin-top: 10px; color: #6a541d; }
.diff-summary { margin-top: 14px; }
.diff-summary pre { max-height: 240px; overflow: auto; padding: 12px; border-radius: 10px; background: #29261f; color: #f8edc7; white-space: pre-wrap; font: 0.82rem/1.5 "SFMono-Regular", Consolas, monospace; }
.empty-state { color: #6c7b8f; text-align: center; }
.evidence-section { margin-top: 8px; }
.section-heading { display: flex; align-items: end; justify-content: space-between; gap: 12px; margin: 18px 0 10px; color: #6c7b8f; }
.section-heading h2 { margin: 3px 0 0; color: #1d3555; font-size: 1.35rem; }
.section-heading .eyebrow { margin: 0; font-size: 0.72rem; }
.evidence-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.evidence-card { min-width: 0; padding: 16px; border: 1px solid #d7e0ea; border-radius: 14px; background: #f8fbfd; }
.evidence-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.evidence-score { color: #6b7f95; font: 0.8rem "SFMono-Regular", Consolas, monospace; }
.evidence-path { display: block; margin-top: 12px; color: #294a70; overflow-wrap: anywhere; }
.evidence-citation { display: block; margin-top: 4px; color: #7890aa; }
.evidence-markdown { margin-top: 10px; font-size: 0.92rem; }
.evidence-markdown pre { max-height: 220px; }
.matched-terms { display: block; margin-top: 12px; color: #7890aa; }
li { margin: 8px 0; line-height: 1.5; }

@media (max-width: 640px) {
  .search-box { align-items: stretch; flex-direction: column; }
  .search-box button { width: 100%; }
  .index-count { margin-left: 0; width: 100%; }
  .evidence-grid { grid-template-columns: 1fr; }
  .section-heading { align-items: start; flex-direction: column; }
}
</style>
