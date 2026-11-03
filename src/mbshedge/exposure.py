"""Empirical rate exposure (empirical duration) of an MBS portfolio.

Definitions
-----------
Daily excess return r_t (decimal) and daily change in the 10-year yield dy_t (decimal,
so 1 bp = 0.0001). Within a calendar month m we fit

    r_t = a + b0 * dy_t + b1 * dy_{t-1} + e_t                         (Dimson lag)

and define the month's realized empirical duration as D_m = -(b0 + b1), in years.
A duration of 4 means the portfolio loses about 4 bp of value per 1 bp rise in the
10-year yield. The lag term (Dimson, 1979) absorbs a response that arrives a day late,
for example an ETF price that is slow to reflect its holdings. The timing of the two
closes works the other way: the 10-year yield is fixed around 3:30 pm ET and the ETF
closes at 4 pm, so a rate move in that half hour enters today's ETF return but
tomorrow's yield change. That lead is not captured here, which can understate duration
slightly. `lead_lag_diagnostic` measures it on development data (notebook 05). The
standard error comes from Newey-West with the HC3 leverage adjustment.

Empirical duration measures how returns co-move with yields. It contains prepayment
(option) effects, spread changes that co-move with rates, and index composition drift.
It is not an option-adjusted (effective) duration, and its changes are not a
structural price-yield derivative.

The updating hedge uses an exponentially weighted regression on all past days, with
weight 0.5 ** (age / half_life) on a day that is `age` trading days old.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import lfilter


# ----------------------------------------------------------------------------
# Regression with Newey-West (HAC) standard errors
# ----------------------------------------------------------------------------
def ols_hac(y: np.ndarray, X: np.ndarray, lags: int, small_sample: bool = True, leverage: bool = False) -> dict:
    """OLS coefficients with a Newey-West (Bartlett kernel) covariance matrix.

    Returns dict with beta, cov, resid, n, k, r2. `small_sample=True` multiplies the
    covariance by n/(n-k), the same correction statsmodels applies by default.
    `leverage=True` replaces each residual by e_i / (1 - h_ii) before forming the sandwich
    (the HC3 adjustment of MacKinnon and White, 1985) and drops the n/(n-k) factor. With
    about 21 daily observations a month, high-leverage days (large yield moves) have
    shrunken residuals, and the plain sandwich understates the sampling error (notebook 04).
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    XtX = X.T @ X
    XtX_inv = np.linalg.inv(XtX)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta
    if leverage:
        h = np.einsum("ij,jk,ik->i", X, XtX_inv, X)
        u = X * (resid / np.clip(1.0 - h, 1e-8, None))[:, None]
        small_sample = False
    else:
        u = X * resid[:, None]
    S = u.T @ u
    for lag in range(1, lags + 1):
        w = 1.0 - lag / (lags + 1.0)
        G = u[lag:].T @ u[:-lag]
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv
    if small_sample and n > k:
        cov *= n / (n - k)
    tss = ((y - y.mean()) ** 2).sum()
    r2 = 1.0 - (resid ** 2).sum() / tss if tss > 0 else np.nan
    return {"beta": beta, "cov": cov, "resid": resid, "n": n, "k": k, "r2": r2}


def duration_from_fit(fit: dict) -> tuple[float, float]:
    """D = -(b0 + b1) and its standard error, from a fit with columns [1, dy, dy_lag]."""
    c = np.array([0.0, -1.0, -1.0])
    d = float(c @ fit["beta"])
    se = float(np.sqrt(max(c @ fit["cov"] @ c, 0.0)))
    return d, se


