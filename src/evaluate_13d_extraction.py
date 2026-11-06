"""Score the 13D transaction extractor against the hand-audited sample.

Ground truth: data_manual/13d_audit/audit_transactions.csv (+ audit_filings.csv).
Rows match on (accession, trade_date, side, shares rounded to whole shares), as multisets,
so duplicated rows must be extracted as many times as they appear. Prices are compared
on matched rows only.

Levels reported:
  rows      recall / precision over transactions (all, and open-market non-derivative)
  days      recall / precision over (accession, trade_date) with any trade -> drives itrade
  filings   agreement on "has at least one trade"
  shares    absolute error in total traded shares per filing

Output: _output/13d_extraction_eval_<audit|holdout>.md and ..._by_filing.csv

Run: python src/evaluate_13d_extraction.py            # tuning sample
     python src/evaluate_13d_extraction.py --holdout  # untouched holdout sample
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_13d_transactions import WINDOW_SLACK_DAYS, run  # noqa: E402
from settings import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data_manual" / "13d_audit"


def keys(df):
    d = pd.to_datetime(df.trade_date, errors="coerce").dt.date
    return list(zip(df.accession, d, df.side.str.lower(), pd.to_numeric(df.shares).round()))


def prf(true, pred):
    t, p = Counter(true), Counter(pred)
    hit = sum((t & p).values())
    rec = hit / sum(t.values()) if t else float("nan")
    prec = hit / sum(p.values()) if p else float("nan")
    return hit, sum(t.values()), sum(p.values()), rec, prec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    holdout = ap.parse_args().holdout
    stem = "holdout" if holdout else "audit"
    truth = pd.read_csv(AUDIT / f"{stem}_transactions.csv", dtype=str)
    truth = truth[pd.to_datetime(truth.trade_date, errors="coerce").notna()]
    filings = pd.read_csv(AUDIT / f"{stem}_filings.csv", dtype=str)
    pred, log = run(set(filings.accession))
    pred = pred.copy()
    pred["side"] = pred.side.astype(str)

    om = truth[(truth.transaction_type == "open_market") & (truth.is_derivative.str.lower() == "false")]
    # Labels use only trades dated inside the filing window (+ the extractor's slack).
    fd = truth.accession.map(pd.to_datetime(filings.set_index("accession").filing_date))
    lo = fd - pd.to_timedelta(config("WINDOW_CALENDAR_DAYS") + WINDOW_SLACK_DAYS, unit="D")
    td = pd.to_datetime(truth.trade_date)
    om_win = om[(td[om.index] >= lo[om.index]) & (td[om.index] <= fd[om.index])]
    lines = [f"# 13D extraction vs hand audit ({'holdout' if holdout else 'tuning'} sample)", "",
             f"Audit filings: {len(filings)}; audited rows with dates: {len(truth)} "
             f"(open-market, non-derivative: {len(om)}). Auditor: "
             f"{filings.auditor.iloc[0]}.", "",
             "| Level | Matched | True | Extracted | Recall | Precision |", "|---|---:|---:|---:|---:|---:|"]
    for name, t, p in [("rows, all", keys(truth), keys(pred)),
                       ("rows, open-market non-derivative", keys(om), keys(pred[pred.accession.isin(om.accession)])),
                       ("rows, open-market, inside window", keys(om_win),
                        keys(pred[pred.accession.isin(om_win.accession)])),
                       ("trade days, all", set((a, d) for a, d, *_ in keys(truth)), set((a, d) for a, d, *_ in keys(pred))),
                       ("trade days, open-market", set((a, d) for a, d, *_ in keys(om)),
                        set((a, d) for a, d, *_ in keys(pred[pred.accession.isin(om.accession)])))]:
        hit, nt, npred, r, pr = prf(list(t), list(p))
        lines.append(f"| {name} | {hit} | {nt} | {npred} | {r:.1%} | {pr:.1%} |")

    by = filings[["accession", "issuer_name", "has_open_market_trades", "packet_truncated_trades_possible"]].copy()
    tc, pc = truth.groupby("accession").size(), pred.groupby("accession").size()
    by["true_rows"] = by.accession.map(tc).fillna(0).astype(int)
    by["pred_rows"] = by.accession.map(pc).fillna(0).astype(int)
    tk, pk = Counter(keys(truth)), Counter(keys(pred))
    by["matched"] = [sum(v for k, v in (tk & pk).items() if k[0] == a) for a in by.accession]
    ts = truth.assign(s=pd.to_numeric(truth.shares)).groupby("accession").s.sum()
    ps = pred.groupby("accession").shares.sum()
    by["true_shares"] = by.accession.map(ts).fillna(0)
    by["pred_shares"] = by.accession.map(ps).fillna(0)
    by["regions"] = by.accession.map(log.set_index("accession").regions)
    agree = ((by.true_rows > 0) == (by.pred_rows > 0)).mean()
    lines += ["", f"Filing-level agreement on 'has any trade': {agree:.1%}.", "",
              "Matched-row price agreement (within 0.5%): " + price_agreement(truth, pred), "",
              "## By filing", "", by.drop(columns=["regions"]).to_markdown(index=False)]
    out = config("OUTPUT_DIR")
    (out / f"13d_extraction_eval_{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    by.to_csv(out / f"13d_extraction_eval_{stem}_by_filing.csv", index=False)
    print("\n".join(lines[:12]))


def price_agreement(truth, pred):
    t = truth.assign(k=keys(truth), p=pd.to_numeric(truth.price, errors="coerce")).drop(columns="price")
    p = pred.assign(k=keys(pred)).drop_duplicates("k")
    m = t.merge(p[["k", "price"]], on="k").dropna(subset=["p", "price"])
    if m.empty:
        return "n/a"
    ok = ((m.p - m.price).abs() <= 0.005 * m.p.abs()).mean()
    return f"{ok:.1%} of {len(m)}"


if __name__ == "__main__":
    main()
