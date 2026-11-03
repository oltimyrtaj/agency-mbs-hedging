"""Forecasts of next month's empirical duration, made walk-forward.

At the close of the last trading day of month m (the decision date) every model forecasts
the realized duration of month m+1 using only information available at that close.

Models
------
S   Static: the average realized duration over the development period, frozen.
U   Updating: the exponentially weighted regression duration at the decision date
    (half-life chosen on development data).
P   Persistence: last month's realized duration.
AR  AR(1) on monthly realized durations, refitted on an expanding window.
E   Economic state: D(m+1) = c0 + c1 * g(m), weighted least squares on an expanding
    window, where g is the share of borrowers in the money. The fitted c0 is the
    "locked-in" duration and c0 + c1 the "everyone in the money" duration.
H   Hybrid: U + c1 * (g(m) - gbar(m)), where gbar is g averaged with the same weights
    the updating regression puts on each day. U is an average of recent durations, so
    H adds the duration change that refinancing conditions imply since that average was
    formed. If c1 = 0, H equals U.
X   Ex-post diagnostic (infeasible): next month's realized duration itself.

Training pairs for a decision at month m are (information at month k, realized duration
of month k+1) with k + 1 <= m, so the target of every training pair is already observed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MODEL_LABELS = {
    "UNH": "Unhedged",
    "S": "Static",
    "U": "Updating (EWMA)",
    "P": "Persistence",
    "AR": "AR(1)",
    "E": "Economic state",
    "H": "Hybrid (updating + refinancing)",
    "X": "Ex-post diagnostic (infeasible)",
}


def static_duration(monthly: pd.DataFrame, first_month: str, last_month: str) -> float:
    sel = monthly.loc[pd.Period(first_month, "M"):pd.Period(last_month, "M")]
    vals = sel.loc[sel["valid"], "D"]
    if len(vals) < 12:
        raise ValueError("Fewer than 12 valid development months for the static hedge")
    return float(vals.mean())


def _wls(x: np.ndarray, y: np.ndarray, se: np.ndarray) -> tuple[float, float, float]:
    """Two-step feasible WLS for y = c0 + c1 x with known measurement variances se^2.
    Step 1 OLS gives the residual variance; tau^2 = max(0, mean(resid^2) - mean(se^2)) is the
    variance not explained by measurement noise. Step 2 weights each month by 1/(se^2 + tau^2)."""
    X = np.column_stack([np.ones_like(x), x])
    b_ols = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ b_ols
    tau2 = max(0.0, float(np.mean(resid ** 2) - np.mean(se ** 2)))
    w = 1.0 / (se ** 2 + tau2 + 1e-12)
    sw = np.sqrt(w)
    b = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
    return float(b[0]), float(b[1]), tau2


def walk_forward(monthly: pd.DataFrame, *, first_decision: str, last_decision: str, static_d: float,
                 u_col: str, gbar_col: str, g_col: str = "g", models: list[str] | None = None,
                 min_pairs: int = 24, e_train_mask_col: str | None = None,
                 fallback_before_fit: bool = False) -> pd.DataFrame:
    """Run every model at every decision month in [first_decision, last_decision].

    `monthly` (index: Period month) needs columns D, se, valid, decision_date, incentive_source,
    plus u_col, gbar_col, g_col. `e_train_mask_col` (optional boolean column) restricts which
    months k may enter the economic model's training pairs.

    `fallback_before_fit=True` (used only by the NMDB-only robustness run) lets the economic
    model use the static duration, and the hybrid the updating estimate, at decisions where
    the state model has fewer than `min_pairs` training pairs. Such rows are flagged in the
    `fallback` column. In the main runs this is off, so a state model that cannot be fitted
    leaves a gap that stops the backtest instead of passing silently.
    """
    models = models or ["S", "U", "P", "AR", "E", "H", "X"]
    mo = monthly.sort_index()
    months = list(mo.index)
    pos = {m: i for i, m in enumerate(months)}
    fd, ld = pd.Period(first_decision, "M"), pd.Period(last_decision, "M")
    D = mo["D"].to_numpy()
    se = mo["se"].to_numpy()
    valid = mo["valid"].to_numpy().astype(bool)
    g = mo[g_col].to_numpy()
    U = mo[u_col].to_numpy()
    gbar = mo[gbar_col].to_numpy()
    mask = mo[e_train_mask_col].to_numpy().astype(bool) if e_train_mask_col else np.ones(len(mo), bool)
    rows = []
    for m in months:
        if m < fd or m > ld:
            continue
        i = pos[m]
        target = m + 1
        rec_base = {"decision_month": m, "target_month": target,
                    "decision_date": mo["decision_date"].iloc[i],
                    "available_at": mo["decision_date"].iloc[i],
                    "training_cutoff_month": m,
                    "incentive_source": mo["incentive_source"].iloc[i]}
        # training pairs (k, k+1) with k+1 <= m
        k = np.arange(0, i)
        k_next = k + 1
        ok_ar = valid[k] & valid[k_next] & (k_next <= i)
        ok_e = np.isfinite(g[k]) & valid[k_next] & mask[k]
        c0 = c1 = a = rho = np.nan
        tau2 = np.nan
        n_e = int(ok_e.sum())
        if n_e >= min_pairs:
            c0, c1, tau2 = _wls(g[k][ok_e], D[k_next][ok_e], se[k_next][ok_e])
        n_ar = int(ok_ar.sum())
        if n_ar >= min_pairs:
            Xa = np.column_stack([np.ones(n_ar), D[k][ok_ar]])
            a, rho = np.linalg.lstsq(Xa, D[k_next][ok_ar], rcond=None)[0]
        last_valid = D[: i + 1][valid[: i + 1]]
        d_last = last_valid[-1] if len(last_valid) else np.nan
        fc = {
            "S": static_d,
            "U": U[i],
            "P": D[i] if valid[i] else d_last,
            "AR": a + rho * (D[i] if valid[i] else d_last) if np.isfinite(rho) else np.nan,
            "E": c0 + c1 * g[i] if np.isfinite(c1) else np.nan,
            "H": U[i] + c1 * (g[i] - gbar[i]) if (np.isfinite(c1) and np.isfinite(gbar[i])) else np.nan,
            "X": D[pos[target]] if (target in pos and valid[pos[target]]) else np.nan,
        }
        fell_back = set()
        if fallback_before_fit and not np.isfinite(c1):
            fc["E"], fc["H"] = static_d, U[i]
            fell_back = {"E", "H"}
        for mod in models:
            rows.append({**rec_base, "model": mod, "forecast": fc[mod], "fallback": mod in fell_back,
                         "n_train": {"AR": n_ar, "E": n_e, "H": n_e}.get(mod, np.nan),
                         "c0": c0 if mod in ("E",) else np.nan,
                         "c1": c1 if mod in ("E", "H") else np.nan,
                         "tau2": tau2 if mod in ("E", "H") else np.nan,
                         "ar_a": a if mod == "AR" else np.nan, "ar_rho": rho if mod == "AR" else np.nan,
                         "infeasible": mod == "X"})
    out = pd.DataFrame(rows)
    return out


def attach_realized(forecasts: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    """Add the realized duration of each target month (for evaluation only)."""
    real = monthly[["D", "se", "valid"]].rename(columns={"D": "realized", "se": "realized_se",
                                                         "valid": "realized_valid"})
    return forecasts.merge(real, left_on="target_month", right_index=True, how="left")
