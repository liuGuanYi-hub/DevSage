"""Bounded, deterministic multi-tool Agent runner for the DevMind MVP."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from ..services.answer_service import compose_evidence_answer
from ..services.index_service import IndexService, SourceRootError
from ..services.project_summary import compose_project_summary
from ..services.knowledge_writeback import KnowledgeWritebackService
from .classifier import classify_question
from .git_tools import GitToolError, get_commit_diff, get_git_history
from .graph import AgentGraph, AgentLimits
from .issue_tools import IssueToolError, search_issues
from .query_rewrite import rewrite_query
from .state import AgentState, AgentStep
from ..services.task_store import TaskNotResumableError


class AgentRunner:
    """Run an observable graph until evidence is sufficient or exhausted."""

    def __init__(
        self,
        index_service: IndexService,
        max_tool_calls: int = 4,
        max_steps: int = 12,
        max_retries: int = 1,
        max_runtime_seconds: float | None = 30.0,
        writeback_service: KnowledgeWritebackService | None = None,
    ) -> None:
        self.index_service = index_service
        self.max_tool_calls = max_tool_calls
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.max_runtime_seconds = max_runtime_seconds
        self.writeback_service = writeback_service or KnowledgeWritebackService(
            Path(
                os.getenv("DEVSAGE_PROJECT_ROOT", str(Path(__file__).resolve().parents[3]))
            ).resolve()
            / "data"
            / "approved-notes"
        )
        self.graph = AgentGraph(
            nodes={
                "classify_question": self._classify_node,
                "retrieve_evidence": self._retrieve_node,
                "evidence_check": self._evidence_node,
                "compose_answer": self._compose_node,
            },
            transitions={},
            limits=AgentLimits(
                max_steps=max_steps,
                max_tool_calls=max_tool_calls,
                max_runtime_seconds=max_runtime_seconds,
            ),
        )

    def run(self, query: str, source_root: str, top_k: int = 5) -> AgentState:
        state = AgentState(uuid4().hex, query, source_root)
        try:
            self.graph.run(state, {"top_k": top_k})
        except (SourceRootError, GitToolError, IssueToolError):
            state.status = "failed"
            state.steps.append(AgentStep("retrieve_evidence", "failed", "invalid source root or tool input"))
            raise
        if state.answer is None and state.status in {
            "tool_limit_reached",
            "step_limit_reached",
            "task_timeout",
        }:
            state.answer = compose_evidence_answer(state.query, state.evidence)
        return state

    def resume(self, state: AgentState, top_k: int = 5) -> AgentState:
        """Resume only a task stopped by a local execution budget."""

        if state.status not in {"tool_limit_reached", "step_limit_reached", "task_timeout"}:
            raise TaskNotResumableError(
                "only bounded-interruption tasks can be resumed"
            )
        state.status = "running"
        state.answer = None
        state.evidence = []
        state.tool_calls = []
        state.steps.append(AgentStep("resume", "started", "new bounded execution budget"))
        try:
            self.graph.run(state, {"top_k": top_k}, start="retrieve_evidence")
        except (SourceRootError, GitToolError, IssueToolError):
            state.status = "failed"
            state.steps.append(AgentStep("retrieve_evidence", "failed", "resume tool input failed"))
            raise
        if state.answer is None and state.status in {
            "tool_limit_reached",
            "step_limit_reached",
            "task_timeout",
        }:
            state.answer = compose_evidence_answer(state.query, state.evidence)
        return state

    def _classify_node(self, state: AgentState, _context: dict[str, object]) -> str:
        category = classify_question(state.query)
        state.set_category(category)
        state.steps.append(AgentStep("classify_question", "completed", category))
        return "retrieve_evidence"

    def _retrieve_node(self, state: AgentState, context: dict[str, object]) -> str:
        top_k = int(context.get("top_k", 5))
        query = state.rewritten_query or state.query
        state.evidence = self._retrieve(state, top_k, query)
        return "evidence_check"

    def _evidence_node(self, state: AgentState, _context: dict[str, object]) -> str:
        has_direct_evidence = any(result.matched_terms for result in state.evidence)
        state.steps.append(
            AgentStep(
                "evidence_check",
                "completed" if has_direct_evidence else "insufficient",
                f"candidates={len(state.evidence)}",
            )
        )
        if not has_direct_evidence and state.retry_count < self.max_retries:
            rewrite = rewrite_query(state.query, state.category)
            if rewrite.changed:
                state.retry_count += 1
                state.rewritten_query = rewrite.rewritten_query
                state.steps.append(
                    AgentStep(
                        "query_rewrite",
                        "completed",
                        f"added={','.join(rewrite.added_terms)}",
                    )
                )
                return "retrieve_evidence"
        return "compose_answer"

    def _compose_node(self, state: AgentState, _context: dict[str, object]) -> None:
        if state.category == "project_summary":
            draft = compose_project_summary(state.query, state.evidence)
        else:
            draft = compose_evidence_answer(state.query, state.evidence)
        state.answer = draft
        state.status = "completed" if draft.evidence_sufficient else "insufficient_evidence"
        state.steps.append(AgentStep("compose_answer", state.status, "evidence-grounded draft"))
        return None

    def _record_tool(self, state: AgentState, name: str, detail: str) -> bool:
        if not state.record_tool_call(name, self.max_tool_calls):
            state.status = "tool_limit_reached"
            state.steps.append(AgentStep("terminate", "limit_reached", f"tool limit reached before {name}"))
            return False
        state.steps.append(AgentStep(name, "completed", detail))
        return True

    def _retrieve(self, state: AgentState, top_k: int, query: str | None = None):
        search_query = query or state.query
        if state.category == "code_location":
            if not self._record_tool(state, "search_code", "code chunks"):
                return []
            results = self.index_service.search_code(state.source_root, search_query, top_k)
            if results and self._record_tool(state, "read_file", results[0].citation):
                result = results[0]
                self.index_service.read_file(
                    state.source_root,
                    result.chunk.source_path,
                    result.chunk.start_line,
                    result.chunk.end_line,
                )
            return results

        if state.category == "project_summary":
            if not self._record_tool(state, "search_documents", "project docs"):
                return []
            if not self._record_tool(state, "search_code", "project code"):
                return []
            return self.index_service.search_project(state.source_root, search_query, top_k)

        if state.category == "knowledge_write":
            if not self._record_tool(state, "search_documents", "writeback source evidence"):
                return []
            results = self.index_service.search_hybrid(state.source_root, search_query, top_k)[1]
            self._read_first_evidence(state, results)
            if results and any(result.matched_terms for result in results):
                preview_draft = compose_evidence_answer(search_query, results)
                if self._record_tool(state, "create_knowledge_note_preview", "pending preview"):
                    self.writeback_service.create_preview(
                        title=search_query[:80],
                        content=preview_draft.answer,
                        target_path=f"DevMind/{state.task_id}.md",
                        source_citations=[
                            result.citation for result in results if result.matched_terms
                        ],
                    )
            return results

        if state.category == "git_history":
            if not self._record_tool(state, "get_git_history", "local repository"):
                return []
            return get_git_history(search_query, limit=top_k)

        if state.category == "git_diff":
            commit_hash = _extract_commit_hash(search_query)
            if commit_hash is None:
                if not self._record_tool(state, "get_git_history", "select latest local commit"):
                    return []
                history = get_git_history("", limit=1)
                if not history:
                    return []
                commit_hash = history[0].chunk.metadata["commit_hash"]
            if not self._record_tool(state, "get_commit_diff", f"commit {commit_hash}"):
                return []
            return [get_commit_diff(commit_hash)]

        if state.category == "issue_search":
            if not self._record_tool(state, "search_issues", "exported Issue records"):
                return []
            return search_issues(search_query, limit=top_k)

        if state.category == "troubleshooting":
            if not self._record_tool(state, "search_documents", "hybrid evidence"):
                return []
            if not self._record_tool(state, "search_issues", "historical failures"):
                return []
            if not self._record_tool(state, "get_git_history", "recent repository changes"):
                return []
            document_results = self.index_service.search_hybrid(
                state.source_root,
                state.query,
                top_k=top_k,
            )[1]
            self._read_first_evidence(state, document_results)
            issue_results = search_issues(state.query, limit=top_k)
            git_results = get_git_history(state.query, limit=top_k)
            from ..retrieval.rrf import reciprocal_rank_fusion

            return reciprocal_rank_fusion(
                [document_results, issue_results, git_results],
                top_k=top_k,
            )

        if not self._record_tool(state, "search_documents", "hybrid evidence"):
            return []
        results = self.index_service.search_hybrid(state.source_root, search_query, top_k)[1]
        self._read_first_evidence(state, results)
        return results

    def _read_first_evidence(self, state: AgentState, results) -> None:
        if not results:
            return
        result = results[0]
        if result.chunk.file_type not in {"markdown", "config", "code"}:
            return
        if not self._record_tool(state, "read_file", result.citation):
            return
        self.index_service.read_file(
            state.source_root,
            result.chunk.source_path,
            result.chunk.start_line,
            result.chunk.end_line,
        )


def _extract_commit_hash(query: str) -> str | None:
    match = re.search(r"(?<![0-9a-fA-F])[0-9a-fA-F]{7,40}(?![0-9a-fA-F])", query)
    return match.group(0) if match else None
