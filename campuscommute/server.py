"""Standard-library HTTP server for the dashboard files and JSON API."""

import json
import mimetypes
import re
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import api, db
from .csv_io import CSVValidationError, export_observations, parse_observations
from .synthetic import generate_observations

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ROUTE_PATH = re.compile(r"^/api/routes/([a-z0-9-]+)$")


class BadRequest(ValueError):
    pass


def _int_param(query, name, default, low, high):
    raw = query.get(name, [str(default)])[0]
    try:
        value = int(raw)
    except ValueError:
        raise BadRequest(f"'{name}' must be an integer")
    if not low <= value <= high:
        raise BadRequest(f"'{name}' must be between {low} and {high}")
    return value


def make_handler(db_path, static_dir=STATIC_DIR):
    static_root = Path(static_dir).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "CampusCommute/1.0"

        def log_message(self, fmt, *args):  # quieter default logging
            if getattr(self.server, "verbose", True):
                super().log_message(fmt, *args)

        # --- response helpers -------------------------------------------------
        def _send(self, status, body, content_type, extra_headers=None):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _json(self, payload, status=HTTPStatus.OK):
            self._send(status, json.dumps(payload), "application/json; charset=utf-8",
                       {"Cache-Control": "no-store"})

        def _error(self, status, message, errors=None):
            payload = {"error": message}
            if errors:
                payload["errors"] = errors
            self._json(payload, status)

        # --- routing ----------------------------------------------------------
        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            try:
                if url.path.startswith("/api/"):
                    self._handle_api_get(url.path, query)
                else:
                    self._serve_static(url.path)
            except BadRequest as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
            except api.NotFound as exc:
                self._error(HTTPStatus.NOT_FOUND, str(exc))

        do_HEAD = do_GET

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/api/import":
                self._handle_import()
            elif path == "/api/demo/reset":
                with closing(db.connect(db_path)) as conn:
                    db.replace_observations(conn, generate_observations(), db.SYNTHETIC_SOURCE)
                    self._json(api.metadata(conn))
            else:
                self._error(HTTPStatus.NOT_FOUND, "Not found")

        def _handle_api_get(self, path, query):
            with closing(db.connect(db_path)) as conn:
                if path == "/api/overview":
                    day = _int_param(query, "day", 0, 0, 6)
                    hour = _int_param(query, "hour", 9, 0, 23)
                    self._json(api.overview(conn, day, hour))
                elif path == "/api/metadata":
                    self._json(api.metadata(conn))
                elif path == "/api/export.csv":
                    body = export_observations(db.fetch_observations(conn))
                    self._send(HTTPStatus.OK, body, "text/csv; charset=utf-8", {
                        "Content-Disposition": 'attachment; filename="campuscommute-observations.csv"',
                        "Cache-Control": "no-store",
                    })
                elif match := ROUTE_PATH.match(path):
                    day = _int_param(query, "day", 0, 0, 6)
                    self._json(api.route_detail(conn, match.group(1), day))
                else:
                    raise api.NotFound("Not found")

        def _handle_import(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if length <= 0:
                self._error(HTTPStatus.BAD_REQUEST, "Send the CSV file as the request body.")
                return
            if length > MAX_UPLOAD_BYTES:
                self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "CSV file is larger than 10 MB.")
                return
            raw = self.rfile.read(length)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                self._error(HTTPStatus.BAD_REQUEST, "CSV file must be UTF-8 encoded.")
                return
            try:
                rows = parse_observations(text)
            except CSVValidationError as exc:
                self._error(HTTPStatus.BAD_REQUEST, "CSV validation failed; existing data was kept.",
                            exc.errors)
                return
            filename = re.sub(r"[^\w.\- ]", "", self.headers.get("X-Filename", ""))[:80]
            source = f"Uploaded CSV ({filename})" if filename else "Uploaded CSV"
            with closing(db.connect(db_path)) as conn:
                db.replace_observations(conn, rows, source)
                self._json(api.metadata(conn))

        def _serve_static(self, path):
            relative = "index.html" if path in ("", "/") else path.lstrip("/")
            target = (static_root / relative).resolve()
            if static_root not in target.parents or not target.is_file():
                self._error(HTTPStatus.NOT_FOUND, "Not found")
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type.endswith("javascript"):
                content_type += "; charset=utf-8"
            self._send(HTTPStatus.OK, target.read_bytes(), content_type)

    return Handler


def create_server(db_path, host="127.0.0.1", port=8000, verbose=True):
    db.init_db(db_path)
    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    server.verbose = verbose
    return server
