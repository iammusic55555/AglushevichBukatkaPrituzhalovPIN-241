"""Показать исходные строки напрямую из S3."""

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common.s3 import configure_s3  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    if not args.path.startswith("s3://raw/"):
        parser.error("Ожидается полный путь s3://raw/…")
    path = args.path.lower()
    if path.endswith(".parquet"):
        reader = "read_parquet"
    elif path.endswith((".json", ".jsonl", ".ndjson")):
        reader = "read_json_auto"
    else:
        reader = "read_csv_auto"
    with duckdb.connect() as connection:
        configure_s3(connection)
        connection.sql(f"SELECT * FROM {reader}(?) LIMIT 5", params=[args.path]).show()


if __name__ == "__main__":
    main()
