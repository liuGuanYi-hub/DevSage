"""DevSage API entrypoint.

阶段 0 只提供健康检查和项目列表占位接口，方便后续接入真实服务。
"""

from pathlib import Path
import json

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
from .schemas.agent import AgentRequest, AgentResponse, AgentStepResponse
from .agents.runner import AgentRunner
from .services.index_service import IndexService, SourceRootError
from .services.answer_service import AnswerDraft, compose_evidence_answer
from .services.knowledge_writeback import KnowledgeWritebackService, WritebackPolicyError


PROJECT_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(
    title="DevSage API",
    version="0.1.0",
    description="研发知识库与故障排查系统 API",
)

index_service = IndexService()
agent_runner = AgentRunner(index_service)
writeback_service = KnowledgeWritebackService(PROJECT_ROOT / "data" / "approved-notes")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return a minimal liveness response."""

    return {"status": "ok", "service": "devsage-api"}


@app.get("/api/projects", tags=["projects"])
def list_projects() -> dict[str, object]:
    """Return an empty project list until persistence is implemented."""

    return {"items": [], "total": 0}


@app.post("/api/index", response_model=IndexResponse, tags=["index"])
def index_source(request: IndexRequest) -> IndexResponse:
    """Build an in-memory snapshot for a project-relative source directory."""

    try:
        source_root, snapshot = index_service.build(request.source_root)
    except SourceRootError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        source_root, results = index_service.search(
            request.source_root,
            request.query,
            request.top_k,
        )
    except SourceRootError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@app.post("/api/answer", response_model=AnswerResponse, tags=["answer"])
def answer_question(request: AnswerRequest) -> AnswerResponse:
    """Return a deterministic answer assembled only from direct evidence."""

    try:
        source_root, results = index_service.search_hybrid(
            request.source_root,
            request.query,
            request.top_k,
        )
    except SourceRootError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _answer_response(
        request.query,
        source_root,
        compose_evidence_answer(request.query, results),
    )


@app.post("/api/answer/stream", tags=["answer"])
def stream_answer(request: AnswerRequest) -> StreamingResponse:
    """Stream the evidence-grounded answer as Server-Sent Events."""

    try:
        source_root, results = index_service.search_hybrid(
            request.source_root,
            request.query,
            request.top_k,
        )
    except SourceRootError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        state = agent_runner.run(request.query, request.source_root, request.top_k)
    except SourceRootError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    draft = state.answer
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
        steps=[
            AgentStepResponse(name=step.name, status=step.status, detail=step.detail)
            for step in state.steps
        ],
        evidence=[_to_search_hit(result) for result in state.evidence],
    )


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
        status=preview.status,
    )
