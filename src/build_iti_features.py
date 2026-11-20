"""Build complete Table IA.3 raw and standardized features for acquired stocks.

python src/build_iti_features.py [--allow-partial]
By default require every requested TAQ day. Partial mode is diagnostic only.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from collect_iti_taq import VERSION
from iti_features import (
    ALLOW_MISSING,
    FEATURES,
    IID_MAP,
    REQUIRED_FEATURES,
    SUPPLEMENTAL,
    derive_features,
    standardize,
)

ROOT = Path(__file__).resolve().parents[1]
WRDS = ROOT / "_data/wrds"
DEST = ROOT / "_data/derived/ml_model"
OUT = ROOT / "_output/ml_model"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()
    request_path = WRDS / "iti_supplemental/request.parquet"
    if not request_path.exists():
        raise SystemExit("Run python src/collect_iti_taq.py first; --pilot alone does not supply training histories.")
    request = pd.read_parquet(request_path)
    files = sorted((WRDS / "iti_supplemental/daily").glob("*.parquet"))
    dates = {p.stem for p in files}
    missing = []
    valid_files = []
    for date, u in request.groupby("date"):
        stamp = date.strftime("%Y%m%d")
        path = WRDS / f"iti_supplemental/daily/{stamp}.parquet"
        meta = path.with_suffix(".json")
        fingerprint = hashlib.sha256((str(VERSION) + u.to_csv(index=False)).encode()).hexdigest()
        if stamp not in dates or not meta.exists() or json.loads(meta.read_text()).get("request_sha256") != fingerprint:
            missing.append(stamp)
        else:
            valid_files.append(path)
    files = valid_files
    if missing and not args.allow_partial:
        raise SystemExit(f"Supplemental acquisition incomplete: {len(missing)} trading dates missing. Resume collect_iti_taq.py.")
    if not files:
        raise SystemExit("No supplemental daily aggregates available.")
    supplemental = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    if not args.allow_partial and len(supplemental) != len(request):
        raise ValueError("Supplemental rows differ from the requested security/day count")
    if supplemental.duplicated(["permno", "date"]).any():
        raise ValueError("Duplicate supplemental stock-days")
    stocks = request.permno.astype(int).unique().tolist()
    frames = []
    for year in range(2004, 2020):
        d = pd.read_parquet(WRDS / f"crsp_daily/{year}.parquet", filters=[("permno", "in", stocks)],
                            columns=["permno", "date", "prc", "ret", "vol", "shrout", "cfacpr"])
        wanted = request.loc[request.date.dt.year.eq(year), ["permno", "date"]]
        d = d.merge(wanted, on=["permno", "date"], validate="one_to_one")
        link = pd.read_parquet(WRDS / f"crsp_taq_links/{year}.parquet", filters=[("permno", "in", stocks)])
        iid_cols = list(dict.fromkeys(["date", "sym_root", "sym_suffix", *IID_MAP.values(),
                    "buyvol_lr", "sellvol_lr", "buynumtrades_lr", "sellnumtrades_lr", "vwavg_buy_price_lr", "vwavg_sell_price_lr"]))
        iid = pd.read_parquet(WRDS / f"intraday_indicators/{year}.parquet", columns=iid_cols)
        for x in (link, iid):
            x["sym_suffix"] = x.sym_suffix.fillna("").astype(str)
        link = link[["permno", "date", "sym_root", "sym_suffix"]].drop_duplicates()
        link = link[~link.duplicated(["date", "sym_root", "sym_suffix"], keep=False)]
        link = link[~link.duplicated(["permno", "date"], keep=False)]
        iid = iid[~iid.duplicated(["date", "sym_root", "sym_suffix"], keep=False)]
        m = link.merge(iid, on=["date", "sym_root", "sym_suffix"], validate="one_to_one")
        frames.append(d.merge(m.drop(columns=["symbol"], errors="ignore"), on=["permno", "date"],
                              how="left", validate="one_to_one"))
    daily = pd.concat(frames, ignore_index=True).sort_values(["permno", "date"]).reset_index(drop=True)
    daily = daily.merge(supplemental[["permno", "date", *SUPPLEMENTAL]],
                        on=["permno", "date"], how="left", validate="one_to_one")
    for c in ["prc", "ret", "vol", "shrout", "cfacpr", *SUPPLEMENTAL]:
        daily[c] = pd.to_numeric(daily[c], errors="coerce")
    raw = derive_features(daily)
    features = standardize(raw)
    # Eligibility at the last available trading day of the preceding month.
    daily["month"] = daily.date.dt.to_period("M")
    daily["mcap"] = daily.prc.abs() * daily.shrout * 1000
    last = daily.groupby(["permno", "month"], sort=False).tail(1)[["permno", "month", "prc", "mcap"]].copy()
    last["month"] += 1
    last["eligible"] = last.prc.abs().gt(5) & last.mcap.gt(100e6)
    eligibility = daily[["permno", "date", "month"]].merge(last[["permno", "month", "eligible"]],
                                                           on=["permno", "month"], how="left")
    names = pd.read_parquet(WRDS / "crsp_names.parquet", columns=["permno", "namedt", "nameendt", "shrcd"])
    names = names[pd.to_numeric(names.shrcd).isin([10, 11])]
    common = daily[["permno", "date"]].merge(names, on="permno")
    common = common[common.date.between(common.namedt, common.nameendt)][["permno", "date"]].drop_duplicates()
    common["common_stock"] = True
    eligibility = eligibility.merge(common, on=["permno", "date"], how="left")
    eligibility["eligible"] = eligibility.eligible.astype("boolean").fillna(False) & eligibility.common_stock.astype("boolean").fillna(False)
    features = features.merge(eligibility[["permno", "date", "eligible"]], on=["permno", "date"], validate="one_to_one")
    features["all_41_complete"] = np.isfinite(features[FEATURES]).all(axis=1)
    features["complete"] = np.isfinite(features[REQUIRED_FEATURES]).all(axis=1)
    DEST.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(DEST / "raw_features.parquet", index=False)
    features.to_parquet(DEST / "features.parquet", index=False)
    missingness = features.groupby(features.date.dt.year)[FEATURES].agg(lambda s: s.isna().mean()).T
    missingness.to_csv(OUT / "feature_missingness_by_year.csv")
    labels = pd.read_parquet(ROOT / "_data/derived/13d/labels_daily.parquet")
    audit = labels.merge(features[["permno", "date", "complete", "all_41_complete"]], on=["permno", "date"], how="left", validate="many_to_one")
    audit["complete"] = audit.complete.astype("boolean").fillna(False)
    audit["all_41_complete"] = audit.all_41_complete.astype("boolean").fillna(False)
    audit.groupby(audit.filing_date.dt.year).agg(label_rows=("filing", "size"), complete_rows=("complete", "sum"),
                                               strict_41_rows=("all_41_complete", "sum"),
                                               filings=("filing", "nunique")).to_csv(OUT / "training_attrition_by_year.csv")
    audit.groupby("filing").agg(label_rows=("date", "size"), complete_rows=("complete", "sum")).to_csv(OUT / "training_attrition_by_filing.csv")
    source_meta = list(WRDS.glob("crsp_daily/*.json")) + list(WRDS.glob("intraday_indicators/*.json")) + list(WRDS.glob("crsp_taq_links/*.json"))
    source_meta += [WRDS / "crsp_names.json"]
    manifest = {"features": FEATURES, "allow_missing": ALLOW_MISSING, "window": 252, "min_periods": 200, "ddof": 1,
                "partial_acquisition": bool(missing), "missing_dates": missing,
                "feature_sha256": sha256(DEST / "features.parquet"),
                "request_sha256": sha256(request_path),
                "sources": {str(p.relative_to(ROOT)): sha256(p.with_suffix(".json")) for p in files},
                "source_manifests": {str(p.relative_to(ROOT)): sha256(p) for p in source_meta}}
    (DEST / "features_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Features: {len(features):,} stock-days; {features.complete.sum():,} complete; acquisition partial: {bool(missing)}")


if __name__ == "__main__":
    main()
