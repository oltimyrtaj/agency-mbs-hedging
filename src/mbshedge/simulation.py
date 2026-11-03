"""Simulation studies with a known truth.

1. Estimator recovery: does the monthly realized-duration estimator recover the true
   (information-weighted) duration of each month, and do its 95% intervals cover the truth
   about 95% of the time?
2. Calibration of Cochran's Q: when the true duration is constant, how often does Q reject
   at the 5% level, given that the standard errors are themselves estimated?
3. Full-pipeline worlds: every world is re-estimated from scratch (half-life selection on
   development data, walk-forward forecasts, backtest, bootstrap), in three scenarios:
   "state" (duration responds to refinancing with a lag), "constant" (duration never
   changes), and "unrelated" (duration moves as much as in "state" but independently of
   refinancing). Each comparison has a reference null world in which the challenger
   should not beat the comparator: "unrelated" for the hybrid against the updating hedge
   (refinancing information adds nothing beyond updating) and "constant" for the
   comparisons against the static hedge (updating has nothing to track). The share of
   reference null worlds that pass the declared "survives costs" verdict is the
   procedure's false-positive rate, and the share of state worlds that pass it is the
   power at the effect size those worlds produce.

These worlds are synthetic. They test whether the procedure can find an effect when one
exists and stays quiet when none exists. They do not show that the effect exists in MBS.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import exposure as ex
from . import pipeline as pl
from . import synthetic as syn


def _tables(world: dict) -> dict:
    return {"fred": world["fred"], "prices": world["prices"], "nmdb": world["nmdb"]}


def recovery_study(cfg: dict, exp: dict, seeds: list[int]) -> pd.DataFrame:
    rows = []
    for seed in seeds:
        w = syn.make_world(seed, "state")
        prep = pl.prepare(_tables(w), cfg, exp)
        d = prep["daily"]
        e = exp["exposure"]
        rd = ex.monthly_realized_durations(d, min_days=e["min_days_per_month"], nw_lags=e["newey_west_lags"],
                                           max_abs=e["max_abs_duration_flag"])
        truth = w["truth"]
        dpr = truth["duration_true"].shift(1).reindex(d.index)
        dy2 = d["dy10"] ** 2
        month = d.index.to_period("M")
        true_m = (dy2 * dpr).groupby(month).sum() / dy2.groupby(month).sum()
        simple_m = truth["duration_true"].groupby(truth.index.to_period("M")).mean()
        df = rd.join(true_m.rename("true_weighted")).join(simple_m.rename("true_simple"))
        df["seed"] = seed
        rows.append(df.reset_index())
    out = pd.concat(rows, ignore_index=True)
    out = out[out["valid"]]
    out["error"] = out["D"] - out["true_weighted"]
    out["covered_95"] = (out["error"].abs() <= 1.96 * out["se"])
    return out


def q_null_study(cfg: dict, exp: dict, seeds: list[int], months: tuple[str, str], reps: int = 200,
                 scenario: str = "constant") -> pd.DataFrame:
    """For each constant-duration world: the naive chi-square p-value of Cochran's Q and the
    p-value of the constant-duration residual bootstrap (the test used on real data)."""
    rows = []
    e = exp["exposure"]
    for seed in seeds:
        w = syn.make_world(seed, scenario)
        prep = pl.prepare(_tables(w), cfg, exp)
        out = ex.null_bootstrap_variation(prep["daily"], months[0], months[1], reps=reps, seed=seed,
                                          nw_lags=e["newey_west_lags"], min_days=e["min_days_per_month"],
                                          max_abs=e["max_abs_duration_flag"])
        rows.append({"seed": seed, "scenario": scenario, **out})
    return pd.DataFrame(rows)


def pipeline_worlds(cfg: dict, exp: dict, seeds: list[int], scenario: str, reps: int) -> pd.DataFrame:
    rows = []
    pairs = exp["models"]["primary_comparisons"]
    for seed in seeds:
        w = syn.make_world(seed, scenario)
        out = pl.run_all(_tables(w), cfg, exp, segment="test", reps=reps)
        ev = out["evaluation"]
        rec = {"seed": seed, "scenario": scenario, "halflife": out["halflife"], "static_d": out["static_d"]}
        for _, b in ev["bootstrap"].iterrows():
            key = f"{b['challenger']}_vs_{b['comparator']}"
            rec[f"vr_{key}"] = b["variance_reduction"]
            rec[f"ci_low_{key}"] = b["vr_ci_low"]
            rec[f"ci_high_{key}"] = b["vr_ci_high"]
        for _, v in ev["verdicts"].iterrows():
            key = f"{v['challenger']}_vs_{v['comparator']}"
            rec[f"verdict_{key}"] = v["verdict"]
            rec[f"survives_{key}"] = v["verdict"] == "survives costs"
        s = ev["summary"]
        for strat in s.index:
            rec[f"vol_{strat}"] = s.loc[strat, "vol_gross_ann_pct"]
        fc = out["forecasts"]
        real = fc.drop_duplicates("target_month").set_index("target_month")["realized"]
        for mdl in ["U", "H", "E", "P", "AR"]:
            f = fc[fc["model"] == mdl].set_index("target_month")["forecast"]
            e2 = (real.reindex(f.index) - f) ** 2
            rec[f"rmse_{mdl}"] = float(np.sqrt(e2.mean()))
        rows.append(rec)
    return pd.DataFrame(rows)


# The world in which each challenger should NOT beat its comparator. The economic model E is
# not nested in the updating hedge U, so no world makes them equal by construction: E wins
# in constant worlds (it smooths more) and loses in unrelated worlds (it cannot track moves
# that refinancing does not explain). It therefore has no reference null.
REFERENCE_NULL = {"H_vs_U": "unrelated", "U_vs_S": "constant", "H_vs_S": "constant", "E_vs_U": None}


def power_summary(worlds: dict[str, pd.DataFrame], key: str = "H_vs_U") -> dict:
    """False-positive rate in the comparison's reference null worlds, and power at the effect
    size of the state worlds, both for the declared survives-costs verdict.

    `worlds` maps a scenario name ("state", "constant", "unrelated") to `pipeline_worlds` output.
    No minimum detectable effect is derived from the null spread: when the challenger really
    differs from its comparator, the test is much noisier than under the null, so a formula
    based on the null spread would overstate the power. The state worlds measure it directly."""
    ref = REFERENCE_NULL.get(key, "constant")
    out = {"comparison": key, "reference_null": ref or "none (not nested)"}
    if ref is not None and ref in worlds:
        null = worlds[ref]
        out.update({"null_mean_variance_reduction": float(null[f"vr_{key}"].mean()),
                    "null_sd_variance_reduction": float(null[f"vr_{key}"].std(ddof=1)),
                    "null_share_ci_above_zero": float((null[f"ci_low_{key}"] > 0).mean()),
                    "null_share_survives_costs": float(null[f"survives_{key}"].mean()),
                    "n_null_worlds": int(len(null))})
    else:
        out.update({"null_mean_variance_reduction": np.nan, "null_sd_variance_reduction": np.nan,
                    "null_share_ci_above_zero": np.nan, "null_share_survives_costs": np.nan, "n_null_worlds": 0})
    for name, df in worlds.items():
        out[f"{name}_mean_variance_reduction"] = float(df[f"vr_{key}"].mean())
        out[f"{name}_sd_variance_reduction"] = float(df[f"vr_{key}"].std(ddof=1))
        out[f"{name}_median_ci_halfwidth"] = float(((df[f"ci_high_{key}"] - df[f"ci_low_{key}"]) / 2).median())
        out[f"{name}_share_ci_above_zero"] = float((df[f"ci_low_{key}"] > 0).mean())
        out[f"{name}_share_survives_costs"] = float(df[f"survives_{key}"].mean())
        out[f"n_{name}_worlds"] = int(len(df))
    return out
