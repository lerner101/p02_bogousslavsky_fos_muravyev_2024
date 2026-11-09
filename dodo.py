"""Build implemented research outputs from local data; acquisition is explicit.

Plain doit runs preflight, tests, 13D validation, the BFKR preview and an output
summary. This is not yet an implementation of all thirteen screenshot targets.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from settings import config

DOIT_CONFIG = {
    "backend": "sqlite3",
    "dep_file": ".doit-db.sqlite",
    "default_tasks": ["research"],
}


def task_config():
    """Create local data and output directories."""
    data_dir = config("DATA_DIR")
    output_dir = config("OUTPUT_DIR")

    def create_directories():
        data_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

    return {
        "actions": [create_directories],
        "targets": [data_dir, output_dir],
        "file_dep": ["src/settings.py"],
    }


# Research tasks require licensed local WRDS extracts. CI uses `doit check`.
# Explicit inputs prevent missing years from disappearing from glob dependencies.
THIRTEEN_D = config("THIRTEEN_D_DIR")
WRDS = Path("_data/wrds")
SEC_13D_TEXT = [WRDS / "sec_13d_filings" / f"{year}.parquet" for year in range(2005, 2020)]
CRSP_DAILY = [WRDS / "crsp_daily" / f"{year}.parquet" for year in range(2004, 2020)]
ITI = Path("_data/public/iti_original_through_2019")
ITI_PARTS = sorted(str(p) for p in ITI.glob("year=*/*.parquet"))
SETTINGS_DEPS = ["src/settings.py"] + ([".env"] if Path(".env").exists() else [])


def python_action(script, *args):
    """Use the same interpreter as doit, including virtualenv/Windows paths."""
    return [sys.executable, script, *args]


def task_preflight():
    """Check completed input years; fail with acquisition instructions if missing."""
    return {"actions": [python_action("src/build_checks.py")],
            "task_dep": ["config"], "uptodate": [False]}


def task_13d_inputs():
    """Require complete 2004-2019 CRSP, 2005-2019 filings and original ITI."""
    return {"actions": [python_action("src/build_checks.py", "--component", "13d")],
            "task_dep": ["config"], "uptodate": [False]}


def task_bfkr_inputs():
    """Check local news, earnings, historical links and 2005-2015 original ITI."""
    return {"actions": [python_action("src/build_checks.py", "--component", "bfkr")],
            "task_dep": ["config"], "uptodate": [False]}


def task_tests():
    """Run project tests without requiring licensed data."""
    return {"actions": [[sys.executable, "-m", "pytest", "-q"]], "uptodate": [False]}


def task_check():
    """Credential-free code checks; suitable for a new clone or CI."""
    return {"actions": None, "task_dep": ["tests"]}


def task_data_status():
    """Refresh the local completed-data inventory."""
    return {"actions": [python_action("src/data_status.py")],
            "task_dep": ["config"], "uptodate": [False],
            "targets": ["_output/data_acquisition_status.md"]}


def task_research():
    """Default: validate inputs and build all currently implemented research outputs."""
    return {"actions": None,
            "task_dep": ["preflight", "tests", "13d_validation", "13d_extraction_eval",
                         "bfkr_preview", "data_status", "build_summary"]}


def task_fetch_public():
    """Explicit network task: download public archives and BFKR CSV (about 1.5 GB)."""
    return {"actions": [python_action("src/download_public_data.py")],
            "file_dep": ["src/download_public_data.py"], "task_dep": ["config"],
            # No producer targets: research builds must never pull this network
            # task implicitly through a raw-data file dependency.
            "uptodate": [False]}


def task_prepare_public():
    """Prepare local public archives; fetch_public must be requested separately."""
    from download_public_data import SOURCES

    optional_zip = Path("Replication Code-20220087.zip")
    return {"actions": [python_action("src/prepare_public_data.py", "--force")],
            "task_dep": ["config"],
            "file_dep": ["src/prepare_public_data.py",
                         *[Path("_data/public") / name for name in SOURCES if name.endswith(".zip")],
                         *([optional_zip] if optional_zip.exists() else [])],
            # Explicit preparation only; a data-only handoff need not include
            # the original multi-GB archives to rebuild research outputs.
            "uptodate": [False]}


def task_collect_wrds():
    """Explicit network task: resume licensed WRDS collection with your own access."""
    return {"actions": [python_action("src/collect_wrds.py", "core", "indicators", "lending", "links",
                                      "--start-year", "2004", "--end-year", "2019"),
                        python_action("src/collect_wrds.py", "sec", "--start-year", "2005", "--end-year", "2019"),
                        python_action("src/build_checks.py", "--component", "wrds")],
            "task_dep": ["config"], "uptodate": [False]}


def task_build_summary():
    """Write a summary of built outputs and unimplemented screenshot targets."""
    return {"actions": [python_action("src/build_summary.py")],
            "task_dep": ["13d_validation", "13d_extraction_eval", "bfkr_preview", "data_status"],
            "file_dep": ["src/build_summary.py", "_output/13d_label_validation.md",
                         "_output/13d_extraction_eval_audit.md", "_output/13d_extraction_eval_holdout.md",
                         "_output/figure_04c_preview.json", "_output/data_acquisition_status.md"],
            "targets": ["_output/build_summary.md"]}


def task_13d_filings():
    """Parse header, cover-page CUSIP and Item 5 location for every original SC 13D."""
    return {
        "actions": [python_action('src/parse_13d_filings.py')],
        "file_dep": ["src/parse_13d_filings.py", "src/schema_13d.py", *SEC_13D_TEXT, *SETTINGS_DEPS],
        "task_dep": ["13d_inputs"],
        "targets": [THIRTEEN_D / "filings.parquet"],
    }


def task_13d_links():
    """Link filings to CRSP PERMNOs (CUSIP first, then CIK), with a name check."""
    return {
        "actions": [python_action('src/link_13d_crsp.py')],
        "file_dep": ["src/link_13d_crsp.py", THIRTEEN_D / "filings.parquet",
                     WRDS / "crsp_names.parquet", WRDS / "sec_cusip_links.parquet", *SETTINGS_DEPS],
        "task_dep": ["13d_inputs"],
        "targets": [THIRTEEN_D / "filing_links.parquet"],
    }


def task_13d_transactions():
    """Extract disclosed transactions from Item 5(c), schedules and exhibits."""
    return {
        "actions": [python_action('src/extract_13d_transactions.py')],
        "file_dep": ["src/extract_13d_transactions.py", "src/parse_13d_filings.py", "src/schema_13d.py",
                     *SEC_13D_TEXT, *SETTINGS_DEPS],
        "task_dep": ["13d_inputs"],
        "targets": [THIRTEEN_D / "transactions.parquet", THIRTEEN_D / "extraction_log.parquet"],
    }


def task_13d_extraction_eval():
    """Score the extractor on the hand-audited tuning and holdout samples."""
    return {
        "actions": [python_action('src/evaluate_13d_extraction.py'),
                    python_action('src/evaluate_13d_extraction.py', '--holdout')],
        "file_dep": ["src/evaluate_13d_extraction.py", "src/extract_13d_transactions.py",
                     "data_manual/13d_audit/audit_transactions.csv",
                     "data_manual/13d_audit/holdout_transactions.csv",
                     "data_manual/13d_audit/audit_filings.csv", "data_manual/13d_audit/holdout_filings.csv",
                     "src/parse_13d_filings.py", "src/schema_13d.py", *SEC_13D_TEXT, *SETTINGS_DEPS],
        "task_dep": ["13d_inputs"],
        "targets": [Path("_output/13d_extraction_eval_audit.md"),
                    Path("_output/13d_extraction_eval_holdout.md"),
                    Path("_output/13d_extraction_eval_audit_by_filing.csv"),
                    Path("_output/13d_extraction_eval_holdout_by_filing.csv")],
    }


def task_13d_authors_windows():
    """Recover the authors' 13D training windows from blanks in the posted ITI file."""
    return {
        "actions": [python_action('src/authors_13d_windows.py')],
        "file_dep": ["src/authors_13d_windows.py",
                     ITI / "manifest.json", *ITI_PARTS, *SETTINGS_DEPS],
        "task_dep": ["13d_inputs"],
        "targets": [THIRTEEN_D / "authors_windows.parquet"],
    }


