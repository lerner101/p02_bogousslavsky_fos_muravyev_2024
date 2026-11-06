"""Parse filing-level metadata from original Schedule 13D submissions.

Input:  _data/wrds/sec_13d_filings/YYYY.parquet (WRDS `filing_sc_13d` text; HTML
        already stripped, so table cells appear one per line).
Output: THIRTEEN_D_DIR/filings.parquet, one row per accession (schema_13d.FILINGS).

Run: python src/parse_13d_filings.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_13d import FILINGS  # noqa: E402
from settings import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "_data" / "wrds" / "sec_13d_filings"

DOC_RE = re.compile(r"<DOCUMENT>(.*?)(?:</DOCUMENT>|\Z)", re.S)
TYPE_RE = re.compile(r"<TYPE>\s*([^\n<]+)")
HEADER_RE = re.compile(r"<SEC-HEADER>(.*?)</SEC-HEADER>", re.S)
CUSIP_LABEL_RE = re.compile(r"\(\s*CUSIP\s+(?:Number|No\.?)\s*\)", re.I)
CUSIP_PAGE_RE = re.compile(r"CUSIP\s*(?:No\.?|Number|#)?\s*[:.]?\s*([0-9A-Z][0-9A-Z \-]{6,13}[0-9A-Z])", re.I)
CUSIP_TOKEN_RE = re.compile(r"\b([0-9A-Z]{6})[ \-]?([0-9A-Z]{2})[ \-]?([0-9])?\b")
ISSUER_LABEL_RE = re.compile(r"\(\s*Name\s+of\s+(?:the\s+)?(?:Issuer|Company)\s*\)", re.I)
EVENT_LABEL_RE = re.compile(r"\(\s*Date\s+of\s+Event", re.I)
MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DATE_TEXT_RE = re.compile(rf"\b{MONTHS}\s+\d{{1,2}}\s*,?\s*(?:19|20)\d\d\b"
                          r"|\b\d{1,2}/\d{1,2}/(?:19|20)?\d\d\b", re.I)
ITEM5_RE = re.compile(r"Item\s*5\s*[.:\-]?\s*(?:\(?\s*\w?\s*\)?\s*)?Interest\s+in\s+Securities", re.I)
ITEM5C_RE = re.compile(r"\(\s*c\s*\)", re.I)
SCHEDULE_REF_RE = re.compile(
    r"\b(Schedule|Annex|Appendix|Exhibit|Attachment)\s+(?!13D)([A-Z0-9]{1,3}(?:[.\-]\d{1,2})?|[IVX]{1,4})\b")


def squash(text):
    """Collapse all whitespace runs to one space."""
    return re.sub(r"\s+", " ", text).strip()


def split_documents(text):
    """Return [(document_type, document_text)] in submission order."""
    docs = []
    for body in DOC_RE.findall(text):
        m = TYPE_RE.search(body)
        docs.append(((m.group(1).strip() if m else ""), body))
    return docs or [("", text)]


def parse_header(text):
    """Extract subject/filer CIK and names from the SGML header."""
    out = {"subject_cik": None, "subject_name": None, "filer_cik": None, "filer_name": None}
    m = HEADER_RE.search(text)
    header = m.group(1) if m else text[:20000]
    for role, key in (("SUBJECT COMPANY", "subject"), ("FILED BY", "filer")):
        start = header.find(role + ":")
        if start < 0:
            continue
        nxt = [header.find(r + ":", start + 1) for r in ("SUBJECT COMPANY", "FILED BY")]
        nxt = [n for n in nxt if n > start]
        block = header[start:min(nxt) if nxt else len(header)]
        name = re.search(r"COMPANY CONFORMED NAME:\s*(.+)", block)
        cik = re.search(r"CENTRAL INDEX KEY:\s*(\d+)", block)
        out[key + "_name"] = name.group(1).strip() if name else None
        out[key + "_cik"] = cik.group(1).zfill(10) if cik else None
    return out


def cusip_check_digit(cusip8):
    """Standard CUSIP modulus-10 'double add double' check digit."""
    total = 0
    for i, ch in enumerate(cusip8.upper()):
        if ch.isdigit():
            v = int(ch)
        elif ch.isalpha():
            v = ord(ch) - ord("A") + 10
        else:
            v = {"*": 36, "@": 37, "#": 38}.get(ch, 0)
        if i % 2 == 1:
            v *= 2
        total += v // 10 + v % 10
    return str((10 - total % 10) % 10)


def normalize_cusip(token):
    """Clean a CUSIP-like token; return 8/9 characters or None."""
    s = re.sub(r"[\s\-]", "", token.upper())
    if not (8 <= len(s) <= 9) or not s.isalnum():
        return None
    if not re.search(r"\d", s[:6]) or not s[6:8].isalnum():
        return None
    return s


def cusip_candidates(doc_text):
    """CUSIP candidates: cover-page label first, then 'CUSIP No.' page headers."""
    found = []
    for m in CUSIP_LABEL_RE.finditer(doc_text[:30000]):
        before = doc_text[max(0, m.start() - 200):m.start()]
        lines = [ln.strip() for ln in before.splitlines() if ln.strip().strip("-_ ")]
        for ln in reversed(lines[-2:]):
            for tok in CUSIP_TOKEN_RE.finditer(ln.upper()):
                c = normalize_cusip("".join(g or "" for g in tok.groups()))
                if c:
                    found.append(c)
            if found:
                break
        if found:
            break
    for m in CUSIP_PAGE_RE.finditer(doc_text[:200000]):
        c = normalize_cusip(m.group(1))
        if c is None:
            tok = CUSIP_TOKEN_RE.search(m.group(1).upper())
            c = normalize_cusip("".join(g or "" for g in tok.groups())) if tok else None
        if c:
            found.append(c)
    return list(dict.fromkeys(found))


def order_cusips(candidates):
    """Order candidates for linking: the cover-page CUSIP first (later pages are
    sometimes copied from another filing), unless it is a 9-character CUSIP with
    an invalid check digit; then valid 9-character, then the rest."""
    def rank(item):
        i, c = item
        valid9 = len(c) == 9 and cusip_check_digit(c[:8]) == c[8]
        bad9 = len(c) == 9 and not valid9
        return (0 if i == 0 and not bad9 else 1, 0 if valid9 else 1 if len(c) == 8 else 2, i)
    return [c for _, c in sorted(enumerate(candidates), key=rank)]


def parse_issuer_name(doc_text):
    """Cover-page issuer name: the text just above '(Name of Issuer)'."""
    m = ISSUER_LABEL_RE.search(doc_text[:30000])
    if not m:
        return None
    before = doc_text[max(0, m.start() - 300):m.start()]
    blocks = [squash(b) for b in re.split(r"\n\s*\n|-{5,}|_{5,}", before)]
    blocks = [b for b in blocks if b.strip("-_ ")]
    return blocks[-1][:200] if blocks else None


def parse_event_date(doc_text):
    m = EVENT_LABEL_RE.search(doc_text[:30000])
    if not m:
        return pd.NaT
    before = squash(doc_text[max(0, m.start() - 160):m.start()])
    dates = DATE_TEXT_RE.findall(before)
    if not dates:
        return pd.NaT
    raw = re.sub(r"\s*,?\s*((?:19|20)\d\d)$", r", \1", dates[-1].replace("Sept", "Sep"))
    return pd.to_datetime(raw, errors="coerce")


def item5_location(doc_text):
    """Return (found, character offset of Item 5(c) or Item 5, schedule reference)."""
    squashed_positions = list(ITEM5_RE.finditer(doc_text))
    if not squashed_positions:
        # Headings are often split over lines ("Item\n5."), which \s* already covers;
        # fall back to any 'Item 5' heading.
        squashed_positions = list(re.finditer(r"Item\s*5\b", doc_text, re.I))
    if not squashed_positions:
        return False, None, None
    start = squashed_positions[-1].start()
    c = ITEM5C_RE.search(doc_text, start, start + 15000)
    anchor = c.start() if c else start
    window = squash(doc_text[anchor:anchor + 1500])
    ref = SCHEDULE_REF_RE.search(window)
    return True, anchor, (f"{ref.group(1).title()} {ref.group(2)}" if ref else None)


def parse_filing(accession, filing_date, text):
    text = str(text)
    docs = split_documents(text)
    main = next((body for typ, body in docs if typ.upper().startswith("SC 13D")), docs[0][1])
    cands = order_cusips(cusip_candidates(main))
    cusip = cands[0] if cands else None
    found, _, ref = item5_location(main)
    row = {"accession": accession, "filing_date": filing_date, **parse_header(text),
           "issuer_name": parse_issuer_name(main), "cusip_cover": cusip,
           "cusip8": cusip[:8] if cusip else None,
           "cusip_candidates": ";".join(dict.fromkeys(c[:8] for c in cands)) or None,
           "event_date": parse_event_date(main), "n_documents": len(docs),
           "item5_found": found, "schedule_ref": ref}
    return row


def apply_schema(df, schema):
    for col, dtype in schema.items():
        if col not in df:
            df[col] = pd.NA
        df[col] = df[col].astype(dtype)
    return df[list(schema)]


def main():
    rows = []
    for path in sorted(SOURCE.glob("*.parquet")):
        df = pd.read_parquet(path, columns=["accession", "form", "filing_date", "filing"])
        df = df[df.form == "SC 13D"]
        rows += [parse_filing(a, d, t) for a, d, t in zip(df.accession, df.filing_date, df.filing)]
        print("Parsed", path.stem, len(df), flush=True)
    out = apply_schema(pd.DataFrame(rows).drop_duplicates("accession"), FILINGS)
    target = config("THIRTEEN_D_DIR") / "filings.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(target, index=False)
    print(f"Saved {len(out):,} filings to {target}")
    print("CUSIP found:", f"{out.cusip8.notna().mean():.1%}",
          "| event date:", f"{out.event_date.notna().mean():.1%}",
          "| Item 5:", f"{out.item5_found.mean():.1%}",
          "| schedule ref:", f"{out.schedule_ref.notna().mean():.1%}")


if __name__ == "__main__":
    main()
