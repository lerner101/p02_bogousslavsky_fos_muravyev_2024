"""Column names, types and units for the Schedule 13D label pipeline.

The daily label file keeps the column names of the authors' `sc13_1994_2018.dta`
as documented in `build/get_13D.py` of the replication package, so model code
written against their layout can use ours unchanged:

- ``permno``, ``date``: one row per stock and trading day in a filing window.
- ``filing_date``: a filing is identified by (``permno``, ``filing_date``).
- ``itrade``: 1 if the filer bought *or* sold that day (about 6% of the authors'
  trades are sales, per ``ITI_main.py``).
- ``ivol``: signed dollar amount traded, sales negative. ``ITI_main.py``
  computes filer turnover as ``|ivol| / (prc * shrout * 1000)``, which only
  yields a turnover if ``ivol`` is in dollars, despite the docstring's
  "number of shares bought".
- ``days_to_filing``: ``filing_date - date`` in calendar days.

Stages and their outputs (all under ``THIRTEEN_D_DIR``):

1. ``filings.parquet``      one row per original SC 13D submission
2. ``transactions.parquet`` one row per disclosed transaction
3. ``events.parquet``       one row per filing, with screens and exclusion reason
4. ``labels_daily.parquet`` one row per filing and trading day
"""

FILINGS = {
    "accession": "string",
    "filing_date": "datetime64[ns]",
    "subject_cik": "string",
    "subject_name": "string",
    "filer_cik": "string",
    "filer_name": "string",
    "issuer_name": "string",  # cover-page "(Name of Issuer)"; EDGAR headers are sometimes wrong
    "cusip_cover": "string",  # as printed on the cover page, cleaned to 9 chars or fewer
    "cusip8": "string",  # first 8 characters, CRSP ncusip format
    "cusip_candidates": "string",  # ";"-joined 8-char candidates in linking priority order
    "event_date": "datetime64[ns]",  # "Date of Event Which Requires Filing"
    "n_documents": "Int64",
    "item5_found": "boolean",
    "schedule_ref": "string",  # e.g. "Schedule A", "Exhibit 99.1", or <NA>
    "is_amendment": "boolean",  # cover page says "Amendment No. N" with N >= 1
}

TRANSACTIONS = {
    "accession": "string",
    "reporting_person": "string",  # section heading the row appeared under, if any
    "trade_date": "datetime64[ns]",
    "side": "string",  # "buy" or "sell"
    "shares": "float64",  # always positive; direction is in `side`
    "price": "float64",  # per-share price as disclosed, USD
    "security_class": "string",
    "is_derivative": "boolean",
    "is_group_member": "boolean",  # False when the text says the entity is not in the group
    "source_document": "Int64",  # 1-based <DOCUMENT> index within the submission
    "char_offset": "Int64",  # offset of the row within that document's text
    "parse_method": "string",  # "table" or "sentence"
}

EVENTS = {
    "accession": "string",
    "filing": "Int64",  # integer event id, like the authors' `filing`
    "permno": "Int64",
    "filing_date": "datetime64[ns]",
    "window_start": "datetime64[ns]",
    "link_method": "string",  # "cusip" or "cik"
    "in_paper_period": "boolean",  # filing year <= PAPER_13D_LAST_YEAR
    # Window matches one recovered from the posted ITI file (authors_13d_windows.py):
    # same PERMNO, filing date 3 days before to 7 days after the window's last day.
    "in_authors_sample": "boolean",
    "pass_original": "boolean",  # not an amendment filed under form type SC 13D
    "pass_linked": "boolean",
    "pass_common_stock": "boolean",
    "pass_price": "boolean",
    "pass_mcap": "boolean",
    "pass_has_trades": "boolean",
    "pass_no_derivatives": "boolean",
    "included": "boolean",
    "exclusion_reason": "string",  # first failed screen, <NA> if included
    "n_transactions": "Int64",
}

LABELS_DAILY = {
    # authors' columns
    "permno": "Int64",
    "date": "datetime64[ns]",
    "filing_date": "datetime64[ns]",
    "itrade": "int8",
    "ivol": "float64",  # signed USD
    "days_to_filing": "Int64",
    "filing": "Int64",
    # additions
    "accession": "string",
    "shares_bought": "float64",
    "shares_sold": "float64",
    "n_trades": "Int64",
    "patient": "boolean",  # days_to_filing > IMPATIENT_CALENDAR_DAYS
    "prc": "float64",  # |CRSP price|
    "shrout": "float64",  # CRSP shares outstanding, thousands
    "vol": "float64",  # CRSP share volume
    "turn": "float64",  # vol / (shrout * 1000)
    "gross_dollars": "float64",  # sum of |shares * price| that day, USD
    "13Dturn": "float64",  # gross_dollars / (prc * shrout * 1000)
    "13Dvol/vol": "float64",  # 13Dturn / turn, capped at 1 (authors' rule)
    "in_paper_period": "boolean",
    "in_authors_sample": "boolean",
}
