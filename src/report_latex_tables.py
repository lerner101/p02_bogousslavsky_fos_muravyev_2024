"""LaTeX tables and number macros for reports/report.tex, from committed outputs.

Every statistic quoted in the report comes from this file's outputs:
_output/report/table{5,10,11}.tex (ours vs paper side by side) and
_output/report/stats.tex (\\newcommand macros for numbers used in the text).
Run after replication_scorecard.py and validation_exhibits.py.

Run: python src/report_latex_tables.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_values as pv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_output"
REPL = OUTPUT / "replication"
REPORT = OUTPUT / "report"


def tex_name(s):
    return s.replace("%", r"\%").replace("*", r"$\times$").replace("_", r"\_")


def regression_table(csv, paper, path, decimals=4):
    t = pd.read_csv(csv)
    t["column"] = t.column.astype(str)
    cols = [str(c) for c in paper]
    variables = list(dict.fromkeys(v for c in paper.values() for v in c))
    lines = [r"\begin{tabular}{l" + "rr" * len(cols) + "}", r"\toprule",
             " & " + " & ".join(rf"\multicolumn{{2}}{{c}}{{({c})}}" for c in cols) + r" \\",
             " & " + " & ".join(["Ours & Paper"] * len(cols)) + r" \\", r"\midrule"]
    for var in variables:
        coef, tstat = [tex_name(var)], [""]
        for c in cols:
            ours = t[(t.column == c) & (t.variable == var)]
            p = paper[int(c)].get(var)
            coef += [f"{ours.coef.iloc[0]:.{decimals}f}" if len(ours) else "",
                     f"{p[0]:.{decimals}f}" if p else ""]
            tstat += [f"({ours.t.iloc[0]:.2f})" if len(ours) else "", f"({p[1]:.2f})" if p else ""]
        lines += [" & ".join(coef) + r" \\", " & ".join(tstat) + r" \\"]
    obs = ["Obs."]
    for c in cols:
        o = t[(t.column == c) & (t.variable == "Obs.")]
        obs += [f"{int(o.coef.iloc[0]):,}" if len(o) else "", ""]
    lines += [r"\midrule", " & ".join(obs) + r" \\", r"\bottomrule", r"\end{tabular}"]
    path.write_text("\n".join(lines) + "\n")


def table11(path):
    t = pd.read_csv(REPL / "table11.csv")
    lines = [r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
             r" & \multicolumn{4}{c}{Raw return} & \multicolumn{4}{c}{FF4 alpha} \\",
             r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}",
             r"Sort variable & Low & High & H$-$L (ours) & H$-$L (paper) & Low & High & H$-$L (ours) & H$-$L (paper) \\",
             r"\midrule"]
    for name in pv.ITI_NAMES:
        g = t[t.measure == name].set_index("portfolio")
        hl = g.loc["H-L"]
        lines.append(
            f"{name} & {g.loc['Low', 'raw']*100:.2f} & {g.loc['High', 'raw']*100:.2f} & "
            f"{hl.raw*100:.2f} ({hl.raw_t:.1f}) & {pv.TABLE11_RAW[name][-1]*100:.2f} ({pv.TABLE11_RAW_HL_T[name]:.1f}) & "
            f"{g.loc['Low', 'alpha']*100:.2f} & {g.loc['High', 'alpha']*100:.2f} & "
            f"{hl.alpha*100:.2f} ({hl.alpha_t:.1f}) & {pv.TABLE11_ALPHA[name][-1]*100:.2f} ({pv.TABLE11_ALPHA_HL_T[name]:.1f}) \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    path.write_text("\n".join(lines) + "\n")


def stats(path):
    card = json.loads((REPORT / "scorecard.json").read_text())
    val = json.loads((REPORT / "validation_summary.json").read_text())
    perf = pd.read_csv(OUTPUT / "ml_model" / "model_performance.csv")
    pooled = perf[(perf["sample"] == "primary") & (perf.fold == "pooled")].iloc[0]
    agree = pd.read_csv(OUTPUT / "ml_model" / "agreement_overall.csv", index_col=0).iloc[:, 0]
    t10 = pd.read_csv(REPL / "table10.csv")
    t10["column"] = t10.column.astype(str)
    c1 = t10[(t10.column == "1") & (t10.variable == "ITI(13D)")].iloc[0]
    t11 = pd.read_csv(REPL / "table11.csv").set_index(["measure", "portfolio"])
    f4a = pd.read_csv(REPL / "figure4a.csv").set_index("day")
    ia5 = pd.read_csv(REPL / "figureIA5.csv").set_index("day")
    f1 = pd.read_csv(REPL / "figure1.csv")
    macros = {
        "ScoreScored": card["scored"], "ScorePassed": card["passed"],
        "ScoreBand": f"{card['ratio_band']:g}",
        "TrainRows": f"{int(pooled.rows):,}", "ModelAUC": f"{pooled.roc_auc:.3f}",
        "PaperAUC": f"{pv.IA6_XGB['roc_auc']:.3f}",
        "AgreePearson": f"{agree['pearson']:.2f}", "AgreeRows": f"{int(agree['rows']):,}",
        "AgreeStocks": f"{int(agree['stocks']):,}",
        "TenCoef": f"{c1.coef:.4f}", "TenT": f"{c1.t:.2f}",
        "ElevenAlpha": f"{t11.loc[('ITI(13D)', 'H-L'), 'alpha']*100:.2f}",
        "ElevenAlphaT": f"{t11.loc[('ITI(13D)', 'H-L'), 'alpha_t']:.1f}",
        "ImpAlpha": f"{t11.loc[('ITI(impatient)', 'H-L'), 'alpha']*100:.2f}",
        "FourDayZero": f"{f4a.loc[0, 'coef']:.3f}", "FourDayZeroPaper": f"{dict(zip(pv.DAYS, pv.FIG4A))[0]:.3f}",
        "IAFiveDayOne": f"{ia5.loc[1, 'coef']:.3f}", "IAFiveEvents": f"{int(ia5.n_events.iloc[0]):,}",
        "FigOneIti": f"{f1.iti_adjusted_r2.mean():.3f}", "FigOneCtrl": f"{f1.controls_adjusted_r2.mean():.3f}",
        "FigOnePaperIti": f"{f1.paper_iti_adjusted_r2.mean():.3f}",
        "ItradeOurs": f"{val['itrade_ours']:.3f}", "ItradePaper": f"{val['itrade_paper']:.3f}",
        "VolRatioMin": f"{val['volume_ratio_min']:.3f}",
        "MinCoverage": f"{val['min_input_coverage_train']:.2f}",
        "MinCoverageYear": val["min_input_coverage_year"],
        "MinPearson": f"{val['min_yearly_pearson']:.2f}",
    }
    path.write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items()))


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    regression_table(REPL / "table5.csv", pv.TABLE5, REPORT / "table5.tex", decimals=3)
    regression_table(REPL / "table10.csv", pv.TABLE10, REPORT / "table10.tex")
    table11(REPORT / "table11.tex")
    stats(REPORT / "stats.tex")
    print("Wrote report tables to", REPORT)


if __name__ == "__main__":
    main()
