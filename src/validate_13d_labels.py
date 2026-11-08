"""Validate rebuilt 13D labels against the paper's published statistics.

Compares events filed 2005-PAPER_13D_LAST_YEAR with the paper (Table 1, Section 4.1,
Table IA.5, Figure IA.1 and the authors' ITI_main.py), and reports:
  - event funnel (filings lost at each screen)
  - label statistics vs paper targets
  - filer volume never above CRSP volume
  - posted ITI(13D) (original vintage) on trade vs non-trade days, within-filing slope
  - buy-and-hold abnormal return around the filing date (Figure IA.1 analogue)

The posted ITI was trained on the authors' own events and excludes their training
windows, so its relation to our labels is a sanity check, not a replication; its
coverage of our label rows also hints at overlap with the authors' sample.

Output: _output/13d_label_validation.md, _output/13d_filing_car.png
Run: python src/validate_13d_labels.py
"""

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screen_13d import load_crsp_daily  # noqa: E402
from settings import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PAPER = {  # target values from the paper / authors' code
    "rows_per_event": (58197 / 1593, "Table 1: 58,197 rows / 1,593 filings"),
    "itrade": (0.3603, "Table 1"),
    "itrade_patient": (0.30, "Sec. 4.1: 30% of days in first 40"),
    "itrade_impatient": (0.49, "Sec. 4.1: 49% of days in last 20"),
    "vol_share": (0.28, "Sec. 3.1: 28% of daily volume when trading"),
    "vol_share_patient": (0.20, "Sec. 4.1"),
    "vol_share_impatient": (0.37, "Sec. 4.1"),
    "turn13d_mean_x100": (0.2755, "Table IA.5, trade days"),
    "turn13d_median_x100": (0.1055, "Table IA.5, trade days"),
    "sell_share": (0.06, "ITI_main.py comment: ~6% of activist trades are sells"),
}


def winsorize(s, q=0.0005):
    lo, hi = s.quantile([q, 1 - q])
    return s.clip(lo, hi)


def label_stats(lab):
    tr = lab[lab.itrade == 1].copy()
    tr["vs"] = winsorize(tr["13Dvol/vol"])
    tr["t"] = winsorize(tr["13Dturn"])
    return {
        "events": lab.filing.nunique(),
        "rows_per_event": len(lab) / max(lab.filing.nunique(), 1),
        "itrade": lab.itrade.mean(),
        "itrade_patient": lab[lab.patient].itrade.mean(),
        "itrade_impatient": lab[~lab.patient].itrade.mean(),
        "vol_share": tr.vs.mean(),
        "vol_share_patient": tr[tr.patient].vs.mean(),
        "vol_share_impatient": tr[~tr.patient].vs.mean(),
        "turn13d_mean_x100": tr.t.mean() * 100,
        "turn13d_median_x100": tr.t.median() * 100,
        "sell_share": (tr.ivol < 0).mean(),
        "filer_shares_gt_crsp_vol": ((tr.shares_bought + tr.shares_sold) > tr.vol).mean(),
    }


def posted_iti(lab):
    files = sorted((ROOT / "_data" / "public" / "iti_original_through_2019").glob("year=*/*.parquet"))
    if not files:
        return None
    years = set(lab.date.dt.year)
    iti = pd.concat([pd.read_parquet(f, columns=["permno", "date", "ITI(13D)"]) for f in files
                     if int(f.parent.name.split("=")[1]) in years])
    iti["permno"] = iti.permno.astype("int64")
    m = lab.assign(permno=lab.permno.astype("int64")).merge(iti, on=["permno", "date"], how="left")
    cov = m["ITI(13D)"].notna().mean()
    m = m.dropna(subset=["ITI(13D)"])
    if m.empty:
        return {"coverage": cov}
    y = m.itrade - m.groupby("filing").itrade.transform("mean")
    x = m["ITI(13D)"] - m.groupby("filing")["ITI(13D)"].transform("mean")
    slope = (x * y).sum() / (x * x).sum()
    r2 = 1 - ((y - slope * x) ** 2).sum() / (y ** 2).sum()
    return {"coverage": cov, "iti_trade": m[m.itrade == 1]["ITI(13D)"].mean(),
            "iti_notrade": m[m.itrade == 0]["ITI(13D)"].mean(), "slope": slope, "within_r2": r2}


def authors_comparison(events):
    """Recall/precision of our events against windows recovered from the posted ITI."""
    path = config("THIRTEEN_D_DIR") / "authors_windows.parquet"
    if not path.exists():
        return ["", "Authors' windows not recovered (run src/authors_13d_windows.py).", ""]
    w = pd.read_parquet(path)
    w = w[(w.end >= "2005-01-01") & (w.end.dt.year <= config("PAPER_13D_LAST_YEAR"))].reset_index(drop=True)
    ev = events[events.permno.notna()].copy()
    ev["permno"] = ev.permno.astype("int64")
    m = w.reset_index(names="wid").merge(ev[["permno", "filing_date", "included", "exclusion_reason"]],
                                         on="permno")
    gap = (m.filing_date - m.end).dt.days
    m = m[(gap >= -3) & (gap <= 7)].sort_values(["wid", "included"], ascending=[True, False])
    best = m.drop_duplicates("wid")
    outcome = best.exclusion_reason.fillna("included").value_counts()
    inc = events[events.included & events.in_paper_period]
    prec = inc.in_authors_sample.mean()
    lines = ["## Comparison with the authors' events", "",
             "The posted ITI file blanks the three 13D-trained scores inside the authors' training "
             "windows (`src/authors_13d_windows.py`). Windows ending 2005-2018 are matched to our "
             "filings on PERMNO and filing date (3 days before to 7 days after the window's end).", "",
             f"Recovered authors' windows ending 2005-{config('PAPER_13D_LAST_YEAR')}: {len(w):,}.", "",
             "| Outcome for the authors' window | Windows |", "|---|---:|"]
    for k, v in outcome.items():
        lines.append(f"| our filing {'included' if k == 'included' else 'excluded at ' + k} | {v:,} |")
    lines.append(f"| no linked filing of ours | {len(w) - best.wid.nunique():,} |")
    lines += ["", f"Recall: {outcome.get('included', 0) / len(w):.1%} of the authors' windows match an "
              f"included event. Precision: {prec:.1%} of our {len(inc):,} included 2005-"
              f"{config('PAPER_13D_LAST_YEAR')} events match an authors' window. Use "
              "`in_authors_sample` to restrict training to the authors' events.", ""]
    return lines


