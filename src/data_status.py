"""Report completed, incomplete and failed data extracts without reading values."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
END_YEAR = 2019


def main():
    data = ROOT / "_data"
    wrds = data / "wrds"
    groups = {}
    failures = []
    later_files = []
    for meta in sorted(wrds.rglob("*.json")):
        # Supplemental aggregates have YYYYMMDD filenames, not YYYY extracts.
        # They are a bounded acquisition and must not count as complete years.
        if meta.is_relative_to(wrds / "iti_supplemental"):
            continue
        if meta.stem.isdigit() and int(meta.stem) > END_YEAR:
            later_files.append(str(meta.relative_to(data)))
            continue
        if meta.name.endswith(".error.json"):
            # A cancelled initial unbounded link query was replaced by yearly
            # extracts. It does not indicate failure of those replacements.
            if meta.name != "crsp_taq_links.error.json":
                failures.append(str(meta.relative_to(data)))
            continue
        obj = json.loads(meta.read_text())
        path = meta.with_suffix(".parquet")
        if not path.exists():
            continue
        actual_rows = pq.read_metadata(path).num_rows
        if actual_rows != obj["rows"]:
            raise ValueError(f"Row count mismatch: {path}")
        group = meta.parent.name if meta.parent != wrds else meta.stem
        g = groups.setdefault(group, {"files": 0, "rows": 0, "bytes": 0, "years": []})
        g["files"] += 1
        g["rows"] += actual_rows
        g["bytes"] += path.stat().st_size
        if meta.stem.isdigit():
            g["years"].append(int(meta.stem))
    lines = ["# Data acquisition status", "",
             f"Snapshot: {datetime.now(UTC).isoformat()}", "",
             "Completed files only; a readable Parquet footer and matching manifest row count were checked.", "",
             "Scope: through 2019, including 2004 warm-up history. Wider combined source extracts must be date-filtered before analysis.", "",
             "| Source | Complete files | Years complete | Rows | Size (GiB) | Completed years |",
             "|---|---:|---:|---:|---:|---|"]
    for name, obj in sorted(groups.items()):
        first_year = 2005 if name.startswith("sec_13d") else 2006 if name == "markit_lending" else 2004
        progress = f"{len(obj['years'])}/{END_YEAR-first_year+1}" if obj["years"] else "—"
        lines.append(f"| {name} | {obj['files']} | {progress} | {obj['rows']:,} | {obj['bytes']/2**30:.3f} | "
                     + ", ".join(map(str, obj["years"])) + " |")
    supplemental = []
    for meta in sorted((wrds / "iti_supplemental/daily").glob("*.json")):
        try:
            obj = json.loads(meta.read_text())
        except json.JSONDecodeError:
            continue  # A concurrent collector may be publishing this sidecar.
        if meta.with_suffix(".parquet").exists():
            supplemental.append((meta, obj))
    if supplemental:
        newest = max(obj["version"] for _, obj in supplemental)
        active = [(p, obj) for p, obj in supplemental if obj["version"] == newest]
        rows, size = 0, 0
        for p, obj in active:
            path = p.with_suffix(".parquet")
            count = pq.read_metadata(path).num_rows
            if count != obj["rows"]:
                raise ValueError(f"Supplemental row count mismatch: {path}")
            rows += count
            size += path.stat().st_size
        lines.append(f"| ITI supplemental TAQ (bounded, v{newest}) | {len(active)} | — | {rows:,} | "
                     f"{size/2**30:.3f} | Bounded daily extract; see ML acquisition report |")
    for name in ["iti_original", "iti_extended", "pin_legacy_daily"]:
        p = data / "public" / (name + "_through_2019")
        manifest = p / "manifest.json"
        if manifest.exists():
            obj = json.loads(manifest.read_text())
            rows = sum(obj["rows_by_year"].values())
            files = list(p.rglob("*.parquet"))
            actual_rows = sum(pq.read_metadata(f).num_rows for f in files)
            if actual_rows != rows:
                raise ValueError(f"Public partition count mismatch: {name}")
            size = sum(f.stat().st_size for f in files) / 2**30
            lines.append(f"| {name} | {len(files)} | {len(obj['rows_by_year'])}/{min(2012 if name == 'pin_legacy_daily' else END_YEAR, END_YEAR)-2004+1} | {rows:,} | {size:.3f} | "
                         + ", ".join(sorted(obj["rows_by_year"])))
            lines[-1] += " |"
    factors = data / "public" / "ff4_daily_2004_2019.parquet"
    if factors.exists():
        lines.append(f"| FF4 daily factors | 1 | 16/16 | {pq.read_metadata(factors).num_rows:,} | "
                     f"{factors.stat().st_size/2**30:.3f} | 2004–2019 |")
    news = data / "public" / "InformationTradingVolatility_DataFile.csv"
    news_manifest = data / "derived" / "bfkr" / "manifest.json"
    if news_manifest.exists():
        obj = json.loads(news_manifest.read_text())
        path = news_manifest.parent / "news_daily.parquet"
        if path.exists():
            rows = pq.read_metadata(path).num_rows
            if rows != obj["link_counts"].get("linked", 0):
                raise ValueError("BFKR linked row count differs from manifest")
            lines.append(f"| BFKR linked news | 1 | — | {rows:,} | "
                         f"{path.stat().st_size/2**30:.3f} | "
                         + ", ".join(sorted(obj["linked_rows_by_year"])) + " |")
    partials = list(data.rglob("*.part"))
    incomplete = [str(p.relative_to(data)) for p in partials
                  if not (p.name[:4].isdigit() and int(p.name[:4]) > END_YEAR)]
    later_partials = [str(p.relative_to(data)) for p in partials
                      if p.name[:4].isdigit() and int(p.name[:4]) > END_YEAR]
    ml = data / "derived/ml_model"
    feature_manifest = ml / "features_manifest.json"
    features_ready = ((ml / "features.parquet").exists() and feature_manifest.exists()
                      and not json.loads(feature_manifest.read_text()).get("partial_acquisition", True))
    model_ready = all((ml / name).exists() for name in ["iti_13d.json", "model_manifest.json", "oof_predictions.parquet"])
    gaps = ["independent 13D label verification", "BCL CPIE"]
    if not news.exists():
        gaps.append("BFKR news classifications")
    gaps.append("full-universe feature/scoring coverage" if features_ready else "supplemental intraday inputs")
    gaps.append("additional ITI model variants" if model_ready else "original training artifacts or retrained models")
    lines += ["", "Incomplete files (not usable yet): " + (", ".join(incomplete) or "none"),
              "", f"Retained later-year WRDS files outside scope: {len(later_files)}. Previously prepared wider public files are also retained.",
              "", "Stopped later-year partial files (not active downloads): " + (", ".join(later_partials) or "none"),
              "", "Failed extracts: " + (", ".join(failures) or "none"), "",
              "BFKR source CSV: " + (f"present ({news.stat().st_size/2**20:.1f} MiB). "
                  "Figure 4(c) still needs adjusted earnings dates and the complete control panel."
                  if news.exists() else "missing."), "",
              "Project ITI(13D): " + ("fitted model and held-out predictions present." if model_ready else "not yet fitted."), "",
              "Remaining gaps: " + "; ".join(gaps) + ".", "",
              "See docs_src/site/project_overview/data_acquisition.md for scope and definitions."]
    report = ROOT / "_output" / "data_acquisition_status.md"
    report.parent.mkdir(exist_ok=True)
    report.write_text("\n".join(lines) + "\n")
    print(report.read_text())


if __name__ == "__main__":
    main()
