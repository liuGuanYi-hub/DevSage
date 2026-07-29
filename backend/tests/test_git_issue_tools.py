import unittest
import subprocess
from unittest.mock import patch
from pathlib import Path

from backend.app.agents.git_tools import GitToolError, get_commit_diff, get_git_history
from backend.app.agents.issue_tools import search_issues


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
