"""Figure 4 event design: checks against a literal port of the authors' pandas code."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import replicate_exhibits  # noqa: E402
from replicate_figure4 import (EA_DAYS, earnings_events, event_dummies, quartile_groups,  # noqa: E402
                               regress, sparse_stocks)


def synthetic_panel(seed=0, stocks=4, days=120, p_event=0.04):
    rng = np.random.default_rng(seed)
    d = pd.MultiIndex.from_product([range(stocks), pd.bdate_range("2010-01-04", periods=days)],
                                  names=["permno", "date"]).to_frame(index=False)
    d["EA"] = (rng.random(len(d)) < p_event).astype(float)
    d["ret"] = rng.normal(0, 0.03, len(d))
    return d


def authors_dummies(d):
    """ITI_main.py run_EAs_test: df['EA'+lag] = df['EA'].groupby(level='permno').shift(lag)."""
    df = d.set_index(["permno", "date"])
    return pd.DataFrame({f"EA{k}": df.EA.groupby(level="permno").shift(k) for k in EA_DAYS})


def authors_quartile_keep(d, quartile):
    """Literal port of the surprise_analysis branch of run_EAs_test."""
    df = d.set_index(["permno", "date"]).join(authors_dummies(d))
    ea_vars = [f"EA{k}" for k in EA_DAYS]
    df["|surprise|"] = np.nan
    df.loc[df.EA == 1, "|surprise|"] = df.loc[df.EA == 1, "ret"].abs()
    if quartile == "bottom":
        idd = df["|surprise|"] < df["|surprise|"].quantile(0.25)
    else:
        idd = df["|surprise|"] > df["|surprise|"].quantile(0.75)
    df["surprise_group"] = np.where(df["|surprise|"].notnull(), idd * 1, np.nan)
    df["surprise_group"] = df["surprise_group"].groupby(level="permno").ffill(limit=10)
    df["surprise_group"] = df["surprise_group"].groupby(level="permno").bfill(limit=10)
    exclude = (df[ea_vars].sum(axis=1) == 1) & df["surprise_group"].isnull()
    keep = ~exclude & ((df["surprise_group"] == 1) | df["surprise_group"].isnull())
    return keep.to_numpy()


def test_event_dummies_match_groupby_shift_and_edge_dropna():
    d = synthetic_panel()
    ref = authors_dummies(d)
    dm, valid = event_dummies(d.permno.to_numpy(), d.EA.to_numpy(), EA_DAYS)
    np.testing.assert_array_equal(valid, ref.notna().all(axis=1).to_numpy())
    np.testing.assert_array_equal(dm[valid], ref.to_numpy()[valid].astype(np.int8))
    # Shifts never cross stocks: the first ten rows of every stock are invalid.
    assert not valid[d.groupby("permno").cumcount().to_numpy() < 10].any()


def test_positive_day_is_after_the_announcement():
    d = synthetic_panel(stocks=1, days=40, p_event=0)
    d.loc[20, "EA"] = 1
    dm, _ = event_dummies(d.permno.to_numpy(), d.EA.to_numpy(), EA_DAYS)
    assert dm[23, EA_DAYS.index(3)] == 1
    assert dm[17, EA_DAYS.index(-3)] == 1
    assert dm[:, EA_DAYS.index(0)].sum() == 1


@pytest.mark.parametrize("quartile", ["top", "bottom"])
def test_quartile_filter_matches_authors(quartile):
    d = synthetic_panel(seed=7, stocks=6, days=200, p_event=0.05)
    d.loc[d.EA.eq(1).idxmax(), "ret"] = np.nan  # an announcement with a missing surprise
    dm, _ = event_dummies(d.permno.to_numpy(), d.EA.to_numpy(), EA_DAYS)
    keep, n = quartile_groups(d.permno.to_numpy(), d.EA.to_numpy(), d.ret.to_numpy(), quartile, dm)
    ref = authors_quartile_keep(d, quartile)
    # Our dummy sums treat out-of-history shifts as 0, the authors' sum skips NaN: identical.
    np.testing.assert_array_equal(keep, ref)
    assert 0 < n < d.EA.sum()


def test_volume_test_moves_after_hours_announcements_and_weekends(monkeypatch):
    crsp = pd.DataFrame({"permno": 1, "date": pd.bdate_range("2010-01-04", periods=10),
                         "vol": [100, 100, 100, 500, 100, 100, 900, 100, 100, 100], "ret": 0.0})
    sources = {
        "compustat_earnings.parquet": pd.DataFrame(
            {"gvkey": "001", "rdq": pd.to_datetime(["2010-01-05", "2010-01-09", "2010-01-13", "2010-01-14"])}),
        "crsp_compustat_links.parquet": pd.DataFrame(
            {"gvkey": ["001"], "lpermno": [1.0], "linktype": ["LC"], "linkprim": ["P"],
             "linkdt": ["2009-01-01"], "linkenddt": ["2010-01-13"]}),
    }
    monkeypatch.setattr(replicate_exhibits.pd, "read_parquet",
                        lambda path, columns=None, **_: sources[Path(path).name][columns])
    out = earnings_events(crsp)
    # Jan 5 stays (next day not higher); Saturday Jan 9 -> Monday Jan 11 -> Jan 12 (900);
    # Jan 13 stays; Jan 14 falls after the link ends.
    assert list(out.date.dt.strftime("%m-%d")) == ["01-05", "01-12", "01-13"]


def test_sparse_stock_rule_uses_median_calendar_gap():
    daily = pd.bdate_range("2010-01-04", periods=30)
    weekly = pd.date_range("2010-01-04", periods=30, freq="7D")
    d = pd.concat([pd.DataFrame({"permno": 1, "date": daily}), pd.DataFrame({"permno": 2, "date": weekly})])
    assert sparse_stocks(d.sort_values(["permno", "date"])) == {2}


def test_regression_recovers_event_profile_with_stock_effects():
    rng = np.random.default_rng(3)
    d = synthetic_panel(seed=3, stocks=40, days=250, p_event=0.02)
    dm, valid = event_dummies(d.permno.to_numpy(), d.EA.to_numpy(), EA_DAYS)
    truth = np.array([0.1 if k == 0 else 0.03 if k == 1 else 0.0 for k in EA_DAYS])
    d["y"] = 0.3 + 0.01 * d.permno + dm @ truth + rng.normal(0, 0.001, len(d))
    frame = d[valid].reset_index(drop=True)
    names = [f"d{k}" for k in EA_DAYS]
    for j, n in enumerate(names):
        frame[n] = dm[valid, j]
    tab, stats = regress(frame, "y", names)
    np.testing.assert_allclose(tab.coef.to_numpy(), truth, atol=0.002)
    assert stats["nobs"] == valid.sum()
