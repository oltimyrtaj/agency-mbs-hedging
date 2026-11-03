"""Risk metrics, uncertainty, forecast tests, and the declared cost verdict.

Conventions
-----------
* Inputs are weekly sums of daily P&L per $1 of MBS notional (decimal returns).
* Annualization: volatility x sqrt(52), means and costs x 52 (or per calendar year for costs).
* Losses are reported as positive numbers (expected shortfall, drawdown).
* Variance reduction of a challenger against a comparator: 1 - Var(challenger) / Var(comparator).

What the paired stationary bootstrap captures
---------------------------------------------
It resamples aligned weeks (all strategies together, in blocks of random length with a
mean of 13 weeks) and recomputes the statistic. It reflects sampling variability of the
realized test-period returns given the positions that were taken, including serial
dependence. It does not refit the forecasting models, so it leaves out estimation
variability of the procedure itself (notebook 04 measures that by simulation), and it
cannot create regimes that never occurred in the sample.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .exposure import ols_hac

WEEKS_PER_YEAR = 52.0


# ----------------------------------------------------------------------------
# Basic metrics
# ----------------------------------------------------------------------------
def ann_vol(x, periods: float = WEEKS_PER_YEAR) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.std(x, ddof=1) * np.sqrt(periods)) if len(x) > 2 else np.nan


def variance_reduction(challenger, comparator) -> float:
    a = np.asarray(challenger, dtype=float)
    b = np.asarray(comparator, dtype=float)
    vb = np.var(b, ddof=1)
    return float(1.0 - np.var(a, ddof=1) / vb) if vb > 0 else np.nan


def expected_shortfall(x, level: float = 0.95) -> float:
    """Average loss in the worst (1 - level) share of periods, as a positive number."""
    x = np.sort(np.asarray(x, dtype=float)[np.isfinite(x)])
    k = max(1, int(np.floor((1 - level) * len(x) + 1e-9)))   # tolerance guards 0.1*20 = 1.9999...
    return float(-x[:k].mean())


def max_drawdown(pnl) -> float:
    """Largest peak-to-trough fall of cumulative (additive) P&L, as a positive number."""
    cum = np.cumsum(np.asarray(pnl, dtype=float))
    peak = np.maximum.accumulate(np.r_[0.0, cum])[1:]
    return float(np.max(peak - cum)) if len(cum) else np.nan


def residual_exposure(weekly_pnl, weekly_dy, lags: int = 4) -> dict:
    """Slope of hedged P&L on the yield change, expressed as residual duration (years)."""
    y = np.asarray(weekly_pnl, dtype=float)
    x = np.asarray(weekly_dy, dtype=float)
    ok = np.isfinite(y) & np.isfinite(x)
    X = np.column_stack([np.ones(ok.sum()), x[ok]])
    fit = ols_hac(y[ok], X, lags)
    return {"residual_duration": float(-fit["beta"][1]), "residual_duration_se": float(np.sqrt(fit["cov"][1, 1])),
            "r2_on_dy": float(fit["r2"])}


def hac_mean_se(x, lags: int) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    fit = ols_hac(x, np.ones((n, 1)), lags)
    return float(np.sqrt(fit["cov"][0, 0]))


# ----------------------------------------------------------------------------
# Paired stationary bootstrap
# ----------------------------------------------------------------------------
def stationary_bootstrap_indices(n: int, mean_block: float, reps: int, rng: np.random.Generator) -> np.ndarray:
    """Politis-Romano stationary bootstrap: blocks start at random points and have
    geometric lengths with mean `mean_block`; the series wraps around."""
    p = 1.0 / mean_block
    idx = np.empty((reps, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, reps)
    new_block = rng.random((reps, n)) < p
    starts = rng.integers(0, n, (reps, n))
    for t in range(1, n):
        idx[:, t] = np.where(new_block[:, t], starts[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def paired_bootstrap(weekly_matrix: pd.DataFrame, pairs: list[tuple[str, str]], reps: int, mean_block: float,
                     seed: int, confidence: float = 0.95) -> pd.DataFrame:
    """Bootstrap the variance reduction and volatility difference for each (challenger, comparator).

    `weekly_matrix` columns are strategies, rows are aligned weeks (no missing values).
    The one-sided p-value for H0 "variance reduction <= 0" is the share of resamples with no
    reduction, read from the same bootstrap distribution as the percentile interval. The
    interval's lower end lies above zero when this p-value is below (1 - confidence) / 2, so
    the test and the reported interval always agree.
    """
    W = weekly_matrix.dropna()
    X = W.to_numpy()
    cols = list(W.columns)
    n = len(W)
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(n, mean_block, reps, rng)
    var_b = np.empty((reps, X.shape[1]))
    for j in range(X.shape[1]):
        xs = X[:, j][idx]
        var_b[:, j] = xs.var(axis=1, ddof=1)
    alpha = 1 - confidence
    rows = []
    for ch, cp in pairs:
        i, k = cols.index(ch), cols.index(cp)
        vr_hat = 1 - X[:, i].var(ddof=1) / X[:, k].var(ddof=1)
        vr_b = 1 - var_b[:, i] / var_b[:, k]
        dvol_hat = np.sqrt(WEEKS_PER_YEAR) * (X[:, k].std(ddof=1) - X[:, i].std(ddof=1))
        dvol_b = np.sqrt(WEEKS_PER_YEAR) * (np.sqrt(var_b[:, k]) - np.sqrt(var_b[:, i]))
        p_one = float(np.mean(vr_b <= 0.0))
        rows.append({
            "challenger": ch, "comparator": cp, "n_weeks": n,
            "variance_reduction": float(vr_hat),
            "vr_ci_low": float(np.quantile(vr_b, alpha / 2)), "vr_ci_high": float(np.quantile(vr_b, 1 - alpha / 2)),
            "vol_reduction_ann": float(dvol_hat),
            "vol_red_ci_low": float(np.quantile(dvol_b, alpha / 2)),
            "vol_red_ci_high": float(np.quantile(dvol_b, 1 - alpha / 2)),
            "p_one_sided": max(p_one, 1.0 / reps),
            "bootstrap_reps": reps, "mean_block_weeks": mean_block,
        })
    return pd.DataFrame(rows)


def holm(pvalues: dict) -> dict:
    """Holm step-down adjustment of a set of p-values."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adj, running = {}, 0.0
    for r, (key, p) in enumerate(items):
        val = min(1.0, (m - r) * p)
        running = max(running, val)
        adj[key] = running
    return adj


