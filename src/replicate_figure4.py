"""Replicate Figure 4: ITI around earnings announcements (a, b) and news events (c).

The specification follows the authors' ITI_main.py (Replication Code-20220087.zip,
sections "Figure 4" and "Figure 4: Panel (c)"):

* The event-time row sequence is each stock's sequence of posted-ITI stock-days
  (the authors' `informed` panel), after dropping "sparse" stocks whose median gap
  between observations exceeds one calendar day.
* Earnings day 0 is the higher-volume of Compustat rdq and the next trading day.
* Indicators for days -10..10 are shifts of the announcement flag within that
  row sequence; rows whose shifts fall outside a stock's history are dropped.
* The plotted no-controls regression still requires every control to be observed.
* Panel (b) runs one regression per quartile of |announcement-day return|. Rows
  within ten observations of an announcement from another quartile are dropped.
* Stock fixed effects; standard errors double-clustered by stock and date; plotted
  bands are +/- 2 SE, as exported by the authors.

Local deviations, recorded in the outputs: the sample is 2005-7/2019 (paper:
1/1993-7/2019) and panel (c) is 2005-2015 (paper: 2000-2015); Kyle's lambda is not
available for the general panel, so the control screen uses the other seven
controls; the with-controls sensitivity uses the panel's units for depth and OI.

Reads _data/derived/panel/daily.parquet (src/build_panel.py) and, for panel (c),
_data/derived/bfkr/news_daily.parquet (src/prepare_bfkr_news.py).
Parts (each owns its outputs, matching the doit tasks):
  ab        figure4{a,b}.csv; _data/derived/figure4/earnings_adjusted.parquet, figure4_counts_ab.json
  c         figure4c.csv; _data/derived/figure4/figure4c_sample.parquet, figure4_counts_c.json
  diagnose  figure4_diagnosis.{csv,md}, figure4_subperiods.csv
  report    figure4.png, figure4{a,b,c}.png, figure4_comparison.md, figure4_manifest.json
Outputs are in _output/replication/ unless noted.

Run: python src/replicate_figure4.py [ab] [c] [diagnose] [report]   (default: ab c report)
"""

import argparse
import json
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
from regress import fe_ols_chunked  # noqa: E402
from replicate_exhibits import earnings_events as shared_earnings_events  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "_data" / "derived" / "panel"
WRDS = ROOT / "_data" / "wrds"
BFKR = ROOT / "_data" / "derived" / "bfkr"
DERIVED = ROOT / "_data" / "derived" / "figure4"
OUT = ROOT / "_output" / "replication"

SAMPLE_START, SAMPLE_END = pd.Timestamp("2005-01-01"), pd.Timestamp("2019-07-31")
NEWS_START, NEWS_END = pd.Timestamp("2005-01-01"), pd.Timestamp("2015-12-31")
EA_DAYS = list(range(-10, 11))
NEWS_DAYS = list(range(-5, 6))
# Authors' controls are ES%, lambda, depth, rvol, turn, OI, |OI|, ret; lambda is unavailable here.
CONTROLS = ["es", "depth", "rvol", "turn", "oi", "absoi", "ret"]
SCORES = ["ITI(13D)", "ITI(patient)", "ITI(impatient)"]
PANEL_COLUMNS = ["permno", "date", "eligible", "vol", "ret", *CONTROLS[:-1], *SCORES]
DEVIATIONS = [
    "Sample 2005-01 to 2019-07 (paper: 1993-01 to 2019-07); local CRSP, TAQ indicators, "
    "Compustat and ITI start in 2004, used only as event-time warm-up.",
    "Panel (c) covers 2005-2015 (paper: 2000-2015).",
    "Control-completeness screen uses seven controls; Kyle's lambda is not built for the general panel.",
    "With-controls sensitivity uses the panel's depth (shares) and OI (share of volume) units, "
    "not the authors' shares-outstanding scaling.",
    "Earnings dates use our own volume test on Compustat rdq, not the authors' EAdates.hdf.",
    "Paper values are read off the published plots (about +/-0.003; panel (c) about +/-0.0003).",
]


# ---------------------------------------------------------------- sample construction

