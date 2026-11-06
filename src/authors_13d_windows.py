"""Recover the authors' Schedule 13D training windows from the posted ITI file.

The paper excludes Schedule 13D trading periods from the extrapolated sample (Section
3.3: "This step drops 0.35% of the sample"). In the posted original-vintage file this
shows up as stock-days where the three 13D-trained scores (ITI(13D), ITI(patient),
ITI(impatient)) are blank while ITI(insider) is present. File-wide that pattern covers
about 0.44% of rows, and inside windows of our rebuilt events it holds ~98% of the time
when it holds at all, against ~2% otherwise.

A window is a run of such blank days for one PERMNO, broken where consecutive blank
days are more than MAX_GAP_DAYS calendar days apart. Runs shorter than MIN_RUN_DAYS
trading days are dropped (isolated data gaps). The run's last day approximates the
filing date (the window ends on it); overlapping windows of one stock merge into a
single run, so a run can cover more than one of the authors' filings.

Output: THIRTEEN_D_DIR/authors_windows.parquet
    permno, start, end, n_days, approx_filing_date (= end)

Run: python src/authors_13d_windows.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from settings import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "_data" / "public" / "iti_original_through_2019"
MAX_GAP_DAYS = 7
MIN_RUN_DAYS = 10


def recover_windows(iti):
    blank = iti[iti["ITI(13D)"].isna() & iti["ITI(patient)"].isna()
                & iti["ITI(impatient)"].isna() & iti["ITI(insider)"].notna()]
    blank = blank[["permno", "date"]].sort_values(["permno", "date"])
    gap = blank.groupby("permno").date.diff().dt.days
    run = (gap.isna() | (gap > MAX_GAP_DAYS)).cumsum()
    w = blank.groupby(run).agg(permno=("permno", "first"), start=("date", "min"),
                               end=("date", "max"), n_days=("date", "size")).reset_index(drop=True)
    w = w[w.n_days >= MIN_RUN_DAYS].copy()
    w["approx_filing_date"] = w.end
    w["permno"] = w.permno.astype("int64")
    return w.reset_index(drop=True)


def main():
    files = sorted(SOURCE.glob("year=*/*.parquet"))
    cols = ["permno", "date", "ITI(13D)", "ITI(patient)", "ITI(impatient)", "ITI(insider)"]
    iti = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
    w = recover_windows(iti)
    out = config("THIRTEEN_D_DIR") / "authors_windows.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    w.to_parquet(out, index=False)
    by_year = w.end.dt.year.value_counts().sort_index()
    print(f"Recovered {len(w):,} windows (median {w.n_days.median():.0f} trading days); by end year: "
          + ", ".join(f"{y}: {n}" for y, n in by_year.items()))


if __name__ == "__main__":
    main()
