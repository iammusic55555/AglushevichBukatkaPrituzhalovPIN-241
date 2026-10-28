"""Диагностика SQL на Git-снимке: два новых процесса Python, без S3.

Это дополнительная проверка. Она не заменяет два запуска на SeaweedFS.
Главный ноутбук не изменяется; диагностическая копия сохраняется в docs/evidence.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"
NOTEBOOK = ROOT / "notebooks/profile_quality.ipynb"


def worker(output):
    os.chdir(ROOT)
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    namespace = {"__name__": "__main__"}
    number = 0
    notebook["metadata"]["lab03_execution"] = "local Git snapshot; fresh Python process; no S3"
    notebook["cells"][0]["source"] = [
        "# Локальная диагностика SQL — не запуск на S3\n",
        "Все вычисления выполнены на Git-снимке в новом процессе Python.\n",
        "Основной ноутбук и проверка на SeaweedFS находятся отдельно.\n",
    ]
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        number += 1
        source = "".join(cell["source"])
        tags = cell["metadata"].get("tags", [])
        if "parameters" in tags:
            source = (
                "RAW_PATH = 'data/source/listings.csv.gz'\n"
                "ANALYTICAL_PERIOD = ('2026-06-15', '2026-06-24')\n"
                "OUTPUT_PREFIX = 'docs/evidence/'\n"
            )
        if "connection" in tags:
            source = source.split("raw_url = urlsplit(RAW_PATH)")[0]
            for unused in [
                "import os\n",
                "from datetime import date\n",
                "from urllib.parse import urlsplit\n",
                "import boto3\n",
                "from common.s3 import configure_s3  # noqa: E402\n",
            ]:
                source = source.replace(unused, "")
            source += """
def raw_fingerprint():
    payload = Path(RAW_PATH).read_bytes()
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
raw_before = raw_fingerprint()
con = duckdb.connect()
con.execute("SET preserve_insertion_order = true")
EXECUTION_ENVIRONMENT = "local Git snapshot; fresh Python process; no S3"
print("Среда:", EXECUTION_ENVIRONMENT)
"""
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            exec(compile(source, f"{NOTEBOOK}:cell-{number}", "exec"), namespace)
        cell["source"] = source.splitlines(True)
        cell["execution_count"] = number
        cell["outputs"] = [
            {
                "output_type": "stream",
                "name": "stdout",
                "text": captured.getvalue().splitlines(True),
            }
        ]
    Path(output).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(namespace["run_result"], ensure_ascii=False))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
        return
    EVIDENCE.mkdir(exist_ok=True)
    results = []
    for i in (1, 2):
        proc = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                str(EVIDENCE / "profile_quality_local.ipynb"),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if proc.returncode:
            raise RuntimeError(proc.stderr)
        result = json.loads(proc.stdout.splitlines()[-1])
        results.append(result)
        print(
            f"Локальный запуск {i}: {result['raw']} → "
            f"{result['staging']} + {result['quarantine']}"
        )
    assert results[0] == results[1], "Результаты различаются"
    (EVIDENCE / "two_runs_local.json").write_text(
        json.dumps(
            {
                "execution": "local Git snapshot; fresh Python processes; no S3",
                "runs": results,
                "identical": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print("Результаты совпали. Основной ноутбук не изменялся.")


if __name__ == "__main__":
    main()
