export interface IndexResponse {
  source_root: string;
  document_count: number;
  chunk_count: number;
  added_documents: number;
  changed_documents: number;
  unchanged_documents: number;
  removed_documents: number;
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
  category: string;
  status: string;
  tool_calls: string[];
  tool_retry_count: number;
  steps: AgentStep[];
  report: TroubleshootingReport | null;
  usage: AgentUsage;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function indexSource(sourceRoot = "sample-data"): Promise<IndexResponse> {
  return request<IndexResponse>("/api/index", {
    method: "POST",
    body: JSON.stringify({ source_root: sourceRoot }),
  });
}

export function searchEvidence(
  query: string,
  sourceRoot = "sample-data",
  topK = 5,
): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({ query, source_root: sourceRoot, top_k: topK }),
  });
}

export function answerQuestion(
  query: string,
  sourceRoot = "sample-data",
  topK = 5,
): Promise<AnswerResponse> {
  return request<AnswerResponse>("/api/answer", {
    method: "POST",
    body: JSON.stringify({ query, source_root: sourceRoot, top_k: topK }),
  });
}

export function runAgent(
  query: string,
  sourceRoot = "sample-data",
  topK = 5,
): Promise<AgentResponse> {
  return request<AgentResponse>("/api/agent/run", {
    method: "POST",
    body: JSON.stringify({ query, source_root: sourceRoot, top_k: topK }),
  });
}
