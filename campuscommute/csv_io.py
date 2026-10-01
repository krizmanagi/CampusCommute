"""CSV import validation and export."""

import csv
import io

from .routes import ROUTES_BY_ID

COLUMNS = ("route_id", "week", "weekday", "hour", "boardings")
MAX_ROWS = 200_000
MAX_ERRORS_REPORTED = 10


class CSVValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def _parse_int(value, field, low=None, high=None):
    try:
        number = int(value.strip())
    except (ValueError, AttributeError):
        raise ValueError(f"{field} must be a whole number (got {value!r})")
    if low is not None and number < low or high is not None and number > high:
        bounds = f"between {low} and {high}" if high is not None else f"at least {low}"
        raise ValueError(f"{field} must be {bounds} (got {number})")
    return number


def parse_observations(text):
    """Validate CSV text and return observation tuples, or raise CSVValidationError."""
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header is None:
        raise CSVValidationError(["The file is empty."])
    header = [h.strip().lower() for h in header]
    if tuple(header) != COLUMNS:
        raise CSVValidationError([f"Header must be exactly: {','.join(COLUMNS)}"])

    rows, errors, seen = [], [], set()
    for line_no, record in enumerate(reader, start=2):
        if len(errors) >= MAX_ERRORS_REPORTED:
            break
        if not record or all(not cell.strip() for cell in record):
            continue
        if len(rows) >= MAX_ROWS:
            errors.append(f"File exceeds the limit of {MAX_ROWS} rows.")
            break
        if len(record) != len(COLUMNS):
            errors.append(f"Line {line_no}: expected {len(COLUMNS)} values, found {len(record)}.")
            continue
        route_id = record[0].strip()
        try:
            if route_id not in ROUTES_BY_ID:
                raise ValueError(f"unknown route_id {route_id!r}")
            week = _parse_int(record[1], "week", low=1)
            weekday = _parse_int(record[2], "weekday", 0, 6)
            hour = _parse_int(record[3], "hour", 0, 23)
            boardings = _parse_int(record[4], "boardings", low=0)
        except ValueError as exc:
            errors.append(f"Line {line_no}: {exc}.")
            continue
        key = (route_id, week, weekday, hour)
        if key in seen:
            errors.append(f"Line {line_no}: duplicate observation for {route_id}, week {week}, "
                          f"weekday {weekday}, hour {hour}.")
            continue
        seen.add(key)
        rows.append((route_id, week, weekday, hour, boardings))

    if errors:
        raise CSVValidationError(errors[:MAX_ERRORS_REPORTED])
    if not rows:
        raise CSVValidationError(["The file has a header but no observations."])
    return rows


def export_observations(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return buffer.getvalue()
