# Tables 1–4 from local project data

This extends the code in PR #9 with a real-data run, source checks, explicit
score provenance, turnover diagnostics, and a published-results comparison.
All regression ITIs come from our project models. Published coefficients and
author scores are benchmarks only.

## Run

From the repository root, using the existing project virtual environment:

```bash
python -m doit tables            # Tables 1, 2, 4; uses existing data and scores
python -m doit iti_train_groups  # Four additional feature-group training runs
python -m doit table3            # Requires completed feature-group predictions
python -m doit tables_report     # Validate and compare all four completed tables
```

These commands do not acquire data or retrain the original full-feature model.
Run the group-training command while the computer remains awake. It defaults
to two XGBoost threads, retains completed groups, and checks source/input
fingerprints and saved held-out keys before reusing a checkpoint. Each group
uses all five outer folds and the original nested five-fold, 24-candidate grid.
The group checkpoint and complete tuning audit remain under ignored
`_data/derived/ml_model/`. An interrupted group restarts from its beginning;
previously completed groups do not need to be trained again. If only one of
the prediction/report checkpoint files exists or fingerprints differ, the
script stops for inspection rather than mixing incompatible runs.

## Samples and definitions

Table 1 builds `_data/derived/panel/table1_local.parquet` from the existing
raw-feature stock-days, saved eligibility flags, CRSP/IID controls, our final
model scores, and posted author series. It does not build or overwrite the
legacy full-market `daily.parquet` panel. It uses the existing 2005–July 2019
comparison window, excludes all reconstructed 13D windows, and requires all
eight controls. The limited supplemental acquisition prevents a full-market
Table 1 replication. Project scores remain missing when unavailable; author
scores never fill those gaps. Each descriptive row reports its own N, and an
additional author ITI(13D) row uses the project-scored overlap. The label mean
uses the actual held-out project sample. Other author ITI variants are
explicitly labeled benchmarks, not project-trained variants.

Tables 2–4 reuse the original held-out 13D sample and the eight controls printed
in the paper's tables, with filing fixed effects and standard errors clustered
by filing. The nine-control Figure 1 caption specification is not used here.
Raw within R², adjusted within R², observation counts, and filing counts are
exported separately. The adjusted within statistic uses n−filings−regressors
residual degrees of freedom. The repository estimator's cluster correction is
G/(G−1); software-specific additional small-sample adjustments may differ from
the paper.

Table 2 computes filer turnover as gross shares bought and sold divided by
CRSP shares outstanding (CRSP `shrout` is in thousands), following the paper's
share-turnover definition. The saved label field instead uses transaction
dollars divided by market capitalization. That proxy can be especially
sensitive to extracted prices and is preserved only as a diagnostic sensitivity.
The saved labels and original model are unchanged. Primary coefficients retain
untrimmed filer turnover. Separate sensitivity results apply 0.05%/99.95%
winsorization to the outcome, exclude turnover above 100%, or use the legacy
dollar proxy. Extreme extracted quantities materially affect the turnover
regressions; independent transaction/label verification remains outstanding.
Flagged filing-day details are saved locally in the ignored
`_data/derived/ml_model/table2_quantity_audit.parquet` for source verification.

Table 3 compares liquidity, return, volatility, and volume subset models, trained
using the same sample and folds as our full ITI. Only the odd-lot feature may be
missing, with native XGBoost routing. Training/tuning never reads author ITI.

Table 4 uses raw CRSP turnover and greedy closest-gap matching within filing,
without replacement, with a maximum absolute gap of 0.00002. Ties follow the
stable input order. Matching starts with complete-control rows so all panels
use the same observations. Replacement and tie-breaking are not fully specified
in the paper and remain explicit implementation choices.

## Reviewable outputs

`_output/replication/table1.csv` contains descriptive statistics with source
labels. Tables 2–4 retain the existing long `(column, variable, coef, t)` format.
The directory also contains:

- `tables_comparison.md`: results, sample counts, methods, and limitations.
- `tables_comparison.csv` and `table1_comparison.csv`: published benchmarks beside project estimates.
- `table1_coverage.json`: eligibility, control, project-score, and overlap counts.
- `table2_turnover_diagnostics.csv` and `table2_turnover_sensitivity.csv`: aggregate quantity diagnostics and alternative outcomes.
- `table3_model_performance.csv`: feature-group held-out performance.
- `tables_manifest.json`: input/output SHA-256 fingerprints and tuning audit.

Raw data, transaction rows, trained models, and stock-day predictions remain
ignored locally. The table outputs and aggregate reports can be reviewed with
the code changes before committing.
