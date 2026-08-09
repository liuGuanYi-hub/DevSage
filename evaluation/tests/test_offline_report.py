import unittest

from evaluation.scripts.generate_offline_report import render_markdown


class OfflineReportRenderingTests(unittest.TestCase):
    def test_render_markdown_contains_stable_baseline_sections(self) -> None:
        report = {
            "dataset": {
                "path": "evaluation/datasets/devmind_mvp_questions.json",
                "questions": 50,
                "sha256": "a" * 64,
            },
            "metrics": {
                "agent_grounding": {
                    "source_recall_at_5": 1.0,
                    "full_source_case_rate": 1.0,
                    "failure_count": 0,
                    "failures": [],
                },
                "tool_call_accuracy": {
                    "expected_tool_coverage": 1.0,
                    "fully_covered_case_rate": 1.0,
                },
                "context_quality": {
                    "context_precision_at_5": 1.0,
                    "context_recall_at_5": 1.0,
                    "answer_relevance_proxy_f1": 1.0,
                    "faithfulness_proxy_precision": 1.0,
                    "failure_count": 0,
                    "failures": [],
                },
                "retrieval_strategies": {
                    "keyword": {
                        "case_recall_at_5": 1.0,
                        "source_recall_at_5": 1.0,
                        "mrr": 1.0,
                    }
                },
            },
            "interpretation": {
                "embedding": "offline Hash baseline",
                "faithfulness": "lexical proxy",
                "external_services": "not used",
            },
        }

        rendered = render_markdown(report)

        self.assertIn("# DevSage 离线 MVP 评估基线", rendered)
        self.assertIn("问题数：`50`", rendered)
        self.assertIn("Agent Source Recall@5", rendered)
        self.assertIn("| keyword | `1.0000` | `1.0000` | `1.0000` |", rendered)
        self.assertIn("- 无", rendered)


if __name__ == "__main__":
    unittest.main()
