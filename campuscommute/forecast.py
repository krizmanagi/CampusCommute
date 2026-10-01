"""Historical-average forecasting, interval suggestions, and holdout evaluation."""

from collections import defaultdict

VEHICLE_CAPACITY = 40
TARGET_OCCUPANCY = 0.8
INTERVAL_OPTIONS = (30, 20, 15, 12, 10)  # minutes, least to most frequent


class Forecaster:
    """Averages historical boardings with route/weekday/hour fallbacks."""

    def __init__(self, observations):
        exact = defaultdict(list)
        route_hour = defaultdict(list)
        route_all = defaultdict(list)
        for route_id, _week, weekday, hour, boardings in observations:
            exact[(route_id, weekday, hour)].append(boardings)
            route_hour[(route_id, hour)].append(boardings)
            route_all[route_id].append(boardings)
        self._exact = {k: _mean(v) for k, v in exact.items()}
        self._route_hour = {k: _mean(v) for k, v in route_hour.items()}
        self._route_all = {k: _mean(v) for k, v in route_all.items()}

    def predict(self, route_id, weekday, hour):
        """Return (forecast boardings, method used)."""
        if (route_id, weekday, hour) in self._exact:
            return self._exact[(route_id, weekday, hour)], "weekday-hour"
        if (route_id, hour) in self._route_hour:
            return self._route_hour[(route_id, hour)], "route-hour"
        if route_id in self._route_all:
            return self._route_all[route_id], "route-overall"
        return 0.0, "no-history"


def _mean(values):
    return sum(values) / len(values)


def hourly_capacity(interval_minutes, capacity=VEHICLE_CAPACITY, occupancy=TARGET_OCCUPANCY):
    """Passengers per hour a single route can carry at the target occupancy."""
    return (60 / interval_minutes) * capacity * occupancy


def suggest_interval(forecast, capacity=VEHICLE_CAPACITY, occupancy=TARGET_OCCUPANCY):
    """Pick the least frequent interval whose target capacity covers the forecast."""
    for interval in INTERVAL_OPTIONS:
        if hourly_capacity(interval, capacity, occupancy) >= forecast:
            over = False
            break
    else:
        interval, over = INTERVAL_OPTIONS[-1], True
    trips = 60 / interval
    seats = trips * capacity
    return {
        "interval_minutes": interval,
        "trips_per_hour": trips,
        "seats_per_hour": seats,
        "target_capacity": hourly_capacity(interval, capacity, occupancy),
        "occupancy": forecast / seats if seats else 0.0,
        "estimated_wait_minutes": interval / 2,
        "exceeds_target": over,
    }


def evaluate_holdout(observations):
    """Hold out the latest week, forecast it from earlier weeks, and report MAE.

    Returns None when fewer than two distinct weeks are available.
    """
    weeks = sorted({row[1] for row in observations})
    if len(weeks) < 2:
        return None
    holdout_week = weeks[-1]
    train = [row for row in observations if row[1] != holdout_week]
    test = [row for row in observations if row[1] == holdout_week]
    model = Forecaster(train)

    # Naive baseline for context: each route's overall training average.
    route_totals = defaultdict(list)
    for row in train:
        route_totals[row[0]].append(row[4])
    route_means = {k: _mean(v) for k, v in route_totals.items()}

    errors, baseline_errors = [], []
    for route_id, _week, weekday, hour, actual in test:
        predicted, _ = model.predict(route_id, weekday, hour)
        errors.append(abs(predicted - actual))
        baseline_errors.append(abs(route_means.get(route_id, 0.0) - actual))
    mean_actual = _mean([row[4] for row in test])
    return {
        "holdout_week": holdout_week,
        "training_weeks": weeks[:-1],
        "predictions": len(test),
        "mae": _mean(errors),
        "baseline_mae": _mean(baseline_errors),
        "mean_actual_boardings": mean_actual,
    }
