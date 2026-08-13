export interface IndexResponse {
  source_root: string;
  document_count: number;
  chunk_count: number;
  added_documents: number;
  changed_documents: number;
  unchanged_documents: number;
  removed_documents: number;
}

export interface IndexStatusResponse {
  source_root: string;
  document_count: number;
  chunk_count: number;
  indexed: boolean;
}

export interface HealthResponse {
  status: string;
  service?: string;
  storage?: string;
  embedding_provider?: string;
  external_issue_configured?: boolean;
  external_issue_write_enabled?: boolean;
  auth_enabled?: boolean;
  cache?: string;
  answer_generation_provider?: string;
  answer_generation_model?: string;
  answer_generation_configured?: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
  actor_id: string;
}

export interface ProjectRole {
  role: string;
  actions: string[];
}

export interface ProjectMember {
  actor_id: string;
  role: string;
  actions: string[];
}

export interface Project {
  project_id: string;
  name: string;
  source_root: string;
  description: string;
  source_kind: string;
  read_only: boolean;
  roles: ProjectRole[];
  members: ProjectMember[];
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
}

export interface SearchHit {
  citation: string;
  source_path: string;
  start_line: number;
  end_line: number;
  score: number;
  matched_terms: string[];
  content: string;
}

export interface SearchResponse {
  query: string;
  source_root: string;
  results: SearchHit[];
}

export interface AnswerResponse {
  query: string;
  source_root: string;
  answer: string;
  citations: string[];
  evidence: SearchHit[];
  evidence_sufficient: boolean;
  warning: string | null;
  generation_mode: string;
  generation_model: string | null;
  generation_warning: string | null;
  generation_runtime_ms: number;
}

export interface AgentStep {
  name: string;
  status: string;
  detail: string;
}

export interface AgentUsage {
  query_tokens: number;
  evidence_tokens: number;
  answer_tokens: number;
  total_token_estimate: number;
  tool_calls: number;
  tool_retries: number;
  runtime_ms: number;
}

export interface TroubleshootingFinding {
  source_type: string;
  citations: string[];
  snippets: string[];
}

export interface TroubleshootingReport {
  query: string;
  summary: string;
  findings: TroubleshootingFinding[];
  next_steps: string[];
  citations: string[];
  evidence_sufficient: boolean;
}

export interface AgentResponse extends AnswerResponse {
  task_id: string;
  project_id: string | null;
  category: string;
  status: string;
  tool_calls: string[];
  tool_retry_count: number;
  steps: AgentStep[];
  report: TroubleshootingReport | null;
  usage: AgentUsage;
  key_steps: string[];
}

export interface AgentTaskSummary {
  task_id: string;
  query: string;
  source_root: string;
  project_id: string | null;
  category: string;
  status: string;
  tool_calls: number;
  step_count: number;
  runtime_ms: number;
  evidence_count: number;
  resumable: boolean;
}

export interface AgentTaskListResponse {
  items: AgentTaskSummary[];
  total: number;
}

export interface AgentProgressEvent {
  task_id: string;
  status: string;
  step: AgentStep;
  completed_steps: number;
  tool_calls: number;
}

export class AgentStreamCancelledError extends Error {
  constructor() {
    super("已取消本次 Agent 检索");
    this.name = "AgentStreamCancelledError";
  }
}

export function isAgentStreamCancelled(error: unknown): error is AgentStreamCancelledError {
  return error instanceof AgentStreamCancelledError;
}

export interface KnowledgeNoteDiff {
  operation: string;
  target_exists: boolean;
  current_content_hash: string | null;
  proposed_content_hash: string;
  additions: number;
  deletions: number;
  unified_diff: string[];
}

export interface KnowledgeNotePreview {
  preview_id: string;
  title: string;
  target_path: string;
  content: string;
  source_citations: string[];
  diff: KnowledgeNoteDiff;
  status: string;
}

export interface CodeChangeDiff {
  operation: string;
  current_content_hash: string;
  proposed_content_hash: string;
  additions: number;
  deletions: number;
  unified_diff: string[];
}

export interface CodeChangePreview {
  preview_id: string;
  source_root: string;
  target_path: string;
  proposed_content: string;
  source_citations: string[];
  diff: CodeChangeDiff;
  status: string;
}

