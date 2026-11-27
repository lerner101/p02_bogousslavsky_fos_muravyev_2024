"""Train the four feature-group ITIs for Table 3 (and Table IA.7).

Each group model (return, liquidity, volatility, volume; iti_features.GROUPS) is
trained exactly like ITI(13D) in train_iti.py: the same held-out sample, the
same outer calendar folds, and nested calendar-fold hyperparameter selection
on the outer-training filings only. Only the feature list changes, so the
group ITIs are directly comparable with the full ITI(13D).

Inputs (from a completed `doit iti_train` run):
  _data/derived/ml_model/oof_predictions.parquet   sample and outer folds
  _data/derived/ml_model/features.parquet          standardized features
  _data/derived/13d/labels_daily.parquet           filing dates for inner folds
Output:
  _data/derived/ml_model/group_oof_predictions.parquet
      filing, permno, date, itrade, outer_fold, ITI(return), ITI(liquidity),
      ITI(volatility), ITI(volume)

Cost: four times one outer-fold training pass (24-candidate grid, nested
five-fold). Run: python src/train_iti_groups.py [--jobs N] [--groups volume ...]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from build_iti_features import sha256
from iti_features import ALLOW_MISSING, FEATURES, REQUIRED_FEATURES

from iti_features import GROUPS
from train_iti import classifier, metrics, select_params

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data/derived/ml_model"
LABELS = ROOT / "_data/derived/13d/labels_daily.parquet"
OUT = DATA / "group_oof_predictions.parquet"
KEY = ["filing", "permno", "date"]


def group_name(group):
    return f"ITI({group})"


def load_sample():
    """Held-out ITI(13D) sample with its outer folds, joined to the features."""
    oof = pd.read_parquet(DATA / "oof_predictions.parquet", columns=[*KEY, "itrade", "outer_fold"])
    features = pd.read_parquet(DATA / "features.parquet")
    feature_cols = [c for cols in GROUPS.values() for c in cols]
    sample = oof.merge(features[["permno", "date", *feature_cols]], on=["permno", "date"],
                       how="left", validate="many_to_one")
    labels = pd.read_parquet(LABELS, columns=["filing", "permno", "date", "filing_date"])
    labels = labels[labels.filing.isin(sample.filing.unique())]
    folds = sample[["filing", "outer_fold"]].drop_duplicates("filing")
    labels = labels.merge(folds, on="filing", validate="many_to_one")
    manifest = json.loads((DATA / "model_manifest.json").read_text())
    if manifest["features_sha256"] != sha256(DATA / "features.parquet"):
        raise ValueError("Standardized features differ from the original model inputs")
    if manifest["feature_order"] != FEATURES or manifest["allow_missing"] != ALLOW_MISSING:
        raise ValueError("Feature contract differs from the saved full model")
    if sample.duplicated(KEY).any() or len(sample) != manifest["train_rows"]:
        raise ValueError("Invalid held-out sample")
    if not np.isfinite(sample[REQUIRED_FEATURES]).all().all() or np.isinf(sample[ALLOW_MISSING]).any().any():
        raise ValueError("Only odd-lot counts may be missing")
    if sample.groupby("filing").outer_fold.nunique().gt(1).any():
        raise ValueError("A filing crosses outer folds")
    # No stock-day may be shared by outer training and validation sets.
    if sample.groupby(["permno", "date"]).outer_fold.nunique().gt(1).any():
        raise ValueError("A stock-day crosses outer folds")
    return sample, labels


def out_of_fold(sample, labels, features, jobs=2, audit=None):
    """Outer-fold predictions for one feature list; mirrors train_iti.main."""
    predictions = pd.Series(index=sample.index, dtype="float64")
    selected = {}
    for fold in sorted(sample.outer_fold.unique()):
        train = sample[sample.outer_fold != fold]
        test = sample[sample.outer_fold == fold]
        print(f"Outer fold {fold}: {len(train):,} training / {len(test):,} validation rows", flush=True)
        params, tuning = select_params(train, labels[labels.outer_fold != fold], jobs, features=features)
        model = classifier(params, jobs)
        model.fit(train[features], train.itrade)
        predictions.loc[test.index] = model.predict_proba(test[features])[:, 1]
        selected[int(fold)] = params
        if audit is not None:
            audit[str(int(fold))] = {"selected": params, "grid": tuning,
                                     "train_rows": len(train), "validation_rows": len(test)}
    return predictions, selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--groups", nargs="+", default=list(GROUPS), choices=list(GROUPS))
    args = parser.parse_args()
    sample, labels = load_sample()
    out = sample[[*KEY, "itrade", "outer_fold"]].copy()
    fingerprint = {str(p.relative_to(ROOT)): sha256(p) for p in
                   [DATA / "features.parquet", DATA / "oof_predictions.parquet", LABELS,
                    ROOT / "src/train_iti.py", Path(__file__), ROOT / "src/iti_features.py"]}
    report_path = DATA / "group_models.json"
    report = {"input_sha256": fingerprint, "groups": {}}
    if OUT.exists() or report_path.exists():
        if not OUT.exists() or not report_path.exists():
            raise ValueError("Incomplete group checkpoint; preserve it and investigate before resuming")
        report = json.loads(report_path.read_text())
        if report.get("input_sha256") != fingerprint:
            raise ValueError("Group checkpoint input fingerprints differ; refusing incompatible reuse")
        previous = pd.read_parquet(OUT)
        pd.testing.assert_frame_equal(previous[[*KEY, "itrade", "outer_fold"]], out)
        out = previous
    for group in args.groups:
        name = group_name(group)
        if group in report["groups"] and name in out and out[name].notna().all():
            print(f"Reusing completed {name}", flush=True)
            continue
        print(f"Training {name} on {len(GROUPS[group])} features", flush=True)
        audit = {}
        p, selected = out_of_fold(sample, labels, GROUPS[group], args.jobs, audit=audit)
        if not p.notna().all() or not p.between(0, 1).all():
            raise ValueError(f"Invalid predictions for {name}")
        out[name] = p
        report["groups"][group] = {"features": GROUPS[group], "selected": selected,
                                    "folds": audit, **metrics(sample.itrade, p)}
        temporary = OUT.with_suffix(".tmp.parquet")
        out.to_parquet(temporary, index=False)
        temporary.replace(OUT)
        temporary_report = report_path.with_suffix(".tmp.json")
        temporary_report.write_text(json.dumps(report, indent=2, default=str) + "\n")
        temporary_report.replace(report_path)
        print(f"  pooled held-out ROC AUC {report['groups'][group]['roc_auc']:.3f}", flush=True)


if __name__ == "__main__":
    main()
