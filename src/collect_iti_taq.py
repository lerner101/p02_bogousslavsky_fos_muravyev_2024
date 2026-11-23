"""Resumable Table IA.3 supplemental TAQ extraction; explicit network command.

Pilot: python src/collect_iti_taq.py --pilot
Training histories + ten scoring stocks: python src/collect_iti_taq.py
Each day is atomic, with a fingerprint of its requested security universe.
"""
import argparse
import hashlib
import json
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from psycopg2 import sql

from collect_wrds import connect

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "_data/wrds/iti_supplemental"
OUT = ROOT / "_output/ml_model"
VERSION = 2


def requested_days(pilot=False):
    """Training windows plus 400 calendar days of feature history; bounded scoring."""
    labels = pd.read_parquet(ROOT / "_data/derived/13d/labels_daily.parquet")
    labels = labels[labels.filing_date.dt.year.between(2005, 2018)]
    events = labels.groupby(["permno", "filing"]).agg(start=("date", "min"), end=("date", "max")).reset_index()
    # Pick scoring stocks deterministically, favoring long available histories.
    bookends = []
    for year in (2004, 2019):
        d = pd.read_parquet(ROOT / f"_data/wrds/crsp_daily/{year}.parquet", columns=["permno"])
        counts = d.groupby("permno").size()
        bookends.append(set(counts[counts >= 200].index))
    candidates = bookends[0] & bookends[1]
    stocks = labels[labels.permno.isin(candidates)].groupby("permno").size().sort_values(
        ascending=False, kind="stable").head(10).index
    frames = []
    for year in range(2004, 2020):
        links = pd.read_parquet(ROOT / f"_data/wrds/crsp_taq_links/{year}.parquet")
        links = links[links.permno.isin(labels.permno.unique())].copy()
        links["date"] = pd.to_datetime(links.date)
        active = links.merge(events, on="permno")
        active = active[active.date.between(active.start - pd.Timedelta(days=400), active.end)]
        if pilot:
            active = links[links.date == links.date.min()].sort_values("permno").head(3) if year in (2004, 2019) else links.iloc[:0]
        else:
            active = pd.concat([active, links[links.permno.isin(stocks)]], ignore_index=True)
        active["sym_suffix"] = active.sym_suffix.fillna("").astype(str)
        active = active[["date", "permno", "sym_root", "sym_suffix"]].drop_duplicates()
        # Ambiguous symbol/stock mappings are rejected, not arbitrarily selected.
        active = active[~active.duplicated(["date", "sym_root", "sym_suffix"], keep=False)]
        active = active[~active.duplicated(["date", "permno"], keep=False)]
        frames.append(active)
    return pd.concat(frames).sort_values(["date", "permno"]).reset_index(drop=True)


def interval_features(intervals):
    """13 endpoints at 10:00..16:00 and 13 volume bins at 09:30..16:00.

    Missing endpoint => dependent daily measure missing; no stale previous-day fill.
    Depth is the sum of bid/ask dollar depth; imbalance is ask minus bid dollars.
    """
    rows = []
    for permno, x in intervals.groupby("permno"):
        x = x.set_index("bucket").reindex(range(13))
        mid = pd.to_numeric(x.mid, errors="coerce")
        vol = pd.to_numeric(x.volume, errors="coerce")
        ret = mid / mid.shift() - 1
        r = ret.iloc[1:]
        rows.append({"permno": int(permno), "mid_1000": mid.iloc[0], "mid_1200": mid.iloc[4],
                     "mid_1400": mid.iloc[8], "mid_close": mid.iloc[12],
                     "rv_in": (r**2).sum(min_count=12),
                     "autocorr_in": r.autocorr() if r.notna().all() and r.std() > 0 else np.nan,
                     "last_return": r.iloc[-1], "volume_open": vol.iloc[0],
                     "market_volume": vol.sum(min_count=13),
                     "svol_am": vol.iloc[1:5].sum(min_count=4),
                     "svol_pm": vol.iloc[9:13].sum(min_count=4),
                     "illiq_in": (r.abs() / vol.iloc[1:].replace(0, np.nan)).mean()
                     if r.notna().all() and vol.notna().all() else np.nan})
    return pd.DataFrame(rows)


