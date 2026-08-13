"""Bounded, deterministic multi-tool Agent runner for the DevMind MVP."""

from __future__ import annotations

import logging
import os
import re
import time
from threading import Event
from pathlib import Path
from typing import Callable
from uuid import uuid4

from ..services.answer_service import compose_evidence_answer, compose_routed_answer
from ..services.index_service import IndexService, SourceRootError
from ..services.knowledge_writeback import KnowledgeWritebackService
from .classifier import classify_question
from .git_tools import GitToolError, get_commit_diff, get_git_history
from .graph import AgentGraph, AgentLimits
from .issue_tools import IssueToolError, search_issues
from .query_rewrite import rewrite_query
from .state import AgentState, AgentStep
from ..services.task_store import TaskNotResumableError
from ..retrieval.answer_search import (
    _code_location_needs_documents,
    _expand_supporting_document_query,
    _is_document_chunk as _is_supporting_document,
)


logger = logging.getLogger("devsage.agent")
AgentProgressCallback = Callable[[AgentState, AgentStep], None]


class AgentRunner:
    """Run an observable graph until evidence is sufficient or exhausted."""

    def __init__(
        self,
        index_service: IndexService,
        max_tool_calls: int = 4,
        max_steps: int = 12,
        max_retries: int = 1,
        max_tool_retries: int = 1,
        max_runtime_seconds: float | None = 30.0,
        writeback_service: KnowledgeWritebackService | None = None,
    ) -> None:
        self.index_service = index_service
        self.max_tool_calls = max_tool_calls
        self.max_steps = max_steps
        self.max_retries = max_retries
        if max_tool_retries < 0:
            raise ValueError("max_tool_retries must be non-negative")
        self.max_tool_retries = max_tool_retries
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

    def run(
        self,
        query: str,
        source_root: str,
        top_k: int = 5,
        project_id: str | None = None,
        progress_callback: AgentProgressCallback | None = None,
        cancel_event: Event | None = None,
    ) -> AgentState:
        state = AgentState(uuid4().hex, query, source_root, project_id=project_id)
        started_at = time.perf_counter()
        try:
            self.graph.run(
                state,
                {"top_k": top_k},
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            )
            if state.answer is None and state.status in {
                "tool_limit_reached",
                "step_limit_reached",
                "task_timeout",
                "cancelled",
            }:
                state.answer = compose_routed_answer(state.query, state.evidence)
        except (SourceRootError, GitToolError, IssueToolError):
            state.status = "failed"
            state.steps.append(AgentStep("retrieve_evidence", "failed", "invalid source root or tool input"))
            raise
        finally:
            self._record_usage(state, started_at)
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
        started_at = time.perf_counter()
        try:
            self.graph.run(state, {"top_k": top_k}, start="retrieve_evidence")
            if state.answer is None and state.status in {
                "tool_limit_reached",
                "step_limit_reached",
                "task_timeout",
            }:
                state.answer = compose_routed_answer(state.query, state.evidence)
        except (SourceRootError, GitToolError, IssueToolError):
            state.status = "failed"
            state.steps.append(AgentStep("retrieve_evidence", "failed", "resume tool input failed"))
            raise
        finally:
            self._record_usage(state, started_at)
        return state

    @staticmethod
    def _record_usage(state: AgentState, started_at: float) -> None:
        state.refresh_usage()
        state.usage.runtime_ms += max(0, round((time.perf_counter() - started_at) * 1000))
        logger.info(
            "agent_run_completed task_id=%s category=%s status=%s tool_calls=%d "
            "tool_retries=%d runtime_ms=%d token_estimate=%d",
            state.task_id,
            state.category,
            state.status,
            state.usage.tool_calls,
            state.usage.tool_retries,
            state.usage.runtime_ms,
            state.usage.total_token_estimate,
        )

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
        draft = compose_routed_answer(state.query, state.evidence)
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

    def _run_retryable_tool(
        self,
        state: AgentState,
        name: str,
        detail: str,
        operation: Callable[[], object],
    ) -> object | None:
        """Run a Git/Issue tool with a bounded retry and observable attempts."""

        attempt = 0
        while True:
            if not state.record_tool_call(name, self.max_tool_calls):
                state.status = "tool_limit_reached"
                state.steps.append(
                    AgentStep("terminate", "limit_reached", f"tool limit reached before {name}")
                )
                return None
            try:
                result = operation()
            except (GitToolError, IssueToolError) as exc:
                state.steps.append(
                    AgentStep(name, "failed", f"attempt={attempt + 1}; {type(exc).__name__}")
                )
                if attempt >= self.max_tool_retries:
                    raise
                attempt += 1
                state.tool_retry_count += 1
                state.steps.append(
                    AgentStep("tool_retry", "scheduled", f"tool={name}; retry={attempt}")
                )
                continue
            state.steps.append(AgentStep(name, "completed", detail))
            return result

    def _retrieve(self, state: AgentState, top_k: int, query: str | None = None):
        search_query = query or state.query
        if state.category == "code_location":
            if not self._record_tool(state, "search_code", "code chunks"):
                return []
            code_results = self.index_service.search_code(
                state.source_root,
                search_query,
                top_k,
            )
            document_results = []
            if _code_location_needs_documents(search_query):
                if self._record_tool(state, "search_documents", "supporting documents"):
                    document_results = [
                        result
                        for result in self.index_service.search_hybrid(
                            state.source_root,
                            _expand_supporting_document_query(search_query),
                            top_k=top_k * 2,
                        )[1]
                        if _is_supporting_document(result.chunk, search_query)
                    ][:top_k]
            if document_results:
                from ..retrieval.rrf import reciprocal_rank_fusion

                results = reciprocal_rank_fusion(
                    [code_results, document_results],
                    top_k=top_k,
                )
            else:
                results = code_results
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
            summary_top_k = max(top_k, 8)
            return self.index_service.search_project(
                state.source_root,
                search_query,
                summary_top_k,
            )

        if state.category == "knowledge_write":
            if not self._record_tool(state, "search_documents", "writeback source evidence"):
                return []
            results = self._search_answer_evidence(
                state.source_root,
                search_query,
                top_k,
            )
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
            results = self._run_retryable_tool(
                state,
                "get_git_history",
                "local repository",
                lambda: get_git_history(search_query, limit=top_k),
            )
            return results or []

        if state.category == "git_diff":
            commit_hash = _extract_commit_hash(search_query)
            if commit_hash is None:
                history = self._run_retryable_tool(
                    state,
                    "get_git_history",
                    "select latest local commit",
                    lambda: get_git_history("", limit=1),
                )
                if not history:
                    return []
                commit_hash = history[0].chunk.metadata["commit_hash"]
            result = self._run_retryable_tool(
                state,
                "get_commit_diff",
                f"commit {commit_hash}",
                lambda: get_commit_diff(commit_hash),
            )
            return [result] if result is not None else []

        if state.category == "issue_search":
            results = self._run_retryable_tool(
                state,
                "search_issues",
                "configured external or exported Issue records",
                lambda: search_issues(search_query, limit=top_k),
            )
            return results or []

        if state.category == "troubleshooting":
            if not self._record_tool(state, "search_documents", "hybrid evidence"):
                return []
            document_results = self.index_service.search_hybrid(
                state.source_root,
                state.query,
                top_k=top_k,
            )[1]
            self._read_first_evidence(state, document_results)
            issue_results = self._run_retryable_tool(
                state,
                "search_issues",
                "historical failures from configured or exported Issues",
                lambda: search_issues(state.query, limit=top_k),
            ) or []
            git_results = self._run_retryable_tool(
                state,
                "get_git_history",
                "recent repository changes",
                lambda: get_git_history(state.query, limit=top_k),
            ) or []
            from ..retrieval.rrf import reciprocal_rank_fusion

            return reciprocal_rank_fusion(
                [document_results, issue_results, git_results],
                top_k=top_k,
            )

        if not self._record_tool(state, "search_documents", "hybrid evidence"):
            return []
        results = self._search_answer_evidence(
            state.source_root,
            search_query,
            top_k,
        )
        self._read_first_evidence(state, results)
        return results

    def _search_answer_evidence(
        self,
        source_root: str,
        query: str,
        top_k: int,
    ) -> list:
        """Reuse category-aware retrieval while keeping lightweight test doubles valid."""

        search_for_answer = getattr(self.index_service, "search_for_answer", None)
        if callable(search_for_answer):
            return search_for_answer(source_root, query, top_k)[1]
        return self.index_service.search_hybrid(source_root, query, top_k)[1]

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