export interface IssueWritePreview {
  preview_id: string;
  project_id: string | null;
  title: string;
  body: string;
  labels: string[];
  status: string;
  remote_number: string | null;
  remote_url: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
let authToken = "";

const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;
const INDEX_REQUEST_TIMEOUT_MS = 60_000;
const AGENT_REQUEST_TIMEOUT_MS = 45_000;

export function getAuthToken(): string {
  return authToken;
}

export function setAuthToken(token: string): void {
  authToken = token;
}

async function request<T>(
  path: string,
  options: RequestInit,
  actorId?: string,
  timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (actorId) {
    headers.set("X-DevSage-Actor", actorId);
  }
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (!response.ok) {
      const responseText = await response.text();
      let detail = responseText.trim();
      try {
        const payload = JSON.parse(responseText) as { detail?: string; message?: string };
        detail = payload.detail ?? payload.message ?? detail;
      } catch {
        // Keep the plain response text when the server did not return JSON.
      }
      throw new Error(detail || `请求失败（HTTP ${response.status}）`);
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`请求超时（${Math.round(timeoutMs / 1000)} 秒），请检查后端服务后重试`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function listProjects(): Promise<ProjectListResponse> {
  return request<ProjectListResponse>("/api/projects", {
    method: "GET",
  });
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", {
    method: "GET",
  });
}

export function indexSource(
  sourceRoot = "sample-data",
  projectId?: string,
  actorId?: string,
): Promise<IndexResponse> {
  return request<IndexResponse>("/api/index", {
    method: "POST",
    body: JSON.stringify({ source_root: sourceRoot, project_id: projectId }),
  }, actorId, INDEX_REQUEST_TIMEOUT_MS);
}

export function getIndexStatus(projectId: string, actorId?: string): Promise<IndexStatusResponse> {
  return request<IndexStatusResponse>(`/api/projects/${projectId}/index-status`, {
    method: "GET",
  }, actorId);
}

export function searchEvidence(
  query: string,
  sourceRoot = "sample-data",
  topK = 5,
  projectId?: string,
  actorId?: string,
): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({ query, source_root: sourceRoot, top_k: topK, project_id: projectId }),
  }, actorId);
}

export function answerQuestion(
  query: string,
  sourceRoot = "sample-data",
  topK = 5,
  projectId?: string,
  actorId?: string,
): Promise<AnswerResponse> {
  return request<AnswerResponse>("/api/answer", {
    method: "POST",
    body: JSON.stringify({ query, source_root: sourceRoot, top_k: topK, project_id: projectId }),
  }, actorId);
}

export function runAgent(
  query: string,
  sourceRoot = "sample-data",
  topK = 5,
  projectId?: string,
  actorId?: string,
): Promise<AgentResponse> {
  return request<AgentResponse>("/api/agent/run", {
    method: "POST",
    body: JSON.stringify({ query, source_root: sourceRoot, top_k: topK, project_id: projectId }),
  }, actorId, AGENT_REQUEST_TIMEOUT_MS);
}

export function listAgentTasks(
  projectId?: string,
  limit = 50,
  actorId?: string,
): Promise<AgentTaskListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (projectId) params.set("project_id", projectId);
  return request<AgentTaskListResponse>(`/api/agent/tasks?${params.toString()}`, {
    method: "GET",
  }, actorId);
}

export function getAgentTask(taskId: string, actorId?: string): Promise<AgentResponse> {
  return request<AgentResponse>(`/api/agent/tasks/${encodeURIComponent(taskId)}`, {
    method: "GET",
  }, actorId, AGENT_REQUEST_TIMEOUT_MS);
}

export function resumeAgentTask(
  taskId: string,
  topK = 5,
  actorId?: string,
): Promise<AgentResponse> {
  return request<AgentResponse>(`/api/agent/tasks/${encodeURIComponent(taskId)}/resume`, {
    method: "POST",
    body: JSON.stringify({ top_k: topK }),
  }, actorId, AGENT_REQUEST_TIMEOUT_MS);
}

interface AgentStreamOptions {
  signal?: AbortSignal;
  onProgress?: (event: AgentProgressEvent) => void;
}

async function consumeSse(
  response: Response,
  onEvent: (eventName: string, data: string) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error("后端没有返回 Agent 任务流");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flushBlock = (block: string) => {
    const lines = block.split(/\r?\n/);
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }
    if (dataLines.length) onEvent(eventName, dataLines.join("\n"));
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        flushBlock(buffer.slice(0, boundary).replace(/\r$/, ""));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    if (buffer.trim()) flushBlock(buffer);
  } finally {
    reader.releaseLock();
  }
}

