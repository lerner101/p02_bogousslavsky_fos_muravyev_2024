# 13D extraction vs hand audit (tuning sample)

Audit filings: 30; audited rows with dates: 382 (open-market, non-derivative: 349). Auditor: claude-subagent (independent of extractor; NOT human-verified).

| Level | Matched | True | Extracted | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| rows, all | 357 | 382 | 357 | 93.5% | 100.0% |
| rows, open-market non-derivative | 335 | 349 | 351 | 96.0% | 95.4% |
| rows, open-market, inside window | 335 | 335 | 351 | 100.0% | 95.4% |
| trade days, all | 116 | 126 | 116 | 92.1% | 100.0% |
| trade days, open-market | 110 | 115 | 111 | 95.7% | 99.1% |

Filing-level agreement on 'has any trade': 90.0%.

Matched-row price agreement (within 0.5%): 99.4% of 357

## By filing

| accession            | issuer_name                              | has_open_market_trades   | packet_truncated_trades_possible   |   true_rows |   pred_rows |   matched |      true_shares |      pred_shares |
|:---------------------|:-----------------------------------------|:-------------------------|:-----------------------------------|------------:|------------:|----------:|-----------------:|-----------------:|
| 0001019056-05-000041 | Steven Madden, Ltd. -                    | yes                      | no                                 |          25 |          25 |        25 | 440344           | 440344           |
| 0000898432-05-000537 | Quality Systems, Inc.                    | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0001193125-06-031684 | NEWMARKET CORPORATION                    | no                       | no                                 |           1 |           0 |         0 | 437220           |      0           |
| 0000950137-06-013881 | OWENS CORNING                            | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0001104659-07-051308 | OAKLEY, INC.                             | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0001129787-07-000092 | Exterran Holdings, Inc.                  | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0001418812-08-000035 | International Rectifier Corporation      | yes                      | no                                 |          26 |          26 |        26 | 977989           | 977989           |
| 0001193125-08-164657 | Vital Signs, Inc.                        | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0001104659-09-003522 | PACWEST BANCORP                          | no                       | yes                                |           0 |           0 |         0 |      0           |      0           |
| 0001462180-09-000030 | nan                                      | no                       | no                                 |           5 |           5 |         5 | 376100           | 376100           |
| 0001341004-10-000246 | CHINA MEDIAEXPRESS HOLDINGS, INC.        | no                       | yes                                |           3 |           0 |         0 |      2.69546e+06 |      0           |
| 0000807249-10-000238 | Micrus Endovascular Corporation          | yes                      | no                                 |          66 |          66 |        66 | 919056           | 919056           |
| 0001193805-11-001412 | Quepasa Corporation                      | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0000902664-11-001642 | Consolidated-Tomoka Land Co.             | yes                      | no                                 |          38 |          38 |        38 | 116842           | 116842           |
| 0001193125-12-060937 | Gevo, Inc.                               | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0000904454-12-000381 | Durata Therapeutics, Inc.                | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0001104659-13-003859 | BARNES & NOBLE, INC.                     | no                       | yes                                |           0 |           0 |         0 |      0           |      0           |
| 0001193125-13-028288 | MAP Pharmaceuticals, Inc.                | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0000002178-14-000026 | ADAMS RESOURCES & ENERGY, INC.           | no                       | yes                                |           0 |           0 |         0 |      0           |      0           |
| 0000921895-14-002048 | Town Sports International Holdings, Inc. | yes                      | no                                 |          84 |          84 |        84 |      2.2366e+06  |      2.2366e+06  |
| 0000927089-15-000306 | Southern Missouri Bancorp, Inc.          | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0000950157-15-000754 | CABLE ONE, INC.                          | no                       | no                                 |           3 |           0 |         0 |      1.26995e+07 |      0           |
| 0001193125-16-693819 | Medpace Holdings, Inc.                   | no                       | yes                                |           0 |           0 |         0 |      0           |      0           |
| 0000941560-16-000052 | Outerwall Inc.                           | yes                      | no                                 |          11 |          11 |        11 |      1.01416e+06 |      1.01416e+06 |
| 0001193125-17-110234 | EXAR CORPORATION                         | no                       | no                                 |           0 |           0 |         0 |      0           |      0           |
| 0000919574-17-008738 | KINDRED HEALTHCARE, INC.                 | yes                      | no                                 |          52 |          37 |        37 |      5.63931e+06 |      4.96663e+06 |
| 0001144204-18-006967 | Solid Biosciences Inc.                   | no                       | no                                 |           4 |           1 |         1 |      2.68944e+06 | 808990           |
| 0000947871-18-000558 | TRICIDA, INC.                            | no                       | yes                                |           0 |           0 |         0 |      0           |      0           |
| 0000807985-19-000015 | CenturyLink, Inc.                        | yes                      | no                                 |          64 |          64 |        64 |      5.88898e+06 |      5.88898e+06 |
| 0000903423-19-000285 | MORPHIC HOLDING, INC.                    | no                       | yes                                |           0 |           0 |         0 |      0           |      0           |
