import unittest

from evaluation.scripts.evaluate_context_quality import (
    lexical_f1,
    lexical_precision,
    lexical_recall,
)


class ContextQualityMetricTests(unittest.TestCase):
    def test_lexical_precision_handles_empty_candidate(self) -> None:
        self.assertEqual(0.0, lexical_precision("", "reference"))

    def test_lexical_f1_is_one_for_same_terms(self) -> None:
        self.assertEqual(1.0, lexical_f1("8080 端口", "8080 端口"))

    def test_lexical_f1_is_bounded_for_partial_overlap(self) -> None:
        score = lexical_f1("8080 端口 PID", "8080 端口")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_lexical_recall_measures_reference_coverage(self) -> None:
        self.assertEqual(1.0, lexical_recall("8080 端口 PID", "8080 端口"))


if __name__ == "__main__":
    unittest.main()
