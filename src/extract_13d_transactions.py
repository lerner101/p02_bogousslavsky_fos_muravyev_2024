"""Extract disclosed transactions from original Schedule 13D filings.

Where trades are looked for (per filing):
  R1  the Item 5(c) block of the main document;
  R2  the schedule/annex/appendix the 5(c) block refers to, located by its heading in the
      main document (last standalone occurrence);
  R3  exhibit documents whose opening mentions transactions/purchases/sales.
A row is accepted only if its date falls in [filing_date - WINDOW - SLACK, filing_date],
which discards most stray dates from agreements, signatures and biographies.

How rows are read ("table"): the region is tokenized into dates, numbers, side words and
text. The layout is inferred per region: numbers follow each date (date-first) or precede
it (date-last). Within a row, a number with a decimal point or $ is the price, the first
integer-like number is the quantity. A quantity in parentheses, negative, or near a sale
word is a sale. Text lines between rows that look like entity names become the
reporting person. "sentence" rows come from prose ("On May 3, 2016, X purchased 1,000
shares ... at $12.50"), used for R1 only when no table rows were found there.

Output: THIRTEEN_D_DIR/transactions.parquet (schema_13d.TRANSACTIONS) and
        THIRTEEN_D_DIR/extraction_log.parquet (one row per filing: regions, counts,
        no-transactions statement).

Run: python src/extract_13d_transactions.py [--accessions A B ...]
"""

import argparse
import re
import sys
from bisect import bisect_left
from functools import lru_cache
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_13d_filings import SCHEDULE_REF_RE, split_documents  # noqa: E402
from schema_13d import TRANSACTIONS  # noqa: E402
from settings import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "_data" / "wrds" / "sec_13d_filings"
WINDOW_SLACK_DAYS = 15  # filers sometimes include a few days beyond 60
MAX_ROW_LETTERS = 15  # letters (outside allowed row words) above which a "row" is prose
NL = " ¦ "  # line-boundary marker kept inside squashed text
SP = r"(?:\s|¦)+"
SPO = r"(?:\s|¦)*"
MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DATE_RE = re.compile(
    rf"(?P<mdy>\b\d{{1,2}}[/\-.]\d{{1,2}}[/\-.](?:\d{{4}}|\d{{2}})\b)"
    rf"|(?P<iso>\b(?:19|20)\d\d-\d{{2}}-\d{{2}}\b)"
    rf"|(?P<dmy>\b\d{{1,2}}-{MON}-(?:\d{{4}}|\d{{2}})\b)"
    rf"|(?P<long>\b{MON}{SP}\d{{1,2}}(?:st|nd|rd|th)?,?{SP}(?:19|20)\d\d\b)", re.I)
NUM_RE = re.compile(r"(?<![\w.,/\-:])(?P<open>\()?\s*(?P<neg>-)?\s*(?P<dol>\$)?\s*"
                    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
                    r"(?P<close>\))?(?P<trail>-(?![\d\-]))?(?![\w/])")  # "7,000-" = sale
FOOTNOTE_RE = re.compile(r"(?<=\d)\(\d{1,2}\)|(?<=\d)\*+")
SELL_RE = re.compile(r"\b(sale|sales|sold|sell|disposition|disposed)\b|\(\s*S\s*\)", re.I)
BUY_RE = re.compile(r"\b(purchase|purchased|purchases|buy|bought|acquired|acquisition)\b|\(\s*[PB]\s*\)", re.I)
DERIV_RE = re.compile(r"\b(option|options|call|calls|put|puts|swap|swaps|warrant|warrants|"
                      r"forward|forwards|convertible|notional)\b", re.I)
# Words that may appear inside a table row; anything else alphabetic counts toward
# the "this is prose, not a row" test.
ALLOWED_ROW_WORDS = re.compile(
    r"\b(common|stock|shares?|ordinary|class|series|[A-C]|ADSs?|units?|buy|bought|sell|sold|sales?|"
    r"purchases?|purchased|open|market|transactions?|per|USD|US|weighted|average|price|"
    r"¦|n/a|na|nil)\b|\$|[\-_*()]", re.I)
