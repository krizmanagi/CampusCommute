import unittest

from campuscommute.forecast import (
    Forecaster,
    evaluate_holdout,
    hourly_capacity,
    suggest_interval,
)
from campuscommute.synthetic import generate_observations


class ForecasterTests(unittest.TestCase):
    def test_exact_match_averages_history(self):
        model = Forecaster([("campus-loop", 1, 0, 9, 100), ("campus-loop", 2, 0, 9, 140)])
        self.assertEqual(model.predict("campus-loop", 0, 9), (120, "weekday-hour"))

    def test_falls_back_to_route_hour_average(self):
        model = Forecaster([("campus-loop", 1, 0, 9, 100), ("campus-loop", 1, 1, 9, 50)])
        self.assertEqual(model.predict("campus-loop", 3, 9), (75, "route-hour"))

    def test_falls_back_to_route_overall_average(self):
        model = Forecaster([("campus-loop", 1, 0, 9, 100), ("campus-loop", 1, 0, 10, 20)])
        self.assertEqual(model.predict("campus-loop", 0, 15), (60, "route-overall"))

    def test_unknown_route_has_no_history(self):
        self.assertEqual(Forecaster([]).predict("campus-loop", 0, 9), (0.0, "no-history"))


class IntervalTests(unittest.TestCase):
    def test_capacity_math(self):
        self.assertEqual(hourly_capacity(30), 64)
        self.assertEqual(hourly_capacity(10), 192)

    def test_picks_least_frequent_interval_that_fits(self):
        self.assertEqual(suggest_interval(0)["interval_minutes"], 30)
        self.assertEqual(suggest_interval(64)["interval_minutes"], 30)
        self.assertEqual(suggest_interval(65)["interval_minutes"], 20)
        self.assertEqual(suggest_interval(128)["interval_minutes"], 15)
        self.assertEqual(suggest_interval(150)["interval_minutes"], 12)
        self.assertEqual(suggest_interval(192)["interval_minutes"], 10)

    def test_flags_demand_above_target_at_ten_minutes(self):
        result = suggest_interval(250)
        self.assertEqual(result["interval_minutes"], 10)
        self.assertTrue(result["exceeds_target"])
        self.assertAlmostEqual(result["occupancy"], 250 / 240)

    def test_wait_is_half_the_interval(self):
        self.assertEqual(suggest_interval(100)["estimated_wait_minutes"], 7.5)


class EvaluationTests(unittest.TestCase):
    def test_requires_two_weeks(self):
        self.assertIsNone(evaluate_holdout([("campus-loop", 1, 0, 9, 10)]))

    def test_holds_out_latest_week(self):
        rows = [
            ("campus-loop", 1, 0, 9, 100),
            ("campus-loop", 2, 0, 9, 120),
            ("campus-loop", 3, 0, 9, 150),
        ]
        result = evaluate_holdout(rows)
        self.assertEqual(result["holdout_week"], 3)
        self.assertEqual(result["training_weeks"], [1, 2])
        self.assertEqual(result["predictions"], 1)
        self.assertEqual(result["mae"], 40)

    def test_synthetic_forecast_beats_naive_baseline(self):
        result = evaluate_holdout(generate_observations())
        self.assertLess(result["mae"], result["baseline_mae"])

    def test_synthetic_data_is_deterministic(self):
        self.assertEqual(generate_observations(), generate_observations())


if __name__ == "__main__":
    unittest.main()
