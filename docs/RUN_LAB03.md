# Запуск ЛР № 3

Ветка `lab-03` основана на выполненной ЛР № 2 (`23009c3`). Логика DAG не менялась.
Работайте из корня папки `AglushevichBukatkaPrituzhalovPIN-241`.

## 1. Стенд

Запустите Docker Desktop. Выполните:

```bash
uv sync --locked
```

Если `.env` отсутствует, скопируйте `.env.example` в `.env`. Существующий файл
сохраните, проверьте параметры `S3_*` и подключения Airflow.
С компьютера endpoint — `localhost:8333`, внутри Docker — `http://seaweedfs:8333`.
HTTP-источник — `https://data.insideairbnb.com`. `.env` не добавляется в Git.

```bash
docker compose up --build -d
docker compose ps
docker compose exec airflow-scheduler airflow dags list-import-errors
```

Порт файлового интерфейса на компьютере — 8890, поскольку 8888 занят Jupyter.
Дождитесь готовности сервисов. Airflow: http://localhost:8080/.
SeaweedFS: http://localhost:8890/buckets/.

## 2. Исходный объект

Запустите DAG ЛР № 2 с логической датой из параметров ноутбука:

```bash
docker compose exec airflow-scheduler airflow dags trigger ingest_raw \
  --exec-date 2026-10-23T00:00:00+00:00 \
  --run-id lab03-source-2026-10-23
docker compose exec airflow-scheduler airflow dags unpause ingest_raw
```

Если такой запуск уже существует, проверьте успех задач, повторно создавать его
не требуется. Существующий raw-объект DAG пропускает. Для другой даты ingestion
измените оба пути в первой ячейке ноутбука и в отчёте.

```bash
uv run --env-file .env python scripts/read_raw.py --path \
  's3://raw/airbnb_amsterdam_listings/ingested_on=2026-10-23/listings.csv.gz'
```

## 3. Два запуска с чистыми ядрами

Откройте `notebooks/profile_quality.ipynb` в VS Code, выберите `.venv/bin/python`.
Дважды выполните **Restart Kernel → Run All**, сопоставьте два `RUN_RESULT`,
сохраните выводы и обновите отчёт.

Можно автоматизировать два запуска; дополнительные библиотеки устанавливаются
через `--with`, поэтому `pyproject.toml` и `uv.lock` остаются согласованы:

```bash
uv run --env-file .env --with 'nbformat>=5,<6' --with 'nbclient>=0.10,<1' \
  python scripts/verify_lab03.py
```

Скрипт сохраняет основной ноутбук с выводами второго запуска и
`docs/evidence/two_runs_s3.json`. Весь аналитический SQL остаётся в ноутбуке.
Оба Parquet записываются в бакет `staging` под префиксом
`airbnb_amsterdam_listings/source_ingested_on=2026-10-23/`.
Пустой карантин создаётся обязательно. Повторный запуск не дописывает строки.

## 4. Проверки и сдача

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
```

Проверка на SeaweedFS уже выполнена: DAG успешен, оба новых Jupyter-ядра дали
10 369 строк staging и пустой карантин. Доказательства и актуальный отчёт сохранены.
После изменений данных или правил повторите проверку и обновите отчёт.
Оформите PR из `lab-03` в `main` с подготовленным описанием.

Дополнительная диагностика без Docker/S3:

```bash
uv run python scripts/validate_local.py
```

Она запускает SQL дважды в новых процессах Python на Git-снимке, сохраняет
отдельный `docs/evidence/profile_quality_local.ipynb`, JSON с результатами
и локальные Parquet (они заменяют копии в `docs/evidence/`, но не S3-объекты).
Основной ноутбук не изменяется. Эти результаты не заменяют
обязательные объекты SeaweedFS и два чистых Jupyter-ядра.