NO_TXN_RE = re.compile(
    r"(ha(?:s|ve)\s+not\s+effected\s+any\s+transactions|no\s+transactions\s+(?:in|involving|were)|"
    r"(?:effected|engaged\s+in)\s+no\s+transactions|\(c\)\s*(?:none|not\s+applicable)\b)", re.I)
# An exhibit is scanned only if its opening reads like a transaction list.
TXN_DOC_RE = re.compile(
    r"transactions?\s+(?:in|effected|by|during)|trade\s+date|"
    r"(?:past|last|preceding)\s+(?:sixty|60)\s*(?:\(60\)\s*)?days", re.I)
ITEM5_FLAT_RE = re.compile(
    rf"Item{SPO}5{SPO}[.:\-]?{SPO}(?:\(?\s*\w?\s*\)?{SPO})?Interest{SP}in{SP}Securities", re.I)
ITEM5_ANY_RE = re.compile(rf"Item{SPO}5\b", re.I)
HEADER_WORDS = re.compile(r"\b(dates?|prices?|shares?|quantity|amount|number|per\s+share|purchased|sold|"
                          r"transactions?|securit(?:y|ies)|class|common|stock|buy|sell|trades?|nature|"
                          r"sales?|purchases?|effected|past|days|acquired|disposed|"
                          r"total|weighted|average|page|cusip|schedule|exhibit|cost|unit|"
                          r"footnote|high|low|range|broker|aggregate)\b", re.I)
PROSE_RE = re.compile(
    rf"\bOn{SP}(?P<date>{MON}{SP}\d{{1,2}},?{SP}(?:19|20)\d\d|\d{{1,2}}/\d{{1,2}}/(?:\d{{4}}|\d{{2}})),?"
    rf"{SP}(?P<who>[^.;]{{0,160}}?){SP}(?P<verb>purchased|acquired|bought|sold|disposed\s+of)"
    rf"{SP}(?:an{SP}aggregate{SP}of{SP}|a{SP}total{SP}of{SP})?(?P<qty>\d{{1,3}}(?:,\d{{3}})+|\d+)"
    rf"{SP}(?:shares|Shares|ordinary|American)"
    rf"(?:[^.;$]{{0,160}}\$\s?(?P<price>\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?))?", re.I)


def to_flat(text):
    """Squash whitespace inside lines; keep line boundaries as NL markers."""
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.splitlines()]
    return NL.join(ln for ln in lines if ln)


@lru_cache(maxsize=100_000)
def parse_date(token):
    """Parse a date token. Numeric dates are month/day/year (US filings); they are read
    day/month only when the first number cannot be a month."""
    t = re.sub(SP, " ", token).replace("Sept", "Sep")
    t = re.sub(r"(\d)(st|nd|rd|th)", r"\1", t)
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})", t)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y = 2000 + y if y < 50 else 1900 + y
        month, day = (b, a) if a > 12 else (a, b)
        try:
            return pd.Timestamp(year=y, month=month, day=day)
        except ValueError:
            return pd.NaT
    return pd.to_datetime(t, errors="coerce")


def tokenize(flat):
    """Return a list of (kind, value, start, end, raw) for dates and numbers."""
    flat = FOOTNOTE_RE.sub(" ", flat)
    toks, taken = [], []
    for m in DATE_RE.finditer(flat):
        d = parse_date(m.group(0))
        if pd.notna(d):
            toks.append(("date", d, m.start(), m.end(), m.group(0)))
            taken.append((m.start(), m.end()))
    t_starts = [a for a, _ in taken]  # date spans are sorted and do not overlap
    for m in NUM_RE.finditer(flat):
        k = bisect_left(t_starts, m.start() + 1) - 1
        if k >= 0 and m.start() < taken[k][1]:
            continue  # inside a date
        num = float(m.group("num").replace(",", ""))
        neg = bool(m.group("neg") or m.group("trail")) or (bool(m.group("open")) and bool(m.group("close")))
        if m.group("open") and m.group("close") and num < 10 and "," not in m.group("num") \
                and "." not in m.group("num"):
            continue  # "(1)" footnote marker standing alone
        is_price = bool(m.group("dol")) or "." in m.group("num")
        toks.append(("num", (num, neg, is_price), m.start(), m.end(), m.group(0)))
    return flat, sorted(toks, key=lambda t: t[2])