def add_holm(boot: pd.DataFrame, family: list) -> pd.DataFrame:
    """Add `primary` and `p_holm` columns: the Holm-adjusted one-sided p-value over the declared
    family of comparisons (NaN for comparisons outside the family)."""
    boot = boot.copy()
    fam = {(a, b) for a, b in family}
    pairs = list(zip(boot["challenger"], boot["comparator"]))
    boot["primary"] = [p in fam for p in pairs]
    adj = holm({f"{a}_vs_{b}": float(p) for (a, b), p, f in zip(pairs, boot["p_one_sided"], boot["primary"]) if f})
    boot["p_holm"] = [adj.get(f"{a}_vs_{b}", np.nan) for a, b in pairs]
    return boot


# ----------------------------------------------------------------------------
# Forecast comparison
# ----------------------------------------------------------------------------
def clark_west(y, f_small, f_big, lags: int) -> dict:
    """Clark-West (2007) test that the larger nested model forecasts better. One-sided."""
    y, fs, fb = (np.asarray(v, dtype=float) for v in (y, f_small, f_big))
    ok = np.isfinite(y) & np.isfinite(fs) & np.isfinite(fb)
    f = (y[ok] - fs[ok]) ** 2 - ((y[ok] - fb[ok]) ** 2 - (fs[ok] - fb[ok]) ** 2)
    se = hac_mean_se(f, lags)
    stat = float(f.mean() / se) if se > 0 else np.nan
    return {"n": int(ok.sum()), "cw_stat": stat, "p_one_sided": float(stats.norm.sf(stat)) if np.isfinite(stat) else np.nan}


def diebold_mariano(y, f1, f2, lags: int) -> dict:
    """Diebold-Mariano test of equal squared-error loss. Positive mean loss difference means
    model 2 is more accurate. Two-sided p-value."""
    y, a, b = (np.asarray(v, dtype=float) for v in (y, f1, f2))
    ok = np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    d = (y[ok] - a[ok]) ** 2 - (y[ok] - b[ok]) ** 2
    se = hac_mean_se(d, lags)
    stat = float(d.mean() / se) if se > 0 else np.nan
    return {"n": int(ok.sum()), "mean_loss_diff": float(d.mean()), "dm_stat": stat,
            "p_two_sided": float(2 * stats.norm.sf(abs(stat))) if np.isfinite(stat) else np.nan}


