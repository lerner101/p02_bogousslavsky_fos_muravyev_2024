"""Replication tolerance tests: committed outputs vs the paper's published values.

The acceptance rule (same sign, within a factor of 3; looser when the paper's
estimate is insignificant) lives in src/replication_scorecard.py and is shared
with the report. Comparisons we know miss are listed in KNOWN_MISSES with the
reason, and run as strict xfails: if one starts passing, the test suite says so.
Runs in CI because it only reads files committed under _output/.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import replication_scorecard as sc  # noqa: E402

KNOWN_MISSES = {
    ("Table 5", "col 3: ret*ES%"): "Effective-spread interaction 3.4x the paper; WRDS IID spread definition differs.",
    ("Table 10", "col 2: ITI(insider)"): "ITI(insider) does not predict returns in our 2005-2019 window.",
    ("Table 10", "col 4: ITI(insider)"): "Same as column 2.",
    ("Table 11", "ITI(13D) H-L FF4 alpha"): "0.33x the paper (boundary); right sign and significant.",
    ("Table 11", "ITI(insider) H-L raw"): "ITI(insider) spread is flat after 2005.",
    ("Table 11", "ITI(insider) H-L FF4 alpha"): "Same as raw.",
    ("Table 11", "ITI(patient) H-L raw"): "Right sign; 0.29x the paper and insignificant.",
    ("Table 11", "ITI(patient) H-L FF4 alpha"): "Right sign; 0.29x the paper and insignificant.",
    ("Figure 2", "ITI change across volatility range"): "Our model's partial dependence on volatility is flat.",
    ("Figure 4(b)", "small day -1"): "Small-surprise pre-announcement bump 3.6x the paper; tiny base value.",
}

CARD = sc.build()
SCORED = CARD[CARD.status.isin(["pass", "fail"])]


def _params():
    for r in SCORED.itertuples():
        key = (r.exhibit, r.item)
        marks = [pytest.mark.xfail(strict=True, reason=KNOWN_MISSES[key])] if key in KNOWN_MISSES else []
        yield pytest.param(r.exhibit, r.item, r.status, id=f"{r.exhibit} | {r.item}", marks=marks)


@pytest.mark.parametrize("exhibit,item,status", list(_params()))
def test_within_tolerance(exhibit, item, status):
    assert status == "pass", f"{exhibit} {item} outside the x{sc.RATIO_BAND:g} band"


def test_known_misses_still_exist():
    """Every documented miss must refer to a scored comparison."""
    keys = set(zip(SCORED.exhibit, SCORED.item))
    assert set(KNOWN_MISSES) <= keys


def test_judge_rule():
    assert sc.judge(0.5, 1.0)[0] == "pass"
    assert sc.judge(0.3, 1.0)[0] == "fail"
    assert sc.judge(-1.0, 1.0)[0] == "fail"
    # Paper insignificant: ours may differ in sign if also insignificant.
    assert sc.judge(-0.1, 0.1, paper_t=1.0, ours_t=-0.5)[0] == "pass"
    assert sc.judge(-0.1, 0.1, paper_t=1.0, ours_t=-3.0)[0] == "fail"


def test_headline_results_hold():
    """The paper's main claims, stated as directions, all hold in our data."""
    card = CARD.set_index(["exhibit", "item"])
    # ITI(13D) predicts next-month returns positively (Table 10 col 1).
    assert card.loc[("Table 10", "col 1: ITI(13D)"), "ours_t"] > sc.T_CRIT
    # Less reversal on high-ITI days (Table 5 col 2 interaction).
    assert card.loc[("Table 5", "col 2: ret*ITI(13D)"), "ours_t"] > sc.T_CRIT
    # ITI spikes on earnings and M&A day 0.
    assert card.loc[("Figure 4(a)", "day +0"), "ours"] > card.loc[("Figure 4(a)", "day -2"), "ours"]
    assert card.loc[("Figure IA.5", "day +0"), "ours"] > 0.1
