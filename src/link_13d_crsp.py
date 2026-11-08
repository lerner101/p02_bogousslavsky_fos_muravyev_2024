"""Link Schedule 13D filings to CRSP PERMNOs.

Candidates, in priority order:
1. "cusip":         a cover/page CUSIP (8 chars) equal to CRSP `ncusip` in a name record
                    covering the filing date ("cusip_undated" if only within 365 days).
                    Candidates are tried in the parser's priority order.
2. "cik":           subject CIK -> CUSIP via WRDS `wciklink_cusip` (link dates within 365
                    days of the filing date), then the same ncusip match. That table is noisy.

Each candidate PERMNO gets `name_score`: the best similarity between the filing's cover
issuer name or header subject name and *any* CRSP company name of that PERMNO in the
extract, so renames are not penalized. EDGAR headers are sometimes wrong (a filer listed
as its own subject), and later "CUSIP No." page headers are sometimes copied from another
filing, so the first candidate with name_score >= MIN_NAME_SCORE wins; if none passes,
the highest-priority candidate is kept with `name_ok = False` for the events screen.

Output: THIRTEEN_D_DIR/filing_links.parquet
    accession, permno, link_method, cusip8_used, crsp_name, name_score, name_ok

Run: python src/link_13d_crsp.py
"""

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from settings import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WRDS = ROOT / "_data" / "wrds"
SLACK = pd.to_timedelta(365, unit="D")
MIN_NAME_SCORE = 0.5
SUFFIXES = (r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|LLC|LP|L P|"
            r"HOLDINGS?|HLDGS|GROUP|GRP|THE|NEW|DEL|DE|NV|SA|AG|N V|S A|N Y|NY)\b")


def normalize_name(name):
    s = "" if pd.isna(name) else str(name).upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(SUFFIXES, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_score(a, b):
    """Similarity in [0, 1] between two company names after removing legal suffixes."""
    a, b = normalize_name(a), normalize_name(b)
    if not a or not b:
        return 0.0
    if a.startswith(b) or b.startswith(a):
        return 1.0
    sa, sb = " ".join(sorted(a.split())), " ".join(sorted(b.split()))  # word order
    return max(SequenceMatcher(None, a, b).ratio(), SequenceMatcher(None, sa, sb).ratio())


def dated_ncusip_matches(cands, names):
    """cands: accession, filing_date, cusip8, priority. Returns matches with method."""
    m = cands.merge(names[["permno", "namedt", "nameendt", "ncusip"]],
                    left_on="cusip8", right_on="ncusip", how="inner")
    covers = (m.namedt <= m.filing_date) & (m.filing_date <= m.nameendt)
    near = (m.namedt - SLACK <= m.filing_date) & (m.filing_date <= m.nameendt + SLACK)
    m = m[near].copy()
    m["dated"] = covers[near]
    m = (m.sort_values(["accession", "priority", "dated"], ascending=[True, True, False])
         .drop_duplicates(["accession", "priority", "permno"]))
    return m[["accession", "priority", "cusip8", "permno", "dated"]]


def main():
    out_dir = config("THIRTEEN_D_DIR")
    filings = pd.read_parquet(out_dir / "filings.parquet")
    names = pd.read_parquet(WRDS / "crsp_names.parquet",
                            columns=["permno", "namedt", "nameendt", "ncusip", "comnam"])
    names = names.dropna(subset=["ncusip"])
    name_history = names.groupby("permno").comnam.agg(lambda s: list(dict.fromkeys(s)))

    # 1. CUSIP candidates from the filing text, in priority order.
    cands = filings[["accession", "filing_date", "cusip_candidates"]].dropna()
    cands = cands.assign(cusip8=cands.cusip_candidates.str.split(";")).explode("cusip8")
    cands["priority"] = cands.groupby("accession").cumcount()
    direct = dated_ncusip_matches(cands[["accession", "filing_date", "cusip8", "priority"]], names)
    direct["link_method"] = direct.dated.map({True: "cusip", False: "cusip_undated"})

    # 2. Subject-CIK candidates, ranked after every text CUSIP.
    links = pd.read_parquet(WRDS / "sec_cusip_links.parquet",
                            columns=["cik", "cusip", "cikdate1", "cikdate2", "tmatch"])
    via = filings[["accession", "filing_date", "subject_cik"]].merge(
        links, left_on="subject_cik", right_on="cik", how="inner")
    via = via[(via.cikdate1 - SLACK <= via.filing_date) & (via.filing_date <= via.cikdate2 + SLACK)]
    via = via.sort_values("tmatch", ascending=False).rename(columns={"cusip": "cusip8"})
    via["priority"] = 100 + via.groupby("accession").cumcount()
    cik = dated_ncusip_matches(via[["accession", "filing_date", "cusip8", "priority"]], names)
    cik["link_method"] = "cik"

    allc = pd.concat([direct, cik], ignore_index=True).merge(
        filings[["accession", "issuer_name", "subject_name"]], on="accession")
    allc["name_score"] = [
        max([name_score(n, h) for n in (iss, sub) for h in name_history.get(p, [])] or [0.0])
        for iss, sub, p in zip(allc.issuer_name, allc.subject_name, allc.permno)]
    allc["name_ok"] = allc.name_score >= MIN_NAME_SCORE
    # Text CUSIPs are trusted without a name match only if nothing else matches;
    # CIK-route links always require a name match.
    allc = allc[(allc.link_method != "cik") | allc.name_ok]
    best = (allc.sort_values(["accession", "name_ok", "priority"], ascending=[True, False, True])
            .drop_duplicates("accession"))
    best["crsp_name"] = best.permno.map(lambda p: name_history.get(p, [None])[-1])
    out = best[["accession", "permno", "link_method", "cusip8", "crsp_name", "name_score", "name_ok"]]
    out = out.rename(columns={"cusip8": "cusip8_used"})
    out["permno"] = out.permno.astype("Int64")
    out.to_parquet(out_dir / "filing_links.parquet", index=False)
    print(f"Linked {len(out):,} of {len(filings):,} filings ({len(out)/len(filings):.1%})")
    print(out.link_method.value_counts().to_string())
    print("Links failing the name check (excluded later):", f"{(~out.name_ok).sum():,}")


if __name__ == "__main__":
    main()
