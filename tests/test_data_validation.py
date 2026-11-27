"""Data validation: check the data against independent benchmarks, not the code.

Tolerances live in src/validation_exhibits.VALIDATION_TOLERANCES (also shown
in the report's validation table). Reads only committed _output/ files.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import validation_exhibits as ve  # noqa: E402

TOL = ve.VALIDATION_TOLERANCES
S = ve.summarize()


def test_13d_trade_frequency_matches_paper():
    """Share of window days with a 13D trade is a direct property of the filings."""
    assert abs(S["itrade_ours"] - S["itrade_paper"]) <= TOL["itrade_abs_diff"]


def test_filers_trade_more_often_near_the_deadline():
    """The 10-day filing deadline makes the last 20 days busier (paper Sec. 4.1)."""
    assert S["impatient_minus_patient_ours"] > 0


def test_taq_volume_reconciles_with_iid():
    """Our TAQ bucket sum vs WRDS IID total_vol_m on the pilot days."""
    lo, hi = TOL["volume_ratio_band"]
    assert lo <= S["volume_ratio_min"] and S["volume_ratio_max"] <= hi


def test_no_coverage_break_in_training_years():
    cov = ve.coverage()
    train = cov[cov.year.isin(ve.TRAIN_YEARS)]
    assert sorted(train.year) == list(ve.TRAIN_YEARS), "a training year is missing entirely"
    assert (train.fraction >= TOL["min_input_coverage"]).all()


def test_scored_universe_matches_authors_file():
    assert S["min_author_match"] >= TOL["min_author_match"]


def test_our_iti_agrees_with_authors_iti_every_year():
    assert S["min_yearly_pearson"] >= TOL["min_yearly_pearson"]
