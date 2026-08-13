<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  approveIssueWrite,
  approveCodeChange,
  approveKnowledgeNote,
  batchAgentTasks,
  getHealth,
  getAgentTask,
  getAuthToken,
  getIndexStatus,
  indexSource,
  login,
  listAgentTasks,
  listProjects,
  previewCodeChange,
  previewIssueWrite,
  previewKnowledgeNote,
  resumeAgentTask,
  submitAnswerFeedback,
  isAgentStreamCancelled,
  streamAgent,
  setAuthToken,
  type AgentResponse,
  type AgentProgressEvent,
  type AgentTaskSummary,
  type AgentTaskBatchAction,
  type CodeChangePreview,
  type HealthResponse,
  type IndexResponse,
  type IndexStatusResponse,
  type IssueWritePreview,
  type KnowledgeNotePreview,
  type Project,
  type SearchHit,
} from "./api/client";
import { renderMarkdown, type MarkdownBlock } from "./markdown";

const query = ref("");
const results = ref<SearchHit[]>([]);
const answer = ref<AgentResponse | null>(null);
const indexInfo = ref<IndexResponse | IndexStatusResponse | null>(null);
const projects = ref<Project[]>([]);
const selectedProjectId = ref("sample-data");
const selectedActorId = ref("local-demo");
const status = ref("等待连接后端");
const backendHealth = ref<"checking" | "online" | "offline">("checking");
const healthDetails = ref<HealthResponse | null>(null);
const isLoading = ref(false);
const isIndexing = ref(false);
const requestError = ref("");
const retryAction = ref<"bootstrap" | "search" | "index" | null>(null);
const noteTitle = ref("DevSage knowledge note");
const noteContent = ref("");
const noteTargetPath = ref("DevMind/answer.md");
const pendingPreview = ref<KnowledgeNotePreview | null>(null);
const writebackStatus = ref("");
const codeTargetPath = ref("repositories/springboot-demo/README.md");
const codeContent = ref("");
const pendingCodePreview = ref<CodeChangePreview | null>(null);
const codeWritebackStatus = ref("");
const issueTitle = ref("");
const issueBody = ref("");
const issueLabels = ref("bug, troubleshooting");
const pendingIssuePreview = ref<IssueWritePreview | null>(null);
const issueWriteStatus = ref("");
const authToken = ref(getAuthToken());
const loginUsername = ref("");
const loginPassword = ref("");
const loginStatus = ref("");
const isLoggingIn = ref(false);
const authUsername = ref("");
const feedbackRating = ref<"helpful" | "needs_revision" | null>(null);
const feedbackComment = ref("");
const feedbackIncorrectCitations = ref<string[]>([]);
const feedbackCorrectionText = ref("");
const feedbackStatus = ref("");
const isSubmittingFeedback = ref(false);
const showExecutionDetails = ref(false);
const agentPhase = ref("");
const agentProgressSteps = ref<AgentProgressEvent[]>([]);
const taskRecords = ref<AgentTaskSummary[]>([]);
const selectedTask = ref<AgentResponse | null>(null);
const isLoadingTasks = ref(false);
const taskLoadError = ref("");
const taskActionId = ref("");
const taskStatusFilter = ref("all");
const taskSortBy = ref<"updated_at" | "runtime_ms">("updated_at");
const taskSortOrder = ref<"asc" | "desc">("desc");
const selectedTaskIds = ref<string[]>([]);
const isBatchingTasks = ref(false);
const taskBatchStatus = ref("");
const taskStatusOptions = [
  { value: "all", label: "全部状态" },
  { value: "completed", label: "已完成" },
  { value: "insufficient_evidence", label: "证据不足" },
  { value: "failed", label: "失败" },
  { value: "cancelled", label: "已取消" },
  { value: "tool_limit_reached", label: "工具上限" },
  { value: "step_limit_reached", label: "步骤上限" },
  { value: "task_timeout", label: "任务超时" },
];
const selectedResumableTaskIds = computed(() =>
  taskRecords.value
    .filter((task) => selectedTaskIds.value.includes(task.task_id) && task.resumable)
    .map((task) => task.task_id),
);
const allVisibleTasksSelected = computed(() =>
  taskRecords.value.length > 0 && taskRecords.value.every((task) => selectedTaskIds.value.includes(task.task_id)),
);
type WorkspaceViewId = "workspace" | "knowledge" | "retrieval" | "tasks" | "evaluation";
const activeView = ref<WorkspaceViewId>("workspace");
let agentAbortController: AbortController | null = null;

const workspaceViews: Array<{ id: WorkspaceViewId; label: string; icon: string; description: string }> = [
  { id: "workspace", label: "工作台", icon: "⌂", description: "问题、答案与证据" },
  { id: "knowledge", label: "知识库", icon: "▤", description: "项目、文件与索引" },
  { id: "retrieval", label: "检索实验室", icon: "⌕", description: "排序与 Chunk 检查" },
  { id: "tasks", label: "任务记录", icon: "◷", description: "运行、恢复与重试" },
  { id: "evaluation", label: "评测中心", icon: "◒", description: "质量、延迟与失败案例" },
];

interface ExampleQuery {
  label: string;
  query: string;
  projectId?: string;
}

interface ExampleGroup {
  label: string;
  icon: string;
  tone: string;
  examples: ExampleQuery[];
}

const exampleGroups: ExampleGroup[] = [
  {
    label: "故障排查",
    icon: "!",
    tone: "troubleshooting",
    examples: [{ label: "8080 端口占用怎么排查？", query: "8080 端口被占用，应该怎么排查？", projectId: "sample-data" }],
  },
  {
    label: "代码定位",
    icon: "</>",
    tone: "code",
    examples: [
      { label: "Spring Boot 用户接口在哪？", query: "示例 Spring Boot 项目的用户接口入口在哪个类？", projectId: "sample-data" },
      { label: "用户查询涉及哪些文件？", query: "示例 Spring Boot 项目包含哪些与用户查询相关的文件？", projectId: "sample-data" },
    ],
  },
  {
    label: "认证与权限",
    icon: "✓",
    tone: "auth",
    examples: [
      { label: "Laravel 任务接口为什么 401？", query: "Laravel 登录成功后访问任务列表为什么返回 401？", projectId: "sample-data" },
      { label: "本地 actor 和正式认证有什么区别？", query: "项目的本地 actor 权限和正式身份认证有什么区别？", projectId: "sample-data" },
    ],
  },
  {
    label: "Vault 知识库",
    icon: "⌂",
    tone: "vault",
    examples: [
      {
        label: "Vault 的目录分别负责什么？",
        query: "Obsidian 知识库的核心目录分别负责什么？",
        projectId: "obsidian-vault",
      },
      {
        label: "如何从 Inbox 进入 Research？",
        query: "Obsidian 知识库的研究资料应该如何从 Inbox 进入 Research？",
        projectId: "obsidian-vault",
      },
      {
        label: "哪些 Obsidian 插件值得先装？",
        query: "第一次使用 Obsidian，哪些插件最值得先安装？",
        projectId: "obsidian-vault",
      },
      {
        label: "如何记录一次 Agent 评估？",
        query: "如何使用 Agent Evaluation Template 记录一次完整评估？",
        projectId: "obsidian-vault",
      },
      {
        label: "如何搭建个人 AI 工作流？",
        query: "如何把 ChatGPT、Codex 和 Obsidian 组成个人 AI 工作流？",
        projectId: "obsidian-vault",
      },
      {
        label: "知识库如何刷新和审计？",
        query: "Obsidian 知识库每周如何刷新 Topic Index 和审计报告？",
        projectId: "obsidian-vault",
      },
    ],
  },
];

const requiresLogin = computed(() => Boolean(healthDetails.value?.auth_enabled && !authToken.value));

const currentProject = computed(() =>
  projects.value.find((project) => project.project_id === selectedProjectId.value),
);
const currentMember = computed(() =>
  currentProject.value?.members.find((member) => member.actor_id === selectedActorId.value),
);
const activeViewMeta = computed(() => workspaceViews.find((view) => view.id === activeView.value) ?? workspaceViews[0]);

const canIssueWrite = computed(() => can("issue_write_preview") || can("issue_write_approve"));
const canCodeWrite = computed(() => can("code_write_preview") || can("code_write_approve"));

const projectMismatch = computed(() => {
  const suggestedProjectId = inferProjectId(query.value);
  if (!suggestedProjectId || !currentProject.value || suggestedProjectId === currentProject.value.project_id) {
    return null;
  }
  const suggestedProject = projects.value.find((project) => project.project_id === suggestedProjectId);
  if (!suggestedProject) return null;
  return { suggestedProjectId, suggestedProject };
});

const answerBlocks = computed<MarkdownBlock[]>(() =>
  answer.value ? renderMarkdown(answer.value.answer) : [],
);

const selectedTaskBlocks = computed<MarkdownBlock[]>(() =>
  selectedTask.value ? renderMarkdown(selectedTask.value.answer) : [],
);

