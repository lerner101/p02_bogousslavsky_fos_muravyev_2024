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
from sklearn.tree import DecisionTreeRegressor, plot_tree

from build_iti_features import sha256
from iti_features import ALLOW_MISSING, FEATURES, REQUIRED_FEATURES, link_indicators

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data/derived/ml_model"
WRDS = ROOT / "_data/wrds"
OUT = ROOT / "_output/replication"
KEY = ["permno", "date"]
SCORE = "ITI(13D)"
# The authors' Figure 1 script uses these eight controls, as in Table 2.
CONTROLS = ["es", "lambda", "depth", "rvol", "turn", "oi", "abs_oi", "ret"]
RAW = ["es", "lambda1", "rvol", "svol", "svol_imb", "ret"]
DEPTH = ["bestofrdepth_share_tw", "bestbiddepth_share_tw"]
FEATURE_LABELS = {"svol": "Volume", "rvol": "Volatility", "prc": "Price"}


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
                     "controls_adjusted_r2": adjusted_r2(sample, CONTROLS)})
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
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(result.year, result.iti_adjusted_r2, marker=".", label="Held-out ITI(13D)")
    ax.plot(result.year, result.controls_adjusted_r2, marker=".", linestyle="--", label="Controls")
    ax.set(title="Stability of ITI in the Schedule 13D sample", xlabel="Stock-day year", ylabel="Adjusted $R^2$")
    ax.set_xticks(result.year.iloc[::2])
    ax.axhline(0, color="0.75", linewidth=0.7)
    ax.legend(frameon=False)
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


def partial_dependence(model, features, feature, bins=100):
    observed = features[feature]
    lower, upper = observed.quantile([0.01, 0.99])
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
                         "filing_days": len(observed)})


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
    fig, axes = plt.subplots(2, 1, figsize=(7, 8), layout="constrained")
    results = []
    for ax, feature in zip(axes, ["svol", "rvol"]):
        label = FEATURE_LABELS[feature]
        result = partial_dependence(model, data[FEATURES], feature)
        results.append(result)
        distribution = ax.twinx()
        distribution.bar(result.bin_left, result.density, width=result.bin_right - result.bin_left,
                         align="edge", color="0.87", linewidth=0)
        distribution.set_ylabel("Density", color="0.35")
        ax.set_zorder(distribution.get_zorder() + 1)
        ax.patch.set_visible(False)
        ax.plot(result.standardized_value, result.mean_iti, color="#1f5fbf")
        ax.set(title=f"Partial dependence of ITI on {label.lower()}",
               xlabel=f"Standardized {label.lower()}", ylabel="Predicted ITI")
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    save_figure(fig, 2, pd.concat(results, ignore_index=True))


def fit_surrogate(data):
    # Require at least 1% of the sample per leaf to discourage very small splits.
    model = DecisionTreeRegressor(max_depth=3, min_samples_leaf=0.01, random_state=0)
    model.fit(data[FEATURES], data[SCORE])
    return model


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
    fig, ax = plt.subplots(figsize=(15, 6), layout="constrained")
    plot_tree(model, feature_names=[FEATURE_LABELS.get(f, f) for f in FEATURES], ax=ax,
              filled=True, rounded=True, precision=3, fontsize=8)
    fit = model.score(data[FEATURES], data[SCORE])
    ax.set_title(f"Three-level surrogate tree for held-out ITI(13D) · Sample $R^2$ = {fit:.3f}")
    save_figure(fig, 3, pd.DataFrame(rows).astype(
        {"left_child": "Int64", "right_child": "Int64", "missing_child": "Int64"}))


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
    print(f"Built {', '.join(f'Figure {number}' for number in sorted(selected))} in {OUT}")


if __name__ == "__main__":
    main()
