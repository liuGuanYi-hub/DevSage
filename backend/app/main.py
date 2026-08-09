"""DevSage API entrypoint for project-aware retrieval and Agent workflows."""

from pathlib import Path
import json
import logging
import os

from fastapi import Depends, FastAPI, Header, HTTPException
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
from .schemas.code_changes import (
    CodeChangeDiffResponse,
    CodeChangePreviewRequest,
    CodeChangePreviewResponse,
    IssueWritePreviewRequest,
    IssueWritePreviewResponse,
)
from .schemas.auth import LoginRequest, LoginResponse, MeResponse
from .auth import AuthError, authenticate, decode_token, issue_token, resolve_actor_id
from .agents.runner import AgentRunner
from .services.index_service import IndexService, SourceRootError
from .services.answer_service import AnswerDraft, compose_routed_answer
from .services.knowledge_writeback import KnowledgeWritebackService, WritebackPolicyError
from .services.code_writeback import CodeChangePolicyError, CodeChangeWritebackService
from .services.issue_writeback import (
    ExternalIssueWritebackService,
    IssueWritePolicyError,
)
from .services.cache import CacheError, CacheBackend, cache_key, create_cache_backend
from .services.project_registry import (
    DEFAULT_ACTOR_ID,
    ProjectRegistry,
    ProjectRegistryError,
)
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
code_writeback_service = CodeChangeWritebackService(PROJECT_ROOT)
issue_writeback_service = ExternalIssueWritebackService()
project_registry = ProjectRegistry.from_environment(PROJECT_ROOT)
approval_logger = logging.getLogger("devsage.approval")


def _create_response_cache() -> CacheBackend:
    try:
        return create_cache_backend()
    except CacheError as exc:
        logging.getLogger("devsage.cache").warning(
            "cache_disabled_due_to_configuration backend_error=%s", str(exc)
        )
        return create_cache_backend_from_disabled()


def create_cache_backend_from_disabled() -> CacheBackend:
    from .services.cache import NullCache

    return NullCache()


response_cache = _create_response_cache()


def _cache_get(key: str) -> str | None:
    try:
        return response_cache.get(key)
    except Exception as exc:  # cache outage must not take down retrieval
        logging.getLogger("devsage.cache").warning(
            "cache_read_unavailable backend=%s error_type=%s",
            response_cache.name,
            type(exc).__name__,
        )
        return None


def _cache_set(key: str, value: str, ttl_seconds: int) -> None:
    try:
        response_cache.set(key, value, ttl_seconds)
    except Exception as exc:  # cache outage must not take down retrieval
        logging.getLogger("devsage.cache").warning(
            "cache_write_unavailable backend=%s error_type=%s",
            response_cache.name,
            type(exc).__name__,
        )


def _cache_delete_prefix(prefix: str) -> None:
    try:
        response_cache.delete_prefix(prefix)
    except Exception as exc:
        logging.getLogger("devsage.cache").warning(
            "cache_invalidation_unavailable backend=%s error_type=%s",
            response_cache.name,
            type(exc).__name__,
        )


def _model_json(model) -> str:
    return model.model_dump_json() if hasattr(model, "model_dump_json") else model.json()


def _validate_model(model_type, payload):
    return (
        model_type.model_validate(payload)
        if hasattr(model_type, "model_validate")
        else model_type.parse_obj(payload)
    )


def _create_task_store():
    storage_mode = os.getenv("DEVSAGE_STORAGE", "memory").strip().lower()
    if storage_mode in {"postgres", "postgresql"}:
        return PostgresTaskStateStore()
    return FileTaskStateStore(PROJECT_ROOT / "data" / "task-state")


task_store = _create_task_store()


@app.get("/health", tags=["system"])
def health() -> dict[str, str | bool]:
    """Return liveness and non-sensitive runtime mode information."""

    storage_mode = os.getenv("DEVSAGE_STORAGE", "memory").strip().lower() or "memory"
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "hash").strip().lower() or "hash"
    external_issue_configured = bool(
        os.getenv("DEVSAGE_EXTERNAL_ISSUE_URL", "").strip()
        and os.getenv("DEVSAGE_EXTERNAL_ISSUE_REPOSITORY", "").strip()
    )
    cache_mode = response_cache.name
    auth_enabled = os.getenv("DEVSAGE_AUTH_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    external_issue_write_enabled = os.getenv(
        "DEVSAGE_EXTERNAL_ISSUE_WRITE_ENABLED", ""
    ).strip().lower() in {"1", "true", "yes", "on"}

    return {
        "status": "ok",
        "service": "devsage-api",
        "storage": storage_mode,
        "embedding_provider": embedding_provider,
        "external_issue_configured": external_issue_configured,
        "external_issue_write_enabled": external_issue_write_enabled,
        "auth_enabled": auth_enabled,
        "cache": cache_mode,
    }


