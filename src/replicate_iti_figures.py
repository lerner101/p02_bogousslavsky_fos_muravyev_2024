"""Build paper Figures 1–3 on the project's saved Schedule 13D training sample."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter
from sklearn.tree import DecisionTreeRegressor

from build_iti_features import sha256
from iti_features import ALLOW_MISSING, FEATURES, REQUIRED_FEATURES, link_indicators

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data/derived/ml_model"
WRDS = ROOT / "_data/wrds"
OUT = ROOT / "_output/replication"
BENCHMARKS = ROOT / "data_manual/iti_figure_benchmarks"
KEY = ["permno", "date"]
SCORE = "ITI(13D)"
# Caption specification is primary; retain archived-script specification as sensitivity.
CONTROLS8 = ["es", "lambda", "depth", "rvol", "turn", "oi", "abs_oi", "ret"]
CONTROLS = ["es", "pi", *CONTROLS8[1:]]
RAW = ["es", "pi", "lambda1", "rvol", "svol", "svol_imb", "ret"]
DEPTH = ["bestofrdepth_share_tw", "bestbiddepth_share_tw"]
FEATURE_LABELS = {"svol": "Volume", "rvol": "Volatility", "prc": "Price"}


def paper_reference(number):
    """Published numerical comparisons only; never used in estimation."""
    return pd.read_csv(BENCHMARKS / f"figure{number}.csv")


def read_parquet(path, **kwargs):
    if not path.is_file():
        raise SystemExit(f"Missing figure input: {path}. Use the saved files from the completed ML run and its WRDS extracts.")
    return pd.read_parquet(path, **kwargs)


def heldout_predictions():
    columns = ["filing", *KEY, "itrade", SCORE]
    data = read_parquet(DATA / "oof_predictions.parquet", columns=columns)
    if (data.empty or data[columns].isna().any().any()
            or data.duplicated(["filing", *KEY]).any()
            or not data.itrade.isin([0, 1]).all() or not data[SCORE].between(0, 1).all()):
        raise ValueError("Invalid or empty held-out filing-day predictions")
    return data.sort_values([*KEY, "filing"]).reset_index(drop=True)


def figure1_controls(predictions):
    raw = read_parquet(DATA / "raw_features.parquet", columns=[*KEY, *RAW])
    # Use the same stock universe as the completed feature build for link disambiguation.
    stocks = raw.permno.astype(int).unique().tolist()
    stock_days = predictions[KEY].drop_duplicates()
    relevant = raw.merge(stock_days, on=KEY, validate="one_to_one")
    frames = []
    for year, needed in stock_days.groupby(stock_days.date.dt.year):
        filters = [("permno", "in", stocks)]
        shares = read_parquet(WRDS / f"crsp_daily/{year}.parquet", columns=[*KEY, "shrout"],
                              filters=[("permno", "in", needed.permno.astype(int).unique().tolist())])
        links = read_parquet(WRDS / f"crsp_taq_links/{year}.parquet",
                              columns=[*KEY, "sym_root", "sym_suffix"], filters=filters)
        iid = read_parquet(WRDS / f"intraday_indicators/{year}.parquet",
                            columns=["date", "sym_root", "sym_suffix", *DEPTH])
        depth = link_indicators(links, iid)[[*KEY, *DEPTH]]
        frames.append(needed.merge(shares, on=KEY, how="left", validate="one_to_one")
                      .merge(depth, on=KEY, how="left", validate="one_to_one"))
    controls = pd.concat(frames, ignore_index=True).merge(relevant, on=KEY, how="left", validate="one_to_one")
    for column in ["shrout", *DEPTH, *RAW]:
        controls[column] = pd.to_numeric(controls[column], errors="coerce").astype("float64")
    shares_outstanding = controls.shrout.where(controls.shrout.gt(0)) * 1000
    controls["depth"] = (controls[DEPTH[0]] + controls[DEPTH[1]]) / shares_outstanding
    controls["turn"] = controls.svol / shares_outstanding
    controls["oi"] = controls.svol_imb / shares_outstanding
    controls["abs_oi"] = controls.oi.abs()
    controls["lambda"] = controls.lambda1 * 1000
    return controls[[*KEY, *CONTROLS]].replace([np.inf, -np.inf], np.nan)


def adjusted_r2(sample, predictors):
    y = sample.itrade.to_numpy(dtype=float)
    if len(y) <= len(predictors) + 1 or sample.itrade.nunique() < 2:
        return np.nan
    x = sample[predictors].to_numpy(dtype=float, copy=True)
    x -= x.mean(axis=0)
    scale = x.std(axis=0)
    x /= np.where(scale > 0, scale, 1)
    design = np.column_stack([np.ones(len(y)), x])
    coef, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coef
    centered = y - y.mean()
    return 1 - (residual @ residual) / (centered @ centered) * (len(y) - 1) / (len(y) - rank)


def annual_stability(predictions, controls):
    data = predictions.merge(controls, on=KEY, how="left", validate="many_to_one")
    data["year"] = data.date.dt.year
    matched = data.dropna(subset=CONTROLS).copy()
    lower, upper = matched[CONTROLS].quantile([0.0005, 0.9995]).to_numpy()
    matched[CONTROLS] = matched[CONTROLS].clip(lower, upper, axis=1)
    rows = []
    by_year = dict(list(matched.groupby("year")))
    for year, group in data.groupby("year"):
        sample = by_year.get(year, matched.iloc[:0])
        rows.append({"year": year, "heldout_days": len(group), "common_days": len(sample),
                     "filings": sample.filing.nunique(), "trade_days": int(sample.itrade.sum()),
                     "iti_adjusted_r2": adjusted_r2(sample, [SCORE]),
                     "controls_adjusted_r2": adjusted_r2(sample, CONTROLS),
                     "controls8_adjusted_r2": adjusted_r2(sample, CONTROLS8)})
    result = pd.DataFrame(rows)
    if not result[["iti_adjusted_r2", "controls_adjusted_r2"]].notna().all(axis=1).any():
        raise ValueError("Figure 1 has no year with enough common observations and variation for both regressions")
    return result


def save_figure(fig, number, values):
    values.to_csv(OUT / f"figure{number}.csv", index=False)
    fig.savefig(OUT / f"figure{number}.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def figure1(predictions):
    result = annual_stability(predictions, figure1_controls(predictions))
    paper = paper_reference(1)[["year", "iti_adjusted_r2", "controls_adjusted_r2"]].rename(
        columns={"iti_adjusted_r2": "paper_iti_adjusted_r2", "controls_adjusted_r2": "paper_controls_adjusted_r2"})
    result = result.merge(paper, on="year", how="left", validate="one_to_one")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(result.year, result.iti_adjusted_r2, marker="o", color="#1f5fbf", label="Project: held-out ITI")
    ax.plot(result.year, result.controls_adjusted_r2, marker="o", color="#c05a19", label="Project: nine controls")
    ax.plot(result.year, result.paper_iti_adjusted_r2, ls="--", color="#1f5fbf", label="Paper: ITI (digitized)")
    ax.plot(result.year, result.paper_controls_adjusted_r2, ls="--", color="#c05a19", label="Paper: controls (digitized)")
    ax.set(title="Figure 1 · Annual explanatory power", xlabel="Stock-day year", ylabel="Adjusted $R^2$")
    ax.set_xticks(result.year.iloc[::2])
    ax.axhline(0, color="0.75", linewidth=0.7)
    ax.legend(frameon=False)
    fig.text(.5, .015, "Published curves are approximate digitizations; project regressions use a common sample.\n"
             "Nine-control caption specification is primary; eight-control sensitivity is exported in the CSV.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .085, 1, 1))
    save_figure(fig, 1, result)


def fitted_sample(predictions):
    path = DATA / "model_manifest.json"
    if not path.is_file():
        raise SystemExit(f"Missing figure input: {path}. Use the manifest from the completed ML run.")
    manifest = json.loads(path.read_text())
    if (manifest["feature_order"] != FEATURES or manifest["allow_missing"] != ALLOW_MISSING
            or manifest["train_rows"] != len(predictions)):
        raise ValueError("Model manifest and held-out predictions do not match the figure inputs")
    path = DATA / "features.parquet"
    features = read_parquet(path, columns=[*KEY, *FEATURES])
    if sha256(path) != manifest["features_sha256"]:
        raise ValueError("Use the standardized features saved with this model")
    data = predictions.merge(features, on=KEY, how="left", validate="many_to_one", indicator=True)
    if (not data["_merge"].eq("both").all() or not np.isfinite(data[REQUIRED_FEATURES]).all().all()
            or np.isinf(data[ALLOW_MISSING]).any().any()):
        raise ValueError("Held-out filing-days must match valid standardized features")
    return data.drop(columns="_merge"), manifest


def partial_dependence(model, features, feature, bins=100, bounds=None):
    observed = features[feature]
    lower, upper = bounds if bounds is not None else observed.quantile([0.01, 0.99])
    if lower == upper:
        lower, upper = observed.min(), observed.max()
    if lower == upper:
        raise ValueError(f"Figure 2 needs variation in {feature}")
    edges = np.linspace(lower, upper, bins + 1)
    grid = (edges[:-1] + edges[1:]) / 2
    counts, _ = np.histogram(observed, bins=edges)
    synthetic = features.copy()
    mean_iti = []
    for value in grid:
        synthetic[feature] = np.float32(value)
        mean_iti.append(model.predict_proba(synthetic)[:, 1].mean(dtype=np.float64))
    return pd.DataFrame({"feature": feature, "standardized_value": grid, "mean_iti": mean_iti,
                         "density": counts / (len(observed) * np.diff(edges)),
                         "bin_left": edges[:-1], "bin_right": edges[1:], "bin_count": counts,
                         "filing_days": len(observed),
                         "observed_fraction_outside_display": float((~observed.between(lower, upper)).mean())})


def figure2(data, manifest):
    from xgboost import XGBClassifier

    path = DATA / "iti_13d.json"
    if not path.is_file():
        raise SystemExit(f"Missing figure input: {path}. Use the model from the completed ML run.")
    if sha256(path) != manifest["model_sha256"]:
        raise ValueError("Use the fitted model saved with this manifest")
    model = XGBClassifier()
    model.load_model(path)
    model.set_params(n_jobs=2)
    fig, axes = plt.subplots(2, 1, figsize=(9, 10), layout="constrained")
    paper = paper_reference(2)
    results = []
    for ax, feature in zip(axes, ["svol", "rvol"]):
        label = FEATURE_LABELS[feature]
        published = paper[paper.feature.eq(feature)].sort_values("standardized_value")
        bounds = (published.standardized_value.min(), published.standardized_value.max())
        result = partial_dependence(model, data[FEATURES], feature, bounds=bounds)
        result["paper_mean_iti"] = np.interp(result.standardized_value, published.standardized_value, published.mean_iti, left=np.nan, right=np.nan)
        result["paper_density"] = np.interp(result.standardized_value, published.standardized_value, published.density, left=np.nan, right=np.nan)
        results.append(result)
        distribution = ax.twinx()
        distribution.bar(result.bin_left, result.density, width=result.bin_right - result.bin_left,
                         align="edge", color="0.87", linewidth=0, label="Project density")
        distribution.plot(published.standardized_value, published.density, color="0.40", ls=":", label="Paper density (digitized)")
        distribution.set_ylabel("Density per standardized unit", color="0.35")
        ax.set_zorder(distribution.get_zorder() + 1)
        ax.patch.set_visible(False)
        ax.plot(result.standardized_value, result.mean_iti, color="#1f5fbf", lw=2, label="Project ITI")
        ax.plot(published.standardized_value, published.mean_iti, color="#c05a19", ls="--", label="Paper ITI (digitized)")
        ax.set(title=f"Partial dependence of ITI on {label.lower()}",
               xlabel=f"Standardized {label.lower()}", ylabel="Predicted ITI")
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
        ax.set_xlim(bounds)
        handles, labels = ax.get_legend_handles_labels()
        dh, dl = distribution.get_legend_handles_labels()
        ax.legend(handles + dh, labels + dl, loc="best", fontsize=8, framealpha=.9)
        outside = result.observed_fraction_outside_display.iloc[0]
        ax.text(.99, .02, f"Project observations outside displayed range: {outside:.1%}",
                transform=ax.transAxes, ha="right", fontsize=8,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": .85})
    fig.suptitle("Figure 2 · Partial dependence and feature distributions\nPublished curves/densities are approximate digitizations", fontsize=12)
    save_figure(fig, 2, pd.concat(results, ignore_index=True))


def fit_surrogate(data):
    # Require at least 1% of the sample per leaf to discourage very small splits.
    model = DecisionTreeRegressor(max_depth=3, min_samples_leaf=0.01, random_state=0)
    model.fit(data[FEATURES], data[SCORE])
    return model


def validate_tree(nodes):
    """Check topology and printed counts, without altering paper rounding."""
    if nodes.node.duplicated().any() or 0 not in nodes.node.to_numpy():
        raise ValueError("Tree needs unique node IDs and root 0")
    indexed = nodes.set_index("node")
    seen = set()

    def visit(node, depth=0):
        if node in seen or node not in indexed.index or depth > 3:
            raise ValueError("Invalid, cyclic or overly deep tree")
        seen.add(node)
        r = indexed.loc[node]
        if r.filing_days <= 0 or not 0 <= r.mean_iti <= 1 or not np.isfinite(r.mse) or r.mse < -1e-10:
            raise ValueError("Invalid tree sample count, mean or MSE")
        if pd.isna(r.feature):
            if pd.notna(r.left_child) or pd.notna(r.right_child):
                raise ValueError("Leaf has children")
            return int(r.filing_days)
        if not np.isfinite(r.threshold) or pd.isna(r.left_child) or pd.isna(r.right_child):
            raise ValueError("Split needs threshold and two children")
        total = visit(int(r.left_child), depth+1) + visit(int(r.right_child), depth+1)
        if total != r.filing_days:
            raise ValueError("Child sample counts do not sum to parent")
        return total

    total = visit(0)
    if len(seen) != len(nodes):
        raise ValueError("Tree contains disconnected nodes")
    return total


def draw_tree(ax, nodes, title):
    validate_tree(nodes)
    indexed = nodes.set_index("node")
    positions = {}
    leaf_count = int(nodes.feature.isna().sum())
    next_leaf = 0

    def place(node, depth):
        nonlocal next_leaf
        r = indexed.loc[node]
        if pd.isna(r.feature):
            x = (next_leaf + .5) / leaf_count
            next_leaf += 1
        else:
            x = (place(int(r.left_child), depth+1) + place(int(r.right_child), depth+1)) / 2
        positions[node] = (x, 1 - depth / 3)
        return x

    place(0, 0)
    for node, r in indexed.iterrows():
        x, y = positions[node]
        if pd.notna(r.feature):
            for child in [int(r.left_child), int(r.right_child)]:
                cx, cy = positions[child]
                ax.annotate("", xy=(cx, cy+.07), xytext=(x, y-.07),
                            arrowprops={"arrowstyle": "->", "color": "0.45", "lw": 1}, zorder=1)
        split = ""
        if pd.notna(r.feature):
            label = FEATURE_LABELS.get(r.feature, r.feature)
            split = f"{label} ≤ {r.threshold:.3f}\n"
            if r.feature in ALLOW_MISSING and pd.notna(r.get("missing_child")):
                route = "left" if r.missing_child == r.left_child else "right"
                split += f"NaN → {route}\n"
        text = f"{split}MSE = {r.mse:.3g}\nn = {int(r.filing_days):,}\nITI = {r.mean_iti:.3f}"
        ax.text(x, y, text, ha="center", va="center", fontsize=9,
                color="white" if r.mean_iti > .65 else "black",
                bbox={"boxstyle": "round,pad=.35", "fc": plt.get_cmap("Blues")(r.mean_iti), "ec": "0.4"}, zorder=2)
    ax.set(xlim=(-.02, 1.02), ylim=(-.15, 1.15), title=title)
    ax.axis("off")


def figure3(data):
    model = fit_surrogate(data)
    tree = model.tree_
    rows = []
    for i in range(tree.node_count):
        left, right = tree.children_left[i], tree.children_right[i]
        leaf = left == right
        rows.append({"node": i, "feature": None if leaf else FEATURES[tree.feature[i]],
                     "threshold": None if leaf else tree.threshold[i], "mse": tree.impurity[i],
                     "filing_days": tree.n_node_samples[i], "mean_iti": tree.value[i, 0, 0],
                     "left_child": None if leaf else int(left), "right_child": None if leaf else int(right),
                     "missing_child": None if leaf else int(left if tree.missing_go_to_left[i] else right)})
    fit = model.score(data[FEATURES], data[SCORE])
    nodes = pd.DataFrame(rows).astype({"left_child": "Int64", "right_child": "Int64", "missing_child": "Int64"})
    nodes["surrogate_r2"] = fit
    paper = paper_reference(3)
    fig, axes = plt.subplots(1, 2, figsize=(29, 8))
    draw_tree(axes[0], nodes, f"Project: held-out ITI surrogate · sample $R^2$ = {fit:.3f}")
    draw_tree(axes[1], paper, "Paper: tree redrawn from printed nodes · caption: about one-third explained")
    fig.suptitle("Figure 3 · Three-level trees approximating ITI", fontsize=16, y=.97)
    fig.text(.5, .025, "All split inputs are standardized; left branch ≤ threshold, right branch > threshold. "
             "Published thresholds/MSEs/values are printed rounded numbers.\n"
             "Paper tree n = 61,255 differs from its main sample n = 58,197; its caption's fit claim is not reconstructed from rounded MSEs.",
             ha="center", fontsize=10)
    fig.subplots_adjust(left=.02, right=.98, bottom=.21, top=.88, wspace=.10)
    cax = fig.add_axes((.38, .14, .24, .012))
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 1), cmap="Blues"), cax=cax, orientation="horizontal")
    bar.set_label("Node mean ITI · same color scale in both panels", fontsize=9)
    fig.savefig(OUT / "figure3.pdf", bbox_inches="tight")
    save_figure(fig, 3, nodes)


def comparison_report(selected, predictions):
    provenance = json.loads((BENCHMARKS / "provenance.json").read_text())
    lines = ["# Figures 1–3: project ITI versus the published paper", "",
             (f"Generated figures: {', '.join(map(str, sorted(selected)))}. Project sample: {len(predictions):,} filing-days, "
             f"{predictions.filing.nunique():,} filings; {predictions.date.min():%Y-%m-%d}–{predictions.date.max():%Y-%m-%d}."), "",
             ("Project estimates use saved project held-out predictions and the saved XGBoost model. "
             "Published curves are digitized benchmarks, never inputs to estimation. No XGBoost retraining or acquisition is performed."), "",
             ("Reference: supplied forthcoming-paper PDF, printed pp. 41–43 (PDF pp. 43–45); DOI 10.1111/jofi.13320. "
             "Figures 1–2 are approximate numerical digitizations. Figure 3 preserves printed rounded nodes."), ""]
    if 1 in selected:
        a = pd.read_csv(OUT / "figure1.csv")
        lines += ["## Figure 1: annual adjusted R²", "",
                  ("Both project regressions use identical complete filing-days, an intercept, and pooled 0.05%/99.95% winsorized controls. "
                  "The primary nine-control specification follows the caption and includes price impact. "
                  "The archived-script eight-control specification remains a same-sample sensitivity column. No filing fixed effects are added to this annual specification."), "",
                  a[["year", "common_days", "iti_adjusted_r2", "controls_adjusted_r2", "controls8_adjusted_r2", "paper_iti_adjusted_r2", "paper_controls_adjusted_r2"]].to_markdown(index=False, floatfmt=".4f"), ""]
    if 2 in selected:
        curves = pd.read_csv(OUT / "figure2.csv")
        support = curves.groupby("feature").agg(display_lower=("bin_left", "min"), display_upper=("bin_right", "max"),
                                                project_fraction_outside=("observed_fraction_outside_display", "first"))
        lines += ["## Figure 2: partial dependence", "",
                  ("For each displayed value, replace only that feature for every retained training observation, predict with the saved final model, "
                  "and average over the full sample. All 41 columns are retained; odd-lot NaNs remain native. "
                  "Display ranges match the published curves; project histograms divide by the full observation count and bin width, "
                  "so displayed density need not integrate to one when tails fall outside the panel. "
                  "Published densities use the printed secondary-axis calibration. No published curve is extrapolated or smoothed."), "",
                  support.to_markdown(floatfmt=".4f"), ""]
    if 3 in selected:
        nodes = pd.read_csv(OUT / "figure3.csv")
        lines += ["## Figure 3: surrogate trees", "",
                  (f"Project sample R²: {nodes.surrogate_r2.iloc[0]:.4f}. This is the surrogate's fit to held-out ITI, not classifier performance. "
                  "It uses depth 3, minimum leaf fraction 1%, squared-error splits, and random seed 0. "
                  "Published tree nodes are transcribed rather than fit to project data. Both panels use the same ITI color scale."), "",
                  *[f"- {note}" for note in provenance["tree_notes"]], ""]
    lines += ["## Interpretation limits", "", ("The project uses a shorter sample, reconstructed filing labels, and documented feature/missing-data conventions. "
              "Differences cannot be attributed to sample dates alone. Published curve precision is limited by raster resolution, axis calibration, dashed-line gaps and narrow spikes. "
              "The eight-versus-nine control discrepancy and the paper's tree sample-count/fit inconsistencies are preserved explicitly."), ""]
    (OUT / "figures1_3_comparison.md").write_text("\n".join(lines))
    inputs = {str(p.relative_to(ROOT)): sha256(p) for p in
              [DATA / "oof_predictions.parquet", BENCHMARKS / "provenance.json",
               *[BENCHMARKS / f"figure{n}.csv" for n in sorted(selected)]]}
    for path in [DATA / "model_manifest.json", DATA / "features.parquet", DATA / "iti_13d.json"]:
        if path.exists():
            inputs[str(path.relative_to(ROOT))] = sha256(path)
    inputs[str(Path(__file__).relative_to(ROOT))] = sha256(Path(__file__))
    if 1 in selected:
        paths = [DATA / "raw_features.parquet"]
        for year in sorted(predictions.date.dt.year.unique()):
            paths.extend(WRDS / folder / f"{year}.parquet"
                         for folder in ("crsp_daily", "crsp_taq_links", "intraday_indicators"))
        inputs.update({str(path.relative_to(ROOT)): sha256(path) for path in paths})
    (OUT / "figures1_3_manifest.json").write_text(json.dumps({"figures_generated": sorted(selected), "input_sha256": inputs}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", type=int, choices=(1, 2, 3), action="append",
                        help="Build only this figure. Repeat to select multiple figures.")
    selected = set(parser.parse_args().figure or [1, 2, 3])
    predictions = heldout_predictions()
    OUT.mkdir(parents=True, exist_ok=True)
    if 1 in selected:
        figure1(predictions)
    if selected & {2, 3}:
        sample, manifest = fitted_sample(predictions)
        if 2 in selected:
            figure2(sample, manifest)
        if 3 in selected:
            figure3(sample)
    comparison_report(selected, predictions)
    print(f"Built {', '.join(f'Figure {number}' for number in sorted(selected))} in {OUT}")


if __name__ == "__main__":
    main()
