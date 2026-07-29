"""Local persistence for deterministic index snapshots in offline mode."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from ..ingestion.indexer import IndexSnapshot
from ..ingestion.models import ChunkRecord, DocumentRecord


class FileIndexSnapshotStore:
    """Persist index documents and chunks so Hash-based reuse survives restart."""

    FORMAT_VERSION = 1

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def _path_for(self, source_root: str) -> Path:
        digest = hashlib.sha256(source_root.encode("utf-8")).hexdigest()[:24]
        return self.root / f"{digest}.json"

    def load(self, source_root: str) -> IndexSnapshot | None:
        path = self._path_for(source_root)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (
                payload.get("format_version") != self.FORMAT_VERSION
                or payload.get("source_root") != source_root
            ):
                return None
            documents = tuple(
                DocumentRecord(**document) for document in payload["documents"]
            )
            chunks = tuple(ChunkRecord(**chunk) for chunk in payload["chunks"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return IndexSnapshot(documents=documents, chunks=chunks)

    def save(self, source_root: str, snapshot: IndexSnapshot) -> Path:
        payload = {
            "format_version": self.FORMAT_VERSION,
            "source_root": source_root,
            "documents": [
                {
                    "source_path": document.source_path,
                    "file_type": document.file_type,
                    "content_hash": document.content_hash,
                    "content": document.content,
                    "line_count": document.line_count,
                }
                for document in snapshot.documents
            ],
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "source_path": chunk.source_path,
                    "file_type": chunk.file_type,
                    "content": chunk.content,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "metadata": chunk.metadata,
                }
                for chunk in snapshot.chunks
            ],
        }
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self._path_for(source_root)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return destination
