"""Nested calendar-fold XGBoost estimation of ITI(13D).

Requires complete supplemental acquisition and all 41 features. Author ITI is
never read by training or tuning. python src/train_iti.py
"""
import argparse
import importlib.metadata
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, mean_absolute_error, roc_auc_score
from sklearn.model_selection import ParameterGrid
from xgboost import XGBClassifier

from build_iti_features import sha256
from iti_features import ALLOW_MISSING, FEATURES, REQUIRED_FEATURES

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data/derived/ml_model"
OUT = ROOT / "_output/ml_model"
GRID = {"max_depth": [2, 3, 4], "learning_rate": [0.03, 0.1],
        "n_estimators": [200, 500], "min_child_weight": [1, 10]}
PAPER = {"roc_auc": 0.7084, "log_loss": 0.5940, "mae": 0.3763}


def calendar_folds(labels, n_splits=5):
    """Consecutive filing-date blocks, with no overlapping stock windows split.

    All filings are assigned before feature attrition. Candidate boundaries inside
    connected overlapping filing windows are forbidden. No random stock-day split.
    """
    e = labels.groupby("filing").agg(permno=("permno", "first"), start=("date", "min"),
                                     end=("date", "max"), filing_date=("filing_date", "first"))
    intervals = []
    for _, stocks in e.groupby("permno"):
        lo = hi = None
        last_end = None
        for r in stocks.sort_values("start").itertuples():
            if last_end is None or r.start > last_end:
                if lo is not None:
                    intervals.append((lo, hi))
                lo = hi = r.filing_date
                last_end = r.end
            else:
                lo, hi = min(lo, r.filing_date), max(hi, r.filing_date)
                last_end = max(last_end, r.end)
        if lo is not None:
            intervals.append((lo, hi))
    dates = sorted(e.filing_date.unique())
    allowed = [pd.Timestamp(d) for d in dates[1:]
               if not any(lo < pd.Timestamp(d) <= hi for lo, hi in intervals)]
    if len(allowed) < n_splits - 1:
        raise ValueError("Insufficient nonoverlapping calendar boundaries for five folds")
    counts = e.filing_date.value_counts().sort_index().cumsum()
    cuts = []
    for k in range(1, n_splits):
        candidates = [d for d in allowed if not cuts or d > cuts[-1]]
        # Leave enough distinct boundaries for remaining folds.
        remaining = n_splits - 1 - k
        candidates = candidates[:len(candidates) - remaining] if remaining else candidates
        if not candidates:
            raise ValueError("Cannot form nonempty ordered folds")
        cuts.append(min(candidates, key=lambda d: abs(counts.loc[counts.index < d].iloc[-1] - len(e) * k / n_splits)))
    event_fold = np.searchsorted(np.array(cuts, dtype="datetime64[ns]"), e.filing_date.to_numpy(), side="right")
    return labels.filing.map(pd.Series(event_fold, index=e.index)).astype(int)


def classifier(params, jobs=2):
    return XGBClassifier(**params, objective="binary:logistic", eval_metric="logloss",
                         subsample=1, colsample_bytree=1, reg_lambda=1, reg_alpha=0,
                         random_state=42, n_jobs=jobs, tree_method="hist", device="cpu")


def metrics(y, p):
    return {"roc_auc": roc_auc_score(y, p) if len(np.unique(y)) == 2 else np.nan,
            "log_loss": log_loss(y, p, labels=[0, 1]), "mae": mean_absolute_error(y, p)}


