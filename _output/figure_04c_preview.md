# News-event regression

PRELIMINARY: raw earnings dates; no control completeness screen

```json
{
  "mode": "PRELIMINARY: raw earnings dates; no control completeness screen",
  "observations": 1127042,
  "stocks": 678,
  "date_range": [
    "2005-01-03",
    "2015-12-23"
  ],
  "earnings_window_rows_excluded_full_news_history": 99578,
  "iti": "Original posted ITI(impatient); all three 13D scores required nonmissing",
  "earnings_input": "/Users/aarbitman/Desktop/Data Pipelines for Quantitative Research/p02_bogousslavsky_fos_muravyev_2024/_data/derived/bfkr/earnings_unadjusted.parquet",
  "control_input": null,
  "specification": "Stock fixed effects; stock/date clustered SE; intervals +/-2 SE",
  "limitations": [
    "Default sample starts 2005; screenshot starts 2000",
    "Ticker links with ambiguity are excluded",
    "Preview does not apply the paper's complete control/universe screens"
  ]
}
```

```text
                          PanelOLS Estimation Summary                           
================================================================================
Dep. Variable:         ITI(impatient)   R-squared:                        0.0047
Estimator:                   PanelOLS   R-squared (Between):             -0.2223
No. Observations:             1127042   R-squared (Within):               0.0047
Date:                Sun, Nov 08 2026   R-squared (Overall):             -0.0007
Time:                        21:42:16   Log-likelihood                 6.784e+05
Cov. Estimator:             Clustered                                           
                                        F-statistic:                      483.79
Entities:                         678   P-value                           0.0000
Avg Obs:                       1662.3   Distribution:              F(11,1126353)
Min Obs:                       1.0000                                           
Max Obs:                       2552.0   F-statistic (robust):             62.815
                                        P-value                           0.0000
Time periods:                    2761   Distribution:              F(11,1126353)
Avg Obs:                       408.20                                           
Min Obs:                       262.00                                           
Max Obs:                       461.00                                           
                                                                                
                             Parameter Estimates                              
==============================================================================
            Parameter  Std. Err.     T-stat    P-value    Lower CI    Upper CI
------------------------------------------------------------------------------
const          0.4102     0.0016     249.64     0.0000      0.4070      0.4135
news-5        -0.0012     0.0005    -2.5579     0.0105     -0.0022     -0.0003
news-4         0.0016     0.0005     3.2873     0.0010      0.0006      0.0025
news-3         0.0023     0.0005     5.1335     0.0000      0.0014      0.0032
news-2         0.0025     0.0005     5.3614     0.0000      0.0016      0.0035
news-1         0.0071     0.0005     14.413     0.0000      0.0061      0.0081
news0          0.0115     0.0005     21.946     0.0000      0.0105      0.0126
news1          0.0081     0.0005     17.462     0.0000      0.0072      0.0090
news2          0.0036     0.0004     8.2428     0.0000      0.0027      0.0044
news3          0.0019     0.0004     4.2944     0.0000      0.0010      0.0028
news4          0.0010     0.0004     2.2869     0.0222      0.0001      0.0018
news5         -0.0004     0.0004    -0.9105     0.3626     -0.0012      0.0004
==============================================================================

F-test for Poolability: 16.639
P-value: 0.0000
Distribution: F(677,1126353)

Included effects: Entity
```
