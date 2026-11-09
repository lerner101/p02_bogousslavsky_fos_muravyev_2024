# Informed Trading Intensity

Replication and extension of Bogousslavsky, Fos, and Muravyev (2024),
*Informed Trading Intensity*, The Journal of Finance 79(2), 903–948.

Group: Jacob Lerner, Andrew Arbitman, Andrew McLaughlin, and Nate Lee.

## Status

Source-data acquisition covers a working target of 2005–2019, with 2004 warm-up
history. Schedule 13D extraction, label construction and validation code are
implemented; independent label verification remains outstanding. BFKR news
linking and a preliminary Figure 4(c) regression are implemented. Complete
features, model training, final event samples and pricing tests remain unfinished;
no final screenshot replication is claimed.

See the [data acquisition inventory](docs_src/site/project_overview/data_acquisition.md)
for sources, collection commands, coverage, and remaining gaps.

## Dataset inventory

Snapshot of **this checkout, November 8, 2026**. Git does not include `_data/`;
other teammates may have more complete extracts. Our working analysis period is
**2005–2019**, with **2004 warm-up**; comparisons to the paper's general sample
stop in **July 2019**. The paper's 13D training filings end in **2018**. Dataset-
specific periods below take precedence over that general scope.

**T = Table; F = Figure.** These refer to the 13 screenshots in
`reference/replication_targets/`: T1–5, T9–11, F1–4, and FIA5. An exhibit listing
can indicate a direct input or an upstream dependency needed to rebuild its ITI
model. Posted ITI can bypass model training for some downstream exhibits, but
cannot replace out-of-fold training predictions or fitted models. BFKR is needed
only for **F4(c)**; BCL only for **T9's BCL row**.

`YYYY` and `*` denote file patterns. **PROPOSED** paths are naming suggestions,
not existing datasets or implemented outputs. Combined source extracts can
extend past 2019 and must be filtered. The downloadable
[CSV inventory](data_manual/dataset_inventory.csv) also records source names,
exact screenshot filenames, status notes and dependency roles.