def person_heading(gap):
    """Last line in the text gap that looks like an entity name, else None."""
    for ln in reversed([s.strip(" -_:*") for s in gap.split("¦")]):
        if 3 <= len(ln) <= 90 and re.search(r"[A-Za-z]{2}", ln) and not HEADER_WORDS.search(ln) \
                and not re.search(r"[<>]|\.htm|\.txt", ln, re.I) \
                and not DATE_RE.search(ln) and not re.fullmatch(r"[\d\s.,$()\-]+", ln):
            return ln
    return None


def line_bounds(flat, pos):
    a = flat.rfind("¦", 0, pos)
    b = flat.find("¦", pos)
    return (a + 1 if a >= 0 else 0), (b if b >= 0 else len(flat))


def infer_date_first(flat, toks, dates):
    """True if each row's numbers follow its date. Vote on lines holding a date and
    numbers; otherwise compare whether a valid row sits after the last date or
    before the first."""
    after = before = 0
    starts = [t[2] for t in toks]  # tokens are sorted by position
    for i in dates[:500]:  # a sample of rows is enough to decide the layout
        a, b = line_bounds(flat, toks[i][2])
        lo_k, hi_k = bisect_left(starts, a), bisect_left(starts, b)
        nums = [t for t in toks[lo_k:hi_k] if t[0] == "num"]
        after += sum(t[2] > toks[i][2] for t in nums)
        before += sum(t[2] < toks[i][2] for t in nums)
    if after or before:
        return after >= before

    def valid(group):
        return any(t[1][2] for t in group) and any(not t[1][2] for t in group)
    tail = [t for t in toks[dates[-1] + 1:dates[-1] + 6] if t[0] == "num" and t[2] - toks[dates[-1]][3] < 200]
    head = [t for t in toks[max(0, dates[0] - 5):dates[0]] if t[0] == "num" and toks[dates[0]][2] - t[3] < 200]
    return valid(tail) or not valid(head)


def nearest_side(text, anchor):
    """Side word in `text` closest to position `anchor`, or None."""
    best = None
    for rx, side in ((SELL_RE, "sell"), (BUY_RE, "buy")):
        for m in rx.finditer(text):
            d = abs(m.start() - anchor)
            if best is None or d < best[0]:
                best = (d, side)
    return best[1] if best else None


