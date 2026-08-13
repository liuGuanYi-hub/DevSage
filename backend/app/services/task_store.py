"""File-backed Agent task snapshots for the engineering MVP."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..agents.state import AgentState


class TaskStateError(RuntimeError):
    """Base error for persisted Agent task state."""


class TaskStateNotFoundError(TaskStateError):
    """Raised when a requested task snapshot does not exist."""


class TaskNotResumableError(TaskStateError):
    """Raised when a task is not in a bounded-interruption state."""


class TaskStateStorageError(TaskStateError):
    """Raised when the configured task-state database is unavailable."""


def task_summary(state: AgentState) -> dict[str, object]:
    """Return a safe, lightweight task record for history screens."""

    return {
        "task_id": state.task_id,
        "query": state.query,
        "source_root": state.source_root,
        "project_id": state.project_id,
        "category": state.category,
        "status": state.status,
        "tool_calls": len(state.tool_calls),
        "step_count": len(state.steps),
        "runtime_ms": state.usage.runtime_ms,
        "evidence_count": len(state.evidence),
        "resumable": state.status in {"tool_limit_reached", "step_limit_reached", "task_timeout"},
    }


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

    def list(self, project_id: str | None = None, limit: int = 50) -> list[dict[str, object]]:
        """List persisted task summaries newest-first without loading full answers into the API."""

        if limit < 1:
            raise TaskStateError("limit must be positive")
        if not self.root.is_dir():
            return []
        summaries: list[dict[str, object]] = []
        for path in sorted(self.root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                state = AgentState.from_dict(payload)
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise TaskStateError("task state is invalid") from exc
            if project_id and state.project_id != project_id:
                continue
            summaries.append(task_summary(state))
            if len(summaries) >= limit:
                break
        return summaries

    def _path_for(self, task_id: str) -> Path:
        if not self._TASK_ID_PATTERN.fullmatch(task_id):
            raise TaskStateError("invalid task id")
        path = (self.root / f"{task_id}.json").resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise TaskStateError("task id escaped state directory") from exc
        return path


class PostgresTaskStateStore:
    """Persist Agent snapshots as JSONB when PostgreSQL storage is enabled."""

    _TASK_ID_PATTERN = FileTaskStateStore._TASK_ID_PATTERN

    def __init__(
        self,
        database_url: str | None = None,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", "").strip()
        self._connection_factory = connection_factory
        self._initialized = False

    def _connect(self):
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self.database_url:
            raise TaskStateStorageError("DATABASE_URL is not configured")
        database_url = self.database_url.replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
        try:
            import psycopg
        except ImportError as exc:
            raise TaskStateStorageError(
                "psycopg is required only when PostgreSQL task storage is enabled"
            ) from exc
        try:
            return psycopg.connect(database_url)
        except Exception as exc:
            raise TaskStateStorageError("PostgreSQL task storage connection failed") from exc

    def initialize(self) -> None:
        """Create the task table without requiring the vector tables first."""

        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_tasks (
                        task_id TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        source_root TEXT NOT NULL,
                        category TEXT NOT NULL,
                        status TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS agent_tasks_status_idx
                        ON agent_tasks (status, updated_at DESC)
                    """
                )
            connection.commit()
            self._initialized = True
        except Exception as exc:
            connection.rollback()
            raise TaskStateStorageError("PostgreSQL task table initialization failed") from exc
        finally:
            connection.close()

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    def save(self, state: AgentState) -> str:
        """Upsert one complete JSON-safe Agent state snapshot."""

        self._validate_task_id(state.task_id)
        self._ensure_initialized()
        payload = json.dumps(state.to_dict(), ensure_ascii=False)
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO agent_tasks
                        (task_id, query, source_root, category, status, payload)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (task_id) DO UPDATE
                    SET query = EXCLUDED.query,
                        source_root = EXCLUDED.source_root,
                        category = EXCLUDED.category,
                        status = EXCLUDED.status,
                        payload = EXCLUDED.payload,
                        updated_at = NOW()
                    """,
                    (
                        state.task_id,
                        state.query,
                        state.source_root,
                        state.category,
                        state.status,
                        payload,
                    ),
                )
            connection.commit()
            return state.task_id
        except Exception as exc:
            connection.rollback()
            raise TaskStateStorageError("PostgreSQL task state save failed") from exc
        finally:
            connection.close()

    def load(self, task_id: str) -> AgentState:
        """Load and validate one task snapshot from JSONB."""

        self._validate_task_id(task_id)
        self._ensure_initialized()
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM agent_tasks WHERE task_id = %s",
                    (task_id,),
                )
                row = cursor.fetchone()
            if row is None:
                raise TaskStateNotFoundError(f"task state not found: {task_id}")
            payload = row[0]
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, dict):
                raise ValueError("task payload must be an object")
            return AgentState.from_dict(payload)
        except TaskStateNotFoundError:
            raise
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise TaskStateError("task state is invalid") from exc
        except Exception as exc:
            raise TaskStateStorageError("PostgreSQL task state load failed") from exc
        finally:
            connection.close()

    def list(self, project_id: str | None = None, limit: int = 50) -> list[dict[str, object]]:
        """List task summaries ordered by the durable update timestamp."""

        if limit < 1:
            raise TaskStateError("limit must be positive")
        self._ensure_initialized()
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                if project_id:
                    cursor.execute(
                        """
                        SELECT payload FROM agent_tasks
                        WHERE payload->>'project_id' = %s
                        ORDER BY updated_at DESC
                        LIMIT %s
                        """,
                        (project_id, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT payload FROM agent_tasks
                        ORDER BY updated_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                rows = cursor.fetchall()
            summaries: list[dict[str, object]] = []
            for (payload,) in rows:
                if isinstance(payload, str):
                    payload = json.loads(payload)
                if not isinstance(payload, dict):
                    raise ValueError("task payload must be an object")
                summaries.append(task_summary(AgentState.from_dict(payload)))
            return summaries
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise TaskStateError("task state is invalid") from exc
        except Exception as exc:
            raise TaskStateStorageError("PostgreSQL task history load failed") from exc
        finally:
            connection.close()

    @classmethod
    def _validate_task_id(cls, task_id: str) -> None:
        if not cls._TASK_ID_PATTERN.fullmatch(task_id):
            raise TaskStateError("invalid task id")