def forecast_table(fc: pd.DataFrame, models: list[str], reference: str = "U") -> pd.DataFrame:
    """Squared-error comparison on months where every listed model has a forecast and the
    target month's realized duration is valid (a common sample)."""
    wide = fc.pivot_table(index="target_month", columns="model", values="forecast")
    real = fc.drop_duplicates("target_month").set_index("target_month")[["realized", "realized_se", "realized_valid"]]
    df = wide.join(real)
    df = df[df["realized_valid"].astype(bool)].dropna(subset=[m for m in models if m in df.columns])
    rows = []
    mse_ref = float(((df["realized"] - df[reference]) ** 2).mean()) if reference in df else np.nan
    noise = float((df["realized_se"] ** 2).mean())
    for m in models:
        if m not in df:
            continue
        e = df["realized"] - df[m]
        mse = float((e ** 2).mean())
        rows.append({"model": m, "n_months": len(df), "rmse_years": np.sqrt(mse), "mae_years": float(e.abs().mean()),
                     "mean_error_years": float(e.mean()), "mse": mse,
                     "noise_adjusted_mse": mse - noise,
                     "oos_r2_vs_reference": 1 - mse / mse_ref if mse_ref > 0 else np.nan})
    out = pd.DataFrame(rows)
    out.attrs["mean_measurement_variance"] = noise
    out.attrs["reference"] = reference
    return out


# ----------------------------------------------------------------------------
# Strategy summary and the declared cost verdict
# ----------------------------------------------------------------------------
def strategy_summary(weekly_by_strategy: dict, info_by_strategy: dict, notional: float,
                     lags: int = 4) -> pd.DataFrame:
    """One row per strategy on its weekly P&L (all strategies should share the same weeks)."""
    rows = []
    unh = weekly_by_strategy.get("UNH")
    for name, w in weekly_by_strategy.items():
        info = info_by_strategy[name]
        res = residual_exposure(w["gross_pnl"], w["dy"], lags)
        row = {
            "strategy": name, "n_weeks": len(w),
            "vol_gross_ann_pct": 100 * ann_vol(w["gross_pnl"]), "vol_net_ann_pct": 100 * ann_vol(w["net_pnl"]),
            "mean_net_ann_pct": 100 * w["net_pnl"].mean() * WEEKS_PER_YEAR,
            "es95_weekly_net_bp": 1e4 * expected_shortfall(w["net_pnl"], 0.95),
            "max_drawdown_net_pct": 100 * max_drawdown(w["net_pnl"]),
            "residual_duration_years": res["residual_duration"],
            "residual_duration_se": res["residual_duration_se"],
            "turnover_per_year": info["turnover_per_year"],
            "cost_drag_bp_per_year": 1e4 * info["cost_per_year"],
            "financing_bp_per_year": 1e4 * info["financing_per_year"],
            "position_limit_hits": info["position_limit_hits"],
            "vol_gross_usd_mm": notional * ann_vol(w["gross_pnl"]) / 1e6,
            "cost_usd_per_year": notional * info["cost_per_year"],
        }
        if unh is not None:
            row["var_reduction_vs_unhedged"] = variance_reduction(w["gross_pnl"], unh.loc[w.index, "gross_pnl"])
        rows.append(row)
    return pd.DataFrame(rows).set_index("strategy")


