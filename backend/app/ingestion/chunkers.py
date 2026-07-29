"""Structure-aware Chunk generation for Markdown, code and config files."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from .models import ChunkRecord, DocumentRecord


MARKDOWN_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
CODE_BOUNDARY = re.compile(
    r"^\s*(?:(?:public|private|protected|static|async|export)\s+)*"
    r"(?:class|interface|trait|def\s+\w+|function\s+\w+|[\w<>\[\],?]+\s+\w+\s*\([^;]*\)\s*\{)"
)


def _window_ranges(start: int, end: int, max_lines: int) -> Iterable[tuple[int, int]]:
    """Yield half-open line ranges while preserving every line."""

    cursor = start
    while cursor < end:
        next_cursor = min(cursor + max_lines, end)
        yield cursor, next_cursor
        cursor = next_cursor


def _make_chunk(
    document: DocumentRecord,
    lines: list[str],
    start: int,
    end: int,
    metadata: dict[str, str] | None = None,
) -> ChunkRecord:
    content = "\n".join(lines[start:end]).strip("\n")
    chunk_seed = f"{document.source_path}:{document.content_hash}:{start + 1}:{end}"
    chunk_id = hashlib.sha256(chunk_seed.encode("utf-8")).hexdigest()[:20]
    return ChunkRecord(
        chunk_id=chunk_id,
        source_path=document.source_path,
        file_type=document.file_type,
        content=content,
        start_line=start + 1,
        end_line=end,
        metadata=metadata or {},
    )


def _split_by_boundaries(
    document: DocumentRecord,
    boundaries: list[tuple[int, dict[str, str]]],
    max_lines: int,
) -> list[ChunkRecord]:
    lines = document.content.splitlines()
    if not lines:
        return []

    starts = sorted({0, *(start for start, _ in boundaries)})
    chunks: list[ChunkRecord] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        metadata = next(
            (metadata for boundary_start, metadata in boundaries if boundary_start == start),
            {},
        )
        for window_start, window_end in _window_ranges(start, end, max_lines):
            if lines[window_start:window_end]:
                chunks.append(
                    _make_chunk(document, lines, window_start, window_end, metadata)
                )
    return chunks


def split_markdown(document: DocumentRecord, max_lines: int = 80) -> list[ChunkRecord]:
    """Split Markdown at heading boundaries and retain heading metadata."""

    boundaries: list[tuple[int, dict[str, str]]] = []
    for index, line in enumerate(document.content.splitlines()):
        match = MARKDOWN_HEADING.match(line)
        if match:
            boundaries.append(
                (
                    index,
                    {
                        "heading_level": str(len(match.group(1))),
                        "heading": match.group(2).strip(),
                    },
                )
            )
    return _split_by_boundaries(document, boundaries, max_lines)


def split_code(document: DocumentRecord, max_lines: int = 80) -> list[ChunkRecord]:
    """Split source code around common class, method and function boundaries."""

    boundaries: list[tuple[int, dict[str, str]]] = []
    for index, line in enumerate(document.content.splitlines()):
        if CODE_BOUNDARY.match(line):
            boundaries.append((index, {"structure": line.strip()}))
    return _split_by_boundaries(document, boundaries, max_lines)


def split_document(document: DocumentRecord, max_lines: int = 80) -> list[ChunkRecord]:
    """Choose a content-aware splitter for one document."""

    if document.file_type == "markdown":
        return split_markdown(document, max_lines=max_lines)
    if document.file_type == "code":
        return split_code(document, max_lines=max_lines)
    return _split_by_boundaries(document, [], max_lines)

