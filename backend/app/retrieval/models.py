"""Search result models shared by retrieval strategies."""

from __future__ import annotations

from dataclasses import dataclass

from ..ingestion.models import ChunkRecord


@dataclass(frozen=True)
class SearchResult:
    chunk: ChunkRecord
    score: float
    matched_terms: tuple[str, ...]

    @property
    def citation(self) -> str:
        return f"{self.chunk.source_path}:{self.chunk.start_line}-{self.chunk.end_line}"