def load_panel():
    d = pd.read_parquet(PANEL / "daily.parquet", columns=PANEL_COLUMNS)
    d = d[d.date <= SAMPLE_END]
    return d.sort_values(["permno", "date"]).reset_index(drop=True)


def earnings_events(crsp):
    """Volume-adjusted earnings day 0 (paper p. 8) from the shared builder in
    replicate_exhibits: Compustat rdq via dated primary CCM links, moved to the next
    trading day when its volume is higher. Returns unique (permno, date)."""
    ev = shared_earnings_events(crsp)[["permno", "day0"]].rename(columns={"day0": "date"})
    return ev.drop_duplicates().sort_values(["permno", "date"]).reset_index(drop=True)


def sparse_stocks(d):
    """Stocks whose median calendar gap between consecutive observations exceeds one day."""
    gap = d.groupby("permno").date.diff().dt.days
    med = gap.groupby(d.permno).median()
    return set(med.index[med > 1])


def row_sequence(d, rows="iti", drop_sparse=True, eligible=True):
    """Event-time row sequence. rows='iti' keeps posted-ITI stock-days with a return
    (the authors' panel); rows='crsp' keeps all CRSP common-stock days (previous build)."""
    keep = d.ret.notna()
    if rows == "iti":
        keep &= d[SCORES].notna().any(axis=1)
    s = d[keep]
    if eligible:
        s = s[s.eligible]
    n_sparse = 0
    if drop_sparse:
        sparse = sparse_stocks(s)
        n_sparse = int(s.permno.isin(sparse).sum())
        s = s[~s.permno.isin(sparse)]
    return s.reset_index(drop=True), n_sparse


def flag_events(seq, events):
    """0/1 announcement flag on the row sequence (events not on a sequence row are lost,
    as with the authors' left join)."""
    f = seq[["permno", "date"]].merge(events.assign(EA=1), on=["permno", "date"], how="left").EA
    return f.fillna(0).to_numpy(np.int8)


def event_dummies(permno, flag, days, edges="drop"):
    """Indicator for day k is the flag shifted by k rows within each stock, i.e.
    groupby(permno).shift(k). Returns (n x len(days) int8 array, valid-row mask).
    With edges='drop', rows whose shifts leave the stock's history are invalid (the
    authors' dropna); with edges='zero' every row is valid (previous build)."""
    permno = np.asarray(permno)
    n = len(permno)
    start = np.r_[True, permno[1:] != permno[:-1]]
    first = np.maximum.accumulate(np.where(start, np.arange(n), 0))
    pos = np.arange(n) - first
    size = np.bincount(np.cumsum(start) - 1)[np.cumsum(start) - 1]
    out = np.zeros((n, len(days)), dtype=np.int8)
    ev = np.flatnonzero(np.asarray(flag) == 1)
    for j, k in enumerate(days):
        p = ev + k
        ok = (p >= 0) & (p < n)
        p, src = p[ok], ev[ok]
        same = permno[p] == permno[src]
        out[p[same], j] = 1
    if edges == "zero":
        return out, np.ones(n, dtype=bool)
    valid = (pos >= max(days)) & (pos < size + min(days))
    return out, valid


def quartile_groups(permno, flag, ret, which, dummies):
    """Authors' run_EAs_test(surprise_analysis=True): returns (keep mask, n_events).

    |surprise| is |ret| on announcement rows; 'bottom' is < 25th percentile and 'top'
    is > 75th, over all announcements. The group flag is forward- then back-filled
    (limit 10 rows) within stock. Rows with exactly one event indicator and no group
    are dropped, then only rows with group 1 or no group are kept."""
    flag = np.asarray(flag)
    surprise = pd.Series(np.where(flag == 1, np.abs(ret), np.nan))
    if which == "bottom":
        idd = surprise < surprise.quantile(0.25)
    else:
        idd = surprise > surprise.quantile(0.75)
    group = pd.Series(np.where(surprise.notna(), idd.astype(float), np.nan))
    g = group.groupby(np.asarray(permno))
    group = g.ffill(limit=10)
    group = group.groupby(np.asarray(permno)).bfill(limit=10)
    # Literal port of the authors' filter. On our sequence it never fires: every
    # announcement row has a return, so it gets a group, and the +/-10-row fills
    # cover the whole event window. Kept so the port stays line-for-line.
    exclude = (dummies.sum(axis=1) == 1) & group.isna().to_numpy()
    keep = ~exclude & ((group == 1) | group.isna()).to_numpy()
    return keep, int(idd.sum())


