# Figure 4(a)-(b) diagnostics

Built by `src/replicate_figure4.py diagnose` (`doit figure4_diagnose`).

## Panel (a) day-0 coefficient by specification step

| step | day 0 | day -1 | day 1 | observations |
|---|---|---|---|---|
| previous build: all CRSP days, no screens, zero-filled edges | 0.1225 | 0.0291 | 0.0606 | 9,569,557 |
| + posted-ITI row sequence, drop edge rows | 0.1228 | 0.0291 | 0.0606 | 9,477,010 |
| + drop sparse stocks | 0.1228 | 0.0291 | 0.0606 | 9,476,747 |
| + require seven controls (final) | 0.1233 | 0.0294 | 0.0611 | 9,231,755 |

Paper day 0: 0.095.

## Day-0 coefficient by subperiod (final specification)

Panel (b) quartile cutoffs are over all announcements, as in the full-sample panel.

| period | all | large \|r\| | small \|r\| | large - small | events (all) | observations (all) |
|---|---|---|---|---|---|---|
| 2005-2009 | 0.1094 | 0.1617 | 0.0785 | 0.0833 | 55,598 | 3,495,774 |
| 2010-2014 | 0.1180 | 0.1671 | 0.0864 | 0.0807 | 48,176 | 3,026,874 |
| 2015-2019 | 0.1474 | 0.2242 | 0.0958 | 0.1284 | 42,786 | 2,709,107 |
| paper, 1993-2019 | 0.095 | 0.155 | 0.058 | 0.097 | | |

Standard errors, days -1 to 2, and ITI(13D) moments are in `figure4_subperiods.csv`.
