import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from campuscommute.server import create_server


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = create_server(os.path.join(cls.tmp.name, "api.db"), port=0, verbose=False)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        self.request("POST", "/api/demo/reset")

    def request(self, method, path, body=None, headers=None):
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read()

    def get_json(self, path):
        status, _, body = self.request("GET", path)
        return status, json.loads(body)

    def test_overview(self):
        status, data = self.get_json("/api/overview?day=0&hour=9")
        self.assertEqual(status, 200)
        self.assertEqual(data["day_name"], "Monday")
        self.assertEqual(len(data["routes"]), 13)
        forecasts = [r["forecast"] for r in data["routes"]]
        self.assertEqual(forecasts, sorted(forecasts, reverse=True))
        self.assertEqual(data["metrics"]["busiest_route"]["id"], data["routes"][0]["id"])
        self.assertEqual(len(data["network_hourly"]), 24)

    def test_overview_rejects_bad_params(self):
        self.assertEqual(self.get_json("/api/overview?day=9")[0], 400)
        self.assertEqual(self.get_json("/api/overview?hour=abc")[0], 400)

    def test_route_detail(self):
        status, data = self.get_json("/api/routes/campus-loop?day=2")
        self.assertEqual(status, 200)
        self.assertEqual(data["name"], "Campus Loop")
        self.assertEqual(len(data["hourly"]), 24)
        self.assertTrue(data["stops"])
        self.assertEqual(self.get_json("/api/routes/nope")[0], 404)

    def test_metadata(self):
        status, data = self.get_json("/api/metadata")
        self.assertEqual(status, 200)
        self.assertEqual(data["source"], "Synthetic demo data")
        self.assertEqual(data["observation_count"], 13 * 4 * 7 * 24)
        self.assertEqual(data["evaluation"]["holdout_week"], 4)

    def test_export_import_round_trip(self):
        status, headers, csv_body = self.request("GET", "/api/export.csv")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        status, _, body = self.request("POST", "/api/import", csv_body,
                                       {"Content-Type": "text/csv", "X-Filename": "export.csv"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["source"], "Uploaded CSV (export.csv)")

    def test_import_replaces_data(self):
        csv_body = b"route_id,week,weekday,hour,boardings\ncampus-loop,1,0,9,300\n"
        status, _, body = self.request("POST", "/api/import", csv_body)
        self.assertEqual(status, 200)
        meta = json.loads(body)
        self.assertEqual(meta["observation_count"], 1)
        self.assertIsNone(meta["evaluation"])
        _, overview = self.get_json("/api/overview?day=0&hour=9")
        loop = next(r for r in overview["routes"] if r["id"] == "campus-loop")
        self.assertEqual(loop["forecast"], 300)
        self.assertTrue(loop["exceeds_target"])

    def test_invalid_import_keeps_existing_data(self):
        status, _, body = self.request("POST", "/api/import", b"route_id,week,weekday,hour,boardings\nx,1,0,9,1\n")
        self.assertEqual(status, 400)
        self.assertIn("errors", json.loads(body))
        _, meta = self.get_json("/api/metadata")
        self.assertEqual(meta["source"], "Synthetic demo data")
        self.assertEqual(meta["observation_count"], 13 * 4 * 7 * 24)

    def test_empty_import_rejected(self):
        self.assertEqual(self.request("POST", "/api/import", b"")[0], 400)

    def test_static_files_and_traversal(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"CampusCommute", body)
        self.assertEqual(self.request("GET", "/app.js")[0], 200)
        self.assertEqual(self.request("GET", "/../campuscommute/db.py")[0], 404)
        self.assertEqual(self.request("GET", "/%2e%2e/campuscommute/db.py")[0], 404)


if __name__ == "__main__":
    unittest.main()
