"""Build the daily and weekly stock panels used by the ITI replication exhibits.

Inputs (all local): CRSP daily, names and delistings, CRSP-TAQ links and WRDS
Intraday Indicators from _data/wrds; posted ITI (original vintage) and FF4
factors from _data/public.

Outputs in _data/derived/panel/:
  daily.parquet   one row per common stock (share code 10/11) and trading day,
                  2004-2019: delisting-adjusted return, price, market cap,
                  turnover, the paper's eligibility screen (price > $5 and
                  market cap > $100M at the end of the previous month), the
                  five posted ITI measures and daily TAQ liquidity controls.
  weekly.parquet  one row per eligible stock and calendar week (Mon-Fri):
                  week-average ITI, next-month return skipping a day, and the
                  Table 10 controls.

Run: python src/build_panel.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_values import ITI_NAMES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WRDS = ROOT / "_data" / "wrds"
PUBLIC = ROOT / "_data" / "public"
OUT = ROOT / "_data" / "derived" / "panel"
YEARS = range(2004, 2020)
MIN_PRICE, MIN_MCAP = 5.0, 100e6
SKIP, HORIZON = 1, 21  # skip one trading day, then a 21-trading-day month


def winsorize(s, lo=0.0005, hi=0.9995):
    a, b = s.quantile([lo, hi])
    return s.clip(a, b)


def common_stock_days(year, names):
    d = pd.read_parquet(WRDS / "crsp_daily" / f"{year}.parquet",
                        columns=["permno", "date", "prc", "ret", "vol", "shrout"])
    d["permno"] = d.permno.astype("int64")
    m = d.merge(names, on="permno")
    m = m[(m.date >= m.namedt) & (m.date <= m.nameendt)]
    return m.drop(columns=["namedt", "nameendt"]).drop_duplicates(["permno", "date"])


def add_delisting_returns(d):
    """Shumway (1997): compound the delisting return into the last trading day;
    a missing delisting return for a performance delisting (500-series) is -30%."""
    dl = pd.read_parquet(WRDS / "crsp_delistings.parquet", columns=["permno", "dlstdt", "dlret", "dlstcd"])
    dl["permno"] = dl.permno.astype("int64")
    dl["dlstcd"] = pd.to_numeric(dl.dlstcd)
    dl["dlret"] = pd.to_numeric(dl.dlret)
    perf = dl.dlstcd.between(500, 599)
    dl.loc[dl.dlret.isna() & perf, "dlret"] = -0.30
    dl = dl.dropna(subset=["dlret"])
    last = d.groupby("permno").date.max().rename("last_date").reset_index()
    dl = dl.merge(last, on="permno")
    dl = dl[dl.dlstdt >= dl.last_date][["permno", "last_date", "dlret"]]
    d = d.merge(dl, left_on=["permno", "date"], right_on=["permno", "last_date"], how="left")
    adj = d.dlret.notna()
    d.loc[adj, "ret"] = (1 + d.loc[adj, "ret"].fillna(0)) * (1 + d.loc[adj, "dlret"]) - 1
    return d.drop(columns=["last_date", "dlret"])


def taq_controls(year):
    """Daily liquidity controls from WRDS Intraday Indicators, linked to PERMNO."""
    cols = ["date", "sym_root", "sym_suffix", "buyvol_lr", "sellvol_lr",
            "effectivespread_percent_dw", "percentpriceimpact_lr_dw",
            "bestofrdepth_share_tw", "bestbiddepth_share_tw", "ivol_t"]
    iid = pd.read_parquet(WRDS / "intraday_indicators" / f"{year}.parquet", columns=cols)
    link = pd.read_parquet(WRDS / "crsp_taq_links" / f"{year}.parquet")
    link = link[["date", "sym_root", "sym_suffix", "permno"]].dropna(subset=["permno"])
    for frame in (iid, link):
        frame["date"] = pd.to_datetime(frame.date)
        frame["sym_suffix"] = frame.sym_suffix.fillna("").astype(str)
        frame["sym_root"] = frame.sym_root.astype(str)
    x = iid.merge(link, on=["date", "sym_root", "sym_suffix"])
    x["permno"] = x.permno.astype("int64")
    tot = x.buyvol_lr + x.sellvol_lr
    out = pd.DataFrame({
        "permno": x.permno, "date": x.date,
        "es": x.effectivespread_percent_dw, "pi": x.percentpriceimpact_lr_dw,
        "depth": (x.bestofrdepth_share_tw + x.bestbiddepth_share_tw) / 2,
        "rvol": x.ivol_t,
        "oi": np.where(tot > 0, (x.buyvol_lr - x.sellvol_lr) / tot, np.nan),
    })
    out["absoi"] = out.oi.abs()
    return out.drop_duplicates(["permno", "date"], keep=False)


def load_iti():
    parts = [pd.read_parquet(PUBLIC / "iti_original_through_2019" / f"year={y}") for y in YEARS]
    iti = pd.concat(parts, ignore_index=True)
    iti["permno"] = iti.permno.astype("int64")
    iti["date"] = pd.to_datetime(iti.date)
    for c in ITI_NAMES:
        iti[c] = iti[c].astype("float32")
    return iti.drop_duplicates(["permno", "date"])


def forward_returns(d):
    """Return from t+1+SKIP to t+SKIP+HORIZON trading days (stock's own days), and
    the next-day return; truncated at delisting."""
    lr = np.log1p(d.ret.fillna(0).clip(lower=-0.99)).to_numpy()
    cs = np.cumsum(lr)
    g = d.permno.to_numpy()
    start = np.flatnonzero(np.r_[True, g[1:] != g[:-1]])
    end = np.r_[start[1:], len(g)] - 1
    last = np.repeat(end, np.diff(np.r_[start, len(g)]))
    i = np.arange(len(g))
    a, b = i + SKIP, np.minimum(i + SKIP + HORIZON, last)
    fwd = np.where(a < last, np.exp(cs[b] - cs[np.minimum(a, last)]) - 1, np.nan)
    nxt = np.where(i < last, d.ret.shift(-1).to_numpy(), np.nan)
    return fwd, nxt


def monthly_controls(d, ff):
    """Stock-month controls measured over the month and applied to the next month:
    CAPM beta (12-month daily), idiosyncratic volatility (FF4 residuals within
    the month), Amihud illiquidity and mean effective spread."""
    x = d[["permno", "date", "ret", "prc", "vol", "mcap", "es"]].merge(ff, on="date")
    x["ym"] = x.date.dt.to_period("M")
    x["ex"] = x.ret - x.rf
    x["dvol"] = x.prc * x.vol
    x["illiq"] = np.where(x.dvol > 0, x.ret.abs() / x.dvol * 1e6, np.nan)
    keys = ["permno", "ym"]
    fac = ["mkt_rf", "smb", "hml", "mom"]
    ok = x.ex.notna()
    x = x[ok]
    # Grouped OLS moments for FF4 residual volatility.
    X = np.column_stack([np.ones(len(x)), x[fac].to_numpy()])
    y = x.ex.to_numpy()
    k = X.shape[1]
    prods = {f"xx{i}{j}": X[:, i] * X[:, j] for i in range(k) for j in range(i, k)}
    prods.update({f"xy{i}": X[:, i] * y for i in range(k)})
    prods["yy"] = y * y
    mom = pd.DataFrame(prods, index=x.index)
    mom[keys] = x[keys]
    s = mom.groupby(keys).sum()
    n = x.groupby(keys).size()
    XX = np.zeros((len(s), k, k))
    for i in range(k):
        for j in range(i, k):
            XX[:, i, j] = XX[:, j, i] = s[f"xx{i}{j}"]
    XY = np.column_stack([s[f"xy{i}"] for i in range(k)])
    good = (n.to_numpy() >= 15) & (np.linalg.det(XX) > 1e-18)
    beta = np.full((len(s), k), np.nan)
    beta[good] = np.linalg.solve(XX[good], XY[good][..., None])[..., 0]
    sse = s.yy.to_numpy() - np.einsum("gi,gi->g", beta, XY)
    ivol = np.sqrt(np.maximum(sse, 0) / np.maximum(n.to_numpy() - k, 1))
    m = pd.DataFrame({"ivol": ivol}, index=s.index)
    # CAPM beta from 12 months of daily data via rolling sums.
    c = x.assign(xy=x.mkt_rf * x.ex, xx=x.mkt_rf ** 2).groupby(keys).agg(
        sx=("mkt_rf", "sum"), sy=("ex", "sum"), sxy=("xy", "sum"), sxx=("xx", "sum"),
        n=("ex", "size"))
    r = c.groupby(level=0).rolling(12, min_periods=6).sum().droplevel(0)
    cov = r.sxy - r.sx * r.sy / r.n
    var = r.sxx - r.sx ** 2 / r.n
    m["beta"] = cov / var
    g = x.groupby(keys)
    m["illiq"] = g.illiq.mean()
    m["es_m"] = g.es.mean()
    m = m.reset_index()
    m["ym"] = m.ym + 1  # measured in month t, used for weeks in month t+1
    return m


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = pd.read_parquet(WRDS / "crsp_names.parquet", columns=["permno", "namedt", "nameendt", "shrcd"])
    names["permno"] = names.permno.astype("int64")
    names = names[pd.to_numeric(names.shrcd).isin([10, 11])].drop(columns="shrcd")
    for c in ("namedt", "nameendt"):
        names[c] = pd.to_datetime(names[c])
    d = pd.concat([common_stock_days(y, names) for y in YEARS], ignore_index=True)
    d = d.sort_values(["permno", "date"]).reset_index(drop=True)
    for c in ("prc", "ret", "vol", "shrout"):
        d[c] = pd.to_numeric(d[c]).astype("float64")
    d["prc"] = d.prc.abs()
    d = add_delisting_returns(d).sort_values(["permno", "date"]).reset_index(drop=True)
    d["mcap"] = d.prc * d.shrout * 1000
    d["turn"] = d.vol / (d.shrout * 1000)
    # Screen: price and market cap at the end of the previous month.
    d["ym"] = d.date.dt.to_period("M")
    me = d.groupby(["permno", "ym"])[["prc", "mcap"]].last().reset_index()
    me["ym"] = me.ym + 1
    d = d.merge(me.rename(columns={"prc": "prc_lag", "mcap": "mcap_lag"}), on=["permno", "ym"], how="left")
    d["eligible"] = (d.prc_lag > MIN_PRICE) & (d.mcap_lag > MIN_MCAP)
    d["fwd_ret"], d["ret_next"] = forward_returns(d)
    print("CRSP common stock days:", len(d), flush=True)

    taq = pd.concat([taq_controls(y) for y in YEARS], ignore_index=True)
    d = d.merge(taq, on=["permno", "date"], how="left")
    print("TAQ controls matched:", f"{d.es.notna().mean():.1%}", flush=True)
    d = d.merge(load_iti(), on=["permno", "date"], how="left")
    print("ITI(13D) matched:", f"{d['ITI(13D)'].notna().mean():.1%}", flush=True)
    d = d.drop(columns=["prc_lag", "mcap_lag"])
    d.to_parquet(OUT / "daily.parquet", index=False)

    ff = pd.read_parquet(PUBLIC / "ff4_daily_2004_2019.parquet")
    ff["date"] = pd.to_datetime(ff.date)
    mc = monthly_controls(d, ff)

    e = d[d.eligible & d[ITI_NAMES].notna().any(axis=1)].copy()
    e["week"] = e.date.dt.to_period("W-FRI")
    g = e.groupby(["permno", "week"])
    w = g[ITI_NAMES].mean()
    w["fwd_ret"] = g.fwd_ret.last()
    w["date"] = g.date.last()
    w = w.reset_index()
    # Last month return and 2-6 month return at the week's last day, from daily data.
    lr = np.log1p(d.ret.fillna(0).clip(lower=-0.99))
    cs = lr.groupby(d.permno).cumsum()
    d["r_1m"] = np.expm1(cs - cs.groupby(d.permno).shift(21))
    d["r_2_6m"] = np.expm1(cs.groupby(d.permno).shift(21) - cs.groupby(d.permno).shift(126))
    w = w.merge(d[["permno", "date", "r_1m", "r_2_6m", "mcap"]], on=["permno", "date"], how="left")
    w["size"] = np.log(w.mcap)
    w["ym"] = w.date.dt.to_period("M")
    w = w.merge(mc[["permno", "ym", "beta", "ivol", "illiq", "es_m"]], on=["permno", "ym"], how="left")
    for c in ["size", "beta", "r_1m", "r_2_6m", "ivol", "illiq", "es_m", *ITI_NAMES]:
        w[c] = winsorize(w[c])
    w["week_id"] = w.week.astype(str)
    w = w.drop(columns=["ym", "mcap"])
    w["week"] = w.week.dt.end_time.dt.normalize()
    w.to_parquet(OUT / "weekly.parquet", index=False)
    print("Weekly rows:", len(w), "with forward return:", w.fwd_ret.notna().sum(), flush=True)


if __name__ == "__main__":
    main()
