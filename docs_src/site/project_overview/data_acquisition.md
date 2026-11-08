# Data acquisition: 2005 onward

The working collection period is January 2005–December 2019. January–December
2004 is retained as warm-up history for lagged variables and scaling. Comparisons
to the original paper stop in July 2019. The extension is undecided.
Previously downloaded later-year files are retained, outside the current scope.
Individual datasets have shorter coverage. Starting in 2005 changes the sample
and does not reproduce the paper's full-period estimates.

## Collection status

As of November 6, 2026, every WRDS and public extract in the source map below
is complete in at least one teammate checkout for its full available range:
2004–2019 for market data (13D filing text 2005–2019, Markit 2006–2019,
legacy PIN 2004–2012). Run `python src/data_status.py` to verify your own
checkout; it validates each Parquet footer against its manifest row count.

Original/refreshed ITI scores, factors, legacy PIN measures, earnings dates and
M&A source extracts have been obtained within their available coverage. Scores
and raw sources are not a completed replication. In particular, the saved 13D
filings are text, not cleaned transaction labels. Existing combined earnings,
M&A and other source files can include observations after 2019; apply date filters.

## Run from a teammate's checkout

1. Clone/pull the repository and install its requirements using the README's
   virtual-environment instructions. Run commands below from the repository root.
2. Use your **own WRDS account and subscriptions**. Copy `.env.example` to `.env`
   and set `WRDS_USERNAME`. The collector reads that file without displaying it.
   Configure your own libpq password file; never copy a teammate's credentials.
   One interactive setup route using the installed WRDS package is:

   ```bash
   python -c "import wrds; db = wrds.Connection(); db.create_pgpass_file(); db.close()"
   ```

   On macOS/Linux the default libpq file is `~/.pgpass`; restrict it to your user
   (`chmod 600 ~/.pgpass`). If using a different file, including on Windows, set
   `PGPASSFILE` to its absolute path in your local `.env`. Login/MFA and product
   access depend on your own WRDS account.
3. Download and prepare the public inputs:

   ```bash
   python src/download_public_data.py
   python src/prepare_public_data.py
   ```

   These download about 1.5 GB of source archives. The ITI archive includes wider
   history, but prepared output is restricted through 2019. The optional journal
   replication ZIP is available from the paper's
   [Supporting Information](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13320).
   Save it as `Replication Code-20220087.zip` at the repository root to also
   prepare its Brown–Hillegeist annual PIN input. The ZIP is not in GitHub.
4. Collect WRDS inputs sequentially, or select individual groups:

   ```bash
   python src/collect_wrds.py core indicators lending links --end-year 2019
   python src/collect_wrds.py sec --start-year 2005 --end-year 2019
   python src/data_status.py
   ```

   A new checkout downloads its own data. GitHub does not contain `_data/`.
   Institutionally permitted transfers must be arranged separately; access to
   this repository does not grant data-product rights.

## Resume this checkout later

Run only the unfinished groups; completed files will be skipped:

```bash
python src/collect_wrds.py core indicators lending --end-year 2019
python src/data_status.py
```

Stop a foreground collector with **Ctrl+C**. Completed Parquet/JSON pairs stay
saved. The currently unfinished year restarts on the next run; `.part` files
are not resumed byte-by-byte. Do not run two collectors for the same group/year
in the same checkout. The commands run locally and stop making progress if the
computer sleeps. The scripts are separate from the current `doit` default task.

## Files and reproducibility

All downloaded research data are in ignored `_data/`, not in Git. The original
replication ZIP is an input supplied by the user and is read in place from the
repository root (it is ignored by Git); its scripts have not been executed.

- `python src/prepare_public_data.py` converts downloaded public archives into
  compact Parquet files. Original and extended ITI vintages remain separate.
- `python src/collect_wrds.py core indicators lending links sec` obtains the
  authenticated WRDS source extracts. It includes 2004 warm-up history by default.
  Use `--start-year` and `--end-year` to change the extract range.
  The default end year is 2019. Already-saved combined source extracts may cover
  a wider period; filter them to the analysis dates before use. Public preparation
  writes scoped `*_through_2019/` directories and preserves the older wider outputs.
- Each completed WRDS extract has a `.parquet` file and a `.json` sidecar with
  its SQL, row count, date coverage, retrieval time, and size. Incomplete files
  end in `.part` and must not be treated as completed data.
- Completed extracts are skipped on reruns. Remove both the Parquet and sidecar
  for an extract to refresh it. Source revisions can change replication results.
- `python src/data_status.py` validates readable Parquet footers against manifest
  row counts and refreshes `_output/data_acquisition_status.md`. This is a
  snapshot of completed downloads, not a claim that every source is finished.
- Existing WRDS credentials are read through libpq and `~/.pgpass`; no passwords
  are copied into the project. The scripts use read-only database transactions.

## Source map

