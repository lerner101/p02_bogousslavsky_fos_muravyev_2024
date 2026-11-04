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


def extract(conn, name, query, params=None):
    """Atomically save an extract and provenance, skipping completed files."""
    path = DEST / (name + ".parquet")
    meta = path.with_suffix(".json")
    if path.exists() and meta.exists():
        print("Already saved:", name, flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    try:
        conn.autocommit = False
        temporary = path.with_suffix(".parquet.part")
        row_count = 0
        date_ranges = {}
        with conn.cursor(name="iti_extract") as cur:
            cur.execute(query, params)
            rows = cur.fetchmany(50000)
            columns = [d[0] for d in cur.description]
            types = [d.type_code for d in cur.description]
            while rows:
                df = pd.DataFrame(rows, columns=columns)
                for col, code in zip(columns, types):
                    if code in (20, 21, 23):
                        df[col] = pd.to_numeric(df[col]).astype("Int64")
                    elif code in (700, 701, 1700):
                        df[col] = pd.to_numeric(df[col]).astype(float)
                    elif code in (25, 1042, 1043):
                        df[col] = df[col].astype("string")
                    elif code in (1082, 1114, 1184):
                        df[col] = pd.to_datetime(df[col])
                    if col in ("date", "datadate", "trandate", "dateann", "rdq") and df[col].notna().any():
                        lo, hi = str(df[col].min()), str(df[col].max())
                        previous = date_ranges.get(col, [lo, hi])
                        date_ranges[col] = [min(lo, previous[0]), max(hi, previous[1])]
                table = pa.Table.from_pandas(df, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
                writer.write_table(table)
                row_count += len(df)
                rows = cur.fetchmany(50000)
        if writer is not None:
            writer.close()
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
    except psycopg2.Error as exc:
        if writer is not None:
            writer.close()
        conn.rollback()
        conn.autocommit = True
        error = {"sqlstate": exc.pgcode, "reason": exc.diag.message_primary}
        path.with_suffix(".error.json").write_text(json.dumps(error, indent=2))
        print("Unavailable:", name, error, flush=True)


def columns(conn, schema, table):
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT * FROM {}.{} LIMIT 0").format(
            sql.Identifier(schema), sql.Identifier(table)))
        return [d[0] for d in cur.description]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="+", choices=["core", "indicators", "lending", "links", "sec"])
    parser.add_argument("--start-year", type=int, default=2004)
    parser.add_argument("--end-year", type=int, default=2019)
    args = parser.parse_args()
    conn = connect()
    start, end = f"{args.start_year}-01-01", f"{args.end_year + 1}-01-01"
    if "core" in args.groups:
        extract(conn, "crsp_names", "SELECT * FROM crsp.dsenames WHERE namedt < %s AND nameendt >= %s", (end, start))
        extract(conn, "crsp_delistings", "SELECT * FROM crsp.dsedelist WHERE dlstdt >= %s AND dlstdt < %s", (start, end))
        extract(conn, "crsp_market", "SELECT * FROM crsp.dsi WHERE date >= %s AND date < %s", (start, end))
        extract(conn, "crsp_compustat_links", "SELECT * FROM crsp.ccmxpf_linktable")
        extract(conn, "compustat_earnings", """SELECT gvkey,datadate,fyearq,fqtr,rdq,epspxq,epsfxq,cshoq,prccq,cusip
            FROM comp.fundq WHERE rdq >= %s AND rdq < %s
            AND indfmt='INDL' AND datafmt='STD' AND popsrc='D' AND consol='C'""", (start, end))
        extract(conn, "sdc_ma", """SELECT master_deal_no,dateann,dateeff,acusip,master_cusip,
            anation,tnation,apublic,tpublic,tticker,status,form,deal_value,tmanames,amanames
            FROM tr_sdc_ma.wrds_ma_details WHERE dateann >= %s AND dateann < %s""", (start, end))
        for year in range(args.start_year, args.end_year + 1):
            bounds = (f"{year}-01-01", f"{year+1}-01-01")
            extract(conn, f"crsp_daily/{year}", """SELECT permno,date,prc,ret,retx,vol,shrout,bid,ask,cfacpr,cfacshr
                FROM crsp.dsf WHERE date >= %s AND date < %s""", bounds)
            extract(conn, f"insider_transactions/{year}", """SELECT fdate,personid,dcn,seqnum,formtype,
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
            available = columns(conn, f"taqm_{year}", f"wrds_iid_{year}")
            selected = [col for col in wanted if col in available]
            extract(conn, f"intraday_indicators/{year}", f"SELECT {','.join(selected)} FROM {table}")
    if "lending" in args.groups:
        for year in range(max(2006, args.start_year), args.end_year + 1):
            table = f"markit_msf_analytics_eqty_amer.amereqty{year}"
            extract(conn, f"markit_lending/{year}", f"""SELECT datadate,dxlid,isin,cusip,sedol,
                quantityonloan,lendablequantity,utilisation FROM {table}
                WHERE cusip IS NOT NULL""")
    if "links" in args.groups:
        for year in range(args.start_year, args.end_year + 1):
            extract(conn, f"crsp_taq_links/{year}", """SELECT *
                FROM wrdsapps_link_crsp_taqm.taqmclink WHERE date >= %s AND date < %s""",
                (f"{year}-01-01", f"{year+1}-01-01"))
    if "sec" in args.groups:
        extract(conn, "sec_cusip_links", "SELECT * FROM wrdssec_common.wciklink_cusip")
        for year in range(args.start_year, args.end_year + 1):
            bounds = (f"{year}-01-01", f"{year+1}-01-01")
            extract(conn, f"sec_13d_index/{year}", """SELECT fdate,accession,form,cik,coname,fname,wrdsfname
                FROM wrdssec.wrds_forms WHERE fdate >= %s AND fdate < %s
                AND form IN ('SC 13D','SC 13D/A')""", bounds)
            extract(conn, f"sec_13d_filings/{year}", """SELECT accession,form,filing_date,report_date,filing
                FROM wrds_sec_search.filing_sc_13d WHERE filing_date >= %s AND filing_date < %s
                AND form = 'SC 13D'""", bounds)
    conn.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Completed files are saved; rerun to retry unfinished years.", flush=True)
        sys.exit(130)