def task_13d_labels():
    """Apply event screens and build daily trade-day labels (authors' layout)."""
    return {
        "actions": [python_action('src/build_13d_labels.py')],
        "file_dep": ["src/build_13d_labels.py", "src/screen_13d.py", "src/schema_13d.py",
                     THIRTEEN_D / "filings.parquet", THIRTEEN_D / "filing_links.parquet",
                     THIRTEEN_D / "transactions.parquet", THIRTEEN_D / "authors_windows.parquet",
                     *CRSP_DAILY, "src/link_13d_crsp.py", WRDS / "crsp_names.parquet", *SETTINGS_DEPS],
        "task_dep": ["13d_inputs"],
        "targets": [THIRTEEN_D / "events.parquet", THIRTEEN_D / "labels_daily.parquet"],
    }


def task_13d_validation():
    """Compare rebuilt labels with the paper's published statistics."""
    return {
        "actions": [python_action('src/validate_13d_labels.py')],
        "file_dep": ["src/validate_13d_labels.py", THIRTEEN_D / "events.parquet",
                     THIRTEEN_D / "labels_daily.parquet", THIRTEEN_D / "authors_windows.parquet",
                     "src/screen_13d.py", WRDS / "crsp_market.parquet", *CRSP_DAILY,
                     ITI / "manifest.json", *ITI_PARTS, *SETTINGS_DEPS],
        "task_dep": ["13d_inputs"],
        "targets": [Path("_output/13d_label_validation.md"), Path("_output/13d_filing_car.png")],
    }


