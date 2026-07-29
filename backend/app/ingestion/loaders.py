"""Safe local file discovery and UTF-8 document loading."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from .models import DocumentRecord


SUPPORTED_EXTENSIONS = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".java": "code",
    ".php": "code",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".vue": "code",
    ".yml": "config",
    ".yaml": "config",
    ".json": "config",
    ".properties": "config",
    ".example": "config",
}

EXCLUDED_DIRECTORIES = {
    ".git",
    ".idea",
    ".venv",
    "node_modules",
    "__pycache__",
}


def iter_source_files(
    root: str | Path,
    extensions: dict[str, str] | None = None,
) -> Iterable[Path]:
    """Yield supported files under ``root`` in deterministic path order."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"Source root does not exist: {root_path}")

    extension_map = extensions or SUPPORTED_EXTENSIONS
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root_path).parts
        if any(part in EXCLUDED_DIRECTORIES for part in relative_parts):
            continue
        if path.suffix.lower() in extension_map:
            yield path


def load_document(path: str | Path, root: str | Path) -> DocumentRecord:
    """Load one UTF-8 document and keep only a root-relative source path."""

    root_path = Path(root).expanduser().resolve()
    file_path = Path(path).expanduser().resolve()
    try:
        relative_path = file_path.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"File is outside source root: {file_path}") from exc

    file_type = SUPPORTED_EXTENSIONS.get(file_path.suffix.lower())
    if file_type is None:
        raise ValueError(f"Unsupported file extension: {file_path.suffix}")

    raw_content = file_path.read_bytes()
    content_hash = hashlib.sha256(raw_content).hexdigest()
    content = raw_content.decode("utf-8", errors="replace")
    return DocumentRecord(
        source_path=relative_path.as_posix(),
        file_type=file_type,
        content_hash=content_hash,
        content=content,
        line_count=len(content.splitlines()),
    )


def load_documents(root: str | Path) -> list[DocumentRecord]:
    """Load every supported document below a source root."""

    root_path = Path(root).expanduser().resolve()
    return [load_document(path, root_path) for path in iter_source_files(root_path)]
