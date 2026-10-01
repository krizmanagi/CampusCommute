import sqlite3
import unittest
from contextlib import closing

from campuscommute import db
from campuscommute.csv_io import CSVValidationError, export_observations, parse_observations

HEADER = "route_id,week,weekday,hour,boardings\n"


class ParseTests(unittest.TestCase):
    def test_valid_file(self):
        rows = parse_observations(HEADER + "campus-loop,1,0,9,42\n\ndowntown,2,6,23,0\n")
        self.assertEqual(rows, [("campus-loop", 1, 0, 9, 42), ("downtown", 2, 6, 23, 0)])

    def test_accepts_bom_and_header_whitespace(self):
        rows = parse_observations("﻿Route_ID, week ,weekday,hour,boardings\ncampus-loop,1,0,9,42\n")
        self.assertEqual(len(rows), 1)

    def assertRejected(self, text, fragment):
        with self.assertRaises(CSVValidationError) as ctx:
            parse_observations(text)
        self.assertIn(fragment, " ".join(ctx.exception.errors))

    def test_rejects_bad_input(self):
        self.assertRejected("", "empty")
        self.assertRejected("a,b,c\n", "Header")
        self.assertRejected(HEADER, "no observations")
        self.assertRejected(HEADER + "nowhere,1,0,9,1\n", "unknown route_id")
        self.assertRejected(HEADER + "campus-loop,1,7,9,1\n", "weekday")
        self.assertRejected(HEADER + "campus-loop,1,0,24,1\n", "hour")
        self.assertRejected(HEADER + "campus-loop,1,0,9,-1\n", "boardings")
        self.assertRejected(HEADER + "campus-loop,0,0,9,1\n", "week")
        self.assertRejected(HEADER + "campus-loop,1,0,9,1.5\n", "whole number")
        self.assertRejected(HEADER + "campus-loop,1,0,9\n", "expected 5 values")
        self.assertRejected(HEADER + "campus-loop,1,0,9,1\ncampus-loop,1,0,9,2\n", "duplicate")

    def test_reports_line_numbers_and_caps_errors(self):
        text = HEADER + "".join(f"campus-loop,1,0,99,{i}\n" for i in range(50))
        with self.assertRaises(CSVValidationError) as ctx:
            parse_observations(text)
        self.assertEqual(len(ctx.exception.errors), 10)
        self.assertTrue(ctx.exception.errors[0].startswith("Line 2:"))

    def test_export_round_trip(self):
        rows = [("campus-loop", 1, 0, 9, 42), ("downtown", 2, 6, 23, 0)]
        self.assertEqual(parse_observations(export_observations(rows)), rows)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.conn.executescript(db.SCHEMA)
        db.replace_observations(self.conn, [("campus-loop", 1, 0, 9, 5)], "original")

    def tearDown(self):
        self.conn.close()

    def test_failed_replace_keeps_existing_data(self):
        bad_rows = [("campus-loop", 1, 0, 9, 1), ("campus-loop", 1, 0, 9, 2)]  # duplicate key
        with self.assertRaises(sqlite3.IntegrityError):
            db.replace_observations(self.conn, bad_rows, "bad")
        self.assertEqual(db.fetch_observations(self.conn), [("campus-loop", 1, 0, 9, 5)])
        self.assertEqual(db.get_source(self.conn), "original")

    def test_replace_swaps_data_and_source(self):
        db.replace_observations(self.conn, [("downtown", 3, 2, 8, 7)], "new")
        self.assertEqual(db.fetch_observations(self.conn), [("downtown", 3, 2, 8, 7)])
        self.assertEqual(db.get_source(self.conn), "new")

    def test_init_seeds_once(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.db")
            db.init_db(path)
            with closing(db.connect(path)) as conn:
                count = len(db.fetch_observations(conn))
                db.replace_observations(conn, [("downtown", 1, 0, 0, 1)], "custom")
            db.init_db(path)
            with closing(db.connect(path)) as conn:
                self.assertEqual(len(db.fetch_observations(conn)), 1)
            self.assertEqual(count, 13 * 4 * 7 * 24)


if __name__ == "__main__":
    unittest.main()
