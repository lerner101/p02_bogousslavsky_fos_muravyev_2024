# Replication and Consultation Plan

Prepared November 4, 2026. The original planning discussion below predates the
implemented 13D pipeline and preliminary news regression. For the current
execution contract, see the [build and professor handoff guide](build.md) and
the dataset inventory in the repository README. This is a
plan grounded in the local paper, all 13 local screenshots, the assignment, and
selected course examples; it is not an instructor-approved scope agreement.

## Understand the paper first

The paper learns the market footprint of informed trading from days when
activists disclose having traded, then applies that pattern to other stock-days.
A Schedule 13D disclosure supplies historical transaction dates, directions,
quantities, and prices. The model learns whether a filer traded on a particular
day within the disclosure window. Days without a disclosed transaction are
comparison days, not proof that no informed investor traded.

The main model is XGBoost trained on 41 same-day price, return, liquidity,
volatility, and volume features. Features are standardized using the stock's
prior-year history. ITI is a score between zero and one. It measures realized
trading activity using that day's data; it is not automatically a forecast that
can be traded before those data arrive, nor a calibrated probability of illegal
insider trading in the general population.

The mechanism is more subtle than "high volume means informed trading":
nonlinearities and combinations such as high volume with relatively low
volatility matter. The paper checks whether the learned measure detects 13D
trading, rises around informational events, and distinguishes lasting price
moves from temporary reversals. It then studies subsequent returns.

Read in this order (printed page numbers in the local PDF):

1. Abstract and Introduction, pp. 1–5: claim, interpretation, main findings.
2. Section 2, pp. 6–8: data, labels, screens, events.
3. Sections 3.1–3.2, pp. 9–16: features, estimation, evaluation.
4. Appendix Tables IA.2–IA.4: datasets, all 41 features, control definitions.
5. Sections 3.3–3.4, pp. 17–20: extrapolation and events/reversal.
6. Sections 4.1–4.2: patient/impatient and alternative training labels.
7. Section 5 and captions of Tables 10–11: future returns and portfolio timing.

The local title page says "Journal of Finance, forthcoming". Confirm this
version's exhibit numbers and values with Jeremy rather than assuming it is
identical to the final published typesetting.

## Exhibit inventory from the screenshots

The folder contains Tables 1–5 and 9–11, Figures 1–4, and Figure IA.5.
Their presence documents intended targets, not instructor confirmation that
all rows, panels, and alternative model variants are required.

| Exhibit | What to implement | Important dependencies or scope questions |
|---|---|---|
| Table 1 | Distribution of controls, ITI variants, and label indicators; sample counts | Full stock-day panel; some rows require insider and short-selling data/models |
| Table 2 | Regressions of 13D trade-day indicator and filer turnover on ITI/controls | Out-of-fold ITI, complete filing windows, transaction quantities, filing effects and clustered errors |
| Table 3 | Separate models using liquidity, return, volatility, and volume groups | Train separate models; grouping is defined by IA.3, not an arbitrary feature-importance ranking |
| Table 4 | Match trade/non-trade days within filing on turnover and re-estimate | Matching details, paper's caliper, matched-sample accounting |
| Table 5 | Next-day return on current return, ITI, and interaction terms | Date effects; stock/date clustered errors; correct stock-day lags |
| Table 9 | Compare ITI variants with model-based measures | PIN/APIN/GPIN/OWR/BCL, patient/impatient and insider/short variants; broader than assigned PIN/VPIN comparison |
| Table 10 | Next-month returns on prior-week ITI averages and controls | One-day gap, overlapping returns, delistings, weekly panel; multiple ITI variants |
| Table 11 | Decile returns and four-factor alphas from prior-week ITI | Correct portfolio timing/overlap; equal weights; Newey-West eight lags; multiple ITI variants |
| Figure 1 | Annual explanatory power of ITI versus controls in 13D sample | Out-of-fold predictions and annual regressions, not training accuracy |
| Figure 2 | Partial dependence for volume and volatility, with distributions | Trained model and standardized feature panel |
| Figure 3 | Three-level regression tree approximating ITI | Surrogate tree trained on ITI scores, not a replacement for the main model |
| Figure 4 | Earnings and news event regressions, including earnings-size groups | Earnings timing, historical event panel, stock effects, stock/date clustered intervals |
| Figure IA.5 | ITI around M&A target announcements | Original caption uses 1996–2010 and 1,577 events; SDC deal/event access needs checking |

