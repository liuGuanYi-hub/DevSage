import unittest

from evaluation.scripts.evaluate_agent_grounding import evaluate


class AgentGroundingEvaluationTests(unittest.TestCase):
    def test_agent_grounding_stays_above_mvp_baseline(self) -> None:
        metrics = evaluate()

        self.assertGreaterEqual(metrics["source_recall_at_5"], 0.90)
        self.assertGreaterEqual(metrics["full_source_case_rate"], 0.80)


if __name__ == "__main__":
    unittest.main()
