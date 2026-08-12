"""State objects for the finite-state Agent runner.

The state is deliberately JSON-serializable so the local runner can later be
replaced by a durable graph runtime without changing the public contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ingestion.models import ChunkRecord
from ..retrieval.keyword_search import tokenize
from ..retrieval.models import SearchResult
from ..services.answer_service import AnswerDraft
from .classifier import QUESTION_CATEGORIES


@dataclass(frozen=True)
class AgentStep:
    name: str
    status: str
    detail: str


@dataclass
class AgentUsage:
    """Explainable offline usage counters, not provider billing data."""

    query_tokens: int = 0
    evidence_tokens: int = 0
    answer_tokens: int = 0
    tool_calls: int = 0
    tool_retries: int = 0
    runtime_ms: int = 0

    @property
    def total_token_estimate(self) -> int:
        return self.query_tokens + self.evidence_tokens + self.answer_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "query_tokens": self.query_tokens,
            "evidence_tokens": self.evidence_tokens,
            "answer_tokens": self.answer_tokens,
            "total_token_estimate": self.total_token_estimate,
            "tool_calls": self.tool_calls,
            "tool_retries": self.tool_retries,
            "runtime_ms": self.runtime_ms,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "AgentUsage":
        if not payload:
            return cls()
        return cls(
            query_tokens=int(payload.get("query_tokens", 0)),
            evidence_tokens=int(payload.get("evidence_tokens", 0)),
            answer_tokens=int(payload.get("answer_tokens", 0)),
            tool_calls=int(payload.get("tool_calls", 0)),
            tool_retries=int(payload.get("tool_retries", 0)),
            runtime_ms=int(payload.get("runtime_ms", 0)),
        )


@dataclass
class AgentState:
    task_id: str
    query: str
    source_root: str
    project_id: str | None = None
    category: str = "knowledge_qa"
    status: str = "running"
    steps: list[AgentStep] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    evidence: list[SearchResult] = field(default_factory=list)
    answer: object | None = None
    rewritten_query: str | None = None
    retry_count: int = 0
    tool_retry_count: int = 0
    usage: AgentUsage = field(default_factory=AgentUsage)

    def set_category(self, category: str) -> None:
        if category not in QUESTION_CATEGORIES:
            raise ValueError(f"unsupported category: {category}")
        self.category = category

    def record_tool_call(self, tool_name: str, limit: int) -> bool:
        """Record a tool call when the bounded execution budget allows it."""

        if limit <= 0 or len(self.tool_calls) >= limit:
            return False
        self.tool_calls.append(tool_name)
        return True

    def refresh_usage(self) -> None:
        """Refresh deterministic token and tool counters from current state."""

        self.usage.query_tokens = len(tokenize(self.query))
        self.usage.evidence_tokens = sum(
            len(tokenize(result.chunk.content)) for result in self.evidence
        )
        self.usage.answer_tokens = (
            len(tokenize(self.answer.answer))
            if isinstance(self.answer, AnswerDraft)
            else 0
        )
        self.usage.tool_calls = len(self.tool_calls)
        self.usage.tool_retries = self.tool_retry_count

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot without runtime-only objects."""

        return {
            "task_id": self.task_id,
            "query": self.query,
            "source_root": self.source_root,
            "project_id": self.project_id,
            "category": self.category,
            "status": self.status,
            "steps": [
                {"name": step.name, "status": step.status, "detail": step.detail}
                for step in self.steps
            ],
            "tool_calls": list(self.tool_calls),
            "evidence": [_serialize_search_result(result) for result in self.evidence],
            "answer": _serialize_answer(self.answer),
            "rewritten_query": self.rewritten_query,
            "retry_count": self.retry_count,
            "tool_retry_count": self.tool_retry_count,
            "usage": self.usage.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentState":
        """Restore a state snapshot produced by :meth:`to_dict`."""

        state = cls(
            task_id=str(payload["task_id"]),
            query=str(payload["query"]),
            source_root=str(payload["source_root"]),
            project_id=(str(payload["project_id"]) if payload.get("project_id") else None),
            category=str(payload.get("category", "knowledge_qa")),
            status=str(payload.get("status", "running")),
            steps=[
                AgentStep(
                    name=str(item["name"]),
                    status=str(item["status"]),
                    detail=str(item.get("detail", "")),
                )
                for item in payload.get("steps", [])
            ],
            tool_calls=[str(item) for item in payload.get("tool_calls", [])],
            evidence=[_deserialize_search_result(item) for item in payload.get("evidence", [])],
            usage=AgentUsage.from_dict(payload.get("usage")),
        )
        state.set_category(state.category)
        state.answer = _deserialize_answer(payload.get("answer"))
        state.rewritten_query = payload.get("rewritten_query")
        state.retry_count = int(payload.get("retry_count", 0))
        state.tool_retry_count = int(payload.get("tool_retry_count", 0))
        if "usage" not in payload:
            state.refresh_usage()
        return state


def _serialize_search_result(result: SearchResult) -> dict[str, Any]:
    chunk = result.chunk
    return {
        "score": result.score,
        "matched_terms": list(result.matched_terms),
        "chunk": {
            "chunk_id": chunk.chunk_id,
            "source_path": chunk.source_path,
            "file_type": chunk.file_type,
            "content": chunk.content,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "metadata": dict(chunk.metadata),
        },
    }


def _deserialize_search_result(payload: dict[str, Any]) -> SearchResult:
    chunk_payload = payload["chunk"]
    chunk = ChunkRecord(
        chunk_id=str(chunk_payload["chunk_id"]),
        source_path=str(chunk_payload["source_path"]),
        file_type=str(chunk_payload["file_type"]),
        content=str(chunk_payload["content"]),
        start_line=int(chunk_payload["start_line"]),
        end_line=int(chunk_payload["end_line"]),
        metadata={str(key): str(value) for key, value in chunk_payload.get("metadata", {}).items()},
    )
    return SearchResult(
        chunk=chunk,
        score=float(payload["score"]),
        matched_terms=tuple(str(item) for item in payload.get("matched_terms", [])),
    )


def _serialize_answer(answer: object | None) -> dict[str, Any] | None:
    if not isinstance(answer, AnswerDraft):
        return None
    return {
        "answer": answer.answer,
        "citations": list(answer.citations),
        "evidence": [_serialize_search_result(result) for result in answer.evidence],
        "evidence_sufficient": answer.evidence_sufficient,
        "warning": answer.warning,
        "key_steps": list(answer.key_steps),
        "generation_mode": answer.generation_mode,
        "generation_model": answer.generation_model,
        "generation_warning": answer.generation_warning,
        "generation_runtime_ms": answer.generation_runtime_ms,
    }


def _deserialize_answer(payload: dict[str, Any] | None) -> AnswerDraft | None:
    if not payload:
        return None
    return AnswerDraft(
        answer=str(payload["answer"]),
        citations=tuple(str(item) for item in payload.get("citations", [])),
        evidence=tuple(_deserialize_search_result(item) for item in payload.get("evidence", [])),
        evidence_sufficient=bool(payload.get("evidence_sufficient", False)),
        warning=payload.get("warning"),
        key_steps=tuple(str(item) for item in payload.get("key_steps", [])),
        generation_mode=str(payload.get("generation_mode", "offline_rules")),
        generation_model=(
            str(payload["generation_model"])
            if payload.get("generation_model")
            else None
        ),
        generation_warning=payload.get("generation_warning"),
        generation_runtime_ms=int(payload.get("generation_runtime_ms", 0)),
    )