Also consult Table IA.6 for model-performance comparisons even though it is not
among the screenshots. Appendix definitions are needed to implement the main
exhibits even when the appendix exhibits are not themselves assigned outputs.

Tables 6–8 and other appendix results are not present in the screenshots. Do not
silently add them to the graded replication scope.

## Resolve these uncertainties before scaling

1. **Training labels.** The original authors manually checked filings. Rebuilding
   their exact 1,593-event sample from EDGAR is not equivalent to downloading
   filing metadata. Inspect transaction schedules and exclusions, original versus
   amendment filings, derivatives, CUSIPs, duplicate events, and missing schedules.
   Preserve accession IDs and extraction provenance. Ask whether original label
   data are available through course resources or the authors. Do not represent a
   newly collected subset as an exact replication of their hand-curated sample.
2. **Additional model variants.** The screenshots include ITI(insider), ITI(short),
   ITI(patient), and ITI(impatient), plus buy/sell insider variants in Table 10.
   Insider training uses opportunistic insider trades; short training uses Markit
   loan/short-interest data. Their raw inputs are not listed in the abbreviated
   assignment. Agree on rows/panels and whether author-provided variants may be
   used for downstream comparisons, clearly distinguished from rebuilt models.
3. **TAQ coverage and scale.** The original general sample is January 1993–July
   2019; 13D events span 1994–2018. Determine access to the historical TAQ products
   rather than assuming one modern table covers the entire history. The paper
   combines four CRSP features, 21 WRDS Intraday Indicators features, and 16
   supplemental features. Ask whether WRDS indicators may be used as intermediate
   inputs or all relevant features must be rebuilt from raw TAQ.
4. **Event sources.** M&A comes from SDC in the paper. Confirm access or an agreed
   substitute. IBES/Compustat supply earnings dates. The assignment permits 8-K
   filing timestamps for news; those observations differ from the original news
   panel, so exact equality of Figure 4(c) is not an appropriate target. An 8-K
   filing timestamp also need not be the first public release of the news.
5. **Original versus refreshed ITI.** The author's current data page says its
   January 2026 update covers January 1993–December 2024, fills historical gaps,
   and includes original measures for replication. Inspect the download's schema
   and documentation before choosing series. Compare historical results to the
   original vintage and label updated comparisons separately. The archive has
   now been downloaded and its schema inspected: date, PERMNO and five ITI
   variants. Preparation preserves original/refreshed vintages separately and
   restricts outputs through 2019; empirical validation remains outstanding.
6. **Specification inconsistencies.** Section 5 describes clustering by stock and
   week; the local Table 10 caption says stock and month. Record and resolve this
   rather than silently choosing whichever produces a closer t-statistic. Figure
   3's depicted sample count also differs from the main regression sample count;
   trace preprocessing and ask about differences if necessary.

## Estimation rules to preserve

- Use a 60-calendar-day disclosure window, mapped to trading days; distinguish
  absence of a reported trade from absence of usable disclosure information.
- Preserve filing IDs in the labeled panel and PERMNO/date in the general panel.
  Resolve historical CUSIP/ticker links using effective dates.
- Treat prior-year scaling as a time-aware transformation. Load history before
  the analysis start. Decide warm-up coverage and zero-variance handling in
  advance. Today's observation must not affect its own historical mean/SD.
- The paper describes nested evaluation: five calendar-time groups of 13D
  events, holding one group out; tune on the remaining groups; rotate to obtain
  out-of-fold scores. Keep each filing intact. This is not automatically a
  strictly forward-only backtest: other groups can occur after a held-out group.
- Keep paper-style evaluation and any proposed chronological deployment test
  separate. For an honest later-period test, freeze training and tuning before
  the evaluation period and account for when disclosures become available.
- Controls are winsorized at 0.05% and 99.95%, not the much more common 1%/99%.
  Scaling, outlier treatment, universe filters, units, and missing-data rules must
  be explicit and applied consistently.
