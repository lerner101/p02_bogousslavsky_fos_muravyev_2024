# Figure 4 replication

Built by `src/replicate_figure4.py` from the posted original-vintage ITI. Specification follows the authors' `ITI_main.py`; see the script docstring.

## Deviations from the paper

- Sample 2005-01 to 2019-07 (paper: 1993-01 to 2019-07); local CRSP, TAQ indicators, Compustat and ITI start in 2004, used only as event-time warm-up.
- Panel (c) covers 2005-2015 (paper: 2000-2015).
- Control-completeness screen uses seven controls; Kyle's lambda is not built for the general panel.
- With-controls sensitivity uses the panel's depth (shares) and OI (share of volume) units, not the authors' shares-outstanding scaling.
- Earnings dates use our own volume test on Compustat rdq, not the authors' EAdates.hdf.
- Paper values are read off the published plots (about +/-0.003; panel (c) about +/-0.0003).

## Panel (a) ITI(13D) around earnings announcements

- all announcements: day 0 0.1233 vs paper 0.0950 (ratio 1.30); correlation with paper profile 0.998; 9,231,755 observations

| group | day | coef | lower | upper | paper |
|---|---|---|---|---|---|
| all | -10 | -0.0043 | -0.0061 | -0.0026 | -0.0030 |
| all | -9 | -0.0066 | -0.0085 | -0.0047 | -0.0040 |
| all | -8 | -0.0082 | -0.0100 | -0.0064 | -0.0060 |
| all | -7 | -0.0061 | -0.0080 | -0.0042 | -0.0050 |
| all | -6 | -0.0052 | -0.0071 | -0.0033 | -0.0040 |
| all | -5 | -0.0029 | -0.0048 | -0.0010 | -0.0030 |
| all | -4 | -0.0029 | -0.0048 | -0.0010 | -0.0030 |
| all | -3 | 0.0002 | -0.0018 | 0.0022 | -0.0020 |
| all | -2 | 0.0104 | 0.0084 | 0.0125 | 0.0050 |
| all | -1 | 0.0294 | 0.0270 | 0.0318 | 0.0180 |
| all | 0 | 0.1233 | 0.1202 | 0.1263 | 0.0950 |
| all | 1 | 0.0611 | 0.0585 | 0.0636 | 0.0440 |
| all | 2 | 0.0449 | 0.0427 | 0.0471 | 0.0340 |
| all | 3 | 0.0338 | 0.0317 | 0.0359 | 0.0260 |
| all | 4 | 0.0261 | 0.0239 | 0.0282 | 0.0200 |
| all | 5 | 0.0228 | 0.0206 | 0.0249 | 0.0170 |
| all | 6 | 0.0162 | 0.0140 | 0.0183 | 0.0110 |
| all | 7 | 0.0134 | 0.0112 | 0.0155 | 0.0090 |
| all | 8 | 0.0115 | 0.0095 | 0.0136 | 0.0080 |
| all | 9 | 0.0093 | 0.0073 | 0.0113 | 0.0070 |
| all | 10 | 0.0090 | 0.0069 | 0.0110 | 0.0060 |

## Panel (b) Top and bottom quartile absolute announcement return

- large |r|: day 0 0.1832 vs paper 0.1550 (ratio 1.18); correlation with paper profile 0.999; 6,945,386 observations
- small |r|: day 0 0.0863 vs paper 0.0580 (ratio 1.49); correlation with paper profile 0.988; 6,906,059 observations

