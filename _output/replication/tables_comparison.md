# Tables 1–4: project estimates and published comparisons

All regression ITIs are our held-out project estimates. Author scores enter only the explicitly labeled Table 1 benchmark rows; published coefficients never enter estimation.

## Table 1: coverage and provenance

The local supplemental-feature acquisition contains 582,754 stock-days. After the saved eligibility screens, excluding all reconstructed 13D windows, and requiring the eight table controls, 408,471 remain (2005-01-03 00:00:00 to 2019-07-31 00:00:00). Our final model scores 127,573 of these; 125,982 also have author ITI(13D). Our scored dates span 2005-01-03 00:00:00 to 2019-07-31 00:00:00.

**This is an available-data descriptive table, not the paper’s full-market Table 1.** Supplemental acquisition was bounded around requested stocks and events. Table 1 follows the existing 2005–July 2019 comparison window; 2004 provides feature warm-up. Missing project scores remain missing. The saved full model is reused; no author-score fallback or zero imputation is applied. The author-overlap row provides a comparison restricted to our scored days. Published Table 1 statistics refer to a substantially broader sample, so differences include selection and coverage effects.

| variable                                | source                  |    mean |      sd |   sd_within |      n |   paper_mean |
|:----------------------------------------|:------------------------|--------:|--------:|------------:|-------:|-------------:|
| es                                      | project controls        | 0.00214 | 0.00270 |     0.00206 | 408471 |    nan       |
| lambda                                  | project controls        | 0.00214 | 0.00656 |     0.00622 | 408471 |    nan       |
| depth                                   | project controls        | 0.00003 | 0.00004 |     0.00003 | 408471 |    nan       |
| rvol                                    | project controls        | 0.02202 | 0.01739 |     0.01590 | 408471 |    nan       |
| turn                                    | project controls        | 0.01116 | 0.01516 |     0.01258 | 408471 |    nan       |
| oi                                      | project controls        | 0.00009 | 0.00236 |     0.00229 | 408471 |    nan       |
| abs_oi                                  | project controls        | 0.00120 | 0.00213 |     0.00201 | 408471 |    nan       |
| ret                                     | project controls        | 0.00008 | 0.02746 |     0.02742 | 408471 |    nan       |
| Project ITI(13D)                        | project final model     | 0.34351 | 0.08526 |     0.07749 | 127573 |      0.27450 |
| Author ITI(13D)                         | posted author benchmark | 0.29459 | 0.16109 |     0.15677 | 396792 |      0.27450 |
| Author ITI(insider)                     | posted author benchmark | 0.47781 | 0.15689 |     0.15368 | 383682 |      0.47860 |
| Author ITI(short)                       | posted author benchmark | 0.41466 | 0.06691 |     0.06307 | 386338 |      0.44600 |
| Author ITI(patient)                     | posted author benchmark | 0.22392 | 0.15053 |     0.14637 | 396792 |      0.20380 |
| Author ITI(impatient)                   | posted author benchmark | 0.42092 | 0.13344 |     0.12843 | 396792 |      0.42130 |
| Project ITI(13D), author-scored overlap | project final model     | 0.34356 | 0.08510 |     0.07734 | 125982 |    nan       |
| Author ITI(13D), project-scored overlap | posted author benchmark | 0.30166 | 0.16355 |     0.15532 | 125982 |    nan       |
| 13D trade (13D sample)                  | project held-out labels | 0.37886 | 0.48511 |     0.41564 |  65752 |      0.36030 |

## Regression samples and fit

The held-out sample has 65,752 filing-days in 1,655 filings, 2005-01-03–2018-12-31.