const keySteps = computed<string[]>(() => {
  if (!answer.value) return [];
  if (answer.value.key_steps.length) return answer.value.key_steps;
  return answer.value.report?.next_steps ?? [];
});

const indexSummary = computed(() => {
  const info = indexInfo.value;
  if (!info) return "";
  if ("indexed" in info && !info.indexed) return "索引：尚未建立";
  return `${info.document_count} files / ${info.chunk_count} chunks`;
});

function uniqueEvidence(hits: SearchHit[], limit = Number.MAX_SAFE_INTEGER): SearchHit[] {
  const seenSources = new Set<string>();
  return hits.filter((hit) => {
    if (seenSources.has(hit.source_path) || seenSources.size >= limit) return false;
    seenSources.add(hit.source_path);
    return true;
  });
}

function evidenceForResponse(response: AgentResponse): SearchHit[] {
  if (response.category !== "project_summary" || !response.citations.length) {
    return response.evidence;
  }
  const cited = response.evidence.filter((hit) => response.citations.includes(hit.citation));
  return cited.length ? cited : response.evidence;
}

const evidenceView = computed(() =>
  uniqueEvidence(results.value).map((result) => ({
    ...result,
    kind: sourceKind(result.source_path),
    blocks: renderMarkdown(result.content),
  })),
);

function can(action: string): boolean {
  return currentMember.value?.actions.includes(action) ?? false;
}

function canIndex(): boolean {
  return can("manage_project") || can("index");
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

function generationLabel(mode: string, model: string | null = null): string {
  if (mode === "ai") return `AI 生成 · ${model ?? "远程模型"}`;
  if (mode === "offline_fallback") return `AI 不可用 · 已回退离线答案`;
  if (mode === "guarded") return "证据不足 · 已拦截生成";
  return "离线证据答案";
}

function sourceKind(sourcePath: string): string {
  if (sourcePath.startsWith("issues/") || sourcePath.startsWith("external-issues/")) return "Issue";
  if (sourcePath.startsWith("git/")) return "Git history";
  if (sourcePath.includes("/repositories/") || sourcePath.startsWith("repositories/")) return "Code";
  return "Document";
}

function inferProjectId(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return null;
  if (/(spring\s*boot|laravel|8080|sanctum|任务接口|端口占用|本地 actor)/i.test(normalized)) {
    return "sample-data";
  }
  if (/(obsidian|vault|inbox|research|topic index|agent evaluation|个人 ai 工作流)/i.test(normalized)) {
    return "obsidian-vault";
  }
  return null;
}

function readableError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  return "请求没有完成，请确认后端服务仍在运行。";
}

function clearRequestError(): void {
  requestError.value = "";
  retryAction.value = null;
}

function resetFeedback(): void {
  feedbackRating.value = null;
  feedbackComment.value = "";
  feedbackIncorrectCitations.value = [];
  feedbackCorrectionText.value = "";
  feedbackStatus.value = "";
}

async function sendAnswerFeedback(): Promise<void> {
  if (!answer.value || !feedbackRating.value || isSubmittingFeedback.value) return;
  isSubmittingFeedback.value = true;
  feedbackStatus.value = "正在提交反馈…";
  try {
    const response = await submitAnswerFeedback(
      {
        task_id: answer.value.task_id,
        project_id: answer.value.project_id ?? undefined,
        query: answer.value.query,
        rating: feedbackRating.value,
        comment: feedbackComment.value.trim(),
        incorrect_citations: [...feedbackIncorrectCitations.value],
        citation_corrections: feedbackIncorrectCitations.value.map((citation) => ({
          citation,
          corrected_citation: feedbackCorrectionText.value.trim(),
        })),
      },
      selectedActorId.value || undefined,
    );
    feedbackStatus.value = response.status === "pending"
      ? "反馈已提交，等待人工确认后进入评测集"
      : `反馈已提交：${response.status}`;
  } catch (error) {
    feedbackStatus.value = `反馈提交失败：${readableError(error)}`;
  } finally {
    isSubmittingFeedback.value = false;
  }
}

function setRequestError(error: unknown, action: "bootstrap" | "search" | "index"): void {
  requestError.value = readableError(error);
  retryAction.value = action;
}

function buildKnowledgeNote(response: AgentResponse, title: string): string {
  const sourceEvidence = uniqueEvidence(evidenceForResponse(response));
  const citations = response.citations.length
    ? [...new Set(response.citations)].map((citation, index) => `${index + 1}. ${citation}`).join("\n")
    : "- No direct citation was returned.";
  const evidence = sourceEvidence.length
    ? sourceEvidence
        .map((hit) => `### ${sourceKind(hit.source_path)} · ${hit.source_path}\n\n${hit.content.trim()}`)
        .join("\n\n")
    : "暂无证据摘要。";
  const warning = response.warning ?? "请结合来源位置进行最终判断。";
  const keySteps = response.key_steps.length
    ? response.key_steps.map((step) => `- ${step}`).join("\n")
    : "- 结合证据来源继续复核";
  return `# ${title}

## 结论

${response.answer.trim()}

## 关键步骤

${keySteps}

## 证据来源

${citations}

## 证据摘要

${evidence}

## 复核提示

${warning}
`;
}

function buildIssueBody(response: AgentResponse): string {
  const citations = response.citations.length
    ? [...new Set(response.citations)].map((citation) => `- ${citation}`).join("\n")
    : "- 暂无直接引用";
  const nextSteps = response.report?.next_steps.length
    ? response.report.next_steps.map((step) => `- ${step}`).join("\n")
    : "- 请结合证据来源继续复核";
  return `## 问题背景

${response.query}

## 当前判断

${response.answer.trim()}

## 建议下一步

${nextSteps}

## 来源

${citations}
`;
}

function toggleExecutionDetails(event: Event): void {
  showExecutionDetails.value = (event.target as HTMLDetailsElement).open;
}

async function selectWorkspaceView(viewId: WorkspaceViewId): Promise<void> {
  activeView.value = viewId;
  if (viewId === "tasks") {
    await loadTaskRecords();
  }
}

function stopAgentProgress(): void {
  agentPhase.value = "";
}

async function loadTaskRecords(): Promise<void> {
  if (isLoadingTasks.value) return;
  isLoadingTasks.value = true;
  taskLoadError.value = "";
  try {
    const response = await listAgentTasks(
      selectedProjectId.value || undefined,
      50,
      selectedActorId.value || undefined,
      taskStatusFilter.value === "all" ? undefined : taskStatusFilter.value,
      taskSortBy.value,
      taskSortOrder.value,
    );
    taskRecords.value = response.items;
    selectedTaskIds.value = selectedTaskIds.value.filter((taskId) =>
      response.items.some((task) => task.task_id === taskId),
    );
    if (selectedTask.value && !response.items.some((task) => task.task_id === selectedTask.value?.task_id)) {
      selectedTask.value = null;
    }
    backendHealth.value = "online";
  } catch (error) {
    taskLoadError.value = readableError(error);
    backendHealth.value = "offline";
  } finally {
    isLoadingTasks.value = false;
  }
}

function toggleSelectAllTasks(): void {
  selectedTaskIds.value = allVisibleTasksSelected.value
    ? []
    : taskRecords.value.map((task) => task.task_id);
}

async function batchManageTasks(action: AgentTaskBatchAction): Promise<void> {
  if (isBatchingTasks.value || !can("agent")) return;
  const taskIds = action === "resume"
    ? selectedResumableTaskIds.value
    : selectedTaskIds.value;
  if (!taskIds.length) return;
  if (action === "rerun" && !window.confirm(`将重新运行 ${taskIds.length} 个任务并创建新的任务记录，是否继续？`)) {
    return;
  }
  isBatchingTasks.value = true;
  taskBatchStatus.value = "";
  taskLoadError.value = "";
  try {
    const response = await batchAgentTasks(
      taskIds,
      action,
      5,
      selectedActorId.value || undefined,
    );
    const successCount = response.items.length;
    const failureCount = response.failures.length;
    taskBatchStatus.value = failureCount
      ? `已处理 ${successCount} 个，${failureCount} 个失败：${response.failures[0]?.detail ?? "请查看任务状态"}`
      : `已处理 ${successCount} 个任务`;
    selectedTaskIds.value = [];
    await loadTaskRecords();
  } catch (error) {
    taskLoadError.value = readableError(error);
  } finally {
    isBatchingTasks.value = false;
  }
}

async function openTaskRecord(taskId: string): Promise<void> {
  if (taskActionId.value) return;
  taskActionId.value = taskId;
  taskLoadError.value = "";
  try {
    selectedTask.value = await getAgentTask(taskId, selectedActorId.value || undefined);
  } catch (error) {
    taskLoadError.value = readableError(error);
  } finally {
    taskActionId.value = "";
  }
}

async function resumeTaskRecord(taskId: string): Promise<void> {
  if (taskActionId.value || !can("agent")) return;
  taskActionId.value = taskId;
  taskLoadError.value = "";
  try {
    selectedTask.value = await resumeAgentTask(
      taskId,
      5,
      selectedActorId.value || undefined,
    );
    await loadTaskRecords();
  } catch (error) {
    taskLoadError.value = readableError(error);
  } finally {
    taskActionId.value = "";
  }
}

