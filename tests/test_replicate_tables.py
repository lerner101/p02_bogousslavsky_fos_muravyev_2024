"""Tables 1-4 code on synthetic data with known answers (no WRDS data needed).

These check the estimators and the matching before the real inputs exist:
a planted coefficient is recovered with filing fixed effects, turnover
matching respects the tolerance and pairs within a filing, and group ITIs are
predicted only out of fold.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import replicate_tables as rt  # noqa: E402
from paper_values import TABLE4_TURN_GAP  # noqa: E402


def synthetic_13d(n_filings=60, days=40, seed=0):
    """Filing-days where P(trade) = 0.2 + 0.6 * ITI + filing effect."""
    rng = np.random.default_rng(seed)
    filing = np.repeat(np.arange(n_filings), days)
    effect = rng.uniform(-0.1, 0.1, n_filings)[filing]
    iti = rng.uniform(0, 1, len(filing))
    itrade = (rng.uniform(size=len(filing)) < 0.2 + 0.6 * iti + effect).astype(int)
    d = pd.DataFrame({"filing": filing, "permno": filing + 100,
                      "date": pd.Timestamp("2010-01-01") + pd.to_timedelta(np.tile(np.arange(days), n_filings), "D"),
                      "itrade": itrade, "ITI": iti})
    for c in rt.CONTROLS:
        d[c] = rng.normal(size=len(d))
    d["turn_crsp"] = 0.01 + rng.normal(scale=0.00002, size=len(d))
    d["13Dturn"] = np.where(itrade == 1, 0.002 + 0.004 * iti + rng.normal(scale=1e-4, size=len(d)), 0)
    return d


def test_table2_recovers_planted_coefficient_and_layout():
    out = rt.table2_frame(synthetic_13d())
    coef = out.set_index(["column", "variable"]).coef
    assert coef[(1, "ITI")] == pytest.approx(0.6, abs=0.05)
    assert coef[(4, "ITI")] == pytest.approx(0.004, abs=3e-4)
    assert set(out.column) == {1, 2, 3, 4, 5, 6}
    # Columns 4-6 use trade days only.
    assert coef[(4, "Obs.")] < coef[(1, "Obs.")]


def test_turnover_matching_pairs_within_filing_and_tolerance():
    d = synthetic_13d(n_filings=10, days=20, seed=1)
    m = rt.match_on_turnover(d)
    assert len(m) > 0 and len(m) % 2 == 0
    for _, pair in m.groupby("pair"):
        assert pair.filing.nunique() == 1
        assert sorted(pair.itrade) == [0, 1]
        assert abs(pair.turn_crsp.diff().iloc[-1]) <= TABLE4_TURN_GAP
    assert not m.index.duplicated().any(), "a day was used in two pairs"


def test_matching_takes_closest_pair_first():
    d = pd.DataFrame({"filing": 1, "itrade": [1, 0, 0], "turn_crsp": [0.010, 0.010015, 0.010001]})
    m = rt.match_on_turnover(d)
    assert m.turn_crsp.tolist() == [0.010, 0.010001]


def test_table4_runs_on_matched_sample():
    out = rt.table4_frame(synthetic_13d())
    t = out.set_index(["column", "variable"])
    # Matching on turnover makes the turnover gap ~0 by construction.
    assert abs(t.loc[("a: turnover", "itrade"), "coef"]) < TABLE4_TURN_GAP
    assert t.loc[("b1", "ITI"), "coef"] > 0


def test_table3_layout():
    d = synthetic_13d()
    rng = np.random.default_rng(2)
    for g in rt.GROUP_ITIS:
        d[g] = d.ITI * rng.uniform(0.3, 0.8) + rng.normal(scale=0.1, size=len(d))
    out = rt.table3_frame(d)
    assert set(out.column) == {1, 2, 3, 4, 5, 6}
    assert set(out[out.column == 6].variable) >= set(rt.GROUP_ITIS)


def test_table1_within_stock_sd():
    panel = pd.DataFrame({"permno": [1, 1, 2, 2], "es": [1.0, 3.0, 11.0, 13.0], "ret": 0.0})
    labels = pd.DataFrame({"filing": [1, 1, 2], "itrade": [1, 0, 1]})
    out = rt.table1_frame(panel, labels).set_index("variable")
    assert out.loc["es", "sd"] > out.loc["es", "sd_within"]
    # Within-stock deviations are +/-1; 0.05% winsorization trims the 4-row toy slightly.
    assert out.loc["es", "sd_within"] == pytest.approx(np.std([-1, 1, -1, 1], ddof=1), rel=0.01)
    assert out.loc["13D trade (13D sample)", "mean"] == pytest.approx(2 / 3)


def test_assemble_joins_and_winsorizes():
    pred = pd.DataFrame({"filing": [1, 1], "permno": [5, 5], "date": pd.to_datetime(["2010-01-04", "2010-01-05"]),
                         "itrade": [1, 0], "ITI(13D)": [0.6, 0.2]})
    labels = pred[["filing", "permno", "date"]].assign(turn=[0.01, 0.02], **{"13Dturn": [0.001, 0.0]})
    controls = pred[["permno", "date"]].assign(**{c: [1.0, 2.0] for c in rt.CONTROLS})
    d = rt.assemble_13d_sample(pred, labels, controls)
    assert {"ITI", "turn_crsp", "turn", "13Dturn"} <= set(d.columns)
    assert d.ITI.tolist() == [0.6, 0.2]


def test_group_models_predict_only_out_of_fold(monkeypatch):
    import train_iti
    import train_iti_groups as tg

    monkeypatch.setattr(train_iti, "GRID", {"max_depth": [2], "learning_rate": [0.1],
                                         "n_estimators": [3], "min_child_weight": [1]})
    rows = []
    for i, date in enumerate(pd.date_range("2005-01-01", periods=40, freq="30D")):
        for j in range(2):
            rows.append({"filing": i, "permno": i % 4, "date": date - pd.Timedelta(days=2 - j),
                         "filing_date": date, "itrade": j})
    labels = pd.DataFrame(rows)
    labels["outer_fold"] = train_iti.calendar_folds(labels)
    sample = labels.copy()
    features = ["svol", "rvol"]
    rng = np.random.default_rng(0)
    for c in features:
        sample[c] = rng.normal(size=len(sample))
    p, selected = tg.out_of_fold(sample, labels, features, jobs=1)
    assert p.notna().all() and p.between(0, 1).all()
    assert set(selected) == set(sample.outer_fold.unique())
