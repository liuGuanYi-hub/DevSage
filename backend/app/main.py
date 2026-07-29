"""DevSage API entrypoint.

阶段 0 只提供健康检查和项目列表占位接口，方便后续接入真实服务。
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException

from .schemas.search import (
    IndexRequest,
    IndexResponse,
    KnowledgeNotePreviewRequest,
    KnowledgeNotePreviewResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from .services.index_service import IndexService, SourceRootError
from .services.knowledge_writeback import KnowledgeWritebackService, WritebackPolicyError


PROJECT_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(
    title="DevSage API",
    version="0.1.0",
    description="研发知识库与故障排查系统 API",
)

index_service = IndexService()
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

    hits = [
        SearchHit(
            citation=result.citation,
            source_path=result.chunk.source_path,
            start_line=result.chunk.start_line,
            end_line=result.chunk.end_line,
            score=result.score,
            matched_terms=list(result.matched_terms),
            content=result.chunk.content,
        )
        for result in results
    ]
    return SearchResponse(query=request.query, source_root=source_root, results=hits)


@app.post(
    "/api/knowledge-notes/preview",
    response_model=KnowledgeNotePreviewResponse,
    tags=["knowledge-notes"],
)
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


@app.post(
    "/api/knowledge-notes/{preview_id}/approve",
    response_model=KnowledgeNotePreviewResponse,
    tags=["knowledge-notes"],
)
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
