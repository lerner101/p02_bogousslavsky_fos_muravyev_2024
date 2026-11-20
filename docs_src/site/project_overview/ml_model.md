# Estimating the project's own ITI(13D)

This workflow implements the main Schedule 13D model described in Section 3.1
and the 41 variables in Table IA.3 of the attached forthcoming-paper PDF. It
uses the group's reconstructed filing labels. No posted author score is used
as a feature, training target, tuning criterion, or feature-selection criterion.

The market-data scope is 2004–2019. 2004 supplies warm-up; training filings are
2005–2018, and scores begin in 2005. The primary sample includes all screened
events. An author-window-matched subset is a sensitivity analysis, not recovered
author transaction ground truth. The extraction audits still need human review.

## Explicit execution

Use the project's Python 3.13 environment from the repository root:

```bash
python src/collect_iti_taq.py --pilot
python src/run_iti_pipeline.py --collect --workers 4
```

The second command is an extended WRDS run. It collects only training histories
and ten scoring stocks, then builds features, runs nested tuning, fits the model,
scores stock-days and generates comparisons. It records progress in
`_output/ml_model/run_status.json`. Keep the computer awake. To interrupt, use
Ctrl+C; rerunning resumes completed TAQ days. Do not run concurrent collectors
against the same destination. `--workers` allows 1–4 read-only connections.

Individual stages are also available:

```bash
python src/collect_iti_taq.py --max-days 8 --workers 4
python src/build_iti_features.py
python src/train_iti.py --jobs 2
python src/score_iti.py
python src/compare_iti.py
```

The first command is bounded and does not provide a full training sample.
`build_iti_features.py --allow-partial` produces coverage diagnostics, but the
trainer refuses those partial acquisitions. Doit tasks `iti_taq_pilot`,
`iti_collect`, `iti_features`, `iti_train`, `iti_score`, and `iti_compare` expose
the same stages. Acquisition and model fitting are explicit; the existing
default `doit` build is unchanged. Full-universe acquisition is not implemented
as a default or launched by this workflow; review pilot cost before expanding.

## Feature contract

All features below are standardized by stock using the preceding 252 CRSP
trading observations, excluding today, with at least 200 nonmissing values.
The denominator is sample SD (ddof=1). Zero variance and nonfinite values remain
missing. All 41 feature columns are retained. Following the user's explicit
approval, only `noddlot` may be missing and is handled natively by XGBoost;
the other 40 standardized inputs must be observed. No zero/mean imputation is
performed. `all_41_complete` preserves the stricter coverage diagnostic.
Dollar-depth fields were verified against the WRDS
column descriptions on November 18, 2026. The local original extracts omitted
them, so the supplemental collector obtains them separately.
For bounded histories, a gap longer than seven calendar days resets the rolling
history so a new acquisition segment cannot borrow stale earlier observations.