@lru_cache(maxsize=64)
def quote_order(conn, year):
    """Use sub-microsecond ordering when present, deterministic tie breaks otherwise."""
    with conn.cursor() as cur:
        cur.execute("""SELECT column_name FROM information_schema.columns
                       WHERE table_schema=%s AND table_name=%s AND column_name='time_m_nano'""",
                    (f"taqm_{year}", f"complete_nbbo_{year}"))
        nano = bool(cur.fetchone())
    return sql.SQL("time_m DESC, " + ("time_m_nano DESC, " if nano else "") +
                   "best_bid DESC,best_ask ASC,best_bidsizeshares DESC,best_asksizeshares DESC")


def collect_day(conn, date, universe):
    """Fetch endpoint NBBOs and interval share volumes, aggregate on WRDS.

    complete_nbbo is the WRDS consolidated NBBO product. Keep positive uncrossed
    quotes with positive displayed sizes. At each endpoint use the last valid
    same-day quote, limited to the preceding 30 minutes.
    Trades: positive price/size, correction 00, regular/odd-lot sale conditions
    (blank/@/E/F/I). Odd lots contribute to volume even though their historical
    absence is handled separately in the odd-lot count feature.
    """
    year, stamp = date.year, date.strftime("%Y%m%d")
    roots = tuple(sorted(universe.sym_root.unique()))
    # Suffix matching is performed inside SQL, preserving share classes.
    values = ",".join(["(%s,%s,%s)"] * len(universe))
    params = []
    for row in universe.itertuples():
        params.extend([int(row.permno), row.sym_root, row.sym_suffix])
    query = sql.SQL("""
      WITH u(permno,root,suffix) AS (VALUES {values}),
      endpoints AS (
        SELECT u.*, b, time '10:00' + b*interval '30 minutes' AS endpoint
        FROM u CROSS JOIN generate_series(0,12) b
      ), mids AS (
        SELECT e.permno,e.b AS bucket,q.mid FROM endpoints e
        LEFT JOIN LATERAL (
          SELECT (best_bid+best_ask)/2.0 AS mid FROM {quotes} q
          WHERE q.sym_root=e.root AND coalesce(q.sym_suffix,'')=e.suffix
          AND q.time_m <= e.endpoint AND q.time_m >= e.endpoint-interval '30 minutes'
          AND best_bid>0 AND best_ask>=best_bid
          AND best_bidsizeshares>0 AND best_asksizeshares>0
          ORDER BY {quote_order} LIMIT 1
        ) q ON true
      ), volumes AS (
        SELECT u.permno,
          least(12,floor(extract(epoch FROM (t.time_m-time '09:30'))/1800)::integer) AS bucket,
          sum(t.size)::double precision AS volume
        FROM {trades} t JOIN u ON t.sym_root=u.root AND coalesce(t.sym_suffix,'')=u.suffix
        WHERE t.time_m>=time '09:30' AND t.time_m<=time '16:00'
          AND t.price>0 AND t.size>0 AND trim(t.tr_corr::text)='00'
          AND regexp_replace(coalesce(t.tr_scond,''),'[@EFI ]','','g')=''
        GROUP BY u.permno,bucket
      )
      SELECT m.*,coalesce(v.volume,0) AS volume FROM mids m
      LEFT JOIN volumes v USING(permno,bucket) ORDER BY m.permno,m.bucket
    """).format(values=sql.SQL(values), quotes=sql.Identifier(f"taqm_{year}", f"complete_nbbo_{stamp}"),
                trades=sql.Identifier(f"taqm_{year}", f"ctm_{stamp}"), quote_order=quote_order(conn, year))
    with conn.cursor() as cur:
        cur.execute(query, params)
        intervals = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
        cur.execute(sql.SQL("""SELECT sym_root,coalesce(sym_suffix,'') AS sym_suffix,
          bestofrdepth_dollar_tw,bestbiddepth_dollar_tw,total_vol_m
          FROM {} WHERE date=%s AND sym_root IN %s""").format(
              sql.Identifier(f"taqm_{year}", f"wrds_iid_{year}")), (date.date(), roots))
        depth = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
    feat = interval_features(intervals)
    depth = universe.merge(depth, on=["sym_root", "sym_suffix"], validate="one_to_one")
    depth["depth_dollar"] = depth.bestofrdepth_dollar_tw + depth.bestbiddepth_dollar_tw
    depth["depth_imb"] = depth.bestofrdepth_dollar_tw - depth.bestbiddepth_dollar_tw
    feat = feat.merge(depth[["permno", "depth_dollar", "depth_imb", "total_vol_m"]], on="permno", how="left", validate="one_to_one")
    feat["date"] = date
    return feat


