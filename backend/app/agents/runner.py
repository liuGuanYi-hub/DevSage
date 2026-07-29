"""Bounded, deterministic multi-tool Agent runner for the DevMind MVP."""

from __future__ import annotations

from uuid import uuid4

from ..services.answer_service import compose_evidence_answer
from ..services.index_service import IndexService, SourceRootError
from .classifier import classify_question
from .git_tools import GitToolError, get_git_history
from .issue_tools import IssueToolError, search_issues
from .state import AgentState, AgentStep


class AgentRunner:
    """Run a small finite workflow until evidence is sufficient or exhausted."""

    def __init__(self, index_service: IndexService, max_tool_calls: int = 4) -> None:
        self.index_service = index_service
        self.max_tool_calls = max_tool_calls

    def run(self, query: str, source_root: str, top_k: int = 5) -> AgentState:
        state = AgentState(uuid4().hex, query, source_root)
        category = classify_question(query)
        state.set_category(category)
        state.steps.append(AgentStep("classify_question", "completed", category))

        try:
            state.evidence = self._retrieve(state, top_k)
        except (SourceRootError, GitToolError, IssueToolError):
            state.status = "failed"
            state.steps.append(AgentStep("retrieve_evidence", "failed", "invalid source root"))
            raise

        state.steps.append(
            AgentStep(
                "evidence_check",
                "completed" if any(result.matched_terms for result in state.evidence) else "insufficient",
                f"candidates={len(state.evidence)}",
            )
        )
        draft = compose_evidence_answer(query, state.evidence)
        state.answer = draft
        state.status = "completed" if draft.evidence_sufficient else "insufficient_evidence"
        state.steps.append(AgentStep("compose_answer", state.status, "evidence-grounded draft"))
        return state

    def _retrieve(self, state: AgentState, top_k: int):
        if state.category == "code_location":
            state.tool_calls.append("search_code")
            state.steps.append(AgentStep("search_code", "completed", "code chunks"))
            results = self.index_service.search_code(state.source_root, state.query, top_k)
            if results and len(state.tool_calls) < self.max_tool_calls:
                result = results[0]
                self.index_service.read_file(
                    state.source_root,
                    result.chunk.source_path,
                    result.chunk.start_line,
                    result.chunk.end_line,
                )
                state.tool_calls.append("read_file")
                state.steps.append(AgentStep("read_file", "completed", result.citation))
            return results

        if state.category == "project_summary":
            state.tool_calls.extend(["search_documents", "search_code"])
            state.steps.append(AgentStep("search_documents", "completed", "project docs"))
            state.steps.append(AgentStep("search_code", "completed", "project code"))
            return self.index_service.search_project(state.source_root, state.query, top_k)

        if state.category == "git_history":
            state.tool_calls.append("get_git_history")
            state.steps.append(AgentStep("get_git_history", "completed", "local repository"))
            return get_git_history(state.query, limit=top_k)

        if state.category == "issue_search":
            state.tool_calls.append("search_issues")
            state.steps.append(AgentStep("search_issues", "completed", "exported Issue records"))
            return search_issues(state.query, limit=top_k)

        if state.category == "troubleshooting":
            state.tool_calls.extend(["search_documents", "search_issues", "get_git_history"])
            state.steps.append(AgentStep("search_documents", "completed", "hybrid evidence"))
            state.steps.append(AgentStep("search_issues", "completed", "historical failures"))
            state.steps.append(AgentStep("get_git_history", "completed", "recent repository changes"))
            document_results = self.index_service.search_hybrid(
                state.source_root,
                state.query,
                top_k=top_k,
            )[1]
            issue_results = search_issues(state.query, limit=top_k)
            git_results = get_git_history(state.query, limit=top_k)
            from ..retrieval.rrf import reciprocal_rank_fusion

            return reciprocal_rank_fusion(
                [document_results, issue_results, git_results],
                top_k=top_k,
            )

        state.tool_calls.append("search_documents")
        state.steps.append(AgentStep("search_documents", "completed", "hybrid evidence"))
        return self.index_service.search_hybrid(state.source_root, state.query, top_k)[1]