| Dataset / source | Current local period | Paper period and comparison | Used for | Screenshots | Repository files | Status |
|---|---|---|---|---|---|---|
| CRSP daily stocks — WRDS crsp.dsf | 2004-2014 complete; later partials unusable | 1993-07/2019 general sample; 1994-2018 13D sample<br>Missing 1993-2003 and local 2015-2019; project starts later | Prices; returns; shares outstanding; volume; sample screens; turnover; feature inputs | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/wrds/crsp_daily/YYYY.parquet` | Partially acquired |
| CRSP historical security names — WRDS crsp.dsenames | Name records overlapping 2004-2024 | History covering each exhibit sample; as early as 1993<br>Historical records ending before 2004 absent | Dated common-stock filters; historical ticker/CUSIP/PERMNO links | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/wrds/crsp_names.parquet` | Acquired; date filtering required |
| CRSP delisting returns — WRDS crsp.dsedelist | Extract requested 2004-2024 | 1993-07/2019 pricing sample<br>Earlier years absent; filter later records | Account for delisting returns in future returns and portfolios | T10; T11 | `_data/wrds/crsp_delistings.parquet` | Acquired; transformations missing |
| CRSP market returns — WRDS crsp.dsi | 2004-2024 | 1993-07/2019 pricing/market history<br>Earlier history absent | Market returns and CAPM beta input | T10 | `_data/wrds/crsp_market.parquet` | Acquired; transformations missing |
| CRSP-Compustat links — WRDS crsp.ccmxpf_linktable | Combined historical link table; no extraction date restriction | Effective-date links covering earnings sample 1993-07/2019<br>Link history may cover earlier dates; other inputs limit usable sample | Link Compustat earnings gvkeys to PERMNOs | F4(a-b); F4(c) | `_data/wrds/crsp_compustat_links.parquet` | Acquired |
| TAQ daily intraday indicators — WRDS taqm_YYYY.wrds_iid_YYYY | 2004-2007 complete | 1993-07/2019 general sample; 1994-2018 training events<br>Earlier history and local 2008-2019 missing; historical schemas require reconciliation | Liquidity; signed volume; trading-activity features and regression controls | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/wrds/intraday_indicators/YYYY.parquet` | Partially acquired |
| TAQ-CRSP daily links — WRDS wrdsapps_link_crsp_taqm.taqmclink | 2004-2019 complete | History aligned with TAQ features from 1993<br>Project interval covered; original earlier period not collected | Link daily TAQ symbols and suffixes to PERMNOs | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/wrds/crsp_taq_links/YYYY.parquet` | Acquired |
| Supplemental TAQ intervals and liquidity — WRDS TAQ; bounded server-side aggregation needed | Not acquired | 1993-07/2019; training windows through 2018<br>Absent; required to rebuild complete paper feature set | 30-minute midquote returns; interval volumes; overnight/intraday volatility and illiquidity; paper depth definitions | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/wrds/taq_supplemental/YYYY.parquet [PROPOSED]` | Missing data and collector |
| Original Schedule 13D filings and index — WRDS SEC filing text and forms | 2005-2019 complete | 1994-2018 training filings<br>1994-2004 absent; 2019 is outside paper training period | Rebuild transaction labels and filing windows | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/wrds/sec_13d_filings/YYYY.parquet`<br>`_data/wrds/sec_13d_index/YYYY.parquet` | Acquired; labels not independently verified |
| SEC CIK-CUSIP links — WRDS wrdssec_common.wciklink_cusip | Combined historical table | Historical matches for 1994-2018 filings<br>Usable coverage depends on filings and CRSP names | Fallback historical issuer identification for 13D linking | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/wrds/sec_cusip_links.parquet` | Acquired |
| Rebuilt 13D events and daily labels — Project extraction and screening pipeline | Not materialized in this checkout | 1994-2018; 1593 filings and 58197 stock-days<br>Shorter period and reconstructed sample; not authors ground truth | Trade-day indicator; signed filer dollars; patient/impatient windows; model training | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/derived/13d/filings.parquet`<br>`_data/derived/13d/filing_links.parquet`<br>`_data/derived/13d/transactions.parquet`<br>`_data/derived/13d/events.parquet`<br>`_data/derived/13d/labels_daily.parquet` | Code implemented; full local run pending |
| Inferred author 13D windows — Blanks in original posted ITI | Recovery code exists; output not materialized locally | Authors training events 1994-2018<br>Approximation from missing scores; shorter available history | Diagnose overlap with authors training sample; not transaction ground truth | T1; T2; T3; T4; T9; F1; F2; F3 | `_data/derived/13d/authors_windows.parquet` | Code implemented; local output pending |
| Original posted ITI scores — Authors public ITI archive | Prepared 2004-2019; original archive contains 1993-2019 | 1993-07/2019 general sample<br>Earlier source history available but not prepared locally | Five supplied ITI variants for downstream analyses and model validation | T1; T5; T9; T10; T11; F4; FIA5 | `_data/public/iti_original_through_2019/year=YYYY/part-*.parquet`<br>`_data/public/ITIs_extended_1993_2024.zip` | Acquired and prepared |
| Updated posted ITI scores — Authors refreshed public release | Prepared 2004-2019; archive extends 1993-2024 | Screenshots use original vintage<br>Different vintage; not the exact screenshot input | Sensitivity comparison and potential extension | T1; T5; T9; T10; T11; F4; FIA5 | `_data/public/iti_extended_through_2019/year=YYYY/part-*.parquet` | Acquired; optional for original screenshots |
| Daily PIN APIN GPIN OWR and mechanical-trading measures — Edwin Hu legacy release | Prepared 2004-2012; source 1993-2012 | Table 9 sample 1994-2012<br>Earlier source years available but not prepared | Alternative informed-trading measures and mechanical-trading control | T9 | `_data/public/pin_legacy_daily_through_2019/year=YYYY/part-*.parquet`<br>`_data/public/cpie_data.zip` | Acquired and prepared |
| BCL CPIE — Back-Crotty-Li measure; Kevin Crotty/ITI authors | Absent | Table 9 comparison sample 1994-2012; exact source coverage to confirm<br>Exact input unavailable locally | BCL comparison row only | T9 | `_data/public/cpie_13d.zip [EXPECTED AUTHORS FILENAME`<br>`NOT PRESENT]` | Missing; no confirmed public download |
| Brown-Hillegeist annual PIN — Authors replication ZIP | Prepared 2004-2010; source 1993-2010 | Annual PIN source 1993-2010; T10(a) column 6 uses available overlap<br>Earlier source data available but not prepared | Annual PIN control in return-predictability regression | T10(a) | `_data/public/pin_brown_annual_2004_2010.parquet`<br>`Replication Code-20220087.zip` | Acquired and prepared |
| Insider transactions — WRDS tr_insiders.table1 | 2004-2014 complete | Insider label sample 1993-2012; T9 common sample 1994-2012<br>Early sample and classification history absent; local later years incomplete | Opportunistic/routine labels; insider ITI; separate buy/sell model training | T1; T9; T10; T11 | `_data/wrds/insider_transactions/YYYY.parquet` | Partially acquired; classification/model code missing |
| Securities lending and short-demand inputs — WRDS Markit analytics | 2006-2018 complete | Short-spike sample 06/2006-12/2010; general posted short ITI extends later<br>Label period broadly available; local 2019 absent | Short-demand normalization and spikes; short ITI training | T1; T9; T10; T11 | `_data/wrds/markit_lending/YYYY.parquet` | Partially acquired; labels/model code missing |
| Compustat earnings announcement dates — WRDS comp.fundq rdq | 2004-2024 | Figure 4(a-b): 1993-07/2019; Figure 4(c): 2000-2015<br>Earlier earnings absent; raw dates need after-hours adjustment | Earnings events; announcement-return groups; exclude earnings near news | F4(a-b); F4(c) | `_data/wrds/compustat_earnings.parquet` | Acquired raw; final timing adjustment missing |
| Adjusted earnings events — Project preparation from earnings and timing/volume inputs | Only unadjusted diagnostic output available | Same event coverage as Figure 4; authors use volume-adjusted Compustat dates<br>Final input absent | After-hours correction and earnings-window exclusions | F4(a-b); F4(c) | `_data/derived/bfkr/earnings_unadjusted.parquet [EXISTS]`<br>`_data/derived/events/earnings_adjusted.parquet [PROPOSED]` | Unadjusted preview implemented; final dataset missing |
| BFKR VIP news classifications — Public Dropbox file linked by BFKR authors | 2000-2015 | Figure 4(c): 2000-2015 S&P 500 stocks<br>Raw source covers paper period; identifier/ITI/earnings coverage limits local analysis | News-day classification and event timing | F4(c) | `_data/public/InformationTradingVolatility_DataFile.csv`<br>`_data/derived/bfkr/news_daily.parquet`<br>`_data/derived/bfkr/news_link_audit.parquet` | Acquired; linked; preliminary regression implemented |
| M&A deal records — WRDS SDC tr_sdc_ma.wrds_ma_details | 2004-2024 | Figure IA.5: 1996-2010; 1577 target events<br>1996-2003 absent; target filtering and historical links unfinished | Identify public target announcement dates and event windows | FIA5 | `_data/wrds/sdc_ma.parquet`<br>`_data/derived/events/ma_targets.parquet [PROPOSED]` | Raw acquired; event dataset missing |
| Fama-French factors momentum and risk-free return — Kenneth French library | Daily prepared 2004-2019 | Table 11 pricing sample 1993-07/2019<br>Earlier years not prepared; must aggregate/align to portfolio holding periods | Four-factor portfolio alphas and excess returns | T11 | `_data/public/ff4_daily_2004_2019.parquet` | Acquired; portfolio-factor alignment missing |
| Complete features and paper controls — Project CRSP/TAQ feature construction | Not built | 1993-07/2019; 13D windows 1994-2018<br>Missing feature construction and supplemental inputs | 41 training features; eight regression controls; prior-year scaling; paper universe | T1; T2; T3; T4; T5; T9; T10; T11; F1; F2; F3; F4; FIA5 | `_data/derived/features/year=YYYY/part-*.parquet [PROPOSED]`<br>`_data/derived/panels/paper_controls.parquet [PROPOSED]` | Missing; filenames proposed |
| Out-of-fold and feature-group predictions — Project nested model training | Not built | 1994-2018 labeled training events<br>Missing training pipeline and authors OOF artifacts | Honest training-window evaluations; group models; stability; model explanations | T2; T3; T4; T9; F1; F2; F3 | `_data/derived/models/13d_oof_predictions.parquet [PROPOSED]`<br>`_data/derived/models/13d_group_predictions.parquet [PROPOSED]` | Missing; filenames proposed |
| Insider buy/sell predictions — Project separate opportunistic insider models | Absent; ZIP has example 2000-2001 slices only | Table 10(b) general sample 1993-07/2019 subject to model coverage<br>Full-period predictions unavailable | Separate insider buy and sell regressors | T10(b) | `_data/derived/models/insider_buy_sell_predictions.parquet [PROPOSED]`<br>`Replication Code-20220087.zip` | Missing full sample; filenames proposed |
| Weekly pricing and portfolio panel — Project aggregation of ITI CRSP and controls | Not built | 1993-07/2019<br>Shorter history and transformations missing | Prior-week scores; future monthly returns; beta; momentum; volatility; Amihud; portfolio formation | T10; T11 | `_data/derived/panels/weekly_pricing.parquet [PROPOSED]` | Missing; filename proposed |

