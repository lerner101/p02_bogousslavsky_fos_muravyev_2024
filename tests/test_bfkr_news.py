"""Historical links, event-window alignment and regression checks."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyze_bfkr_news import SCORES, estimate, event_design, require_keys
from prepare_bfkr_news import link_earnings, link_news


def test_ticker_reuse_and_ambiguous_links():
    news = pd.DataFrame({"ticker": ["X", "X", "Y", "Z"],
                         "date": pd.to_datetime(["2005-01-03", "2010-01-04", "2010-01-04", "2010-01-04"]),
                         "CC_day_type": [0, 1, 2, 3]})
    names = pd.DataFrame({"ticker": ["X", "X", "X", "Y", "Y"], "permno": [1, 1, 2, 3, 4],
                          "namedt": pd.to_datetime(["2000-01-01"] * 2 + ["2009-01-01"] * 3),
                          "nameendt": pd.to_datetime(["2008-12-31"] * 2 + ["2015-12-31"] * 3),
                          "shrcd": [10] * 5})
    out = link_news(news, names)
    assert out.link_status.tolist() == ["linked", "linked", "ambiguous", "unmatched"]
    assert out.permno.iloc[:2].tolist() == [1, 2]


def test_two_tickers_for_one_stock_day_are_rejected():
    news = pd.DataFrame({"ticker": ["X", "Y"], "date": pd.to_datetime(["2010-01-04"] * 2),
                         "CC_day_type": [1, 0]})
    names = pd.DataFrame({"ticker": ["X", "Y"], "permno": [1, 1], "shrcd": [10, 10],
                          "namedt": pd.to_datetime(["2000-01-01"] * 2),
                          "nameendt": pd.to_datetime(["2020-01-01"] * 2)})
    assert link_news(news, names).link_status.eq("duplicate_stock_day").all()


def test_earnings_use_dated_primary_ccm_links():
    e = pd.DataFrame({"gvkey": ["A", "A"], "rdq": pd.to_datetime(["2005-01-03", "2010-01-04"])})
    links = pd.DataFrame({"gvkey": ["A", "A", "A"], "lpermno": [1, 2, 3],
                          "linktype": ["LC", "LU", "LC"], "linkprim": ["P", "C", "J"],
                          "linkdt": pd.to_datetime(["2000-01-01", "2009-01-01", "2000-01-01"]),
                          "linkenddt": pd.to_datetime(["2008-12-31", None, None])})
    assert link_earnings(e, links).permno.tolist() == [1, 2]


def test_event_lags_follow_stock_observation_days_and_sign():
    dates = pd.bdate_range("2010-01-04", periods=30)
    n = pd.DataFrame({"permno": 1, "date": dates, "CC_day_type": 0})
    n.loc[15, "CC_day_type"] = 2
    empty_e = pd.DataFrame({"permno": pd.Series(dtype=int), "date": pd.Series(dtype="datetime64[ns]")})
    design, excluded = event_design(n, empty_e, dates)
    assert excluded == 0
    assert design.loc[design.date == dates[16], "news1"].item() == 1
    assert design.loc[design.date == dates[14], "news-1"].item() == 1
    e = pd.DataFrame({"permno": [1], "date": [pd.Timestamp("2010-01-09")]})
    design, excluded = event_design(n, e, dates)
    assert excluded == 5
    assert not design.date.isin(dates[3:8]).any()  # Saturday maps to Monday, index 5.


def test_duplicate_panel_keys_raise():
    with pytest.raises(ValueError, match="duplicate"):
        require_keys(pd.DataFrame({"permno": [1, 1], "date": pd.to_datetime(["2010-01-04"] * 2)}), "test")


def test_regression_recovers_known_effect_with_stock_fixed_effects():
    pytest.importorskip("linearmodels")
    rng = np.random.default_rng(123)
    d = pd.MultiIndex.from_product([range(10), pd.bdate_range("2010-01-04", periods=80)],
                                  names=["permno", "date"]).to_frame(index=False)
    for lag in range(-5, 6):
        d[f"news{lag}"] = rng.integers(0, 2, len(d)).astype(float)
    y = 0.2 + d.permno * 0.01 + 0.05 * d.news0 + rng.normal(0, 0.0001, len(d))
    for c in SCORES:
        d[c] = y
    result, fit, _ = estimate(d)
    assert result.loc[result.event_day == 0, "coefficient"].item() == pytest.approx(0.05, abs=0.001)
    assert fit.nobs == len(d)
