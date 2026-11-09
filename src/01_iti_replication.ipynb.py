# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # ITI replication: what our data supports
#
# Bogousslavsky, Fos and Muravyev (2024), *Informed Trading Intensity*, JF 79(2).
#
# **Sample:** 2005–7/2019 (the paper uses 1993–7/2019). ITI values are the authors'
# posted file (original vintage); we have not trained our own model. Every number
# below is read from files built by:
#
# | Step | Command | Output |
# |---|---|---|
# | 13D trade-day labels | `doit 13d_validation` | `_data/derived/13d/`, `_output/13d_label_validation.md` |
# | Stock panels | `doit panel` | `_data/derived/panel/{daily,weekly}.parquet` |
# | Exhibits | `doit replication` | `_output/replication/` |

# %%
from pathlib import Path

import pandas as pd
from IPython.display import Image, Markdown, display

import paper_values as pv
from validate_13d_labels import PAPER, label_stats

ROOT = Path("..")
REP = ROOT / "_output" / "replication"
D13 = ROOT / "_data" / "derived" / "13d"
pd.set_option("display.float_format", "{:,.4f}".format)

# %% [markdown]
# ## 1. Schedule 13D labels (rebuilt from SEC filing text)
#
# The authors' label file is not public, so we rebuild it from 27,622 original SC 13D
# filings. Screens follow paper footnote 5; the funnel shows the first failed screen.

# %%
events = pd.read_parquet(D13 / "events.parquet")
labels = pd.read_parquet(D13 / "labels_daily.parquet")
funnel = events.exclusion_reason.fillna("included").value_counts().rename("filings").to_frame()
funnel

# %%
paper_period = labels[labels.in_paper_period]
ours = label_stats(paper_period)
authors = label_stats(paper_period[paper_period.in_authors_sample.fillna(False)])
compare_13d = pd.DataFrame({
    "ours (2005-2018)": ours,
    "ours, authors' events": authors,
    "paper": {k: v[0] for k, v in PAPER.items()},
    "source": {k: v[1] for k, v in PAPER.items()},
}).drop(index=["filer_shares_gt_crsp_vol"])
compare_13d

# %% [markdown]
# Trade-day frequency matches the paper (0.36). The filer's share of daily volume is
# about half the paper's, and sales are a larger share of trade days; both are open
# items. Abnormal return around the filing (paper Figure IA.1):

# %%
Image(ROOT / "_output" / "13d_filing_car.png", width=650)

# %% [markdown]
# ## 2. Table 10: weekly ITI predicts next-month returns
#
# Stock-week panel; return over the next 21 trading days after skipping one day,
# delisting-adjusted (Shumway). Week fixed effects, errors clustered by stock and week.
# Price > \$5 and market cap > \$100M at the previous month end. Column 5 controls:
# log size, CAPM beta, last-month and 2–6 month returns, FF4 idiosyncratic volatility,
# Amihud illiquidity, effective spread (**Kyle's lambda omitted**: not computed).

# %%
def side_by_side(ours_long, paper, nobs_paper):
    rows = []
    for col, spec in paper.items():
        o = ours_long[ours_long.column.astype(str) == str(col)].set_index("variable")
        for var, (pc, pt) in spec.items():
            rows.append({"column": col, "variable": var, "paper coef": pc, "paper t": pt,
                         "ours coef": o.loc[var, "coef"], "ours t": o.loc[var, "t"]})
        rows.append({"column": col, "variable": "Obs.", "paper coef": nobs_paper,
                     "ours coef": o.loc["Obs.", "coef"]})
    return pd.DataFrame(rows).set_index(["column", "variable"])


t10 = pd.read_csv(REP / "table10.csv")
side_by_side(t10, pv.TABLE10, pv.TABLE10_NOBS)

# %%
t10[(t10.column == 5) & ~t10.variable.str.startswith("ITI")].set_index("variable")[["coef", "t"]]

# %% [markdown]
# Signs match for ITI(13D), ITI(impatient) and ITI(short); ITI(impatient) beats
# ITI(patient) as in the paper. Coefficients are roughly 40% of the paper's and
# t-statistics about half, consistent with weaker return predictability after 2005.
# ITI(insider) is weak here.
#
# ## 3. Table 11: decile portfolios on prior-week ITI
#
# Equal-weighted, next-month return (same window as Table 10); weekly overlapping
# observations, Newey-West with 8 lags. Alphas from FF4 factors compounded over the
# same window.

