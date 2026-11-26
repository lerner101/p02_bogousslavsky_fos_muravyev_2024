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

import pandas as pd

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
    return sample, labels


def out_of_fold(sample, labels, features, jobs=2):
    """Outer-fold predictions for one feature list; mirrors train_iti.main."""
    predictions = pd.Series(index=sample.index, dtype="float64")
    selected = {}
    for fold in sorted(sample.outer_fold.unique()):
        train = sample[sample.outer_fold != fold]
        test = sample[sample.outer_fold == fold]
        params, _ = select_params(train, labels[labels.outer_fold != fold], jobs, features=features)
        model = classifier(params, jobs)
        model.fit(train[features], train.itrade)
        predictions.loc[test.index] = model.predict_proba(test[features])[:, 1]
        selected[int(fold)] = params
    return predictions, selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--groups", nargs="+", default=list(GROUPS), choices=list(GROUPS))
    args = parser.parse_args()
    sample, labels = load_sample()
    out = sample[[*KEY, "itrade", "outer_fold"]].copy()
    if OUT.exists():  # resume: keep groups already trained
        previous = pd.read_parquet(OUT)
        keep = [c for c in previous if c.startswith("ITI(")]
        out = out.merge(previous[[*KEY, *keep]], on=KEY, how="left", validate="one_to_one")
    report = {}
    for group in args.groups:
        print(f"Training {group_name(group)} on {len(GROUPS[group])} features", flush=True)
        p, selected = out_of_fold(sample, labels, GROUPS[group], args.jobs)
        out[group_name(group)] = p
        report[group] = {"selected": selected, **metrics(sample.itrade, p)}
        out.to_parquet(OUT, index=False)
        print(f"  pooled held-out ROC AUC {report[group]['roc_auc']:.3f}", flush=True)
    (DATA / "group_models.json").write_text(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
