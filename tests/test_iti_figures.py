"""Exercise the figure task using saved artifacts and local extracts only."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_iti_features import sha256
from iti_features import ALLOW_MISSING, FEATURES
from replicate_iti_figures import (
    CONTROLS,
    adjusted_r2,
    annual_stability,
    fit_surrogate,
    paper_reference,
    partial_dependence,
    validate_tree,
)


def test_nine_control_primary_and_eight_control_sensitivity_share_sample():
    rng = np.random.default_rng(21)
    days = pd.bdate_range("2005-01-03", periods=80)
    y = np.tile([0, 1], 40)
    predictions = pd.DataFrame({"permno": 1, "date": days, "filing": np.arange(80),
                                "itrade": y, "ITI(13D)": .3 + .2*y})
    controls = predictions[["permno", "date"]].copy()
    for c in CONTROLS:
        controls[c] = rng.normal(size=80)
    controls["pi"] = y + rng.normal(scale=.01, size=80)
    controls.loc[0, "pi"] = np.nan
    result = annual_stability(predictions, controls).iloc[0]
    assert result.heldout_days == 80 and result.common_days == 79
    assert result.iti_adjusted_r2 == pytest.approx(1)
    assert result.controls_adjusted_r2 > result.controls8_adjusted_r2 + .8
    assert adjusted_r2(predictions.assign(constant=1), ["constant"]) == pytest.approx(0)
    assert np.isnan(adjusted_r2(predictions.assign(itrade=1), ["ITI(13D)"]))


def test_partial_dependence_averages_background_and_preserves_truncated_density():
    features = pd.DataFrame({"svol": [-2., 0., 2.], "rvol": [0., 1., 2.], "noddlot": [np.nan, 1., np.nan]})
    before = features.copy(deep=True)

    class KnownModel:
        def predict_proba(self, x):
            assert x.noddlot.isna().sum() == 2
            p = .5 + .05*x.svol.to_numpy() + .02*x.rvol.to_numpy()
            return np.column_stack([1-p, p])

    result = partial_dependence(KnownModel(), features, "svol", bins=4, bounds=(-1., 1.))
    np.testing.assert_allclose(result.mean_iti, .52 + .05*result.standardized_value)
    assert (result.density * (result.bin_right-result.bin_left)).sum() == pytest.approx(1/3)
    assert result.observed_fraction_outside_display.iloc[0] == pytest.approx(2/3)
    pd.testing.assert_frame_equal(features, before)


def test_published_nodes_and_curves_are_valid_benchmarks():
    nodes = paper_reference(3)
    assert validate_tree(nodes) == 61255
    assert nodes.set_index("node").loc[2, "threshold"] == -1.347
    bad = nodes.copy()
    bad.loc[bad.node.eq(0), "filing_days"] += 1
    with pytest.raises(ValueError, match="counts"):
        validate_tree(bad)
    annual = paper_reference(1)
    assert annual.year.tolist() == list(range(2005, 2019))
    assert annual[["iti_adjusted_r2", "controls_adjusted_r2"]].ge(0).all().all()
    curves = paper_reference(2)
    for _, group in curves.groupby("feature"):
        assert group.standardized_value.is_monotonic_increasing
        assert group.mean_iti.between(0, 1).all() and group.density.ge(0).all()
        assert .8 < np.trapezoid(group.density, group.standardized_value) < 1.1


def test_surrogate_uses_project_scores_with_native_missing_feature(monkeypatch):
    import replicate_iti_figures
    rng = np.random.default_rng(7)
    data = pd.DataFrame(rng.normal(size=(100, len(FEATURES))), columns=FEATURES)
    data["noddlot"] = np.nan
    data["ITI(13D)"] = np.where(data.svol > 0, .6, .2)

    def forbidden_reference(_):
        raise AssertionError("Published values must not enter surrogate fitting")

    monkeypatch.setattr(replicate_iti_figures, "paper_reference", forbidden_reference)
    tree = fit_surrogate(data)
    assert tree.get_depth() <= 3 and tree.score(data[FEATURES], data["ITI(13D)"]) == pytest.approx(1)


def test_figures_build_without_training_inputs(tmp_path):
    shutil.copy(ROOT / "dodo.py", tmp_path)
    shutil.copytree(ROOT / "src", tmp_path / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "data_manual/iti_figure_benchmarks", tmp_path / "data_manual/iti_figure_benchmarks")
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
    raw = keys.join(features[["es", "pi", "lambda1", "rvol", "svol", "svol_imb", "ret"]])
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
                            capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    out = tmp_path / "_output/replication"
    for number in (1, 2, 3):
        assert (out / f"figure{number}.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    annual = pd.read_csv(out / "figure1.csv")
    assert annual.year.tolist() == [2005, 2006]
    assert annual.heldout_days.tolist() == [41, 40]
    assert annual.common_days.tolist() == [40, 40]
    assert np.isfinite(annual[["iti_adjusted_r2", "controls_adjusted_r2"]]).all().all()
    assert np.isfinite(annual[["paper_iti_adjusted_r2", "paper_controls_adjusted_r2", "controls8_adjusted_r2"]]).all().all()
    curves = pd.read_csv(out / "figure2.csv")
    assert curves.groupby("feature").size().to_dict() == {"rvol": 100, "svol": 100}
    assert curves.mean_iti.between(0, 1).all()
    nodes = pd.read_csv(out / "figure3.csv")
    leaves = nodes[nodes.feature.isna()]
    assert 1 < len(leaves) <= 8
    assert leaves.filing_days.sum() == len(predictions)
    assert (out / "figure3.pdf").read_bytes().startswith(b"%PDF")
    assert (out / "figures1_3_comparison.md").exists()
    assert sha256(data / "iti_13d.json") == json.loads((data / "model_manifest.json").read_text())["model_sha256"]
