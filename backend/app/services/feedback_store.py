"""Durable, reviewable answer feedback storage for the local MVP."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4


class FeedbackStoreError(RuntimeError):
    """Base error for feedback persistence."""


class FeedbackNotFoundError(FeedbackStoreError):
    """Raised when a feedback record is missing."""


class FeedbackAlreadyReviewedError(FeedbackStoreError):
    """Raised when a pending record has already been reviewed."""


class FeedbackStore:
    """Store feedback under DevSage data and keep approved cases out of the Vault."""

    _ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")

    def __init__(self, root: str | Path, evaluation_path: str | Path) -> None:
        self.root = Path(root).resolve()
        self.evaluation_path = Path(evaluation_path).resolve()

    def create(self, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
        feedback_id = uuid4().hex
        record = {
            "feedback_id": feedback_id,
            **payload,
            "actor_id": actor_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
            "evaluation_case_id": None,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self._path_for(feedback_id).write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return record

    def load(self, feedback_id: str) -> dict[str, Any]:
        path = self._path_for(feedback_id)
        if not path.is_file():
            raise FeedbackNotFoundError(f"feedback not found: {feedback_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FeedbackStoreError("feedback record is invalid") from exc
        if not isinstance(payload, dict):
            raise FeedbackStoreError("feedback record must be an object")
        return payload

    def list(
        self,
        project_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 200:
            raise FeedbackStoreError("feedback limit must be between 1 and 200")
        if not self.root.is_dir():
            return []
        records: list[dict[str, Any]] = []
        for path in self.root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise FeedbackStoreError("feedback record is invalid") from exc
            if not isinstance(payload, dict):
                continue
            if project_id and payload.get("project_id") != project_id:
                continue
            if status and payload.get("status") != status:
                continue
            records.append(payload)
        records.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return records[:limit]

    def approve(
        self,
        feedback_id: str,
        reviewer_id: str,
        reference_answer: str,
        expected_sources: list[str],
        expected_tools: list[str],
        reviewer_comment: str,
    ) -> dict[str, Any]:
        record = self.load(feedback_id)
        if record.get("status") != "pending":
            raise FeedbackAlreadyReviewedError("feedback has already been reviewed")
        evaluation_case_id = f"feedback-{feedback_id[:12]}"
        case = {
            "id": evaluation_case_id,
            "category": "human_feedback",
            "difficulty": "reviewed",
            "question": record["query"],
            "expected_sources": expected_sources,
            "reference_answer": reference_answer,
            "expected_tools": expected_tools,
            "feedback_id": feedback_id,
            "reviewer_id": reviewer_id,
        }
        self.evaluation_path.parent.mkdir(parents=True, exist_ok=True)
        with self.evaluation_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
        record.update(
            {
                "status": "approved",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": reviewer_id,
                "evaluation_case_id": evaluation_case_id,
                "reviewer_comment": reviewer_comment,
            }
        )
        self._path_for(feedback_id).write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return record

    def _path_for(self, feedback_id: str) -> Path:
        if not self._ID_PATTERN.fullmatch(feedback_id):
            raise FeedbackStoreError("invalid feedback id")
        return self.root / f"{feedback_id}.json"