- Do not substitute univariate averages for event regressions with stock effects
  and the specified confidence intervals. Treat after-hours news carefully.
- PIN and VPIN are different measures with different aggregation frequencies.
  Specify estimation windows, trade signing, volume buckets, and alignment to
  the common stock/event sample before comparing their performance.

## Code worth having before the consultation

The official consultation deliverable is the one-page pitch and proposed data
validation. The following code milestone is a recommendation to establish
feasibility, not an extra grading requirement.

Aim to reproduce one small path with real data:

`raw market data + one inspected 13D filing -> linked stock-days -> a few verified features and labels -> one diagnostic table and chart`

Suggested modules, created only as their work starts:

- `pull_crsp.py`: small daily stock sample, identifier history, caching.
- `pull_taq.py`: bounded trades/quotes sample with requested columns only.
- `pull_edgar.py`: filings index and source documents with provenance.
- `clean_market_data.py`: deterministic filtering and quote/trade alignment.
- `build_13d_labels.py`: hand-audited transaction extraction and daily labels.
- `build_features.py`: start with a few definitions, then expand to IA.3.
- `validate_data.py`: sample counts, identifier matches, volume reconciliation.

A useful initial sample is a handful of filings and their underlying stocks,
with a full disclosure window and enough preceding history for standardization.
Begin raw TAQ timing/memory tests with one stock-day. A one-month data extract
alone is not enough for the paper's prior-year standardization.

Do not spend the whole week building a general EDGAR parser or pulling all TAQ.
Hand-audit a few schedules first. If parsing is blocked, establish a second
independent path using author ITI plus CRSP for downstream analysis. This helps
progress but does not fulfill the raw-data/model-replication requirement.

Before the meeting, aim to show:

- A rerunnable bounded pull, cached output, and explicit data-access results.
- One linked filing window with disclosed transaction dates independently checked.
- One table of coverage/filter counts and one figure of volume or feature coverage.
- Tests for historical identifier links, rolling-window timing, trade/quote
  alignment, and conservation of extracted transaction quantities as applicable.
- Time and memory estimates for scaling, plus the actual blockers.

A tiny XGBoost experiment is a stretch milestone once labels/features are sound.
Too few events do not justify claims of replicating the paper's performance.
Use synthetic inputs for tests when useful and label them as such; they are not
empirical replication evidence.

## Plan through the November 13 consultation deadline

| When | Outcome |
|---|---|
| November 4–5 | Book consultation; read targeted sections; agree team ownership; send screenshots/version and scope questions |
| November 5–7 | Verify WRDS/TAQ/CRSP/event access; inspect author ITI documentation; manually inspect several 13D schedules |
| November 7–10 | Implement bounded market-data pull, historical links, initial labels/features, and diagnostics |
| November 10–12 | Review the small pipeline on a teammate's machine; document scaling estimates; finish pitch and validation plan |
| Consultation, by November 13 | Agree exact exhibits/variants, substitutions, original labels strategy, update coverage, and extension acceptance criteria |

Have each teammate own an implementation stream and review another's pull
request. Suggested streams: market data/features, EDGAR labels, estimation and
validation, downstream events/pricing and publication. Everyone needs the full
paper/pipeline understanding for the final individual questioning.

## Proposed extension

**Status: undecided.** The following is an earlier candidate, not an agreed
extension. Later-year collection does not establish the extension. Confirm the
research question with the group and instructor before implementing it.

Build a documented end-of-day informed-trading comparison tool for empirical
researchers, with ITI/PIN/VPIN aligned to one common sample, a frozen-model test
on later data, and diagnostics for changes in coverage and performance. Separate
this from the routine sample update. Use a small agreed universe if full-market
modern TAQ is too expensive.

The specific research question is whether a model trained on historical activist
trades remains useful under later market conditions, beyond what changes in
volume, volatility, and sample coverage explain. A null result is informative.
Evaluation must not be tuned until the desired conclusion appears.

