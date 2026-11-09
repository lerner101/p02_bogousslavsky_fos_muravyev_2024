"""Resumable, read-only extracts for the 2005–2019 ITI project.

Run: python src/collect_wrds.py core indicators lending links sec
Reads existing ~/.pgpass via libpq; never writes credentials. Includes 2004
warm-up data. Source extracts are not yet linked or paper-filtered panels.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "_data" / "wrds"
BATCH_ROWS = 50000
FAILURES = []


class Database:
    """Holds the WRDS connection and reopens it after a dropped connection."""

    def __init__(self):
        self.conn = connect()

    def ensure_open(self):
        if self.conn.closed:
            print("Reconnecting to WRDS...", flush=True)
            self.conn = connect()


def connect():
    load_dotenv(ROOT / ".env", override=False)
    username = os.environ.get("WRDS_USERNAME")
    host = "wrds-pgdata.wharton.upenn.edu"
    port = "9737"
    if not username:
        pgpass = Path(os.environ.get("PGPASSFILE", str(Path.home() / ".pgpass")))
        for line in (pgpass.read_text().splitlines() if pgpass.exists() else []):
            if line and not line.startswith("#"):
                parts = line.split(":")
                if len(parts) == 5 and "wrds" in parts[0].lower():
                    host, port, _, username, _ = parts
                    break
    if not username:
        raise RuntimeError("Set WRDS_USERNAME and configure libpq credentials.")
    for attempt in range(3):
        try:
            conn = psycopg2.connect(host=host, port=port, dbname="wrds",
                                    user=username, sslmode="require", connect_timeout=10)
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = 600000")
            return conn
        except psycopg2.OperationalError:
            if attempt == 2:
                raise
            time.sleep(2)


def convert(df, columns, types):
    """Give each column a type fixed by its Postgres type, so batch schemas match."""
    for col, code in zip(columns, types):
        if code in (20, 21, 23):
            df[col] = pd.to_numeric(df[col]).astype("Int64")
        elif code in (700, 701, 1700):
            df[col] = pd.to_numeric(df[col]).astype(float)
        elif code == 16:
            df[col] = df[col].astype("boolean")
        elif code in (1082, 1114):
            df[col] = pd.to_datetime(df[col])
        elif code == 1184:
            df[col] = pd.to_datetime(df[col], utc=True)
        else:
            df[col] = df[col].astype("string")
    return df


def extract(db, name, query, params=None, batch_rows=BATCH_ROWS):
    """Atomically save an extract and provenance, skipping completed files.

    Any failure is recorded in a .error.json file and the run continues with
    the next extract; KeyboardInterrupt still stops the run.
    """
    path = DEST / (name + ".parquet")
    meta = path.with_suffix(".json")
    if path.exists() and meta.exists():
        print("Already saved:", name, flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".parquet.part")
    writer = None
    db.ensure_open()
    conn = db.conn
    try:
        conn.autocommit = False
        row_count = 0
        date_ranges = {}
        with conn.cursor(name="iti_extract") as cur:
            cur.execute(query, params)
            rows = cur.fetchmany(batch_rows)
            columns = [d[0] for d in cur.description]
            types = [d.type_code for d in cur.description]
            while rows:
                df = convert(pd.DataFrame(rows, columns=columns), columns, types)
                for col in columns:
                    if col in ("date", "datadate", "trandate", "dateann", "rdq") and df[col].notna().any():
                        lo, hi = str(df[col].min()), str(df[col].max())
                        previous = date_ranges.get(col, [lo, hi])
                        date_ranges[col] = [min(lo, previous[0]), max(hi, previous[1])]
                table = pa.Table.from_pandas(df, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
                elif not table.schema.equals(writer.schema):
                    table = table.cast(writer.schema)
                writer.write_table(table)
                row_count += len(df)
                rows = cur.fetchmany(batch_rows)
        if writer is not None:
            writer.close()
            writer = None
        else:
            pd.DataFrame(columns=columns).to_parquet(temporary, index=False)
        conn.commit()
        conn.autocommit = True
        temporary.replace(path)
        meta.write_text(json.dumps({"rows": row_count, "columns": columns,
            "date_ranges": date_ranges, "bytes": path.stat().st_size,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "query": query, "parameters": params}, indent=2, default=str))
        path.with_suffix(".error.json").unlink(missing_ok=True)
        print("Saved:", name, row_count, "rows", path.stat().st_size, "bytes", flush=True)
    except Exception as exc:
        record_failure(db, name, exc, path)
    finally:
        if writer is not None:
            writer.close()
        temporary.unlink(missing_ok=True)


def record_failure(db, name, exc, path):
    """Reset the connection and save the reason an extract failed."""
    if not db.conn.closed:
        try:
            db.conn.rollback()
            db.conn.autocommit = True
        except psycopg2.Error:
            db.conn.close()
    if isinstance(exc, psycopg2.Error):
        error = {"sqlstate": exc.pgcode,
                 "reason": exc.diag.message_primary or str(exc).strip()}
    else:
        error = {"sqlstate": None, "reason": f"{type(exc).__name__}: {exc}"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".error.json").write_text(json.dumps(error, indent=2))
    FAILURES.append(name)
    print("Failed:", name, error, flush=True)


def columns(db, schema, table):
    db.ensure_open()
    with db.conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT * FROM {}.{} LIMIT 0").format(
            sql.Identifier(schema), sql.Identifier(table)))
        return [d[0] for d in cur.description]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="+", choices=["core", "indicators", "lending", "links", "sec"])
    parser.add_argument("--start-year", type=int, default=2004)
    parser.add_argument("--end-year", type=int, default=2019)
    args = parser.parse_args()
    db = Database()
    start, end = f"{args.start_year}-01-01", f"{args.end_year + 1}-01-01"
    if "core" in args.groups:
        extract(db, "crsp_names", "SELECT * FROM crsp.dsenames WHERE namedt < %s AND nameendt >= %s", (end, start))
        extract(db, "crsp_delistings", "SELECT * FROM crsp.dsedelist WHERE dlstdt >= %s AND dlstdt < %s", (start, end))
        extract(db, "crsp_market", "SELECT * FROM crsp.dsi WHERE date >= %s AND date < %s", (start, end))
        extract(db, "crsp_compustat_links", "SELECT * FROM crsp.ccmxpf_linktable")
        extract(db, "compustat_earnings", """SELECT gvkey,datadate,fyearq,fqtr,rdq,epspxq,epsfxq,cshoq,prccq,cusip
            FROM comp.fundq WHERE rdq >= %s AND rdq < %s
            AND indfmt='INDL' AND datafmt='STD' AND popsrc='D' AND consol='C'""", (start, end))
        extract(db, "sdc_ma", """SELECT master_deal_no,dateann,dateeff,acusip,master_cusip,
            anation,tnation,apublic,tpublic,tticker,status,form,deal_value,tmanames,amanames
            FROM tr_sdc_ma.wrds_ma_details WHERE dateann >= %s AND dateann < %s""", (start, end))
        for year in range(args.start_year, args.end_year + 1):
            bounds = (f"{year}-01-01", f"{year+1}-01-01")
            extract(db, f"crsp_daily/{year}", """SELECT permno,date,prc,ret,retx,vol,shrout,bid,ask,cfacpr,cfacshr
                FROM crsp.dsf WHERE date >= %s AND date < %s""", bounds)
            extract(db, f"insider_transactions/{year}", """SELECT fdate,personid,dcn,seqnum,formtype,
                cusip6,cusip2,cusipx,trancode,acqdisp,trandate,tprice,shares,sharesheld,cleanse,sectitle
                FROM tr_insiders.table1 WHERE trandate >= %s AND trandate < %s""", bounds)
    if "indicators" in args.groups:
        for year in range(args.start_year, args.end_year + 1):
            table = f"taqm_{year}.wrds_iid_{year}"
            wanted = """date sym_root sym_suffix symbol buynumtrades_lr sellnumtrades_lr
                buyvol_lr sellvol_lr vwavg_buy_price_lr vwavg_sell_price_lr
                total_vol_b total_vol_m total_vol_a total_n_trades_b total_n_trades_m
                total_n_trades_a n_oddlot_trade quotedspread_percent_tw
                bestofrdepth_share_tw bestbiddepth_share_tw effectivespread_percent_dw
                percentrealizedspread_lr_dw percentpriceimpact_lr_dw ivol_t ivol_q
                tsignsqrtdvol1 tsignsqrtdvol2 n5_pos n30_pos hindex var_ratio1 var_ratio2
                oprc cprc mid_after_open mid_before_close""".split()
            name = f"intraday_indicators/{year}"
            try:
                available = columns(db, f"taqm_{year}", f"wrds_iid_{year}")
            except psycopg2.Error as exc:
                record_failure(db, name, exc, DEST / (name + ".parquet"))
                continue
            selected = [col for col in wanted if col in available]
            if not selected:
                record_failure(db, name, ValueError(f"no wanted columns in {table}"),
                               DEST / (name + ".parquet"))
                continue
            extract(db, name, f"SELECT {','.join(selected)} FROM {table}")
    if "lending" in args.groups:
        for year in range(max(2006, args.start_year), args.end_year + 1):
            table = f"markit_msf_analytics_eqty_amer.amereqty{year}"
            extract(db, f"markit_lending/{year}", f"""SELECT datadate,dxlid,isin,cusip,sedol,
                quantityonloan,lendablequantity,utilisation FROM {table}
                WHERE cusip IS NOT NULL""")
    if "links" in args.groups:
        for year in range(args.start_year, args.end_year + 1):
            extract(db, f"crsp_taq_links/{year}", """SELECT *
                FROM wrdsapps_link_crsp_taqm.taqmclink WHERE date >= %s AND date < %s""",
                (f"{year}-01-01", f"{year+1}-01-01"))
    if "sec" in args.groups:
        extract(db, "sec_cusip_links", "SELECT * FROM wrdssec_common.wciklink_cusip")
        for year in range(args.start_year, args.end_year + 1):
            bounds = (f"{year}-01-01", f"{year+1}-01-01")
            extract(db, f"sec_13d_index/{year}", """SELECT fdate,accession,form,cik,coname,fname,wrdsfname
                FROM wrdssec.wrds_forms WHERE fdate >= %s AND fdate < %s
                AND form IN ('SC 13D','SC 13D/A')""", bounds)
            extract(db, f"sec_13d_filings/{year}", """SELECT accession,form,filing_date,report_date,filing
                FROM wrds_sec_search.filing_sc_13d WHERE filing_date >= %s AND filing_date < %s
                AND form = 'SC 13D'""", bounds, batch_rows=500)
    db.conn.close()
    if FAILURES:
        print(f"{len(FAILURES)} extract(s) failed:", ", ".join(FAILURES), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Completed files are saved; rerun to retry unfinished years.", flush=True)
        sys.exit(130)
