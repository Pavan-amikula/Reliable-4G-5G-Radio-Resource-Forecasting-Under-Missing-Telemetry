import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_supervised import eligibility


class SupervisedRules(unittest.TestCase):
    splits = [("train", 0, 3600), ("test", 3600, 7200)]

    def test_observed_zero_is_kept(self):
        self.assertEqual(eligibility("development", 0, 15, {0:0,900:0}, self.splits), ("train",None))

    def test_exact_future_required_despite_later_observation(self):
        self.assertEqual(eligibility("development", 0, 15, {0:2,1800:3}, self.splits), (None,"missing_future_target"))

    def test_current_must_be_observed(self):
        self.assertEqual(eligibility("development", 900, 15, {0:2,1800:3}, self.splits), (None,"missing_current"))

    def test_purge_even_when_boundary_label_exists(self):
        self.assertEqual(eligibility("development", 2700, 15, {2700:2,3600:3}, self.splits), (None,"boundary_or_outside"))

    def test_holdout_only_allows_test(self):
        self.assertEqual(eligibility("station_holdout", 0, 15, {0:2,900:3}, self.splits), (None,"holdout_non_test"))
        self.assertEqual(eligibility("station_holdout", 3600, 15, {3600:2,4500:3}, self.splits), ("test",None))
