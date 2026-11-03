"""The common hedge backtest engine. Every strategy runs through `run_backtest`.

Accounting (per $1 of MBS notional; multiply by the notional for dollars)
---------------------------------------------------------------------
The investor holds a constant $N of MBS exposure (daily gains and losses are swept to a
cash account) and a short position of h dollars of the synthetic 10-year Treasury per
dollar of MBS. The short is financed like a futures position or a repo short, so it earns
the bond's excess return over the bill rate with the sign flipped. On day i:

    mbs_pnl[i]   = r_mbs_ex[i]
    hedge_pnl[i] = -h_held[i] * r_h_ex[i]          h_held[i] = position after the close of day i-1
    cost[i]      = c * |trade[i]|                   c = one-way cost per $1 of hedge notional traded
    financing[i] = h_held[i] * s * days[i] / 365    s = financing spread on the short proceeds
    net_pnl[i]   = mbs_pnl + hedge_pnl - cost - financing

All P&L is excess of the bill return on capital, so the cash account's own interest drops
out. Daily P&L adds up to weekly and total P&L because the notional is held constant.

Timing
------
A decision made at the close of decision date T is executed at the close of the trading
day `delay` days later. The new position earns returns from the following day on.
Establishment cost (from zero) is booked on the first ledger day and liquidation cost (back
to zero) on the last ledger day.

Rebalancing rules
-----------------
monthly      trade to target at every decision
quarterly    trade only at decisions made at the end of March, June, September, December
band_x       trade to target only when target duration differs from the duration currently
             hedged (h * hedge duration) by more than x years
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _should_trade(rule: str, first: bool, decision_month: pd.Period, target_d: float, current_d: float) -> bool:
    if first or rule == "monthly":
        return True
    if rule == "quarterly":
        return decision_month.month in (3, 6, 9, 12)
    if rule.startswith("band_"):
        return abs(target_d - current_d) > float(rule.split("_", 1)[1])
    raise ValueError(f"unknown rebalance rule {rule!r}")


def run_backtest(daily: pd.DataFrame, decisions: pd.DataFrame, *, end_date, ret_col: str = "r_mbb_ex",
                 hedge_ret_col: str = "r_h10_ex", dur_col: str = "dur_h10", delay: int = 1,
                 rule: str = "monthly", cost_bp: float = 2.0, financing_bp: float = 0.0,
                 max_h: float = 1.5) -> dict:
    """Run one strategy.

    decisions : DataFrame with columns decision_month (Period), decision_date, forecast (years).
                A forecast of 0 for every decision gives the unhedged portfolio.
    end_date  : last date of the evaluation window (inclusive); the position is liquidated there.
    """
    dates = daily.index
    n = len(dates)
    end_i = int(dates.searchsorted(pd.Timestamp(end_date), side="right") - 1)
    r = daily[ret_col].to_numpy()
    rh = daily[hedge_ret_col].to_numpy()
    dur = daily[dur_col].to_numpy()
    gaps = daily["days"].to_numpy()

    dec = decisions.sort_values("decision_date").reset_index(drop=True)
    pos = np.zeros(n)                      # position after the close of day i
    trades = np.zeros(n)
    trade_rows = []
    h_cur = 0.0
    first_exec = None
    clip_hits = 0
    for j, row in dec.iterrows():
        i_dec = int(dates.searchsorted(pd.Timestamp(row["decision_date"])))
        if i_dec >= n or dates[i_dec] != pd.Timestamp(row["decision_date"]):
            raise ValueError(f"decision date {row['decision_date']} is not a trading date in the panel")
        e = i_dec + delay
        if e > end_i:
            continue
        f = row["forecast"]
        d_h = dur[e]
        rec = {"decision_month": row["decision_month"], "decision_date": dates[i_dec], "execution_date": dates[e],
               "forecast_years": f, "hedge_duration": d_h, "h_before": h_cur}
        if not np.isfinite(f) or not np.isfinite(d_h) or d_h <= 0:
            rec.update({"target_h": np.nan, "executed": False, "trade": 0.0, "note": "no usable forecast, position kept"})
            trade_rows.append(rec)
            continue
        target = f / d_h
        clipped = target < 0 or target > max_h
        if clipped:
            clip_hits += 1
        target = float(np.clip(target, 0.0, max_h))
        do = _should_trade(rule, first_exec is None, row["decision_month"], f, h_cur * d_h)
        if do:
            if first_exec is None:
                first_exec = e
            trades[e] += target - h_cur
            pos[e:] = target
            rec.update({"target_h": target, "executed": True, "trade": target - h_cur,
                        "note": "position limit hit" if clipped else ""})
            h_cur = target
        else:
            rec.update({"target_h": target, "executed": False, "trade": 0.0, "note": "inside band / off-cycle"})
        trade_rows.append(rec)
    if first_exec is None:
        raise ValueError("no executable decision in the window")
    pos[end_i + 1:] = 0.0
    start_i = first_exec + 1
    idx = np.arange(start_i, end_i + 1)
    h_held = pos[idx - 1]
    trade_on_day = trades[idx].copy()
    trade_on_day[0] += trades[first_exec]          # establishment booked on the first ledger day
    trade_on_day[-1] += -pos[end_i]                 # liquidation at the final close
    c = cost_bp / 1e4
    ledger = pd.DataFrame({
        "h_held": h_held,
        "trade": trade_on_day,
        "mbs_pnl": r[idx],
        "hedge_pnl": -h_held * rh[idx],
        "cost": c * np.abs(trade_on_day),
        "financing": h_held * (financing_bp / 1e4) * gaps[idx] / 365.0,
    }, index=dates[idx])
    ledger["gross_pnl"] = ledger["mbs_pnl"] + ledger["hedge_pnl"]
    ledger["net_pnl"] = ledger["gross_pnl"] - ledger["cost"] - ledger["financing"]
    years = (dates[end_i] - dates[first_exec]).days / 365.25
    info = {
        "start": dates[start_i], "end": dates[end_i], "years": years,
        "n_decisions": int(len(dec)), "n_trades": int((ledger["trade"].abs() > 0).sum()),
        "turnover_total": float(np.abs(ledger["trade"]).sum()),
        "turnover_per_year": float(np.abs(ledger["trade"]).sum() / years) if years > 0 else np.nan,
        "cost_total": float(ledger["cost"].sum()),
        "cost_per_year": float(ledger["cost"].sum() / years) if years > 0 else np.nan,
        "financing_per_year": float(ledger["financing"].sum() / years) if years > 0 else np.nan,
        "position_limit_hits": int(clip_hits), "rule": rule, "delay": delay, "cost_bp": cost_bp,
    }
    return {"ledger": ledger, "trades": pd.DataFrame(trade_rows), "info": info}


def weekly(ledger: pd.DataFrame, daily: pd.DataFrame, dy_col: str = "dy10", min_days: int = 3) -> pd.DataFrame:
    """Friday-ending weekly sums of P&L and of the yield change (for residual exposure).

    Weeks with fewer than `min_days` trading days (usually the partial first and last weeks
    of a window) are left out of the risk measures, because a two-day week is not comparable
    with a five-day week. Their trading and financing costs are not dropped: they are carried
    into the nearest kept week (the next one, or the previous one at the end of the window),
    so the weekly costs add up to the daily ledger's costs, including the cost of establishing
    the first hedge and of closing the last one."""
    df = ledger[["gross_pnl", "net_pnl", "mbs_pnl", "hedge_pnl", "cost", "financing"]].copy()
    df["dy"] = daily.loc[ledger.index, dy_col]
    g = df.groupby(pd.Grouper(freq="W-FRI"))
    out = g.sum(min_count=1)
    out["n_days"] = g["gross_pnl"].count()
    out = out[out["n_days"] > 0]
    return carry_costs(out, (out["n_days"] >= min_days).to_numpy())


def carry_costs(weekly_df: pd.DataFrame, keep: np.ndarray) -> pd.DataFrame:
    """Keep the rows marked in `keep`, moving the trading and financing costs of every dropped
    row into the next kept row (or the previous one after the last kept row), so that no cost
    disappears when weeks are dropped. Net P&L is recomputed from gross P&L and costs."""
    keep = np.asarray(keep, dtype=bool)
    out = weekly_df.copy()
    kept = np.flatnonzero(keep)
    if len(kept) == 0:
        return out.iloc[0:0]
    drop = np.flatnonzero(~keep)
    if len(drop):
        cols = [out.columns.get_loc(c) for c in ("cost", "financing")]
        for i in drop:
            later = kept[kept > i]
            target = later[0] if len(later) else kept[kept < i][-1]
            for c in cols:
                val = out.iat[i, c]
                if np.isfinite(val):
                    out.iat[target, c] = out.iat[target, c] + val
        out["net_pnl"] = out["gross_pnl"] - out["cost"] - out["financing"]
    return out[keep]