# ---------------------------------------------------------------- estimation

def regress(frame, y, dummy_cols, controls=()):
    frame = frame.copy()
    frame["date_id"] = frame.date.dt.strftime("%Y%m%d").astype(int)
    xs = [*dummy_cols, *controls]
    tab, stats = fe_ols_chunked(frame, y, xs, fe="permno", cluster2="date_id")
    return tab.loc[dummy_cols], stats


def event_table(seq, flag, y="ITI(13D)", which=None, edges="drop", controls_screen=True,
                with_controls=True, start=SAMPLE_START, end=SAMPLE_END):
    names = [f"d{k}" for k in EA_DAYS]
    dm, valid = event_dummies(seq.permno.to_numpy(), flag, EA_DAYS, edges=edges)
    keep = valid.copy()
    n_events = int(flag.sum())
    if which is not None:
        q, n_events = quartile_groups(seq.permno.to_numpy(), flag, seq.ret.to_numpy(), which, dm)
        keep &= q
    keep &= ((seq.date >= start) & (seq.date <= end)).to_numpy()
    keep &= seq[y].notna().to_numpy() & seq.eligible.to_numpy()
    if controls_screen:
        keep &= seq[CONTROLS].notna().all(axis=1).to_numpy()
    frame = seq.loc[keep, ["permno", "date", y, *CONTROLS]].reset_index(drop=True)
    for j, n in enumerate(names):
        frame[n] = dm[keep, j]
    tab, stats = regress(frame, y, names)
    res = pd.DataFrame({"day": EA_DAYS, "coef": tab.coef.to_numpy(), "se": tab.se.to_numpy()})
    if with_controls:
        for c in CONTROLS:
            frame[c] = winsorize(frame[c])
        tc, _ = regress(frame, y, names, CONTROLS)
        res["coef_controls"], res["se_controls"] = tc.coef.to_numpy(), tc.se.to_numpy()
    in_sample = frame[frame[names[EA_DAYS.index(0)]] == 1]
    res["nobs"], res["n_events"] = stats["nobs"], len(in_sample)
    res["n_stocks"] = frame.permno.nunique()
    return res.assign(lower=res.coef - 2 * res.se, upper=res.coef + 2 * res.se), n_events


# ---------------------------------------------------------------- panels

def panels_ab(d):
    seq, n_sparse = row_sequence(d)
    ev = earnings_events(d)
    DERIVED.mkdir(parents=True, exist_ok=True)
    ev.to_parquet(DERIVED / "earnings_adjusted.parquet", index=False)
    flag = flag_events(seq, ev)
    a, _ = event_table(seq, flag)
    a.insert(0, "group", "all")
    a["paper"] = pv.FIG4A
    parts = []
    for which, label, paper in [("top", "large", pv.FIG4B_LARGE), ("bottom", "small", pv.FIG4B_SMALL)]:
        t, n_q = event_table(seq, flag, which=which)
        t.insert(0, "group", label)
        t["paper"] = paper
        t["n_quartile_events_all_years"] = n_q
        parts.append(t)
    b = pd.concat(parts, ignore_index=True)
    a.to_csv(OUT / "figure4a.csv", index=False)
    b.to_csv(OUT / "figure4b.csv", index=False)
    info = {"sequence_rows": len(seq), "sparse_rows_dropped": n_sparse,
            "sequence_stocks": int(seq.permno.nunique()),
            "earnings_events_crsp_days": len(ev), "earnings_events_on_sequence": int(flag.sum()),
            "posted_iti_rows_ineligible_share": ineligible_share(d)}
    write_counts("ab", info)
    return a, b, info


def ineligible_share(d):
    iti = d[d.ret.notna() & d[SCORES].notna().any(axis=1) & (d.date >= SAMPLE_START)]
    return float((~iti.eligible).mean())


