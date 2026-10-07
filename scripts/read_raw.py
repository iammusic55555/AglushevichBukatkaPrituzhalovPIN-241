import argparse
import os
from urllib.parse import urlparse

import duckdb


def main():
       parser = argparse.ArgumentParser()
       parser.add_argument("--path", required=True)
       args = parser.parse_args()

       raw_endpoint = os.environ["S3_ENDPOINT"]
       if "://" not in raw_endpoint:
        raw_endpoint = "http://" + raw_endpoint
       endpoint = urlparse(raw_endpoint)
       use_ssl = "true" if endpoint.scheme == "https" else "false"

       con = duckdb.connect()
       con.execute("INSTALL httpfs")
       con.execute("LOAD httpfs")
       con.execute(f"SET s3_endpoint='{endpoint.netloc}'")
       con.execute(f"SET s3_access_key_id='{os.environ['S3_ACCESS_KEY']}'")
       con.execute(f"SET s3_secret_access_key='{os.environ['S3_SECRET_KEY']}'")
       con.execute(f"SET s3_use_ssl={use_ssl}")
       con.execute("SET s3_url_style='path'")

       path = args.path.lower()
       if path.endswith(".parquet"):
           reader = "read_parquet"
       elif path.endswith((".json", ".jsonl", ".ndjson")):
           reader = "read_json_auto"
       else:
           reader = "read_csv_auto"

       relation = con.sql(f"SELECT * FROM {reader}('{args.path}') LIMIT 5")
       relation.show()


if __name__ == "__main__":
       main()