# ----------------------------------------------------------------------------
# Monthly realized durations
# ----------------------------------------------------------------------------
def monthly_realized_durations(daily: pd.DataFrame, ret_col: str = "r_mbb_ex", dy_col: str = "dy10",
                               min_days: int = 15, nw_lags: int = 2, max_abs: float = 12.0,
                               leverage: bool = True) -> pd.DataFrame:
    """One realized empirical duration per calendar month.

    `daily` must be indexed by date (the project trading calendar) and contain the
    excess return and yield change columns. The lagged yield change for the first
    day of a month is the last change of the previous month (known at that time).

    Output columns: n_days, D, se, r2, valid, flag, month_end (last trading date in the
    month, which is also the time the estimate becomes available).
    """
    df = daily[[ret_col, dy_col]].copy()
    df["dy_lag"] = df[dy_col].shift(1)
    df = df.dropna()
    month = df.index.to_period("M")
    rows = []
    for m, g in df.groupby(month):
        n = len(g)
        rec = {"month": m, "month_end": g.index.max(), "n_days": n, "D": np.nan, "se": np.nan,
               "r2": np.nan, "valid": False, "flag": ""}
        if n < min_days:
            rec["flag"] = f"too few days ({n} < {min_days})"
            rows.append(rec)
            continue
        X = np.column_stack([np.ones(n), g[dy_col].to_numpy(), g["dy_lag"].to_numpy()])
        try:
            fit = ols_hac(g[ret_col].to_numpy(), X, nw_lags, leverage=leverage)
            d, se = duration_from_fit(fit)
        except np.linalg.LinAlgError:
            rec["flag"] = "singular design"
            rows.append(rec)
            continue
        rec.update({"D": d, "se": se, "r2": fit["r2"]})
        if not np.isfinite(d) or not np.isfinite(se) or se <= 0:
            rec["flag"] = "non-finite estimate"
        elif abs(d) > max_abs:
            rec["flag"] = f"|D| > {max_abs} years"
        else:
            rec["valid"] = True
        rows.append(rec)
    out = pd.DataFrame(rows).set_index("month")
    out.index.name = "month"
    return out


def lead_lag_diagnostic(daily: pd.DataFrame, first_month: str, last_month: str, ret_col: str = "r_mbb_ex",
                        dy_col: str = "dy10", min_days: int = 15, nw_lags: int = 2) -> dict:
    """Timing check: month by month, fit r_t = a + b_lead dy_{t+1} + b0 dy_t + b1 dy_{t-1}.

    A rate move between the yield fix (about 3:30 pm) and the ETF close (4 pm) shows up as
    b_lead < 0. The function reports, across the valid months in [first_month, last_month],
    the mean lead and lag effects in years of duration with cross-month standard errors, and
    how much the duration changes when the lead is added. The lead uses the next trading
    day's yield change, so this is an after-the-fact measurement, not something a hedger
    could compute at the close."""
    df = daily[[ret_col, dy_col]].copy()
    df["dy_lag"] = df[dy_col].shift(1)
    df["dy_lead"] = df[dy_col].shift(-1)
    df = df.dropna().loc[str(first_month):str(last_month)]
    rows = []
    for m, g in df.groupby(df.index.to_period("M")):
        if len(g) < min_days:
            continue
        y = g[ret_col].to_numpy()
        X2 = np.column_stack([np.ones(len(g)), g[dy_col], g["dy_lag"]])
        X3 = np.column_stack([np.ones(len(g)), g["dy_lead"], g[dy_col], g["dy_lag"]])
        try:
            f2 = ols_hac(y, X2, nw_lags, leverage=True)
            f3 = ols_hac(y, X3, nw_lags, leverage=True)
        except np.linalg.LinAlgError:
            continue
        b = f3["beta"]
        rows.append({"month": m, "n_days": len(g), "D_lag_only": -(f2["beta"][1] + f2["beta"][2]),
                     "lead_years": -b[1], "same_day_years": -b[2], "lag_years": -b[3],
                     "D_with_lead": -(b[1] + b[2] + b[3])})
    tab = pd.DataFrame(rows).set_index("month") if rows else pd.DataFrame()
    if tab.empty:
        return {"months": 0, "table": tab}

    def mean_se(x):
        x = x[np.isfinite(x)]
        return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else np.nan

    lead, lead_se = mean_se(tab["lead_years"].to_numpy())
    lag, lag_se = mean_se(tab["lag_years"].to_numpy())
    diff, diff_se = mean_se((tab["D_with_lead"] - tab["D_lag_only"]).to_numpy())
    base = float(tab["D_lag_only"].mean())
    return {"months": int(len(tab)), "mean_lead_years": lead, "mean_lead_se": lead_se,
            "mean_lag_years": lag, "mean_lag_se": lag_se, "mean_duration_lag_only": base,
            "mean_change_when_lead_added": diff, "mean_change_se": diff_se,
            "change_share_of_duration": diff / base if base else np.nan, "table": tab}


