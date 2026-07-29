"""Pydantic request and response models for the stage-1 API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IndexRequest(BaseModel):
    source_root: str = Field(default="sample-data", min_length=1)
    project_id: str | None = Field(default=None, min_length=1)


class IndexResponse(BaseModel):
    source_root: str
    document_count: int
    chunk_count: int
    added_documents: int
    changed_documents: int
    unchanged_documents: int
    removed_documents: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    source_root: str = Field(default="sample-data", min_length=1)
    project_id: str | None = Field(default=None, min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    citation: str
    source_path: str
    start_line: int
    end_line: int
    score: float
    matched_terms: list[str]
    content: str


class SearchResponse(BaseModel):
    query: str
    source_root: str
    results: list[SearchHit]


class AnswerRequest(SearchRequest):
    pass


class AnswerResponse(BaseModel):
    query: str
    source_root: str
    answer: str
    citations: list[str]
    evidence: list[SearchHit]
    evidence_sufficient: bool
    warning: str | None = None


class KnowledgeNotePreviewRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    source_citations: list[str] = Field(default_factory=list)
    project_id: str | None = Field(default=None, min_length=1)


class KnowledgeNoteDiffResponse(BaseModel):
    operation: str
    target_exists: bool
    current_content_hash: str | None
    proposed_content_hash: str
    additions: int
    deletions: int
    unified_diff: list[str]


class KnowledgeNotePreviewResponse(BaseModel):
    preview_id: str
    title: str
    target_path: str
    content: str
    source_citations: list[str]
    diff: KnowledgeNoteDiffResponse
    status: str
