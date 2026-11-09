"""Build Schedule 13D event screens and daily trade-day labels.

Inputs (THIRTEEN_D_DIR): filings.parquet, filing_links.parquet, transactions.parquet,
extraction_log.parquet; CRSP daily/names from _data/wrds.

events.parquet: one row per filing (schema_13d.EVENTS). Screens, applied in order, with
the first failure recorded in `exclusion_reason`:
    original           not an amendment ("Amendment No. N", N >= 1) filed as SC 13D
                       (paper, footnote 5)
    linked             CRSP PERMNO found and the issuer name matches CRSP's name history
    common_stock       CRSP share code 10 or 11 on the filing date
    price, mcap        |price| >= MIN_PRICE and market cap >= MIN_MCAP on the first CRSP
                       day of the window (paper, footnote 5)
    no_derivatives     no extracted row in the window is a derivative trade (footnote 5)
    has_trades         at least one priced, dated trade by a group member in the window
    duplicate_event    another included filing has the same (permno, filing_date); the
                       authors identify an event by that pair, so trades are pooled under
                       the first accession
Events filed after PAPER_13D_LAST_YEAR are built but flagged `in_paper_period = False`.
`in_authors_sample` marks events matching a window recovered from the posted ITI file
(src/authors_13d_windows.py), i.e. events the authors very likely used.

labels_daily.parquet: one row per included event and CRSP trading day with
filing_date - WINDOW_CALENDAR_DAYS <= date <= filing_date (schema_13d.LABELS_DAILY), using
the authors' column names: itrade (bought or sold that day), ivol (signed dollars,
sales negative), days_to_filing (calendar days), filing (event id).
13Dturn = gross dollars traded / (prc * shrout * 1000), so same-day buys and sells
add rather than net out (equals |ivol| / (prc * shrout * 1000) on one-sided days); 13Dvol/vol = 13Dturn / turn capped at 1
(ITI_main.py). Values are not winsorized here; the authors winsorize at 0.05% in analysis.

Run: python src/build_13d_labels.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_13d import EVENTS, LABELS_DAILY  # noqa: E402
from screen_13d import load_crsp_daily, window_start_screens  # noqa: E402
from settings import config  # noqa: E402

SCREENS = ["original", "linked", "common_stock", "price", "mcap", "no_derivatives", "has_trades"]


def cast(df, schema):
    for col, dtype in schema.items():
        if col not in df:
            df[col] = pd.NA
        df[col] = df[col].astype(dtype)
    return df[list(schema)]


def authors_match(ev, windows, before=3, after=7):
    """True where a filing matches a recovered authors' window: same PERMNO and filing
    date from `before` days before to `after` days after the window's last day. <NA> if
    the windows file is unavailable."""
    if windows is None:
        return pd.Series(pd.NA, index=ev.index, dtype="boolean")
    e = ev[["accession", "permno", "filing_date"]].dropna(subset=["permno"]).copy()
    e["permno"] = e.permno.astype("int64")
    m = e.merge(windows[["permno", "end"]], on="permno")
    gap = (m.filing_date - m.end).dt.days
    hit = set(m.loc[(gap >= -before) & (gap <= after), "accession"])
    return ev.accession.isin(hit).astype("boolean")


def build(filings, links, tx, crsp=None, authors_windows=None):
    ev = filings[["accession", "filing_date", "is_amendment"]].merge(
        links[["accession", "permno", "link_method", "name_ok"]], on="accession", how="left")
    ev["pass_original"] = ~ev.pop("is_amendment").astype("boolean").fillna(False).astype(bool)
    ev["pass_linked"] = ev.permno.notna() & ev.name_ok.astype("boolean").fillna(False).astype(bool)
    linked = ev[ev.pass_linked].drop(columns=["name_ok"])
    crsp = crsp if crsp is not None else load_crsp_daily(linked.permno)
    scr = window_start_screens(linked, crsp=crsp)
    ev = ev.drop(columns=["name_ok"]).merge(
        scr[["accession", "window_start", "pass_common_stock", "pass_price", "pass_mcap"]],
        on="accession", how="left")

    # In-window trades by group members (the extractor already applies the date window
    # plus a small slack; enforce the exact window here).
    t = tx.merge(ev[["accession", "filing_date"]], on="accession")
    lo = t.filing_date - pd.to_timedelta(config("WINDOW_CALENDAR_DAYS"), unit="D")
    t = t[(t.trade_date >= lo) & (t.trade_date <= t.filing_date)]
    deriv = t.groupby("accession").is_derivative.any()
    usable = t[~t.is_derivative.astype(bool) & t.is_group_member.astype(bool) & t.price.notna()]
    ev["n_transactions"] = ev.accession.map(usable.groupby("accession").size()).fillna(0)
    ev["pass_no_derivatives"] = ~ev.accession.map(deriv).fillna(False).astype(bool)
    ev["pass_has_trades"] = ev.n_transactions > 0
    for s in ["common_stock", "price", "mcap"]:
        ev[f"pass_{s}"] = ev[f"pass_{s}"].astype("boolean").fillna(False).astype(bool)

    ev["exclusion_reason"] = pd.Series(pd.NA, index=ev.index, dtype="string")
    for s in reversed(SCREENS):
        ev.loc[~ev[f"pass_{s}"], "exclusion_reason"] = s
    ev["included"] = ev.exclusion_reason.isna()
    # One event per (permno, filing_date): pool trades under the first accession.
    inc = ev[ev.included].sort_values("accession")
    first = inc.groupby(["permno", "filing_date"]).accession.transform("first")
    dup = inc.accession != first
    ev.loc[dup[dup].index, ["included", "exclusion_reason"]] = [False, "duplicate_event"]
    pool = dict(zip(inc.accession, first))
    ev["in_paper_period"] = ev.filing_date.dt.year <= config("PAPER_13D_LAST_YEAR")
    ev["in_authors_sample"] = authors_match(ev, authors_windows)
    ev = ev.sort_values(["filing_date", "accession"]).reset_index(drop=True)
    ev["filing"] = pd.Series(pd.NA, index=ev.index, dtype="Int64")
    ev.loc[ev.included, "filing"] = np.arange(ev.included.sum())
    events = cast(ev, EVENTS)

    # Daily labels.
    inc = events[events.included]
    usable = usable[usable.accession.isin(pool)].assign(accession=lambda d: d.accession.map(pool))
    usable["gross"] = (usable.shares * usable.price).abs()
    usable["dollars"] = np.where(usable.side == "sell", -1, 1) * usable.gross
    daily = usable.groupby(["accession", "trade_date"]).agg(
        ivol=("dollars", "sum"), gross_dollars=("gross", "sum"), n_trades=("shares", "size"),
        shares_bought=("shares", lambda s: s[usable.loc[s.index, "side"] == "buy"].sum()),
        shares_sold=("shares", lambda s: s[usable.loc[s.index, "side"] == "sell"].sum()),
    ).reset_index().rename(columns={"trade_date": "date"})
    c = crsp[["permno", "date", "prc", "shrout", "vol"]]
    w = inc[["accession", "filing", "permno", "filing_date", "window_start",
             "in_authors_sample"]].merge(c, on="permno")
    w = w[(w.date >= w.window_start) & (w.date <= w.filing_date)]
    lab = w.merge(daily, on=["accession", "date"], how="left")
    for col in ["ivol", "gross_dollars", "shares_bought", "shares_sold", "n_trades"]:
        lab[col] = lab[col].fillna(0)
    lab["itrade"] = (lab.n_trades > 0).astype("int8")
    lab["days_to_filing"] = (lab.filing_date - lab.date).dt.days
    lab["patient"] = lab.days_to_filing > config("IMPATIENT_CALENDAR_DAYS")
    lab["prc"] = lab.prc.abs()
    lab["turn"] = lab.vol / (lab.shrout * 1000)
    lab["13Dturn"] = lab.gross_dollars / (lab.prc * lab.shrout * 1000)
    ratio = np.where(lab.turn > 0, lab["13Dturn"] / lab.turn, 0.0)
    lab["13Dvol/vol"] = np.minimum(ratio, 1.0)
    lab["in_paper_period"] = lab.filing_date.dt.year <= config("PAPER_13D_LAST_YEAR")
    labels = cast(lab.sort_values(["filing", "date"]).reset_index(drop=True), LABELS_DAILY)

    # Trades whose date is not a CRSP trading day for the stock cannot be labelled.
    matched = daily.merge(labels[["accession", "date"]], on=["accession", "date"], how="inner")
    off_days = len(daily) - len(matched)
    return events, labels, off_days


def main():
    d = config("THIRTEEN_D_DIR")
    filings = pd.read_parquet(d / "filings.parquet")
    links = pd.read_parquet(d / "filing_links.parquet")
    tx = pd.read_parquet(d / "transactions.parquet")
    aw = d / "authors_windows.parquet"
    windows = pd.read_parquet(aw) if aw.exists() else None
    if windows is None:
        print("authors_windows.parquet not found: in_authors_sample left empty "
              "(run src/authors_13d_windows.py)")
    events, labels, off_days = build(filings, links, tx, authors_windows=windows)
    events.to_parquet(d / "events.parquet", index=False)
    labels.to_parquet(d / "labels_daily.parquet", index=False)
    funnel = events.exclusion_reason.fillna("included").value_counts()
    print("Event funnel:\n" + funnel.to_string())
    inc = events[events.included]
    print(f"Included events: {len(inc):,} ({inc.in_paper_period.sum():,} filed 2005-"
          f"{config('PAPER_13D_LAST_YEAR')}); label rows: {len(labels):,}; "
          f"itrade mean: {labels.itrade.mean():.3f}; trade-days not on a CRSP trading day: {off_days}")


if __name__ == "__main__":
    main()
