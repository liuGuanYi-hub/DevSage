"""State objects for the finite-state Agent runner."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..retrieval.models import SearchResult
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