export function streamAgent(
  query: string,
  sourceRoot = "sample-data",
  topK = 5,
  projectId?: string,
  actorId?: string,
  options: AgentStreamOptions = {},
): Promise<AgentResponse> {
  const controller = new AbortController();
  const externalSignal = options.signal;
  let externallyCancelled = Boolean(externalSignal?.aborted);
  const abortExternal = () => {
    externallyCancelled = true;
    controller.abort();
  };
  externalSignal?.addEventListener("abort", abortExternal, { once: true });
  const timeoutHandle = window.setTimeout(() => controller.abort(), AGENT_REQUEST_TIMEOUT_MS);

  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (actorId) headers.set("X-DevSage-Actor", actorId);
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  return (async () => {
    try {
      if (externallyCancelled) throw new AgentStreamCancelledError();
      const response = await fetch(`${API_BASE_URL}/api/agent/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          query,
          source_root: sourceRoot,
          top_k: topK,
          project_id: projectId,
          persist: true,
        }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const responseText = await response.text();
        let detail = responseText.trim();
        try {
          const payload = JSON.parse(responseText) as { detail?: string; message?: string };
          detail = payload.detail ?? payload.message ?? detail;
        } catch {
          // Keep the plain response text when the server did not return JSON.
        }
        throw new Error(detail || `请求失败（HTTP ${response.status}）`);
      }

      let finalResponse: AgentResponse | null = null;
      await consumeSse(response, (eventName, data) => {
        if (eventName === "progress") {
          options.onProgress?.(JSON.parse(data) as AgentProgressEvent);
          return;
        }
        if (eventName === "error") {
          const payload = JSON.parse(data) as { detail?: string };
          throw new Error(payload.detail || "Agent 任务执行失败");
        }
        if (eventName === "done") {
          finalResponse = JSON.parse(data) as AgentResponse;
        }
      });
      if (!finalResponse) {
        throw new Error("Agent 任务流意外中断，未收到最终答案");
      }
      return finalResponse;
    } catch (error) {
      if (externallyCancelled || externalSignal?.aborted) {
        throw new AgentStreamCancelledError();
      }
      if (controller.signal.aborted) {
        throw new Error("Agent 任务超时，请稍后重试");
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutHandle);
      externalSignal?.removeEventListener("abort", abortExternal);
    }
  })();
}

export function previewKnowledgeNote(
  title: string,
  content: string,
  targetPath: string,
  sourceCitations: string[],
  projectId?: string,
  actorId?: string,
): Promise<KnowledgeNotePreview> {
  return request<KnowledgeNotePreview>("/api/knowledge-notes/preview", {
    method: "POST",
    body: JSON.stringify({
      title,
      content,
      target_path: targetPath,
      source_citations: sourceCitations,
      project_id: projectId,
    }),
  }, actorId);
}

export function approveKnowledgeNote(previewId: string, actorId?: string): Promise<KnowledgeNotePreview> {
  return request<KnowledgeNotePreview>(`/api/knowledge-notes/${previewId}/approve`, {
    method: "POST",
  }, actorId);
}

export function previewCodeChange(
  targetPath: string,
  proposedContent: string,
  sourceCitations: string[],
  sourceRoot = "sample-data",
  projectId?: string,
  actorId?: string,
): Promise<CodeChangePreview> {
  return request<CodeChangePreview>("/api/code-changes/preview", {
    method: "POST",
    body: JSON.stringify({
      target_path: targetPath,
      proposed_content: proposedContent,
      source_citations: sourceCitations,
      source_root: sourceRoot,
      project_id: projectId,
    }),
  }, actorId);
}

export function approveCodeChange(previewId: string, actorId?: string): Promise<CodeChangePreview> {
  return request<CodeChangePreview>(`/api/code-changes/${previewId}/approve`, {
    method: "POST",
  }, actorId);
}

export function previewIssueWrite(
  title: string,
  body: string,
  labels: string[],
  projectId?: string,
  actorId?: string,
): Promise<IssueWritePreview> {
  return request<IssueWritePreview>("/api/issues/preview", {
    method: "POST",
    body: JSON.stringify({ title, body, labels, project_id: projectId }),
  }, actorId);
}

export function approveIssueWrite(previewId: string, actorId?: string): Promise<IssueWritePreview> {
  return request<IssueWritePreview>(`/api/issues/${previewId}/approve`, {
    method: "POST",
  }, actorId);
}