# ----------------------------------------------------------------------------
# Exponentially weighted (updating) duration via exact recursive sums
# ----------------------------------------------------------------------------
def _ewsum(x: np.ndarray, lam: float) -> np.ndarray:
    """s_t = x_t + lam * s_{t-1}: exponentially weighted sum over all past observations."""
    return lfilter([1.0], [1.0, -lam], x)


def ewma_duration(daily: pd.DataFrame, halflife_days: float, ret_col: str = "r_mbb_ex",
                  dy_col: str = "dy10", state_col: str | None = "g", min_effective_days: float = 10.0
                  ) -> pd.DataFrame:
    """Exponentially weighted regression duration at every date.

    Weight on a day `a` trading days before date t is 0.5 ** (a / halflife_days).
    Uses only data up to and including t. Returns columns:
      U      : -(b0 + b1) from the weighted regression r = a + b0 dy + b1 dy_lag
      gbar   : the state variable averaged with weights w * dy^2 (the information weights
               the regression puts on each day), used by the hybrid model
      n_eff  : effective number of observations (sum w)^2 / sum w^2
    """
    df = daily[[ret_col, dy_col] + ([state_col] if state_col else [])].copy()
    df["dy_lag"] = df[dy_col].shift(1)
    ok = df[[ret_col, dy_col, "dy_lag"]].notna().all(axis=1).to_numpy()
    lam = 0.5 ** (1.0 / halflife_days)
    w = ok.astype(float)
    r = np.where(ok, df[ret_col].to_numpy(), 0.0)
    x1 = np.where(ok, df[dy_col].to_numpy(), 0.0)
    x2 = np.where(ok, df["dy_lag"].to_numpy(), 0.0)
    S = {}
    terms = {
        "1": w, "x1": x1, "x2": x2, "y": r,
        "x1x1": x1 * x1, "x2x2": x2 * x2, "x1x2": x1 * x2,
        "x1y": x1 * r, "x2y": x2 * r, "w2": w,
    }
    for key, val in terms.items():
        S[key] = _ewsum(val, lam if key != "w2" else lam ** 2)
    n = len(df)
    U = np.full(n, np.nan)
    A = np.empty((n, 3, 3))
    A[:, 0, 0], A[:, 0, 1], A[:, 0, 2] = S["1"], S["x1"], S["x2"]
    A[:, 1, 0], A[:, 1, 1], A[:, 1, 2] = S["x1"], S["x1x1"], S["x1x2"]
    A[:, 2, 0], A[:, 2, 1], A[:, 2, 2] = S["x2"], S["x1x2"], S["x2x2"]
    b = np.stack([S["y"], S["x1y"], S["x2y"]], axis=1)
    usable = np.where(np.cumsum(ok) >= 5)[0]
    if len(usable):
        idx = usable
        try:
            beta = np.linalg.solve(A[idx], b[idx][..., None])[..., 0]
            U[idx] = -(beta[:, 1] + beta[:, 2])
        except np.linalg.LinAlgError:
            for t in idx:
                try:
                    bt = np.linalg.solve(A[t], b[t])
                    U[t] = -(bt[1] + bt[2])
                except np.linalg.LinAlgError:
                    continue
    n_eff = S["1"] ** 2 / np.maximum(S["w2"], 1e-300)
    out = pd.DataFrame({"U": U, "n_eff": n_eff}, index=df.index)
    out.loc[out["n_eff"] < min_effective_days, "U"] = np.nan
    if state_col:
        gvals = df[state_col].to_numpy()
        okg = ok & np.isfinite(gvals)
        wdy2 = np.where(okg, x1 * x1, 0.0)
        num = _ewsum(wdy2 * np.where(okg, gvals, 0.0), lam)
        den = _ewsum(wdy2, lam)
        out["gbar"] = np.where(den > 0, num / np.maximum(den, 1e-300), np.nan)
    return out


