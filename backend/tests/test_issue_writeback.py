import json
import os
import unittest
from unittest.mock import patch

from backend.app.services.issue_writeback import (
    ExternalIssueWritebackService,
    IssueWritePolicyError,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class IssueWritebackTests(unittest.TestCase):
    def test_preview_never_calls_transport(self) -> None:
        calls = []
        service = ExternalIssueWritebackService(opener=lambda *_args: calls.append(True))
        preview = service.create_preview(
            title="Port binding timeout",
            body="8080 is occupied",
            labels=["bug", "bug"],
            project_id="sample-data",
        )
        self.assertEqual("pending", preview.status)
        self.assertEqual(("bug",), preview.labels)
        self.assertEqual([], calls)

    def test_approval_requires_explicit_write_configuration(self) -> None:
        service = ExternalIssueWritebackService()
        preview = service.create_preview("Title", "Body", [])
        with patch.dict(os.environ, {"DEVSAGE_EXTERNAL_ISSUE_WRITE_ENABLED": "false"}, clear=False):
            with self.assertRaisesRegex(IssueWritePolicyError, "disabled"):
                service.approve(preview.preview_id)

    def test_approval_posts_only_after_preview_and_sanitizes_response(self) -> None:
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({"number": 42, "html_url": "https://example.test/issues/42"})

        service = ExternalIssueWritebackService(opener=opener)
        preview = service.create_preview("Title", "Body", ["bug"])
        with patch.dict(
            os.environ,
            {
                "DEVSAGE_EXTERNAL_ISSUE_WRITE_ENABLED": "true",
                "DEVSAGE_EXTERNAL_ISSUE_URL": "https://api.example.test",
                "DEVSAGE_EXTERNAL_ISSUE_REPOSITORY": "demo/repo",
                "DEVSAGE_EXTERNAL_ISSUE_TOKEN_ENV": "DEVSAGE_TEST_ISSUE_TOKEN",
                "DEVSAGE_TEST_ISSUE_TOKEN": "test-token-only",
            },
            clear=False,
        ):
            created = service.approve(preview.preview_id)
        self.assertEqual("created", created.status)
        self.assertEqual("42", created.remote_number)
        self.assertEqual("POST", captured["request"].get_method())
        self.assertIn("/repos/demo/repo/issues", captured["request"].full_url)
        self.assertIn("Bearer test-token-only", captured["request"].headers["Authorization"])
        self.assertEqual({"title": "Title", "body": "Body", "labels": ["bug"]}, json.loads(captured["request"].data))


if __name__ == "__main__":
    unittest.main()
