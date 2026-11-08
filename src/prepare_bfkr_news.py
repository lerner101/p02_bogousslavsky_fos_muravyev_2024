"""Link the public BFKR VIP classifications to dated CRSP common-stock IDs.

Also prepares unadjusted Compustat earnings dates for a preliminary analysis.
Those dates are NOT the authors' volume-adjusted earnings dates.
Run from the repository root: python src/prepare_bfkr_news.py
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WRDS = ROOT / "_data/wrds"
OUT = ROOT / "_data/derived/bfkr"
SOURCE = ROOT / "_data/public/InformationTradingVolatility_DataFile.csv"


def link_news(news, names):
    """Use exact ticker and inclusive name-record dates; reject ambiguous IDs.

    No current-ticker backfill, punctuation substitutions, or nearest-date links.
    Overlapping name records for the same PERMNO are harmless.
    """
    news = news.copy().reset_index(drop=True)
    news["ticker"] = news.ticker.astype("string").str.strip().str.upper()
    if news.duplicated(["ticker", "date"]).any():
        raise ValueError("Duplicate source ticker/date keys")
    if not news.CC_day_type.isin([0, 1, 2, 3]).all():
        raise ValueError("Missing or invalid CC_day_type classification")
    news["source_row"] = news.index
    n = names[["ticker", "permno", "namedt", "nameendt", "shrcd"]].copy()
    n["ticker"] = n.ticker.astype("string").str.strip().str.upper()
    n = n[n.shrcd.isin([10, 11]) & n.ticker.notna() & n.permno.notna()]
    candidates = news[["source_row", "ticker", "date"]].merge(n, on="ticker")
    candidates = candidates[candidates.date.between(candidates.namedt, candidates.nameendt)]
    candidates = candidates.drop_duplicates(["source_row", "permno"])
    counts = candidates.groupby("source_row").size()
    news["link_status"] = news.source_row.map(counts).fillna(0).map(
        lambda k: "unmatched" if k == 0 else "linked" if k == 1 else "ambiguous")
    unique = candidates[candidates.source_row.map(counts) == 1]
    news = news.merge(unique[["source_row", "permno"]], on="source_row", how="left",
                      validate="one_to_one")
    news["permno"] = news.permno.astype("Int64")
    # Multiple source tickers must not silently create multiple observations per stock-day.
    duplicate = news.permno.notna() & news.duplicated(["permno", "date"], keep=False)
    news.loc[duplicate, "link_status"] = "duplicate_stock_day"
    return news


def link_earnings(earnings, links):
    """Dated primary CCM links; no use of a firm's current CUSIP."""
    e = earnings[["gvkey", "rdq"]].dropna().drop_duplicates().copy()
    e["rdq"] = pd.to_datetime(e.rdq)
    links = links[links.linktype.isin(["LC", "LU"]) & links.linkprim.isin(["P", "C"])].copy()
    links["linkenddt"] = pd.to_datetime(links.linkenddt).fillna(pd.Timestamp("2099-12-31"))
    m = e.merge(links, on="gvkey")
    m = m[m.rdq.between(m.linkdt, m.linkenddt) & m.lpermno.notna()]
    m = m.rename(columns={"lpermno": "permno", "rdq": "date"})
    m["permno"] = m.permno.astype("int64")
    return m[["permno", "date"]].drop_duplicates().sort_values(["permno", "date"])


def main():
    news = pd.read_csv(SOURCE, dtype={"ticker": "string"})
    news["date"] = pd.to_datetime(news.date, format="%d%b%Y", errors="raise")
    linked = link_news(news, pd.read_parquet(WRDS / "crsp_names.parquet"))
    OUT.mkdir(parents=True, exist_ok=True)
    linked.to_parquet(OUT / "news_link_audit.parquet", index=False)
    good = linked[linked.link_status == "linked"].drop(columns=["source_row", "link_status"])
    good.to_parquet(OUT / "news_daily.parquet", index=False)
    earnings = link_earnings(pd.read_parquet(WRDS / "compustat_earnings.parquet"),
                             pd.read_parquet(WRDS / "crsp_compustat_links.parquet"))
    earnings.to_parquet(OUT / "earnings_unadjusted.parquet", index=False)
    yearly = linked.assign(year=linked.date.dt.year).groupby(["year", "link_status"]).size()
    metadata = {
        "source": str(SOURCE.relative_to(ROOT)),
        "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "source_rows": len(news), "source_tickers": news.ticker.nunique(),
        "date_range": [str(news.date.min().date()), str(news.date.max().date())],
        "link_counts": linked.link_status.value_counts().to_dict(),
        "linked_rows_by_year": good.groupby(good.date.dt.year).size().to_dict(),
        "earnings_rows": len(earnings),
        "earnings_timing": "Raw Compustat rdq; no after-hours volume adjustment",
    }
    (OUT / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    report = ROOT / "_output/bfkr_preparation.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# BFKR news preparation\n\n```json\n" + json.dumps(metadata, indent=2)
                      + "\n```\n\nLink outcomes by year:\n\n```\n" + yearly.to_string()
                      + "\n```\n\nUnmatched, ambiguous and duplicate stock-days are retained only in "
                      "news_link_audit.parquet. Dates outside the local CRSP name history can be unmatched.\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
