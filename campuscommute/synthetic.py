"""Deterministic synthetic hourly boarding counts for the fictional routes."""

import math
import random

from .routes import ROUTES

SYNTHETIC_WEEKS = 4
SEED = 20260901


def _daily_shape(route_id, weekday, hour):
    """Relative demand for an hour of a day, before route scaling and noise."""
    weekend = weekday >= 5
    if hour < 6 and route_id != "night-owl":
        return 0.03  # near-empty overnight hours
    if route_id == "night-owl":
        # Evening-heavy service with a Friday/Saturday bump.
        evening = math.exp(-((hour - 22) ** 2) / 6)
        return evening * (1.5 if weekday in (4, 5) else 1.0)
    if route_id == "airport":
        return 0.6 + 0.4 * math.exp(-((hour - 14) ** 2) / 30) * (1.4 if weekday in (4, 6) else 1.0)
    if route_id == "athletics":
        peak = math.exp(-((hour - 17) ** 2) / 4)
        return 0.3 + peak * (1.6 if weekend else 1.0)
    morning = math.exp(-((hour - 8.5) ** 2) / 2.5)
    midday = 0.55 * math.exp(-((hour - 12.5) ** 2) / 3)
    evening = 0.8 * math.exp(-((hour - 17) ** 2) / 3)
    shape = 0.15 + morning + midday + evening
    if weekend:
        shape = 0.15 + 0.45 * math.exp(-((hour - 14) ** 2) / 12)
    elif weekday == 4:
        shape *= 0.85
    return shape


def generate_observations(weeks=SYNTHETIC_WEEKS, seed=SEED):
    """Return a list of (route_id, week, weekday, hour, boardings) tuples."""
    rng = random.Random(seed)
    rows = []
    for week in range(1, weeks + 1):
        trend = 1 + 0.02 * (week - 1)  # mild growth through the term
        for route in ROUTES:
            for weekday in range(7):
                for hour in range(24):
                    expected = 120 * route.base_demand * _daily_shape(route.id, weekday, hour) * trend
                    boardings = max(0, round(rng.gauss(expected, expected * 0.12 + 2)))
                    rows.append((route.id, week, weekday, hour, boardings))
    return rows