## Setup

Use Python 3.13 and `uv` to create the environment and install dependencies.
Python 3.14 may select package versions without compatible wheels for this
project's dependency set, causing pip to attempt a local source build.

```bash
uv venv --python 3.13 .venv-py313
source .venv-py313/bin/activate
uv pip install -r requirements.txt
```

On Windows, activate with `.venv-py313\Scripts\Activate.ps1` in PowerShell.
Copy `.env.example` to `.env` and set your WRDS username and local paths when
using data access. Never commit credentials or licensed raw data. Each teammate
needs their own WRDS login and product access; see the
[data setup and resume instructions](docs_src/site/project_overview/data_acquisition.md).

## Commands

```bash
doit                            # Build implemented research outputs from local data
doit preflight                  # Check required local data before building
doit check                      # Run tests; no downloads or credentials required
doit list                       # List available tasks
doit build_chartbook_site       # Build the ChartBook site into docs/
doit report                     # Compile reports/report.pdf
python src/download_public_data.py    # Obtain public source archives
python src/prepare_public_data.py     # Prepare public inputs through 2019
python src/collect_wrds.py core indicators lending links --end-year 2019
python src/collect_wrds.py sec --start-year 2005 --end-year 2019
python src/data_status.py             # Inspect completed data in this checkout
doit fetch_public                    # Explicit public downloads, including BFKR CSV
doit prepare_public                  # Rebuild prepared public inputs from local archives
doit collect_wrds                    # Explicit licensed WRDS collection; own access required
python src/prepare_bfkr_news.py       # Link the locally supplied BFKR news CSV
doit bfkr_preview                    # Preliminary Figure 4(c); see limitations below
```

