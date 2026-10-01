# CampusCommute

CampusCommute is a full-stack shuttle demand planning dashboard. It uses historical hourly boarding counts to
forecast demand across 13 routes, lets a user explore busy periods, and suggests shuttle intervals based on
predicted ridership and vehicle capacity. It has a responsive frontend, a Python API, SQLite storage, CSV import
and export, and automated tests.

> **The routes and data are synthetic.** The app shows how the system works. It does not report measured
> results for a real campus, so treat its schedule suggestions as planning estimates.

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

## Quick start

You need Python 3.9 or newer. No packages are required, since everything uses the standard library.

```bash
python -m campuscommute            # serves http://127.0.0.1:8000
python -m campuscommute --port 9000 --db data/my.db --host 0.0.0.0
python -m unittest discover -v     # run the test suite
```

On first launch, the app creates `data/campuscommute.db` and seeds it with four weeks of synthetic observations.

## How it works

1. **Data enters the system.** The backend generates four weeks of deterministic, seeded hourly observations
   for 13 fictional routes. Uploading a CSV replaces them.
2. **The backend forecasts boardings.** For each route, weekday and hour, it averages the matching historical
   counts. If that exact combination has no history, it falls back to the route's average for that hour, then
   to the route's overall average.
3. **The backend suggests an interval.** It compares forecast boardings with a 40-seat vehicle at 80% target
   occupancy (32 riders per trip). It then picks the least frequent interval from 30, 20, 15, 12 or 10 minutes
   whose hourly target capacity covers the forecast. If demand exceeds the target even at 10 minutes
   (192 riders/hour), it flags the route.
4. **The frontend displays the results.** Changing the weekday, the hour, or the selected route updates the
   metrics, hourly chart, route ranking, capacity estimate and suggested interval. The selection is also
   stored in the URL, so a view can be shared by link.

The displayed wait time is a model estimate equal to half the suggested interval, which assumes passengers
arrive uniformly between shuttles. The schedule suggestion does not account for a shared vehicle fleet, travel
times, operating costs, transfers or observed passenger waits.

## Project layout

```
campuscommute/
  routes.py      13 fictional routes and their stops
  synthetic.py   seeded synthetic data generator
  db.py          SQLite schema, transactional replace, queries
  forecast.py    historical-average forecaster, interval rule, holdout evaluation
  csv_io.py      CSV validation and export
  api.py         JSON payload builders (independent of HTTP)
  server.py      standard-library HTTP server: static files + JSON API
  __main__.py    command-line entry point
static/
  index.html, styles.css, app.js   vanilla JS dashboard; chart drawn with Canvas
tests/           unit tests plus end-to-end API tests against a live server
.github/workflows/ci.yml           tests on Python 3.9 / 3.11 / 3.13 and a server smoke test
```

## Frontend

The frontend uses plain HTML, CSS and JavaScript, with no framework and no external requests. It includes:

- weekday and hour filters
- a searchable route list that matches route names and stops
- an hourly forecast chart drawn with the Canvas API, with hover tooltips, click-to-select-hour, a reference line
  for 10-minute target capacity, and a table view for accessibility
- the selected route's suggestion, seat capacity, occupancy, estimated wait and stops
- a busiest-routes ranking
- data controls: CSV export, CSV import and a reset to the demo data

The layout is responsive down to phone width and supports light and dark color schemes.

## Backend and database

Python's `http.server` (`ThreadingHTTPServer`) serves both the dashboard files and the JSON endpoints. SQLite
stores one row per observation, keyed by `(route_id, week, weekday, hour)`. CSV uploads are fully validated
before anything is written. The replace then runs in a single transaction, so an invalid file leaves the
current dataset intact.

| Endpoint | What it provides |
| --- | --- |
| `GET /api/overview?day=0&hour=9` | Dashboard metrics, the route ranking and per-route forecasts |
| `GET /api/routes/campus-loop?day=0` | One route's 24-hour forecast, suggestions and stops |
| `GET /api/metadata` | Data source, observation count, assumptions and evaluation results |
| `GET /api/export.csv` | The current observations as a CSV |
| `POST /api/import` | Replace all observations with a validated CSV (raw CSV request body) |
| `POST /api/demo/reset` | Restore the synthetic dataset |

`day` runs from 0 (Monday) to 6 (Sunday), and `hour` runs from 0 to 23.

### CSV format

```csv
route_id,week,weekday,hour,boardings
campus-loop,1,0,9,182
downtown,1,0,9,140
```

Validation rules:

- the header must match exactly
- `route_id` must be one of the 13 known routes
- `week` must be 1 or greater, `weekday` 0–6, `hour` 0–23, and `boardings` a non-negative whole number
- duplicate keys are not allowed
- files are limited to 10 MB and 200,000 rows

Errors report their line numbers. You can try an import from the command line:

```bash
curl -X POST --data-binary @observations.csv -H "Content-Type: text/csv" http://127.0.0.1:8000/api/import
```

## Forecast evaluation

When the dataset contains at least two weeks, the project holds out the latest week and predicts its
observations from the earlier weeks. It reports the **mean absolute error (MAE)**: the average difference
between predicted and recorded boardings. For context, it also reports a naive baseline that predicts each
route's overall average. The dashboard forecast itself uses all available weeks.

On the bundled synthetic data, the holdout MAE is about 6.4 boardings per route-hour, against about 30.4 for
the baseline. The synthetic data includes a small week-over-week growth trend, which a plain historical
average lags behind. These numbers describe the synthetic data only.


> I built CampusCommute as a full-stack transportation analytics demo. The Python backend stores hourly route
> observations in SQLite, forecasts boardings from historical weekday and hour patterns, and exposes the
> results through a JSON API. I built a responsive JavaScript dashboard for exploring routes and comparing
> capacity-based schedule suggestions. I also added CSV import and export, a last-week holdout evaluation,
> automated tests, and a GitHub Actions workflow. The bundled dataset is synthetic, so I present the schedule
> results as planning estimates rather than measured improvements.
