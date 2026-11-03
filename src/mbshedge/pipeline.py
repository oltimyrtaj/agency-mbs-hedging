"""High-level steps shared by the notebooks and the simulation studies.

The notebooks call these functions one step at a time and explain each output. The
simulation study (notebook 04) calls the same functions on synthetic worlds, so the
pipeline that is validated is the pipeline that produces the results.
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from pandas.tseries.holiday import AbstractHolidayCalendar, GoodFriday, USFederalHolidayCalendar

from . import backtest as bt
from . import evaluation as ev
from . import exposure as ex
from . import models as md
from . import prepare as pr
from .sources import RawStore, load_raw_tables


# ----------------------------------------------------------------------------
# Windows
# ----------------------------------------------------------------------------
class _GoodFriday(AbstractHolidayCalendar):
    rules = [GoodFriday]


def market_holidays(start, end) -> pd.DatetimeIndex:
    """Weekdays on which the bond or stock market is closed (approximation): US federal
    holidays, which the bond market observes, plus Good Friday, when the stock market closes.
    When New Year's Day falls on a Saturday, the federal calendar observes it on Friday
    December 31, but both markets stay open that day (the end of the yearly accounting
    period), so that date is removed."""
    hol = USFederalHolidayCalendar().holidays(start, end).union(_GoodFriday().holidays(start, end))
    return hol[~((hol.month == 12) & (hol.day == 31))]


def last_complete_month(index: pd.DatetimeIndex) -> pd.Period:
    """Last month whose final trading day is in the data. The month of the last observation
    counts as complete only if every weekday after that observation, up to month end, is a
    market holiday (for example Memorial Day on May 31, or Good Friday at the end of March)."""
    last = pd.Timestamp(index.max()).normalize()
    m = last.to_period("M")
    month_end = m.to_timestamp(how="end").normalize()
    remaining = pd.bdate_range(last + pd.Timedelta(days=1), month_end)
    if len(remaining) and not remaining.isin(market_holidays(remaining[0], remaining[-1])).all():
        return m - 1
    return m


def windows(daily: pd.DataFrame, exp: dict) -> dict:
    """Decision and evaluation windows for the development and test segments."""
    s = exp["sample"]
    first = pd.Period(s["first_month"], "M")
    dev_end = pd.Period(s["development_end"], "M")
    test_start = pd.Period(s["test_start"], "M")
    test_end = pd.Period(s["test_end"], "M") if s.get("test_end") else last_complete_month(daily.index)
    first_decision = first + s["min_training_months"] - 1

    def last_date(m: pd.Period) -> pd.Timestamp:
        sel = daily.index[daily.index.to_period("M") == m]
        return sel.max()

    return {
        "first_month": first, "development_end": dev_end, "test_start": test_start, "test_end": test_end,
        "dev": {"first_decision": first_decision, "last_decision": dev_end - 1, "end_date": last_date(dev_end),
                "first_target": first_decision + 1, "last_target": dev_end},
        "test": {"first_decision": test_start - 1, "last_decision": test_end - 1, "end_date": last_date(test_end),
                 "first_target": test_start, "last_target": test_end},
        "development_end_date": dev_end.to_timestamp(how="end").normalize(),
    }


# ----------------------------------------------------------------------------
# Data preparation
# ----------------------------------------------------------------------------
def load_tables(paths) -> dict:
    return load_raw_tables(RawStore(paths.raw), {})


def prepare(tables: dict, cfg: dict, exp: dict, *, lag_quarters: int | None = None,
            markets: list[str] | None = None, sigma: float | None = None,
            proxy_params: dict | None = None, use_proxy: bool = True) -> dict:
    """Build the daily panel and attach the refinancing state (as known at each close)."""
    daily, quality = pr.build_daily_panel(tables)
    s = exp["sample"]
    dev_end_date = pd.Period(s["development_end"], "M").to_timestamp(how="end").normalize()
    inc = exp["incentive"]
    lag = cfg["timing"]["nmdb_lag_quarters"] if lag_quarters is None else lag_quarters
    mk = markets or cfg["data"]["nmdb"]["markets_core"]
    state, info = pr.build_state(
        daily.index, tables["fred"]["MORTGAGE30US"], tables.get("nmdb"), markets=mk, lag_quarters=lag,
        theta=inc["refi_threshold_pp"], sigma=sigma, development_end=dev_end_date,
        proxy_grid_years=inc["proxy_halflife_grid_years"], sigma_default=inc["dispersion_default_pp"],
        proxy_params=proxy_params, use_proxy=use_proxy)
    keep = ["pmms", "pmms_release_date", "stock_rate", "stock_rate_quarter_end", "stock_rate_available_from",
            "incentive_source", "incentive", "g"]
    daily = daily.join(state[keep])
    return {"daily": daily, "quality": quality, "state_info": info}


def monthly_panel(daily: pd.DataFrame, exp: dict, halflives: list[int], ret_col: str = "r_mbb_ex",
                  dy_col: str = "dy10", g_col: str = "g") -> pd.DataFrame:
    """Realized durations, updating estimates, and state at each month-end decision date."""
    e = exp["exposure"]
    rd = ex.monthly_realized_durations(daily, ret_col=ret_col, dy_col=dy_col, min_days=e["min_days_per_month"],
                                       nw_lags=e["newey_west_lags"], max_abs=e["max_abs_duration_flag"])
    cols = [c for c in ["incentive", g_col, "incentive_source", "pmms", "stock_rate", "y10"] if c in daily]
    me = pr.month_end_table(daily, cols)
    for h in halflives:
        u = ex.ewma_duration(daily, h, ret_col=ret_col, dy_col=dy_col, state_col=g_col)
        me[f"U_{h}"] = u["U"].reindex(me["decision_date"]).to_numpy()
        me[f"gbar_{h}"] = u["gbar"].reindex(me["decision_date"]).to_numpy()
    out = me.join(rd, how="left")
    out["valid"] = out["valid"].fillna(False).astype(bool)
    if g_col != "g":
        out["g"] = out[g_col]
    return out


# ----------------------------------------------------------------------------
# Forecasts and strategies
# ----------------------------------------------------------------------------
def forecasts(monthly: pd.DataFrame, win: dict, segment: str, static_d: float, halflife: int,
              models: list[str], e_train_mask_col: str | None = None,
              fallback_before_fit: bool = False) -> pd.DataFrame:
    w = win[segment]
    fc = md.walk_forward(monthly, first_decision=str(w["first_decision"]), last_decision=str(w["last_decision"]),
                         static_d=static_d, u_col=f"U_{halflife}", gbar_col=f"gbar_{halflife}", models=models,
                         e_train_mask_col=e_train_mask_col, fallback_before_fit=fallback_before_fit)
    fc["segment"] = segment
    return md.attach_realized(fc, monthly)


def decisions(fc: pd.DataFrame, model: str) -> pd.DataFrame:
    if model == "UNH":
        d = fc[fc["model"] == fc["model"].iloc[0]][["decision_month", "decision_date"]].copy()
        d["forecast"] = 0.0
        return d
    return fc[fc["model"] == model][["decision_month", "decision_date", "forecast"]].copy()


def run_strategies(daily: pd.DataFrame, fc: pd.DataFrame, strategies: list[str], end_date, *, delay: int,
                   rule: str, cost_bp: float, financing_bp: float, max_h: float, ret_col: str = "r_mbb_ex",
                   hedge_ret_col: str = "r_h10_ex", dur_col: str = "dur_h10", dy_col: str = "dy10",
                   min_days_week: int = 3) -> dict:
    out = {}
    for s in strategies:
        res = bt.run_backtest(daily, decisions(fc, s), end_date=end_date, ret_col=ret_col,
                              hedge_ret_col=hedge_ret_col, dur_col=dur_col, delay=delay, rule=rule,
                              cost_bp=cost_bp, financing_bp=financing_bp, max_h=max_h)
        res["weekly"] = bt.weekly(res["ledger"], daily, dy_col=dy_col, min_days=min_days_week)
        out[s] = res
    # align every strategy on the same weeks; costs in weeks that only some strategies have are
    # carried into the nearest common week, so no strategy loses a trading cost in the alignment
    common = None
    for s, r in out.items():
        common = r["weekly"].index if common is None else common.intersection(r["weekly"].index)
    for s in out:
        w = out[s]["weekly"]
        out[s]["weekly"] = bt.carry_costs(w, w.index.isin(common)).loc[common]
    return out


def evaluate(results: dict, exp: dict, notional: float, pairs: list, seed: int, reps: int | None = None,
             block: float | None = None, cost_bp: float | None = None) -> dict:
    ev_cfg = exp["evaluation"]
    reps = reps or ev_cfg["bootstrap_reps"]
    block = block or ev_cfg["bootstrap_block_weeks"]
    cost_bp = exp["hedging"]["base_cost_bp"] if cost_bp is None else cost_bp
    weekly = {s: r["weekly"] for s, r in results.items()}
    info = {s: r["info"] for s, r in results.items()}
    summary = ev.strategy_summary(weekly, info, notional, lags=ev_cfg["hac_lags_weekly"])
    W = pd.DataFrame({s: w["gross_pnl"] for s, w in weekly.items()})
    boot = ev.paired_bootstrap(W, [tuple(p) for p in pairs], reps, block, seed, ev_cfg["confidence"])
    boot = ev.add_holm(boot, [tuple(p) for p in pairs])
    verdicts = []
    for ch, cp in pairs:
        practical = ev_cfg["practical_variance_reduction_vs_U"] if cp == "U" else ev_cfg["practical_variance_reduction_vs_S"]
        verdicts.append(ev.cost_verdict(summary, boot, ch, cp, ev_cfg["hurdle_information_ratio"], cost_bp, practical,
                                        alpha=(1 - ev_cfg["confidence"]) / 2))
    return {"summary": summary, "bootstrap": boot, "verdicts": pd.DataFrame(verdicts), "weekly_matrix": W}


def select_halflife(daily: pd.DataFrame, monthly: pd.DataFrame, win: dict, exp: dict, static_d: float,
                    ret_col: str = "r_mbb_ex", hedge_ret_col: str = "r_h10_ex", dur_col: str = "dur_h10",
                    dy_col: str = "dy10") -> tuple[int, pd.DataFrame]:
    """Choose the EWMA half-life on development data only, by the declared objective
    J = hurdle_IR * annualized gross volatility + annual cost drag (base cost and rule)."""
    h = exp["hedging"]
    rows = []
    for hl in exp["exposure"]["ewma_halflife_grid_days"]:
        fc = forecasts(monthly, win, "dev", static_d, hl, ["U"])
        res = run_strategies(daily, fc, ["U"], win["dev"]["end_date"], delay=h["base_delay_days"],
                             rule=h["base_rule"], cost_bp=h["base_cost_bp"], financing_bp=h["financing_spread_bp_per_year"],
                             max_h=h["max_hedge_ratio"], ret_col=ret_col, hedge_ret_col=hedge_ret_col,
                             dur_col=dur_col, dy_col=dy_col)["U"]
        vol = ev.ann_vol(res["weekly"]["gross_pnl"])
        cost = res["info"]["cost_per_year"]
        rows.append({"halflife_days": hl, "dev_vol_gross_ann_pct": 100 * vol, "dev_cost_bp_per_year": 1e4 * cost,
                     "objective_bp": 1e4 * (exp["evaluation"]["hurdle_information_ratio"] * vol + cost),
                     "dev_turnover_per_year": res["info"]["turnover_per_year"]})
    table = pd.DataFrame(rows)
    best = int(table.loc[table["objective_bp"].idxmin(), "halflife_days"])
    return best, table


# ----------------------------------------------------------------------------
# Everything in one call (used by the simulation study and the perturbation test)
# ----------------------------------------------------------------------------
def run_all(tables: dict, cfg: dict, exp: dict, *, segment: str = "test", strategies: list[str] | None = None,
            halflife: int | None = None, reps: int = 0, select: bool = True) -> dict:
    """Prepare, estimate, forecast, and backtest one dataset. With reps=0 no bootstrap is run."""
    prep = prepare(tables, cfg, exp)
    daily = prep["daily"]
    win = windows(daily, exp)
    grid = exp["exposure"]["ewma_halflife_grid_days"]
    monthly = monthly_panel(daily, exp, grid if (select and halflife is None) else [halflife])
    static_d = md.static_duration(monthly, exp["sample"]["first_month"], exp["sample"]["development_end"])
    hl_table = None
    if halflife is None:
        halflife, hl_table = select_halflife(daily, monthly, win, exp, static_d)
    strategies = strategies or ["UNH", "S", "U", "P", "AR", "E", "H", "X"]
    models = [s for s in strategies if s != "UNH"]
    fc = forecasts(monthly, win, segment, static_d, halflife, models)
    h = exp["hedging"]
    res = run_strategies(daily, fc, strategies, win[segment]["end_date"], delay=h["base_delay_days"],
                         rule=h["base_rule"], cost_bp=h["base_cost_bp"],
                         financing_bp=h["financing_spread_bp_per_year"], max_h=h["max_hedge_ratio"])
    out = {"prep": prep, "daily": daily, "windows": win, "monthly": monthly, "static_d": static_d,
           "halflife": halflife, "halflife_table": hl_table, "forecasts": fc, "results": res}
    if reps:
        out["evaluation"] = evaluate(res, exp, 1.0, exp["models"]["primary_comparisons"], exp["seed"], reps=reps)
    return out


# ----------------------------------------------------------------------------
# Look-ahead perturbation test
# ----------------------------------------------------------------------------
def perturb_after(tables: dict, cut: pd.Timestamp, lag_quarters: int, seed: int) -> dict:
    """Replace every value that was not yet available at the close of `cut` with noise.
    NMDB quarters are perturbed by their availability date, not their quarter-end date."""
    rng = np.random.default_rng(seed)
    t = copy.deepcopy(tables)
    for sid, df in t["fred"].items():
        late = df["date"] > cut
        df.loc[late & df["value"].notna(), "value"] = rng.uniform(0.1, 9.0, int((late & df["value"].notna()).sum()))
    for tk, df in t["prices"].items():
        late = df["date"] > cut
        k = int(late.sum())
        df.loc[late, "close"] = rng.uniform(10, 200, k)
        df.loc[late, "adj_close"] = np.nan          # the total-return check then covers only real rows
        df.loc[late, "dividend"] = rng.uniform(0, 1, k) * (rng.random(k) < 0.05)
    if t.get("nmdb") is not None:
        n = t["nmdb"]
        avail = pr.availability_dates(n["quarter_end"], lag_quarters)
        late = avail > cut
        ranges = {"AVE_INTRATE": (2.0, 8.0), "TOT_UPB": (1000.0, 9000.0)}
        for series, grp in n[late].groupby("series"):
            lo, hi = ranges.get(series, (0.0, 100.0))
            n.loc[grp.index, "value1"] = rng.uniform(lo, hi, len(grp))
            n.loc[grp.index, "value2"] = rng.uniform(lo, hi, len(grp))
    return t


def perturbation_check(tables: dict, cfg: dict, exp: dict, cut: pd.Timestamp, seed: int,
                       halflife: int, segment: str = "test") -> dict:
    """Run the pipeline on original and perturbed data and compare everything dated at or
    before `cut`. Forecasts and positions known by then must be bit-identical."""
    base = run_all(tables, cfg, exp, segment=segment, halflife=halflife, reps=0, select=False)
    pert = run_all(perturb_after(tables, cut, cfg["timing"]["nmdb_lag_quarters"], seed), cfg, exp,
                   segment=segment, halflife=halflife, reps=0, select=False)
    cut = pd.Timestamp(cut)
    key = ["model", "decision_month"]
    # outer merge: a forecast that appears or disappears also counts as a change
    m = base["forecasts"].merge(pert["forecasts"], on=key, how="outer", suffixes=("_a", "_b"))
    decided = m["decision_date_a"].fillna(m["decision_date_b"])
    infeasible = m["infeasible_a"].fillna(m["infeasible_b"]).astype(bool)
    early = (decided <= cut) & ~infeasible
    late = (decided > cut) & ~infeasible
    ch_early = change_between(m.loc[early, "forecast_a"], m.loc[early, "forecast_b"])
    ch_late = change_between(m.loc[late, "forecast_a"], m.loc[late, "forecast_b"])
    pos_changes = []
    for s in base["results"]:
        if s == "X":
            continue
        ha, hb = base["results"][s]["ledger"]["h_held"], pert["results"][s]["ledger"]["h_held"]
        # positions held on every day up to and including the first day after the cut, which is the
        # position set at the close of the cut date itself
        days = ha.index.union(hb.index)
        after = days[days > cut]
        days = days[days <= (after[0] if len(after) else cut)]
        pos_changes.append(float(change_between(ha.reindex(days), hb.reindex(days)).max()) if len(days) else 0.0)
    max_fc = float(ch_early.max()) if len(ch_early) else 0.0
    max_pos = float(max(pos_changes)) if pos_changes else 0.0
    return {"cut": str(cut.date()), "n_early_forecasts": int(early.sum()),
            "max_abs_change_early_forecasts": max_fc, "max_abs_change_early_positions": max_pos,
            "share_late_forecasts_changed": float((ch_late > 1e-9).mean()) if len(ch_late) else np.nan,
            "passed": bool(max_fc == 0.0 and max_pos == 0.0)}


def change_between(a, b) -> np.ndarray:
    """Absolute change between two aligned value arrays. A missing value on one side only
    counts as an infinite change, and a value missing on both sides counts as no change."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    out = np.abs(a - b)
    out[np.isnan(a) & np.isnan(b)] = 0.0
    out[np.isnan(a) ^ np.isnan(b)] = np.inf
    return out


