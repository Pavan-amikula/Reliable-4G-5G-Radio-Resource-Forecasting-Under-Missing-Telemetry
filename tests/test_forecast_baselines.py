"""Regression checks for clock alignment, availability and leakage boundaries."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "baselines", Path(__file__).resolve().parents[1] / "scripts/forecast_baselines.py")
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


class ForecastProtocolTests(unittest.TestCase):
    def test_gaps_do_not_become_lags(self):
        t = b.epoch("2025-02-10T00:00:00+00:00")
        values = {t-1800: 9, t: 12, t+3600: 99}
        self.assertIsNone(values.get(t-900))
        self.assertIsNone(values.get(t+900))
        self.assertEqual(b.predictions(values, t, 60)["persistence"], 12)

    def test_seasonal_is_aligned_to_future_target_clock(self):
        t = b.epoch("2025-02-10T00:00:00+00:00")
        values = {t-86400: 1, t+1800-86400: 7, t: 12}
        self.assertEqual(b.predictions(values, t, 30)["daily_seasonal"], 7)

    def test_missing_current_abstains_instead_of_using_stale_value(self):
        self.assertIsNone(b.predictions({0: 20}, 900, 15)["persistence"])

    def test_missing_seasonal_abstains(self):
        self.assertIsNone(b.predictions({0: 20}, 0, 15)["daily_seasonal"])

    def test_boundary_label_is_purged(self):
        splits = [("train", 0, 3600), ("tuning", 3600, 7200)]
        self.assertIsNone(b.partition(2700, 3600, splits))
        self.assertEqual(b.partition(1800, 2700, splits), "train")
        self.assertEqual(b.partition(3600, 4500, splits), "tuning")

    def test_future_changes_do_not_change_predictions(self):
        t = 86400
        past = {t: 10, 900: 3}
        self.assertEqual(b.predictions(past, t, 15),
                         b.predictions(past | {t+900: 100, t+1800: 0}, t, 15))

    def test_naive_timestamps_are_utc_and_off_grid_fails(self):
        self.assertEqual(b.epoch("2025-02-10 00:00:00"),
                         b.epoch("2025-02-10T00:00:00+00:00"))
        with self.assertRaises(ValueError):
            b.epoch("2025-02-10 00:01:00")

    def test_database_rejects_even_identical_duplicate_targets(self):
        connection = b.sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE x (tech, band, station, sector, t, y, PRIMARY KEY(tech,band,station,sector,t))")
        row = ("NR", 2100, "Site 1", "1", 0, 3)
        connection.execute("INSERT INTO x VALUES (?,?,?,?,?,?)", row)
        with self.assertRaises(b.sqlite3.IntegrityError):
            connection.execute("INSERT INTO x VALUES (?,?,?,?,?,?)", row)
        connection.close()


if __name__ == "__main__":
    unittest.main()
