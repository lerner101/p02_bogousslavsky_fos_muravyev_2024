# Running and handing off the build

## What plain doit does

After installing `requirements.txt`, run from the repository root:

```bash
python -m doit
```

`doit` and `python -m doit` use the same tasks; the latter makes the Python
environment explicit. The default `research` task builds the **implemented**
pipeline: input checks, tests, 13D parsing/linking/extraction/labels/validation,
extractor evaluation, BFKR preparation and preliminary Figure 4(c), the data
inventory and `_output/build_summary.md`. The build summary lists outputs and
remaining screenshot work. Existing outputs are reused when their dependencies
have not changed; preflight checks and tests run on each request.

This is not a completed implementation of all thirteen screenshots. The news
chart remains a preview, and features, model training and the remaining final
exhibits remain unfinished. Successful execution of the implemented tasks must
not be described as a completed paper replication.

## Does the command include the data?

**It uses local data; it does not download them automatically.** `_data/`,
`_output/`, the supplied replication ZIP and local reference screenshots/PDFs
are excluded from Git. A repository clone alone is not enough to run the
research tasks. Do not include a teammate's credentials in a handoff.

The default build currently requires:

| Local input | Required scope |
|---|---|
| `_data/wrds/crsp_daily/YYYY.parquet` and matching `.json` | Every year 2004–2019 |
| `_data/wrds/sec_13d_filings/YYYY.parquet` and matching `.json` | Every year 2005–2019 |
| `_data/wrds/crsp_names`, `crsp_market`, `sec_cusip_links`, `compustat_earnings`, `crsp_compustat_links` | Each `.parquet` and matching `.json` pair |
| `_data/public/iti_original_through_2019/` | Manifest and all partitions for 2004–2019 |
| `_data/public/InformationTradingVolatility_DataFile.csv` | BFKR public source CSV |

Preflight checks validate completed Parquet footers, manifest row counts and
the expected file years. They do not certify economic definitions or final
sample equivalence. Partial `.part` files do not count. Current source readers
use repository-local paths, so custom `DATA_DIR`, `OUTPUT_DIR` or
`THIRTEEN_D_DIR` overrides are rejected by preflight to avoid mixing task
dependencies and actual inputs.

**As of November 8, this checkout lacks CRSP daily 2015–2019**, so its default
build stops with an actionable missing-input message before building the 13D
labels. The BFKR preview can run separately with its available inputs:

```bash
python -m doit bfkr_preview
```

## First-time setup / professor handoff

1. Install Python 3.13 and dependencies as described in the README.
2. Supply the required local data in the paths above. A permitted data handoff
   must include each WRDS `.json` sidecar and the ITI preparation manifest, not
   just the Parquet files. Do not redistribute licensed data without permission.
3. Run `python -m doit preflight` to verify the handoff, then `python -m doit`.
4. Inspect `_output/build_summary.md` and the validation reports; share those
   reports with the code, subject to the applicable data restrictions.

If collecting rather than transferring permitted inputs, explicitly request:

```bash
python -m doit fetch_public
python -m doit prepare_public
# Configure your own WRDS username, libpq credentials and product access first:
python -m doit collect_wrds
python -m doit
```

`fetch_public` downloads public archives and the BFKR CSV (roughly 1.5 GB total,
skipping valid saved sources). `prepare_public` rebuilds the scoped public
outputs from those archives. These are explicit setup tasks, not automatic
dependencies of the default research build. Original archives need not be
included in a data handoff if the required prepared data are already supplied.

`collect_wrds` requests all currently implemented source groups, including some
inputs for analyses not yet implemented. It skips completed WRDS Parquet/JSON
pairs, restarts unfinished years and checks all expected extracts after
collection; a source failure must not appear as a successful acquisition task.
It requires network access and the user's own WRDS product subscriptions.

## Checks without research data

```bash
python -m doit list
python -m doit check
```

The check task runs synthetic unit/build tests; it does not fetch data. If local
filing extracts exist, the existing audit test also evaluates them. CI uses this
path because GitHub Actions has neither licensed inputs nor WRDS credentials.

## Report and site

```bash
python -m doit report
python -m doit build_chartbook_site
```

These are separate publishing tasks. `report` needs `latexmk` and a LaTeX
installation; the report is currently a skeleton. The ChartBook site task
depends on the implemented research summary and needs the `chartbook` command.
Neither publishing tool is required just to run the research tasks. Final
report/exhibit integration must be added as the research is completed.