The report requires a LaTeX distribution with `latexmk` and `pdflatex`.
The default build runs the implemented 13D and preliminary news pipelines,
tests and validation reports. It **requires local `_data/` inputs** and does
**not download data automatically**. A clone alone cannot reproduce the research
outputs. This checkout still needs CRSP daily 2015–2019 before the full default
build can pass. The pipeline does not yet reproduce all 13 screenshots.

See the [build and professor handoff instructions](docs_src/site/project_overview/build.md)
for exact required data, first-time acquisition commands, outputs, and the
credential-free CI/check path. With a complete permitted data handoff, the
professor can run `python -m doit` without WRDS credentials or original archives.

The BFKR news preview uses unadjusted earnings dates and an incomplete sample
screen; it is not a final replication. See the [news analysis instructions](docs_src/site/project_overview/bfkr_news.md)
for input requirements, outputs and the final-analysis command.

## Project Structure

- `src/`: project configuration and future research modules.
- `dodo.py`: PyDoit build tasks.
- `_data/`: reproducible local data, excluded from Git.
- `_output/`: generated tables, charts, and notebooks, excluded from Git.
- `data_manual/`: documentation and permitted manual inputs.
- `reports/report.tex`: the single project report.
- `docs_src/`: project documentation for the ChartBook site.
- `chartbook.toml`: project metadata and future artifact registrations.

## Assigned Work

- Build TAQ-based features and Schedule 13D trade-day labels (buys and sells,
  as in the authors' `itrade`).
- Replicate ITI estimation and model performance.
- Replicate event evidence and asset-pricing results.
- Benchmark against PIN and VPIN on a common sample.
- Validate against the authors' posted ITI series.
- Extend the measure beyond the posted series.

Confirm the exact paper version and assigned exhibits with the instructor.

See [the replication and consultation plan](docs_src/site/project_overview/replication_plan.md)
and [the draft consultation pitch](docs_src/site/project_overview/consultation_pitch.md).
Store local paper PDFs and exhibit screenshots in `reference/`, which is ignored
by Git.

## Extension

Pending agreement at the instructor consultation. Record the agreed scope here
after the meeting.

## Tests and Collaboration

Tests cover Schedule 13D parsing/extraction and BFKR historical links and news
regressions. Run them with `python -m pytest`. GitHub Actions runs tests on pushes
and pull requests. Each pull request must be reviewed by a teammate before merging.