def read_rows(flat, toks, lo, hi):
    """Group tokens into transaction rows; return list of dicts (rows dated in [lo, hi])."""
    dates = [i for i, t in enumerate(toks) if t[0] == "date"]
    if not any(lo <= toks[i][1] <= hi for i in dates):
        return []
    date_first = infer_date_first(flat, toks, dates)
    intro = flat[max(0, toks[dates[0]][2] - 600):toks[dates[0]][2]]
    col = re.search(r"purchas\w*.{0,80}?sold|sold.{0,80}?purchas\w*", intro, re.I)
    sold_second = bool(col) and col.group(0).lower().startswith("purchas")
    s_in, b_in = bool(SELL_RE.search(intro)), bool(BUY_RE.search(intro))
    section_side = "sell" if s_in and not b_in and not col else "buy" if b_in and not s_in and not col else None

    def nums_between(a, b):
        return [toks[k] for k in range(a + 1, b) if toks[k][0] == "num"]

    rows, prev_end = [], 0
    for j, i in enumerate(dates):
        if date_first:
            stop = dates[j + 1] if j + 1 < len(dates) else min(len(toks), i + 6)
            group = [t for t in nums_between(i, stop) if t[2] - toks[i][3] < 250]
            # the row ends at its price: later numbers are page numbers, footnotes, totals
            cut = next((k for k, t in enumerate(group) if t[1][2] and k > 0), None)
            if cut is not None and cut + 1 < len(group) and group[cut + 1][1][2]:
                cut += 1  # "qty  $total  $price": keep both money columns
            group = group[:cut + 1] if cut is not None else group[:3]
            span = (toks[i][2], group[-1][3] if group else toks[i][3])
        else:
            start = dates[j - 1] if j > 0 else max(-1, i - 6)
            group = [t for t in nums_between(start, i) if toks[i][2] - t[3] < 250][-3:]
            span = (group[0][2] if group else toks[i][2], toks[i][3])
        gap = flat[prev_end:span[0]]
        # A heading line with a side word ("Sales of Common Stock") sets the section side.
        for ln in gap.split("¦"):
            if not re.search(r"\d", ln) and len(ln) < 120:
                s = nearest_side(ln, 0)
                if s and (SELL_RE.search(ln) is None) != (BUY_RE.search(ln) is None):
                    section_side = s
        qtys = [t for t in group if not t[1][2] and t[1][0] >= 1]
        money = [t for t in group if t[1][2]]
        if qtys and len(money) >= 2:
            # A total-dollar column: drop any money value equal to qty x another money value.
            qv = (qtys[0] if date_first else qtys[-1])[1][0]
            totals = [m for m in money if any(o is not m and abs(qv * o[1][0] - m[1][0])
                                              <= 0.02 * m[1][0] for o in money)]
            group = [t for t in group if t not in totals]
        prices = [t for t in group if t[1][2] and 0.005 <= t[1][0] <= 20000]
        if not qtys:
            big = [t for t in group if t[1][0] >= 1 and t not in prices[:1]]
            qtys = big[:1]
        if not prices and len(qtys) >= 2:
            # whole-dollar price without "$" or decimals, e.g. "(276) 30"
            cand = qtys[1] if date_first else qtys[-1]
            if cand[1][0] <= 5000 and "," not in cand[4] and not cand[1][1]:
                prices = [cand]
                qtys = [t for t in qtys if t is not cand]
        in_window = lo <= toks[i][1] <= hi
        if not in_window or not qtys or not prices:  # a row needs a date, quantity and price
            prev_end = max(prev_end, span[1])
            continue
        q = qtys[0] if date_first else qtys[-1]
        pr = prices[0] if date_first else prices[-1]
        if not date_first:
            # the row starts at its own quantity/price, not at stray numbers before it
            span = (min(q[2], pr[2]), toks[i][3])
            gap = flat[prev_end:span[0]]
            for ln in gap.split("¦"):
                if not re.search(r"\d", ln) and len(ln) < 120:
                    s = nearest_side(ln, 0)
                    if s and (SELL_RE.search(ln) is None) != (BUY_RE.search(ln) is None):
                        section_side = s
        letters = len(re.findall(r"[A-Za-z]", ALLOWED_ROW_WORDS.sub(" ", flat[span[0]:span[1]])))
        if letters > MAX_ROW_LETTERS:  # a prose sentence, not a table row
            prev_end = max(prev_end, span[1])
            continue
        a, _ = line_bounds(flat, span[0])
        row_text = flat[max(prev_end, a):span[1]]
        anchor = toks[i][2] - max(prev_end, a)
        side = "sell" if q[1][1] else nearest_side(row_text, anchor)
        if side is None and col:
            between = flat[toks[i][3]:q[2]] if date_first else flat[span[0]:q[2]]
            placeholder = bool(re.search(r"(?:^|\s)(?:--+|—|-|n/a)(?:\s|$)", between, re.I))
            side = ("sell" if sold_second else "buy") if placeholder else ("buy" if sold_second else "sell")
        side = side or section_side or "buy"
        rows.append({"trade_date": toks[i][1], "side": side, "shares": q[1][0],
                     "price": pr[1][0],
                     "security_class": "Common Stock" if re.search(r"common", row_text + gap[-200:], re.I) else None,
                     "is_derivative": bool(DERIV_RE.search(row_text)),
                     "heading": person_heading(gap), "char_offset": span[0]})
        prev_end = span[1]
    person = None
    for r in rows:
        person = r.pop("heading") or person
        r["reporting_person"] = person
    return rows


