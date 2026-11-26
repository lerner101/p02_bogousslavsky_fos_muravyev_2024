"""Data-validation table and figure for the report, from committed outputs.

Each check compares our data with something known independently of our code:

1. Rebuilt 13D labels vs statistics the paper publishes (Table 1, Sec. 3.1/4.1,
   Table IA.5), parsed from _output/13d_label_validation.md.
2. TAQ consolidated volume vs CRSP daily volume on the acquisition pilot days.
3. Coverage through time: share of 13D label rows with complete model inputs,
   and share of our scored stock-days present in the authors' posted ITI file.
4. Agreement between our ITI(13D) and the authors' posted ITI(13D) by year.

The tolerances are stated in VALIDATION_TOLERANCES and enforced by
tests/test_data_validation.py. Writes _output/report/validation_table.tex,
validation_coverage.png and validation_summary.json.

Run: python src/validation_exhibits.py
"""

import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_output"
ML = OUTPUT / "ml_model"
REPORT = OUTPUT / "report"
TRAIN_YEARS = range(2005, 2019)  # 13D training filings; 2019 is out of sample by design

VALIDATION_TOLERANCES = {
    # Trade-day frequency is a direct property of the filings; the paper
    # reports 36.03%. Five points allows for our shorter 2005-2018 sample.
    "itrade_abs_diff": 0.05,
    # TAQ and CRSP volumes count the same trades; after 2014 CRSP excludes some
    # off-exchange odd-lot prints that TAQ includes, so allow 20%.
    "volume_ratio_band": (0.8, 1.2),
    # At least 60% of label rows in each training year must have model inputs.
    "min_input_coverage": 0.60,
    # Our scored stock-days must exist in the authors' file (same universe).
    "min_author_match": 0.95,
    # Two independently trained ITI(13D) models should be clearly correlated.
    "min_yearly_pearson": 0.40,
}


def parse_markdown_table(text, heading):
    """Return the first markdown table after `heading` as a DataFrame of strings."""
    block = text.split(heading, 1)[1]
    lines = [ln for ln in block.splitlines() if ln.startswith("|")]
    rows = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        rows.append(cells)
        if len(rows) > 1 and not ln.startswith("|"):
            break
    header, body = rows[0], rows[1:]
    return pd.DataFrame(body, columns=header)


def label_stats():
    text = (OUTPUT / "13d_label_validation.md").read_text()
    t = parse_markdown_table(text, "## Labels vs paper")
    t = t.rename(columns={"Ours, 2005-2018": "ours", "Paper": "paper"})
    t["ours"] = pd.to_numeric(t.ours.str.replace(",", ""), errors="coerce")
    t["paper"] = pd.to_numeric(t.paper.str.replace(",", ""), errors="coerce")
    return t[["Statistic", "ours", "paper", "Source"]].dropna(subset=["paper"])


def volume_reconciliation():
    v = pd.read_csv(ML / "pilot_volume_reconciliation.csv")
    v["ratio"] = v.market_volume / v.total_vol_m
    return v


def coverage():
    inputs = pd.read_csv(ML / "available_input_attrition.csv").rename(columns={"filing_date": "year"})
    match = pd.read_csv(ML / "comparison_coverage.csv").rename(columns={"date": "year"})
    agree = pd.read_csv(ML / "agreement_by_year.csv").rename(columns={"date": "year"})
    return inputs.merge(match, on="year", how="outer").merge(
        agree[["year", "pearson", "spearman", "mae"]], on="year", how="outer").sort_values("year")


def summarize():
    labels = label_stats().set_index("Statistic")
    vol = volume_reconciliation()
    cov = coverage()
    train = cov[cov.year.isin(TRAIN_YEARS)]
    return {
        "itrade_ours": float(labels.loc["itrade", "ours"]),
        "itrade_paper": float(labels.loc["itrade", "paper"]),
        "impatient_minus_patient_ours": float(labels.loc["itrade_impatient", "ours"]
                                              - labels.loc["itrade_patient", "ours"]),
        "volume_ratio_min": float(vol.ratio.min()),
        "volume_ratio_max": float(vol.ratio.max()),
        "volume_pilot_rows": int(len(vol)),
        "min_input_coverage_train": float(train.fraction.min()),
        "min_input_coverage_year": int(train.loc[train.fraction.idxmin(), "year"]),
        "input_coverage_2019": float(cov.loc[cov.year == 2019, "fraction"].iloc[0]),
        "min_author_match": float(cov.match_fraction.min()),
        "min_yearly_pearson": float(cov.pearson.min()),
        "median_yearly_pearson": float(cov.pearson.median()),
        "tolerances": VALIDATION_TOLERANCES,
    }


