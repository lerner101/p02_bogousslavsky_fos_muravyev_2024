"""Score every committed replication output against the published values.

Our sample is shorter (2005-2019 vs 1993-2019), our 13D labels are rebuilt from
filing text, and our ITI(13D) is trained on that rebuilt sample, so exact
equality is not the goal. The acceptance rule is fixed here, before results are
inspected, and is the same for every exhibit:

* MAGNITUDE: an estimate passes if it has the same sign as the paper and lies
  within a factor of ``RATIO_BAND`` of it (ours / paper in [1/3, 3]).
* INSIGNIFICANT IN THE PAPER: when the paper's |t| < 1.96 the point estimate is
  noise, so we only require that ours is also insignificant or has the same sign.
* NOT COMPARABLE: rows whose units differ by construction are reported but not
  scored (listed in ``UNIT_MISMATCH``).

Reads only files committed under _output/, so it runs from a clean clone and in
CI. Writes _output/report/scorecard.csv, scorecard.tex and scorecard.png.

Run: python src/replication_scorecard.py
"""

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

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_output"
REPL = OUTPUT / "replication"
REPORT = OUTPUT / "report"

RATIO_BAND = 3.0
T_CRIT = 1.96
# ret*rvol: our realized volatility (WRDS ivol_t, second-by-second) is on a
# different scale from the paper's 30-minute realized volatility.
UNIT_MISMATCH = {("Table 5", "col 3: ret*rvol")}


def judge(ours, paper, paper_t=None, ours_t=None):
    """Apply the fixed acceptance rule; return (status, ratio)."""
    if ours is None or paper is None or np.isnan(ours) or np.isnan(paper):
        return "missing", np.nan
    ratio = ours / paper if paper != 0 else np.nan
    if paper_t is not None and abs(paper_t) < T_CRIT:
        ok = np.sign(ours) == np.sign(paper) or (ours_t is not None and abs(ours_t) < T_CRIT)
        return ("pass" if ok else "fail"), ratio
    ok = np.sign(ours) == np.sign(paper) and 1 / RATIO_BAND <= ratio <= RATIO_BAND
    return ("pass" if ok else "fail"), ratio


def row(exhibit, item, ours, paper, paper_t=None, ours_t=None):
    status, ratio = judge(ours, paper, paper_t, ours_t)
    if (exhibit, item) in UNIT_MISMATCH:
        status = "not comparable"
    return {"exhibit": exhibit, "item": item, "ours": ours, "paper": paper,
            "ours_t": ours_t, "paper_t": paper_t, "ratio": ratio, "status": status}


def regression_rows(exhibit, csv, paper_table):
    t = pd.read_csv(csv)
    t["column"] = t.column.astype(str)
    rows = []
    for col, coefs in paper_table.items():
        sub = t[t.column == str(col)].set_index("variable")
        for var, (p_coef, p_t) in coefs.items():
            if var in sub.index:
                rows.append(row(exhibit, f"col {col}: {var}", sub.loc[var, "coef"], p_coef,
                                p_t, sub.loc[var, "t"]))
    return rows


def table11_rows():
    t = pd.read_csv(REPL / "table11.csv")
    rows = []
    for name in pv.ITI_NAMES:
        hl = t[(t.measure == name) & (t.portfolio == "H-L")].iloc[0]
        rows.append(row("Table 11", f"{name} H-L raw", hl.raw, pv.TABLE11_RAW[name][-1],
                        pv.TABLE11_RAW_HL_T[name], hl.raw_t))
        rows.append(row("Table 11", f"{name} H-L FF4 alpha", hl.alpha, pv.TABLE11_ALPHA[name][-1],
                        pv.TABLE11_ALPHA_HL_T[name], hl.alpha_t))
    return rows


def event_rows(exhibit, csv, group, paper, days=(-2, -1, 0, 1, 2), day_col="day", coef_col="coef"):
    t = pd.read_csv(csv)
    if "group" in t:
        t = t[t.group == group]
    t = t.set_index(day_col)[coef_col]
    all_days = pv.NEWS_DAYS if exhibit == "Figure 4(c)" else pv.DAYS
    ref = dict(zip(all_days, paper))
    label = f"{group} " if group not in ("all", None) else ""
    return [row(exhibit, f"{label}day {d:+d}", t.get(d, np.nan), ref[d]) for d in days]


def figure1_rows():
    f = pd.read_csv(REPL / "figure1.csv")
    return [
        row("Figure 1", "mean annual adj. R2, ITI", f.iti_adjusted_r2.mean(), f.paper_iti_adjusted_r2.mean()),
        row("Figure 1", "mean annual adj. R2, controls", f.controls_adjusted_r2.mean(),
            f.paper_controls_adjusted_r2.mean()),
        row("Figure 1", "share of years ITI beats controls",
            (f.iti_adjusted_r2 > f.controls_adjusted_r2).mean(),
            (f.paper_iti_adjusted_r2 > f.paper_controls_adjusted_r2).mean()),
    ]