# ----------------------------------------------------------------------------
# Saving and loading results so notebooks share data only through files
# ----------------------------------------------------------------------------
def load_forecasts(path) -> pd.DataFrame:
    fc = pd.read_csv(path)
    for c in ("decision_month", "target_month", "training_cutoff_month"):
        if c in fc:
            fc[c] = pd.PeriodIndex(fc[c].astype(str), freq="M")
    for c in ("decision_date", "available_at", "execution_date"):
        if c in fc:
            fc[c] = pd.to_datetime(fc[c]).astype("datetime64[ns]")
    if "infeasible" in fc:
        fc["infeasible"] = fc["infeasible"].astype(str).str.lower().isin(["true", "1"])
    return fc


def save_runs(res: dict, folder, tag: str, save_ledgers: bool = True) -> None:
    from pathlib import Path
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    weekly, trades, info = [], [], []
    for s, r in res.items():
        w = r["weekly"].copy()
        w["strategy"] = s
        weekly.append(w.reset_index().rename(columns={"index": "week", "date": "week"}))
        t = r["trades"].copy()
        t["strategy"] = s
        trades.append(t)
        info.append({"strategy": s, **{k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in r["info"].items()}})
        if save_ledgers:
            r["ledger"].to_parquet(folder / f"ledger_{tag}_{s}.parquet")
    wk = pd.concat(weekly, ignore_index=True)
    wk = wk.rename(columns={wk.columns[0]: "week"}) if "week" not in wk.columns else wk
    wk.to_parquet(folder / f"weekly_{tag}.parquet")
    tr = pd.concat(trades, ignore_index=True)
    for c in ("decision_month",):
        if c in tr:
            tr[c] = tr[c].astype(str)
    tr.to_csv(folder / f"trades_{tag}.csv", index=False)
    pd.DataFrame(info).to_csv(folder / f"info_{tag}.csv", index=False)


