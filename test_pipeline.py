import csv, io, json, unittest
from pathlib import Path
from pipeline import prepare, export


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(Path(__file__).with_name("example.json").read_text())
        self.e = prepare(self.d)

    def test_aliases_and_exact_routes(self):
        rows = self.e["candidates"]
        self.assertNotIn("/about", [x["from"] for x in rows])
        self.assertEqual(len([x for x in rows if x["basis"] == "Competing aliases"]), 2)

    def test_conflicting_redirects_refused(self):
        with self.assertRaises(ValueError):
            export(
                self.d,
                self.e,
                [x for x in self.e["candidates"] if x["from"] == "/billing/receipt"],
            )

    def test_partial_approval_exports_real_rules(self):
        pick = [x for x in self.e["candidates"] if x["from"] == "/guide/first-run"]
        out = export(self.d, self.e, pick)
        self.assertEqual(out["_redirects"], "/guide/first-run /start 301\n")
        self.assertIn("/setup/media", out["unresolved-routes.csv"])

    def test_unresolved_title_is_literal_in_spreadsheet(self):
        self.d["old_routes"].append({"path": "/team", "title": "@support"})
        evidence = prepare(self.d)
        result = export(self.d, evidence, [])
        rows = csv.DictReader(io.StringIO(result["unresolved-routes.csv"]))
        self.assertEqual(
            next(row for row in rows if row["legacy_path"] == "/team")["title"],
            "'@support",
        )
        self.assertEqual(
            next(row for row in evidence["records"] if row["path"] == "/team")["title"],
            "@support",
        )

    def test_dot_segments_and_duplicate_normalized_paths(self):
        for path in ("/about/", "/x/../z", "https://somewhere.test"):
            with self.assertRaises(ValueError):
                prepare(
                    dict(
                        self.d,
                        old_routes=self.d["old_routes"]
                        + [{"path": path, "title": "Extra"}],
                    )
                )
