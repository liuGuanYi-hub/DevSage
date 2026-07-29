"""Preview and approved-write service for generated Markdown notes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


class WritebackPolicyError(ValueError):
    """Raised when a requested knowledge write violates the safety policy."""


@dataclass(frozen=True)
class NotePreview:
    preview_id: str
    title: str
    target_path: str
    content: str
    source_citations: tuple[str, ...]
    status: str = "pending"


def validate_target_path(target_path: str) -> str:
    """Allow only relative Markdown paths inside the configured note root."""

    candidate = Path(target_path)
    if candidate.is_absolute():
        raise WritebackPolicyError("target_path must be relative")
    if candidate.suffix.lower() != ".md":
        raise WritebackPolicyError("target_path must end with .md")
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise WritebackPolicyError("target_path contains an invalid path segment")
    if any(part.startswith(".") for part in candidate.parts):
        raise WritebackPolicyError("hidden target paths are not allowed")
    return candidate.as_posix()


class KnowledgeWritebackService:
    """Keep previews in memory and write only after explicit approval."""

    def __init__(self, note_root: str | Path) -> None:
        self.note_root = Path(note_root).expanduser().resolve()
        self._previews: dict[str, NotePreview] = {}

    def create_preview(
        self,
        title: str,
        content: str,
        target_path: str,
        source_citations: list[str],
    ) -> NotePreview:
        clean_title = title.strip()
        clean_content = content.strip()
        if not clean_title:
            raise WritebackPolicyError("title must not be empty")
        if not clean_content:
            raise WritebackPolicyError("content must not be empty")

        safe_target = validate_target_path(target_path)
        preview = NotePreview(
            preview_id=uuid4().hex,
            title=clean_title,
            target_path=safe_target,
            content=clean_content,
            source_citations=tuple(source_citations),
        )
        self._previews[preview.preview_id] = preview
        return preview

    def get_preview(self, preview_id: str) -> NotePreview:
        try:
            return self._previews[preview_id]
        except KeyError as exc:
            raise WritebackPolicyError("preview does not exist") from exc

    def approve(self, preview_id: str) -> NotePreview:
        preview = self.get_preview(preview_id)
        destination = (self.note_root / preview.target_path).resolve()
        try:
            destination.relative_to(self.note_root)
        except ValueError as exc:
            raise WritebackPolicyError("target_path escaped the note root") from exc

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(preview.content + "\n", encoding="utf-8")
        approved = NotePreview(
            preview_id=preview.preview_id,
            title=preview.title,
            target_path=preview.target_path,
            content=preview.content,
            source_citations=preview.source_citations,
            status="approved",
        )
        self._previews[preview_id] = approved
        return approved

