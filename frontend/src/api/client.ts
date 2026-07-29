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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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

