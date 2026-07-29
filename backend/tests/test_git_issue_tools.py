import unittest
import subprocess
import json
import os
from unittest.mock import patch
from pathlib import Path
from urllib.error import HTTPError

from backend.app.agents.git_tools import GitToolError, get_commit_diff, get_git_history
from backend.app.agents.issue_tools import (
    ExternalIssueConfig,
    IssueToolError,
    search_external_issues,
    search_issues,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class GitIssueToolTests(unittest.TestCase):
    def test_git_history_reads_recent_local_commits(self) -> None:
        results = get_git_history(repository_path=".", limit=2)
        self.assertTrue(results)
        self.assertTrue(all(len(result.chunk.metadata["commit_hash"]) == 40 for result in results))

    def test_issue_search_returns_issue_citation(self) -> None:
        results = search_issues("Laravel 认证 401", limit=3)
        self.assertTrue(results)
        self.assertTrue(any("ISSUE-002" in result.citation for result in results))

    def test_external_issue_search_is_opt_in_and_normalizes_response(self) -> None:
        payload = {
            "items": [
                {
                    "number": 42,
                    "title": "Port binding timeout",
                    "body": "8080 port is occupied",
                    "state": "open",
                    "html_url": "https://example.test/issues/42",
                    "labels": [{"name": "incident"}],
                }
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        with patch.dict(
            os.environ,
            {
                "DEVSAGE_EXTERNAL_ISSUE_URL": "https://api.example.test",
                "DEVSAGE_EXTERNAL_ISSUE_REPOSITORY": "demo/repo",
            },
            clear=False,
        ):
            with patch(
                "backend.app.agents.issue_tools._default_external_open",
                return_value=FakeResponse(),
            ) as opener:
                results = search_issues("8080 port", limit=1)

        self.assertEqual(1, len(results))
        self.assertIn("external-issues/demo/repo/42", results[0].citation)
        self.assertEqual("demo/repo", results[0].chunk.metadata["repository"])
        request = opener.call_args.args[0]
        self.assertIn("repo%3Ademo%2Frepo", request.full_url)
        self.assertNotIn("Authorization", request.headers)

    def test_external_issue_http_auth_error_is_sanitized(self) -> None:
        with self.assertRaisesRegex(IssueToolError, "rejected"):
            search_external_issues(
                "timeout",
                config=ExternalIssueConfig(
                    api_url="https://api.example.test",
                    repository="demo/repo",
                ),
                opener=lambda _request, _timeout: (_ for _ in ()).throw(
                    HTTPError("https://api.example.test", 401, "secret body", {}, None)
                ),
            )

    def test_git_history_rejects_path_escape(self) -> None:
        with self.assertRaises(GitToolError):
            get_git_history(repository_path="../", limit=1)

    def test_commit_diff_is_bounded_and_cited(self) -> None:
        history = get_git_history(repository_path=".", limit=1)
        result = get_commit_diff(history[0].chunk.metadata["commit_hash"], max_lines=10)
        self.assertEqual("git_diff", result.chunk.file_type)
        self.assertIn("git-diff", result.matched_terms)
        self.assertLessEqual(result.chunk.end_line, 11)

    def test_commit_diff_rejects_path_escape_and_bad_hash(self) -> None:
        with self.assertRaises(GitToolError):
            get_commit_diff("not-a-commit")
        with self.assertRaises(GitToolError):
            get_commit_diff("faedcf2", path="../README.md")

    def test_git_tools_convert_timeout_to_safe_error(self) -> None:
        with patch(
            "backend.app.agents.git_tools.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git"], 0.01),
        ):
            with self.assertRaisesRegex(GitToolError, "timed out"):
                get_git_history(limit=1, timeout_seconds=0.01)


if __name__ == "__main__":
    unittest.main()