def select_params(training, fold_universe, jobs=2):
    fold_map = fold_universe[["filing"]].copy()
    fold_map["inner_fold"] = calendar_folds(fold_universe)
    fold_map = fold_map.drop_duplicates("filing")
    d = training.merge(fold_map, on="filing", validate="many_to_one")
    if d.inner_fold.nunique() != 5:
        raise ValueError("Feature attrition emptied an inner fold; inspect coverage before fitting")
    rows = []
    candidates = list(ParameterGrid(GRID))
    for i, params in enumerate(candidates, 1):
        losses = []
        for fold in range(5):
            a, b = d[d.inner_fold != fold], d[d.inner_fold == fold]
            if a.itrade.nunique() != 2 or b.empty:
                raise ValueError("Insufficient labeled classes/rows in nested fold")
            model = classifier(params, jobs)
            model.fit(a[FEATURES], a.itrade)
            losses.append(log_loss(b.itrade, model.predict_proba(b[FEATURES])[:, 1], labels=[0, 1]))
        rows.append({**params, "mean_log_loss": float(np.mean(losses)), "fold_losses": losses})
        print(f"Tuning candidate {i}/{len(candidates)}: mean validation log loss {np.mean(losses):.6f}", flush=True)
    best = min(rows, key=lambda r: r["mean_log_loss"])
    return {k: best[k] for k in GRID}, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    manifest_path = DATA / "features_manifest.json"
    if not manifest_path.exists():
        raise SystemExit("Build all 41 features first: python src/build_iti_features.py")
    manifest = json.loads(manifest_path.read_text())
    if manifest["partial_acquisition"]:
        raise SystemExit("Partial acquisition is diagnostic only; resume TAQ collection and rebuild before training.")
    if manifest.get("allow_missing") != ALLOW_MISSING:
        raise ValueError("Feature missingness policy changed; rebuild features before training")
    if manifest["feature_sha256"] != sha256(DATA / "features.parquet"):
        raise ValueError("Feature fingerprint differs from manifest; rebuild features")
    labels_path = ROOT / "_data/derived/13d/labels_daily.parquet"
    labels = pd.read_parquet(labels_path)
    labels = labels[labels.filing_date.dt.year.between(2005, 2018) & labels.date.ge("2005-01-01")].copy()
    labels["outer_fold"] = calendar_folds(labels)
    features = pd.read_parquet(DATA / "features.parquet")
    d = labels.drop(columns=[c for c in FEATURES if c in labels]).merge(
        features[["permno", "date", *FEATURES]], on=["permno", "date"], how="left", validate="many_to_one")
    d["complete"] = np.isfinite(d[REQUIRED_FEATURES]).all(axis=1)
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    d[["filing", "permno", "date", "outer_fold", "complete"]].to_parquet(DATA / "fold_assignments.parquet", index=False)
    train = d[d.complete].copy()
    if train.outer_fold.nunique() != 5:
        raise ValueError("Feature attrition emptied an outer fold")
    train["ITI(13D)"] = np.nan
    train["sensitivity_iti"] = np.nan
    tuning, performance = {}, []
    for fold in range(5):
        a, b = train[train.outer_fold != fold], train[train.outer_fold == fold]
        params, scores = select_params(a, labels[labels.outer_fold != fold], args.jobs)
        tuning[str(fold)] = {"selected": params, "grid": scores}
        model = classifier(params, args.jobs)
        model.fit(a[FEATURES], a.itrade)
        p = model.predict_proba(b[FEATURES])[:, 1]
        train.loc[b.index, "ITI(13D)"] = p
        model.save_model(DATA / f"outer_{fold}.json")
        performance.append({"sample": "primary", "fold": fold, "rows": len(b), **metrics(b.itrade, p)})
        # Selection used only the corresponding outer training sample.
        sa = a[a.in_authors_sample.fillna(False)]
        sb = b[b.in_authors_sample.fillna(False)]
        if sa.itrade.nunique() == 2 and not sb.empty:
            sensitivity = classifier(params, args.jobs)
            sensitivity.fit(sa[FEATURES], sa.itrade)
            sp = sensitivity.predict_proba(sb[FEATURES])[:, 1]
            train.loc[sb.index, "sensitivity_iti"] = sp
            performance.append({"sample": "author_window_subset", "fold": fold, "rows": len(sb), **metrics(sb.itrade, sp)})
        (OUT / "tuning.json").write_text(json.dumps(tuning, indent=2))
        print("Outer fold complete:", fold, flush=True)
    params, scores = select_params(train, labels, args.jobs)
    tuning["full"] = {"selected": params, "grid": scores}
    model = classifier(params, args.jobs)
    model.fit(train[FEATURES], train.itrade)
    model.save_model(DATA / "iti_13d.json")
    train[["filing", "permno", "date", "itrade", "outer_fold", "in_authors_sample", "ITI(13D)", "sensitivity_iti"]].to_parquet(DATA / "oof_predictions.parquet", index=False)
    performance.append({"sample": "primary", "fold": "pooled", "rows": len(train), **metrics(train.itrade, train["ITI(13D)"])})
    sensitivity_rows = train[train.sensitivity_iti.notna()]
    if not sensitivity_rows.empty:
        performance.append({"sample": "author_window_subset", "fold": "pooled", "rows": len(sensitivity_rows),
                            **metrics(sensitivity_rows.itrade, sensitivity_rows.sensitivity_iti)})
        performance.append({"sample": "primary_on_author_subset", "fold": "pooled", "rows": len(sensitivity_rows),
                            **metrics(sensitivity_rows.itrade, sensitivity_rows["ITI(13D)"])})
    pd.DataFrame(performance).to_csv(OUT / "model_performance.csv", index=False)
    (OUT / "tuning.json").write_text(json.dumps(tuning, indent=2))
    final = {"feature_order": FEATURES, "allow_missing": ALLOW_MISSING, "selected": params, "fixed": classifier(params, args.jobs).get_params(),
             "labels_sha256": sha256(labels_path), "features_sha256": sha256(DATA / "features.parquet"),
             "feature_manifest_sha256": sha256(manifest_path), "model_sha256": sha256(DATA / "iti_13d.json"),
             "versions": {p: importlib.metadata.version(p) for p in ["xgboost", "scikit-learn", "pandas", "numpy"]},
             "paper_benchmarks": PAPER, "train_rows": len(train), "train_filings": train.filing.nunique()}
    (DATA / "model_manifest.json").write_text(json.dumps(final, indent=2, default=str))


if __name__ == "__main__":
    main()
