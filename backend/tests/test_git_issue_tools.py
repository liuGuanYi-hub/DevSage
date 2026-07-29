import unittest
from pathlib import Path

from backend.app.agents.git_tools import GitToolError, get_git_history
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


if __name__ == "__main__":
    unittest.main()