async function chooseExample(exampleQuery: string, projectId?: string): Promise<void> {
  query.value = exampleQuery;
  const targetProjectId = projectId ?? "sample-data";
  if (targetProjectId !== selectedProjectId.value) {
    selectedProjectId.value = targetProjectId;
    await handleProjectChange();
  }
}

async function switchToSuggestedProject(): Promise<void> {
  const targetProjectId = projectMismatch.value?.suggestedProjectId;
  if (!targetProjectId) return;
  selectedProjectId.value = targetProjectId;
  await handleProjectChange();
}

function showIndexPermissionNotice(): void {
  clearRequestError();
  backendHealth.value = "online";
  status.value = "后端在线，当前角色无索引权限";
}

async function refreshIndex() {
  if (isIndexing.value) return;
  if (!canIndex()) {
    showIndexPermissionNotice();
    return;
  }
  isIndexing.value = true;
  clearRequestError();
  status.value = "正在建立当前项目索引…";
  try {
    indexInfo.value = await indexSource(
      "sample-data",
      selectedProjectId.value || undefined,
      selectedActorId.value || undefined,
    );
    backendHealth.value = "online";
    clearRequestError();
    status.value = `已索引 ${indexInfo.value.document_count} 个文件、${indexInfo.value.chunk_count} 个 Chunk`;
  } catch (error) {
    backendHealth.value = "offline";
    setRequestError(error, "index");
    status.value = `后端未连接：${readableError(error)}`;
  } finally {
    isIndexing.value = false;
  }
}

async function search() {
  if (!query.value.trim() || isLoading.value || isIndexing.value) return;
  if (projectMismatch.value) {
    status.value = `当前项目与问题不匹配，请先切换到${projectMismatch.value.suggestedProject.name}。`;
    return;
  }
  clearRequestError();
  resetFeedback();
  isLoading.value = true;
  agentProgressSteps.value = [];
  status.value = "Agent 正在分类、检索并组织证据…";
  agentAbortController = new AbortController();
  try {
    const response = await streamAgent(
      query.value,
      "sample-data",
      5,
      selectedProjectId.value || undefined,
      selectedActorId.value || undefined,
      {
        signal: agentAbortController.signal,
        onProgress: (progress) => {
          agentProgressSteps.value = [...agentProgressSteps.value, progress];
          agentPhase.value = `${progress.step.name} · ${progress.step.detail}`;
          status.value = `Agent 正在执行：${progress.step.name}`;
        },
      },
    );
    backendHealth.value = "online";
    answer.value = response;
    const visibleEvidence = evidenceForResponse(response);
    results.value = visibleEvidence;
    noteTitle.value = query.value.trim().slice(0, 80) || "DevSage knowledge note";
    noteContent.value = buildKnowledgeNote(response, noteTitle.value);
    issueTitle.value = `[${categoryLabel(response.category)}] ${query.value.trim()}`.slice(0, 200);
    issueBody.value = buildIssueBody(response);
    pendingPreview.value = null;
    pendingCodePreview.value = null;
    pendingIssuePreview.value = null;
    issueWriteStatus.value = "";
    showExecutionDetails.value = false;
    clearRequestError();
    status.value = response.evidence_sufficient
      ? `找到 ${uniqueEvidence(visibleEvidence).length} 个来源的直接证据`
      : "证据不足，页面保留排查线索";
  } catch (error) {
    if (isAgentStreamCancelled(error)) {
      clearRequestError();
      status.value = "已取消本次 Agent 检索，可以修改问题后重新排查";
      return;
    }
    backendHealth.value = "offline";
    setRequestError(error, "search");
    status.value = `检索失败：${readableError(error)}`;
  } finally {
    stopAgentProgress();
    isLoading.value = false;
    agentAbortController = null;
  }
}

function cancelAgentSearch(): void {
  if (!agentAbortController) return;
  agentAbortController.abort();
  status.value = "正在取消 Agent 任务…";
}

