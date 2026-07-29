"""DevSage API entrypoint for project-aware retrieval and Agent workflows."""

from pathlib import Path
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .schemas.search import (
    IndexRequest,
    IndexResponse,
    AnswerRequest,
    AnswerResponse,
    KnowledgeNotePreviewRequest,
    KnowledgeNotePreviewResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from .schemas.agent import (
    AgentRequest,
    AgentResumeRequest,
    AgentResponse,
    AgentUsageResponse,
    AgentStepResponse,
    TroubleshootingFindingResponse,
    TroubleshootingReportResponse,
)
from .schemas.projects import ProjectListResponse, ProjectResponse
from .agents.runner import AgentRunner
from .services.index_service import IndexService, SourceRootError
from .services.answer_service import AnswerDraft, compose_evidence_answer
from .services.knowledge_writeback import KnowledgeWritebackService, WritebackPolicyError
from .services.project_registry import ProjectRegistry, ProjectRegistryError
from .services.troubleshooting import TroubleshootingReport, build_troubleshooting_report
from .services.task_store import (
    FileTaskStateStore,
    PostgresTaskStateStore,
    TaskNotResumableError,
    TaskStateError,
    TaskStateNotFoundError,
    TaskStateStorageError,
)
from .storage.postgres_repository import PostgresRepositoryError


PROJECT_ROOT = Path(
    os.getenv("DEVSAGE_PROJECT_ROOT", str(Path(__file__).resolve().parents[2]))
).resolve()

app = FastAPI(
    title="DevSage API",
    version="0.1.0",
    description="研发知识库与故障排查系统 API",
)

index_service = IndexService()
agent_runner = AgentRunner(index_service)
writeback_service = KnowledgeWritebackService(PROJECT_ROOT / "data" / "approved-notes")
project_registry = ProjectRegistry.from_environment(PROJECT_ROOT)


def _create_task_store():
    storage_mode = os.getenv("DEVSAGE_STORAGE", "memory").strip().lower()
    if storage_mode in {"postgres", "postgresql"}:
        return PostgresTaskStateStore()
    return FileTaskStateStore(PROJECT_ROOT / "data" / "task-state")


task_store = _create_task_store()


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return a minimal liveness response."""

    return {"status": "ok", "service": "devsage-api"}


@app.get("/api/projects", response_model=ProjectListResponse, tags=["projects"])
def list_projects() -> ProjectListResponse:
    """List safe project metadata and local role capability boundaries."""

    items = [ProjectResponse(**definition.to_dict()) for definition in project_registry.list_projects()]
    return ProjectListResponse(items=items, total=len(items))


@app.get("/api/projects/{project_id}", response_model=ProjectResponse, tags=["projects"])
def get_project(project_id: str) -> ProjectResponse:
    """Return one registered project without exposing absolute filesystem paths."""

    try:
        definition = project_registry.get(project_id)
    except ProjectRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectResponse(**definition.to_dict())


def _resolve_request_source_root(project_id: str | None, source_root: str) -> str:
    """Resolve a registered project while preserving the legacy source_root API."""

    if not project_id:
        return source_root
    resolved = project_registry.resolve_source_root(project_id)
    return resolved.relative_to(PROJECT_ROOT).as_posix()


@app.post("/api/index", response_model=IndexResponse, tags=["index"])
def index_source(request: IndexRequest) -> IndexResponse:
    """Build or incrementally update a project-relative source snapshot."""

    try:
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        source_root, snapshot = index_service.build(requested_root)
    except (SourceRootError, ProjectRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PostgresRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    stats = snapshot.stats
    return IndexResponse(
        source_root=source_root,
        document_count=len(snapshot.documents),
        chunk_count=len(snapshot.chunks),
        added_documents=stats.added_documents if stats else len(snapshot.documents),
        changed_documents=stats.changed_documents if stats else 0,
        unchanged_documents=stats.unchanged_documents if stats else 0,
        removed_documents=stats.removed_documents if stats else 0,
    )


@app.post("/api/search", response_model=SearchResponse, tags=["retrieval"])
def search_source(request: SearchRequest) -> SearchResponse:
    """Return keyword evidence with source citations."""

    try:
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        source_root, results = index_service.search(
            requested_root,
            request.query,
            request.top_k,
        )
    except (SourceRootError, ProjectRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PostgresRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    hits = [_to_search_hit(result) for result in results]
    return SearchResponse(query=request.query, source_root=source_root, results=hits)


def _to_search_hit(result) -> SearchHit:
    """Convert an internal result to the public citation contract."""

    return SearchHit(
        citation=result.citation,
        source_path=result.chunk.source_path,
        start_line=result.chunk.start_line,
        end_line=result.chunk.end_line,
        score=result.score,
        matched_terms=list(result.matched_terms),
        content=result.chunk.content,
    )


def _answer_response(
    query: str,
    source_root: str,
    draft: AnswerDraft,
) -> AnswerResponse:
    return AnswerResponse(
        query=query,
        source_root=source_root,
        answer=draft.answer,
        citations=list(draft.citations),
        evidence=[_to_search_hit(result) for result in draft.evidence],
        evidence_sufficient=draft.evidence_sufficient,
        warning=draft.warning,
    )


def _troubleshooting_response(report: TroubleshootingReport) -> TroubleshootingReportResponse:
    return TroubleshootingReportResponse(
        query=report.query,
        summary=report.summary,
        findings=[
            TroubleshootingFindingResponse(
                source_type=finding.source_type,
                citations=list(finding.citations),
                snippets=list(finding.snippets),
            )
            for finding in report.findings
        ],
        next_steps=list(report.next_steps),
        citations=list(report.citations),
        evidence_sufficient=report.evidence_sufficient,
    )


@app.post("/api/answer", response_model=AnswerResponse, tags=["answer"])
def answer_question(request: AnswerRequest) -> AnswerResponse:
    """Return a deterministic answer assembled only from direct evidence."""

    try:
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        source_root, results = index_service.search_hybrid(
            requested_root,
            request.query,
            request.top_k,
        )
    except (SourceRootError, ProjectRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PostgresRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _answer_response(
        request.query,
        source_root,
        compose_evidence_answer(request.query, results),
    )


@app.post("/api/answer/stream", tags=["answer"])
def stream_answer(request: AnswerRequest) -> StreamingResponse:
    """Stream the evidence-grounded answer as Server-Sent Events."""

    try:
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        source_root, results = index_service.search_hybrid(
            requested_root,
            request.query,
            request.top_k,
        )
    except (SourceRootError, ProjectRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PostgresRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    draft = compose_evidence_answer(request.query, results)
    response = _answer_response(request.query, source_root, draft)

    def events():
        yield f"event: meta\ndata: {json.dumps({'source_root': source_root}, ensure_ascii=False)}\n\n"
        for start in range(0, len(response.answer), 96):
            payload = {"text": response.answer[start : start + 96]}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {response.model_dump_json() if hasattr(response, 'model_dump_json') else response.json()}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/agent/run", response_model=AgentResponse, tags=["agent"])
def run_agent(request: AgentRequest) -> AgentResponse:
    """Run the bounded offline Agent workflow."""

    try:
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        state = agent_runner.run(request.query, requested_root, request.top_k)
    except (SourceRootError, ProjectRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PostgresRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if request.persist:
        task_store.save(state)
    return _agent_response(state)


def _agent_response(state) -> AgentResponse:
    """Convert an internal task state to the public Agent response."""

    draft = state.answer
    if draft is None:
        raise HTTPException(status_code=500, detail="Agent task has no answer draft")
    report = None
    if state.category == "troubleshooting":
        report = _troubleshooting_response(
            build_troubleshooting_report(state.query, state.evidence)
        )
    return AgentResponse(
        task_id=state.task_id,
        query=state.query,
        source_root=state.source_root,
        category=state.category,
        status=state.status,
        answer=draft.answer,
        citations=list(draft.citations),
        evidence_sufficient=draft.evidence_sufficient,
        warning=draft.warning,
        tool_calls=state.tool_calls,
        tool_retry_count=state.tool_retry_count,
        steps=[
            AgentStepResponse(name=step.name, status=step.status, detail=step.detail)
            for step in state.steps
        ],
        evidence=[_to_search_hit(result) for result in state.evidence],
        usage=AgentUsageResponse(**state.usage.to_dict()),
        report=report,
    )


@app.get("/api/agent/tasks/{task_id}", response_model=AgentResponse, tags=["agent"])
def get_agent_task(task_id: str) -> AgentResponse:
    """Load an explicitly persisted Agent task snapshot."""

    try:
        return _agent_response(task_store.load(task_id))
    except TaskStateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskStateStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TaskStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/agent/tasks/{task_id}/resume", response_model=AgentResponse, tags=["agent"])
def resume_agent_task(task_id: str, request: AgentResumeRequest) -> AgentResponse:
    """Resume a task stopped by the local tool or graph budget."""

    try:
        state = task_store.load(task_id)
        state = agent_runner.resume(state, request.top_k)
        task_store.save(state)
        return _agent_response(state)
    except TaskStateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskNotResumableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskStateStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (TaskStateError, SourceRootError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/knowledge-notes/preview", response_model=KnowledgeNotePreviewResponse, tags=["knowledge-notes"])
def create_knowledge_note_preview(
    request: KnowledgeNotePreviewRequest,
) -> KnowledgeNotePreviewResponse:
    """Create a pending note preview without writing to disk."""

    try:
        preview = writeback_service.create_preview(
            title=request.title,
            content=request.content,
            target_path=request.target_path,
            source_citations=request.source_citations,
        )
    except WritebackPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeNotePreviewResponse(
        preview_id=preview.preview_id,
        title=preview.title,
        target_path=preview.target_path,
        content=preview.content,
        source_citations=list(preview.source_citations),
        diff={
            "operation": preview.diff.operation,
            "target_exists": preview.diff.target_exists,
            "current_content_hash": preview.diff.current_content_hash,
            "proposed_content_hash": preview.diff.proposed_content_hash,
            "additions": preview.diff.additions,
            "deletions": preview.diff.deletions,
            "unified_diff": list(preview.diff.unified_diff),
        },
        status=preview.status,
    )


@app.post("/api/knowledge-notes/{preview_id}/approve", response_model=KnowledgeNotePreviewResponse, tags=["knowledge-notes"])
def approve_knowledge_note(preview_id: str) -> KnowledgeNotePreviewResponse:
    """Write a previously previewed note into the approved-note staging root."""

    try:
        preview = writeback_service.approve(preview_id)
    except WritebackPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeNotePreviewResponse(
        preview_id=preview.preview_id,
        title=preview.title,
        target_path=preview.target_path,
        content=preview.content,
        source_citations=list(preview.source_citations),
        diff={
            "operation": preview.diff.operation,
            "target_exists": preview.diff.target_exists,
            "current_content_hash": preview.diff.current_content_hash,
            "proposed_content_hash": preview.diff.proposed_content_hash,
            "additions": preview.diff.additions,
            "deletions": preview.diff.deletions,
            "unified_diff": list(preview.diff.unified_diff),
        },
        status=preview.status,
    )
