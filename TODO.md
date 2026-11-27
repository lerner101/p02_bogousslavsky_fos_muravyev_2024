# TODO — Final project checklist (by rubric)

Status as of 2026-11-26. `[x]` done, `[~]` partial, `[ ]` not started.
Tolerance policy: **correct magnitude, not exact numbers.** An estimate passes if
it has the paper's sign and lies within ×3 of it (looser when the paper's own
estimate is insignificant). Rule in `src/replication_scorecard.py`; results in
`_output/report/scorecard.csv` (currently **49/59 pass**).

## Replication (20 pts): assigned exhibits T1–5, T9–11, F1–4, FIA5

| Exhibit | Status | Where / what's left |
|---|---|---|
| Table 1 (descriptive stats) | [ ] | Needs data machine: summary stats of controls + ITIs on the daily panel (`_data/derived/panel/daily.parquet`) and label means. |
| Table 2 (ITI detects 13D days) | [ ] | Needs data machine: `itrade ~ ITI(13D)` (+ controls) with filing FE on `oof_predictions.parquet`; controls already built in `replicate_iti_figures.figure1_controls`. |
| Table 3 (feature-group ITIs) | [ ] | Train 4 subset models (`iti_features.GROUPS`) with `train_iti.py` logic; regress `itrade` on each. Most expensive item; consider dropping if short on time. |
| Table 4 (turnover matching) | [ ] | Match trade/non-trade days within filing on turnover (abs diff ≤ 0.00002); regress. Cheap once Table 2 inputs load. |
| Table 5 (reversal) | [x] | `_output/replication/table5.csv`; 8/9 pass (ret×ES% 3.4×; ret×rvol not comparable, units). |
| Table 9 (vs PIN measures) | [ ] | PIN/APIN/GPIN/OWR prepared 2004–2012; BCL missing. Needs patient/impatient 13D labels + posted ITIs. |
| Table 10 (return predictability) | [~] | Cols 1–5 done (14/16 pass; ITI(insider) misses). Col 6 (PIN control) and Panel B (insider buy/sell) not done. |
| Table 11 (decile sorts) | [x] | 5/10 H-L comparisons pass; ITI(13D) and ITI(impatient) right sign and significant, smaller. |
| Figure 1 (annual R²) | [x] | ITI beats controls every year; level ~½ the paper's. |
| Figure 2 (partial dependence) | [x] | Volume shape matches; volatility curve flat (documented miss). |
| Figure 3 (surrogate tree) | [x] | Qualitatively similar; first split differs. |
| Figure 4(a)(b) (earnings) | [x] | Close match. |
| Figure 4(c) (news) | [~] | Preliminary: raw earnings dates for exclusion, incomplete control screen. |
| Figure IA.5 (M&A) | [x] | Close match after announcement. |
| Tolerance unit tests | [x] | `tests/test_replication_tolerance.py`; known misses are strict xfails with reasons. |

## Update (10 pts)
- [ ] Rerun Tables 5, 10, 11 and Figure 4 through the latest data. The authors'
      extended ITI (1993–2024) is already prepared (`_data/public/iti_extended_*`);
      needs CRSP daily + TAQ indicators for 2020–2024 on the data machine.
- [ ] Move `SAMPLE_START/SAMPLE_END` in `src/replicate_exhibits.py` to use
      `settings.py` (`START_DATE`, `PAPER_END_DATE`/`END_DATE`), committed constants.
- [ ] One or two sentences in report §4: did the results hold after publication?

## Data validation (10 pts)
- [x] Checks against independent benchmarks run as tests (`tests/test_data_validation.py`):
      13D trade frequency vs paper, impatient > patient, TAQ vs CRSP volume,
      coverage with no break in training years, universe match with the authors'
      file, yearly correlation with the authors' ITI.
- [x] Table + figure of what the checks found (`src/validation_exhibits.py` →
      report Table 2 and Figure 1).
- [~] Weakness: tolerances were written after the pilot numbers had been looked at,
      and the TAQ/CRSP pilot has only 6 stock-days. Consider a larger reconciliation sample.

## Extension (30 pts): public ChartBook site on GitHub Pages
- [x] README **Extension** section drafted. **Team: confirm it matches the consultation agreement.**
- [x] `chartbook.toml` registers 8 dataframes (with sources) + 5 charts + notebook.
- [x] `.github/workflows/pages.yml` builds the site from a clean clone and deploys on push to main.
- [ ] **Repo settings → Pages → Source: "GitHub Actions"** (one-time, needs repo admin).
- [ ] Add a site page for the scorecard/extension narrative in `docs_src/site/`
      (currently `goals.md` is still the template; fill it in or delete it).
- [ ] Optional: a downloadable CSV of our ITI(13D) aggregated (e.g. monthly
      cross-sectional mean); no licensed row-level data.

## Report and site (9 pts)
- [x] `reports/report.tex` covers overview, successes/challenges, data sources,
      validation, all generated exhibits with takeaway captions; numbers are macros
      from `src/report_tables.py`.
- [ ] Fill §4 Updated Results once the update exists.
- [~] Notebook `_output/01_iti_replication.ipynb` is registered; check it renders on the site.

## Engineering (36 pts)
- [~] **Runs end to end from a clean clone** (8): `doit publish` and
      `doit build_chartbook_site` work without data. Plain `doit` (the
      `research` default) needs `_data/` and fails on a clean clone. **Decide:**
      make the default the clean-clone path, or document the data handoff clearly
      for the grader.
- [x] Cleaning separate from analysis (`build_*`/`parse_*` vs `replicate_*`).
- [x] Report statistics generated by code (`_output/report/stats.tex`).
- [x] Tests motivated; CI runs `doit check` on push/PR.
- [x] No `.env`, raw data or secrets in git history (checked 2026-11-26).
- [~] Settings: `START_DATE`/`END_DATE` are in `settings.py`, but some scripts
      hardcode dates and `_data` paths instead of using them (`replicate_exhibits.py`,
      `build_panel.py`, `train_iti.py`).
- [x] Cruft scaffold, README run instructions, `requirements.txt`.
- [x] Module docstrings in every Python file.
- [ ] `.env.example`: add `END_DATE` note (it must *not* be read from `.env`).

## Individual (85 pts)
- [ ] Every member has authored ≥1 merged PR **and** reviewed ≥1 teammate PR.
- [ ] Every PR reviewed by someone else before merge (do not self-merge).
- [ ] Each member can explain every part (paper, data filters, tolerances,
      extension, "what reruns if END_DATE changes and how doit knows").
