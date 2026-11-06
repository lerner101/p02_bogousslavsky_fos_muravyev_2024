"""Filing metadata and CRSP-link helpers, on synthetic text (no WRDS needed)."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from link_13d_crsp import name_score  # noqa: E402
from parse_13d_filings import (  # noqa: E402
    cusip_candidates,
    cusip_check_digit,
    normalize_cusip,
    order_cusips,
    parse_event_date,
    parse_filing,
    parse_header,
    parse_issuer_name,
)

HEADER = """<SEC-HEADER>0000000000-10-000001.hdr.sgml
SUBJECT COMPANY:

\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\tACME WIDGETS INC
\t\tCENTRAL INDEX KEY:\t\t\t0000855906

FILED BY:

\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\tACTIVIST FUND LP
\t\tCENTRAL INDEX KEY:\t\t\t1345523
</SEC-HEADER>"""

COVER = """SCHEDULE 13D
(Amendment No. )*

Acme Widgets,
Inc.

(Name
of
Issuer)

Common Stock, par value $0.01

(Title of Class of Securities)

827057 10 0

(CUSIP
Number)

John Doe, Esq.

(Name, Address and Telephone Number of Person Authorized to Receive Notices and Communications)

November
13, 2009

(Date of Event Which Requires Filing of this Statement)
"""


def test_header_subject_and_filer():
    h = parse_header(HEADER)
    assert h["subject_name"] == "ACME WIDGETS INC"
    assert h["subject_cik"] == "0000855906"
    assert h["filer_cik"] == "0001345523"  # zero-padded to 10 digits


def test_cusip_check_digit_and_normalization():
    assert cusip_check_digit("82705710") == "0"
    assert cusip_check_digit("037833100"[:8]) == "0"  # Apple
    assert normalize_cusip("827057 10 0") == "827057100"
    assert normalize_cusip("827057-10-0") == "827057100"
    assert normalize_cusip("N/A") is None


def test_cover_cusip_beats_copied_page_header():
    # Cover CUSIP is 8 characters; a later "CUSIP No." is a valid CUSIP copied from
    # another filing. The cover must stay first.
    assert order_cusips(["21886810", "90342V109"])[0] == "21886810"
    # A 9-character cover CUSIP with a bad check digit yields to a valid page CUSIP.
    assert order_cusips(["827057109", "827057100"])[0] == "827057100"


def test_cover_fields():
    assert cusip_candidates(COVER)[0] == "827057100"
    assert parse_issuer_name(COVER) == "Acme Widgets, Inc."
    assert parse_event_date(COVER) == pd.Timestamp("2009-11-13")


def test_parse_filing_row():
    text = HEADER + "\n<DOCUMENT>\n<TYPE>SC 13D\n<TEXT>\n" + COVER + "\nItem 5. Interest in Securities of the Issuer\n(c) None.\n</DOCUMENT>"
    row = parse_filing("0000000000-10-000001", pd.Timestamp("2010-01-04"), text)
    assert row["cusip8"] == "82705710"
    assert row["item5_found"] and row["n_documents"] == 1


def test_name_score_handles_suffixes_and_word_order():
    assert name_score("Silicon Storage Technology, Inc.", "SILICON STORAGE TECHNOLOGY INC") == 1.0
    assert name_score("Thomas Nelson, Inc.", "NELSON THOMAS INC") >= 0.9
    assert name_score("Corinthian Colleges, Inc.", "U S BIOENERGY CORP") < 0.5
