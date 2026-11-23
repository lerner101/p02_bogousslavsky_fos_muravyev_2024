# Project ITI(13D) comparison

Training sample: 65,752 filing-day observations from 1,655 filings (2005–2018).
Scored sample: 191,040 eligible stock-days (2005–2019).
Common comparison sample: 125,982 stock-days, 1180 stocks.

Scores use the full 41-feature specification. Training uses reconstructed 2005–2018 labels and nested calendar-fold evaluation.
Only odd-lot count may be missing and is handled natively by XGBoost; the other 40 features must be observed. This approved choice differs from the original complete-case plan.
Author scores are the original vintage through July 2019. Reconstructed training windows are excluded from score agreement.
Author training-window recovery is approximate; score agreement is a replication diagnostic, not independent ground truth.

## Agreement on matched stock-days

|              |         value |
|:-------------|--------------:|
| rows         | 125982        |
| stocks       |   1180        |
| mae          |      0.117064 |
| rmse         |      0.142715 |
| pearson      |      0.552442 |
| spearman     |      0.524986 |
| project_mean |      0.343557 |
| author_mean  |      0.301662 |

## Held-out performance

|          |   project |   paper_IA6 |
|:---------|----------:|------------:|
| roc_auc  |  0.635013 |      0.7084 |
| log_loss |  0.631536 |      0.594  |
| mae      |  0.442335 |      0.3763 |

## Author-window training sensitivity

| sample                   | fold   |   rows |   roc_auc |   log_loss |      mae |
|:-------------------------|:-------|-------:|----------:|-----------:|---------:|
| primary                  | pooled |  65752 |  0.635013 |   0.631536 | 0.442335 |
| author_window_subset     | pooled |  31847 |  0.648111 |   0.622177 | 0.432105 |
| primary_on_author_subset | pooled |  31847 |  0.656443 |   0.62047  | 0.436218 |

Earnings regression: 125,982 common stock-days, 1180 stocks; stock FE and stock/date clustered intervals. Day-zero coefficients relative to non-event days: project 0.0939, author 0.1438 ITI units.

The bounded scoring sample contains training-history stocks and ten long-coverage scoring stocks; it is not the full stock universe.
Paper and project training labels, sample periods, and undocumented implementation choices differ; matching published performance is not an acceptance criterion.