|   table | column      |   observations |   filings |   within_r2 |   adjusted_within_r2 |
|--------:|:------------|---------------:|----------:|------------:|---------------------:|
|       2 | 1           |          65752 |      1655 |     0.07971 |              0.07970 |
|       2 | 2           |          65752 |      1655 |     0.03652 |              0.03640 |
|       2 | 3           |          65752 |      1655 |     0.08286 |              0.08273 |
|       2 | 4           |          24911 |      1644 |     0.00012 |              0.00008 |
|       2 | 5           |          24911 |      1644 |     0.00007 |             -0.00027 |
|       2 | 6           |          24911 |      1644 |     0.00015 |             -0.00024 |
|       3 | 1           |          65752 |      1655 |     0.07971 |              0.07970 |
|       3 | 2           |          65752 |      1655 |     0.05367 |              0.05365 |
|       3 | 3           |          65752 |      1655 |     0.04108 |              0.04106 |
|       3 | 4           |          65752 |      1655 |     0.03626 |              0.03625 |
|       3 | 5           |          65752 |      1655 |     0.05650 |              0.05648 |
|       3 | 6           |          65752 |      1655 |     0.08054 |              0.08048 |
|       4 | a: ITI      |           2156 |       695 |     0.00829 |              0.00761 |
|       4 | a: turnover |           2156 |       695 |     0.00000 |             -0.00068 |
|       4 | b1          |           2156 |       695 |     0.00829 |              0.00761 |
|       4 | b2          |           2156 |       695 |     0.00647 |              0.00168 |
|       4 | b3          |           2156 |       695 |     0.01464 |              0.00922 |

Tables 2–4 absorb filing fixed effects and cluster standard errors by filing, reusing the repository estimator. It uses a G/(G−1) cluster correction; no additional software-specific degrees-of-freedom multiplier is imposed. Raw within R² and adjusted within R² are exported separately. The latter uses residual degrees of freedom n−filings−regressors and within-total degrees of freedom n−filings. Published adjusted R² may follow different software conventions.

Table 2 uses the same complete-control rows for columns 1–3; columns 4–6 additionally require a trade day and observed filer turnover. All controls are pooled-winsorized at 0.05%/99.95%; ITI and filer turnover are not winsorized. The eight printed table controls are used, rather than the nine-control Figure 1 caption specification. Controls use Figure 1 definitions: summed bid/ask share depth divided by CRSP shares outstanding, share volume and signed share imbalance divided by shares outstanding, lambda multiplied by 1,000, and the saved raw realized-volatility feature.

Table 4 matches raw CRSP turnover within filing, without replacement, taking the smallest absolute gaps first. All pairs satisfy |turnover difference| ≤ 0.00002 and contain one trade day and one non-trade day. Matching starts with complete-control observations so all panels use the same matched rows. The paper does not fully specify tie-breaking or replacement; this deterministic greedy rule is an implementation choice.

## Table 2: turnover definition and extraction sensitivity

The saved labels contain a dollar-volume/market-value proxy. The primary table instead computes (shares bought + shares sold) / (CRSP shares outstanding × 1,000), matching the paper’s share-turnover definition. The saved labels and trained full model are unchanged. The legacy proxy is retained only as a sensitivity.

| measure              |   trade_days |   above_one |       mean |   median |      p99 |            max |
|:---------------------|-------------:|------------:|-----------:|---------:|---------:|---------------:|
| 13Dturn              |        24911 |           3 |   0.006412 | 0.000828 | 0.025753 |      45.890870 |
| 13Dturn_dollar_proxy |        24911 |           9 | 401.523602 | 0.000809 | 0.025657 | 5395205.777405 |

**Unverified extracted quantities materially affect the turnover regressions.** Three trade days have gross reported shares exceeding total outstanding shares, and the legacy dollar proxy has nine values above one. These are diagnostic flags, not an automatic proof of error. The primary table retains them; the 0.05%/99.95% winsorized and at-most-100% turnover checks are separately labeled sensitivity results. Neither trimming rule is silently substituted for the paper specification. The binary trading-day results do not depend on these turnover amounts, although independent trade-label verification remains outstanding.

| specification                          |    coef |        t |
|:---------------------------------------|--------:|---------:|
| raw share turnover (primary)           | 0.04612 |  1.62783 |
| share turnover winsorized 0.05%/99.95% | 0.01770 | 18.49563 |
| share turnover at most 100%            | 0.01779 | 17.96836 |
| legacy dollar turnover proxy           | 0.05286 |  1.83849 |

## Table 3: feature-group models