def load_runs(folder, tag: str) -> dict:
    from pathlib import Path
    folder = Path(folder)
    wk = pd.read_parquet(folder / f"weekly_{tag}.parquet")
    info = pd.read_csv(folder / f"info_{tag}.csv").set_index("strategy")
    out = {}
    for s, g in wk.groupby("strategy", sort=False):
        w = g.drop(columns="strategy").set_index("week").sort_index()
        out[s] = {"weekly": w, "info": info.loc[s].to_dict()}
    return out


def grid_runs(daily: pd.DataFrame, fc: pd.DataFrame, strategies: list[str], end_date, exp: dict,
              rules: list[str], delays: list[int], financing_values: list[float]) -> pd.DataFrame:
    """Run every strategy under each rebalancing rule, delay, and financing spread at a 1 bp
    cost. Costs are linear in the cost level, so net P&L at any cost c is
    gross - c * cost_1bp - financing, computed later without rerunning."""
    h = exp["hedging"]
    rows = []
    configs = [(r, d, 0.0) for r in rules for d in delays] + \
              [(h["base_rule"], h["base_delay_days"], f) for f in financing_values if f]
    for rule, delay, fin in configs:
        res = run_strategies(daily, fc, strategies, end_date, delay=delay, rule=rule, cost_bp=1.0,
                             financing_bp=fin, max_h=h["max_hedge_ratio"])
        for s, r in res.items():
            w = r["weekly"][["gross_pnl", "cost", "financing", "dy"]].rename(columns={"cost": "cost_1bp"}).copy()
            w["strategy"], w["rule"], w["delay"], w["financing_bp"] = s, rule, delay, fin
            w["turnover_per_year"] = r["info"]["turnover_per_year"]
            w["position_limit_hits"] = r["info"]["position_limit_hits"]
            rows.append(w.reset_index().rename(columns={w.index.name or "index": "week"}))
    return pd.concat(rows, ignore_index=True)
