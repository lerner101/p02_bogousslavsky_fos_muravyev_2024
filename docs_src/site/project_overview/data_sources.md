# Data Sources

The working collection covers 2005–2019 with 2004 warm-up history. The extension
is undecided. The [acquisition inventory](data_acquisition.md) documents
sources, local paths, commands, and outstanding gaps.

Source extracts come from WRDS (CRSP, Compustat, TAQ daily indicators, insider
transactions, Markit securities lending, SDC M&A and SEC filings), the authors'
public ITI download, Edwin Hu's legacy PIN-family data, and Kenneth French's
factor library. Actual completion is recorded by each extract's JSON sidecar in
`_data/`; `.part` files are incomplete.

Research data and credentials stay outside Git. Downloaded source extracts are
not yet linked, screened, or transformed into a validated replication panel.
The cleaned 13D labels, exact news sample, BCL comparison measures and some
intraday inputs remain outstanding; see the inventory for details.

Downloads in the original checkout were stopped on November 4, 2026. GitHub
contains scripts and instructions, not the local data. See the inventory for
the paused coverage snapshot, teammate setup, and commands to resume collection.
