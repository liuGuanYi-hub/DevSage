"""Preview and approved-write service for generated Markdown notes."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import hashlib
from pathlib import Path
from uuid import uuid4


class WritebackPolicyError(ValueError):
    """Raised when a requested knowledge write violates the safety policy."""


@dataclass(frozen=True)
class NoteDiff:
    """Describe the exact change that an approval would apply."""

    operation: str
    target_exists: bool
    current_content_hash: str | None
    proposed_content_hash: str
    additions: int
    deletions: int
    unified_diff: tuple[str, ...]


@dataclass(frozen=True)
class NotePreview:
    preview_id: str
    title: str
    target_path: str
    content: str
    source_citations: tuple[str, ...]
    diff: NoteDiff
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

    def _resolve_destination(self, target_path: str) -> Path:
        destination = (self.note_root / target_path).resolve()
        try:
            destination.relative_to(self.note_root)
        except ValueError as exc:
            raise WritebackPolicyError("target_path escaped the note root") from exc
        return destination

    @staticmethod
    def _content_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _build_diff(self, target_path: str, content: str) -> NoteDiff:
        destination = self._resolve_destination(target_path)
        proposed_bytes = (content + "\n").encode("utf-8")
        target_exists = destination.is_file()
        current_bytes = destination.read_bytes() if target_exists else b""
        current_text = current_bytes.decode("utf-8", errors="replace")
        proposed_text = proposed_bytes.decode("utf-8")
        diff_lines = tuple(
            difflib.unified_diff(
                current_text.splitlines(),
                proposed_text.splitlines(),
                fromfile=target_path if target_exists else "/dev/null",
                tofile=target_path,
                lineterm="",
            )
        )
        additions = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )
        if not target_exists:
            operation = "create"
        elif current_bytes == proposed_bytes:
            operation = "noop"
        else:
            operation = "update"
        return NoteDiff(
            operation=operation,
            target_exists=target_exists,
            current_content_hash=self._content_hash(current_bytes) if target_exists else None,
            proposed_content_hash=self._content_hash(proposed_bytes),
            additions=additions,
            deletions=deletions,
            unified_diff=diff_lines,
        )

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
            diff=self._build_diff(safe_target, clean_content),
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
        if preview.status != "pending":
            raise WritebackPolicyError("preview has already been approved")
        destination = self._resolve_destination(preview.target_path)
        current_diff = self._build_diff(preview.target_path, preview.content)
        if current_diff.current_content_hash != preview.diff.current_content_hash:
            raise WritebackPolicyError(
                "target changed after preview; create a new preview before approval"
            )
        if current_diff.operation != "noop":
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(preview.content + "\n", encoding="utf-8")
        approved = NotePreview(
            preview_id=preview.preview_id,
            title=preview.title,
            target_path=preview.target_path,
            content=preview.content,
            source_citations=preview.source_citations,
            diff=preview.diff,
            status="approved",
        )
        self._previews[preview_id] = approved
        return approved
