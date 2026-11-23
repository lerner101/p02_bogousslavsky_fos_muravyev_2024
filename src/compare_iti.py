"""Compare project ITI with original posted scores on identical stock-days.

Output is confined to _output/ml_model; existing replication exhibits are kept.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from regress import fe_ols
from replicate_exhibits import earnings_events, event_offsets
from train_iti import PAPER, metrics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data/derived/ml_model"
OUT = ROOT / "_output/ml_model"


def agreement(d):
    x, y = d["project"], d["author"]
    return pd.Series({"rows": len(d), "stocks": d.permno.nunique(), "mae": (x-y).abs().mean(),
                      "rmse": np.sqrt(((x-y)**2).mean()), "pearson": x.corr(y),
                      "spearman": x.corr(y, method="spearman"),
                      "project_mean": x.mean(), "author_mean": y.mean()})


def finish(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=160)
    plt.close(fig)


def earnings_comparison(matched):
    stocks = matched.permno.unique().tolist()
    daily = pd.concat([pd.read_parquet(ROOT / f"_data/wrds/crsp_daily/{y}.parquet",
                      columns=["permno", "date", "ret", "vol"], filters=[("permno", "in", stocks)])
                       for y in range(2004, 2020)], ignore_index=True)
    # WRDS stores nullable Int64, while earnings_events constructs numpy int64.
    # merge_asof requires identical identifier dtypes on both sides.
    daily["permno"] = daily.permno.astype("int64")
    daily = daily.sort_values(["permno", "date"]).reset_index(drop=True)
    events = earnings_events(daily)
    events = events[events.day0.between("2005-01-01", "2019-07-31")]
    indicators, _ = event_offsets(daily, events)
    names = [f"day_{k}" for k in range(-10, 11)]
    daily[names] = indicators
    d = daily.merge(matched, on=["permno", "date"], validate="one_to_one")
    active = [c for c in names if d[c].sum() > 0]
    if len(active) != len(names) or d.permno.nunique() < 2:
        return "Insufficient common-sample event coverage for an earnings regression."
    rows = []
    fig, ax = plt.subplots(figsize=(8, 4))
    for measure in ["project", "author"]:
        table, stats = fe_ols(d, measure, names, fe="permno", cluster=("permno", "date"))
        table["day"] = range(-10, 11)
        table["measure"] = measure
        table["nobs"] = stats["nobs"]
        rows.append(table)
        ax.errorbar(table.day, table.coef, yerr=1.96*table.se, marker="o", markersize=3,
                    label=measure, capsize=2)
    ax.axvline(0, color="gray", ls="--")
    ax.axhline(0, color="gray", lw=0.5)
    ax.set_xticks(range(-10, 11, 2))
    ax.set(xlabel="Trading days relative to earnings", ylabel="ITI coefficient relative to non-event days",
           title="Earnings: project and original author ITI on the same stock-days")
    ax.legend()
    finish(fig, "earnings_comparison.png")
    pd.concat(rows).to_csv(OUT / "earnings_comparison.csv", index=False)
    day_zero = {t.measure.iloc[0]: float(t.loc["day_0", "coef"]) for t in rows}
    return (f"Earnings regression: {len(d):,} common stock-days, {d.permno.nunique()} stocks; stock FE and stock/date clustered intervals. "
            f"Day-zero coefficients relative to non-event days: project {day_zero['project']:.4f}, author {day_zero['author']:.4f} ITI units.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model_manifest = json.loads((DATA / "model_manifest.json").read_text())
    scores = pd.read_parquet(DATA / "scores.parquet").rename(columns={"ITI(13D)": "project"})
    base = scores[scores.date.le("2019-07-31") & ~scores.in_training_window].copy()
    stocks = base.permno.unique().tolist()
    paths = sorted((ROOT / "_data/public/iti_original_through_2019").glob("year=*/*.parquet"))
    authors = pd.concat([pd.read_parquet(p, columns=["permno", "date", "ITI(13D)"],
                        filters=[("permno", "in", stocks)]) for p in paths], ignore_index=True)
    authors = authors.rename(columns={"ITI(13D)": "author"})
    if authors.duplicated(["permno", "date"]).any():
        raise ValueError("Original author series contains duplicate stock-days")
    joined = base.merge(authors, on=["permno", "date"], how="left", validate="one_to_one")
    coverage = joined.groupby(joined.date.dt.year).agg(project_rows=("project", "size"), author_matches=("author", "count"))
    coverage["match_fraction"] = coverage.author_matches / coverage.project_rows
    coverage.to_csv(OUT / "comparison_coverage.csv")
    matched = joined.dropna(subset=["author", "project"])
    if matched.empty:
        raise ValueError("No original author scores overlap the acquired eligible stock-days")
    matched[["permno", "date", "project", "author"]].to_parquet(DATA / "matched_scores.parquet", index=False)
    annual = matched.groupby(matched.date.dt.year).apply(agreement, include_groups=False)
    annual.to_csv(OUT / "agreement_by_year.csv")
    agreement(matched).to_csv(OUT / "agreement_overall.csv", header=["value"])
    fig, ax = plt.subplots(figsize=(6, 5))
    h = ax.hexbin(matched.author, matched.project, gridsize=55, bins="log", mincnt=1)
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set(xlabel="Original author ITI(13D)", ylabel="Project ITI(13D)", xlim=(0, 1), ylim=(0, 1),
           title="Score agreement outside reconstructed training windows")
    fig.colorbar(h, ax=ax, label="Matched stock-day count (log scale)")
    finish(fig, "score_agreement.png")
    fig, ax = plt.subplots(figsize=(7, 4))
    for c in ["project", "author"]:
        ax.hist(matched[c], bins=np.linspace(0, 1, 41), density=True, histtype="step", linewidth=1.5, label=c)
    ax.set(xlabel="ITI(13D)", ylabel="Density", title="ITI distributions on identical stock-days")
    ax.legend()
    finish(fig, "score_distributions.png")
    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    annual[["project_mean", "author_mean"]].plot(ax=axes[0], marker="o")
    annual[["pearson", "spearman"]].plot(ax=axes[1], marker="o")
    axes[0].set_ylabel("Mean ITI")
    axes[1].set(ylabel="Score correlation", xlabel="Year")
    finish(fig, "annual_comparison.png")
    oof = pd.read_parquet(DATA / "oof_predictions.parquet")
    if scores.duplicated(["permno", "date"]).any() or oof.duplicated(["filing", "date"]).any():
        raise ValueError("Duplicate score or filing-day prediction keys")
    if oof.groupby("filing").outer_fold.nunique().max() != 1:
        raise ValueError("A filing crosses outer evaluation folds")
    if oof.groupby(["permno", "date"]).outer_fold.nunique().max() != 1:
        raise ValueError("A stock-day crosses outer evaluation folds")
    if not scores.project.between(0, 1).all() or not oof["ITI(13D)"].between(0, 1).all():
        raise ValueError("Predictions are missing or outside [0, 1]")
    validation = {"unique_stock_day_scores": True, "unique_filing_day_predictions": True,
                  "filings_kept_within_fold": True, "stock_days_kept_within_fold": True,
                  "bounded_finite_scores": True, "scored_rows": len(scores), "heldout_rows": len(oof),
                  "comparison_excludes_reconstructed_training_windows": not bool(matched.in_training_window.any()),
                  "score_min": float(scores.project.min()), "score_max": float(scores.project.max())}
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2))
    annual_oof = oof.groupby(oof.date.dt.year).apply(lambda x: pd.Series(metrics(x.itrade, x["ITI(13D)"])), include_groups=False)
    annual_oof.to_csv(OUT / "oof_metrics_by_year.csv")
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.5))
    pooled = metrics(oof.itrade, oof["ITI(13D)"])
    for ax, (name, published) in zip(axes, PAPER.items()):
        ax.bar(["Project OOF", "Paper IA.6"], [pooled[name], published], color=["#2369a0", "#999999"])
        ax.set(title=name, ylim=(0, 1))
    finish(fig, "model_performance.png")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    for value, label in [(0, "No disclosed trade"), (1, "Disclosed trade")]:
        axes[0].hist(oof.loc[oof.itrade.eq(value), "ITI(13D)"], bins=30, density=True, histtype="step", label=label)
    axes[0].set(xlabel="Held-out ITI", ylabel="Density")
    axes[0].legend()
    axes[1].plot(annual_oof.index, annual_oof.roc_auc, marker="o")
    axes[1].axhline(PAPER["roc_auc"], color="gray", ls="--", label="Paper IA.6 pooled AUC")
    axes[1].set(xlabel="Year", ylabel="Held-out ROC AUC")
    axes[1].legend()
    finish(fig, "heldout_diagnostics.png")
    event_note = earnings_comparison(matched)
    performance = pd.read_csv(OUT / "model_performance.csv")
    sensitivity = performance[performance.fold.astype(str).eq("pooled")]
    report = ["# Project ITI(13D) comparison", "",
              f"Training sample: {int(model_manifest['train_rows']):,} filing-day observations from {int(model_manifest['train_filings']):,} filings (2005–2018).",
              f"Scored sample: {len(scores):,} eligible stock-days (2005–2019).",
              f"Common comparison sample: {len(matched):,} stock-days, {matched.permno.nunique()} stocks.",
              "", "Scores use the full 41-feature specification. Training uses reconstructed 2005–2018 labels and nested calendar-fold evaluation.",
              "Only odd-lot count may be missing and is handled natively by XGBoost; the other 40 features must be observed. This approved choice differs from the original complete-case plan.",
              "Author scores are the original vintage through July 2019. Reconstructed training windows are excluded from score agreement.",
              "Author training-window recovery is approximate; score agreement is a replication diagnostic, not independent ground truth.",
              "", "## Agreement on matched stock-days", "", agreement(matched).to_frame("value").to_markdown(),
              "", "## Held-out performance", "", pd.DataFrame({"project": pooled, "paper_IA6": PAPER}).to_markdown(),
              "", "## Author-window training sensitivity", "", sensitivity.to_markdown(index=False),
              "", event_note, "", "The bounded scoring sample contains training-history stocks and ten long-coverage scoring stocks; it is not the full stock universe.",
              "Paper and project training labels, sample periods, and undocumented implementation choices differ; matching published performance is not an acceptance criterion."]
    (OUT / "comparison.md").write_text("\n".join(report) + "\n")
    (OUT / "comparison.json").write_text(json.dumps({"rows": len(matched), "stocks": matched.permno.nunique(), "oof": pooled}, indent=2, default=float))


if __name__ == "__main__":
    main()
