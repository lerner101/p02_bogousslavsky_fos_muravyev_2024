"""Transaction extraction on synthetic filings, plus an audit check when data exist."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from extract_13d_transactions import extract_filing, finalize  # noqa: E402

FILED = pd.Timestamp("2010-01-04")


def filing(item5c, exhibits=()):
    docs = [f"<DOCUMENT>\n<TYPE>SC 13D\n<TEXT>\nSCHEDULE 13D\n"
            f"Item\n5.\nInterest in Securities of the Issuer\n(a) 1,000,000 Shares.\n"
            f"{item5c}\n(d) Not applicable.\nItem 6. Contracts\n</TEXT>\n</DOCUMENT>"]
    for typ, body in exhibits:
        docs.append(f"<DOCUMENT>\n<TYPE>{typ}\n<TEXT>\n{body}\n</TEXT>\n</DOCUMENT>")
    return "\n".join(docs)


def rows(text, filed=FILED):
    r, log = extract_filing("acc", filed, text)
    return finalize(r), log


def triples(df):
    return [(str(d.date()), s, int(q), p) for d, s, q, p in
            zip(df.trade_date, df.side, df.shares, df.price)]


def test_one_cell_per_line_schedule_with_sales_in_parentheses():
    text = filing("(c) Schedule\nB annexed hereto lists all transactions.\n"
                  "SCHEDULE\nB\nTransactions in the Securities of the Issuer During the Past 60 Days\n"
                  "Class\nof\nSecurity\nSecurities\nPurchased / (Sold)\nPrice\nPer\nShare ($)\nDate\n"
                  "FUND ONE, L.P.\nCommon\nStock\n(153,877)\n2.2916\n11/16/2009\n"
                  "Common\nStock\n19,942\n2.0000\n11/17/2009\n"
                  "FUND TWO, LLC\nCommon\nStock\n828\n2.2500\n12/16/2009\n")
    df, _ = rows(text)
    assert triples(df) == [("2009-11-16", "sell", 153877, 2.2916),
                           ("2009-11-17", "buy", 19942, 2.0),
                           ("2009-12-16", "buy", 828, 2.25)]
    assert list(df.reporting_person) == ["FUND ONE, L.P.", "FUND ONE, L.P.", "FUND TWO, LLC"]


def test_row_per_line_date_first_and_repeated_identical_rows_kept():
    text = filing("(c) Schedule A sets forth purchases during the past 60 days.\n"
                  "Schedule A\nDate Quantity Price Per Share ($)\n"
                  "11/19/2009 600 12.290\n11/19/2009 300 12.325\n11/19/2009 300 12.325\n")
    df, _ = rows(text)
    assert [t[2] for t in triples(df)] == [600, 300, 300]
    assert set(df.side) == {"buy"}


def test_trailing_minus_and_side_word_before_date():
    text = filing("(c) Transactions:\n11/06/09 7,000- 21.6150\n11/12/09 4,000 23.1950\n"
                  "Sale 12/17/09 380 $16.61\nPurchase 12/18/09 2,000 $16.70\n")
    df, _ = rows(text, filed=pd.Timestamp("2009-12-31"))
    sides = dict(zip(df.shares.astype(int), df.side))
    assert sides[7000] == "sell" and sides[4000] == "buy"
    assert sides[380] == "sell" and sides[2000] == "buy"


def test_purchased_and_sold_columns_with_placeholder():
    text = filing("(c) Schedule II lists the transactions.\nSchedule II\n"
                  "Transaction Date Reporting Person Number of Shares Purchased Number of Shares Sold Price Per Share\n"
                  "12/01/2009 DSTR Common Stock 5,703 -- $6.05\n"
                  "12/02/2009 DSTR Common Stock -- 1,000 $6.10\n")
    df, _ = rows(text)
    assert dict(zip(df.shares.astype(int), df.side)) == {5703: "buy", 1000: "sell"}


def test_section_intro_sets_side_and_footnote_marker_ignored():
    text = filing("(c) During the sixty days preceding this report, the Reporting Persons sold the "
                  "following shares in the open market:\nReporting Person Trade Date Shares Price/Share\n"
                  "Fund 12/24/2009 43,012 $21.56(1)\n12/28/2009 85,682 $21.74\n")
    df, _ = rows(text)
    assert triples(df) == [("2009-12-24", "sell", 43012, 21.56), ("2009-12-28", "sell", 85682, 21.74)]


def test_prose_transactions():
    text = filing("(c) On December 3, 2009, the Fund purchased 1,000 shares of Common Stock in the "
                  "open market at a price of $12.50 per share.")
    df, _ = rows(text)
    assert triples(df) == [("2009-12-03", "buy", 1000, 12.5)]
    assert df.parse_method.iloc[0] == "sentence"


def test_window_filter_no_transactions_and_prose_not_a_row():
    text = filing("(c) The Reporting Persons have not effected any transactions in the Common Stock "
                  "during the past 60 days. As of December 20, 2009 there were 29,596,383 shares "
                  "outstanding, with 5.5 percent held.\nOld trade 01/05/2009 1,000 $3.00\n")
    df, log = rows(text)
    assert df.empty
    assert log["no_txn_statement"]


def test_referenced_exhibit_document_is_scanned():
    text = filing("(c) Set forth on Exhibit 2 are all transactions effected during the past sixty days.",
                  exhibits=[("EX-99.1", "Joint Filing Agreement dated 12/30/2009. EX-99.1 2 copies"),
                            ("EX-99.2", "Trade Date Shares Purchased Price\n12/01/2009 8,001 $8.03\n")])
    df, log = rows(text)
    assert triples(df) == [("2009-12-01", "buy", 8001, 8.03)]
    assert "exhibit:EX-99.2:1" in log["regions"]


AUDIT = ROOT / "data_manual" / "13d_audit" / "audit_transactions.csv"
WRDS = ROOT / "_data" / "wrds" / "sec_13d_filings"


@pytest.mark.skipif(not (AUDIT.exists() and WRDS.exists()), reason="needs local WRDS 13D text")
def test_extractor_on_audit_sample():
    from collections import Counter

    from evaluate_13d_extraction import keys
    from extract_13d_transactions import run

    truth = pd.read_csv(AUDIT, dtype=str)
    truth = truth[pd.to_datetime(truth.trade_date, errors="coerce").notna()]
    pred, _ = run(set(truth.accession))
    t, p = Counter(keys(truth)), Counter(keys(pred))
    hit = sum((t & p).values())
    assert hit / sum(p.values()) >= 0.98  # extracted rows are real
    om = truth[truth.transaction_type == "open_market"]
    tom = Counter(keys(om))
    assert sum((tom & p).values()) / sum(tom.values()) >= 0.90  # open-market rows are found