def panel_c(d, earnings=None):
    from analyze_bfkr_news import estimate, event_design

    news = pd.read_parquet(BFKR / "news_daily.parquet")
    if earnings is None:
        path = DERIVED / "earnings_adjusted.parquet"
        earnings = pd.read_parquet(path) if path.exists() else earnings_events(d)
    market = pd.read_parquet(WRDS / "crsp_market.parquet", columns=["date"])
    design, excluded = event_design(news, earnings, market.date)
    seq, _ = row_sequence(d)
    sample = design[(design.date >= NEWS_START) & (design.date <= NEWS_END)].merge(
        seq[["permno", "date", *SCORES, *CONTROLS]], on=["permno", "date"], how="inner",
        validate="one_to_one").dropna(subset=CONTROLS)
    result, fit, used = estimate(sample)
    used.reset_index().to_parquet(DERIVED / "figure4c_sample.parquet", index=False)
    c = result.rename(columns={"event_day": "day", "coefficient": "coef", "standard_error": "se"})
    c.insert(0, "group", "all news")
    c["paper"] = pv.FIG4C
    c["nobs"] = int(fit.nobs)
    c["n_stocks"] = int(used.index.get_level_values("permno").nunique())
    c["n_news_days"] = int(used.news0.eq(1).sum()) if "news0" in used else np.nan
    c.to_csv(OUT / "figure4c.csv", index=False)
    info = {"news_rows_linked": len(news), "earnings_window_rows_excluded": excluded,
            "news_sample_dates": [str(used.index.get_level_values("date").min().date()),
                                  str(used.index.get_level_values("date").max().date())]}
    write_counts("c", info)
    return c, info


def write_counts(part, info):
    (DERIVED / f"figure4_counts_{part}.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")


def read_counts():
    info = {}
    for part in ["ab", "c"]:
        path = DERIVED / f"figure4_counts_{part}.json"
        if path.exists():
            info.update(json.loads(path.read_text(encoding="utf-8")))
    return info


def diagnose(d):
    """Day-0 coefficient of panel (a) as each specification change is applied."""
    ev = earnings_events(d)
    steps = [
        ("previous build: all CRSP days, no screens, zero-filled edges",
         dict(rows="crsp", drop_sparse=False, eligible=False), dict(edges="zero", controls_screen=False)),
        ("+ posted-ITI row sequence, drop edge rows",
         dict(rows="iti", drop_sparse=False), dict(edges="drop", controls_screen=False)),
        ("+ drop sparse stocks", dict(rows="iti", drop_sparse=True), dict(edges="drop", controls_screen=False)),
        ("+ require seven controls (final)", dict(rows="iti", drop_sparse=True),
         dict(edges="drop", controls_screen=True)),
    ]
    rows = []
    for label, seq_kw, tab_kw in steps:
        seq, _ = row_sequence(d, **seq_kw)
        t, _ = event_table(seq, flag_events(seq, ev), with_controls=False, **tab_kw)
        day0 = t[t.day == 0].iloc[0]
        rows.append({"step": label, "day0_coef": day0.coef, "day_minus1_coef": t[t.day == -1].coef.item(),
                     "day1_coef": t[t.day == 1].coef.item(), "nobs": int(day0.nobs),
                     "paper_day0": pv.FIG4A[EA_DAYS.index(0)]})
        print(label, f"{day0.coef:.4f}", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "figure4_diagnosis.csv", index=False)
    # Final specification by subperiod, for panel (a) and both panel (b) quartiles: does
    # the response drift over time, and by the same amount for large and small |r|? The
    # paper's sample adds 1993-2004, which local data do not cover. Quartile cutoffs are
    # over all announcements, as in panel (b).
    seq, _ = row_sequence(d)
    flag = flag_events(seq, ev)
    sub = []
    for lo, hi in SUBPERIODS:
        window = seq[(seq.date >= lo) & (seq.date <= hi)]
        for which, group in [(None, "all"), ("top", "large"), ("bottom", "small")]:
            t, _ = event_table(seq, flag, which=which, with_controls=False,
                               start=pd.Timestamp(lo), end=pd.Timestamp(hi))
            coef = t.set_index("day").coef
            sub.append({"period": f"{lo[:4]}-{hi[:4]}", "group": group,
                        "day_minus1_coef": coef[-1], "day0_coef": coef[0],
                        "day0_se": t[t.day == 0].se.item(), "day1_coef": coef[1], "day2_coef": coef[2],
                        "mean_iti13d": float(window["ITI(13D)"].mean()),
                        "sd_iti13d": float(window["ITI(13D)"].std()), "nobs": int(t.nobs.iloc[0]),
                        "n_events": int(t.n_events.iloc[0])})
            print(sub[-1], flush=True)
    sp = pd.DataFrame(sub)
    sp.to_csv(OUT / "figure4_subperiods.csv", index=False)
    write_diagnosis_md(out, sp)
    return out


