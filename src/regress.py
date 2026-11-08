"""Panel OLS with one absorbed fixed effect and one- or two-way clustered errors.

Matches the paper's specifications: one fixed effect (date, week or stock) and
standard errors clustered by one or two dimensions (Cameron-Gelbach-Miller
two-way: V_a + V_b - V_ab, with V_ab clustered on the intersection).
"""

import numpy as np
import pandas as pd


def _meat(scores, groups):
    codes, _ = pd.factorize(groups)
    summed = pd.DataFrame(scores).groupby(codes).sum().to_numpy()
    n_groups = len(summed)
    return summed.T @ summed * n_groups / (n_groups - 1), n_groups


def fe_ols(df, y, xs, fe=None, cluster=()):
    """Return a coefficient table and fit statistics.

    df: DataFrame; y: column name; xs: regressor names; fe: column absorbed by
    within-group demeaning; cluster: one or two column names.
    """
    cols = [y, *xs, *([fe] if fe else []), *cluster]
    data = df[list(dict.fromkeys(cols))].dropna()
    Y = data[y].to_numpy(float)
    X = data[list(xs)].to_numpy(float)
    if fe:
        keys = data[fe]
        Y = Y - pd.Series(Y).groupby(keys.to_numpy()).transform("mean").to_numpy()
        Xd = pd.DataFrame(X).groupby(keys.to_numpy()).transform("mean").to_numpy()
        X = X - Xd
    else:
        X = np.column_stack([np.ones(len(X)), X])
        xs = ["const", *xs]
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ Y
    resid = Y - X @ beta
    scores = X * resid[:, None]
    if len(cluster) == 0:
        meat = scores.T @ scores
    elif len(cluster) == 1:
        meat, _ = _meat(scores, data[cluster[0]].to_numpy())
    else:
        a, b = (data[c].to_numpy() for c in cluster)
        meat_a, _ = _meat(scores, a)
        meat_b, _ = _meat(scores, b)
        both = pd.MultiIndex.from_arrays([a, b])
        meat_ab, _ = _meat(scores, both)
        meat = meat_a + meat_b - meat_ab
    vcov = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.diag(vcov))
    r2 = 1 - resid @ resid / ((Y - Y.mean()) @ (Y - Y.mean()))
    table = pd.DataFrame({"coef": beta, "se": se, "t": beta / se}, index=list(xs))
    return table, {"nobs": len(Y), "r2_within": r2}


def newey_west_mean(series, lags=8, factors=None):
    """Mean (or intercept on factors) with Newey-West standard error."""
    yv = np.asarray(series, float)
    if factors is None:
        X = np.ones((len(yv), 1))
    else:
        X = np.column_stack([np.ones(len(yv)), np.asarray(factors, float)])
    keep = ~np.isnan(yv) & ~np.isnan(X).any(axis=1)
    yv, X = yv[keep], X[keep]
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ yv
    u = X * (yv - X @ beta)[:, None]
    S = u.T @ u
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        g = u[lag:].T @ u[:-lag]
        S += w * (g + g.T)
    se = np.sqrt(np.diag(xtx_inv @ S @ xtx_inv))
    return beta[0], beta[0] / se[0]


def fe_ols_chunked(df, y, xs, fe, cluster2, n_chunks=25):
    """fe_ols with the fixed effect also as the first cluster, two-way clustered by
    (fe, cluster2), computed in chunks of fe groups to bound memory."""
    data = df[list(dict.fromkeys([y, *xs, fe, cluster2]))].dropna().sort_values(fe)
    codes2, uniq2 = pd.factorize(data[cluster2])
    g = data[fe].to_numpy()
    starts = np.flatnonzero(np.r_[True, g[1:] != g[:-1]])
    cuts = starts[np.linspace(0, len(starts), n_chunks + 1, dtype=int)[1:-1]]
    bounds = list(zip(np.r_[0, cuts], np.r_[cuts, len(data)]))
    k = len(xs)

    def chunk(lo, hi):
        part = data.iloc[lo:hi]
        keys = part[fe].to_numpy()
        X = part[list(xs)].to_numpy(float)
        Y = part[y].to_numpy(float)
        X = X - pd.DataFrame(X).groupby(keys).transform("mean").to_numpy()
        Y = Y - pd.Series(Y).groupby(keys).transform("mean").to_numpy()
        return keys, X, Y

    xtx, xty, yy = np.zeros((k, k)), np.zeros(k), 0.0
    for lo, hi in bounds:
        _, X, Y = chunk(lo, hi)
        xtx += X.T @ X
        xty += X.T @ Y
        yy += Y @ Y
    xtx_inv = np.linalg.inv(xtx)
    beta = xtx_inv @ xty
    meat_a, meat_obs = np.zeros((k, k)), np.zeros((k, k))
    sums_b = np.zeros((len(uniq2), k))
    n_a, sse = 0, 0.0
    for lo, hi in bounds:
        keys, X, Y = chunk(lo, hi)
        u = Y - X @ beta
        sse += u @ u
        s = X * u[:, None]
        sa = pd.DataFrame(s).groupby(keys).sum().to_numpy()
        n_a += len(sa)
        meat_a += sa.T @ sa
        sb = pd.DataFrame(s).groupby(codes2[lo:hi]).sum()
        sums_b[sb.index.to_numpy()] += sb.to_numpy()
        meat_obs += s.T @ s
    n_b = len(uniq2)
    meat = (meat_a * n_a / (n_a - 1) + sums_b.T @ sums_b * n_b / (n_b - 1) - meat_obs)
    se = np.sqrt(np.diag(xtx_inv @ meat @ xtx_inv))
    table = pd.DataFrame({"coef": beta, "se": se, "t": beta / se}, index=list(xs))
    return table, {"nobs": len(data), "r2_within": 1 - sse / yy}