def prose_rows(flat, lo, hi):
    rows = []
    for m in PROSE_RE.finditer(flat):
        d = parse_date(m.group("date"))
        if pd.isna(d) or not (lo <= d <= hi):
            continue
        rows.append({"trade_date": d, "side": "sell" if re.match(r"sold|disposed", m.group("verb"), re.I) else "buy",
                     "shares": float(m.group("qty").replace(",", "")),
                     "price": float(m.group("price").replace(",", "")) if m.group("price") else None,
                     "security_class": None, "is_derivative": bool(DERIV_RE.search(m.group(0))),
                     "reporting_person": re.sub(SP, " ", m.group("who")).strip()[:90] or None,
                     "char_offset": m.start()})
    return rows


def item5c_block(flat):
    heads = list(ITEM5_FLAT_RE.finditer(flat)) or list(ITEM5_ANY_RE.finditer(flat))
    if not heads:
        return None, None
    start = heads[-1].start()
    # Prefer lowercase "(c)": "(C) 809,000 shares" can appear inside Item 5(a).
    c = (re.search(rf"\({SPO}c{SPO}\)|(?:^|¦)\s*c\)", flat[start:start + 20000])
         or re.search(rf"\({SPO}C{SPO}\)|(?:^|¦)\s*C\)", flat[start:start + 20000]))
    if not c:
        return start, flat[start:start + 6000]
    s = start + c.start()
    end = re.search(rf"\({SPO}d{SPO}\)|Item{SPO}6\b", flat[s + 3:s + 60000], re.I)
    return s, flat[s:s + 3 + (end.start() if end else 6000)]


def referenced_block(flat, ref, after):
    """Text under the last standalone heading named `ref` (e.g. 'Schedule A') after `after`."""
    kind, label = ref.split(" ", 1)
    pat = re.compile(rf"(?:^|¦)\s*{kind}{SP}{re.escape(label)}\b", re.I)
    hits = [m for m in pat.finditer(flat) if m.start() > (after or 0)]
    if not hits:
        return None, None
    s = hits[-1].start()
    nxt = re.search(r"¦\s*(?:SCHEDULE|ANNEX|APPENDIX|EXHIBIT|SIGNATURES?)\b(?!\s*" + re.escape(label) + ")",
                    flat[s + 20:], re.I)
    return s, flat[s:s + 20 + (nxt.start() if nxt else 200000)]


def exhibit_matches(label, doc_type, flat):
    """True if the exhibit document is the one Item 5(c) points to: its type ends with the
    label ("Exhibit 2" -> EX-2 / EX-99.2) or its opening names it ("Schedule A")."""
    if not label:
        return False
    lab = re.escape(label.upper())
    if re.search(rf"(?:^|[-.]){lab}$", doc_type.upper().strip()):
        return True
    return bool(re.search(rf"\b(?:SCHEDULE|ANNEX|APPENDIX|EXHIBIT|ATTACHMENT){SP}{lab}\b",
                          flat[:600], re.I))