async function retryLastRequest(): Promise<void> {
  if (retryAction.value === "search") {
    await search();
    return;
  }
  if (retryAction.value === "index") {
    await refreshIndex();
    return;
  }
  if (retryAction.value === "bootstrap") {
    clearRequestError();
    await checkBackendHealth();
    const loaded = await loadProjects();
    if (loaded) {
      await loadIndexStatus();
      if (!canIndex()) showIndexPermissionNotice();
    }
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

async function createIssuePreview() {
  if (!answer.value || !issueTitle.value.trim() || !issueBody.value.trim() || !can("issue_write_preview")) return;
  issueWriteStatus.value = "正在生成 Issue 草稿预览…";
  try {
    pendingIssuePreview.value = await previewIssueWrite(
      issueTitle.value.trim(),
      issueBody.value.trim(),
      issueLabels.value.split(",").map((label) => label.trim()).filter(Boolean),
      selectedProjectId.value || undefined,
      selectedActorId.value || undefined,
    );
    issueWriteStatus.value = "预览已生成；尚未发送到外部 Issue 平台。";
  } catch (error) {
    issueWriteStatus.value = `Issue 预览失败：${error instanceof Error ? error.message : "未知错误"}`;
  }
}

async function approveIssue() {
  if (!pendingIssuePreview.value) return;
  issueWriteStatus.value = "正在提交 Issue…";
  try {
    pendingIssuePreview.value = await approveIssueWrite(
      pendingIssuePreview.value.preview_id,
      selectedActorId.value || undefined,
    );
    issueWriteStatus.value = "Issue 已提交。";
  } catch (error) {
    issueWriteStatus.value = `Issue 提交失败：${error instanceof Error ? error.message : "未知错误"}`;
  }
}

async function loadProjects(): Promise<boolean> {
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
    clearRequestError();
    return true;
  } catch (error) {
    backendHealth.value = "offline";
    setRequestError(error, "bootstrap");
    status.value = `项目列表未连接：${readableError(error)}`;
    return false;
  }
}

async function loadIndexStatus(): Promise<void> {
  if (!selectedProjectId.value) return;
  try {
    const info = await getIndexStatus(selectedProjectId.value, selectedActorId.value || undefined);
    indexInfo.value = info;
    backendHealth.value = "online";
    status.value = info.indexed
      ? `已读取最新索引：${info.document_count} 个文件、${info.chunk_count} 个 Chunk`
      : "当前项目尚未建立索引，可点击按钮建立快照";
  } catch {
    indexInfo.value = null;
  }
}

function resetScopeState() {
  answer.value = null;
  results.value = [];
  resetFeedback();
  indexInfo.value = null;
  pendingPreview.value = null;
  pendingCodePreview.value = null;
  pendingIssuePreview.value = null;
  writebackStatus.value = "";
  codeWritebackStatus.value = "";
  issueWriteStatus.value = "";
  taskRecords.value = [];
  selectedTask.value = null;
  taskLoadError.value = "";
  selectedTaskIds.value = [];
  taskBatchStatus.value = "";
}

async function handleProjectChange() {
  const project = projects.value.find((item) => item.project_id === selectedProjectId.value);
  if (project && !project.members.some((member) => member.actor_id === selectedActorId.value)) {
    selectedActorId.value = project.members[0]?.actor_id ?? "local-demo";
  }
  resetScopeState();
  clearRequestError();
  status.value = "正在切换项目并读取最新索引状态…";
  await loadIndexStatus();
  if (!canIndex()) showIndexPermissionNotice();
}

async function handleActorChange() {
  resetScopeState();
  clearRequestError();
  status.value = "正在切换本地角色并读取最新索引状态…";
  await loadIndexStatus();
  if (!canIndex()) showIndexPermissionNotice();
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
  if (isLoggingIn.value) return;
  isLoggingIn.value = true;
  loginStatus.value = "正在登录…";
  try {
    const response = await login(loginUsername.value.trim(), loginPassword.value);
    setAuthToken(response.access_token);
    authToken.value = response.access_token;
    selectedActorId.value = response.actor_id;
    authUsername.value = response.username;
    loginPassword.value = "";
    loginStatus.value = `已登录 ${response.username}`;
    const loaded = await loadProjects();
    if (loaded) {
      await loadIndexStatus();
      if (!canIndex()) showIndexPermissionNotice();
    }
  } catch (error) {
    loginStatus.value = `登录失败：${readableError(error)}`;
  } finally {
    isLoggingIn.value = false;
  }
}

function logout() {
  setAuthToken("");
  authToken.value = "";
  authUsername.value = "";
  loginPassword.value = "";
  resetScopeState();
  status.value = "已退出登录";
}

onMounted(async () => {
  await checkBackendHealth();
  if (requiresLogin.value) {
    status.value = "后端已启用正式认证，请先登录";
    return;
  }
  const loaded = await loadProjects();
  if (loaded) {
    await loadIndexStatus();
    if (!canIndex()) showIndexPermissionNotice();
  }
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
        <div class="login-card-heading">
          <span class="eyebrow">SECURE ACCESS</span>
          <strong>正式身份认证</strong>
        </div>
        <p>当前后端已开启 Bearer Token 认证，登录后才能访问项目和检索能力。</p>
        <label class="field-label">
          用户名
          <input v-model="loginUsername" autocomplete="username" aria-label="用户名" required :disabled="isLoggingIn" />
        </label>
        <label class="field-label">
          密码
          <input v-model="loginPassword" type="password" autocomplete="current-password" aria-label="密码" required :disabled="isLoggingIn" />
        </label>
        <button type="submit" :disabled="isLoggingIn">{{ isLoggingIn ? "登录中…" : "登录" }}</button>
        <small v-if="loginStatus" class="writeback-status" role="status" aria-live="polite">{{ loginStatus }}</small>
      </form>

      <div v-if="!requiresLogin" class="workspace-layout">
        <aside class="workspace-sidebar" aria-label="DevSage 工作台导航">
          <div class="workspace-sidebar-heading">
            <span class="eyebrow">WORKSPACE</span>
            <strong>研发助手</strong>
          </div>
          <nav class="workspace-nav" aria-label="工作台页面">
            <button
              v-for="view in workspaceViews"
              :key="view.id"
              type="button"
              :class="{ active: activeView === view.id }"
              :aria-current="activeView === view.id ? 'page' : undefined"
              @click="selectWorkspaceView(view.id)"
            >
              <span class="workspace-nav-icon" aria-hidden="true">{{ view.icon }}</span>
              <span>
                <strong>{{ view.label }}</strong>
                <small>{{ view.description }}</small>
              </span>
            </button>
          </nav>
          <div class="workspace-sidebar-note">
            <span class="eyebrow">SAFETY</span>
            <p>答案先读证据，写回必须经过预览和审批。</p>
          </div>
        </aside>

        <div class="workspace-main">
          <div class="workspace-view-heading">
            <div>
              <span class="eyebrow">{{ activeViewMeta.label }}</span>
              <h2>{{ activeViewMeta.description }}</h2>
            </div>
            <span class="workspace-view-status">{{ currentProject?.name ?? "等待项目" }}</span>
          </div>

          <div v-if="activeView === 'workspace'" class="workspace-query">
          <div class="toolbar">
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
        <span v-if="currentProject?.read_only" class="readonly-badge">
          外部只读 · {{ currentProject.source_kind === "obsidian_vault" ? "Obsidian Vault" : "只读源" }}
        </span>
        <span v-if="healthDetails?.auth_enabled" class="auth-badge">
          已认证 · {{ authUsername || selectedActorId }}
        </span>
        <button v-if="healthDetails?.auth_enabled" type="button" class="secondary-button" @click="logout">
          退出登录
        </button>
        <button type="button" @click="refreshIndex" :disabled="!canIndex() || isIndexing">
          {{ isIndexing ? "索引中…" : "重新索引当前项目" }}
        </button>
        <span class="health-badge" :class="`health-${backendHealth}`" aria-live="polite">
          后端：{{ backendHealth === "checking" ? "检查中" : backendHealth === "online" ? "在线" : "离线" }}
        </span>
        <span v-if="healthDetails" class="health-details">
          {{ healthDetails.storage ?? "memory" }} · Embedding {{ healthDetails.embedding_provider ?? "unknown" }} · AI {{ healthDetails.answer_generation_model ?? "offline-rules" }} · Issue {{ healthDetails.external_issue_configured ? "已配置" : "未配置" }}
        </span>
        <span>{{ status }}</span>
        <span v-if="indexSummary" class="index-count">{{ indexSummary }}</span>
          </div>

      <form class="search-box" @submit.prevent="search">
        <input
          v-model="query"
          placeholder="例如：8080 端口被占用，应该怎么排查？"
          aria-label="研发问题"
        />
        <button type="submit" :disabled="isLoading || isIndexing">
          {{ isIndexing ? "索引中…" : isLoading ? "检索中…" : "开始排查" }}
        </button>
      </form>

      <div v-if="isLoading" class="agent-progress" role="status" aria-live="polite">
        <span class="agent-progress-spinner" aria-hidden="true"></span>
        <span>{{ agentPhase || "Agent 正在处理…" }}</span>
        <small>后端 SSE 已连接 · 已完成 {{ agentProgressSteps.length }} 个步骤</small>
        <button type="button" class="secondary-button agent-cancel-button" @click="cancelAgentSearch">
          取消任务
        </button>
      </div>

      <div v-if="requestError" class="request-error" role="alert">
        <div>
          <strong>{{ retryAction === "search" ? "检索没有完成" : "后端连接没有完成" }}</strong>
          <span>{{ requestError }}</span>
        </div>
        <button
          type="button"
          class="secondary-button"
          :disabled="isLoading || isIndexing"
          @click="retryLastRequest"
        >
          重新尝试
        </button>
      </div>

      <div v-if="projectMismatch" class="project-mismatch" role="alert">
        <div>
          <strong>检索范围提醒</strong>
          <span>当前项目是“{{ currentProject?.name }}”，但这个问题更像属于“{{ projectMismatch.suggestedProject.name }}”。</span>
        </div>
        <button type="button" class="secondary-button" @click="switchToSuggestedProject">
          切换到{{ projectMismatch.suggestedProject.name }}
        </button>
      </div>

      <section class="example-prompts" aria-label="知识库问题示例">
        <div class="example-prompts-heading">
          <strong>从知识库试试</strong>
          <span>点击示例会自动切换到对应项目，再点击“开始排查”</span>
        </div>
        <div class="example-group-list">
          <div v-for="group in exampleGroups" :key="group.label" class="example-group">
            <div class="example-group-label">
              <span class="example-group-icon" :class="`example-group-icon-${group.tone}`" aria-hidden="true">{{ group.icon }}</span>
              <span>{{ group.label }}</span>
            </div>
            <div class="prompt-chip-row">
              <button
                v-for="example in group.examples"
                :key="example.query"
                type="button"
                class="prompt-chip"
                @click="chooseExample(example.query, example.projectId)"
              >
                {{ example.label }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="currentProject?.read_only" class="vault-project-card" aria-label="Obsidian Vault 项目状态">
        <div class="vault-project-head">
          <div>
            <span class="eyebrow">External knowledge source</span>
            <h2>{{ currentProject.name }}</h2>
          </div>
          <span class="status-pill">只读保护</span>
        </div>
        <p>当前页面只读取 Vault 内容，所有索引快照保存在 DevSage 自己的 data 目录，不会在 Vault 内创建或修改文件。</p>
        <div class="vault-project-facts">
          <span>项目：{{ currentProject.source_root }}</span>
          <span>角色：{{ currentMember?.role ?? "vault_viewer" }}</span>
          <span>过滤：.obsidian · cache · build · node_modules</span>
          <span v-if="indexSummary">{{ indexSummary.replace("files", "文件").replace("chunks", "Chunk") }}</span>
        </div>
      </section>

      <section v-if="answer" class="results" aria-live="polite">
        <article class="answer-card">
          <div class="result-meta">
            <strong>回答</strong>
            <span>{{ categoryLabel(answer.category) }} · {{ answer.status }} · 项目 {{ answer.project_id ?? "兼容 source_root" }}</span>
          </div>
          <div class="generation-status" :class="`generation-${answer.generation_mode}`">
            {{ generationLabel(answer.generation_mode, answer.generation_model) }}
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
          <section v-if="keySteps.length" class="key-steps" aria-labelledby="key-steps-heading">
            <div class="subsection-heading">
              <span class="eyebrow">NEXT STEPS</span>
              <h3 id="key-steps-heading">关键步骤</h3>
            </div>
            <ol class="key-step-list">
              <li v-for="(step, index) in keySteps" :key="`key-step-${index}`">
                <span class="key-step-number">{{ index + 1 }}</span>
                <span>{{ step }}</span>
              </li>
            </ol>
          </section>
          <small v-if="answer.warning" class="warning">{{ answer.warning }}</small>
          <small v-if="answer.generation_warning" class="generation-warning">
            {{ answer.generation_warning }}。当前答案仍来自已检索证据，未使用未经验证的模型内容。
          </small>
        </article>

        <article class="feedback-card" aria-label="答案反馈与引用纠错">
          <div class="result-meta">
            <strong>答案反馈与引用纠错</strong>
            <span>人工确认后回流评测集</span>
          </div>
          <div class="feedback-actions">
            <button
              type="button"
              class="secondary-button"
              :class="{ 'feedback-selected': feedbackRating === 'helpful' }"
              :disabled="isSubmittingFeedback"
              @click="feedbackRating = 'helpful'; sendAnswerFeedback()"
            >
              答案有帮助
            </button>
            <button
              type="button"
              class="secondary-button"
              :class="{ 'feedback-selected': feedbackRating === 'needs_revision' }"
              :disabled="isSubmittingFeedback"
              @click="feedbackRating = 'needs_revision'"
            >
              需要修正
            </button>
          </div>
          <template v-if="feedbackRating === 'needs_revision'">
            <label class="field-label" for="feedback-comment">
              问题说明
              <textarea
                id="feedback-comment"
                v-model="feedbackComment"
                rows="3"
                placeholder="例如：结论没有回答端口冲突的处理顺序"
              ></textarea>
            </label>
            <fieldset class="feedback-fieldset">
              <legend>错误引用（可选）</legend>
              <label v-for="evidence in evidenceView" :key="`feedback-${evidence.citation}`" class="feedback-citation-option">
                <input v-model="feedbackIncorrectCitations" type="checkbox" :value="evidence.citation">
                <span>{{ evidence.source_path }} · L{{ evidence.start_line }}-L{{ evidence.end_line }}</span>
              </label>
              <small v-if="!evidenceView.length" class="field-help">当前答案没有可标记的直接引用。</small>
            </fieldset>
            <label class="field-label" for="feedback-correction">
              正确引用（可选）
              <textarea
                id="feedback-correction"
                v-model="feedbackCorrectionText"
                rows="2"
                placeholder="填写正确文件路径或文件路径:行号"
              ></textarea>
            </label>
            <div class="feedback-submit-row">
              <button type="button" :disabled="isSubmittingFeedback" @click="sendAnswerFeedback">
                {{ isSubmittingFeedback ? "提交中…" : "提交修正反馈" }}
              </button>
            </div>
          </template>
          <small v-if="feedbackStatus" class="feedback-status" role="status">{{ feedbackStatus }}</small>
        </article>

        <section class="evidence-section" aria-labelledby="evidence-heading">
          <div class="section-heading">
            <div>
              <span class="eyebrow">GROUNDING</span>
              <h2 id="evidence-heading">引用证据</h2>
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
              <small class="evidence-citation">{{ answer.source_root }}/{{ evidence.source_path }} · L{{ evidence.start_line }}-L{{ evidence.end_line }}</small>
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

        <details class="execution-details" :open="showExecutionDetails" @toggle="toggleExecutionDetails">
          <summary>检索过程与调试信息 · {{ answer.tool_calls.length }} 个工具 · {{ answer.steps.length }} 个步骤</summary>
          <div class="tool-tags">
            <span v-for="tool in answer.tool_calls" :key="tool" class="tool-tag">{{ tool }}</span>
          </div>
          <small>
            工具重试：{{ answer.tool_retry_count }} 次 · Token 估算：{{ answer.usage.total_token_estimate }} ·
            Agent {{ answer.usage.runtime_ms }}ms
            <span v-if="answer.generation_runtime_ms > 0"> · 模型生成 {{ answer.generation_runtime_ms }}ms</span>
          </small>
          <ol class="agent-steps">
            <li v-for="step in answer.steps" :key="`${step.name}-${step.status}`">
              <strong>{{ step.name }}</strong> · {{ step.status }} · {{ step.detail }}
            </li>
          </ol>
        </details>

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

        <template v-if="canIssueWrite">
        <article class="issue-writeback-card">
          <div class="result-meta">
            <strong>External Issue preview and approval</strong>
            <span v-if="pendingIssuePreview" class="status-pill">{{ pendingIssuePreview.status }}</span>
          </div>
          <p class="approval-hint">
            先把当前排查结果整理成 Issue 草稿；预览不会联网，只有 operator 审批后才会尝试发送到外部平台。
          </p>
          <div v-if="!can('issue_write_preview')" class="locked-state">
            当前角色没有 Issue 写入权限。请切换到 operator，或仅保留检索和阅读。
          </div>
          <template v-else>
            <label class="field-label">
              Issue title
              <input v-model="issueTitle" aria-label="Issue title" />
            </label>
            <label class="field-label">
              Labels <span class="field-help">用英文逗号分隔</span>
              <input v-model="issueLabels" aria-label="Issue labels" />
            </label>
            <label class="field-label">
              Issue body
              <textarea v-model="issueBody" rows="9" aria-label="Issue body"></textarea>
            </label>
            <div class="writeback-actions">
              <button type="button" @click="createIssuePreview" :disabled="!issueTitle.trim() || !issueBody.trim()">
                Generate Issue preview
              </button>
              <button
                v-if="pendingIssuePreview && pendingIssuePreview.status === 'pending'"
                type="button"
                @click="approveIssue"
                :disabled="!can('issue_write_approve')"
              >
                Approve and submit
              </button>
            </div>
            <small v-if="issueWriteStatus" class="writeback-status">{{ issueWriteStatus }}</small>
            <div v-if="pendingIssuePreview" class="issue-preview-summary">
              <span>状态：{{ pendingIssuePreview.status }}</span>
              <a v-if="pendingIssuePreview.remote_url" :href="pendingIssuePreview.remote_url" target="_blank" rel="noreferrer noopener">
                打开远程 Issue #{{ pendingIssuePreview.remote_number }}
              </a>
            </div>
          </template>
        </article>

        </template>
        <details v-else class="locked-writeback-card">
          <summary>External Issue 写回（当前角色不可用）</summary>
          <div class="locked-state">
            当前角色没有 Issue 写入权限；只保留检索和阅读，不会向外部 Issue 平台发送内容。
          </div>
        </details>

        <template v-if="canCodeWrite">
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

        </template>
        <details v-else class="locked-writeback-card">
          <summary>代码修改写回（当前角色不可用）</summary>
          <div class="locked-state">
            当前角色没有代码写入权限；只读项目不会修改源文件或 Vault 内容。
          </div>
        </details>

      </section>
      <p v-else class="empty-state">输入问题后查看带来源引用的检索证据。</p>
          </div>

          <section v-else-if="activeView === 'tasks'" class="task-history-page" aria-label="Agent 任务记录">
            <div class="task-history-toolbar">
              <div>
                <span class="eyebrow">TASK HISTORY</span>
                <h3>已持久化的 Agent 任务</h3>
                <p>按当前项目查看排查记录；打开任务可回看答案、引用和执行步骤。</p>
              </div>
              <button type="button" class="secondary-button" @click="loadTaskRecords" :disabled="isLoadingTasks">
                {{ isLoadingTasks ? "读取中…" : "刷新记录" }}
              </button>
            </div>

            <div class="task-filter-bar" aria-label="任务筛选与排序">
              <label>
                <span>状态</span>
                <select v-model="taskStatusFilter" aria-label="任务状态筛选" @change="loadTaskRecords">
                  <option v-for="option in taskStatusOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
              </label>
              <label>
                <span>排序</span>
                <select v-model="taskSortBy" aria-label="任务排序字段" @change="loadTaskRecords">
                  <option value="updated_at">最新更新时间</option>
                  <option value="runtime_ms">耗时</option>
                </select>
              </label>
              <label>
                <span>顺序</span>
                <select v-model="taskSortOrder" aria-label="任务排序顺序" @change="loadTaskRecords">
                  <option value="desc">从高到低 / 最新</option>
                  <option value="asc">从低到高 / 最早</option>
                </select>
              </label>
              <span class="task-filter-count">当前列表 {{ taskRecords.length }} 条</span>
            </div>

            <div v-if="can('agent') && taskRecords.length" class="task-batch-toolbar">
              <button type="button" class="secondary-button" @click="toggleSelectAllTasks">
                {{ allVisibleTasksSelected ? "清除选择" : "全选当前列表" }}
              </button>
              <span>已选择 {{ selectedTaskIds.length }} 条</span>
              <button type="button" @click="batchManageTasks('resume')" :disabled="isBatchingTasks || !selectedResumableTaskIds.length">
                {{ isBatchingTasks ? "处理中…" : `批量恢复（${selectedResumableTaskIds.length}）` }}
              </button>
              <button type="button" class="secondary-button" @click="batchManageTasks('rerun')" :disabled="isBatchingTasks || !selectedTaskIds.length">
                批量重新运行
              </button>
              <span v-if="taskBatchStatus" class="task-batch-status" role="status">{{ taskBatchStatus }}</span>
            </div>

            <div v-if="isLoadingTasks" class="task-state-card" role="status">正在读取任务记录…</div>
            <div v-else-if="taskLoadError" class="task-state-card task-state-error" role="alert">
              <strong>任务记录读取失败</strong>
              <span>{{ taskLoadError }}</span>
              <button type="button" class="secondary-button" @click="loadTaskRecords">重新尝试</button>
            </div>
            <div v-else-if="!taskRecords.length" class="task-state-card">
              <strong>当前项目还没有持久化任务</strong>
              <span>回到工作台提交一次问题，完成后的 Agent 任务会自动出现在这里。</span>
              <button type="button" @click="selectWorkspaceView('workspace')">返回工作台</button>
            </div>
            <div v-else class="task-history-layout">
              <div class="task-record-list">
                <article v-for="task in taskRecords" :key="task.task_id" class="task-record-card" :class="{ selected: selectedTask?.task_id === task.task_id }">
                  <div class="task-record-head">
                    <label v-if="can('agent')" class="task-select-control">
                      <input v-model="selectedTaskIds" type="checkbox" :value="task.task_id" :aria-label="`选择任务 ${task.task_id}`">
                      <span>选择</span>
                    </label>
                    <span class="task-status" :class="`task-status-${task.status}`">{{ task.status }}</span>
                    <small>{{ task.category }}</small>
                  </div>
                  <strong>{{ task.query }}</strong>
                  <small class="task-record-id">{{ task.task_id }} · {{ task.runtime_ms }}ms</small>
                  <div class="task-record-meta">
                    <span>{{ task.step_count }} 步骤</span>
                    <span>{{ task.tool_calls }} 工具</span>
                    <span>{{ task.evidence_count }} 条证据</span>
                  </div>
                  <div class="task-record-actions">
                    <button type="button" class="secondary-button" @click="openTaskRecord(task.task_id)" :disabled="Boolean(taskActionId)">
                      {{ taskActionId === task.task_id ? "打开中…" : "查看详情" }}
                    </button>
                    <button v-if="task.resumable && can('agent')" type="button" @click="resumeTaskRecord(task.task_id)" :disabled="Boolean(taskActionId)">
                      {{ taskActionId === task.task_id ? "恢复中…" : "恢复任务" }}
                    </button>
                  </div>
                </article>
              </div>

              <article v-if="selectedTask" class="task-detail-card">
                <div class="result-meta">
                  <strong>任务详情</strong>
                  <span>{{ selectedTask.status }} · {{ selectedTask.task_id }}</span>
                </div>
                <h3>{{ selectedTask.query }}</h3>
                <div class="markdown-content task-detail-answer">
                  <template v-for="(block, index) in selectedTaskBlocks" :key="`task-answer-${index}`">
                    <h4 v-if="block.type === 'heading'" v-html="block.html"></h4>
                    <p v-else-if="block.type === 'paragraph'" v-html="block.html"></p>
                    <blockquote v-else-if="block.type === 'quote'" v-html="block.html"></blockquote>
                    <component v-else-if="block.type === 'list'" :is="block.ordered ? 'ol' : 'ul'">
                      <li v-for="(item, itemIndex) in block.items" :key="`task-item-${index}-${itemIndex}`" v-html="item"></li>
                    </component>
                    <pre v-else-if="block.type === 'code'"><code>{{ block.code }}</code></pre>
                  </template>
                </div>
                <div v-if="selectedTask.citations.length" class="task-detail-section">
                  <span class="eyebrow">GROUNDING</span>
                  <strong>引用证据</strong>
                  <ul>
                    <li v-for="citation in selectedTask.citations" :key="citation">{{ citation }}</li>
                  </ul>
                </div>
                <details class="execution-details">
                  <summary>执行步骤 · {{ selectedTask.steps.length }} 步</summary>
                  <ol class="agent-steps">
                    <li v-for="step in selectedTask.steps" :key="`${step.name}-${step.status}`">
                      <strong>{{ step.name }}</strong> · {{ step.status }} · {{ step.detail }}
                    </li>
                  </ol>
                </details>
              </article>
            </div>
          </section>

          <div v-else-if="activeView !== 'tasks'" class="workspace-placeholder">
            <span class="eyebrow">NEXT BUILD</span>
            <h3>{{ activeViewMeta.label }}页面骨架已就位</h3>
            <p>{{ activeViewMeta.description }}会在后续阶段接入真实数据和操作。当前项目上下文、权限和索引状态仍保持可见。</p>

            <div class="placeholder-grid">
              <article>
                <span class="placeholder-icon">✓</span>
                <div>
                  <strong>当前项目上下文</strong>
                  <p>{{ currentProject?.name ?? "尚未连接项目" }}</p>
                </div>
              </article>
              <article>
                <span class="placeholder-icon">▤</span>
                <div>
                  <strong>索引状态</strong>
                  <p>{{ indexSummary || "正在读取索引状态" }}</p>
                </div>
              </article>
              <article v-if="activeView === 'retrieval'">
                <span class="placeholder-icon">⌕</span>
                <div>
                  <strong>当前测试问题</strong>
                  <p>{{ query || "输入问题后在工作台运行一次检索" }}</p>
                </div>
              </article>
              <article v-else-if="activeView === 'tasks'">
                <span class="placeholder-icon">◷</span>
                <div>
                  <strong>任务状态</strong>
                  <p>后端任务快照已支持持久化，历史列表和恢复操作待接入。</p>
                </div>
              </article>
              <article v-else-if="activeView === 'evaluation'">
                <span class="placeholder-icon">◒</span>
                <div>
                  <strong>评测状态</strong>
                  <p>离线评测报告已生成，指标趋势和失败案例筛选待接入。</p>
                </div>
              </article>
              <article v-else>
                <span class="placeholder-icon">→</span>
                <div>
                  <strong>下一步</strong>
                  <p>先返回工作台提交问题，查看自然语言答案和单列引用证据。</p>
                </div>
              </article>
            </div>
          </div>
        </div>

        <aside class="workspace-inspector" aria-label="当前项目上下文">
          <div class="context-card">
            <div class="context-card-heading">
              <div>
                <span class="eyebrow">CONTEXT</span>
                <h2>当前上下文</h2>
              </div>
              <span class="health-badge" :class="`health-${backendHealth}`">
                {{ backendHealth === "online" ? "在线" : backendHealth === "checking" ? "检查中" : "离线" }}
              </span>
            </div>
            <dl class="context-facts">
              <div>
                <dt>项目</dt>
                <dd>{{ currentProject?.name ?? "未选择" }}</dd>
              </div>
              <div>
                <dt>角色</dt>
                <dd>{{ currentMember?.role ?? selectedActorId }}</dd>
              </div>
              <div>
                <dt>索引</dt>
                <dd>{{ indexSummary || "尚未读取" }}</dd>
              </div>
              <div>
                <dt>权限</dt>
                <dd>{{ currentProject?.read_only ? "外部只读" : canIndex() ? "可管理索引" : "只读检索" }}</dd>
              </div>
            </dl>
          </div>

          <div class="context-card">
            <span class="eyebrow">GROUNDING</span>
            <h2>证据上下文</h2>
            <template v-if="answer">
              <strong class="context-stat">{{ evidenceView.length }}</strong>
              <p>条去重后的直接证据</p>
              <div class="context-source-list">
                <span v-for="evidence in evidenceView.slice(0, 4)" :key="evidence.citation">
                  {{ evidence.source_path }} · L{{ evidence.start_line }}-L{{ evidence.end_line }}
                </span>
              </div>
            </template>
            <p v-else>提交问题后，这里会显示来源文件、行号和答案引用范围。</p>
          </div>

          <div class="context-card context-safety-card">
            <span class="eyebrow">SAFE WRITEBACK</span>
            <h2>安全边界</h2>
            <p>知识笔记、代码变更和外部 Issue 都必须先预览，再由具备权限的角色审批。</p>
          </div>
        </aside>
      </div>
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
  width: min(1440px, 100%);
  padding: clamp(24px, 5vw, 48px);
  border: 1px solid #d7e0ea;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 20px 60px rgba(42, 67, 101, 0.12);
}

.workspace-layout {
  display: grid;
  grid-template-columns: 188px minmax(0, 1fr) 280px;
  gap: 20px;
  align-items: start;
  margin-top: 28px;
}

.workspace-sidebar,
.workspace-inspector {
  position: sticky;
  top: 18px;
  display: grid;
  gap: 14px;
}

.workspace-sidebar {
  padding: 14px;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #f7faff;
}

.workspace-sidebar-heading,
.context-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.workspace-sidebar-heading {
  display: grid;
  gap: 4px;
  padding: 4px 6px 10px;
}

.workspace-sidebar-heading strong { color: #1d3555; font-size: 1.05rem; }
.workspace-nav { display: grid; gap: 6px; }
.workspace-nav button {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  width: 100%;
  padding: 9px 8px;
  border: 1px solid transparent;
  border-radius: 11px;
  color: #526176;
  background: transparent;
  text-align: left;
}
.workspace-nav button:hover,
.workspace-nav button.active {
  border-color: #c5d9ed;
  color: #1d568b;
  background: #eaf4fc;
}
.workspace-nav button > span:last-child { display: grid; gap: 2px; min-width: 0; }
.workspace-nav strong { font-size: 0.86rem; }
.workspace-nav small { color: #7890aa; font-size: 0.7rem; line-height: 1.35; }
.workspace-nav-icon {
  display: inline-flex;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  color: #4674a8;
  background: #dcecf9;
  font-size: 0.78rem;
  font-weight: 800;
}
.workspace-sidebar-note {
  margin-top: 8px;
  padding: 10px;
  border-top: 1px solid #dbe4ee;
  color: #68788d;
  font-size: 0.76rem;
  line-height: 1.5;
}
.workspace-sidebar-note p { margin: 6px 0 0; }
.workspace-main { min-width: 0; }
.workspace-view-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.workspace-view-heading h2 { margin: 4px 0 0; color: #1d3555; font-size: 1.35rem; }
.workspace-view-status { max-width: 45%; overflow-wrap: anywhere; color: #7890aa; font-size: 0.8rem; text-align: right; }
.workspace-query { min-width: 0; }
.workspace-placeholder {
  min-height: 390px;
  padding: 28px;
  border: 1px dashed #b8cde3;
  border-radius: 16px;
  background: linear-gradient(135deg, #f8fbff, #f1f6fb);
}
.workspace-placeholder h3 { margin: 8px 0; color: #1d3555; font-size: 1.45rem; }
.workspace-placeholder > p { max-width: 680px; color: #526176; line-height: 1.7; }
.task-history-page { display: grid; gap: 16px; }
.task-history-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 20px; border: 1px solid #d7e3ef; border-radius: 16px; background: #f8fbff; }
.task-history-toolbar h3 { margin: 6px 0 4px; color: #1d3555; font-size: 1.25rem; }
.task-history-toolbar p { margin: 0; color: #68788d; line-height: 1.5; }
.task-filter-bar, .task-batch-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 12px 14px; border: 1px solid #d7e3ef; border-radius: 12px; background: #ffffff; color: #526176; font-size: 0.84rem; }
.task-filter-bar label { display: inline-flex; align-items: center; gap: 7px; font-weight: 700; }
.task-filter-bar select { padding: 7px 9px; font-size: 0.82rem; }
.task-filter-count { margin-left: auto; color: #7890aa; }
.task-batch-toolbar { background: #f8fbff; }
.task-batch-toolbar > span { color: #68788d; }
.task-batch-status { flex: 1 1 260px; color: #315e8c !important; overflow-wrap: anywhere; }
.task-state-card { display: grid; gap: 8px; justify-items: start; padding: 24px; border: 1px dashed #b8cde3; border-radius: 14px; color: #526176; background: #fbfdff; line-height: 1.5; }
.task-state-card strong { color: #1d3555; }
.task-state-error { border-color: #e0a0a0; color: #8b3030; background: #fff5f5; }
.task-history-layout { display: grid; grid-template-columns: minmax(240px, 0.9fr) minmax(0, 1.35fr); align-items: start; gap: 16px; }
.task-record-list { display: grid; gap: 10px; }
.task-record-card { display: grid; gap: 9px; padding: 15px; border: 1px solid #d7e3ef; border-radius: 14px; background: #ffffff; }
.task-record-card.selected { border-color: #6d9dcc; box-shadow: 0 0 0 3px #e8f2fc; }
.task-record-head, .task-record-meta, .task-record-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.task-record-head { justify-content: space-between; color: #7890aa; }
.task-select-control { display: inline-flex; align-items: center; gap: 5px; margin-right: auto; color: #526176; font-size: 0.78rem; font-weight: 700; }
.task-select-control input { flex: 0 0 auto; width: 15px; height: 15px; margin: 0; }
.task-record-card > strong { color: #26384f; line-height: 1.45; }
.task-record-id { color: #7890aa; overflow-wrap: anywhere; }
.task-record-meta { color: #68788d; font-size: 0.8rem; }
.task-record-actions { margin-top: 2px; }
.task-record-actions button { padding: 7px 10px; font-size: 0.82rem; }
.task-status { display: inline-flex; padding: 4px 8px; border-radius: 999px; color: #315e8c; background: #e8f2fc; font-size: 0.75rem; font-weight: 700; }
.task-status-completed { color: #276749; background: #e8f7ee; }
.task-status-insufficient_evidence, .task-status-cancelled { color: #765b00; background: #fff4c2; }
.task-status-failed { color: #9b2c2c; background: #fff0f0; }
.task-detail-card { display: grid; gap: 14px; padding: 20px; border: 1px solid #c8d8ec; border-radius: 16px; background: #ffffff; }
.task-detail-card h3 { margin: 0; color: #1d3555; line-height: 1.4; }
.task-detail-answer { max-height: 360px; overflow: auto; }
.task-detail-section { display: grid; gap: 7px; padding-top: 12px; border-top: 1px solid #e2eaf2; }
.task-detail-section ul { margin: 0; padding-left: 20px; }
.task-detail-section li { color: #526176; overflow-wrap: anywhere; }
.placeholder-grid { display: grid; gap: 10px; margin-top: 24px; }
.placeholder-grid article {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 13px 14px;
  border: 1px solid #d7e3ef;
  border-radius: 12px;
  background: #ffffff;
}
.placeholder-grid article p { margin: 4px 0 0; color: #68788d; font-size: 0.86rem; line-height: 1.5; overflow-wrap: anywhere; }
.placeholder-icon {
  display: inline-flex;
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #315e8c;
  background: #dcecf9;
  font-weight: 800;
}
.context-card {
  padding: 16px;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #fbfdff;
}
.context-card h2 { margin: 4px 0 0; color: #1d3555; font-size: 1.02rem; }
.context-card p { margin: 10px 0 0; color: #68788d; font-size: 0.82rem; line-height: 1.55; }
.context-facts { display: grid; gap: 10px; margin: 16px 0 0; }
.context-facts div { display: grid; gap: 3px; }
.context-facts dt { color: #8b98a8; font-size: 0.72rem; }
.context-facts dd { margin: 0; color: #405673; font-size: 0.82rem; font-weight: 700; overflow-wrap: anywhere; }
.context-stat { display: block; margin-top: 14px; color: #1d568b; font-size: 2rem; line-height: 1; }
.context-source-list { display: grid; gap: 6px; margin-top: 12px; }
.context-source-list span { padding: 7px 8px; border-radius: 8px; color: #526176; background: #f0f6fb; font: 0.72rem/1.4 "SFMono-Regular", Consolas, monospace; overflow-wrap: anywhere; }
.context-safety-card { border-color: #d6c38e; background: #fffaf0; }
.context-safety-card .eyebrow { color: #8a6421; }

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
.login-card-heading { display: grid; gap: 4px; }
.login-card-heading strong { color: #1d3555; font-size: 1.15rem; }
.login-card p { color: #526176; line-height: 1.5; }

.toolbar { margin: 28px 0 16px; color: #526176; font-size: 0.9rem; flex-wrap: wrap; }
.project-picker, .actor-picker { display: flex; align-items: center; gap: 8px; font-weight: 600; }
select { border: 1px solid #cbd6e2; border-radius: 10px; padding: 10px 12px; color: #26384f; background: #ffffff; font: inherit; }
.index-count { margin-left: auto; color: #7890aa; }
.capability-badge { border-radius: 999px; padding: 5px 9px; color: #5b4b82; background: #f0ebff; font-weight: 700; }
.readonly-badge { border-radius: 999px; padding: 5px 9px; color: #315e8c; background: #e3f0fb; font-weight: 700; }
.auth-badge { border-radius: 999px; padding: 5px 9px; color: #24664b; background: #e7f6ee; font-weight: 700; }
.secondary-button { color: #416b98; background: #edf4fb; border: 1px solid #c7d9eb; }
.request-error { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; padding: 12px 14px; border: 1px solid #e0a0a0; border-radius: 12px; color: #8b3030; background: #fff1f1; line-height: 1.5; }
.request-error div { display: grid; gap: 2px; }
.request-error span { font-size: 0.88rem; overflow-wrap: anywhere; }
.agent-progress { display: flex; align-items: center; gap: 10px; margin-top: 12px; padding: 10px 12px; border: 1px solid #c8d8ec; border-radius: 10px; color: #315e8c; background: #f4f8fd; line-height: 1.45; }
.agent-progress small { margin-left: auto; color: #7890aa; }
.agent-cancel-button { flex: 0 0 auto; padding: 7px 10px; }
.agent-progress-spinner { width: 13px; height: 13px; flex: 0 0 auto; border: 2px solid #b9d0e6; border-top-color: #326aa5; border-radius: 50%; animation: agent-progress-spin 0.8s linear infinite; }
@keyframes agent-progress-spin { to { transform: rotate(360deg); } }
.project-mismatch { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; padding: 12px 14px; border: 1px solid #e4c46d; border-radius: 12px; color: #6e5520; background: #fff8df; line-height: 1.5; }
.project-mismatch div { display: grid; gap: 2px; }
.project-mismatch span { font-size: 0.88rem; }
.health-badge { border-radius: 999px; padding: 5px 9px; font-weight: 700; }
.health-checking { color: #765b00; background: #fff4c2; }
.health-online { color: #276749; background: #e8f7ee; }
.health-offline { color: #9b2c2c; background: #fff0f0; }
.health-details { color: #7890aa; font-size: 0.82rem; }
button { border: 0; border-radius: 10px; padding: 10px 14px; color: #ffffff; background: #326aa5; cursor: pointer; font: inherit; font-weight: 600; }
button:disabled { cursor: wait; opacity: 0.6; }
input { flex: 1; min-width: 0; border: 1px solid #cbd6e2; border-radius: 10px; padding: 12px 14px; font: inherit; }
.example-prompts { margin: 12px 0 4px; }
.example-prompts-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; color: #416b98; font-size: 0.86rem; }
.example-prompts-heading span { color: #7890aa; font-size: 0.78rem; }
.example-group-list { display: grid; gap: 10px; }
.example-group { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.example-group-label { display: inline-flex; align-items: center; gap: 6px; min-width: 92px; color: #526176; font-size: 0.8rem; font-weight: 700; }
.example-group-icon { display: inline-flex; width: 22px; height: 22px; align-items: center; justify-content: center; border-radius: 7px; font-size: 0.72rem; font-weight: 800; }
.example-group-icon-troubleshooting { color: #8b5a18; background: #fff0c7; }
.example-group-icon-code { color: #315e8c; background: #dcecf9; }
.example-group-icon-auth { color: #276749; background: #e0f4e8; }
.example-group-icon-vault { color: #6b4e8f; background: #efe6fb; }
.prompt-chip-row { display: flex; flex: 1; min-width: 0; gap: 8px; flex-wrap: wrap; }
.prompt-chip { padding: 8px 11px; border: 1px solid #cbdbea; border-radius: 999px; color: #416b98; background: #f1f6fb; font-size: 0.84rem; text-align: left; }
.prompt-chip:hover { border-color: #8bb5d8; background: #e5f0fa; }
.vault-project-card { margin-top: 14px; padding: 16px 18px; border: 1px solid #cbbbe2; border-radius: 14px; background: linear-gradient(135deg, #fbf8ff, #f2edfb); }
.vault-project-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.vault-project-head h2 { margin: 5px 0 0; color: #4e3c70; font-size: 1.15rem; }
.vault-project-card p { margin: 10px 0; color: #665b7d; line-height: 1.55; }
.vault-project-facts { display: flex; gap: 8px; flex-wrap: wrap; color: #6c5b86; font-size: 0.8rem; }
.vault-project-facts span { padding: 5px 8px; border-radius: 8px; background: rgba(255,255,255,0.72); }
.results { display: grid; gap: 12px; margin-top: 24px; }
.result-card, .answer-card, .report-card { padding: 18px; border-radius: 14px; }
.result-card { border: 1px solid #d7e0ea; background: #f8fbfd; }
.answer-card { border: 1px solid #8bb5d8; background: #eef7ff; }
.feedback-card { padding: 16px 18px; border: 1px solid #c8d8ec; border-radius: 14px; background: #f8fbff; }
.feedback-actions, .feedback-submit-row { display: flex; gap: 9px; flex-wrap: wrap; margin-top: 12px; }
.feedback-actions .feedback-selected { color: #ffffff; border-color: #315e8c; background: #315e8c; }
.feedback-fieldset { display: grid; gap: 7px; margin: 14px 0 0; padding: 10px 12px; border: 1px solid #d7e3ef; border-radius: 10px; }
.feedback-fieldset legend { padding: 0 5px; color: #526176; font-size: 0.86rem; font-weight: 700; }
.feedback-citation-option { display: flex; align-items: flex-start; gap: 8px; color: #526176; font-size: 0.84rem; line-height: 1.45; }
.feedback-citation-option input { flex: 0 0 auto; width: 15px; height: 15px; margin: 3px 0 0; }
.feedback-submit-row button { background: #315e8c; }
.feedback-status { display: block; margin-top: 10px; color: #416b98; line-height: 1.5; }
.report-card { border: 1px solid #b9d8c5; background: #f3fbf5; }
.writeback-card { border: 1px solid #d6c38e; background: #fffaf0; }
.code-writeback-card { border: 1px solid #c5b6dd; background: #faf7ff; }
.issue-writeback-card { border: 1px solid #b7c9e5; background: #f4f8ff; }
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
.answer-card { padding: 22px; box-shadow: 0 10px 28px rgba(49, 94, 140, 0.08); }
.answer-card > .result-meta strong { color: #1d568b; font-size: 1rem; }
.generation-status { display: inline-flex; width: fit-content; margin: 12px 0 2px; padding: 5px 9px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }
.generation-ai { color: #276749; background: #e1f5e9; }
.generation-offline_rules { color: #315e8c; background: #dcecf9; }
.generation-offline_fallback { color: #8a5b16; background: #fff0c7; }
.generation-guarded { color: #8b3a3a; background: #ffe3e3; }
.generation-warning { display: block; margin-top: 8px; color: #8a5b16; line-height: 1.5; }
.key-steps { margin-top: 20px; padding-top: 16px; border-top: 1px solid #c8deef; }
.subsection-heading { display: flex; align-items: baseline; gap: 10px; }
.subsection-heading .eyebrow { margin: 0; font-size: 0.7rem; }
.subsection-heading h3 { margin: 0; color: #1d3555; font-size: 1rem; }
.key-step-list { display: grid; gap: 8px; margin: 12px 0 0; padding: 0; list-style: none; }
.key-step-list li { display: flex; align-items: flex-start; gap: 10px; margin: 0; padding: 10px 12px; border-radius: 10px; color: #405673; background: rgba(255,255,255,0.72); line-height: 1.55; }
.key-step-number { display: inline-flex; flex: 0 0 auto; width: 22px; height: 22px; align-items: center; justify-content: center; border-radius: 50%; color: #ffffff; background: #4e83b5; font-size: 0.78rem; font-weight: 800; }
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
.field-help { color: #8b98a8; font-size: 0.78rem; font-weight: 400; }
.locked-state { margin: 14px 0; padding: 12px 14px; border-radius: 10px; color: #6e5b2a; background: #fff7dc; line-height: 1.5; }
.locked-writeback-card { padding: 14px 16px; border: 1px dashed #b7c9e5; border-radius: 14px; color: #526176; background: #f7faff; }
.locked-writeback-card summary { cursor: pointer; font-weight: 700; color: #416b98; }
.status-pill { border-radius: 999px; padding: 4px 8px; color: #315e8c; background: #dcecf9; font-size: 0.78rem; font-weight: 700; }
.issue-preview-summary { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 12px; color: #526176; font-size: 0.88rem; }
.issue-preview-summary a { color: #1f65a6; font-weight: 700; }
.field-label { display: grid; gap: 6px; margin-top: 12px; color: #526176; font-size: 0.88rem; font-weight: 600; }
.field-label textarea { resize: vertical; border: 1px solid #cbd6e2; border-radius: 10px; padding: 12px 14px; font: inherit; line-height: 1.5; }
.writeback-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.writeback-actions button:last-child { background: #8a6421; }
.writeback-status { display: block; margin-top: 10px; color: #6a541d; }
.diff-summary { margin-top: 14px; }
.diff-summary pre { max-height: 240px; overflow: auto; padding: 12px; border-radius: 10px; background: #29261f; color: #f8edc7; white-space: pre-wrap; font: 0.82rem/1.5 "SFMono-Regular", Consolas, monospace; }
.empty-state { color: #6c7b8f; text-align: center; }
.evidence-section { margin-top: 4px; padding-top: 4px; }
.section-heading { display: flex; align-items: end; justify-content: space-between; gap: 12px; margin: 18px 0 10px; color: #6c7b8f; }
.section-heading h2 { margin: 3px 0 0; color: #1d3555; font-size: 1.35rem; }
.section-heading .eyebrow { margin: 0; font-size: 0.72rem; }
.evidence-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; }
.evidence-card { min-width: 0; padding: 16px; border: 1px solid #d7e0ea; border-radius: 14px; background: #f8fbfd; }
.evidence-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.evidence-score { color: #6b7f95; font: 0.8rem "SFMono-Regular", Consolas, monospace; }
.evidence-path { display: block; margin-top: 12px; color: #294a70; overflow-wrap: anywhere; }
.evidence-citation { display: block; margin-top: 4px; color: #7890aa; }
.evidence-markdown { margin-top: 10px; font-size: 0.92rem; }
.evidence-markdown pre { max-height: 220px; }
.matched-terms { display: block; margin-top: 12px; color: #7890aa; }
li { margin: 8px 0; line-height: 1.5; }

@media (max-width: 1120px) {
  .workspace-layout { grid-template-columns: 176px minmax(0, 1fr); }
  .workspace-inspector { grid-column: 2; position: static; grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 760px) {
  .page-shell { padding: 12px; }
  .hero-card { padding: 22px 18px; border-radius: 18px; }
  .workspace-layout { grid-template-columns: 1fr; gap: 14px; }
  .workspace-sidebar, .workspace-inspector { position: static; grid-column: auto; }
  .workspace-nav { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workspace-inspector { grid-template-columns: 1fr; }
  .workspace-view-heading { align-items: flex-start; flex-direction: column; }
  .workspace-view-status { max-width: 100%; text-align: left; }
  .workspace-placeholder { min-height: 0; padding: 20px; }
  .task-history-layout { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .search-box { align-items: stretch; flex-direction: column; }
  .search-box button { width: 100%; }
  .request-error { align-items: stretch; flex-direction: column; }
  .task-history-toolbar { align-items: stretch; flex-direction: column; }
  .agent-progress { align-items: flex-start; flex-wrap: wrap; }
  .agent-progress small { width: 100%; margin-left: 23px; }
  .agent-cancel-button { margin-left: 23px; }
  .project-mismatch { align-items: stretch; flex-direction: column; }
  .index-count { margin-left: 0; width: 100%; }
  .evidence-grid { grid-template-columns: 1fr; }
  .section-heading { align-items: start; flex-direction: column; }
}
</style>
