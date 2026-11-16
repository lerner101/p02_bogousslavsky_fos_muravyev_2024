# Schedule 13D label validation

Filings are original SC 13D submissions 2005-2019 from WRDS. 'Paper period' means filed 2005-2018 (the paper's sample is 1994-2018, 1,593 events).

## Event funnel

| First failed screen | Filings |
|---|---:|
| linked | 11,204 |
| common_stock | 4,144 |
| price | 3,911 |
| mcap | 1,272 |
| no_derivatives | 58 |
| has_trades | 3,386 |
| duplicate_event | 59 |
| included | 2,193 |

Included events by filing year: 2005: 174, 2006: 218, 2007: 263, 2008: 223, 2009: 78, 2010: 127, 2011: 123, 2012: 126, 2013: 123, 2014: 172, 2015: 146, 2016: 105, 2017: 102, 2018: 122, 2019: 91

## Comparison with the authors' events

The posted ITI file blanks the three 13D-trained scores inside the authors' training windows (`src/authors_13d_windows.py`). Windows ending 2005-2018 are matched to our filings on PERMNO and filing date (3 days before to 7 days after the window's end).

Recovered authors' windows ending 2005-2018: 1,100.

| Outcome for the authors' window | Windows |
|---|---:|
| our filing included | 906 |
| our filing excluded at has_trades | 96 |
| our filing excluded at original | 13 |
| our filing excluded at price | 9 |
| our filing excluded at mcap | 4 |
| our filing excluded at common_stock | 3 |
| our filing excluded at no_derivatives | 2 |
| our filing excluded at linked | 1 |
| no linked filing of ours | 66 |

Recall: 82.4% of the authors' windows match an included event. Precision: 43.6% of our 2,102 included 2005-2018 events match an authors' window. Use `in_authors_sample` to restrict training to the authors' events.

## Labels vs paper

| Statistic | Ours, 2005-2018 | Ours, authors' events only | Ours, 2005-2019 | Paper | Source |
|---|---:|---:|---:|---:|---|
| events | 2,102.0000 | 916.0000 | 2,193.0000 |  |  |
| rows_per_event | 40.9933 | 42.2172 | 40.9580 | 36.5330 | Table 1: 58,197 rows / 1,593 filings |
| itrade | 0.3630 | 0.3826 | 0.3610 | 0.3603 | Table 1 |
| itrade_patient | 0.3214 | 0.3274 | 0.3190 | 0.3000 | Sec. 4.1: 30% of days in first 40 |
| itrade_impatient | 0.4404 | 0.4878 | 0.4392 | 0.4900 | Sec. 4.1: 49% of days in last 20 |
| vol_share | 0.1424 | 0.1401 | 0.1422 | 0.2800 | Sec. 3.1: 28% of daily volume when trading |
| vol_share_patient | 0.1247 | 0.1250 | 0.1245 | 0.2000 | Sec. 4.1 |
| vol_share_impatient | 0.1665 | 0.1594 | 0.1661 | 0.3700 | Sec. 4.1 |
| turn13d_mean_x100 | 0.2937 | 0.2419 | 0.3014 | 0.2755 | Table IA.5, trade days |
| turn13d_median_x100 | 0.0780 | 0.0827 | 0.0786 | 0.1055 | Table IA.5, trade days |
| sell_share | 0.1198 | 0.0842 | 0.1221 | 0.0600 | ITI_main.py comment: ~6% of activist trades are sells |
| filer_shares_gt_crsp_vol | 0.0092 | 0.0055 | 0.0094 |  |  |

## Posted ITI(13D), original vintage

Coverage of our paper-period label rows: 47.1% (the authors' file omits their own training windows, so low coverage suggests overlap with their sample).
Mean ITI on trade days 0.368 vs non-trade days 0.303; within-filing slope of itrade on ITI 0.409, within R2 0.030 (paper Table 2 col. 1, out-of-fold ITI: 0.697, R2 0.099).

## Abnormal return around filing

Events: 1952. Cumulative excess return from day -40 to day -1: 1.20% (paper Fig. IA.1: about 3%); days 0 to +1: 2.03% (paper: about 2%). Chart: `_output/13d_filing_car.png`.
