"""Table IA.3 feature definitions and strictly historical transformations.

Supplemental inputs are collected separately; no author ITI enters this module.
"""
import numpy as np
import pandas as pd

# Ordered feature contract: six return, ten liquidity, eleven volatility, fourteen volume.
GROUPS = {
    "return": ["ret", "prc", "ret_ov", "ret_in", "ret_am", "ret_pm"],
    "liquidity": ["es", "rs", "pi", "qs", "lambda1", "lambda2", "illiq_in", "illiq_ov", "depth_dollar", "depth_imb"],
    "volatility": ["ret_abs", "ret_ov_abs", "ret_in_abs", "rvol_in", "rvol", "ivol_q", "ivol_t", "var_ratio15s", "var_ratio1mn", "autocorr_in", "ov_last"],
    "volume": ["svol", "svol_am", "svol_pm", "trade_n30", "trade_n5", "ntrades_oc", "ntrades_post", "noddlot", "hindex", "svol_imb", "svol_imb_abs", "ntrades_imb", "ntrades_imb_abs", "vwap_imb"],
}
FEATURES = [feature for group in GROUPS.values() for feature in group]
assert len(FEATURES) == 41 and len(set(FEATURES)) == 41
# Approved exception: odd-lot history is unavailable before tape reporting began.
# XGBoost handles this column's NaNs natively; no zero or mean imputation.
ALLOW_MISSING = ["noddlot"]
REQUIRED_FEATURES = [c for c in FEATURES if c not in ALLOW_MISSING]
IID_MAP = {
    "es": "effectivespread_percent_dw", "rs": "percentrealizedspread_lr_dw",
    "pi": "percentpriceimpact_lr_dw", "qs": "quotedspread_percent_tw",
    "lambda1": "tsignsqrtdvol1", "lambda2": "tsignsqrtdvol2",
    "ivol_q": "ivol_q", "ivol_t": "ivol_t", "var_ratio15s": "var_ratio1",
    "var_ratio1mn": "var_ratio2", "trade_n30": "n30_pos", "trade_n5": "n5_pos",
    "ntrades_oc": "total_n_trades_m", "ntrades_post": "total_n_trades_a",
    "noddlot": "n_oddlot_trade", "hindex": "hindex",
}
SUPPLEMENTAL = ["mid_1000", "mid_1200", "mid_1400", "mid_close", "rv_in", "autocorr_in", "last_return", "volume_open", "svol_am", "svol_pm", "illiq_in", "depth_dollar", "depth_imb"]


def link_indicators(link, iid):
    """Link WRDS indicators to one PERMNO per stock-day, dropping ambiguous keys."""
    symbol_key = ["date", "sym_root", "sym_suffix"]
    for frame in (link, iid):
        frame["sym_suffix"] = frame.sym_suffix.fillna("").astype(str)
    link = link[["permno", *symbol_key]].drop_duplicates()
    link = link[~link.duplicated(symbol_key, keep=False)]
    link = link[~link.duplicated(["permno", "date"], keep=False)]
    iid = iid[~iid.duplicated(symbol_key, keep=False)]
    return link.merge(iid, on=symbol_key, validate="one_to_one")


def derive_features(d):
    """Daily CRSP + IID + supplemental TAQ, sorted by PERMNO/date.

    Overnight return uses previous CRSP close adjusted for changes in cfacpr.
    Midquote returns are simple returns; illiquidity uses absolute simple returns.
    """
    d = d.sort_values(["permno", "date"]).copy()
    if d.duplicated(["permno", "date"]).any():
        raise ValueError("Feature inputs must have unique PERMNO/date keys")
    g = d.groupby("permno", sort=False)
    prior_close = g.prc.shift().abs() / g.cfacpr.shift() * d.cfacpr
    out = d[["permno", "date"]].copy()
    out["ret"], out["prc"], out["svol"] = d.ret, d.prc.abs(), d.vol
    out["ret_ov"] = d.mid_1000 / prior_close - 1
    out["ret_in"] = d.mid_close / d.mid_1000 - 1
    out["ret_am"] = d.mid_1200 / d.mid_1000 - 1
    out["ret_pm"] = d.mid_close / d.mid_1400 - 1
    for target, source in IID_MAP.items():
        out[target] = pd.to_numeric(d[source], errors="coerce")
    for c in ["illiq_in", "depth_dollar", "depth_imb", "svol_am", "svol_pm", "autocorr_in"]:
        out[c] = d[c]
    out["illiq_ov"] = np.where(d.volume_open.eq(0), 0, out.ret_ov.abs() / d.volume_open)
    for c in ["ret", "ret_ov", "ret_in"]:
        out[c + "_abs"] = out[c].abs()
    out["rvol_in"] = np.sqrt(d.rv_in)
    out["rvol"] = np.sqrt(out.ret_ov**2 + d.rv_in)
    out["ov_last"] = out.ret_ov * d.last_return
    out["svol_imb"] = d.buyvol_lr - d.sellvol_lr
    out["svol_imb_abs"] = out.svol_imb.abs()
    out["ntrades_imb"] = d.buynumtrades_lr - d.sellnumtrades_lr
    out["ntrades_imb_abs"] = out.ntrades_imb.abs()
    out["vwap_imb"] = d.vwavg_buy_price_lr - d.vwavg_sell_price_lr
    return out[["permno", "date", *FEATURES]].replace([np.inf, -np.inf], np.nan)


def standardize(raw, window=252, min_periods=200):
    """Previous observations only; never fill missing features or zero SD."""
    d = raw.sort_values(["permno", "date"]).reset_index(drop=True)
    d[FEATURES] = d[FEATURES].astype("float64")
    out = pd.concat([d[["permno", "date"]], pd.DataFrame(np.nan, index=d.index, columns=FEATURES)], axis=1)
    # Truncated acquisition histories must not borrow observations across a gap.
    segment = d.groupby("permno").date.diff().dt.days.gt(7).groupby(d.permno).cumsum()
    for _, part in d.groupby([d.permno, segment], sort=False):
        history = part[FEATURES].shift(1).rolling(window, min_periods=min_periods)
        sd = history.std(ddof=1).replace(0, np.nan)
        out.loc[part.index, FEATURES] = ((part[FEATURES] - history.mean()) / sd).to_numpy()
    out[FEATURES] = out[FEATURES].astype("float32")
    out[FEATURES] = out[FEATURES].where(np.isfinite(out[FEATURES]))
    return out
