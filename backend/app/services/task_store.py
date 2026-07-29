"""File-backed Agent task snapshots for the engineering MVP."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..agents.state import AgentState


class TaskStateError(RuntimeError):
    """Base error for persisted Agent task state."""


class TaskStateNotFoundError(TaskStateError):
    """Raised when a requested task snapshot does not exist."""


class TaskNotResumableError(TaskStateError):
    """Raised when a task is not in a bounded-interruption state."""


class FileTaskStateStore:
    """Persist explicit Agent snapshots under one project-relative directory."""

    _TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def save(self, state: AgentState) -> Path:
        path = self._path_for(state.task_id)
        self.root.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def load(self, task_id: str) -> AgentState:
        path = self._path_for(task_id)
        if not path.is_file():
            raise TaskStateNotFoundError(f"task state not found: {task_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return AgentState.from_dict(payload)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise TaskStateError("task state is invalid") from exc

    def _path_for(self, task_id: str) -> Path:
        if not self._TASK_ID_PATTERN.fullmatch(task_id):
            raise TaskStateError("invalid task id")
        path = (self.root / f"{task_id}.json").resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise TaskStateError("task id escaped state directory") from exc
        return path