The `n_oddlot_trade` source is missing on nearly all local 2004–2012 observations
(2007 contains one nonmissing day) and mostly missing in 2013. See the generated
`oddlot_source_coverage.csv`. This is a data-availability issue: consolidated-tape reporting
of odd lots began in late 2013 ([SEC discussion](https://www.sec.gov/about/odd-lot-rates-post-transparency-world)).
The paper does not disclose its handling of this historical feature gap. Native
missing-value routing for this feature is an approved implementation choice;
strict complete-case filtering would eliminate the intended early training folds.

| Feature | Definition / source before standardization |
|---|---|
| ret | CRSP daily return, decimal |
| prc | Absolute CRSP daily closing price, dollars |
| ret_ov | 10:00 midquote / split-adjusted previous CRSP close − 1 |
| ret_in | 16:00 / 10:00 midquote − 1 |
| ret_am | 12:00 / 10:00 midquote − 1 |
| ret_pm | 16:00 / 14:00 midquote − 1 |
| es | IID effectivespread_percent_dw |
| rs | IID percentrealizedspread_lr_dw |
| pi | IID percentpriceimpact_lr_dw |
| qs | IID quotedspread_percent_tw |
| lambda1 | IID tsignsqrtdvol1, with intercept |
| lambda2 | IID tsignsqrtdvol2, without intercept |
| illiq_in | Mean absolute 30-minute return / interval share volume, 10:00–16:00; zero-volume intervals excluded |
| illiq_ov | Absolute overnight return / 09:30–10:00 share volume; zero if volume is zero |
| depth_dollar | Sum of IID time-weighted offer and bid dollar depth |
| depth_imb | IID time-weighted offer minus bid dollar depth |
| ret_abs | Absolute CRSP daily return |
| ret_ov_abs | Absolute overnight return |
| ret_in_abs | Absolute intraday return |
| rvol_in | Square root of sum of twelve squared 30-minute returns, 10:00–16:00 |
| rvol | Square root of overnight squared return plus intraday realized variance |
| ivol_q | IID second-by-second quote volatility, unchanged source units |
| ivol_t | IID second-by-second trade volatility, unchanged source units |
| var_ratio15s | IID var_ratio1, 15-second / (3 × 5-second) |
| var_ratio1mn | IID var_ratio2, 1-minute / (4 × 15-second) |
| autocorr_in | Lag-one Pearson autocorrelation of the twelve intraday returns |
| ov_last | Overnight return × 15:30–16:00 return |
| svol | CRSP daily share volume |
| svol_am | Share volume, 10:00–12:00 |
| svol_pm | Share volume, 14:00–16:00 |
| trade_n30 | IID n30_pos |
| trade_n5 | IID n5_pos |
| ntrades_oc | IID total_n_trades_m, market hours |
| ntrades_post | IID total_n_trades_a, after market close |
| noddlot | IID n_oddlot_trade, market hours |
| hindex | IID hindex, 30-minute volume concentration |
| svol_imb | IID buyvol_lr − sellvol_lr, shares |
| svol_imb_abs | Absolute share-volume imbalance |
| ntrades_imb | IID buynumtrades_lr − sellnumtrades_lr |
| ntrades_imb_abs | Absolute trade-count imbalance |
| vwap_imb | IID vwavg_buy_price_lr − vwavg_sell_price_lr, dollars |

Supplemental midpoint endpoints use WRDS complete NBBO, positive bid and ask,
uncrossed quotes, and positive bid/ask sizes. They use the last valid same-day
quote at or before the endpoint, no more than 30 minutes old. Share volume uses
positive-price, positive-size uncorrected trades (tr_corr=00) with regular/odd-lot
sale conditions blank/@/E/F/I. Odd lots contribute to interval volume whenever
reported. Endpoints use sub-microsecond ordering where available and deterministic
bid/ask/size tie breaks for otherwise equal timestamps. Bins are left-closed/right-open, with the final bin
including exactly 16:00. Early-close days without the required endpoints remain
incomplete. Overnight prices are adjusted using CRSP cfacpr; do not carry an
unadjusted price across a split. Ambiguous symbol/PERMNO links are excluded.

The PDF does not fully specify quote filtering, staleness cutoffs, early closes,
morning-volume boundaries, the standardization observation count, the objective,
or the tuning grid. The choices above and below are explicit implementation
conventions, not recovered author code. IID depth also inherits WRDS's cleaning
rules, which need not exactly match the authors' Holden–Jacobsen implementation.
These limitations prevent a claim of bit-for-bit reproduction even with all 41
feature names present. No unavailable feature is silently approximated.
The saved pilot volume reconciliation compares the retained trade volumes with
IID total market-hours volume: the three early-day stocks match, while the
three late-day ratios are approximately 0.967, 0.901, and 0.834. The regular/odd-lot
sale-condition screen excludes other reported transaction conditions; this is
a documented cleaning convention, not evidence of exact author volume parity.

## Training and evaluation

The binary target is `itrade`: a disclosed buy or sell on that filing-day.
Five outer folds are consecutive blocks of filing dates. Filings remain intact;
connected overlapping windows for the same stock cannot cross a fold boundary.
Folds are established before feature attrition. Each outer training sample has
five inner calendar folds; each inner validation loss is evaluated on data not
used to fit that candidate. This follows the paper's calendar-block evaluation,
not a strictly forward-only deployment backtest.

Candidates use `binary:logistic` and histogram tree construction on CPU. The
grid is max_depth {2,3,4}, learning_rate {0.03,0.1}, n_estimators {200,500}, and
min_child_weight {1,10}. Select the lowest mean inner-fold log loss; fixed grid
ordering breaks ties. Fix subsample=1, colsample_bytree=1, reg_lambda=1,
reg_alpha=0, seed=42, and two CPU threads. The paper does not disclose this grid.
After outer evaluation, tune again on all training data and fit the extrapolation
model. The author-window sensitivity uses only the corresponding outer-training
selected settings, preserving the outer holdout.

Artifacts under `_data/derived/ml_model/` include raw/scaled features, complete
case flags, filing fold assignments, outer and final XGBoost JSON models, model
and feature manifests, held-out filing/PERMNO/date predictions, and extrapolated
PERMNO/date scores. Fingerprints and installed package versions support audit.
Scores lie in [0,1]; they are measures of realized trading, not forecasts or
calibrated population probabilities of illegal trading.

## Comparisons

`_output/ml_model/` contains coverage/attrition tables, tuning results, model
metrics, and score comparisons. The authors' original vintage is matched on
PERMNO/date through July 2019. Both series use identical eligible stock-days,
requiring common shares, preceding-month closing price >$5 and market cap >$100M.
Reconstructed training windows are excluded from score agreement, including
days dropped from training for missing features. Posted author blanks also remove
their training windows where those scores are unavailable; window recovery is
approximate, so this comparison is not an independent generalization experiment.

Plots include score density agreement, distributions, yearly means/correlations,
held-out trade/non-trade distributions, yearly AUC, and held-out metrics against
Table IA.6 (AUC .7084, log loss .5940, MAE .3763). Earnings regressions use the same
common sample for both scores, volume-adjusted Compustat announcement dates,
stock effects and stock/date clustered intervals. The bounded acquisition is
selected around activist events and is not representative of the full universe.
Published metric equality is not a tuning or success criterion.

Run `python -m pytest -q tests/test_iti_model.py` for deterministic checks of
historical scaling, split handling, interval aggregation, overlapping-window
fold separation, nested tuning, model serialization, and training-window flags.
