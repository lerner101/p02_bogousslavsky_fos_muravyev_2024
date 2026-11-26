"""Replicate Tables 1-4 on our rebuilt Schedule 13D sample and daily panel.

Table 1: descriptive statistics of the controls and ITI measures (full panel)
         and of the 13D trade indicator (13D sample).
Table 2: day-with-13D-trade (cols 1-3) and 13D filer turnover on trade days
         (cols 4-6) on held-out ITI(13D) and controls, filing FE.
Table 3: day-with-13D-trade on the feature-group ITIs, filing FE
         (needs src/train_iti_groups.py).
Table 4: within-filing turnover matching of trade and non-trade days.

Inputs, all produced by existing tasks:
  _data/derived/ml_model/oof_predictions.parquet   held-out ITI(13D) (iti_train)
  _data/derived/ml_model/raw_features.parquet + WRDS extracts  controls (as Figure 1)
  _data/derived/13d/labels_daily.parquet           itrade, turn, 13Dturn (13d_labels)
  _data/derived/panel/daily.parquet                full panel (panel)
  _data/derived/ml_model/group_oof_predictions.parquet  group ITIs (Table 3 only)
Outputs: _output/replication/table{1,2,3,4}.csv, in the same long format as
Tables 5 and 10 (column, variable, coef, t) so the scorecard can read them.

Run: python src/replicate_tables.py [table1 table2 table3 table4]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_values import ITI_NAMES, TABLE4_TURN_GAP  # noqa: E402
from regress import fe_ols  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "_data/derived/ml_model"
LABELS = ROOT / "_data/derived/13d/labels_daily.parquet"
PANEL = ROOT / "_data/derived/panel/daily.parquet"
OUT = ROOT / "_output/replication"
SAMPLE_START, SAMPLE_END = "2005-01-01", "2019-07-31"
# Table 2 controls as listed in the table (the text also mentions price impact).
CONTROLS = ["es", "lambda", "depth", "rvol", "turn", "oi", "abs_oi", "ret"]
SCORE = "ITI(13D)"
GROUP_ITIS = ["ITI(liquidity)", "ITI(return)", "ITI(volatility)", "ITI(volume)"]


def winsorize_frame(df, columns, lo=0.0005, hi=0.9995):
    """Pooled winsorization at 0.05% / 99.95%, as in the paper's tables."""
    df = df.copy()
    bounds = df[columns].quantile([lo, hi])
    df[columns] = df[columns].clip(bounds.loc[lo], bounds.loc[hi], axis=1)
    return df


def stack(results):
    """Long table: one row per (column, variable), plus Obs. and within R2."""
    rows = []
    for col, (tab, stats) in results.items():
        for var, r in tab.iterrows():
            rows.append({"column": col, "variable": var, "coef": r.coef, "t": r.t})
        rows.append({"column": col, "variable": "Obs.", "coef": stats["nobs"], "t": np.nan})
        rows.append({"column": col, "variable": "R2 (within)", "coef": stats["r2_within"], "t": np.nan})
    return pd.DataFrame(rows)


def filing_regression(df, y, xs):
    """Paper specification for Tables 2-4: filing FE, SE clustered by filing."""
    return fe_ols(df, y, xs, fe="filing", cluster=("filing",))


# ---------------------------------------------------------------- inputs

def load_13d_sample():
    """Held-out filing-days with ITI(13D), labels, and winsorized controls."""
    require(LABELS, ML / "oof_predictions.parquet", ML / "raw_features.parquet")
    from replicate_iti_figures import figure1_controls, heldout_predictions

    predictions = heldout_predictions()
    labels = pd.read_parquet(LABELS, columns=["filing", "permno", "date", "turn", "13Dturn"])
    controls = figure1_controls(predictions)
    return assemble_13d_sample(predictions, labels, controls)


def assemble_13d_sample(predictions, labels, controls):
    """Join predictions, labels and controls; winsorize controls. Pure, for tests."""
    labels = labels.rename(columns={"turn": "turn_crsp"})
    d = predictions.merge(labels, on=["filing", "permno", "date"], how="left", validate="one_to_one")
    d = d.merge(controls, on=["permno", "date"], how="left", validate="many_to_one")
    d = d.rename(columns={SCORE: "ITI"})
    present = [c for c in CONTROLS if c in d]
    complete = d.dropna(subset=present)
    d.loc[complete.index, present] = winsorize_frame(complete, present)[present]
    return d


# ---------------------------------------------------------------- Table 1

def describe(series, groups=None):
    s = series.dropna()
    out = {"mean": s.mean(), "sd": s.std()}
    if groups is not None:
        g = groups.loc[s.index]
        out["sd_within"] = (s - s.groupby(g).transform("mean")).std()
    q = s.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    out.update({f"p{int(k * 100)}": v for k, v in q.items()})
    out["n"] = len(s)
    return out


def table1_frame(panel, labels):
    """Descriptive statistics in the layout of the paper's Table 1."""
    controls = [c for c in ["es", "depth", "rvol", "turn", "oi", "absoi", "ret"] if c in panel]
    p = winsorize_frame(panel, controls)
    rows = [{"variable": c, **describe(p[c], p.permno)} for c in [*controls, *ITI_NAMES] if c in p]
    rows.append({"variable": "13D trade (13D sample)", **describe(labels.itrade.astype(float), labels.filing)})
    return pd.DataFrame(rows)


