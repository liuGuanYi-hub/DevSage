"""Data structures shared by loaders, splitters and indexing services."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentRecord:
    """A source file loaded into the local indexing pipeline."""

    source_path: str
    file_type: str
    content_hash: str
    content: str
    line_count: int


@dataclass(frozen=True)
class ChunkRecord:
    """A searchable section with source location metadata."""

    chunk_id: str
    source_path: str
    file_type: str
    content: str
    start_line: int
    end_line: int
    metadata: dict[str, str] = field(default_factory=dict)