# ----------------------------------------------------------------------------
# Variation beyond noise: Cochran's Q and DerSimonian-Laird tau
# ----------------------------------------------------------------------------
def cochran_q(estimates: np.ndarray, std_errors: np.ndarray) -> dict:
    """Test whether estimates with known standard errors share one common value.

    Q = sum w_i (x_i - xbar_w)^2 with w_i = 1/se_i^2 is compared with chi^2(k-1).
    tau is the DerSimonian-Laird estimate of the standard deviation of the true values
    (in the units of the estimates, here years of duration).
    """
    x = np.asarray(estimates, dtype=float)
    se = np.asarray(std_errors, dtype=float)
    keep = np.isfinite(x) & np.isfinite(se) & (se > 0)
    x, se = x[keep], se[keep]
    k = len(x)
    w = 1.0 / se ** 2
    xbar = (w * x).sum() / w.sum()
    Q = float((w * (x - xbar) ** 2).sum())
    df = k - 1
    p = float(stats.chi2.sf(Q, df)) if df > 0 else np.nan
    c = w.sum() - (w ** 2).sum() / w.sum()
    tau2 = max(0.0, (Q - df) / c) if c > 0 else np.nan
    i2 = max(0.0, (Q - df) / Q) if Q > 0 else 0.0
    return {"k": k, "weighted_mean": float(xbar), "Q": Q, "df": df, "p_value": p,
            "tau": float(np.sqrt(tau2)), "tau2": float(tau2), "I2": float(i2),
            "median_se": float(np.median(se)), "sd_estimates": float(np.std(x, ddof=1)) if k > 1 else np.nan}


def null_bootstrap_variation(daily: pd.DataFrame, first_month: str, last_month: str, reps: int, seed: int,
                             ret_col: str = "r_mbb_ex", dy_col: str = "dy10", nw_lags: int = 2,
                             min_days: int = 15, block_days: int = 5, max_abs: float = 12.0) -> dict:
    """Constant-duration residual bootstrap for the variation test (Q1).

    Under the null, every month shares one duration. We fit the pooled regression
    r = a + b0 dy + b1 dy_lag over the window, then rebuild each month's returns from the
    pooled fit plus residuals resampled within that same month in circular blocks of
    `block_days` (keeping each month's own noise level and some serial dependence), and
    re-estimate every monthly duration and its standard error with the same estimator.

    Returns the observed Cochran Q, its bootstrap p-value (share of null draws with Q* >= Q),
    the naive chi-square p-value for reference, and a robust estimate of the true
    between-month standard deviation: tau_robust^2 = Var(observed D) - mean Var(D*) under the null.
    """
    df = daily[[ret_col, dy_col]].copy()
    df["dy_lag"] = df[dy_col].shift(1)
    df = df.dropna()
    lo, hi = pd.Period(first_month, "M"), pd.Period(last_month, "M")
    per = df.index.to_period("M")
    df = df[(per >= lo) & (per <= hi)]
    per = df.index.to_period("M")
    counts = per.value_counts()
    keep_m = counts[counts >= min_days].index
    df = df[per.isin(keep_m)]
    per = df.index.to_period("M")
    X = np.column_stack([np.ones(len(df)), df[dy_col].to_numpy(), df["dy_lag"].to_numpy()])
    y = df[ret_col].to_numpy()
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    fitted = X @ beta
    groups = [np.where(per == m)[0] for m in sorted(set(per))]

    def estimates(yy):
        D, S = [], []
        for idx in groups:
            fit = ols_hac(yy[idx], X[idx], nw_lags, leverage=True)
            d, s = duration_from_fit(fit)
            D.append(d)
            S.append(s)
        D, S = np.array(D), np.array(S)
        ok = np.isfinite(D) & np.isfinite(S) & (S > 0) & (np.abs(D) <= max_abs)
        return D[ok], S[ok]

    D_obs, S_obs = estimates(y)
    q_obs = cochran_q(D_obs, S_obs)
    rng = np.random.default_rng(seed)
    q_star, var_star, tau_star = np.empty(reps), np.empty(reps), np.empty(reps)
    for r in range(reps):
        e_star = np.empty_like(resid)
        for idx in groups:
            n = len(idx)
            starts = rng.integers(0, n, int(np.ceil(n / block_days)))
            take = (starts[:, None] + np.arange(block_days)[None, :]).ravel()[:n] % n
            e_star[idx] = resid[idx][take]
        Ds, Ss = estimates(fitted + e_star)
        qs = cochran_q(Ds, Ss)
        q_star[r], tau_star[r], var_star[r] = qs["Q"], qs["tau"], np.var(Ds, ddof=1)
    var_obs = float(np.var(D_obs, ddof=1))
    tau2_robust = max(0.0, var_obs - float(var_star.mean()))
    return {
        "months": int(len(D_obs)), "pooled_duration": float(-(beta[1] + beta[2])),
        "Q": q_obs["Q"], "df": q_obs["df"], "p_chi2_naive": q_obs["p_value"],
        "p_bootstrap": float(max((q_star >= q_obs["Q"]).mean(), 1.0 / reps)),
        "tau_dl_naive": q_obs["tau"], "tau_null_95pct": float(np.quantile(tau_star, 0.95)),
        "sd_observed": float(np.sqrt(var_obs)), "sd_noise_under_null": float(np.sqrt(var_star.mean())),
        "tau_robust": float(np.sqrt(tau2_robust)), "reps": reps, "block_days": block_days,
    }


