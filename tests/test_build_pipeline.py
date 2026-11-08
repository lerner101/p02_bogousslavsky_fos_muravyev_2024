"""Build readiness and dependency graph tests, using temporary source extracts."""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import prepare_public_data
from build_checks import check_inputs, required_extracts
from download_public_data import valid_download


def ready_sources(root):
    for name in required_extracts("research"):
        base = root / "_data/wrds" / name
        base.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"sample": [1]}).to_parquet(base.with_suffix(".parquet"), index=False)
        base.with_suffix(".json").write_text(json.dumps({"rows": 1}))
    public = root / "_data/public"
    folder = public / "iti_original_through_2019"
    counts = {}
    for year in range(2004, 2020):
        part = folder / f"year={year}" / "part-00000.parquet"
        part.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"sample": [1]}).to_parquet(part, index=False)
        counts[str(year)] = 1
    (folder / "manifest.json").write_text(json.dumps({"rows_by_year": counts}))
    (public / "InformationTradingVolatility_DataFile.csv").write_text(
        "ticker,date,CC_day_type,CO_day_type,OC_day_type\nA,03jan2005,1,0,1\n")


def test_preflight_catches_missing_year_partial_and_corrupt_manifest(tmp_path):
    ready_sources(tmp_path)
    assert check_inputs(tmp_path) == []
    base = tmp_path / "_data/wrds/crsp_daily/2019"
    base.with_suffix(".parquet").rename(base.with_suffix(".parquet.part"))
    errors = check_inputs(tmp_path)
    assert len(errors) == 1 and "2019" in errors[0] and ".part" in errors[0]
    base.with_suffix(".parquet.part").rename(base.with_suffix(".parquet"))
    base.with_suffix(".json").write_text('{"rows": 2}')
    assert "row-count mismatch" in check_inputs(tmp_path)[0]


def test_preflight_catches_missing_public_partition(tmp_path):
    ready_sources(tmp_path)
    part = tmp_path / "_data/public/iti_original_through_2019/year=2005/part-00000.parquet"
    part.unlink()
    assert any("year=2005" in error for error in check_inputs(tmp_path))


def test_bfkr_can_run_without_crsp_daily_but_research_cannot(tmp_path):
    ready_sources(tmp_path)
    (tmp_path / "_data/wrds/crsp_daily/2019.parquet").unlink()
    assert check_inputs(tmp_path, "bfkr") == []
    assert check_inputs(tmp_path, "research")


def test_default_graph_has_all_implemented_outputs_and_no_network_tasks(monkeypatch):
    monkeypatch.chdir(ROOT)
    namespace = runpy.run_path(str(ROOT / "dodo.py"))
    tasks = {name[5:]: fn() for name, fn in namespace.items() if name.startswith("task_")}
    producers = {str(path): name for name, task in tasks.items() for path in task.get("targets", [])}
    visited = set()

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        task = tasks[name]
        for dependency in task.get("task_dep", []):
            visit(dependency)
        for dependency in task.get("file_dep", []):
            if str(dependency) in producers:
                visit(producers[str(dependency)])

    for name in namespace["DOIT_CONFIG"]["default_tasks"]:
        visit(name)
    assert {"preflight", "tests", "13d_filings", "13d_transactions", "13d_links",
            "13d_authors_windows", "13d_labels", "13d_validation", "13d_extraction_eval",
            "bfkr_news", "bfkr_preview", "data_status", "build_summary"} <= visited
    assert not {"fetch_public", "prepare_public", "collect_wrds"} & visited
    for name in visited:
        for action in tasks[name].get("actions") or []:
            if isinstance(action, list):
                assert action[0] == sys.executable


def test_doit_clean_checkout_reports_missing_inputs(tmp_path):
    pytest.importorskip("doit")
    # Only preflight is selected: no project data, credentials or download targets.
    import shutil

    shutil.copy(ROOT / "dodo.py", tmp_path / "dodo.py")
    shutil.copytree(ROOT / "src", tmp_path / "src", ignore=shutil.ignore_patterns("__pycache__"))
    result = subprocess.run([sys.executable, "-m", "doit", "preflight"], cwd=tmp_path,
                            text=True, capture_output=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Required local data are missing" in output
    assert "Plain doit does not download data" in output
    assert "collect_wrds" in output
    assert not (tmp_path / "_data/wrds").exists()


def test_force_public_preparation_rebuilds_changed_archive(tmp_path, monkeypatch):
    from zipfile import ZipFile

    monkeypatch.setattr(prepare_public_data, "DATA", tmp_path)

    def archive(value):
        with ZipFile(tmp_path / "test.zip", "w") as z:
            z.writestr("test.csv", f"date,value\n2005-01-03,{value}\n")

    archive(1)
    prepare_public_data.partition("test.zip", "test.csv", "test", "%Y-%m-%d")
    archive(2)
    prepare_public_data.partition("test.zip", "test.csv", "test", "%Y-%m-%d", force=True)
    files = list((tmp_path / "test_through_2019").rglob("*.parquet"))
    assert len(files) == 1
    assert pd.read_parquet(files[0]).value.tolist() == [2]


def test_bfkr_downloader_rejects_html_response(tmp_path):
    name = "InformationTradingVolatility_DataFile.csv"
    path = tmp_path / name
    path.write_text('<html>Please sign in</html>')
    assert not valid_download(path, name)
    path.write_text("ticker,date,CC_day_type,CO_day_type,OC_day_type\nA,03jan2005,1,0,1\n")
    assert valid_download(path, name)
