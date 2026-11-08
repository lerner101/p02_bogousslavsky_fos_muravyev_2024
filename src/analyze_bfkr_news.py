"""Figure 4(c) news regression, or an explicitly preliminary local-data chart.

Final mode requires a prepared paper control panel and adjusted earnings events.
Preview mode uses raw Compustat rdq, omits control-based sample selection, and
must not be interpreted as an exact replication. Both use posted original ITI.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data/derived/bfkr"
CONTROLS = ["ES%", "lambda", "depth", "rvol", "turn", "OI", "|OI|", "ret"]
SCORES = ["ITI(13D)", "ITI(patient)", "ITI(impatient)"]


def require_keys(df, name):
    if df[["permno", "date"]].isna().any().any() or df.duplicated(["permno", "date"]).any():
        raise ValueError(f"{name}: null or duplicate permno/date keys")


def event_design(news, earnings, calendar):
    """Authors' ordering: exclude earnings +/-2 rows, then shift news +/-5 rows.

    Shifts run on each stock's supplied BFKR observation sequence, as in
    ITI_main.py, not on calendar days. A positive regressor lag means a news
    event in the past, i.e. a positive chart event day. Weekend rdq is mapped
    forward to the next market trading date for the raw-date preview.
    """
    require_keys(news, "news")
    n = news.sort_values(["permno", "date"]).copy()
    e = earnings[["permno", "date"]].dropna().drop_duplicates().copy()
    cal = pd.DatetimeIndex(calendar).sort_values().unique()
    ix = cal.searchsorted(e.date)
    e = e.loc[ix < len(cal)].copy()
    e["date"] = cal[ix[ix < len(cal)]]
    e = e.drop_duplicates().assign(EA=1)
    n = n.merge(e, on=["permno", "date"], how="left", validate="one_to_one")
    n["EA"] = n.EA.fillna(0)
    exclude = pd.Series(False, index=n.index)
    for lag in range(-2, 3):
        exclude |= n.groupby("permno").EA.shift(lag).eq(1)
    n = n.loc[~exclude].copy()
    n["news"] = n.CC_day_type.isin([1, 2, 3]).astype(float)
    for lag in range(-5, 6):
        n[f"news{lag}"] = n.groupby("permno").news.shift(lag)
    return n, int(exclude.sum())


def estimate(panel):
    from linearmodels.panel import PanelOLS

    terms = [f"news{k}" for k in range(-5, 6)]
    sample = panel.dropna(subset=terms + SCORES).copy()
    sample["const"] = 1.0
    sample = sample.set_index(["permno", "date"]).sort_index()
    fit = PanelOLS(sample["ITI(impatient)"], sample[["const"] + terms],
                   entity_effects=True).fit(cov_type="clustered", cluster_entity=True,
                                             cluster_time=True)
    result = pd.DataFrame({"event_day": range(-5, 6), "coefficient": fit.params[terms].values,
                           "standard_error": fit.std_errors[terms].values})
    # The authors export twice the standard error as their plotted 95% interval.
    result["lower"] = result.coefficient - 2 * result.standard_error
    result["upper"] = result.coefficient + 2 * result.standard_error
    return result, fit, sample


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--controls", type=Path, help="Paper-screened stock-day Parquet with all eight controls")
    ap.add_argument("--earnings", type=Path, help="Adjusted earnings events, unique permno/date keys")
    ap.add_argument("--start-year", type=int, default=2005)
    ap.add_argument("--end-year", type=int, default=2015)
    args = ap.parse_args()
    if args.start_year > args.end_year:
        ap.error("start-year must not exceed end-year")
    if not args.preview and (args.controls is None or args.earnings is None):
        ap.error("Final analysis needs --controls and --earnings; use --preview for the raw-date diagnostic")
    if args.preview and (args.controls is not None or args.earnings is not None):
        ap.error("Preview uses the unadjusted local earnings input and no controls; omit --controls/--earnings")
    news = pd.read_parquet(DATA / "news_daily.parquet")
    # Retain the entire available sequence when creating lags and earnings exclusions.
    market = pd.read_parquet(ROOT / "_data/wrds/crsp_market.parquet", columns=["date"])
    earnings = pd.read_parquet(args.earnings or DATA / "earnings_unadjusted.parquet")
    require_keys(earnings, "earnings")
    if not args.preview and not earnings.date.isin(market.date).all():
        raise ValueError("Adjusted earnings must already be aligned to dates in the market calendar")
    design, excluded = event_design(news, earnings, market.date)
    parts = sorted((ROOT / "_data/public/iti_original_through_2019").glob("year=*/*.parquet"))
    parts = [p for p in parts if args.start_year <= int(p.parent.name.split("=")[1]) <= args.end_year]
    if not parts:
        raise ValueError("No original-vintage ITI partitions for requested years")
    iti = pd.concat([pd.read_parquet(p, columns=["permno", "date"] + SCORES) for p in parts],
                    ignore_index=True)
    require_keys(iti, "ITI")
    panel = design[design.date.dt.year.between(args.start_year, args.end_year)].merge(
        iti, on=["permno", "date"], how="left", validate="one_to_one")
    if args.controls:
        controls = pd.read_parquet(args.controls, columns=["permno", "date"] + CONTROLS)
        require_keys(controls, "controls")
        panel = panel.merge(controls, on=["permno", "date"], how="inner", validate="one_to_one")
        # The plotted no-controls regression still requires complete controls in authors' code.
        panel = panel.dropna(subset=CONTROLS)
    result, fit, sample = estimate(panel)
    label = "PRELIMINARY: raw earnings dates; no control completeness screen" if args.preview else "Figure 4(c): supplied controls and adjusted earnings"
    stem = "figure_04c_preview" if args.preview else "figure_04c"
    sample.reset_index().to_parquet(DATA / f"{stem}_sample.parquet", index=False)
    out = ROOT / "_output"
    out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out / f"{stem}.csv", index=False)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.errorbar(result.event_day, result.coefficient, yerr=2 * result.standard_error,
                fmt="o-", color="#3157a4", capsize=3, lw=1)
    ax.axhline(0, color="grey", ls="--", lw=0.8)
    ax.set(xticks=np.arange(-5, 6), xlabel="Observation days relative to news event",
           ylabel="Change in ITI(impatient)", title="ITI around news events, excluding earnings windows")
    fig.text(0.5, 0.01, label, ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out / f"{stem}.png", dpi=160)
    plt.close(fig)
    summary = {"mode": label, "observations": int(fit.nobs),
               "stocks": int(sample.index.get_level_values("permno").nunique()),
               "date_range": [str(sample.index.get_level_values("date").min().date()),
                              str(sample.index.get_level_values("date").max().date())],
               "earnings_window_rows_excluded_full_news_history": excluded,
               "iti": "Original posted ITI(impatient); all three 13D scores required nonmissing",
               "earnings_input": str(args.earnings or DATA / "earnings_unadjusted.parquet"),
               "control_input": str(args.controls) if args.controls else None,
               "specification": "Stock fixed effects; stock/date clustered SE; intervals +/-2 SE",
               "limitations": ["Default sample starts 2005; screenshot starts 2000",
                               "Ticker links with ambiguity are excluded",
                               "Preview does not apply the paper's complete control/universe screens"] if args.preview else
                              ["Exactness depends on supplied control universe and adjusted earnings", "Check date range against screenshot"]}
    (out / f"{stem}.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / f"{stem}.md").write_text("# News-event regression\n\n" + label + "\n\n```json\n"
                                     + json.dumps(summary, indent=2) + "\n```\n\n```text\n"
                                     + str(fit.summary) + "\n```\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
