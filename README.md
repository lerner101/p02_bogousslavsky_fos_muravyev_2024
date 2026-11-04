# Informed Trading Intensity

Replication and extension of Bogousslavsky, Fos, and Muravyev (2024),
*Informed Trading Intensity*, The Journal of Finance 79(2), 903–948.

Group: Jacob Lerner, Andrew Arbitman, Andrew McLaughlin, and Nate Lee.

## Status

The ChartBook scaffold is initialized. Source-data acquisition has started for
2005–2019, with 2004 warm-up history. Feature construction, cleaned 13D labels,
ITI estimation, event studies, pricing tests, and validation are not yet
implemented. No research results are currently produced.

See the [data acquisition inventory](docs_src/site/project_overview/data_acquisition.md)
for sources, collection commands, coverage, and remaining gaps.

## Setup

From the repository root, create and activate a Python environment, then install
its dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
Copy `.env.example` to `.env` and set your WRDS username and local paths when
using data access. Never commit credentials or licensed raw data. Each teammate
needs their own WRDS login and product access; see the
[data setup and resume instructions](docs_src/site/project_overview/data_acquisition.md).

## Commands

```bash
doit                            # Create data/output directories only
doit list                       # List available tasks
doit build_chartbook_site       # Build the ChartBook site into docs/
doit report                     # Compile reports/report.pdf
python src/download_public_data.py    # Obtain public source archives
python src/prepare_public_data.py     # Prepare public inputs through 2019
python src/collect_wrds.py core indicators lending links --end-year 2019
python src/collect_wrds.py sec --start-year 2005 --end-year 2019
python src/data_status.py             # Inspect completed data in this checkout
```

The report requires a LaTeX distribution with `latexmk` and `pdflatex`.
The default build currently creates directories only; research tasks and their
dependencies will be added as the replication is implemented.

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

- Build TAQ-based features and Schedule 13D purchase labels.
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

No project tests exist yet. Add meaningful tests alongside the research modules;
run them with `python -m pytest`. GitHub Actions runs tests on pushes and pull
requests once test files exist. Each pull request must be reviewed by a teammate
before merging.
