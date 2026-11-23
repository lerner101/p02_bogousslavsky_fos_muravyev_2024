"""Exercise the figure task using saved artifacts and local extracts only."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_iti_features import sha256
from iti_features import ALLOW_MISSING, FEATURES


def test_figures_build_without_training_inputs(tmp_path):
    shutil.copy(ROOT / "dodo.py", tmp_path)
    shutil.copytree(ROOT / "src", tmp_path / "src", ignore=shutil.ignore_patterns("__pycache__"))
    rng = np.random.default_rng(4)
    days = pd.bdate_range("2005-02-01", periods=40).append(pd.bdate_range("2006-02-01", periods=40))
    keys = pd.DataFrame({"permno": 10001, "date": days})
    features = pd.DataFrame(rng.normal(size=(len(days), len(FEATURES))), columns=FEATURES, dtype="float32")
    features.loc[::4, "noddlot"] = np.nan
    iti = (features.svol + 2 * features.rvol).apply(lambda x: 1 / (1 + np.exp(-x)))
    labels = (iti > 0.5).astype(int)
    model = XGBClassifier(n_estimators=3, n_jobs=1, random_state=0)
    model.fit(features, labels)
    data = tmp_path / "_data/derived/ml_model"
    data.mkdir(parents=True)
    model.save_model(data / "iti_13d.json")
    keys.join(features).to_parquet(data / "features.parquet", index=False)
    predictions = keys.assign(itrade=labels, filing=days.year.astype(str), **{"ITI(13D)": iti})
    # Two filing windows can share a stock-day without being duplicate filing-days.
    predictions = pd.concat([predictions, predictions.iloc[[1]].assign(filing="overlap")], ignore_index=True)
    predictions.to_parquet(data / "oof_predictions.parquet", index=False)
    (data / "model_manifest.json").write_text(json.dumps({
        "feature_order": FEATURES, "allow_missing": ALLOW_MISSING, "train_rows": len(predictions),
        "features_sha256": sha256(data / "features.parquet"), "model_sha256": sha256(data / "iti_13d.json"),
    }))
    raw = keys.join(features[["es", "lambda1", "rvol", "svol", "svol_imb", "ret"]])
    raw.to_parquet(data / "raw_features.parquet", index=False)

    wrds = tmp_path / "_data/wrds"
    for year, group in keys.groupby(days.year):
        symbols = group[["date"]].assign(sym_root="TEST", sym_suffix=None)
        for source, frame in {
            "crsp_daily": group.assign(shrout=1000),
            "crsp_taq_links": symbols.assign(permno=10001),
            "intraday_indicators": symbols.assign(bestofrdepth_share_tw=rng.uniform(10, 50, len(group)),
                                                   bestbiddepth_share_tw=30),
        }.items():
            folder = wrds / source
            folder.mkdir(parents=True, exist_ok=True)
            if source == "intraday_indicators" and year == 2005:
                frame = frame.iloc[1:]
            frame.to_parquet(folder / f"{year}.parquet", index=False)

    result = subprocess.run([sys.executable, "-m", "doit", "iti_figures"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    out = tmp_path / "_output/replication"
    for number in (1, 2, 3):
        assert (out / f"figure{number}.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    annual = pd.read_csv(out / "figure1.csv")
    assert annual.year.tolist() == [2005, 2006]
    assert annual.heldout_days.tolist() == [41, 40]
    assert annual.common_days.tolist() == [40, 40]
    assert np.isfinite(annual[["iti_adjusted_r2", "controls_adjusted_r2"]]).all().all()
    curves = pd.read_csv(out / "figure2.csv")
    assert curves.groupby("feature").size().to_dict() == {"rvol": 100, "svol": 100}
    assert curves.mean_iti.between(0, 1).all()
    nodes = pd.read_csv(out / "figure3.csv")
    leaves = nodes[nodes.feature.isna()]
    assert 1 < len(leaves) <= 8
    assert leaves.filing_days.sum() == len(predictions)
