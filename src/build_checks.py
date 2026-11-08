"""Validate the local inputs required by the implemented doit pipelines.

No network requests or credentials are used. A missing year must not silently
turn a full-period build into a truncated sample.
"""

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def required_extracts(component):
    common = ["crsp_names", "crsp_market", "crsp_compustat_links", "compustat_earnings"]
    thirteen = ["crsp_names", "crsp_market", "sec_cusip_links"]
    thirteen += [f"crsp_daily/{y}" for y in range(2004, 2020)]
    thirteen += [f"sec_13d_filings/{y}" for y in range(2005, 2020)]
    if component == "13d":
        return thirteen
    if component == "bfkr":
        return common
    if component == "research":
        return sorted(set(common + thirteen))
    if component == "wrds":
        result = common + thirteen + ["crsp_delistings", "sdc_ma"]
        for group, years in [("insider_transactions", range(2004, 2020)),
                             ("intraday_indicators", range(2004, 2020)),
                             ("crsp_taq_links", range(2004, 2020)),
                             ("markit_lending", range(2006, 2020)),
                             ("sec_13d_index", range(2005, 2020))]:
            result += [f"{group}/{y}" for y in years]
        return sorted(set(result))
    raise ValueError(f"Unknown component: {component}")


def check_extract(base):
    """A completed WRDS extract needs both a readable Parquet and its manifest."""
    import pyarrow.parquet as pq

    path, meta = base.with_suffix(".parquet"), base.with_suffix(".json")
    if not path.is_file() or not meta.is_file():
        return f"{base}: missing completed Parquet/JSON pair (.part files do not count)"
    try:
        obj = json.loads(meta.read_text())
        actual = pq.read_metadata(path).num_rows
        if actual != obj["rows"] or actual == 0:
            return f"{base}: empty extract or manifest row-count mismatch"
    except Exception as exc:
        return f"{base}: invalid extract ({exc})"
    return None


def check_iti(root, years):
    import pyarrow.parquet as pq

    folder = root / "_data/public/iti_original_through_2019"
    errors = []
    try:
        manifest = json.loads((folder / "manifest.json").read_text())
        expected = manifest["rows_by_year"]
    except (OSError, ValueError, KeyError) as exc:
        return [f"{folder}: missing or invalid preparation manifest ({exc})"]
    for year in years:
        files = sorted((folder / f"year={year}").glob("*.parquet"))
        try:
            count = sum(pq.read_metadata(p).num_rows for p in files)
            if not files or count == 0 or count != expected.get(str(year)):
                errors.append(f"{folder}/year={year}: missing partitions or row-count mismatch")
        except Exception as exc:
            errors.append(f"{folder}/year={year}: unreadable partition ({exc})")
    return errors


def check_inputs(root=ROOT, component="research"):
    errors = [err for name in required_extracts(component)
              if (err := check_extract(root / "_data/wrds" / name))]
    if component != "wrds":
        years = range(2005, 2016) if component == "bfkr" else range(2004, 2020)
        errors += check_iti(root, years)
    if component in ("bfkr", "research"):
        source = root / "_data/public/InformationTradingVolatility_DataFile.csv"
        if not source.is_file():
            errors.append(f"{source}: missing public BFKR source CSV")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--component", choices=["research", "13d", "bfkr", "wrds"], default="research")
    args = ap.parse_args()
    packages = ["pandas", "pyarrow", "decouple"]
    if args.component in ("research", "bfkr"):
        packages += ["matplotlib", "linearmodels"]
    if args.component in ("research", "13d"):
        packages += ["matplotlib", "tabulate"]
    missing_packages = [name for name in packages if importlib.util.find_spec(name) is None]
    if missing_packages:
        raise SystemExit("Missing Python packages: " + ", ".join(missing_packages)
                         + ". Install requirements.txt into the environment running doit.")
    # Current source readers use repository-local paths; do not accept overrides
    # that would make doit dependencies and the scripts refer to different files.
    from settings import config

    for key, expected in [("DATA_DIR", ROOT / "_data"), ("OUTPUT_DIR", ROOT / "_output"),
                          ("THIRTEEN_D_DIR", ROOT / "_data/derived/13d")]:
        if Path(config(key)).resolve() != expected.resolve():
            raise SystemExit(f"{key} must be {expected} for the current repository-local pipeline; "
                             "remove custom path overrides before building.")
    errors = check_inputs(component=args.component)
    if errors:
        message = ["Required local data are missing or invalid:", *[f"  - {e}" for e in errors], "",
                   "Git does not contain _data. Plain doit does not download data.",
                   "Public inputs: python -m doit fetch_public prepare_public",
                   "Licensed inputs: configure your own WRDS access, then python -m doit collect_wrds",
                   "A permitted complete _data transfer can be used instead of recollection.",
                   "See README.md and docs_src/site/project_overview/build.md."]
        raise SystemExit("\n".join(message))
    print(f"Input check passed: {args.component}. Completed files and expected years verified.")


if __name__ == "__main__":
    main()
