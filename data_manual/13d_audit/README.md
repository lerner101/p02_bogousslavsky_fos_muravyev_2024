# Schedule 13D hand-audit samples

Ground truth used to score `src/extract_13d_transactions.py`. Schedule 13D filings
are public SEC documents, so these transcriptions may be committed.

## Samples

| Files | Sample | Use |
|---|---|---|
| `audit_filings.csv`, `audit_transactions.csv` | 30 filings, 2 per filing year 2005–2019 | **Tuning**: the extractor was developed against these, so their scores are in-sample |
| `holdout_filings.csv`, `holdout_transactions.csv` | 15 filings, 1 per year, different seed, excluding the tuning sample | **Holdout**: scored once with the frozen extractor before any further change |

Both are drawn by `src/make_13d_audit_packets.py` (seed 32800 and 32801) from filings
that link to CRSP common stock and pass the price ≥ $5 and market cap ≥ $100M screens.
Within a year, distinct filing agents (accession prefixes) are preferred because
layouts cluster by agent. The script writes one reading packet per filing to
`_output/13d_audit_packets/` or `_output/13d_holdout_packets/`. Tuning packets start
at Item 5; holdout packets start at Item 3, because some filings disclose trades
there by reference.

## Who audited

Transcriptions were made by Claude agents that read the packet text without running
parsing code and without seeing the extractor. **They have not been verified by a
person.** Fill in `verified_by` after checking a filing against its packet or EDGAR.
Priority: the filings whose `notes` describe a judgment call.

## Columns

`*_transactions.csv`: one row per disclosed transaction, as the filing lists it.
- `trade_date` (YYYY-MM-DD, blank if the filing gives none), `side` (buy/sell),
  `shares` (positive), `price` (USD per share, blank if not stated)
- `transaction_type`: `open_market`, `private`, `other` (IPO allocation, conversion,
  grant, exercise, merger consideration, spin-off), `unknown`
- `is_derivative`, `is_group_member` (false only if the filing says the entity is not
  a reporting person or group member), `document_no`, `quote` (source text)

Rows older than 60 days before filing are kept if the filing lists them. The
evaluation reports a separate "inside window" score because labels use only the
window.

`*_filings.csv`: per filing, `has_open_market_trades`, `has_derivatives`,
`n_transactions`, `packet_truncated_trades_possible`, `notes`.

## Known judgment calls

- Swap-linked rows (Kindred 2017) and option exercises (Steve Madden 2005) are marked
  derivative.
- Rows that only appear in Items 3/4 were not recorded for the tuning sample when
  those items were outside the packet (`packet_truncated_trades_possible = yes`).
- Edenbrook (holdout 2017): the stripped text loses the Purchased/Sold column. The
  auditor checked the original EDGAR HTML: both rows are purchases.
- Lapetus (holdout 2018): footnote numbers are glued to prices in the text
  ("7.09781" is $7.0978 plus footnote 1). The audit records the corrected price.
