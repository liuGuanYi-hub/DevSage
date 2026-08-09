export interface IndexResponse {
  source_root: string;
  document_count: number;
  chunk_count: number;
  added_documents: number;
  changed_documents: number;
  unchanged_documents: number;
  removed_documents: number;
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

export function getAuthToken(): string {
  return authToken;
}

export function setAuthToken(token: string): void {
  authToken = token;
}

async function request<T>(path: string, options: RequestInit, actorId?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (actorId) {
    headers.set("X-DevSage-Actor", actorId);
  }
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
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
  }, actorId);
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