# %%
t11 = pd.read_csv(REP / "table11.csv")
order = ["Low", "2", "3", "4", "5", "6", "7", "8", "9", "High", "H-L"]
alpha = t11.pivot(index="measure", columns="portfolio", values="alpha")[order]
paper_alpha = pd.DataFrame(pv.TABLE11_ALPHA, index=order).T
hl = t11[t11.portfolio == "H-L"].set_index("measure")[["raw", "raw_t", "alpha", "alpha_t"]]
hl["paper raw"] = pd.Series({k: v[-1] for k, v in pv.TABLE11_RAW.items()})
hl["paper raw t"] = pd.Series(pv.TABLE11_RAW_HL_T)
hl["paper alpha"] = pd.Series({k: v[-1] for k, v in pv.TABLE11_ALPHA.items()})
hl["paper alpha t"] = pd.Series(pv.TABLE11_ALPHA_HL_T)
hl

# %%
display(Markdown("**FF4 alphas by decile, ours**"))
display(alpha)
display(Markdown("**FF4 alphas by decile, paper**"))
paper_alpha

# %% [markdown]
# High-minus-low FF4 alphas are positive and significant for ITI(13D) and
# ITI(impatient), insignificant for ITI(short), as in the paper, but about a third
# of the paper's size. ITI(insider) and ITI(patient) are not significant here.
#
# ## 4. Table 5: return reversal is weaker on high-ITI days
#
# Daily ret(t+1) on ret(t), ITI(13D) and their interaction, date fixed effects,
# errors clustered by stock and date. Column 3 controls come from WRDS Intraday
# Indicators (effective spread, price impact, depth, intraday volatility, order
# imbalance) and CRSP turnover; **lambda omitted**. "2 (col 3 sample)" re-runs
# column 2 on the rows with all controls.

# %%
t5 = pd.read_csv(REP / "table5.csv")
side_by_side(t5, pv.TABLE5, pv.TABLE5_NOBS)

# %% [markdown]
# The key result replicates: ret×ITI(13D) is positive and significant (t ≈ 7 without
# controls, 4.5 with). Units of our spread and volatility controls differ from the
# paper's, so their interaction coefficients are not comparable in size.
#
# ## 5. Figure 4(a)–(b): ITI(13D) around earnings announcements
#
# Compustat `rdq` linked through CCM; day 0 is the higher-volume of the reported day
# and the next trading day. Stock fixed effects; errors clustered by stock and date;
# bars are 95% intervals. Panel (b) puts top, middle and bottom quartiles of
# |day-0 return| in one regression. Dashed lines are read off the paper's plots.

# %%
Image(REP / "figure4a.png", width=700)

# %%
Image(REP / "figure4b.png", width=700)

# %% [markdown]
# Same shape as the paper: ITI rises from day −2, spikes on day 0, decays over ten
# days, and the spike is larger for large-|r| announcements.
#
# ## 6. Figure IA.5: ITI(13D) around M&A announcements
#
# SDC completed acquisitions of US public targets (merger, acquisition, majority or
# remaining interest), linked by 6-digit CUSIP.

# %%
fia5 = pd.read_csv(REP / "figureIA5.csv")
display(Markdown(f"Events: {fia5.n_events.iloc[0]:,} (paper: {pv.FIGIA5_EVENTS:,}, 1996–2010)"))
Image(REP / "figureIA5.png", width=700)

# %% [markdown]
# The post-announcement jump replicates and is larger than the paper's; the paper's
# small pre-announcement run-up (days −5 to −1) does not appear in our sample.
#
# ## 7. Not replicated, and what is needed
#
# | Exhibit | Missing input |
# |---|---|
# | Our own ITI model; Tables 2–4, 7, 8; rest of Table 6 | TAQ-built daily features and controls (compute on WRDS, ~2–4 GB) |
# | Table 10 col 6 | Brown–Hillegeist annual PIN (authors' replication ZIP) |
# | Table 10 Panel B | ITI(insider buy/sell): not posted; needs our own model |
# | Lambda in Tables 5, 10 controls | Kyle's lambda from TAQ trades |
# | Figure 4(c), Table 6 cols 5–6 | BFKR news file (public; on teammate's `bfkr-news` branch, not merged) |
# | Table 6 col 7 | Ahern (2020) illegal insider trades |
# | Table 9 | BCL measure |
# | Insider-trained ITI from scratch | Insider trades before 2004 (routine vs opportunistic) |
# | Exact 13D sample | Authors' `sc13_1994_2018.dta` (not public) |
# | Full 1993–2019 period | All inputs for 1993–2004 (~30–40 GB) |
