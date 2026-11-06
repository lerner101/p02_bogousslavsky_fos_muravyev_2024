"""Build the ITI project directories, report, and ChartBook site.

Research tasks will be added as the replication is implemented.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from settings import config

DOIT_CONFIG = {
    "backend": "sqlite3",
    "dep_file": ".doit-db.sqlite",
    "default_tasks": ["config"],
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


## Schedule 13D labels. Not default tasks: they need local WRDS extracts
## (_data/wrds), which CI does not have. Run with `doit 13d_validation`.
THIRTEEN_D = config("THIRTEEN_D_DIR")
WRDS = Path("_data/wrds")
SEC_13D_TEXT = sorted(str(p) for p in (WRDS / "sec_13d_filings").glob("*.parquet"))
CRSP_DAILY = sorted(str(p) for p in (WRDS / "crsp_daily").glob("*.parquet"))


def task_13d_filings():
    """Parse header, cover-page CUSIP and Item 5 location for every original SC 13D."""
    return {
        "actions": ["python src/parse_13d_filings.py"],
        "file_dep": ["src/parse_13d_filings.py", "src/schema_13d.py", *SEC_13D_TEXT],
        "targets": [THIRTEEN_D / "filings.parquet"],
    }


def task_13d_links():
    """Link filings to CRSP PERMNOs (CUSIP first, then CIK), with a name check."""
    return {
        "actions": ["python src/link_13d_crsp.py"],
        "file_dep": ["src/link_13d_crsp.py", THIRTEEN_D / "filings.parquet",
                     WRDS / "crsp_names.parquet", WRDS / "sec_cusip_links.parquet"],
        "targets": [THIRTEEN_D / "filing_links.parquet"],
    }


def task_13d_transactions():
    """Extract disclosed transactions from Item 5(c), schedules and exhibits."""
    return {
        "actions": ["python src/extract_13d_transactions.py"],
        "file_dep": ["src/extract_13d_transactions.py", "src/parse_13d_filings.py", *SEC_13D_TEXT],
        "targets": [THIRTEEN_D / "transactions.parquet", THIRTEEN_D / "extraction_log.parquet"],
    }


def task_13d_extraction_eval():
    """Score the extractor on the hand-audited tuning and holdout samples."""
    return {
        "actions": ["python src/evaluate_13d_extraction.py",
                    "python src/evaluate_13d_extraction.py --holdout"],
        "file_dep": ["src/evaluate_13d_extraction.py", "src/extract_13d_transactions.py",
                     "data_manual/13d_audit/audit_transactions.csv",
                     "data_manual/13d_audit/holdout_transactions.csv"],
        "targets": [Path("_output/13d_extraction_eval_audit.md"),
                    Path("_output/13d_extraction_eval_holdout.md")],
    }


def task_13d_authors_windows():
    """Recover the authors' 13D training windows from blanks in the posted ITI file."""
    return {
        "actions": ["python src/authors_13d_windows.py"],
        "file_dep": ["src/authors_13d_windows.py",
                     *sorted(str(p) for p in Path("_data/public/iti_original_through_2019").glob("year=*/*.parquet"))],
        "targets": [THIRTEEN_D / "authors_windows.parquet"],
    }


def task_13d_labels():
    """Apply event screens and build daily trade-day labels (authors' layout)."""
    return {
        "actions": ["python src/build_13d_labels.py"],
        "file_dep": ["src/build_13d_labels.py", "src/screen_13d.py", "src/schema_13d.py",
                     THIRTEEN_D / "filings.parquet", THIRTEEN_D / "filing_links.parquet",
                     THIRTEEN_D / "transactions.parquet", THIRTEEN_D / "authors_windows.parquet",
                     *CRSP_DAILY],
        "targets": [THIRTEEN_D / "events.parquet", THIRTEEN_D / "labels_daily.parquet"],
    }


def task_13d_validation():
    """Compare rebuilt labels with the paper's published statistics."""
    return {
        "actions": ["python src/validate_13d_labels.py"],
        "file_dep": ["src/validate_13d_labels.py", THIRTEEN_D / "events.parquet",
                     THIRTEEN_D / "labels_daily.parquet"],
        "targets": [Path("_output/13d_label_validation.md"), Path("_output/13d_filing_car.png")],
    }


def task_report():
    """Compile the project report (requires latexmk and a LaTeX distribution)."""
    return {
        "actions": ["latexmk -pdf -halt-on-error -cd reports/report.tex"],
        "file_dep": ["reports/report.tex", "reports/bibliography.bib", ".latexmkrc"],
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
            *sorted(Path("docs_src").rglob("*.md")),
        ],
        "targets": ["docs/index.html"],
        "task_dep": ["config"],
        "clean": True,
    }