# ----------------------------------------------------------------------------
# Comparing two funds' exposures (descriptive, notebook 09)
# ----------------------------------------------------------------------------
def compare_exposure(mon_x: pd.DataFrame, mon_ref: pd.DataFrame, first_month, last_month, hac_lags: int,
                     min_months: int = 12) -> dict:
    """Compare a fund's monthly realized durations with a reference fund's (descriptive).

    `mon_x` and `mon_ref` are monthly panels from `pipeline.monthly_panel` (columns D, valid,
    and g in the reference panel). The refinancing share is taken at the start of each month,
    g at the previous month-end, which is what an investor knew when setting that month's hedge
    (the same pairing the economic model uses). Months count only when both durations are valid.

    Reported, with Newey-West standard errors (`hac_lags` months):
      - the correlation of the two monthly durations,
      - the mean difference (fund minus reference), in years,
      - each fund's slope on g: the change in duration, in years, from no borrowers in the money
        (g = 0) to all of them (g = 1),
      - the slope of the difference. A negative value means the fund's duration falls by more
        than the reference's when more borrowers can refinance.
    """
    ref = mon_ref[["D", "valid", "g"]].copy()
    ref["g_start"] = ref["g"].shift(1)
    m = mon_x[["D", "valid"]].join(ref[["D", "valid", "g_start"]], lsuffix="_x", rsuffix="_ref", how="inner")
    m = m.loc[pd.Period(str(first_month), "M"):pd.Period(str(last_month), "M")]
    m = m[m["valid_x"].astype(bool) & m["valid_ref"].astype(bool) & m["g_start"].notna()
          & m["D_x"].notna() & m["D_ref"].notna()]
    out = {"months": int(len(m)), "first_month": str(m.index.min()) if len(m) else None,
           "last_month": str(m.index.max()) if len(m) else None}
    if len(m) < min_months:
        out["status"] = f"too few common months ({len(m)} < {min_months})"
        return out
    g = m["g_start"].to_numpy(dtype=float)
    X1 = np.ones((len(m), 1))
    Xg = np.column_stack([np.ones(len(m)), g])

    def slope(y):
        fit = ols_hac(np.asarray(y, dtype=float), Xg, hac_lags)
        return float(fit["beta"][1]), float(np.sqrt(max(fit["cov"][1, 1], 0.0)))

    diff = (m["D_x"] - m["D_ref"]).to_numpy(dtype=float)
    fit_mean = ols_hac(diff, X1, hac_lags)
    sx, sx_se = slope(m["D_x"])
    sr, sr_se = slope(m["D_ref"])
    sd, sd_se = slope(diff)
    fit_diff = ols_hac(diff, Xg, hac_lags)
    z = float(stats.norm.ppf(0.975))
    out.update({
        "status": "ok",
        "corr": float(np.corrcoef(m["D_x"], m["D_ref"])[0, 1]),
        "mean_x_years": float(m["D_x"].mean()), "mean_ref_years": float(m["D_ref"].mean()),
        "mean_diff_years": float(fit_mean["beta"][0]), "mean_diff_se_years": float(np.sqrt(max(fit_mean["cov"][0, 0], 0.0))),
        "slope_x_years": sx, "slope_x_se": sx_se, "slope_ref_years": sr, "slope_ref_se": sr_se,
        "slope_diff_years": sd, "slope_diff_se": sd_se, "intercept_diff_years": float(fit_diff["beta"][0]),
        "slope_diff_ci_low": sd - z * sd_se, "slope_diff_ci_high": sd + z * sd_se,
        "g_start_min": float(g.min()), "g_start_max": float(g.max()), "hac_lags": int(hac_lags),
    })
    return out