Four new group models use the original sample and outer-fold assignments, with nested five-fold selection over the original 24-candidate grid. No outer validation outcomes enter tuning. Overlapping stock-days may not cross outer folds. Only historically unavailable odd-lot counts may remain missing, using native XGBoost routing as in the approved full model.

| group      |   roc_auc |   log_loss |   features |
|:-----------|----------:|-----------:|-----------:|
| return     |   0.57893 |    0.64751 |          6 |
| liquidity  |   0.61103 |    0.64046 |         10 |
| volatility |   0.56758 |    0.64978 |         11 |
| volume     |   0.61769 |    0.64181 |         14 |

## Published coefficient comparisons

|   table | column      | variable         |   project_coef |   project_t |   paper_coef |   paper_t |
|--------:|:------------|:-----------------|---------------:|------------:|-------------:|----------:|
|       2 | 1           | ITI              |        1.24021 |    35.33171 |      0.69700 |  43.57200 |
|       2 | 1           | Adj. R2 (within) |        0.07970 |   nan       |      0.09860 | nan       |
|       2 | 2           | es               |       -5.81051 |    -4.56743 |     -3.41200 |  -4.05300 |
|       2 | 2           | lambda           |       -1.99169 |    -3.89736 |     -1.18600 |  -4.82200 |
|       2 | 2           | depth            |      108.08249 |    11.22802 |     34.36000 |   8.99600 |
|       2 | 2           | rvol             |       -0.41210 |    -3.31771 |     -0.83200 |  -6.14900 |
|       2 | 2           | turn             |        0.92471 |     7.39136 |      1.37700 |   9.84500 |
|       2 | 2           | oi               |        0.04355 |     0.07969 |      0.37900 |   0.74800 |
|       2 | 2           | abs_oi           |        7.26577 |    10.86124 |      6.73200 |  10.53400 |
|       2 | 2           | ret              |       -0.25490 |    -4.47667 |     -0.08300 |  -1.25800 |
|       2 | 2           | Adj. R2 (within) |        0.03640 |   nan       |      0.04610 | nan       |
|       2 | 3           | ITI              |        1.12153 |    28.69307 |      0.60400 |  36.64800 |
|       2 | 3           | es               |       -1.68422 |    -1.43208 |     -0.80700 |  -1.09800 |
|       2 | 3           | lambda           |        0.43883 |     0.99119 |     -0.58900 |  -2.59900 |
|       2 | 3           | depth            |       64.03031 |     8.19978 |     21.32300 |   8.03700 |
|       2 | 3           | rvol             |       -0.08371 |    -0.83173 |     -0.36100 |  -3.47500 |
|       2 | 3           | turn             |        0.26065 |     2.81718 |      0.64000 |   6.11000 |
|       2 | 3           | oi               |       -0.28166 |    -0.65231 |      0.29400 |   0.70300 |
|       2 | 3           | abs_oi           |        0.38811 |     0.69869 |      2.61300 |   4.78100 |
|       2 | 3           | ret              |       -0.07699 |    -1.42989 |     -0.03000 |  -0.51100 |
|       2 | 3           | Adj. R2 (within) |        0.08273 |   nan       |      0.10730 | nan       |
|       2 | 4           | ITI              |        0.04612 |     1.62783 |      0.00700 |  22.18400 |
|       2 | 4           | Adj. R2 (within) |        0.00008 |   nan       |      0.06920 | nan       |
|       2 | 5           | es               |        0.21064 |     2.34290 |      0.09900 |   3.17900 |
|       2 | 5           | lambda           |       -0.04695 |    -3.33544 |     -0.02400 |  -5.27500 |
|       2 | 5           | depth            |       -2.79838 |    -1.06501 |     -0.09600 |  -1.13500 |
|       2 | 5           | rvol             |       -0.02869 |    -0.98652 |      0.00000 |   0.11100 |
|       2 | 5           | turn             |        0.04540 |     2.78397 |      0.03900 |   8.28400 |
|       2 | 5           | oi               |       -0.05350 |    -0.46769 |      0.07300 |   3.06500 |
|       2 | 5           | abs_oi           |        0.25606 |     3.54050 |      0.18000 |   6.32900 |
|       2 | 5           | ret              |        0.00468 |     0.42500 |     -0.00800 |  -3.37500 |
|       2 | 5           | Adj. R2 (within) |       -0.00027 |   nan       |      0.25790 | nan       |
|       2 | 6           | ITI              |        0.04099 |     1.24596 |      0.00400 |  13.65700 |
|       2 | 6           | es               |        0.29006 |     1.92872 |      0.10800 |   3.50500 |
|       2 | 6           | lambda           |        0.06344 |     0.75173 |     -0.02000 |  -4.67300 |
|       2 | 6           | depth            |       -3.53235 |    -1.10133 |     -0.13200 |  -1.60300 |
|       2 | 6           | rvol             |       -0.02601 |    -0.96795 |      0.00100 |   0.32900 |
|       2 | 6           | turn             |        0.03240 |     4.70543 |      0.03700 |   7.88500 |
|       2 | 6           | oi               |       -0.07161 |    -0.55877 |      0.07100 |   3.09200 |
|       2 | 6           | abs_oi           |        0.07171 |     0.79331 |      0.16100 |   5.81100 |
|       2 | 6           | ret              |        0.01247 |     0.72738 |     -0.00700 |  -3.06400 |
|       2 | 6           | Adj. R2 (within) |       -0.00024 |   nan       |      0.27560 | nan       |
|       3 | 1           | ITI              |        1.24021 |    35.33171 |      0.69700 |  43.57200 |
|       3 | 1           | Adj. R2 (within) |        0.07970 |   nan       |      0.09860 | nan       |
|       3 | 2           | ITI(liquidity)   |        1.17613 |    26.38026 |      0.59600 |  24.56100 |
|       3 | 2           | Adj. R2 (within) |        0.05365 |   nan       |      0.04120 | nan       |
|       3 | 3           | ITI(return)      |        1.18247 |    25.13775 |      0.51000 |  18.96300 |
|       3 | 3           | Adj. R2 (within) |        0.04106 |   nan       |      0.02640 | nan       |
|       3 | 4           | ITI(volatility)  |        1.20516 |    22.00157 |      0.49800 |  19.26600 |
|       3 | 4           | Adj. R2 (within) |        0.03625 |   nan       |      0.02780 | nan       |
|       3 | 5           | ITI(volume)      |        1.15414 |    34.75577 |      0.67100 |  39.23500 |
|       3 | 5           | Adj. R2 (within) |        0.05648 |   nan       |      0.07690 | nan       |
|       3 | 6           | ITI(liquidity)   |        0.46998 |    10.13750 |      0.28900 |  17.94500 |
|       3 | 6           | ITI(return)      |        0.60679 |    13.51793 |      0.23900 |  14.25600 |
|       3 | 6           | ITI(volatility)  |        0.14428 |     2.58423 |      0.20800 |  12.91200 |
|       3 | 6           | ITI(volume)      |        0.68789 |    20.89529 |      0.52600 |  36.53300 |
|       3 | 6           | Adj. R2 (within) |        0.08048 |   nan       |      0.10430 | nan       |
|       4 | a: turnover | itrade           |        0.00000 |     1.02293 |      0.00000 |   1.02700 |
|       4 | a: ITI      | itrade           |        0.00790 |     4.15233 |      0.03300 |   5.25300 |
|       4 | b1          | ITI              |        1.04888 |     4.14043 |      0.50900 |   5.44500 |
|       4 | b3          | ITI              |        1.15088 |     4.08847 |      0.50700 |   5.28400 |

The project uses shorter dates, reconstructed labels, bounded supplemental acquisition, and documented feature conventions. These estimates are a replication on available data, not an exact reproduction of the published sample. Insider and short-interest training samples and project-specific patient/impatient variants are not estimated here.

Reproduce with `python -m doit tables`, `python -m doit iti_train_groups`, `python -m doit table3`, then `python -m doit tables_report`. Completed feature groups are reused only when input fingerprints and held-out keys match. A partially trained group is rerun; completed groups are retained.