def acquisition_report(request):
    """Measured cost and coverage, never inferred model performance."""
    records = [obj for p in (DEST / "daily").glob("*.json") if (obj := json.loads(p.read_text())).get("version") == VERSION]
    if not records:
        return
    measured = pd.DataFrame(records)
    days = request.date.nunique()
    seconds = measured.seconds.median()
    target_counts = request.groupby("date").size()
    per_stock_second = measured.seconds.sum() / measured.requested.sum()
    # Cost scaling is illustrative: fixed daily overhead makes it nonlinear.
    full_links = sum(pd.read_parquet(ROOT / f"_data/wrds/crsp_taq_links/{y}.parquet", columns=["permno"]).permno.notna().sum()
                     for y in range(2004, 2020))
    lines = ["# Supplemental TAQ acquisition", "",
             f"Requested: {len(request):,} stock-days, {days:,} dates, {request.permno.nunique():,} stocks.",
             f"Saved: {len(measured):,} daily files, {measured.rows.sum():,} rows.", "",
             (f"Median observed query time: {seconds:.2f} seconds/day; measured days contain "
              f"{measured.requested.min():,}–{measured.requested.max():,} stocks."),
             f"Requested daily universe: median {target_counts.median():.0f}, maximum {target_counts.max():,} stocks.",
             f"Fixed daily-time extrapolation: {seconds*days/3600:.1f} connection-hours, before concurrency and tuning.",
             f"Stock-day-proportional extrapolation for this request: {per_stock_second*len(request)/3600:.1f} connection-hours.",
             (f"Full available TAQ-link universe ({full_links:,} rows): approximately "
              f"{per_stock_second*full_links/3600:.1f} connection-hours under the same proportional assumption."), "",
             "These are rough bounds/scenarios, not validated runtime forecasts. Query plans, liquidity, network latency and WRDS load vary.",
             "The full universe has not been requested. Acquisition covers training histories and ten scoring stocks only.",
             "Missing endpoints remain missing; no reduced-feature model has been substituted."]
    (OUT / "acquisition_report.md").write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--max-days", type=int, help="Bound a run; completed days resume automatically")
    ap.add_argument("--workers", type=int, default=1, choices=range(1, 5), help="Concurrent WRDS connections (1–4)")
    args = ap.parse_args()
    if args.max_days is not None and args.max_days <= 0:
        ap.error("--max-days must be positive")
    request = requested_days(args.pilot)
    DEST.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    request.to_parquet(DEST / ("pilot_request.parquet" if args.pilot else "request.parquet"), index=False)
    timings, connections = [], []
    local = threading.local()
    lock = threading.Lock()

    def one_day(item):
        date, u = item
        folder = DEST / ("pilot" if args.pilot else "daily")
        folder.mkdir(exist_ok=True)
        path = folder / f"{date:%Y%m%d}.parquet"
        fingerprint = hashlib.sha256((str(VERSION) + u.to_csv(index=False)).encode()).hexdigest()
        meta = path.with_suffix(".json")
        if path.exists() and meta.exists() and json.loads(meta.read_text())["request_sha256"] == fingerprint:
            return None
        if not hasattr(local, "conn") or local.conn.closed:
            local.conn = connect()
            with lock:
                connections.append(local.conn)
        start = time.monotonic()
        feat = collect_day(local.conn, date, u)
        elapsed = time.monotonic() - start
        temporary = path.with_suffix(".parquet.part")
        feat.to_parquet(temporary, index=False)
        temporary.replace(path)
        record = {"date": str(date.date()), "requested": len(u), "rows": len(feat),
                  "seconds": elapsed, "bytes": path.stat().st_size,
                  "request_sha256": fingerprint, "version": VERSION}
        meta.write_text(json.dumps(record, indent=2))
        print(json.dumps(record), flush=True)
        return record

    try:
        days = list(request.groupby("date"))
        if args.max_days is not None:
            days = days[:args.max_days]
        remaining = iter(days)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {pool.submit(one_day, item) for item in [next(remaining, None) for _ in range(args.workers)] if item is not None}
            while pending:
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    record = future.result()  # Failure stops new work; at most four queries remain.
                    if record:
                        timings.append(record)
                    item = next(remaining, None)
                    if item is not None:
                        pending.add(pool.submit(one_day, item))
    finally:
        for conn in connections:
            conn.close()
        if timings:
            pd.DataFrame(timings).to_csv(OUT / ("acquisition_pilot.csv" if args.pilot else "acquisition_run.csv"), index=False)
        if not args.pilot:
            acquisition_report(request)


if __name__ == "__main__":
    main()
