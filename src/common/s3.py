"""Общее подключение DuckDB к S3 для ЛР № 2 и ЛР № 3."""

import os
from urllib.parse import urlsplit

import duckdb


def configure_s3(connection: duckdb.DuckDBPyConnection) -> None:
    endpoint = os.environ["S3_ENDPOINT"]
    parsed = urlsplit(endpoint if "://" in endpoint else f"http://{endpoint}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("S3_ENDPOINT должен содержать корректный HTTP(S) адрес")
    try:
        connection.execute("LOAD httpfs")
    except duckdb.Error:
        connection.execute("INSTALL httpfs")
        connection.execute("LOAD httpfs")
    connection.execute("SET s3_endpoint = ?", [parsed.netloc])
    connection.execute("SET s3_access_key_id = ?", [os.environ["S3_ACCESS_KEY"]])
    connection.execute("SET s3_secret_access_key = ?", [os.environ["S3_SECRET_KEY"]])
    connection.execute("SET s3_region = 'us-east-1'")
    connection.execute("SET s3_url_style = 'path'")
    connection.execute("SET s3_use_ssl = ?", [parsed.scheme == "https"])