| group | day | coef | lower | upper | paper |
|---|---|---|---|---|---|
| large | -10 | -0.0042 | -0.0065 | -0.0019 | 0.0000 |
| large | -9 | -0.0073 | -0.0097 | -0.0049 | -0.0030 |
| large | -8 | -0.0087 | -0.0111 | -0.0062 | -0.0050 |
| large | -7 | -0.0043 | -0.0068 | -0.0019 | -0.0030 |
| large | -6 | -0.0049 | -0.0073 | -0.0025 | 0.0000 |
| large | -5 | -0.0017 | -0.0040 | 0.0007 | 0.0000 |
| large | -4 | 0.0006 | -0.0019 | 0.0031 | 0.0010 |
| large | -3 | 0.0056 | 0.0031 | 0.0081 | 0.0040 |
| large | -2 | 0.0156 | 0.0130 | 0.0182 | 0.0130 |
| large | -1 | 0.0376 | 0.0346 | 0.0405 | 0.0300 |
| large | 0 | 0.1832 | 0.1786 | 0.1877 | 0.1550 |
| large | 1 | 0.1085 | 0.1052 | 0.1117 | 0.0900 |
| large | 2 | 0.0765 | 0.0736 | 0.0795 | 0.0640 |
| large | 3 | 0.0589 | 0.0561 | 0.0616 | 0.0480 |
| large | 4 | 0.0467 | 0.0440 | 0.0494 | 0.0390 |
| large | 5 | 0.0418 | 0.0392 | 0.0445 | 0.0340 |
| large | 6 | 0.0318 | 0.0292 | 0.0345 | 0.0270 |
| large | 7 | 0.0281 | 0.0254 | 0.0308 | 0.0230 |
| large | 8 | 0.0246 | 0.0221 | 0.0271 | 0.0210 |
| large | 9 | 0.0209 | 0.0184 | 0.0234 | 0.0190 |
| large | 10 | 0.0211 | 0.0185 | 0.0237 | 0.0190 |
| small | -10 | -0.0005 | -0.0028 | 0.0018 | 0.0000 |
| small | -9 | -0.0028 | -0.0052 | -0.0004 | -0.0020 |
| small | -8 | -0.0039 | -0.0063 | -0.0015 | -0.0040 |
| small | -7 | -0.0026 | -0.0050 | -0.0003 | -0.0030 |
| small | -6 | -0.0019 | -0.0044 | 0.0006 | -0.0020 |
| small | -5 | -0.0002 | -0.0026 | 0.0023 | -0.0020 |
| small | -4 | -0.0010 | -0.0035 | 0.0016 | -0.0010 |
| small | -3 | 0.0013 | -0.0013 | 0.0039 | 0.0000 |
| small | -2 | 0.0091 | 0.0065 | 0.0117 | 0.0020 |
| small | -1 | 0.0216 | 0.0188 | 0.0245 | 0.0060 |
| small | 0 | 0.0863 | 0.0831 | 0.0895 | 0.0580 |
| small | 1 | 0.0297 | 0.0268 | 0.0326 | 0.0140 |
| small | 2 | 0.0291 | 0.0265 | 0.0317 | 0.0180 |
| small | 3 | 0.0239 | 0.0214 | 0.0265 | 0.0140 |
| small | 4 | 0.0190 | 0.0164 | 0.0217 | 0.0120 |
| small | 5 | 0.0165 | 0.0138 | 0.0191 | 0.0090 |
| small | 6 | 0.0113 | 0.0087 | 0.0140 | 0.0050 |
| small | 7 | 0.0077 | 0.0051 | 0.0103 | 0.0030 |
| small | 8 | 0.0080 | 0.0055 | 0.0105 | 0.0020 |
| small | 9 | 0.0058 | 0.0033 | 0.0082 | 0.0020 |
| small | 10 | 0.0060 | 0.0035 | 0.0086 | 0.0020 |

## Panel (c) ITI(impatient) around news events (excluding earnings announcements)

- all news days: day 0 0.0115 vs paper 0.0120 (ratio 0.96); correlation with paper profile 0.985; 1,110,684 observations

| group | day | coef | lower | upper | paper |
|---|---|---|---|---|---|
| all news | -5 | -0.0013 | -0.0022 | -0.0003 | -0.0011 |
| all news | -4 | 0.0015 | 0.0005 | 0.0025 | 0.0007 |
| all news | -3 | 0.0022 | 0.0013 | 0.0032 | 0.0010 |
| all news | -2 | 0.0025 | 0.0015 | 0.0034 | 0.0018 |
| all news | -1 | 0.0071 | 0.0061 | 0.0080 | 0.0063 |
| all news | 0 | 0.0115 | 0.0105 | 0.0126 | 0.0120 |
| all news | 1 | 0.0081 | 0.0072 | 0.0090 | 0.0065 |
| all news | 2 | 0.0035 | 0.0027 | 0.0044 | 0.0032 |
| all news | 3 | 0.0019 | 0.0010 | 0.0028 | 0.0007 |
| all news | 4 | 0.0010 | 0.0001 | 0.0019 | -0.0001 |
| all news | 5 | -0.0003 | -0.0011 | 0.0005 | -0.0001 |

## Panel (a) day-0 coefficient by specification step

| step | day 0 | day -1 | day 1 | observations |
|---|---|---|---|---|
| previous build: all CRSP days, no screens, zero-filled edges | 0.1225 | 0.0291 | 0.0606 | 9,569,557 |
| + posted-ITI row sequence, drop edge rows | 0.1228 | 0.0291 | 0.0606 | 9,477,010 |
| + drop sparse stocks | 0.1228 | 0.0291 | 0.0606 | 9,476,747 |
| + require seven controls (final) | 0.1233 | 0.0294 | 0.0611 | 9,231,755 |

Paper day 0: 0.095.

## Panel (a) by subperiod (final specification)

| period | day 0 | SE | mean ITI(13D) | SD ITI(13D) | events | observations |
|---|---|---|---|---|---|---|
| 2005-2009 | 0.1094 | 0.0020 | 0.281 | 0.157 | 55,598 | 3,495,774 |
| 2010-2014 | 0.1180 | 0.0023 | 0.286 | 0.165 | 48,176 | 3,026,874 |
| 2015-2019 | 0.1474 | 0.0025 | 0.305 | 0.168 | 42,786 | 2,709,107 |

## Sample counts

```json
{
  "sequence_rows": 10279512,
  "sparse_rows_dropped": 369,
  "sequence_stocks": 6523,
  "earnings_events_crsp_days": 250940,
  "earnings_events_on_sequence": 162663,
  "posted_iti_rows_ineligible_share": 0.0004354626401465845,
  "news_rows_linked": 1634901,
  "earnings_window_rows_excluded": 109016,
  "news_sample_dates": [
    "2005-01-03",
    "2015-12-23"
  ]
}
```
