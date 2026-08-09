"""Explicit preview and approval workflow for external Issue creation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any, Callable
from uuid import uuid4

from ..agents.issue_tools import (
    ExternalIssueConfig,
    IssueToolError,
    load_external_issue_write_config,
)


class IssueWritePolicyError(ValueError):
    """Raised when a remote Issue write violates the explicit approval policy."""


@dataclass(frozen=True)
class IssueWritePreview:
    preview_id: str
    project_id: str | None
    title: str
    body: str
    labels: tuple[str, ...]
    status: str = "pending"
    remote_number: str | None = None
    remote_url: str | None = None


IssueWriteOpen = Callable[[Request, float], Any]


class ExternalIssueWritebackService:
    """Never issue a remote request during preview; approval is the only write edge."""

    def __init__(self, opener: IssueWriteOpen | None = None) -> None:
        self._previews: dict[str, IssueWritePreview] = {}
        self._opener = opener or _default_open

    def create_preview(
        self,
        title: str,
        body: str,
        labels: list[str],
        project_id: str | None = None,
    ) -> IssueWritePreview:
        clean_title = title.strip()
        clean_body = body.strip()
        if not 1 <= len(clean_title) <= 200:
            raise IssueWritePolicyError("Issue title must contain 1 to 200 characters")
        if not 1 <= len(clean_body) <= 10_000:
            raise IssueWritePolicyError("Issue body must contain 1 to 10000 characters")
        clean_labels: list[str] = []
        for label in labels[:10]:
            clean_label = label.strip()
            if clean_label and len(clean_label) <= 50 and re.fullmatch(r"[^\r\n]+", clean_label):
                clean_labels.append(clean_label)
            elif clean_label:
                raise IssueWritePolicyError("Issue labels contain an invalid value")
        preview = IssueWritePreview(
            preview_id=uuid4().hex,
            project_id=project_id,
            title=clean_title,
            body=clean_body,
            labels=tuple(dict.fromkeys(clean_labels)),
        )
        self._previews[preview.preview_id] = preview
        return preview

    def get_preview(self, preview_id: str) -> IssueWritePreview:
        try:
            return self._previews[preview_id]
        except KeyError as exc:
            raise IssueWritePolicyError("Issue write preview does not exist") from exc

    def approve(self, preview_id: str) -> IssueWritePreview:
        preview = self.get_preview(preview_id)
        if preview.status != "pending":
            raise IssueWritePolicyError("Issue write preview has already been submitted")
        try:
            config = load_external_issue_write_config()
        except IssueToolError as exc:
            raise IssueWritePolicyError(str(exc)) from exc
        token = os.getenv(config.token_env, "").strip()
        request = Request(
            self._create_url(config),
            data=json.dumps(
                {"title": preview.title, "body": preview.body, "labels": list(preview.labels)},
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "DevSage/0.1",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with self._opener(request, config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise IssueWritePolicyError("external Issue platform rejected the write") from exc
            raise IssueWritePolicyError("external Issue write failed") from exc
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            raise IssueWritePolicyError("external Issue write failed or timed out") from exc
        if not isinstance(payload, dict) or payload.get("number") is None:
            raise IssueWritePolicyError("external Issue response has no Issue number")
        submitted = IssueWritePreview(
            preview_id=preview.preview_id,
            project_id=preview.project_id,
            title=preview.title,
            body=preview.body,
            labels=preview.labels,
            status="created",
            remote_number=str(payload["number"]),
            remote_url=str(payload.get("html_url") or "") or None,
        )
        self._previews[preview_id] = submitted
        return submitted

    @staticmethod
    def _create_url(config: ExternalIssueConfig) -> str:
        return f"{config.api_url.rstrip('/')}/repos/{config.repository}/issues"


def _default_open(request: Request, timeout: float):
    return urlopen(request, timeout=timeout)
