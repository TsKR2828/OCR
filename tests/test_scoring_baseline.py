import json
import unittest

from tests.scoring_harness import GOLDEN_PATH, generate_scoring_baseline


class ScoringBaselineSnapshotTests(unittest.TestCase):
    def test_current_candidates_match_golden_and_are_deterministic(self):
        expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

        first = generate_scoring_baseline()
        second = generate_scoring_baseline()

        self.assertEqual(first, second)
        self.assertEqual(first, expected)


if __name__ == "__main__":
    unittest.main()