def car_around_filing(events, crsp, pre=40, post=10):
    mkt = pd.read_parquet(ROOT / "_data" / "wrds" / "crsp_market.parquet", columns=["date", "vwretd"])
    r = crsp[["permno", "date", "ret"]].merge(mkt, on="date")
    r["ex"] = pd.to_numeric(r.ret, errors="coerce") - r.vwretd
    paths = []
    for p, fd in zip(events.permno.astype("int64"), events.filing_date):
        s = r[r.permno == p].reset_index(drop=True)
        k = s.date.searchsorted(fd)
        if k >= len(s) or k - pre < 0 or k + post >= len(s):
            continue
        seg = s.iloc[k - pre:k + post + 1]
        paths.append((np.cumprod(1 + seg.ret.astype(float).fillna(0).values)
                      - np.cumprod(1 + seg.vwretd.fillna(0).values)))
    return np.arange(-pre, post + 1), (np.nanmean(paths, axis=0) if paths else None), len(paths)


def main():
    d = config("THIRTEEN_D_DIR")
    out = config("OUTPUT_DIR")
    events = pd.read_parquet(d / "events.parquet")
    lab = pd.read_parquet(d / "labels_daily.parquet")
    inc = events[events.included]
    lab_p = lab[lab.in_paper_period]

    funnel = events.exclusion_reason.fillna("included").value_counts()
    order = ["linked", "common_stock", "price", "mcap", "no_derivatives", "has_trades",
             "duplicate_event", "included"]
    lines = ["# Schedule 13D label validation", "",
             "Filings are original SC 13D submissions 2005-2019 from WRDS. 'Paper period' means "
             f"filed 2005-{config('PAPER_13D_LAST_YEAR')} (the paper's sample is 1994-2018, "
             "1,593 events).", "", "## Event funnel", "",
             "| First failed screen | Filings |", "|---|---:|"]
    lines += [f"| {k} | {funnel.get(k, 0):,} |" for k in order]
    yr = inc.groupby(inc.filing_date.dt.year).size()
    lines += ["", "Included events by filing year: " + ", ".join(f"{y}: {n}" for y, n in yr.items()), ""]

    lines += authors_comparison(events)

    st, st_all = label_stats(lab_p), label_stats(lab)
    lab_a = lab_p[lab_p.in_authors_sample.fillna(False)]
    st_a = label_stats(lab_a) if len(lab_a) else {k: float("nan") for k in st}
    lines += ["## Labels vs paper", "",
              "| Statistic | Ours, 2005-2018 | Ours, authors' events only | Ours, 2005-2019 | Paper | Source |",
              "|---|---:|---:|---:|---:|---|"]
    for k, v in st.items():
        tgt = PAPER.get(k)
        lines.append(f"| {k} | {v:,.4f} | {st_a[k]:,.4f} | {st_all[k]:,.4f} | "
                     f"{'' if tgt is None else f'{tgt[0]:.4f}'} | {'' if tgt is None else tgt[1]} |")

    it = posted_iti(lab_p)
    if it:
        lines += ["", "## Posted ITI(13D), original vintage", "",
                  f"Coverage of our paper-period label rows: {it['coverage']:.1%} (the authors' file "
                  "omits their own training windows, so low coverage suggests overlap with their sample)."]
        if "slope" in it:
            lines += [f"Mean ITI on trade days {it['iti_trade']:.3f} vs non-trade days {it['iti_notrade']:.3f}; "
                      f"within-filing slope of itrade on ITI {it['slope']:.3f}, within R2 {it['within_r2']:.3f} "
                      "(paper Table 2 col. 1, out-of-fold ITI: 0.697, R2 0.099)."]

    crsp = load_crsp_daily(inc.permno, columns=("permno", "date", "ret"))
    x, car, n = car_around_filing(inc[inc.in_paper_period], crsp)
    if car is not None:
        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.plot(x, car, color="#2a6f97")
        ax.axhline(0, color="grey", lw=0.8, ls="--")
        ax.axvline(0, color="grey", lw=0.8)
        ax.set_xlabel("Trading days relative to Schedule 13D filing")
        ax.set_ylabel("Buy-and-hold return minus CRSP VW")
        ax.set_title(f"Abnormal return around filing, rebuilt 13D events (n={n})")
        fig.tight_layout()
        fig.savefig(out / "13d_filing_car.png", dpi=150)
        k0 = int(np.where(x == -1)[0][0])
        lines += ["", "## Abnormal return around filing", "",
                  f"Events: {n}. Cumulative excess return from day -40 to day -1: {car[k0]:.2%} "
                  "(paper Fig. IA.1: about 3%); days 0 to +1: "
                  f"{car[k0 + 2] - car[k0]:.2%} (paper: about 2%). Chart: `_output/13d_filing_car.png`."]
    (out / "13d_label_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
