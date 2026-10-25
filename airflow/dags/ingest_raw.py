from datetime import datetime
from urllib.parse import urlparse

import requests

from airflow import DAG
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.http.sensors.http import HttpSensor

try:
       from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
       from airflow.operators.python import PythonOperator

SOURCE_URL = "https://data.insideairbnb.com/the-netherlands/north-holland/amsterdam/2026-06-15/data/listings.csv.gz"
FILENAME = "listings.csv.gz"
DATASET_SLUG = "airbnb_amsterdam_listings"

S3_CONN_ID = "s3_conn"
HTTP_CONN_ID = "source_http_conn"
BUCKET = "raw"


def load_to_raw(url, filename, dataset_slug, s3_conn_id, logical_date):
       hook = S3Hook(aws_conn_id=s3_conn_id)

       if not hook.check_for_bucket(BUCKET):
           raise RuntimeError(
               "Бакет raw не найден. Выполните docker compose up -d"
           )

       key = f"{dataset_slug}/ingested_on={logical_date}/{filename}"

       if hook.check_for_key(key, bucket_name=BUCKET):
           print(f"Объект s3://{BUCKET}/{key} уже существует, загрузка пропущена")
           return

       response = requests.get(url, timeout=300)
       response.raise_for_status()

       hook.load_bytes(
           response.content,
           key=key,
           bucket_name=BUCKET,
           replace=False,
       )
       print(f"Загружено: s3://{BUCKET}/{key}")


with DAG(
       dag_id="ingest_raw",
       start_date=datetime(2026, 1, 1),
       schedule=None,
       catchup=False,
   ) as dag:
       wait_for_primary_source = HttpSensor(
           task_id="wait_for_primary_source",
           http_conn_id=HTTP_CONN_ID,
           endpoint=urlparse(SOURCE_URL).path.lstrip("/"),
           method="HEAD",
           poke_interval=60,
           timeout=600,
       )

       load_to_raw_task = PythonOperator(
           task_id="load_to_raw",
           python_callable=load_to_raw,
           op_kwargs=dict(
               url=SOURCE_URL,
               filename=FILENAME,
               dataset_slug=DATASET_SLUG,
               s3_conn_id=S3_CONN_ID,
               logical_date="{{ ds }}",
           ),
       )

       wait_for_primary_source >> load_to_raw_task