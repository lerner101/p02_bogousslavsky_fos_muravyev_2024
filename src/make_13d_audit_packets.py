"""Draw the 13D hand-audit sample and write one review packet per filing.

Sample: filings that link to CRSP common stock (share code 10/11) passing the price and
market-cap screens at the window start, two per filing year, preferring distinct filing
agents (the accession prefix identifies the agent, and layouts cluster by agent).
The draw is deterministic (SEED) so teammates get the same sample.

Outputs:
    data_manual/13d_audit/audit_filings.csv   sample list (committed; columns for auditors)
    _output/13d_audit_packets/<accession>.txt Item 3 onward of the main document plus
                                              every exhibit, for reading (not committed).
                                              (The first tuning packets started at Item 5.)

A second, untouched "holdout" sample (one per year, a different seed, excluding the
tuning sample) gives an honest out-of-sample score once the extractor has been tuned:
    data_manual/13d_audit/holdout_filings.csv

Run after parse_13d_filings.py and link_13d_crsp.py:
    python src/make_13d_audit_packets.py              # tuning sample
    python src/make_13d_audit_packets.py --holdout    # holdout sample
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_13d_filings import split_documents  # noqa: E402
from screen_13d import window_start_screens  # noqa: E402
from settings import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEED = 32800
PER_YEAR = 2
MAIN_CAP = 80_000
EXHIBIT_CAP = 40_000


def draw_sample(screened, seed=SEED, per_year=PER_YEAR):
    screened = screened.assign(agent=screened.accession.str[:10], year=screened.filing_date.dt.year)
    picks = []
    for _, g in screened.sample(frac=1, random_state=seed).groupby("year"):
        chosen, agents = [], set()
        for _, row in g.iterrows():
            if row.agent not in agents:
                chosen.append(row)
                agents.add(row.agent)
            if len(chosen) == per_year:
                break
        picks += chosen
    return pd.DataFrame(picks).sort_values("filing_date")


def packet_text(text):
    docs = split_documents(str(text))
    parts = []
    for i, (typ, body) in enumerate(docs, start=1):
        if i == 1 or typ.upper().startswith("SC 13D"):
            item3 = [m.start() for m in re.finditer(r"Item\s*3\b", body, re.I)]
            start = item3[-1] if item3 else 0  # from Item 3, so "see Item 3/4" references are visible
            chunk = body[max(start, 0):][:MAIN_CAP]
            cap = MAIN_CAP
        else:
            chunk, cap = body[:EXHIBIT_CAP], EXHIBIT_CAP
        trunc = len(body) > cap
        parts.append(f"\n\n===== DOCUMENT {i} | TYPE {typ} | "
                     f"{'TRUNCATED at ' + str(cap) + ' chars' if trunc else 'complete'} =====\n\n{chunk}")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    holdout = ap.parse_args().holdout
    out_dir = config("THIRTEEN_D_DIR")
    filings = pd.read_parquet(out_dir / "filings.parquet")
    links = pd.read_parquet(out_dir / "filing_links.parquet")
    ev = links[links.name_ok].merge(filings[["accession", "filing_date", "issuer_name", "filer_name"]],
                                    on="accession")
    ev = window_start_screens(ev)
    screened = ev[ev.pass_common_stock & ev.pass_price & ev.pass_mcap]
    if holdout:
        tuning = pd.read_csv(ROOT / "data_manual" / "13d_audit" / "audit_filings.csv").accession
        sample = draw_sample(screened[~screened.accession.isin(tuning)], seed=SEED + 1, per_year=1)
    else:
        sample = draw_sample(screened)

    packets = config("OUTPUT_DIR") / ("13d_holdout_packets" if holdout else "13d_audit_packets")
    packets.mkdir(parents=True, exist_ok=True)
    for year, accs in sample.groupby(sample.filing_date.dt.year).accession:
        src = pd.read_parquet(ROOT / "_data" / "wrds" / "sec_13d_filings" / f"{year}.parquet",
                              columns=["accession", "filing"]).set_index("accession")
        for acc in accs:
            (packets / f"{acc}.txt").write_text(packet_text(src.loc[acc, "filing"]), encoding="utf-8")

    audit = sample[["accession", "filing_date", "permno", "issuer_name", "filer_name"]].copy()
    audit["filing_date"] = audit.filing_date.dt.date
    for col in ["auditor", "verified_by", "has_open_market_trades", "has_derivatives",
                "packet_truncated_trades_possible", "notes"]:
        audit[col] = ""
    target = ROOT / "data_manual" / "13d_audit" / ("holdout_filings.csv" if holdout else "audit_filings.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print("Kept existing", target, "(delete it to redraw)")
    else:
        audit.to_csv(target, index=False)
        print("Wrote", target)
    print(f"Wrote {len(sample)} packets to {packets}")


if __name__ == "__main__":
    main()
