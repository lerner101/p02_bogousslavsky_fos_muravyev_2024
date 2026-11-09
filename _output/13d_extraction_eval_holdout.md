# 13D extraction vs hand audit (holdout sample)

Audit filings: 15; audited rows with dates: 121 (open-market, non-derivative: 104). Auditor: claude-subagent (independent of extractor; NOT human-verified).

| Level | Matched | True | Extracted | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| rows, all | 102 | 121 | 102 | 84.3% | 100.0% |
| rows, open-market non-derivative | 102 | 104 | 102 | 98.1% | 100.0% |
| rows, open-market, inside window | 102 | 104 | 102 | 98.1% | 100.0% |
| trade days, all | 78 | 87 | 78 | 89.7% | 100.0% |
| trade days, open-market | 78 | 78 | 78 | 100.0% | 100.0% |

Filing-level agreement on 'has any trade': 60.0%.

Matched-row price agreement (within 0.5%): 100.0% of 102

## By filing

| accession            | issuer_name                         | has_open_market_trades   | packet_truncated_trades_possible   |   true_rows |   pred_rows |   matched |      true_shares |      pred_shares |
|:---------------------|:------------------------------------|:-------------------------|:-----------------------------------|------------:|------------:|----------:|-----------------:|-----------------:|
| 0000950152-05-004672 | American Greetings Corporation      | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0001033475-06-000005 | Saga Communications, Inc. -         | yes                      | no                                 |          15 |          15 |        15 | 486930           | 486930           |
| 0001104659-07-055445 | INSPIRE PHARMACEUTICALS, INC.       | no                       | no                                 |           1 |           0 |         0 | 140186           |      0           |
| 0001193125-08-242286 | Life Time Fitness, Inc.             | yes                      | no                                 |          48 |          46 |        46 |      3.63241e+06 |      3.46695e+06 |
| 0001040063-09-000003 | Kimball International, Inc.         | no                       | no                                 |           5 |           0 |         0 | 112240           |      0           |
| 0001104659-10-021019 | Facet Biotech Corporation           | no                       | no                                 |           3 |           0 |         0 |      8.19107e+07 |      0           |
| 0001193125-11-068847 | 99 ONLY STORES                      | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0001188112-12-000920 | Greenway Medical Technologies, Inc. | no                       | no                                 |           4 |           0 |         0 |      5.28468e+06 |      0           |
| 0001193125-13-214474 | T-Mobile US, Inc.                   | no                       | no                                 |           1 |           0 |         0 |      5.35286e+08 |      0           |
| 0000921895-14-000641 | Cbeyond, Inc.                       | yes                      | no                                 |          17 |          17 |        17 | 598491           | 598491           |
| 0001104659-15-010748 | Genocea Biosciences, Inc.           | no                       | no                                 |           3 |           0 |         0 |      1.29242e+06 |      0           |
| 0001193125-16-525027 | MIDDLEBURG FINANCIAL CORPORATION    | yes                      | no                                 |           6 |           6 |         6 |   6948           |   6948           |
| 0000919574-17-003011 | DigitalGlobe, Inc.                  | yes                      | no                                 |           2 |           2 |         2 |   4000           |   4000           |
| 0000899140-18-000607 | Horizon Global Corporation          | yes                      | no                                 |          16 |          16 |        16 | 812163           | 812163           |
| 0000950142-19-000821 | Hemisphere Media Group, Inc.        | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