Offer a minimal version: fixed-period holdout comparison, reproducible feature
builder, event diagnostics, and one notebook. A daily refreshed monitor is an
optional expansion only after data latency, compute, and access are established.
Do not promise a trading strategy, real-time detection, or daily free data access.
PIN/VPIN benchmarking is already assigned, so ask what additional scope makes
this an independently graded extension.

## Learn from the sample projects

The dividend-strip site makes intermediate datasets and their parents visible.
Adopt that structure for raw pulls, clean market data, labeled events, features,
predictions, and final panels; publish metadata without redistributing licensed
inputs. [Example site](https://jlin12-cpu.github.io/p04_golez_jackwerth_2024/).

The financial-ratios project separates published benchmarks from computed
results and automates cell-level comparisons. Use that pattern, verify reference
transcriptions against rendered screenshots, and retain diagnostic evidence for
mismatches. Its plain article report also confirms custom theorem styles are
unnecessary. [Benchmark module](https://github.com/amazingmazy/Financial-Ratios-Project/blob/main/src/paper_values.py),
[report source](https://github.com/amazingmazy/Financial-Ratios-Project/blob/main/reports/replication_report.tex).

The crash-bounds project centralizes schemas and fixed parameters. Define shared
keys, units, and feature names early so four contributors can integrate their
outputs. [Schema module](https://github.com/rileykhaas/forecasting_crashes_smile/blob/main/src/schema.py).

These are examples to assess, not proof every advertised feature or current
branch has been tested. None of their code was run during this review.

## Report and website target

Keep one concise report, with these parts:

1. Claim, replication scope, paper version, and current status.
2. Data sources, sample construction, features, labels, and estimator.
3. Validation results: at least one original table and figure showing checks.
4. Replicated exhibits with paper/ours/difference comparisons and explanations.
5. Updated sample results, kept distinct from the original-period comparison.
6. Agreed extension, evaluation, limitations, and usefulness.

Generate every empirical statistic in tables and prose from code. Use LaTeX
inputs/macros and figure files from `_output/`. A caption should state the finding
and why the reader should care. The project report is currently a skeleton;
it contains no empirical results.

The site should contain dataset lineage, charts, clear source/access metadata,
and a project-specific notebook tour. End-to-end build dependencies must connect
data, tests, outputs, notebook, report, and site. The `doit` default now builds
implemented research tasks from local data and rejects missing required years;
the final screenshot pipeline is still incomplete. Publishing remains separate;
see the build guide.

## Cleanup audit

No removed file contained ITI analysis or unique required data. The removed
FRED/OFR/Bloomberg/R/Stata tasks referenced absent or irrelevant example files.
The generic weighted-statistics library was unused and can be recovered from
Git if a specific function becomes useful. The plain article replaces the
example reports; booktabs, graphics, and bibliography support remain.

ChartBook, Jupyter, Jupytext, plotting, statistics, WRDS, and testing dependencies
remain. XGBoost has now been added. A real data-tour notebook and corresponding
build task must be implemented later; the deleted interactive tutorial does not
satisfy that requirement. GitHub Pages deployment also still needs configuring.
No old template restoration is needed to implement these capabilities.

`reference/` is now ignored so the local PDF and screenshots stay outside Git.
The current project still needs dependency/version standardization, committed
research date constants, credential-free tests, and full build integration.
The old 1913–2024 settings defaults are not a verified research sample.

## Sources and limits

- Local `reference/Informed Trading Intensity.pdf`, including Internet Appendix,
  plus all 13 images under `reference/replication_targets/`.
- [Project instructions and rubric](https://finm-32800.github.io/FinalProject/final_project_rubric.html).
- [Project list](https://finm-32800.github.io/FinalProject/potential_final_projects.html)
  and the assignment message supplied in chat.
- [Course previews](https://finm-32800.github.io/FinalProject/project_previews.html)
  and selected linked project sources above.
- [Author data page](https://bogousslavsky.github.io/data/).

The initial review did not attempt WRDS access. Subsequently, WRDS access was
verified, the author archive was inspected, and source-data collection began.
Collection is now stopped at the user's request, with a 2005–2019 target and
2004 warm-up history. See the [data acquisition inventory](data_acquisition.md)
for actual coverage, teammate instructions and unresolved inputs. Downloaded
data have not yet been turned into validated research results.