def require(*paths):
    missing = [str(p) for p in paths if not Path(p).exists()]
    if missing:
        raise SystemExit("Missing input(s): " + ", ".join(missing)
                         + ". Link the shared _data/ folder and run `doit panel` / `doit 13d_labels` first.")


def table1():
    require(PANEL, LABELS)
    cols = ["permno", "date", "eligible", "es", "depth", "rvol", "turn", "oi", "absoi", "ret", *ITI_NAMES]
    panel = pd.read_parquet(PANEL, columns=cols)
    panel = panel[panel.eligible & panel.date.between(SAMPLE_START, SAMPLE_END)]
    labels = pd.read_parquet(LABELS, columns=["filing", "permno", "date", "itrade", "in_paper_period"])
    # Like the paper, the full sample excludes the 13D training stock-days.
    window = labels[["permno", "date"]].drop_duplicates().assign(in_13d=True)
    panel = panel.merge(window, on=["permno", "date"], how="left")
    panel = panel[panel.in_13d.isna()].drop(columns="in_13d")
    out = table1_frame(panel, labels[labels.in_paper_period.fillna(False)])
    out.to_csv(OUT / "table1.csv", index=False)
    return out


# ---------------------------------------------------------------- Table 2

def table2_frame(d):
    full = d.dropna(subset=["ITI", "itrade", *CONTROLS])
    trades = full[full.itrade == 1].dropna(subset=["13Dturn"])
    specs = {
        1: (full, "itrade", ["ITI"]),
        2: (full, "itrade", CONTROLS),
        3: (full, "itrade", ["ITI", *CONTROLS]),
        4: (trades, "13Dturn", ["ITI"]),
        5: (trades, "13Dturn", CONTROLS),
        6: (trades, "13Dturn", ["ITI", *CONTROLS]),
    }
    return stack({c: filing_regression(df, y, x) for c, (df, y, x) in specs.items()})


def table2():
    out = table2_frame(load_13d_sample())
    out.to_csv(OUT / "table2.csv", index=False)
    return out


# ---------------------------------------------------------------- Table 3

def table3_frame(d):
    full = d.dropna(subset=["ITI", "itrade", *GROUP_ITIS])
    specs = {1: ["ITI"], **{i + 2: [g] for i, g in enumerate(GROUP_ITIS)}, 6: GROUP_ITIS}
    return stack({c: filing_regression(full, "itrade", x) for c, x in specs.items()})


def table3():
    path = ML / "group_oof_predictions.parquet"
    if not path.exists():
        raise SystemExit(f"Missing {path}: run `doit iti_train_groups` first (four extra model fits).")
    groups = pd.read_parquet(path, columns=["filing", "permno", "date", *GROUP_ITIS])
    from replicate_iti_figures import heldout_predictions

    d = heldout_predictions().rename(columns={SCORE: "ITI"}).merge(
        groups, on=["filing", "permno", "date"], how="left", validate="one_to_one")
    out = table3_frame(d)
    out.to_csv(OUT / "table3.csv", index=False)
    return out


# ---------------------------------------------------------------- Table 4

def match_on_turnover(d, turn="turn_crsp", gap=TABLE4_TURN_GAP):
    """Within each filing, pair each trade day with the closest-turnover
    non-trade day (without replacement); keep pairs at most `gap` apart.

    Greedy on the smallest gaps first, so the best pairs are formed first.
    Returns the matched rows with a `pair` id.
    """
    d = d.dropna(subset=[turn])
    pairs = []
    for filing, g in d.groupby("filing"):
        treated = g[g.itrade == 1]
        control = g[g.itrade == 0]
        if treated.empty or control.empty:
            continue
        dist = np.abs(treated[turn].to_numpy()[:, None] - control[turn].to_numpy()[None, :])
        candidates = np.argwhere(dist <= gap)
        order = np.argsort(dist[candidates[:, 0], candidates[:, 1]], kind="stable")
        used_t, used_c = set(), set()
        for i, j in candidates[order]:
            if i in used_t or j in used_c:
                continue
            used_t.add(i)
            used_c.add(j)
            pairs.append((treated.index[i], control.index[j]))
    rows = [idx for pair in pairs for idx in pair]
    matched = d.loc[rows].copy()
    matched["pair"] = np.repeat(np.arange(len(pairs)), 2)
    return matched


def table4_frame(d):
    m = match_on_turnover(d.dropna(subset=["ITI", "itrade"]))
    panel_a = {
        "a: turnover": filing_regression(m, "turn_crsp", ["itrade"]),
        "a: ITI": filing_regression(m, "ITI", ["itrade"]),
    }
    controls = [c for c in CONTROLS if c not in ("turn",)]
    full = m.dropna(subset=controls)
    panel_b = {
        "b1": filing_regression(m, "itrade", ["ITI"]),
        "b2": filing_regression(full, "itrade", controls),
        "b3": filing_regression(full, "itrade", ["ITI", *controls]),
    }
    return stack({**panel_a, **panel_b})


def table4():
    out = table4_frame(load_13d_sample())
    out.to_csv(OUT / "table4.csv", index=False)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:] or ["table1", "table2", "table3", "table4"]
    for name in wanted:
        print("Running", name, flush=True)
        globals()[name]()


if __name__ == "__main__":
    main()