def figure2_rows():
    f = pd.read_csv(REPL / "figure2.csv")
    rows = []
    for feat, label in [("svol", "volume"), ("rvol", "volatility")]:
        g = f[f.feature == feat].dropna(subset=["paper_mean_iti"])
        ours = g.mean_iti.iloc[-1] - g.mean_iti.iloc[0]
        paper = g.paper_mean_iti.iloc[-1] - g.paper_mean_iti.iloc[0]
        rows.append(row("Figure 2", f"ITI change across {label} range", ours, paper))
    return rows


def model_rows():
    perf = pd.read_csv(OUTPUT / "ml_model" / "model_performance.csv")
    pooled = perf[(perf["sample"] == "primary") & (perf.fold == "pooled")].iloc[0]
    # AUC above a coin flip, so the ratio measures discriminating power.
    return [row("Table IA.6", "ROC AUC minus 0.5", pooled.roc_auc - 0.5, pv.IA6_XGB["roc_auc"] - 0.5)]


def build():
    rows = []
    rows += regression_rows("Table 5", REPL / "table5.csv", pv.TABLE5)
    rows += regression_rows("Table 10", REPL / "table10.csv", pv.TABLE10)
    rows += table11_rows()
    rows += figure1_rows()
    rows += figure2_rows()
    rows += model_rows()
    rows += event_rows("Figure 4(a)", REPL / "figure4a.csv", "all", pv.FIG4A)
    rows += event_rows("Figure 4(b)", REPL / "figure4b.csv", "large", pv.FIG4B_LARGE, days=(-1, 0, 1))
    rows += event_rows("Figure 4(b)", REPL / "figure4b.csv", "small", pv.FIG4B_SMALL, days=(-1, 0, 1))
    rows += event_rows("Figure 4(c)", OUTPUT / "figure_04c_preview.csv", None, pv.FIG4C,
                       days=(-1, 0, 1), day_col="event_day", coef_col="coefficient")
    rows += event_rows("Figure IA.5", REPL / "figureIA5.csv", "all", pv.FIGIA5, days=(-1, 0, 1, 5))
    return pd.DataFrame(rows)


def fmt(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    return f"{x:.2f}" if abs(x) >= 10 else f"{x:.4f}"


def write_latex(card, path):
    # longtable so the scorecard can break across pages; the report defines
    # \ScorecardCaption before \input-ing this file.
    header = r"Exhibit & Item & Ours & Paper & Ours/Paper & Status \\"
    lines = [r"\begin{longtable}{llrrrl}", r"\ScorecardCaption \\", r"\toprule", header, r"\midrule",
             r"\endfirsthead", r"\toprule", header, r"\midrule", r"\endhead"]
    for exhibit, group in card.groupby("exhibit", sort=False):
        for i, r in enumerate(group.itertuples()):
            name = exhibit if i == 0 else ""
            item = r.item.replace("%", r"\%").replace("_", r"\_").replace("*", r"$\times$")
            lines.append(f"{name} & {item} & {fmt(r.ours)} & {fmt(r.paper)} & "
                         f"{'' if np.isnan(r.ratio) else f'{r.ratio:.2f}'} & {r.status} \\\\")
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines.append(r"\end{longtable}")
    path.write_text("\n".join(lines) + "\n")


def plot(card, path):
    scored = card[card.status.isin(["pass", "fail"]) & card.ratio.notna()].copy()
    scored["label"] = scored.exhibit + " · " + scored.item
    scored = scored.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 0.22 * len(scored) + 1.2))
    y = np.arange(len(scored))
    ratio = scored.ratio.clip(-RATIO_BAND * 2, RATIO_BAND * 2)
    colors = np.where(scored.status == "pass", "#1f5fbf", "#c0392b")
    ax.axvspan(1 / RATIO_BAND, RATIO_BAND, color="#1f5fbf", alpha=0.08, label="Tolerance band (×1/3 to ×3)")
    ax.axvline(1, color="0.4", lw=0.8)
    ax.axvline(0, color="0.7", lw=0.6, ls=":")
    ax.scatter(ratio, y, c=colors, s=18, zorder=3)
    ax.set_yticks(y, scored.label, fontsize=7)
    ax.set_xlabel("Our estimate ÷ paper estimate (clipped at ±6)")
    ax.set_title("Replication scorecard: blue = within tolerance, red = outside", fontsize=10)
    ax.legend(fontsize=7, loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def summary(card):
    scored = card[card.status.isin(["pass", "fail"])]
    return {"scored": int(len(scored)), "passed": int((scored.status == "pass").sum()),
            "by_exhibit": {k: {"scored": int(len(g)), "passed": int((g.status == "pass").sum())}
                           for k, g in scored.groupby("exhibit", sort=False)},
            "ratio_band": RATIO_BAND}


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    card = build()
    card.to_csv(REPORT / "scorecard.csv", index=False)
    write_latex(card, REPORT / "scorecard.tex")
    plot(card, REPORT / "scorecard.png")
    s = summary(card)
    (REPORT / "scorecard.json").write_text(json.dumps(s, indent=2))
    print(f"Scorecard: {s['passed']}/{s['scored']} comparisons within tolerance")


if __name__ == "__main__":
    main()