def task_bfkr_news():
    """Link the public BFKR news CSV and prepare raw-date earnings diagnostics."""
    return {
        "actions": [python_action('src/prepare_bfkr_news.py')],
        "file_dep": ["src/prepare_bfkr_news.py",
                     "_data/public/InformationTradingVolatility_DataFile.csv",
                     WRDS / "crsp_names.parquet", WRDS / "compustat_earnings.parquet",
                     WRDS / "crsp_compustat_links.parquet"],
        "task_dep": ["bfkr_inputs"],
        "targets": ["_data/derived/bfkr/news_daily.parquet",
                    "_data/derived/bfkr/news_link_audit.parquet",
                    "_data/derived/bfkr/earnings_unadjusted.parquet",
                    "_data/derived/bfkr/manifest.json", "_output/bfkr_preparation.md"],
    }


def task_bfkr_preview():
    """Preliminary Figure 4(c), with raw earnings dates and incomplete sample screens."""
    return {
        "actions": [python_action('src/analyze_bfkr_news.py', '--preview')],
        "file_dep": ["src/analyze_bfkr_news.py", "_data/derived/bfkr/news_daily.parquet",
                     "_data/derived/bfkr/earnings_unadjusted.parquet", WRDS / "crsp_market.parquet",
                     ITI / "manifest.json", *ITI_PARTS],
        "task_dep": ["bfkr_inputs"],
        "targets": ["_output/figure_04c_preview.png", "_output/figure_04c_preview.csv",
                    "_output/figure_04c_preview.md", "_output/figure_04c_preview.json",
                    "_data/derived/bfkr/figure_04c_preview_sample.parquet"],
    }


## Replication exhibits from the posted ITI file. Not default tasks (need local WRDS data).
PANEL = Path("_data/derived/panel")
REPLICATION = Path("_output/replication")


def task_panel():
    """Build the daily and weekly stock panels (CRSP, TAQ indicators, posted ITI)."""
    return {
        "actions": [python_action("src/build_panel.py")],
        "file_dep": ["src/build_panel.py", "src/paper_values.py", *CRSP_DAILY],
        "targets": [PANEL / "daily.parquet", PANEL / "weekly.parquet"],
    }


def task_replication():
    """Replicate Tables 5, 10, 11 and Figures 4(a)-(b), IA.5."""
    return {
        "actions": [python_action("src/replicate_exhibits.py")],
        "file_dep": ["src/replicate_exhibits.py", "src/regress.py", "src/paper_values.py",
                     PANEL / "daily.parquet", PANEL / "weekly.parquet"],
        "targets": [REPLICATION / f for f in ["table10.csv", "table11.csv", "table5.csv",
                                              "figure4a.csv", "figure4b.csv", "figureIA5.csv"]],
    }


def task_replication_notebook():
    """Execute the replication notebook and export it to HTML in _output/."""
    py = Path("src/01_iti_replication.ipynb.py")
    nb = py.with_suffix("")
    return {
        "actions": [
            f"jupytext --to notebook --output {nb} {py}",
            f"jupyter nbconvert --execute --to notebook --ClearMetadataPreprocessor.enabled=True --inplace {nb}",
            f"jupyter nbconvert --to html --output-dir=_output {nb}",
            f"mv {nb} _output/",
        ],
        "file_dep": [py, *[REPLICATION / f for f in ["table10.csv", "table11.csv", "table5.csv"]],
                     THIRTEEN_D / "labels_daily.parquet"],
        "targets": [Path("_output/01_iti_replication.html")],
        "clean": True,
    }


def task_report():
    """Compile the project report (requires latexmk and a LaTeX distribution)."""
    return {
        "actions": ["latexmk -pdf -halt-on-error -cd reports/report.tex"],
        "file_dep": ["reports/report.tex", "reports/bibliography.bib", ".latexmkrc",
                     *sorted(Path("reports").rglob("*.tex"))],
        "targets": ["reports/report.pdf"],
        "clean": True,
    }


def task_build_chartbook_site():
    """Build the project site from its metadata and documentation."""
    return {
        "actions": ["chartbook docs build -f"],
        "file_dep": [
            "README.md",
            "chartbook.toml",
            "_output/build_summary.md",
            THIRTEEN_D / "labels_daily.parquet",
            *sorted(Path("docs_src").rglob("*.md")),
        ],
        "targets": ["docs/index.html"],
        "task_dep": ["build_summary"],
        "clean": True,
    }
