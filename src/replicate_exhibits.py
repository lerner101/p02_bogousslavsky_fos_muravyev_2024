"""Replicate the ITI exhibits that the posted ITI file and our local data allow.

Table 10 (cols 1-5): weekly ITI predicting next-month returns.
Table 11: decile portfolios on prior-week ITI, raw and FF4 alphas.
Table 5: daily return reversal and ITI(13D).
Figure 4(a)-(b): ITI(13D) around earnings announcements.
Figure IA.5: ITI(13D) around M&A announcements (targets).

Reads _data/derived/panel/{daily,weekly}.parquet (src/build_panel.py).
Writes CSVs and PNGs to _output/replication/.

Run: python src/replicate_exhibits.py [table10 table11 table5 fig4 figia5]
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_values as pv  # noqa: E402
from build_panel import winsorize  # noqa: E402
from paper_values import ITI_NAMES  # noqa: E402
from regress import fe_ols, fe_ols_chunked, newey_west_mean  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "_data" / "derived" / "panel"
WRDS = ROOT / "_data" / "wrds"
OUT = ROOT / "_output" / "replication"
SAMPLE_START, SAMPLE_END = "2005-01-01", "2019-07-31"  # posted ITI ends 7/2019 in the paper
DAYS = pv.DAYS


def load_daily(columns):
    d = pd.read_parquet(PANEL / "daily.parquet", columns=list(dict.fromkeys(["permno", "date", *columns])))
    return d[(d.date >= SAMPLE_START) & (d.date <= SAMPLE_END)]


def stack(results):
    rows = []
    for col, (tab, stats) in results.items():
        for var, r in tab.iterrows():
            rows.append({"column": col, "variable": var, "coef": r.coef, "t": r.t})
        rows.append({"column": col, "variable": "Obs.", "coef": stats["nobs"], "t": np.nan})
        rows.append({"column": col, "variable": "R2 (within)", "coef": stats["r2_within"], "t": np.nan})
    return pd.DataFrame(rows)


def table10():
    w = pd.read_parquet(PANEL / "weekly.parquet")
    w = w[(w.date >= SAMPLE_START) & (w.date <= SAMPLE_END)]
    controls = ["size", "beta", "r_1m", "r_2_6m", "ivol", "illiq", "es_m"]
    specs = {
        1: ["ITI(13D)"],
        2: ["ITI(13D)", "ITI(insider)", "ITI(short)"],
        3: ["ITI(patient)", "ITI(impatient)"],
        4: ITI_NAMES,
        5: ITI_NAMES + controls,
    }
    base = w.dropna(subset=["fwd_ret", *ITI_NAMES, *controls])
    res = {c: fe_ols(base, "fwd_ret", x, fe="week_id", cluster=("permno", "week_id"))
           for c, x in specs.items()}
    out = stack(res)
    out.to_csv(OUT / "table10.csv", index=False)
    return out


def table11():
    w = pd.read_parquet(PANEL / "weekly.parquet", columns=["permno", "week", "date", "fwd_ret", *ITI_NAMES])
    w = w[(w.date >= SAMPLE_START) & (w.date <= SAMPLE_END)].dropna(subset=["fwd_ret"])
    ff = pd.read_parquet(ROOT / "_data" / "public" / "ff4_daily_2004_2019.parquet")
    ff["date"] = pd.to_datetime(ff.date)
    # Factor returns over the same skip-a-day, 21-trading-day window on the market calendar.
    cal = ff.set_index("date")
    fac = ["mkt_rf", "smb", "hml", "mom", "rf"]
    fwd = {}
    lc = np.log1p(cal[fac]).cumsum()
    for k in fac:
        a = lc[k].shift(-1)
        b = lc[k].shift(-(1 + 21))
        fwd[k] = np.expm1(b - a)
    fwd = pd.DataFrame(fwd)
    week_end = w.groupby("week").date.max()
    rows, alphas = [], []
    for name in ITI_NAMES:
        x = w.dropna(subset=[name]).copy()
        x["decile"] = x.groupby("week")[name].transform(
            lambda v: pd.qcut(v.rank(method="first"), 10, labels=False) + 1)
        p = x.groupby(["week", "decile"]).fwd_ret.mean().unstack()
        p["H-L"] = p[10] - p[1]
        f = fwd.reindex(week_end.reindex(p.index).to_numpy())
        f.index = p.index
        for col in p.columns:
            mean, t = newey_west_mean(p[col], 8)
            excess = p[col] - (0 if col == "H-L" else f.rf)
            a, ta = newey_west_mean(excess, 8, f[["mkt_rf", "smb", "hml", "mom"]])
            rows.append({"measure": name, "portfolio": col, "raw": mean, "raw_t": t,
                         "alpha": a, "alpha_t": ta})
        alphas.append(len(p))
    out = pd.DataFrame(rows)
    out["portfolio"] = out.portfolio.astype(str).replace({"1": "Low", "10": "High"})
    out.to_csv(OUT / "table11.csv", index=False)
    return out


def table5():
    cols = ["ret", "ret_next", "eligible", "ITI(13D)", "turn", "rvol", "es", "pi", "depth", "oi", "absoi"]
    d = load_daily(cols)
    d = d[d.eligible].dropna(subset=["ret", "ret_next", "ITI(13D)"]).drop(columns="eligible")
    d["date_id"] = d.date.dt.strftime("%Y%m%d").astype(int)
    for c in ["turn", "rvol", "es", "pi", "depth", "oi", "absoi"]:
        d[c] = winsorize(d[c])
    d["ret*ITI(13D)"] = d.ret * d["ITI(13D)"]
    d["ret*turn"] = d.ret * d.turn
    d["ret*rvol"] = d.ret * d.rvol
    d["ret*ES%"] = d.ret * d.es
    controls = ["es", "pi", "depth", "rvol", "turn", "oi", "absoi"]
    full = d.dropna(subset=controls)
    specs = {
        1: (d, ["ret"]),
        2: (d, ["ret", "ITI(13D)", "ret*ITI(13D)"]),
        "2 (col 3 sample)": (full, ["ret", "ITI(13D)", "ret*ITI(13D)"]),
        3: (full, ["ret", "ITI(13D)", "ret*ITI(13D)", "ret*turn", "ret*rvol", "ret*ES%", *controls]),
    }
    res = {c: fe_ols(df, "ret_next", x, fe="date_id", cluster=("permno", "date_id"))
           for c, (df, x) in specs.items()}
    out = stack(res)
    out.to_csv(OUT / "table5.csv", index=False)
    return out


def event_offsets(d, events):
    """Mark trading-day offsets -10..10 around each (permno, day-0 date) event.
    Returns an array (rows of d) x 21 of 0/1 indicators."""
    idx = d.groupby("permno").cumcount().to_numpy()
    key = pd.Series(np.arange(len(d)), index=pd.MultiIndex.from_arrays([d.permno, d.date]))
    pos0 = key.reindex(pd.MultiIndex.from_arrays([events.permno, events.day0])).to_numpy()
    pos0 = pos0[~np.isnan(pos0)].astype(int)
    dummies = np.zeros((len(d), len(DAYS)), dtype=np.int8)
    perm = d.permno.to_numpy()
    for j, k in enumerate(DAYS):
        p = pos0 + k
        ok = (p >= 0) & (p < len(d))
        p, src = p[ok], pos0[ok]
        same = perm[p] == perm[src]
        dummies[p[same], j] = 1
    return dummies, idx


def day0_after(d, dates):
    """First trading day of the stock on or after each (permno, date)."""
    ev = dates.sort_values("date")
    tr = d[["permno", "date", "vol", "ret"]].sort_values("date")
    m = pd.merge_asof(ev, tr.rename(columns={"date": "day0"}), left_on="date", right_on="day0",
                      by="permno", direction="forward", tolerance=pd.Timedelta(days=7))
    return m.dropna(subset=["day0"])


def earnings_events(d):
    e = pd.read_parquet(WRDS / "compustat_earnings.parquet", columns=["gvkey", "rdq"])
    lk = pd.read_parquet(WRDS / "crsp_compustat_links.parquet",
                         columns=["gvkey", "lpermno", "linktype", "linkprim", "linkdt", "linkenddt"])
    lk = lk[lk.linktype.isin(["LC", "LU"]) & lk.linkprim.isin(["P", "C"])].dropna(subset=["lpermno"])
    lk["linkenddt"] = pd.to_datetime(lk.linkenddt).fillna(pd.Timestamp("2099-12-31"))
    lk["linkdt"] = pd.to_datetime(lk.linkdt)
    e = e.dropna(subset=["rdq"]).merge(lk, on="gvkey")
    e["rdq"] = pd.to_datetime(e.rdq)
    e = e[(e.rdq >= e.linkdt) & (e.rdq <= e.linkenddt)]
    e = e.assign(permno=e.lpermno.astype("int64"), date=e.rdq)[["permno", "date"]].drop_duplicates()
    m = day0_after(d, e)
    # Announcement day = the higher-volume of the reported day and the next trading day
    # (after-close announcements trade on the next day).
    nxt = d[["permno", "date", "vol", "ret"]].copy()
    nxt["prev"] = nxt.groupby("permno").date.shift(1)
    m = m.merge(nxt.rename(columns={"date": "day1", "vol": "vol1", "ret": "ret1", "prev": "day0"}),
                on=["permno", "day0"], how="left")
    use_next = m.vol1 > m.vol
    m.loc[use_next, "day0"] = m.loc[use_next, "day1"]
    m["ret0"] = np.where(use_next, m.ret1, m.ret)
    return m[["permno", "day0", "ret0"]].drop_duplicates(["permno", "day0"])


def event_regression(d, events, groups=None):
    """ITI(13D) on day dummies with stock FE, clustered by stock and date."""
    d = d.sort_values(["permno", "date"]).reset_index(drop=True)
    sets = {"all": events} if groups is None else {g: events[events.group == g] for g in groups}
    names = []
    for g, ev in sets.items():
        dm, _ = event_offsets(d, ev)
        for j, k in enumerate(DAYS):
            n = f"{g}:{k}"
            d[n] = dm[:, j]
            names.append(n)
    d["date_id"] = d.date.dt.strftime("%Y%m%d").astype(int)
    keep = d.eligible & d["ITI(13D)"].notna()
    tab, stats = fe_ols_chunked(d[keep], "ITI(13D)", names, fe="permno", cluster2="date_id")
    tab = tab.reset_index(names="term")
    tab[["group", "day"]] = tab.term.str.split(":", expand=True)
    tab["day"] = tab.day.astype(int)
    tab["nobs"] = stats["nobs"]
    return tab


def plot_event(tab, paper, title, path, labels=None):
    fig, ax = plt.subplots(figsize=(7, 3.2))
    groups = tab.group.unique()
    colors = ["#1f5fbf", "#c0392b", "#7f8c8d"]
    for i, g in enumerate(groups):
        t = tab[tab.group == g]
        ax.errorbar(t.day, t.coef, yerr=1.96 * t.se, marker="o", ms=3, capsize=2,
                    color=colors[i], label=f"Ours: {labels.get(g, g) if labels else g}")
    for i, (lab, vals) in enumerate(paper.items()):
        ax.plot(DAYS, vals, ls="--", color=colors[i], alpha=0.6, label=f"Paper: {lab}")
    ax.axhline(0, color="black", lw=0.6, ls=":")
    ax.set_xticks(DAYS)
    ax.set_xlabel("Trading day relative to announcement")
    ax.set_ylabel("Δ ITI(13D)")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig4():
    d = load_daily(["eligible", "vol", "ret", "ITI(13D)"]).sort_values(["permno", "date"])
    ev = earnings_events(d)
    ev = ev[(ev.day0 >= SAMPLE_START) & (ev.day0 <= SAMPLE_END)]
    a = event_regression(d, ev)
    a.to_csv(OUT / "figure4a.csv", index=False)
    plot_event(a, {"all": pv.FIG4A}, "Figure 4(a): ITI(13D) around earnings announcements",
               OUT / "figure4a.png", {"all": "all announcements"})
    q = ev.ret0.abs()
    lo, hi = q.quantile([0.25, 0.75])
    ev = ev.assign(group=np.select([q >= hi, q <= lo], ["large", "small"], "middle"))
    b = event_regression(d, ev, groups=["large", "small", "middle"])
    b.to_csv(OUT / "figure4b.csv", index=False)
    plot_event(b[b.group != "middle"], {"large |r|": pv.FIG4B_LARGE, "small |r|": pv.FIG4B_SMALL},
               "Figure 4(b): top vs bottom quartile |announcement return|", OUT / "figure4b.png",
               {"large": "large |r|", "small": "small |r|"})
    return a, b, len(ev)


def ma_events(d):
    """Completed acquisitions of US public targets, linked to CRSP by 6-digit CUSIP."""
    s = pd.read_parquet(WRDS / "sdc_ma.parquet")
    s = s[(s.tpublic == "Public") & (s.tnation == "United States") & (s.status == "Completed")
          & s.form.isin(["Merger", "Acquisition", "Acq. Maj. Int.", "Acq. Rem. Int."])]
    s = s.dropna(subset=["master_cusip", "dateann"])
    s["cusip6"] = s.master_cusip.str[:6]
    names = pd.read_parquet(WRDS / "crsp_names.parquet", columns=["permno", "ncusip", "namedt", "nameendt"])
    names = names.dropna(subset=["ncusip"]).assign(cusip6=lambda x: x.ncusip.str[:6])
    m = s.merge(names, on="cusip6")
    m["dateann"] = pd.to_datetime(m.dateann)
    m = m[(m.dateann >= pd.to_datetime(m.namedt)) & (m.dateann <= pd.to_datetime(m.nameendt))]
    m = m.assign(permno=m.permno.astype("int64"), date=m.dateann)[["permno", "date"]].drop_duplicates()
    m = day0_after(d, m)
    return m[["permno", "day0"]].drop_duplicates()


def figia5():
    d = load_daily(["eligible", "vol", "ret", "ITI(13D)"]).sort_values(["permno", "date"])
    ev = ma_events(d)
    ev = ev[(ev.day0 >= SAMPLE_START) & (ev.day0 <= SAMPLE_END)]
    tab = event_regression(d, ev)
    tab["n_events"] = len(ev)
    tab.to_csv(OUT / "figureIA5.csv", index=False)
    plot_event(tab, {"M&A targets": pv.FIGIA5}, "Figure IA.5: ITI(13D) around M&A announcements",
               OUT / "figureIA5.png", {"all": "M&A targets"})
    return tab


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:] or ["table10", "table11", "table5", "fig4", "figia5"]
    for name in wanted:
        print("Running", name, flush=True)
        globals()[name]()
        print("Done", name, flush=True)


if __name__ == "__main__":
    main()
