# Methodology

## Schedule 13D trade-day labels

The model is trained to recognise days when a Schedule 13D filer traded. The authors'
hand-collected label file (`sc13_1994_2018.dta`) is not public, so we rebuild labels
for filings made 2005–2019 from the full text of original SC 13D submissions (WRDS
`wrds_sec_search.filing_sc_13d`). The output uses the authors' column layout,
documented in `build/get_13D.py` of their replication package, so training code
written for their file can read ours.

### What the authors' code fixes

- `itrade` = 1 if the filer bought **or** sold that day. About 6% of their trades are
  sales.
- `ivol` is a signed **dollar** amount (sales negative). `ITI_main.py` computes filer
  turnover as `|ivol| / (prc × shrout × 1000)`, which only makes sense in dollars,
  even though the docstring says "number of shares bought".
- One row per stock and trading day. A filing is identified by (`permno`,
  `filing_date`), and `days_to_filing` counts calendar days.
- Patient days are the first 40 calendar days of the window (`days_to_filing` > 20),
  impatient days the last 20.
- The filer's share of daily volume is capped at 1. Both turnover measures are
  winsorized at 0.05% in analysis.

The package contains no 13D extraction code, no model-training code and no
cross-validation code.

### Pipeline

Each step has a script in `src/` and a `doit` task (`doit 13d_validation` runs all of
them; they are not part of the default build because they need local WRDS data).

1. **`parse_13d_filings.py`** reads the SGML header (subject and filer CIK), the cover
   page (issuer name, CUSIP, event date) and locates Item 5. EDGAR headers are
   sometimes wrong (a filer listed as its own subject), and "CUSIP No." page headers
   are sometimes copied from another filing, so the cover-page CUSIP is tried first.
2. **`link_13d_crsp.py`** matches CUSIP candidates to CRSP's historical `ncusip`, then
   falls back to the subject CIK through WRDS's CIK–CUSIP table. A link is kept only if
   the cover issuer name (or header subject name) resembles *some* CRSP name of that
   PERMNO, which tolerates renames.
3. **`extract_13d_transactions.py`** reads trades from the Item 5(c) block, the
   schedule or exhibit it references, and exhibits that read like transaction lists.
   It handles one-cell-per-line tables, one-row-per-line tables, sales in
   parentheses or with a trailing minus, side words and "(S)/(P)" markers, separate
   Purchased/Sold columns, total-dollar columns, footnote markers and prose
   sentences. A row must have a date inside the filing window, a quantity and a price.
4. **`build_13d_labels.py`** applies the screens below and writes `events.parquet` and
   `labels_daily.parquet`.
5. **`validate_13d_labels.py`** compares the labels with the paper's statistics.

### Screens (paper Section 2 and footnote 5)

In order, with the first failure recorded per filing: linked to CRSP with a name
match; CRSP share code 10/11; price ≥ $5 and market cap ≥ $100M on the first trading
day of the window; no derivative trades in the window; at least one priced, dated
trade by a group member. Filings with the same (`permno`, `filing_date`) are pooled.

### Decisions

| Question | Choice | Why |
|---|---|---|
| Label definition | Buys and sells | Authors' `itrade` |
| Trades by entities the filing says are not group members | Excluded | They are not the filer's informed trades |
| 2019 filings | Built, flagged `in_paper_period = False` | Paper's 13D sample ends in 2018 |
| Window | Trading days with filing date − 60 ≤ date ≤ filing date | Paper; rows outside are dropped even if listed |
| Dollar amount | Shares × disclosed price | Authors' `ivol` is dollars |
| Non-open-market acquisitions without a price (IPO allocations, conversions, spin-offs) | Not extracted | Not open-market trading; no price to form `ivol` |

### Extraction accuracy

Scored by `evaluate_13d_extraction.py` against hand transcriptions in
`data_manual/13d_audit/` (see its README). The transcriptions were made by agents
that read the filings without seeing the extractor and **have not yet been verified
by a person**.

Matching is on (accession, trade date, side, shares). "Open-market" rows exclude
derivatives; "trade days" drive `itrade`.

| Sample | Level | Recall | Precision |
|---|---|---:|---:|
| Tuning (30 filings, in-sample) | open-market rows inside the window | 100.0% | 95.4% |
| Tuning | open-market trade days | 95.7% | 99.1% |
| **Holdout (15 filings), frozen extractor** | open-market rows | **84.6%** | **93.6%** |
| **Holdout, frozen extractor** | open-market trade days | **89.7%** | **100.0%** |
| Holdout after two further fixes (no longer out-of-sample) | open-market trade days | 100.0% | 100.0% |

The frozen holdout score is the honest out-of-sample number; the two fixes it
prompted (sales marked "(S)", total-dollar columns) were then applied. A fresh
holdout is needed to re-measure. Extracted rows are almost never spurious; misses
are mostly unusual layouts and non-open-market acquisitions without prices, which
are not extracted by design.

### Validation against the paper

`validate_13d_labels.py` writes `_output/13d_label_validation.md`. Headline results
for events filed 2005–2018:

- **Event counts.** 27,622 original filings → 2,279 included events (2,186 filed
  2005–2018). Most exclusions are unlinked issuers (not CRSP common stock) and
  filings without open-market trades (merger agreements, IPO and private
  acquisitions).
- **The authors' events can be identified.** The posted ITI file blanks the three
  13D-trained scores inside the authors' training windows (0.44% of rows; the paper
  says excluding them "drops 0.35% of the sample"). `authors_13d_windows.py`
  recovers 1,100 windows ending 2005–2018, median 41 trading days. Our pipeline
  includes **83.5%** of them; 97 fail the has-trades screen and 66 have no linked
  filing. Only **42.5%** of our included events are authors' events: the authors'
  hand-curated sample is narrower, and no simple screen reproduces it. The
  `in_authors_sample` flag lets training use either sample.
- **Labels vs paper.** Share of trade days 0.357 (authors' events 0.381; paper
  0.360); patient/impatient 0.315/0.435 (authors' events 0.326/0.485; paper
  0.30/0.49); mean filer turnover ×100 0.285 (paper 0.276); sales 12.6% of trade
  days (authors' events 8.5%; paper about 6%).
- **Open gap: filer share of daily volume** is about 0.14 in both samples against the
  paper's 0.28. It does not come from sample selection. A plausible cause is higher
  market volume in 2005–2018 than in 1994–2004, but this is unconfirmed.
- **Abnormal return around filing** (2,058 events): +1.3% from day −40 to −1 (paper
  about 3%) and +1.95% on days 0 to +1 (paper about 2%).
- **Posted ITI(13D)** is higher on our trade days (0.367) than non-trade days (0.303).
