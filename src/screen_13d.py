"""Shared CRSP helpers for Schedule 13D event screens.

`window_start_screens` applies the paper's footnote-5 screens at the beginning of the
filing window: CRSP share code 10/11, |price| >= MIN_PRICE and market cap >= MIN_MCAP,
measured on the first CRSP trading day on or after filing_date - WINDOW_CALENDAR_DAYS.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from settings import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WRDS = ROOT / "_data" / "wrds"


def load_crsp_daily(permnos, columns=("permno", "date", "prc", "shrout", "vol", "ret")):
    """CRSP daily rows for the given PERMNOs across all saved years."""
    permnos = pd.Series(pd.unique(pd.Series(permnos).dropna())).astype("int64")
    frames = []
    for path in sorted((WRDS / "crsp_daily").glob("*.parquet")):
        df = pd.read_parquet(path, columns=list(columns))
        frames.append(df[df.permno.isin(permnos)])
    out = pd.concat(frames, ignore_index=True)
    out["permno"] = out.permno.astype("int64")
    return out.sort_values(["permno", "date"]).reset_index(drop=True)


def window_start_screens(events, crsp=None):
    """Add window_start, prc0, mcap0, shrcd and pass_* columns to `events`
    (needs accession, permno, filing_date)."""
    ev = events.copy()
    ev["permno"] = ev.permno.astype("int64")
    ev["window_start"] = ev.filing_date - pd.to_timedelta(config("WINDOW_CALENDAR_DAYS"), unit="D")
    if crsp is None:
        crsp = load_crsp_daily(ev.permno, columns=("permno", "date", "prc", "shrout"))
    first = pd.merge_asof(ev.sort_values("window_start"),
                          crsp[["permno", "date", "prc", "shrout"]].rename(columns={"date": "d0"}).sort_values("d0"),
                          left_on="window_start", right_on="d0", by="permno", direction="forward")
    first.loc[first.d0 > first.filing_date, ["prc", "shrout"]] = pd.NA
    first["prc0"] = first.prc.abs()
    first["mcap0"] = first.prc0 * first.shrout * 1000
    names = pd.read_parquet(WRDS / "crsp_names.parquet", columns=["permno", "namedt", "nameendt", "shrcd"])
    names["permno"] = names.permno.astype("int64")
    sh = first[["accession", "permno", "filing_date"]].merge(names, on="permno")
    sh = sh[(sh.namedt <= sh.filing_date) & (sh.filing_date <= sh.nameendt)].drop_duplicates("accession")
    first = first.merge(sh[["accession", "shrcd"]], on="accession", how="left")
    first["pass_common_stock"] = first.shrcd.isin([10, 11])
    first["pass_price"] = (first.prc0 >= config("MIN_PRICE")).fillna(False)
    first["pass_mcap"] = (first.mcap0 >= config("MIN_MCAP")).fillna(False)
    return first.drop(columns=["d0", "prc", "shrout"]).reset_index(drop=True)
