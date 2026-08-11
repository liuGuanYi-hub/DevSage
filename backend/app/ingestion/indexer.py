"""Build a deterministic index snapshot from local project data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .chunkers import CHUNK_METADATA_VERSION, split_document
from .loaders import load_documents
from .models import ChunkRecord, DocumentRecord


@dataclass(frozen=True)
class IndexSnapshot:
    """Documents and searchable Chunks produced by one indexing run."""

    documents: tuple[DocumentRecord, ...]
    chunks: tuple[ChunkRecord, ...]
    stats: "IndexBuildStats | None" = None


@dataclass(frozen=True)
class IndexBuildStats:
    """Explain how a snapshot changed compared with a previous snapshot."""

    added_documents: int = 0
    changed_documents: int = 0
    unchanged_documents: int = 0
    removed_documents: int = 0


def build_index(
    root: str | Path,
    previous: IndexSnapshot | None = None,
) -> IndexSnapshot:
    """Load, split and return a deterministic local index snapshot.

    When ``previous`` is supplied, unchanged documents reuse their existing
    Chunks and the returned stats describe added, changed, unchanged and
    removed files.
    """

    documents = load_documents(root)
    previous_documents = {
        document.source_path: document for document in (previous.documents if previous else ())
    }
    previous_chunks: dict[str, list[ChunkRecord]] = {}
    if previous:
        for chunk in previous.chunks:
            previous_chunks.setdefault(chunk.source_path, []).append(chunk)

    chunks: list[ChunkRecord] = []
    added = changed = unchanged = 0
    for document in documents:
        old_document = previous_documents.get(document.source_path)
        if old_document is None:
            added += 1
            chunks.extend(split_document(document))
        elif (
            old_document.content_hash == document.content_hash
            and previous_chunks.get(document.source_path)
            and all(
                chunk.metadata.get("metadata_version") == CHUNK_METADATA_VERSION
                for chunk in previous_chunks[document.source_path]
            )
        ):
            unchanged += 1
            chunks.extend(previous_chunks.get(document.source_path, []))
        else:
            changed += 1
            chunks.extend(split_document(document))

    current_paths = {document.source_path for document in documents}
    removed = len(set(previous_documents) - current_paths)
    stats = IndexBuildStats(added, changed, unchanged, removed)
    return IndexSnapshot(tuple(documents), tuple(chunks), stats)
