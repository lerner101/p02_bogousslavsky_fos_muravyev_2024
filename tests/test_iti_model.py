"""Scientific invariants for ITI preprocessing and honest held-out evaluation."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from collect_iti_taq import interval_features
from iti_features import (
    ALLOW_MISSING,
    FEATURES,
    IID_MAP,
    SUPPLEMENTAL,
    derive_features,
    standardize,
)
from score_iti import window_flags
from train_iti import calendar_folds, classifier, select_params


def test_standardization_excludes_today_future_and_other_stocks():
    raw = pd.DataFrame({"permno": np.repeat([1, 2], 7), "date": list(pd.date_range("2004-01-01", periods=7))*2})
    for c in FEATURES:
        raw[c] = np.r_[np.arange(7), np.arange(7)*10]
    z = standardize(raw, window=3, min_periods=3)
    expected = (3 - np.mean([0, 1, 2])) / np.std([0, 1, 2], ddof=1)
    assert z.loc[3, "svol"] == pytest.approx(expected)
    changed = raw.copy()
    changed.loc[4:, "svol"] = 999
    z2 = standardize(changed, window=3, min_periods=3)
    assert z2.loc[3, "svol"] == z.loc[3, "svol"]
    assert z.loc[:2, FEATURES].isna().all().all()
    raw["svol"] = 1
    assert standardize(raw, 3, 3).svol.isna().all()
    raw["svol"] = pd.Series([pd.NA]*len(raw), dtype="Float64")
    assert standardize(raw, 3, 3).svol.isna().all()


def test_interval_returns_and_volume_boundary_conservation():
    x = pd.DataFrame({"permno": 1, "bucket": range(13), "mid": 10*1.01**np.arange(13), "volume": np.arange(1, 14)})
    y = interval_features(x).iloc[0]
    assert y.rv_in == pytest.approx(12 * 0.01**2)
    assert y.volume_open == 1
    assert y.svol_am == sum(range(2, 6))
    assert y.svol_pm == sum(range(10, 14))
    assert y.illiq_in == pytest.approx(np.mean(0.01 / np.arange(2, 14)))
    x.loc[3, "mid"] = np.nan
    y = interval_features(x).iloc[0]
    assert np.isnan(y.rv_in) and np.isnan(y.illiq_in)


def test_overnight_split_adjustment_and_imbalance_units():
    x = pd.DataFrame({"permno": [1, 1], "date": pd.date_range("2005-01-01", periods=2),
                      "prc": [100., 50.], "cfacpr": [2., 1.], "ret": [0., 0.], "vol": [100., 200.]})
    for c in set(IID_MAP.values()) | set(SUPPLEMENTAL):
        x[c] = 1.
    x["mid_1000"] = [100., 50.]
    x["mid_close"] = [100., 50.]
    x["buyvol_lr"], x["sellvol_lr"] = 300., 100.
    x["buynumtrades_lr"], x["sellnumtrades_lr"] = 30., 10.
    x["vwavg_buy_price_lr"], x["vwavg_sell_price_lr"] = 50., 49.
    y = derive_features(x)
    assert y.ret_ov.iloc[1] == pytest.approx(0)
    assert y.svol_imb.iloc[1] == 200  # share difference, not normalized imbalance
    assert y.vwap_imb.iloc[1] == 1
    assert list(y.columns) == ["permno", "date", *FEATURES]


def fixture_labels(n=40):
    rows = []
    for i, date in enumerate(pd.date_range("2005-01-01", periods=n, freq="30D")):
        for j in range(2):
            rows.append({"filing": i, "permno": i % 4, "date": date-pd.Timedelta(days=2-j),
                         "filing_date": date, "itrade": j})
    return pd.DataFrame(rows)


def test_folds_keep_overlaps_dates_and_filings_together():
    d = fixture_labels()
    # Two filing windows of the same stock overlap, straddling an initial split.
    first, second = 7, 8
    d.loc[d.filing.eq(second), "permno"] = d.loc[d.filing.eq(first), "permno"].iloc[0]
    d.loc[d.filing.eq(second), "date"] -= pd.Timedelta(days=30)
    d["fold"] = calendar_folds(d)
    assert d.groupby("filing").fold.nunique().max() == 1
    assert d[d.filing.isin([first, second])].fold.nunique() == 1
    assert d.sort_values("filing_date").fold.is_monotonic_increasing
    assert set(d.fold) == set(range(5))
    for fold in range(5):
        a, b = d[d.fold.ne(fold)], d[d.fold.eq(fold)]
        assert not set(zip(a.permno, a.date)) & set(zip(b.permno, b.date))
        assert calendar_folds(a).nunique() == 5


def test_tiny_nested_selection_and_model_roundtrip(tmp_path, monkeypatch):
    import train_iti
    labels = fixture_labels()
    d = labels.copy()
    rng = np.random.default_rng(42)
    for c in FEATURES:
        d[c] = rng.normal(size=len(d))
    monkeypatch.setattr(train_iti, "GRID", {"max_depth": [2], "learning_rate": [0.1],
                                         "n_estimators": [3], "min_child_weight": [1]})
    params, scores = select_params(d, labels, jobs=1)
    assert len(scores) == 1 and len(scores[0]["fold_losses"]) == 5
    model = classifier(params, 1)
    model.fit(d[FEATURES], d.itrade)
    p = model.predict_proba(d[FEATURES])[:, 1]
    path = tmp_path / "model.json"
    model.save_model(path)
    loaded = classifier(params, 1)
    loaded.load_model(path)
    np.testing.assert_array_equal(loaded.predict_proba(d[FEATURES])[:, 1], p)
    assert np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()


def test_comparison_excludes_training_windows_even_without_feature_rows():
    labels = fixture_labels(1)
    keys = pd.DataFrame({"permno": [0]*3, "date": pd.to_datetime(["2004-12-29", "2004-12-30", "2004-12-31"])})
    assert window_flags(keys, labels).tolist() == [False, True, True]


def test_training_scoring_and_comparison_integration(tmp_path, monkeypatch):
    """Synthetic smoke run; all artifacts stay in the temporary fixture tree."""
    import compare_iti
    import score_iti
    import train_iti
    from build_iti_features import sha256

    data = tmp_path / "_data/derived/ml_model"
    out = tmp_path / "_output/ml_model"
    label_dir = tmp_path / "_data/derived/13d"
    data.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    labels = fixture_labels()
    labels["date"] += pd.Timedelta(days=10)
    labels["filing_date"] += pd.Timedelta(days=10)
    labels["in_authors_sample"] = True
    labels["prc"] = 50.  # Ensure labels' raw price cannot shadow standardized price.
    labels.to_parquet(label_dir / "labels_daily.parquet", index=False)
    f = labels[["permno", "date"]].copy()
    general = f.copy()
    general["date"] += pd.Timedelta(days=10)
    f = pd.concat([f, general], ignore_index=True)
    rng = np.random.default_rng(42)
    for c in FEATURES:
        f[c] = rng.normal(size=len(f)).astype("float32")
    f["noddlot"] = np.nan  # Approved structural absence must not empty folds.
    f["complete"], f["eligible"] = True, True
    f.to_parquet(data / "features.parquet", index=False)
    manifest = {"partial_acquisition": False, "allow_missing": ALLOW_MISSING,
                "feature_sha256": sha256(data / "features.parquet")}
    (data / "features_manifest.json").write_text(json.dumps(manifest))
    for module in (train_iti, score_iti, compare_iti):
        monkeypatch.setattr(module, "ROOT", tmp_path)
        monkeypatch.setattr(module, "DATA", data)
    for module in (train_iti, compare_iti):
        monkeypatch.setattr(module, "OUT", out)
    monkeypatch.setattr(train_iti, "GRID", {"max_depth": [2], "learning_rate": [0.1],
                                         "n_estimators": [3], "min_child_weight": [1]})
    monkeypatch.setattr(sys, "argv", ["train_iti.py", "--jobs", "1"])
    train_iti.main()
    score_iti.main()
    oof = pd.read_parquet(data / "oof_predictions.parquet")
    assert len(oof) == len(labels) and oof["ITI(13D)"].notna().all()
    s = pd.read_parquet(data / "scores.parquet")
    assert s.in_training_window.sum() == len(labels)
    author_dir = tmp_path / "_data/public/iti_original_through_2019/year=2005"
    author_dir.mkdir(parents=True)
    author = s[["permno", "date", "ITI(13D)"]].copy()
    author.to_parquet(author_dir / "part.parquet", index=False)
    monkeypatch.setattr(compare_iti, "earnings_comparison", lambda matched: "Synthetic fixture: earnings regression tested separately.")
    compare_iti.main()
    match = pd.read_parquet(data / "matched_scores.parquet")
    assert len(match) == len(general)
    assert (match.project == match.author).all()
    assert (out / "model_performance.png").exists()
    assert (out / "comparison.md").exists()


def test_earnings_comparison_uses_identical_regression_rows(tmp_path, monkeypatch):
    import compare_iti
    root = tmp_path
    folder = root / "_data/wrds/crsp_daily"
    folder.mkdir(parents=True)
    calendar = pd.bdate_range("2005-01-03", periods=260)
    events = pd.DataFrame({"permno": [1, 2], "day0": [calendar[100], calendar[150]]})
    daily = pd.concat([pd.DataFrame({"permno": p, "date": calendar, "vol": 100., "ret": .001})
                       for p in [1, 2]], ignore_index=True)
    daily["permno"] = daily.permno.astype("Int64")
    for year in range(2004, 2020):
        daily[daily.date.dt.year.eq(year)].to_parquet(folder / f"{year}.parquet", index=False)
    from replicate_exhibits import event_offsets
    dm, _ = event_offsets(daily, events)
    signal = dm @ np.linspace(.001, .021, 21)
    matched = daily[["permno", "date"]].copy()
    matched["project"] = .2 + signal
    matched["author"] = .3 + signal
    # Deliberately remove some common sample dates: both regressions must drop them.
    matched = matched.drop(index=[2, 5, 8])
    out = root / "out"
    out.mkdir()
    monkeypatch.setattr(compare_iti, "ROOT", root)
    monkeypatch.setattr(compare_iti, "OUT", out)
    def checked_earnings(d):
        assert d.permno.dtype == np.dtype("int64")
        return events
    monkeypatch.setattr(compare_iti, "earnings_events", checked_earnings)
    compare_iti.earnings_comparison(matched)
    r = pd.read_csv(out / "earnings_comparison.csv")
    assert r.nobs.unique().tolist() == [len(matched)]
    a = r[r.measure.eq("project")].coef.to_numpy()
    b = r[r.measure.eq("author")].coef.to_numpy()
    np.testing.assert_allclose(a, b, atol=1e-12)


def test_data_inventory_does_not_treat_daily_dates_as_later_years(tmp_path, monkeypatch):
    import data_status
    folder = tmp_path / "_data/wrds/iti_supplemental/daily"
    folder.mkdir(parents=True)
    pd.DataFrame({"permno": [1]}).to_parquet(folder / "20040102.parquet", index=False)
    (folder / "20040102.json").write_text(json.dumps({"rows": 1, "version": 2}))
    monkeypatch.setattr(data_status, "ROOT", tmp_path)
    data_status.main()
    report = (tmp_path / "_output/data_acquisition_status.md").read_text()
    assert "Retained later-year WRDS files outside scope: 0" in report
    assert "ITI supplemental TAQ (bounded, v2)" in report
