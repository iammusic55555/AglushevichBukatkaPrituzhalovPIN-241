"""Два запуска ноутбука в новых Jupyter-ядрах и сравнение результатов из S3.

uv run --env-file .env --with 'nbformat>=5,<6' --with 'nbclient>=0.10,<1' \
    python scripts/verify_lab03.py
"""

import json
import sys
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/profile_quality.ipynb"


def execute_once():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
    # Глобальный kernelspec python3 может указывать на другой Python.
    # Каждое ядро запускается интерпретатором текущего процесса.
    manager = KernelManager(kernel_name="python3")
    manager.kernel_spec.argv = [
        sys.executable,
        "-m",
        "ipykernel_launcher",
        "-f",
        "{connection_file}",
    ]
    client = NotebookClient(
        notebook, km=manager, timeout=300, resources={"metadata": {"path": str(ROOT)}}
    )
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    result = None
    for cell in notebook.cells:
        for output in cell.get("outputs", []):
            for line in output.get("text", "").splitlines():
                if line.startswith("RUN_RESULT="):
                    result = json.loads(line.removeprefix("RUN_RESULT="))
    if result is None:
        raise RuntimeError("Ноутбук не вернул результат проверки")
    nbformat.validate(notebook)
    return notebook, result


def main():
    results = []
    for number in (1, 2):
        notebook, result = execute_once()
        results.append(result)
        print(
            f"Запуск {number}: raw={result['raw']}; staging={result['staging']}; "
            f"карантин={result['quarantine']}",
            flush=True,
        )
    if results[0] != results[1]:
        raise AssertionError("Результаты двух независимых запусков различаются")
    nbformat.write(notebook, NOTEBOOK)
    evidence = ROOT / "docs/evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "two_runs_s3.json").write_text(
        json.dumps(
            {"execution": "fresh Jupyter kernels", "runs": results, "identical": True},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Два запуска совпадают. Ноутбук сохранён с выводами второго запуска.")


if __name__ == "__main__":
    main()
