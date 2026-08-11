"""Structure-aware Chunk generation for Markdown, code and config files."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from pathlib import Path

from .models import ChunkRecord, DocumentRecord


MARKDOWN_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
CODE_BOUNDARY = re.compile(
    r"^\s*(?:(?:public|private|protected|static|async|export)\s+)*"
    r"(?:class|interface|trait|def\s+\w+|function\s+\w+|[\w<>\[\],?]+\s+\w+\s*\([^;]*\)\s*\{)"
)
CHUNK_METADATA_VERSION = "2"
CLASS_SYMBOL = re.compile(r"\b(class|interface|trait)\s+([A-Za-z_]\w*)")
FUNCTION_SYMBOL = re.compile(
    r"\b(?:def|function)\s+([A-Za-z_]\w*)|\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:\{|$)"
)


def _infer_document_role(document: DocumentRecord) -> str:
    """Infer a conservative file responsibility for retrieval metadata."""

    path = document.source_path.replace("\\", "/")
    lowered = path.lower()
    file_name = Path(path).name.lower()
    if "/issues/" in f"/{lowered}" or lowered.startswith("issues/"):
        return "issue-record"
    if "/git/" in f"/{lowered}" or lowered.startswith("git/"):
        return "git-history"
    if file_name == "readme.md":
        return "project-overview"
    if "controller" in lowered:
        return "api-entry"
    if "middleware" in lowered:
        return "authentication-boundary"
    if "/routes/" in lowered or file_name.startswith("routes."):
        return "route-definition"
    if "service" in lowered:
        return "business-service"
    if file_name in {".env.example", "application.yml", "application.yaml"}:
        return "runtime-configuration"
    if document.file_type == "markdown":
        return "knowledge-document"
    if document.file_type == "code":
        return "implementation-code"
    if document.file_type == "config":
        return "configuration"
    return "source-document"


def _base_metadata(document: DocumentRecord) -> dict[str, str]:
    source = Path(document.source_path.replace("\\", "/"))
    parent = source.parent.as_posix()
    if parent == ".":
        parent = ""
    return {
        "metadata_version": CHUNK_METADATA_VERSION,
        "file_name": source.name,
        "directory": parent,
        "document_role": _infer_document_role(document),
        "source_kind": document.file_type,
        "line_count": str(document.line_count),
    }


def _structure_metadata(structure: str) -> dict[str, str]:
    """Expose symbols so code-location queries can match file responsibilities."""

    metadata = {"structure": structure, "chunk_role": "code-structure"}
    class_match = CLASS_SYMBOL.search(structure)
    if class_match:
        metadata.update({"symbol_kind": class_match.group(1), "symbol": class_match.group(2)})
        return metadata
    function_match = FUNCTION_SYMBOL.search(structure)
    if function_match:
        symbol = function_match.group(1) or function_match.group(2)
        if symbol:
            metadata.update({"symbol_kind": "function-or-method", "symbol": symbol})
    return metadata


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
    chunk_metadata = _base_metadata(document)
    chunk_metadata.update(metadata or {})
    chunk_metadata["line_range"] = f"{start + 1}-{end}"
    return ChunkRecord(
        chunk_id=chunk_id,
        source_path=document.source_path,
        file_type=document.file_type,
        content=content,
        start_line=start + 1,
        end_line=end,
        metadata=chunk_metadata,
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
    heading_stack: list[tuple[int, str]] = []
    for index, line in enumerate(document.content.splitlines()):
        match = MARKDOWN_HEADING.match(line)
        if match:
            level = len(match.group(1))
            heading = match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading))
            boundaries.append(
                (
                    index,
                    {
                        "heading_level": str(level),
                        "heading": heading,
                        "section_title": heading,
                        "heading_path": " / ".join(item[1] for item in heading_stack),
                        "chunk_role": "markdown-section",
                    },
                )
            )
    return _split_by_boundaries(document, boundaries, max_lines)


def split_code(document: DocumentRecord, max_lines: int = 80) -> list[ChunkRecord]:
    """Split source code around common class, method and function boundaries."""

    boundaries: list[tuple[int, dict[str, str]]] = []
    for index, line in enumerate(document.content.splitlines()):
        if CODE_BOUNDARY.match(line):
            boundaries.append((index, _structure_metadata(line.strip())))
    return _split_by_boundaries(document, boundaries, max_lines)


def split_document(document: DocumentRecord, max_lines: int = 80) -> list[ChunkRecord]:
    """Choose a content-aware splitter for one document."""

    if document.file_type == "markdown":
        return split_markdown(document, max_lines=max_lines)
    if document.file_type == "code":
        return split_code(document, max_lines=max_lines)
    return _split_by_boundaries(document, [], max_lines)