| Input | Source / local location | Interpretation |
|---|---|---|
| Original and extended ITI | [Author data page](https://bogousslavsky.github.io/data/), `_data/public/iti_original_through_2019/` and `iti_extended_through_2019/` | Supplied scores, not a model trained by this project |
| Daily PIN-family CPIE | [Edwin Hu legacy release](https://github.com/edwinhu/pin-code/releases/tag/legacy-1993-2012), `_data/public/pin_legacy_daily_through_2019/` | Original daily PIN, DY/APIN, GPIN and OWR comparisons, through 2012 |
| Brown–Hillegeist annual PIN | Supplied replication ZIP, `return_predictability/pin_brown_annual.dta` | This input spans 1993–2010 despite the ZIP's other example market-data slices being limited to 2000–2001; retained 2004–2010 in `_data/public/pin_brown_annual_2004_2010.parquet` |
| Four-factor inputs | [Kenneth French library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), `_data/public/ff4_daily_2004_2019.parquet` | Market, SMB, HML, momentum and risk-free rate; percentage inputs converted to decimal returns |
| Daily stocks and links | WRDS `crsp.dsf`, `dsenames`, `dsedelist`, `dsi`, `ccmxpf_linktable`, `_data/wrds/` | Source extracts include non-common stocks; apply dated stock/sample filters later |
| Earnings dates | WRDS `comp.fundq`, `_data/wrds/compustat_earnings.parquet` | Raw `rdq`; the paper's volume-based after-hours adjustment remains to implement |
| M&A | WRDS `tr_sdc_ma.wrds_ma_details`, `_data/wrds/sdc_ma.parquet` | Raw deal records; US public target/acquirer filters and historical CRSP linking remain |
| Insider transactions | WRDS `tr_insiders.table1`, `_data/wrds/insider_transactions/` | Routine/opportunistic classification, cleansing, linking and train/test design remain |
| Securities lending | WRDS `markit_msf_analytics_eqty_amer.amereqtyYYYY`, `_data/wrds/markit_lending/` | Starts in 2006 for this collection; identifiers, CRSP shares outstanding, settlement timing and spike labels remain to implement |
| Daily intraday indicators | WRDS `taqm_YYYY.wrds_iid_YYYY`, `_data/wrds/intraday_indicators/` | Selected source columns, not yet paper-standardized features; definitions must be reconciled with IA.3 |
| TAQ–CRSP links | WRDS `wrdsapps_link_crsp_taqm.taqmclink`, `_data/wrds/crsp_taq_links/` | Daily links retain suffixes and match levels |
| Original 13D filing text | WRDS `wrds_sec_search.filing_sc_13d`, `_data/wrds/sec_13d_filings/` | Filing text, not cleaned daily transaction labels |
| 13D index and CIK links | WRDS `wrdssec.wrds_forms` and `wrdssec_common.wciklink_cusip` | Index includes amendments for provenance; originals are collected separately for extraction |

## Remaining gaps

1. **Authors' cleaned 13D labels:** `sc13_1994_2018.dta` is absent from the
   supplied replication ZIP, which also contains no 13D extraction code and no
   model-training or cross-validation code. `build/get_13D.py` documents only
   the label file's layout (see the 13D section of the methodology page). We
   rebuild labels from the downloaded filing text; an index or text download
   does not reproduce the 1,593-event sample. The authors' event *windows*
   (PERMNO and dates, not the trades) can be recovered from blanks in the posted
   ITI file; see `src/authors_13d_windows.py`.
2. **Supplemental intraday inputs:** daily indicators do not supply all the
   paper's 30-minute midquote returns, morning/afternoon volumes and derived
   volatility/autocorrelation/illiquidity variables. TAQ access was verified, but
   these intraday inputs still need a bounded server-side extraction. Raw tick
   history has not been bulk-downloaded. New depth fields must be reconciled with
   the original definitions before substitution.
3. **Exact news events:** `bfkr.hdf`, the Boudoukh–Feldman–Kogan–Richardson news
   classifications referenced by the authors, was not obtained. A generic news
   dataset is a different sample.
4. **Back–Crotty–Li CPIE:** `cpie_13d.zip` is absent; the main script credits
   Kevin Crotty. Legacy PIN-family data do not include this comparison measure.
5. **Out-of-fold training predictions and fitted models:** small-sample prediction
   files referenced by `get_13D.py` are absent. Feature-group models, partial
   dependence, and the surrogate tree require retraining or author artifacts.
6. **Longer training history:** 2004 provides one year of market-data warm-up,
   but replicating routine/opportunistic insider classifications requires earlier
   transaction history. The exact historical lookback must be implemented before
   treating early sample labels as comparable.

The public SEC index attempt returned HTTP 403 from this environment; the WRDS
filing-text route worked. No Databento API key was configured in the project or
process environment, and no paid Databento requests were made. WRDS supplies
the primary daily sources used here.

## Important coverage notes

The ITI archive README documents missing extended-series observations on
February 26, 2007 and June 6, 2013 due to unavailable WRDS indicator data.
The extended vintage fills other historical gaps and is different from the
original vintage; keep their analyses separate.

The replication ZIP's return-predictability examples contain only 2000–2001
market-data slices. Those are outside this project's working analysis period
and are not substituted for the new WRDS extracts.
