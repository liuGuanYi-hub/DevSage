"""API contracts for approved code-file changes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CodeChangePreviewRequest(BaseModel):
    source_root: str = Field(default="sample-data", min_length=1)
    project_id: str | None = Field(default=None, min_length=1)
    target_path: str = Field(min_length=1)
    proposed_content: str
    source_citations: list[str] = Field(default_factory=list)


class CodeChangeDiffResponse(BaseModel):
    operation: str
    current_content_hash: str
    proposed_content_hash: str
    additions: int
    deletions: int
    unified_diff: list[str]


class CodeChangePreviewResponse(BaseModel):
    preview_id: str
    source_root: str
    target_path: str
    proposed_content: str
    source_citations: list[str]
    diff: CodeChangeDiffResponse
    status: str
