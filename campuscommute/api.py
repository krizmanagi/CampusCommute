"""JSON payload builders, independent of the HTTP layer."""

from . import db
from .forecast import (
    INTERVAL_OPTIONS,
    TARGET_OCCUPANCY,
    VEHICLE_CAPACITY,
    Forecaster,
    evaluate_holdout,
    suggest_interval,
)
from .routes import ROUTES, ROUTES_BY_ID, WEEKDAYS


class NotFound(LookupError):
    pass


def assumptions():
    return {
        "vehicle_capacity": VEHICLE_CAPACITY,
        "target_occupancy": TARGET_OCCUPANCY,
        "interval_options": list(INTERVAL_OPTIONS),
        "wait_model": "Half the suggested interval, assuming passengers arrive uniformly.",
    }


def _forecast_entry(model, route_id, day, hour):
    forecast, method = model.predict(route_id, day, hour)
    entry = {"hour": hour, "forecast": round(forecast, 1), "method": method}
    entry.update(suggest_interval(forecast))
    entry["occupancy"] = round(entry["occupancy"], 3)
    return entry


def overview(conn, day, hour):
    model = Forecaster(db.fetch_observations(conn))
    routes = []
    network_hourly = [0.0] * 24
    for route in ROUTES:
        entry = _forecast_entry(model, route.id, day, hour)
        daily_total = 0.0
        for h in range(24):
            value, _ = model.predict(route.id, day, h)
            daily_total += value
            network_hourly[h] += value
        entry.update({"id": route.id, "name": route.name, "daily_total": round(daily_total, 1)})
        routes.append(entry)
    routes.sort(key=lambda r: (-r["forecast"], r["name"]))

    busiest = routes[0]
    return {
        "day": day,
        "day_name": WEEKDAYS[day],
        "hour": hour,
        "metrics": {
            "hour_boardings": round(sum(r["forecast"] for r in routes), 1),
            "day_boardings": round(sum(network_hourly), 1),
            "busiest_route": {"id": busiest["id"], "name": busiest["name"], "forecast": busiest["forecast"]},
            "routes_exceeding_target": sum(r["exceeds_target"] for r in routes),
            "average_wait_minutes": round(sum(r["estimated_wait_minutes"] for r in routes) / len(routes), 1),
            "trips_per_hour": round(sum(r["trips_per_hour"] for r in routes), 1),
        },
        "routes": routes,
        "network_hourly": [{"hour": h, "forecast": round(v, 1)} for h, v in enumerate(network_hourly)],
        "assumptions": assumptions(),
    }


def route_detail(conn, route_id, day):
    route = ROUTES_BY_ID.get(route_id)
    if route is None:
        raise NotFound(f"Unknown route: {route_id}")
    model = Forecaster(db.fetch_observations(conn))
    hourly = [_forecast_entry(model, route.id, day, h) for h in range(24)]
    peak = max(hourly, key=lambda e: e["forecast"])
    return {
        "id": route.id,
        "name": route.name,
        "stops": list(route.stops),
        "day": day,
        "day_name": WEEKDAYS[day],
        "hourly": hourly,
        "daily_total": round(sum(e["forecast"] for e in hourly), 1),
        "peak_hour": peak["hour"],
        "assumptions": assumptions(),
    }


def metadata(conn):
    observations = db.fetch_observations(conn)
    evaluation = evaluate_holdout(observations)
    if evaluation:
        for key in ("mae", "baseline_mae", "mean_actual_boardings"):
            evaluation[key] = round(evaluation[key], 2)
    return {
        "source": db.get_source(conn),
        "observation_count": len(observations),
        "route_count": len(ROUTES),
        "weeks": sorted({row[1] for row in observations}),
        "evaluation": evaluation,
        "assumptions": assumptions(),
        "routes": [{"id": r.id, "name": r.name, "stops": list(r.stops)} for r in ROUTES],
    }
