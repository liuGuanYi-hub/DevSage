"""State objects for the finite-state Agent runner.

The state is deliberately JSON-serializable so the local runner can later be
replaced by a durable graph runtime without changing the public contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ingestion.models import ChunkRecord
from ..retrieval.models import SearchResult
from ..services.answer_service import AnswerDraft
from .classifier import QUESTION_CATEGORIES


@dataclass(frozen=True)
class AgentStep:
    name: str
    status: str
    detail: str


@dataclass
class AgentState:
    task_id: str
    query: str
    source_root: str
    category: str = "knowledge_qa"
    status: str = "running"
    steps: list[AgentStep] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    evidence: list[SearchResult] = field(default_factory=list)
    answer: object | None = None

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

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot without runtime-only objects."""

        return {
            "task_id": self.task_id,
            "query": self.query,
            "source_root": self.source_root,
            "category": self.category,
            "status": self.status,
            "steps": [
                {"name": step.name, "status": step.status, "detail": step.detail}
                for step in self.steps
            ],
            "tool_calls": list(self.tool_calls),
            "evidence": [_serialize_search_result(result) for result in self.evidence],
            "answer": _serialize_answer(self.answer),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentState":
        """Restore a state snapshot produced by :meth:`to_dict`."""

        state = cls(
            task_id=str(payload["task_id"]),
            query=str(payload["query"]),
            source_root=str(payload["source_root"]),
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
        )
        state.set_category(state.category)
        state.answer = _deserialize_answer(payload.get("answer"))
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
    )
