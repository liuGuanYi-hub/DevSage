"""Preview and approve bounded code-file changes."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import hashlib
from pathlib import Path
from uuid import uuid4


class CodeChangePolicyError(ValueError):
    """Raised when a proposed code change violates the approval policy."""


@dataclass(frozen=True)
class CodeChangeDiff:
    operation: str
    current_content_hash: str
    proposed_content_hash: str
    additions: int
    deletions: int
    unified_diff: tuple[str, ...]


@dataclass(frozen=True)
class CodeChangePreview:
    preview_id: str
    source_root: str
    project_id: str | None
    target_path: str
    proposed_content: str
    source_citations: tuple[str, ...]
    diff: CodeChangeDiff
    status: str = "pending"


class CodeChangeWritebackService:
    """Keep code previews in memory and write only after explicit approval."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self._previews: dict[str, CodeChangePreview] = {}

    def _resolve_source_root(self, source_root: str) -> Path:
        requested = Path(source_root)
        if requested.is_absolute() or any(part in {"", ".", ".."} for part in requested.parts):
            raise CodeChangePolicyError("source_root must stay inside the workspace")
        resolved = (self.workspace_root / requested).resolve()
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise CodeChangePolicyError("source_root escaped the workspace") from exc
        if not resolved.is_dir():
            raise CodeChangePolicyError("source_root is not a directory")
        return resolved

    def _resolve_target(self, source_root: str, target_path: str) -> tuple[Path, str]:
        root = self._resolve_source_root(source_root)
        requested = Path(target_path)
        if requested.is_absolute() or any(part in {"", ".", ".."} for part in requested.parts):
            raise CodeChangePolicyError("target_path must stay inside source_root")
        if any(part.startswith(".") for part in requested.parts):
            raise CodeChangePolicyError("hidden target paths are not allowed")
        destination = (root / requested).resolve()
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise CodeChangePolicyError("target_path escaped source_root") from exc
        if not destination.is_file():
            raise CodeChangePolicyError("target_path must reference an existing file")
        return destination, requested.as_posix()

    @staticmethod
    def _content_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def create_preview(
        self,
        source_root: str,
        target_path: str,
        proposed_content: str,
        source_citations: list[str],
        project_id: str | None = None,
    ) -> CodeChangePreview:
        if not proposed_content.strip():
            raise CodeChangePolicyError("proposed_content must not be empty")
        destination, safe_target = self._resolve_target(source_root, target_path)
        current_bytes = destination.read_bytes()
        proposed_bytes = proposed_content.encode("utf-8")
        current_text = current_bytes.decode("utf-8", errors="replace")
        proposed_text = proposed_bytes.decode("utf-8")
        diff_lines = tuple(
            difflib.unified_diff(
                current_text.splitlines(),
                proposed_text.splitlines(),
                fromfile=safe_target,
                tofile=safe_target,
                lineterm="",
            )
        )
        additions = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )
        diff = CodeChangeDiff(
            operation="noop" if current_bytes == proposed_bytes else "update",
            current_content_hash=self._content_hash(current_bytes),
            proposed_content_hash=self._content_hash(proposed_bytes),
            additions=additions,
            deletions=deletions,
            unified_diff=diff_lines,
        )
        preview = CodeChangePreview(
            preview_id=uuid4().hex,
            source_root=Path(source_root).as_posix(),
            project_id=project_id,
            target_path=safe_target,
            proposed_content=proposed_content,
            source_citations=tuple(source_citations),
            diff=diff,
        )
        self._previews[preview.preview_id] = preview
        return preview

    def get_preview(self, preview_id: str) -> CodeChangePreview:
        try:
            return self._previews[preview_id]
        except KeyError as exc:
            raise CodeChangePolicyError("code change preview does not exist") from exc

    def approve(self, preview_id: str) -> CodeChangePreview:
        preview = self.get_preview(preview_id)
        if preview.status != "pending":
            raise CodeChangePolicyError("code change preview has already been approved")
        destination, _ = self._resolve_target(preview.source_root, preview.target_path)
        current_bytes = destination.read_bytes()
        if self._content_hash(current_bytes) != preview.diff.current_content_hash:
            raise CodeChangePolicyError(
                "target changed after preview; create a new code change preview before approval"
            )
        proposed_bytes = preview.proposed_content.encode("utf-8")
        if current_bytes != proposed_bytes:
            destination.write_bytes(proposed_bytes)
        approved = CodeChangePreview(
            preview_id=preview.preview_id,
            source_root=preview.source_root,
            project_id=preview.project_id,
            target_path=preview.target_path,
            proposed_content=preview.proposed_content,
            source_citations=preview.source_citations,
            diff=preview.diff,
            status="approved",
        )
        self._previews[preview_id] = approved
        return approved
