"""Score acquired stock-days with the fitted primary ITI model."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from build_iti_features import sha256
from iti_features import ALLOW_MISSING, FEATURES

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data/derived/ml_model"


def window_flags(keys, labels):
    """Exclude all reconstructed training windows, including incomplete-feature days."""
    windows = labels[labels.filing_date.dt.year.between(2005, 2018)].groupby(["permno", "filing"]).agg(
        start=("date", "min"), end=("date", "max")).reset_index()
    result = pd.Series(False, index=keys.index)
    for permno, w in windows.groupby("permno"):
        index = keys.index[keys.permno == permno]
        dates = keys.loc[index, "date"]
        inside = np.zeros(len(index), dtype=bool)
        for r in w.itertuples():
            inside |= dates.between(r.start, r.end).to_numpy()
        result.loc[index] = inside
    return result


def main():
    manifest = json.loads((DATA / "model_manifest.json").read_text())
    if manifest["feature_order"] != FEATURES:
        raise ValueError("Feature order differs from fitted model")
    if manifest.get("allow_missing") != ALLOW_MISSING:
        raise ValueError("Missing-value policy differs from fitted model")
    if manifest["features_sha256"] != sha256(DATA / "features.parquet"):
        raise ValueError("Features changed after training; refit before scoring")
    if manifest["model_sha256"] != sha256(DATA / "iti_13d.json"):
        raise ValueError("Model fingerprint differs from manifest")
    d = pd.read_parquet(DATA / "features.parquet")
    d = d[d.complete & d.eligible & d.date.between("2005-01-01", "2019-12-31")].copy()
    if d.empty:
        raise ValueError("No complete eligible stock-days available for scoring")
    model = XGBClassifier()
    model.load_model(DATA / "iti_13d.json")
    result = d[["permno", "date"]].copy()
    result["ITI(13D)"] = model.predict_proba(d[FEATURES])[:, 1]
    result["in_training_window"] = window_flags(result, pd.read_parquet(ROOT / "_data/derived/13d/labels_daily.parquet"))
    if result.duplicated(["permno", "date"]).any() or not result["ITI(13D)"].between(0, 1).all():
        raise ValueError("Invalid score keys or range")
    result.to_parquet(DATA / "scores.parquet", index=False)
    print(f"Scored {len(result):,} stock-days; {result.in_training_window.sum():,} flagged training-window rows")


if __name__ == "__main__":
    main()
