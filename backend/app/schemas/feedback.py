"""Answer feedback and human-reviewed citation correction contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CitationCorrection(BaseModel):
    citation: str = Field(min_length=1, max_length=500)
    corrected_citation: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=1000)


class AnswerFeedbackRequest(BaseModel):
    task_id: str = Field(min_length=8, max_length=64)
    project_id: str | None = Field(default=None, min_length=1)
    query: str = Field(min_length=1, max_length=2000)
    rating: Literal["helpful", "needs_revision"]
    comment: str = Field(default="", max_length=4000)
    incorrect_citations: list[str] = Field(default_factory=list, max_length=20)
    citation_corrections: list[CitationCorrection] = Field(default_factory=list, max_length=20)


class AnswerFeedbackResponse(BaseModel):
    feedback_id: str
    task_id: str
    project_id: str | None = None
    rating: str
    status: str
    created_at: str
    reviewed_at: str | None = None
    evaluation_case_id: str | None = None


class FeedbackListResponse(BaseModel):
    items: list[AnswerFeedbackResponse]
    total: int


class FeedbackApprovalRequest(BaseModel):
    reference_answer: str = Field(min_length=1, max_length=8000)
    expected_sources: list[str] = Field(min_length=1, max_length=20)
    expected_tools: list[str] = Field(min_length=1, max_length=20)
    reviewer_comment: str = Field(default="", max_length=4000)


class FeedbackApprovalResponse(AnswerFeedbackResponse):
    reviewed_by: str
    evaluation_case_id: str
