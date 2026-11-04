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
