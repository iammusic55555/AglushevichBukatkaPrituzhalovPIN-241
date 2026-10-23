"""Проверка реального SQL ноутбука на граничных данных, без S3."""

import json
import unittest
from pathlib import Path

import duckdb

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks/profile_quality.ipynb"
COLUMNS = [
    "id",
    "neighbourhood_cleansed",
    "room_type",
    "price",
    "availability_365",
    "has_availability",
    "last_scraped",
    "calendar_last_scraped",
]


def row(
    id="1",
    district="Centrum-West",
    room="Entire home/apt",
    price="$100.00",
    days="365",
    calendar="t",
):
    return (id, district, room, price, days, calendar, "2026-06-15", "2026-06-15")


def process(rows, threshold_override=None):
    con = duckdb.connect()
    con.execute("CREATE TABLE raw (" + ", ".join(f"{c} VARCHAR" for c in COLUMNS) + ")")
    if rows:
        con.executemany("INSERT INTO raw VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    context = {
        "con": con,
        "raw_columns": COLUMNS,
        "show_table": lambda *args: None,
        "show_sql": lambda query: con.execute(query).fetchall(),
    }
    nb = json.loads(NOTEBOOK.read_text())
    for cell in nb["cells"]:
        tags = cell["metadata"].get("tags", [])
        if any(tag in tags for tag in ["prepare", "rule", "transform"]):
            source = "".join(cell["source"])
            if threshold_override is not None and "rule" in tags:
                source = source.replace(" = 0\n", f" = {threshold_override}\n", 1)
            exec(compile(source, str(NOTEBOOK), "exec"), context)
    return con, context


class QualityTests(unittest.TestCase):
    def test_valid_boundaries_and_currency(self):
        con, _ = process([row(days="0"), row(id="2", price="$1,234.50")])
        self.addCleanup(con.close)
        self.assertEqual(con.execute("SELECT count(*) FROM quarantine").fetchone()[0], 0)
        self.assertEqual(
            con.execute("SELECT availability_365 FROM staging WHERE id='1'").fetchone()[0], 0
        )
        self.assertEqual(
            str(con.execute("SELECT price_eur FROM staging WHERE id='2'").fetchone()[0]), "1234.50"
        )
        columns = [x[0] for x in con.execute("DESCRIBE quarantine").fetchall()]
        self.assertIn("quality_rule_ids", columns)

    def test_multiple_reasons_preserve_originals(self):
        con, _ = process([row(id="7", district=None, days="366"), row(id=" 7 "), row(id=None)])
        self.addCleanup(con.close)
        self.assertEqual(con.execute("SELECT count(*) FROM staging").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT count(*) FROM quarantine").fetchone()[0], 3)
        reasons = con.execute("SELECT quality_rule_ids FROM quarantine WHERE id='7'")
        self.assertEqual(reasons.fetchone()[0], "id_integrity;district_present;availability_valid")
        self.assertEqual(
            con.execute("SELECT availability_365 FROM quarantine WHERE id='7'").fetchone()[0], "366"
        )

    def test_warnings_apply_below_threshold(self):
        con, ctx = process(
            [row(price=None, calendar=None), row(id="2", price="$0.00", calendar="f", days="3")],
            100,
        )
        self.addCleanup(con.close)
        self.assertTrue(all(not r["exceeded"] for r in ctx["rule_results"]))
        self.assertEqual(con.execute("SELECT count(*) FROM staging").fetchone()[0], 2)
        self.assertEqual(
            con.execute(
                "SELECT flag_price_missing, flag_calendar_unknown " "FROM staging WHERE id='1'"
            ).fetchone(),
            (True, True),
        )
        self.assertEqual(
            con.execute(
                "SELECT price_eur, flag_price_invalid, "
                "flag_calendar_inconsistent FROM staging WHERE id='2'"
            ).fetchone(),
            (None, True, True),
        )

    def test_bad_prices_and_fractional_days(self):
        con, _ = process(
            [
                row(price="$1,23.00"),
                row(id="2", days="1.5"),
                row(id="3", price="NaN"),
                row(id="4", room="unknown"),
            ]
        )
        self.addCleanup(con.close)
        self.assertEqual(
            con.execute("SELECT id FROM staging ORDER BY id").fetchall(), [("1",), ("3",)]
        )
        self.assertEqual(
            con.execute(
                "SELECT count(*) FROM staging " "WHERE price_eur IS NULL AND flag_price_invalid"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(con.execute("SELECT count(*) FROM quarantine").fetchone()[0], 2)

    def test_empty_dataset(self):
        con, ctx = process([])
        self.addCleanup(con.close)
        self.assertTrue(
            all(r["checked"] == r["violations"] == r["share"] == 0 for r in ctx["rule_results"])
        )
        self.assertEqual(con.execute("SELECT count(*) FROM staging").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