SUBPERIODS = [("2005-01-01", "2009-12-31"), ("2010-01-01", "2014-12-31"), ("2015-01-01", "2019-07-31")]
PAPER_DAY0 = {"all": pv.FIG4A, "large": pv.FIG4B_LARGE, "small": pv.FIG4B_SMALL}


def write_diagnosis_md(dg, sp):
    i0 = EA_DAYS.index(0)
    lines = ["# Figure 4(a)-(b) diagnostics", "",
             "Built by `src/replicate_figure4.py diagnose` (`doit figure4_diagnose`).", "",
             "## Panel (a) day-0 coefficient by specification step", "",
             "| step | day 0 | day -1 | day 1 | observations |", "|---|---|---|---|---|"]
    lines += [f"| {r.step} | {r.day0_coef:.4f} | {r.day_minus1_coef:.4f} | {r.day1_coef:.4f} | {r.nobs:,} |"
              for r in dg.itertuples()]
    lines += ["", f"Paper day 0: {pv.FIG4A[i0]:.3f}.", "",
              "## Day-0 coefficient by subperiod (final specification)", "",
              "Panel (b) quartile cutoffs are over all announcements, as in the full-sample panel.", "",
              "| period | all | large \\|r\\| | small \\|r\\| | large - small | events (all) | observations (all) |",
              "|---|---|---|---|---|---|---|"]
    for period, g in sp.groupby("period", sort=False):
        v = g.set_index("group")
        lines.append(f"| {period} | {v.day0_coef['all']:.4f} | {v.day0_coef['large']:.4f} | "
                     f"{v.day0_coef['small']:.4f} | {v.day0_coef['large'] - v.day0_coef['small']:.4f} | "
                     f"{v.n_events['all']:,} | {v.nobs['all']:,} |")
    p = {k: v[i0] for k, v in PAPER_DAY0.items()}
    lines += [f"| paper, 1993-2019 | {p['all']:.3f} | {p['large']:.3f} | {p['small']:.3f} | "
              f"{p['large'] - p['small']:.3f} | | |", "",
              "Standard errors, days -1 to 2, and ITI(13D) moments are in `figure4_subperiods.csv`.", ""]
    (OUT / "figure4_diagnosis.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- outputs

COLORS = {"all": "#1f5fbf", "large": "#1f5fbf", "small": "#c0392b", "all news": "#1f5fbf"}
LABELS = {"all": "all announcements", "large": "large |r|", "small": "small |r|", "all news": "all news days"}


def draw(ax, tab, title, xlabel):
    for g, t in tab.groupby("group", sort=False):
        ax.errorbar(t.day, t.coef, yerr=2 * t.se, marker="o", ms=3, capsize=2, lw=1,
                    color=COLORS[g], label=f"Ours: {LABELS[g]}")
        ax.plot(t.day, t.paper, ls="--", lw=1, color=COLORS[g], alpha=0.55, label=f"Paper: {LABELS[g]}")
    ax.axhline(0, color="black", lw=0.6, ls=":")
    ax.set_xticks(sorted(tab.day.unique()))
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Δ ITI")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, frameon=False)


PANELS = {
    "a": ("(a) ITI(13D) around earnings announcements", "Day around earnings announcement"),
    "b": ("(b) Top and bottom quartile absolute announcement return", "Day around earnings announcement"),
    "c": ("(c) ITI(impatient) around news events (excluding earnings announcements)", "Day around news event"),
}


def plot(tables):
    for key, tab in tables.items():
        fig, ax = plt.subplots(figsize=(7, 3.2))
        draw(ax, tab, *PANELS[key])
        fig.text(0.99, 0.01, "Bands: ±2 SE, double-clustered by stock and date", ha="right", fontsize=6)
        fig.tight_layout()
        fig.savefig(OUT / f"figure4{key}.png", dpi=150)
        plt.close(fig)
    fig, axes = plt.subplots(len(tables), 1, figsize=(7, 3.0 * len(tables)))
    for ax, (key, tab) in zip(np.atleast_1d(axes), tables.items()):
        draw(ax, tab, *PANELS[key])
    fig.suptitle("Figure 4: ITI around earnings announcements and news events", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "figure4.png", dpi=150)
    plt.close(fig)


def md_table(tab):
    cols = ["group", "day", "coef", "lower", "upper", "paper"]
    t = tab[cols].copy()
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in t.itertuples(index=False):
        lines.append(f"| {r.group} | {r.day} | {r.coef:.4f} | {r.lower:.4f} | {r.upper:.4f} | {r.paper:.4f} |")
    return lines


def summary_lines(tab):
    lines = []
    for g, t in tab.groupby("group", sort=False):
        z = t[t.day == 0].iloc[0]
        ratio = z.coef / z.paper if z.paper else np.nan
        corr = np.corrcoef(t.coef, t.paper)[0, 1]
        lines.append(f"- {LABELS[g]}: day 0 {z.coef:.4f} vs paper {z.paper:.4f} (ratio {ratio:.2f}); "
                     f"correlation with paper profile {corr:.3f}; {int(z.nobs):,} observations")
    return lines


def write_reports(tables, info):
    lines = ["# Figure 4 replication", "",
             "Built by `src/replicate_figure4.py` from the posted original-vintage ITI. "
             "Specification follows the authors' `ITI_main.py`; see the script docstring.", "",
             "## Deviations from the paper", "", *[f"- {x}" for x in DEVIATIONS], ""]
    for key, tab in tables.items():
        lines += [f"## Panel {PANELS[key][0]}", "", *summary_lines(tab), "", *md_table(tab), ""]
    lines += ["Specification diagnostics and the subperiod split are in `figure4_diagnosis.md` "
              "(`doit figure4_diagnose`).", ""]
    lines += ["## Sample counts", "", "```json", json.dumps(info, indent=2), "```", ""]
    (OUT / "figure4_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = {"script": "src/replicate_figure4.py", "panels": sorted(tables),
                "sample": [str(SAMPLE_START.date()), str(SAMPLE_END.date())],
                "news_sample": [str(NEWS_START.date()), str(NEWS_END.date())],
                "controls_screen": CONTROLS, "deviations": DEVIATIONS, "counts": info,
                "inputs": {str(p.relative_to(ROOT)).replace("\\", "/"): {"bytes": p.stat().st_size}
                           for p in [PANEL / "daily.parquet", WRDS / "compustat_earnings.parquet",
                                     WRDS / "crsp_compustat_links.parquet", BFKR / "news_daily.parquet"]
                           if p.exists()}}
    (OUT / "figure4_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def load_existing(key):
    path = OUT / f"figure4{key}.csv"
    return pd.read_csv(path) if path.exists() else None


PARTS = ["ab", "c", "diagnose", "report"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # No `choices`: with nargs="*", Python <= 3.11 rejects the empty default against them.
    ap.add_argument("parts", nargs="*", metavar="part", help=f"any of {', '.join(PARTS)} (default: ab c report)")
    args = ap.parse_args()
    bad = sorted(set(args.parts) - set(PARTS))
    if bad:
        ap.error(f"invalid part(s) {', '.join(bad)}; choose from {', '.join(PARTS)}")
    parts = args.parts or ["ab", "c", "report"]
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    d = load_panel() if set(parts) & {"ab", "c", "diagnose"} else None
    ea = None
    if "diagnose" in parts:
        diagnose(d)
    if "ab" in parts:
        panels_ab(d)
        ea = pd.read_parquet(DERIVED / "earnings_adjusted.parquet")
    if "c" in parts:
        panel_c(d, ea)
    if "report" in parts:
        tables = {k: load_existing(k) for k in "abc"}
        tables = {k: v for k, v in tables.items() if v is not None}
        plot(tables)
        write_reports(tables, read_counts())
        for k, t in tables.items():
            print(f"Panel ({k})", *summary_lines(t), sep="\n  ", flush=True)


if __name__ == "__main__":
    main()