def extract_filing(accession, filing_date, text):
    hi = pd.Timestamp(filing_date)
    lo = hi - pd.to_timedelta(config("WINDOW_CALENDAR_DAYS") + WINDOW_SLACK_DAYS, unit="D")
    docs = split_documents(str(text))
    rows, log = [], {"accession": accession, "regions": [], "no_txn_statement": False}
    ref_label = None
    for doc_no, (typ, body) in enumerate(docs, start=1):
        flat_all = to_flat(body)
        if doc_no == 1 or typ.upper().startswith("SC 13D"):
            pos, block = item5c_block(flat_all)
            regions = []
            if block:
                log["no_txn_statement"] = bool(NO_TXN_RE.search(block))
                regions.append(("item5c", pos, block))
                ref = SCHEDULE_REF_RE.search(re.sub(SP, " ", block[:2500]))
                if ref:
                    ref_label = ref.group(2)
                    rpos, rblock = referenced_block(flat_all, f"{ref.group(1)} {ref.group(2)}", pos)
                    if rblock:
                        regions.append((f"ref:{ref.group(1)} {ref.group(2)}", rpos, rblock))
        elif typ.upper().startswith(("GRAPHIC", "EX-24", "ZIP", "XML")):
            continue
        elif exhibit_matches(ref_label, typ, flat_all) or TXN_DOC_RE.search(flat_all[:3000]):
            regions = [(f"exhibit:{typ}", 0, flat_all)]
        else:
            continue
        for name, pos, block in regions:
            flat, toks = tokenize(block)
            found = read_rows(flat, toks, lo, hi)
            method = "table"
            if not found and name == "item5c":
                found, method = prose_rows(flat, lo, hi), "sentence"
            for r in found:
                r.update(accession=accession, source_document=doc_no, parse_method=method,
                         char_offset=(pos or 0) + r["char_offset"], region=name)
            rows += found
            log["regions"].append(f"{name}:{len(found)}")
    log["regions"] = ";".join(log["regions"])
    log["n_rows"] = len(rows)
    return rows, log


def finalize(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=list(TRANSACTIONS) + ["region"])
    # The same text read twice (overlapping regions) is kept once; identical trades on
    # separate lines are genuine and kept.
    df = df.drop_duplicates(["accession", "source_document", "char_offset"])
    nonmember = re.compile(r"not\s+(?:a\s+)?(?:member|reporting\s+person)", re.I)
    df["is_group_member"] = ~df.reporting_person.fillna("").str.contains(nonmember)
    out = df.copy()
    for col, dtype in TRANSACTIONS.items():
        if col not in out:
            out[col] = pd.NA
        out[col] = out[col].astype(dtype)
    return out[list(TRANSACTIONS) + ["region"]]


def run(accessions=None):
    rows, logs = [], []
    for path in sorted(p for p in SOURCE.glob("*.parquet")
                       if p.stem.isdigit() and 2005 <= int(p.stem) <= 2019):
        df = pd.read_parquet(path, columns=["accession", "form", "filing_date", "filing"])
        df = df[df.form == "SC 13D"]
        if accessions is not None:
            df = df[df.accession.isin(accessions)]
        for a, d, t in zip(df.accession, df.filing_date, df.filing):
            r, lg = extract_filing(a, d, t)
            rows += r
            logs.append(lg)
        if len(df):
            print("Extracted", path.stem, len(df), flush=True)
    return finalize(rows), pd.DataFrame(logs)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--accessions", nargs="*")
    p.add_argument("--out", type=Path, default=None, help="directory for outputs")
    args = p.parse_args()
    tx, log = run(set(args.accessions) if args.accessions else None)
    out = args.out or config("THIRTEEN_D_DIR")
    out.mkdir(parents=True, exist_ok=True)
    tx.to_parquet(out / "transactions.parquet", index=False)
    log.to_parquet(out / "extraction_log.parquet", index=False)
    print(f"{len(tx):,} transactions from {log.accession.nunique():,} filings; "
          f"{(log.n_rows > 0).mean():.1%} of filings have >= 1 row; "
          f"{log.no_txn_statement.mean():.1%} state no transactions")


if __name__ == "__main__":
    main()
