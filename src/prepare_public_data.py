"""Convert downloaded public archives to compact, year-partitioned Parquet.

Keep original and extended ITI vintages separate. Preserve source headers and
units, except French factor percentages, which are converted to decimal returns.
Includes 2004 warm-up history; the intended analysis is 2005–2019.
Writes separate scoped outputs, preserving previously prepared wider files.
"""

import argparse
import io
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data" / "public"


def partition(archive, member, name, date_format, force=False):
    target = DATA / (name + "_through_2019")
    target.mkdir(exist_ok=True)
    if (target / "manifest.json").exists() and not force:
        print("Already prepared:", name, flush=True)
        return
    (target / "manifest.json").unlink(missing_ok=True)
    for p in target.glob("year=*/part-*.parquet"):
        p.unlink()
    counts, ranges = {}, {}
    with ZipFile(DATA / archive) as z, z.open(member) as source:
        for i, chunk in enumerate(pd.read_csv(source, chunksize=250000)):
            chunk["date"] = pd.to_datetime(chunk["date"].astype(str), format=date_format)
            chunk = chunk[chunk.date.between("2004-01-01", "2019-12-31")]
            for year, df in chunk.groupby(chunk.date.dt.year):
                folder = target / f"year={year}"
                folder.mkdir(exist_ok=True)
                df.to_parquet(folder / f"part-{i:05d}.parquet", index=False, compression="zstd")
                counts[int(year)] = counts.get(int(year), 0) + len(df)
                lo, hi = str(df.date.min().date()), str(df.date.max().date())
                prev = ranges.get(int(year), [lo, hi])
                ranges[int(year)] = [min(prev[0], lo), max(prev[1], hi)]
    (target / "manifest.json").write_text(json.dumps({"archive": archive,
        "member": member, "rows_by_year": counts, "dates_by_year": ranges,
        "units": "unchanged from source"}, indent=2))
    print("Prepared:", name, sum(counts.values()), "rows", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Rebuild scoped partitions from local archives")
    args = parser.parse_args()
    factors = []
    for filename, cols in [
        ("F-F_Research_Data_Factors_daily_CSV.zip", ["date", "mkt_rf", "smb", "hml", "rf"]),
        ("F-F_Momentum_Factor_daily_CSV.zip", ["date", "mom"]),
    ]:
        with ZipFile(DATA / filename) as z:
            text = z.read(z.namelist()[0]).decode("utf-8-sig")
        lines = [s for s in text.splitlines() if len(s.split(",")[0].strip()) == 8
                 and s.split(",")[0].strip().isdigit()]
        df = pd.read_csv(io.StringIO("\n".join(lines)), names=cols)
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
        df = df[df.date.between("2004-01-01", "2019-12-31")]
        for col in cols[1:]:
            df[col] = df[col].replace({-99.99: float("nan"), -999: float("nan")}) / 100
        factors.append(df)
    factors[0].merge(factors[1], on="date", validate="one_to_one").to_parquet(
        DATA / "ff4_daily_2004_2019.parquet", index=False)
    with ZipFile(DATA / "ITIs_extended_1993_2024.zip") as z:
        (DATA / "ITI_readme.txt").write_bytes(z.read("readme.txt"))
    partition("ITIs_extended_1993_2024.zip", "ITIs_original_1993_2019.csv", "iti_original", "%Y-%m-%d", args.force)
    partition("ITIs_extended_1993_2024.zip", "ITIs_extended_1993_2024.csv", "iti_extended", "%Y-%m-%d", args.force)
    partition("cpie_data.zip", "cpie_daily.csv", "pin_legacy_daily", "%Y%m%d", args.force)
    supplied_zip = ROOT / "Replication Code-20220087.zip"
    if supplied_zip.exists():
        with ZipFile(supplied_zip) as z, z.open(
            "Replication Code-20220087/return_predictability/pin_brown_annual.dta"
        ) as source:
            annual_pin = pd.read_stata(source)
        annual_pin = annual_pin[annual_pin.yearpin.between(2004, 2019)]
        annual_pin.to_parquet(DATA / "pin_brown_annual_2004_2010.parquet", index=False)


if __name__ == "__main__":
    main()