def cost_verdict(summary: pd.DataFrame, boot: pd.DataFrame, challenger: str, comparator: str,
                 hurdle_ir: float, cost_bp: float, practical_vr: float, alpha: float = 0.025) -> dict:
    """Apply the declared survives-costs definition (docs/research_design.md, section 7).

    gain = hurdle_ir * (sigma_comparator - sigma_challenger) - (cost_challenger - cost_comparator)
    computed per year in return units at `cost_bp` per unit of hedge notional traded.

    Statistical support: the 95% bootstrap interval must lie above zero, and for a comparison in
    the declared family (a finite `p_holm` in `boot`) the Holm-adjusted one-sided p-value must
    also be below `alpha` (0.025, the one-sided level that matches a two-sided 95% interval).
    A supported result therefore never sits next to an interval that includes zero.
    """
    s_ch, s_cp = summary.loc[challenger], summary.loc[comparator]
    sig_ch, sig_cp = s_ch["vol_gross_ann_pct"] / 100, s_cp["vol_gross_ann_pct"] / 100
    to_ch, to_cp = s_ch["turnover_per_year"], s_cp["turnover_per_year"]
    fin_ch, fin_cp = s_ch["financing_bp_per_year"] / 1e4, s_cp["financing_bp_per_year"] / 1e4
    c = cost_bp / 1e4
    extra_cost = c * (to_ch - to_cp) + (fin_ch - fin_cp)
    value = hurdle_ir * (sig_cp - sig_ch)
    gain = value - extra_cost
    # Net gain as a function of the cost per unit traded k: gain(k) = base - k * extra_turnover.
    # It changes sign once, at the break-even cost, and which side is positive depends on
    # whether the challenger trades more or less than the comparator.
    base = value - (fin_ch - fin_cp)
    extra_turnover = to_ch - to_cp
    if extra_turnover != 0 and base / extra_turnover > 0:
        breakeven_bp = 1e4 * base / extra_turnover
        positive_when = "below break-even cost" if extra_turnover > 0 else "above break-even cost"
    else:
        breakeven_bp = np.nan
        positive_when = "at every cost" if base > 0 or (base == 0 and extra_turnover < 0) else "at no cost"
    b = boot[(boot["challenger"] == challenger) & (boot["comparator"] == comparator)]
    vr = float(b["variance_reduction"].iloc[0]) if len(b) else np.nan
    lo = float(b["vr_ci_low"].iloc[0]) if len(b) else np.nan
    p_holm = float(b["p_holm"].iloc[0]) if (len(b) and "p_holm" in b) else np.nan
    if np.isfinite(p_holm):
        stat_ok = bool(p_holm < alpha and lo > 0)
        support_rule = f"Holm-adjusted one-sided p < {alpha:g} and 95% interval above zero"
    else:
        stat_ok = bool(lo > 0)
        support_rule = "95% interval above zero (no multiplicity adjustment)"
    econ_ok = bool(gain > 0)
    if econ_ok and stat_ok:
        verdict = "survives costs"
    elif econ_ok:
        verdict = "economically positive, statistically inconclusive"
    elif vr > 0:
        verdict = "risk reduction does not pay for its extra cost"
    else:
        verdict = "no risk reduction"
    return {"challenger": challenger, "comparator": comparator, "cost_bp": cost_bp,
            "variance_reduction": vr, "vr_ci_low": lo, "meets_practical_target": bool(vr >= practical_vr),
            "practical_target": practical_vr, "value_of_risk_reduction_bp_per_year": 1e4 * value,
            "extra_cost_bp_per_year": 1e4 * extra_cost, "net_gain_bp_per_year": 1e4 * gain,
            "breakeven_cost_bp_per_trade": float(breakeven_bp), "net_gain_positive_when": positive_when,
            "p_holm": p_holm, "statistical_support": stat_ok, "support_rule": support_rule, "verdict": verdict}


def breakeven_text(v) -> str:
    """One plain sentence describing where the challenger's net gain is positive."""
    when, be = v["net_gain_positive_when"], v["breakeven_cost_bp_per_trade"]
    if when == "below break-even cost":
        return f"Its net gain is positive at costs below {be:.1f} bp per unit traded (the break-even cost)."
    if when == "above break-even cost":
        return (f"It trades less than its comparator, so its net gain turns positive only at costs above "
                f"{be:.1f} bp per unit traded.")
    if when == "at every cost":
        return "Its net gain is positive at every cost level."
    return "Its net gain is negative at every cost level."



OUTCOMES = ("useful improvement", "small but statistically supported improvement",
            "advantage limited to particular environments", "no demonstrated gain over the simple updating hedge")


def classify_outcome(verdict: dict, boot_row: dict, regimes: pd.DataFrame, practical_vr: float,
                     min_slice_weeks: int = 52, comparison: str = "H vs U") -> dict:
    """Map the headline comparison to the four outcomes declared in docs/outcome_interpretations.md.

    verdict  : `cost_verdict` output for the hybrid against the updating hedge at the base cost
    boot_row : the matching row of the paired bootstrap table (needs vr_ci_high)
    regimes  : regime slices with columns comparison, weeks, variance_reduction, ci_low
    Outcome 4 is called inconclusive when the 95% interval still reaches the practical target,
    because the data then cannot rule out a gain of the size a desk would care about.
    """
    vr = float(verdict["variance_reduction"])
    ci_high = float(boot_row["vr_ci_high"])
    reg = regimes if regimes is not None else pd.DataFrame(columns=["comparison", "weeks", "variance_reduction", "ci_low"])
    slices = reg[(reg["comparison"] == comparison) & (reg["weeks"] >= min_slice_weeks)
                 & (reg["variance_reduction"] >= practical_vr) & (reg["ci_low"] > 0)]
    if verdict["verdict"] == "survives costs" and verdict["meets_practical_target"]:
        outcome = OUTCOMES[0]
    elif verdict["verdict"] == "survives costs":
        outcome = OUTCOMES[1]
    elif vr > 0 and len(slices):
        outcome = OUTCOMES[2]
    else:
        outcome = OUTCOMES[3]
    no_gain = outcome == OUTCOMES[3]
    return {"outcome": outcome, "variance_reduction": vr, "ci_low": float(verdict["vr_ci_low"]), "ci_high": ci_high,
            "practical_target": practical_vr, "verdict": verdict["verdict"],
            "inconclusive": bool(no_gain and ci_high >= practical_vr),
            "rules_out_practical_gain": bool(no_gain and ci_high < practical_vr),
            "qualifying_slices": slices.to_dict(orient="records")}
