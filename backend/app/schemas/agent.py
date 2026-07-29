"""API contracts for finite-state Agent tasks."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .search import SearchHit


class AgentRequest(BaseModel):
    query: str = Field(min_length=1)
    source_root: str = Field(default="sample-data", min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    persist: bool = False


class AgentResumeRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)


class AgentStepResponse(BaseModel):
    name: str
    status: str
    detail: str


class TroubleshootingFindingResponse(BaseModel):
    source_type: str
    citations: list[str]
    snippets: list[str]


class TroubleshootingReportResponse(BaseModel):
    query: str
    summary: str
    findings: list[TroubleshootingFindingResponse]
    next_steps: list[str]
    citations: list[str]
    evidence_sufficient: bool


class AgentResponse(BaseModel):
    task_id: str
    query: str
    source_root: str
    category: str
    status: str
    answer: str
    citations: list[str]
    evidence_sufficient: bool
    warning: str | None = None
    tool_calls: list[str]
    steps: list[AgentStepResponse]
    evidence: list[SearchHit]
    report: TroubleshootingReportResponse | None = None
