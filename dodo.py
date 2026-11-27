"""Build implemented research outputs from local data; acquisition is explicit.

Plain doit runs preflight, tests, 13D validation, the BFKR preview and an output
summary. This is not yet an implementation of all thirteen screenshot targets.
"""

import sys
import tomllib
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


# Report exhibits read only committed _output/ files, so they rebuild from a
# clean clone without WRDS access.
REPORT_DIR = Path("_output/report")
REPLICATION_CSVS = [REPLICATION / f for f in [
    "table5.csv", "table10.csv", "table11.csv", "figure1.csv", "figure2.csv",
    "figure4a.csv", "figure4b.csv", "figureIA5.csv"]]
VALIDATION_INPUTS = [Path("_output/13d_label_validation.md"), *[Path("_output/ml_model") / f for f in [
    "pilot_volume_reconciliation.csv", "available_input_attrition.csv",
    "comparison_coverage.csv", "agreement_by_year.csv"]]]


REPORT_FIGURES = [Path("_output") / f for f in [
    "replication/figure1.png", "replication/figure2.png", "replication/figure3.png",
    "replication/figure4a.png", "replication/figure4b.png", "replication/figureIA5.png",
    "figure_04c_preview.png", "13d_filing_car.png"]]


def committed_outputs_unchanged(paths):
    """Rerun when committed outputs change, without making them file_dep.

    These files are targets of data-dependent tasks (replication, iti_figures,
    bfkr_preview, 13d_validation); listing them as file_dep would make doit try
    to rebuild them from WRDS data. The hash is computed when the task is
    checked, not when dodo.py loads, so a producer that rewrites a file earlier
    in the same run makes the consumer rerun.
    """
    import json
    from hashlib import md5

    def check(task, values):
        hashes = {str(p): md5(Path(p).read_bytes()).hexdigest() if Path(p).exists() else None
                  for p in paths}
        digest = md5(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        task.value_savers.append(lambda: {"outputs_digest": digest})
        return values.get("outputs_digest") == digest
    return check


def task_scorecard():
    """Score every replicated number against the paper with the fixed tolerance."""
    return {
        "actions": [python_action("src/replication_scorecard.py")],
        "file_dep": ["src/replication_scorecard.py", "src/paper_values.py"],
        "uptodate": [committed_outputs_unchanged([*REPLICATION_CSVS, "_output/figure_04c_preview.csv",
                                                  "_output/ml_model/model_performance.csv"])],
        "targets": [REPORT_DIR / f for f in ["scorecard.csv", "scorecard.tex", "scorecard.png", "scorecard.json"]],
    }


def task_validation_exhibits():
    """Data-validation table and coverage figure from committed validation outputs."""
    return {
        "actions": [python_action("src/validation_exhibits.py")],
        "file_dep": ["src/validation_exhibits.py"],
        "uptodate": [committed_outputs_unchanged(VALIDATION_INPUTS)],
        "targets": [REPORT_DIR / f for f in ["validation_table.tex", "validation_coverage.png",
                                             "validation_summary.json"]],
    }


def task_report_tables():
    """Ours-vs-paper LaTeX tables and the number macros quoted in the report."""
    return {
        "actions": [python_action("src/report_latex_tables.py")],
        "file_dep": ["src/report_latex_tables.py", "src/paper_values.py",
                     REPORT_DIR / "scorecard.json", REPORT_DIR / "validation_summary.json"],
        "uptodate": [committed_outputs_unchanged([*REPLICATION_CSVS, "_output/ml_model/model_performance.csv",
                                                  "_output/ml_model/agreement_overall.csv"])],
        "targets": [REPORT_DIR / f for f in ["table5.tex", "table10.tex", "table11.tex", "stats.tex"]],
    }


def task_report():
    """Compile the project report (requires latexmk and a LaTeX distribution)."""
    return {
        "actions": ["latexmk -pdf -halt-on-error -cd reports/report.tex"],
        "file_dep": ["reports/report.tex", "reports/bibliography.bib", ".latexmkrc",
                     REPORT_DIR / "scorecard.tex", REPORT_DIR / "scorecard.png",
                     REPORT_DIR / "validation_table.tex", REPORT_DIR / "validation_coverage.png",
                     REPORT_DIR / "table5.tex", REPORT_DIR / "table10.tex",
                     REPORT_DIR / "table11.tex", REPORT_DIR / "stats.tex"],
        # Figures included directly from _output/ (produced by data tasks).
        "uptodate": [committed_outputs_unchanged(REPORT_FIGURES)],
        "targets": ["reports/report.pdf"],
        "clean": True,
    }


def task_publish():
    """Clean-clone build: scorecard, validation exhibits, tests and report; no data needed."""
    return {"actions": None, "task_dep": ["report", "tests"]}


def task_build_chartbook_site():
    """Build the public project site into docs/ from committed outputs; no data needed."""
    def exhibits_unchanged(task, values):
        manifest = tomllib.loads(Path("chartbook.toml").read_text(encoding="utf-8"))
        exhibits = [
            Path(entry["path"])
            for section in ("charts", "dataframes", "notebooks")
            for entry in manifest[section].values()
        ]
        return committed_outputs_unchanged(exhibits)(task, values)

    return {
        "actions": ["chartbook docs build -f", python_action("src/style_chartbook.py")],
        "file_dep": [
            "README.md",
            "chartbook.toml",
            "src/style_chartbook.py",
            "docs_src/site/_static/iti.css",
            REPORT_DIR / "scorecard.png",
            REPORT_DIR / "validation_coverage.png",
            *sorted(Path("docs_src").rglob("*.md")),
        ],
        "uptodate": [exhibits_unchanged],
        "targets": ["docs/index.html", "docs/cb/charts.html", "docs/_static/iti.css"],
        "clean": True,
    }


# Explicit ML tasks: never added to default research or automatic downloads.
ML_DATA = Path("_data/derived/ml_model")
ML_OUT = Path("_output/ml_model")


def task_iti_taq_pilot():
    """Network: measure supplemental TAQ extraction on early/late pilot days."""
    return {"actions": [python_action("src/collect_iti_taq.py", "--pilot")], "uptodate": [False]}


def task_iti_collect():
    """Network: resume training-history and ten-stock scoring TAQ acquisition."""
    return {"actions": [python_action("src/collect_iti_taq.py")], "uptodate": [False]}


def task_iti_features():
    """Build all 41 features from existing supplemental aggregates; no download."""
    return {"actions": [python_action("src/build_iti_features.py")],
            "file_dep": ["src/build_iti_features.py", "src/iti_features.py"],
            "targets": [ML_DATA / "features.parquet", ML_DATA / "features_manifest.json"],
            "uptodate": [False]}


def task_iti_train():
    """Explicit nested XGBoost training; requires a complete feature build."""
    return {"actions": [python_action("src/train_iti.py")],
            "file_dep": ["src/train_iti.py", "src/iti_features.py", ML_DATA / "features.parquet",
                         ML_DATA / "features_manifest.json", THIRTEEN_D / "labels_daily.parquet"],
            "targets": [ML_DATA / "iti_13d.json", ML_DATA / "oof_predictions.parquet",
                        ML_DATA / "model_manifest.json"], "uptodate": [False]}


def task_iti_score():
    """Score eligible acquired stock-days using the fitted ITI(13D) model."""
    return {"actions": [python_action("src/score_iti.py")],
            "file_dep": ["src/score_iti.py", ML_DATA / "model_manifest.json", ML_DATA / "iti_13d.json",
                         ML_DATA / "features.parquet", THIRTEEN_D / "labels_daily.parquet"],
            "targets": [ML_DATA / "scores.parquet"]}


def task_iti_compare():
    """Compare new project scores with original author ITI and published metrics."""
    return {"actions": [python_action("src/compare_iti.py")],
            "file_dep": ["src/compare_iti.py", "src/replicate_exhibits.py", "src/regress.py",
                         ML_DATA / "scores.parquet", ML_DATA / "oof_predictions.parquet"],
            "targets": [ML_OUT / "comparison.md", ML_OUT / "score_agreement.png",
                        ML_OUT / "model_performance.png", ML_OUT / "annual_comparison.png"]}


def task_iti_figures():
    """Build Figures 1–3 from a completed ML run and local WRDS extracts."""
    return {
        "actions": [python_action("src/replicate_iti_figures.py")],
        "file_dep": ["src/replicate_iti_figures.py", "src/iti_features.py", "src/build_iti_features.py",
                     *[f"data_manual/iti_figure_benchmarks/figure{n}.csv" for n in (1, 2, 3)],
                     "data_manual/iti_figure_benchmarks/provenance.json"],
        # The script checks saved input paths. Listing the model artifacts as
        # file_dep would make doit invoke their producers and retrain XGBoost.
        "uptodate": [False],
        "targets": [*[REPLICATION / f"figure{number}.{extension}"
                      for number in (1, 2, 3) for extension in ("csv", "png")],
                    REPLICATION / "figure3.pdf", REPLICATION / "figures1_3_comparison.md",
                    REPLICATION / "figures1_3_manifest.json"],
    }


def task_tables():
    """Build Tables 1, 2 and 4 from the saved ML run, 13D labels and daily panel."""
    return {
        "actions": [python_action("src/replicate_tables.py", "table1", "table2", "table4")],
        "file_dep": ["src/replicate_tables.py", "src/regress.py", "src/paper_values.py",
                     "src/replicate_iti_figures.py"],
        # Like iti_figures: model artifacts are checked by the script, not listed
        # as file_dep, so doit never retrains XGBoost to rebuild a table.
        "uptodate": [False],
        "targets": [*[REPLICATION / f"table{n}.csv" for n in (1, 2, 4)],
                    REPLICATION / "table1_coverage.json", REPLICATION / "table2_turnover_diagnostics.csv",
                    REPLICATION / "table2_turnover_sensitivity.csv"],
    }


def task_iti_train_groups():
    """Explicit: train the four feature-group ITIs for Table 3 (four extra model fits)."""
    return {"actions": [python_action("src/train_iti_groups.py")],
            "file_dep": ["src/train_iti_groups.py", "src/train_iti.py", "src/iti_features.py"],
            "targets": [ML_DATA / "group_oof_predictions.parquet", ML_DATA / "group_models.json"],
            "uptodate": [False]}


def task_table3():
    """Build Table 3 from the saved group ITIs; run `doit iti_train_groups` first."""
    return {"actions": [python_action("src/replicate_tables.py", "table3")],
            "file_dep": ["src/replicate_tables.py", "src/regress.py"],
            "uptodate": [False],
            "targets": [REPLICATION / "table3.csv"]}


def task_tables_report():
    """Validate completed Tables 1–4 and summarize published comparisons."""
    return {"actions": [python_action("src/report_tables.py")],
            "file_dep": ["src/report_tables.py", "src/paper_values.py"],
            "uptodate": [False],
            "targets": [REPLICATION / "tables_comparison.md", REPLICATION / "tables_comparison.csv",
                        REPLICATION / "table1_comparison.csv", REPLICATION / "table3_model_performance.csv",
                        REPLICATION / "tables_manifest.json"]}