def write_table(path):
    labels = label_stats()
    vol = volume_reconciliation()
    s = summarize()
    names = {"rows_per_event": "Stock-days per filing", "itrade": "Share of days with 13D trade",
             "itrade_patient": "  ... first 40 days (patient)", "itrade_impatient": "  ... last 20 days (impatient)",
             "vol_share": "Filer share of daily volume", "vol_share_patient": "  ... patient",
             "vol_share_impatient": "  ... impatient", "turn13d_mean_x100": r"13D turnover, mean ($\times 100$)",
             "turn13d_median_x100": r"13D turnover, median ($\times 100$)", "sell_share": "Share of 13D trades that are sells"}
    lines = [r"\begin{tabular}{lrrl}", r"\toprule", r"Check & Ours & Benchmark & Benchmark source \\", r"\midrule",
             r"\multicolumn{4}{l}{\textit{A. Rebuilt Schedule 13D labels (2005--2018) vs published statistics}} \\"]
    for r in labels.itertuples():
        src = r.Source.replace("_", r"\_").replace("~", r"$\sim$").replace("%", r"\%")
        lines.append(f"{names.get(r.Statistic, r.Statistic)} & {r.ours:.3f} & {r.paper:.3f} & {src} \\\\")
    lines += [r"\midrule", r"\multicolumn{4}{l}{\textit{B. TAQ consolidated volume vs CRSP daily volume (pilot days)}} \\"]
    for year, g in vol.groupby(vol.date.str[:4]):
        lines.append(f"Volume ratio {year} ({len(g)} stocks) & {g.ratio.min():.3f}--{g.ratio.max():.3f} & 1.000 & identity \\\\")
    lo, hi = VALIDATION_TOLERANCES["volume_ratio_band"]
    lines += [r"\midrule", r"\multicolumn{4}{l}{\textit{C. Coverage and agreement with the authors' posted ITI}} \\",
              f"Min.\\ label rows with model inputs, 2005--2018 & {s['min_input_coverage_train']:.3f} & "
              f"$\\geq$ {VALIDATION_TOLERANCES['min_input_coverage']:.2f} & tolerance \\\\",
              f"Min.\\ scored days found in authors' file & {s['min_author_match']:.3f} & "
              f"$\\geq$ {VALIDATION_TOLERANCES['min_author_match']:.2f} & tolerance \\\\",
              f"Min.\\ yearly Pearson, ours vs authors' ITI(13D) & {s['min_yearly_pearson']:.3f} & "
              f"$\\geq$ {VALIDATION_TOLERANCES['min_yearly_pearson']:.2f} & tolerance \\\\",
              f"Volume ratio band & {s['volume_ratio_min']:.3f}--{s['volume_ratio_max']:.3f} & {lo:.1f}--{hi:.1f} & tolerance \\\\",
              r"\bottomrule", r"\end{tabular}"]
    path.write_text("\n".join(lines) + "\n")


def plot(path):
    cov = coverage()
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.8))
    a.bar(cov.year, cov.label_rows, color="0.82", label="13D label rows")
    a.bar(cov.year, cov.rows_with_available_inputs, color="#1f5fbf", label="... with model inputs")
    a2 = a.twinx()
    a2.plot(cov.year, cov.fraction, color="#c0392b", marker="o", ms=3, label="Coverage share")
    a2.axhline(VALIDATION_TOLERANCES["min_input_coverage"], color="#c0392b", ls=":", lw=0.8)
    a2.set_ylim(0, 1.05)
    a2.set_ylabel("Share with inputs")
    a.set(title="(a) 13D label rows with complete model inputs", xlabel="Filing year", ylabel="Stock-days")
    h1, l1 = a.get_legend_handles_labels()
    h2, l2 = a2.get_legend_handles_labels()
    a.legend(h1 + h2, l1 + l2, fontsize=7, frameon=False, loc="upper right")
    b.plot(cov.year, cov.match_fraction, marker="o", ms=3, color="#1f5fbf", label="Scored days found in authors' file")
    b.plot(cov.year, cov.pearson, marker="o", ms=3, color="#c05a19", label="Pearson: ours vs authors' ITI(13D)")
    b.plot(cov.year, cov.spearman, marker="o", ms=3, ls="--", color="#c05a19", alpha=0.6, label="Spearman")
    b.axhline(VALIDATION_TOLERANCES["min_yearly_pearson"], color="#c05a19", ls=":", lw=0.8)
    b.set_ylim(0, 1.05)
    b.set(title="(b) Coverage and agreement with posted ITI", xlabel="Year")
    b.legend(fontsize=7, frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    write_table(REPORT / "validation_table.tex")
    plot(REPORT / "validation_coverage.png")
    s = summarize()
    (REPORT / "validation_summary.json").write_text(json.dumps(s, indent=2, default=lambda x: list(x)))
    print(json.dumps({k: v for k, v in s.items() if k != "tolerances"}, indent=2))


if __name__ == "__main__":
    main()