@app.post("/api/auth/login", response_model=LoginResponse, tags=["auth"])
def login(request: LoginRequest) -> LoginResponse:
    """Issue a signed Bearer token when formal auth is enabled."""

    if os.getenv("DEVSAGE_AUTH_ENABLED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise HTTPException(status_code=404, detail="formal authentication is disabled")
    try:
        user = authenticate(request.username, request.password, PROJECT_ROOT)
        access_token, expires_in = issue_token(user)
    except AuthError:
        raise HTTPException(status_code=401, detail="invalid credentials") from None
    return LoginResponse(
        access_token=access_token,
        expires_in=expires_in,
        username=user.username,
        actor_id=user.actor_id,
    )


@app.get("/api/auth/me", response_model=MeResponse, tags=["auth"])
def get_current_user(
    actor_id: str = Depends(resolve_actor_id),
    authorization: str | None = Header(default=None),
) -> MeResponse:
    """Return the authenticated actor identity without exposing token data."""

    if os.getenv("DEVSAGE_AUTH_ENABLED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise HTTPException(status_code=404, detail="formal authentication is disabled")
    try:
        token = decode_token((authorization or "")[7:].strip())
    except AuthError:
        raise HTTPException(status_code=401, detail="Bearer authentication is invalid") from None
    return MeResponse(username=token.username, actor_id=actor_id)


@app.get("/api/projects", response_model=ProjectListResponse, tags=["projects"])
def list_projects(_actor_id: str = Depends(resolve_actor_id)) -> ProjectListResponse:
    """List safe project metadata and local role capability boundaries."""

    items = [ProjectResponse(**definition.to_dict()) for definition in project_registry.list_projects()]
    return ProjectListResponse(items=items, total=len(items))


@app.get("/api/projects/{project_id}", response_model=ProjectResponse, tags=["projects"])
def get_project(
    project_id: str,
    actor_id: str = Depends(resolve_actor_id),
) -> ProjectResponse:
    """Return one registered project without exposing absolute filesystem paths."""

    try:
        definition = project_registry.get(project_id)
    except ProjectRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _authorize_project(project_id, actor_id, "read")
    return ProjectResponse(**definition.to_dict())


def _resolve_request_source_root(project_id: str | None, source_root: str) -> str:
    """Resolve a registered project while preserving the legacy source_root API."""

    if not project_id:
        return source_root
    resolved = project_registry.resolve_source_root(project_id)
    return resolved.relative_to(PROJECT_ROOT).as_posix()


def _scope_knowledge_target_path(project_id: str | None, target_path: str) -> str:
    """Keep project-specific approved notes isolated while preserving legacy paths."""

    if not project_id:
        return target_path
    project_registry.get(project_id)
    return f"projects/{project_id}/{target_path}"


def _authorize_project(project_id: str, actor_id: str, action: str) -> None:
    """Enforce local project capability boundaries without pretending to authenticate."""

    project_registry.get(project_id)
    try:
        project_registry.require_action(project_id, actor_id, action)
    except ProjectRegistryError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _project_id_from_target_path(target_path: str) -> str | None:
    parts = target_path.split("/")
    if len(parts) >= 3 and parts[0] == "projects":
        return parts[1]
    return None


@app.post("/api/index", response_model=IndexResponse, tags=["index"])
def index_source(
    request: IndexRequest,
    actor_id: str = Depends(resolve_actor_id),
) -> IndexResponse:
    """Build or incrementally update a project-relative source snapshot."""

    try:
        if request.project_id:
            _authorize_project(request.project_id, actor_id, "manage_project")
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        source_root, snapshot = index_service.build(requested_root)
    except (SourceRootError, ProjectRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PostgresRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    stats = snapshot.stats
    _cache_delete_prefix("search:")
    _cache_delete_prefix("answer:")
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
def search_source(
    request: SearchRequest,
    actor_id: str = Depends(resolve_actor_id),
) -> SearchResponse:
    """Return keyword evidence with source citations."""

    try:
        if request.project_id:
            _authorize_project(request.project_id, actor_id, "search")
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        cache_key_value = cache_key(
            "search",
            request.project_id,
            requested_root,
            request.query,
            request.top_k,
            os.getenv("EMBEDDING_PROVIDER", "hash"),
        )
        cached = _cache_get(cache_key_value)
        if cached:
            return _validate_model(SearchResponse, json.loads(cached))
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
    response = SearchResponse(query=request.query, source_root=source_root, results=hits)
    _cache_set(cache_key_value, _model_json(response), ttl_seconds=60)
    return response


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


def _code_change_response(preview) -> CodeChangePreviewResponse:
    return CodeChangePreviewResponse(
        preview_id=preview.preview_id,
        source_root=preview.source_root,
        target_path=preview.target_path,
        proposed_content=preview.proposed_content,
        source_citations=list(preview.source_citations),
        diff=CodeChangeDiffResponse(
            operation=preview.diff.operation,
            current_content_hash=preview.diff.current_content_hash,
            proposed_content_hash=preview.diff.proposed_content_hash,
            additions=preview.diff.additions,
            deletions=preview.diff.deletions,
            unified_diff=list(preview.diff.unified_diff),
        ),
        status=preview.status,
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
def answer_question(
    request: AnswerRequest,
    actor_id: str = Depends(resolve_actor_id),
) -> AnswerResponse:
    """Return a deterministic answer assembled only from direct evidence."""

    try:
        if request.project_id:
            _authorize_project(request.project_id, actor_id, "search")
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        cache_key_value = cache_key(
            "answer",
            request.project_id,
            requested_root,
            request.query,
            request.top_k,
            os.getenv("EMBEDDING_PROVIDER", "hash"),
        )
        cached = _cache_get(cache_key_value)
        if cached:
            return _validate_model(AnswerResponse, json.loads(cached))
        source_root, results = index_service.search_for_answer(
            requested_root,
            request.query,
            request.top_k,
        )
    except (SourceRootError, ProjectRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PostgresRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = _answer_response(
        request.query,
        source_root,
        compose_routed_answer(request.query, results),
    )
    _cache_set(cache_key_value, _model_json(response), ttl_seconds=60)
    return response


@app.post("/api/answer/stream", tags=["answer"])
def stream_answer(
    request: AnswerRequest,
    actor_id: str = Depends(resolve_actor_id),
) -> StreamingResponse:
    """Stream the evidence-grounded answer as Server-Sent Events."""

    try:
        if request.project_id:
            _authorize_project(request.project_id, actor_id, "search")
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        source_root, results = index_service.search_for_answer(
            requested_root,
            request.query,
            request.top_k,
        )
    except (SourceRootError, ProjectRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PostgresRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    draft = compose_routed_answer(request.query, results)
    response = _answer_response(request.query, source_root, draft)

    def events():
        yield f"event: meta\ndata: {json.dumps({'source_root': source_root}, ensure_ascii=False)}\n\n"
        for start in range(0, len(response.answer), 96):
            payload = {"text": response.answer[start : start + 96]}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {response.model_dump_json() if hasattr(response, 'model_dump_json') else response.json()}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post(
    "/api/code-changes/preview",
    response_model=CodeChangePreviewResponse,
    tags=["code-changes"],
)
def create_code_change_preview(
    request: CodeChangePreviewRequest,
    actor_id: str = Depends(resolve_actor_id),
) -> CodeChangePreviewResponse:
    """Preview a bounded code-file update without writing to the project."""

    try:
        if request.project_id:
            _authorize_project(request.project_id, actor_id, "code_write_preview")
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        preview = code_writeback_service.create_preview(
            source_root=requested_root,
            target_path=request.target_path,
            proposed_content=request.proposed_content,
            source_citations=request.source_citations,
            project_id=request.project_id,
        )
    except (SourceRootError, ProjectRegistryError, CodeChangePolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    approval_logger.info(
        "code_preview_created preview_id=%s actor_id=%s project_id=%s target_path=%s",
        preview.preview_id,
        actor_id,
        preview.project_id,
        preview.target_path,
    )
    return _code_change_response(preview)


@app.post(
    "/api/code-changes/{preview_id}/approve",
    response_model=CodeChangePreviewResponse,
    tags=["code-changes"],
)
def approve_code_change(
    preview_id: str,
    actor_id: str = Depends(resolve_actor_id),
) -> CodeChangePreviewResponse:
    """Apply a previously previewed code change after a fresh Hash check."""

    try:
        preview = code_writeback_service.get_preview(preview_id)
        if preview.project_id:
            _authorize_project(preview.project_id, actor_id, "code_write_approve")
        approved = code_writeback_service.approve(preview_id)
    except (ProjectRegistryError, CodeChangePolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    approval_logger.info(
        "code_approved preview_id=%s actor_id=%s project_id=%s target_path=%s status=%s",
        approved.preview_id,
        actor_id,
        approved.project_id,
        approved.target_path,
        approved.status,
    )
    return _code_change_response(approved)


@app.post("/api/agent/run", response_model=AgentResponse, tags=["agent"])
def run_agent(
    request: AgentRequest,
    actor_id: str = Depends(resolve_actor_id),
) -> AgentResponse:
    """Run the bounded offline Agent workflow."""

    try:
        if request.project_id:
            _authorize_project(request.project_id, actor_id, "agent")
        requested_root = _resolve_request_source_root(request.project_id, request.source_root)
        state = agent_runner.run(
            request.query,
            requested_root,
            request.top_k,
            project_id=request.project_id,
        )
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
        project_id=state.project_id,
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
def get_agent_task(
    task_id: str,
    actor_id: str = Depends(resolve_actor_id),
) -> AgentResponse:
    """Load an explicitly persisted Agent task snapshot."""

    try:
        state = task_store.load(task_id)
        if state.project_id:
            _authorize_project(state.project_id, actor_id, "read")
        return _agent_response(state)
    except TaskStateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskStateStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TaskStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/agent/tasks/{task_id}/resume", response_model=AgentResponse, tags=["agent"])
def resume_agent_task(
    task_id: str,
    request: AgentResumeRequest,
    actor_id: str = Depends(resolve_actor_id),
) -> AgentResponse:
    """Resume a task stopped by the local tool or graph budget."""

    try:
        state = task_store.load(task_id)
        if state.project_id:
            _authorize_project(state.project_id, actor_id, "agent")
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
    actor_id: str = Depends(resolve_actor_id),
) -> KnowledgeNotePreviewResponse:
    """Create a pending note preview without writing to disk."""

    try:
        if request.project_id:
            _authorize_project(request.project_id, actor_id, "writeback_preview")
        target_path = _scope_knowledge_target_path(request.project_id, request.target_path)
        preview = writeback_service.create_preview(
            title=request.title,
            content=request.content,
            target_path=target_path,
            source_citations=request.source_citations,
        )
    except (ProjectRegistryError, WritebackPolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    approval_logger.info(
        "knowledge_preview_created preview_id=%s actor_id=%s project_id=%s target_path=%s",
        preview.preview_id,
        actor_id,
        request.project_id,
        preview.target_path,
    )
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
def approve_knowledge_note(
    preview_id: str,
    actor_id: str = Depends(resolve_actor_id),
) -> KnowledgeNotePreviewResponse:
    """Write a previously previewed note into the approved-note staging root."""

    try:
        preview = writeback_service.get_preview(preview_id)
        project_id = _project_id_from_target_path(preview.target_path)
        if project_id:
            _authorize_project(project_id, actor_id, "writeback_approve")
        preview = writeback_service.approve(preview_id)
    except (ProjectRegistryError, WritebackPolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    approval_logger.info(
        "knowledge_approved preview_id=%s actor_id=%s project_id=%s target_path=%s status=%s",
        preview.preview_id,
        actor_id,
        project_id,
        preview.target_path,
        preview.status,
    )
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


def _issue_write_response(preview) -> IssueWritePreviewResponse:
    return IssueWritePreviewResponse(
        preview_id=preview.preview_id,
        project_id=preview.project_id,
        title=preview.title,
        body=preview.body,
        labels=list(preview.labels),
        status=preview.status,
        remote_number=preview.remote_number,
        remote_url=preview.remote_url,
    )


@app.post(
    "/api/issues/preview",
    response_model=IssueWritePreviewResponse,
    tags=["issues"],
)
def create_issue_write_preview(
    request: IssueWritePreviewRequest,
    actor_id: str = Depends(resolve_actor_id),
) -> IssueWritePreviewResponse:
    """Create an external Issue payload without making a network request."""

    try:
        if request.project_id:
            _authorize_project(request.project_id, actor_id, "issue_write_preview")
        preview = issue_writeback_service.create_preview(
            title=request.title,
            body=request.body,
            labels=request.labels,
            project_id=request.project_id,
        )
    except (ProjectRegistryError, IssueWritePolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    approval_logger.info(
        "issue_write_preview_created preview_id=%s actor_id=%s project_id=%s",
        preview.preview_id,
        actor_id,
        preview.project_id,
    )
    return _issue_write_response(preview)


@app.post(
    "/api/issues/{preview_id}/approve",
    response_model=IssueWritePreviewResponse,
    tags=["issues"],
)
def approve_issue_write(
    preview_id: str,
    actor_id: str = Depends(resolve_actor_id),
) -> IssueWritePreviewResponse:
    """Submit one previously previewed external Issue after capability checks."""

    try:
        preview = issue_writeback_service.get_preview(preview_id)
        if preview.project_id:
            _authorize_project(preview.project_id, actor_id, "issue_write_approve")
        approved = issue_writeback_service.approve(preview_id)
    except ProjectRegistryError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except IssueWritePolicyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    approval_logger.info(
        "issue_write_approved preview_id=%s actor_id=%s project_id=%s status=%s",
        approved.preview_id,
        actor_id,
        approved.project_id,
        approved.status,
    )
    return _issue_write_response(approved)
