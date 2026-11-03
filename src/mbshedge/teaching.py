"""Deterministic teaching example: why a mortgage hedge goes stale.

Everything here is ASSUMED behavior chosen for clarity. None of it is estimated from data.

Part A: cash flows (transparent amortization arithmetic)
    A pool of 30-year fixed-rate mortgages with a 6.5% note rate passes a 6.0% coupon to
    investors (the 0.5% difference pays servicing and the guarantee fee). Borrowers prepay
    at a constant annual rate (CPR). Faster prepayment returns principal sooner, which
    shortens the weighted-average life and the duration of the cash flows.

Part B: a stylized exposure model
    Prepayment speed depends on the refinancing incentive (note rate minus the current
    mortgage rate) through an S-curve. In a yield scenario y the current mortgage rate is
    y + 1.7%, so the incentive, the CPR, the projected cash flows, and their duration all
    depend on y. We use the duration of the projected cash flows, D(y), as the pool's price
    sensitivity at y and build the price curve by integrating it:

        log P(y) - log P(y0) = - integral from y0 to y of D(u) du

    Convexity then follows the identity C = D^2 - dD/dy. Where duration rises with yields
    (dD/dy > D^2), convexity is negative. A real desk model averages over many rate paths
    (option-adjusted analysis). This sketch keeps only the mechanism.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .instruments import bond_full_price, par_bond_modified_duration

MORTGAGE_SPREAD = 0.017     # current mortgage rate minus 10-year Treasury yield (assumed)
DISCOUNT_SPREAD = 0.012     # MBS discount rate minus 10-year Treasury yield (assumed)
NOTE_RATE, COUPON = 0.065, 0.060


def cpr_s_curve(incentive_pp, turnover: float = 0.06, max_refi: float = 0.45, center_pp: float = 0.75,
                width_pp: float = 0.35):
    """Annual prepayment rate given the refinancing incentive in percentage points."""
    x = np.asarray(incentive_pp, dtype=float)
    return turnover + max_refi / (1.0 + np.exp(-(x - center_pp) / width_pp))


def pool_cashflows(cpr: float, note_rate: float = NOTE_RATE, coupon: float = COUPON, wam_months: int = 360,
                   balance: float = 100.0) -> pd.DataFrame:
    """Monthly investor cash flows of a level-payment pool with a constant CPR."""
    smm = 1.0 - (1.0 - cpr) ** (1.0 / 12.0)
    r = note_rate / 12.0
    rows, b = [], balance
    for t in range(1, wam_months + 1):
        n_left = wam_months - t + 1
        pmt = b * r / (1.0 - (1.0 + r) ** (-n_left))
        sched = pmt - b * r
        prepay = (b - sched) * smm
        rows.append({"month": t, "balance_start": b, "interest": b * coupon / 12.0, "scheduled": sched,
                     "prepaid": prepay})
        b -= sched + prepay
    df = pd.DataFrame(rows)
    df["cashflow"] = df["interest"] + df["scheduled"] + df["prepaid"]
    return df


def cashflow_measures(cf: pd.DataFrame, discount_rate: float) -> dict:
    """Weighted-average life, price, and modified duration of projected cash flows."""
    t = cf["month"].to_numpy() / 12.0
    principal = (cf["scheduled"] + cf["prepaid"]).to_numpy()
    disc = (1.0 + discount_rate / 12.0) ** (-cf["month"].to_numpy())
    pv = cf["cashflow"].to_numpy() * disc
    price = pv.sum()
    macaulay = (pv * t).sum() / price
    return {"wal_years": float((principal * t).sum() / principal.sum()), "price": float(price),
            "duration": float(macaulay / (1.0 + discount_rate / 12.0))}


def scenario_table(yields: np.ndarray, base_yield: float = 0.048, **cpr_kw) -> pd.DataFrame:
    """Incentive, CPR, life, duration, price index, and convexity across yield scenarios."""
    ys = np.sort(np.asarray(yields, dtype=float))
    rows = []
    for y in ys:
        inc = 100.0 * (NOTE_RATE - (y + MORTGAGE_SPREAD))
        cpr = float(cpr_s_curve(inc, **cpr_kw))
        m = cashflow_measures(pool_cashflows(cpr), y + DISCOUNT_SPREAD)
        rows.append({"treasury_yield_pct": 100 * y, "incentive_pp": inc, "cpr_pct": 100 * cpr,
                     "wal_years": m["wal_years"], "mbs_duration": m["duration"]})
    df = pd.DataFrame(rows)
    # price index from integrating duration (trapezoid rule), scaled to 100 at the base yield
    y = ys
    d = df["mbs_duration"].to_numpy()
    logp = np.concatenate([[0.0], -np.cumsum(0.5 * (d[1:] + d[:-1]) * np.diff(y))])
    logp -= np.interp(base_yield, y, logp)
    df["mbs_price_index"] = 100 * np.exp(logp)
    df["mbs_convexity"] = d ** 2 - np.gradient(d, y)
    # 10-year Treasury with its coupon fixed at the base yield (fixed cash flows)
    h = 1e-4
    t0 = bond_full_price(base_yield, 10.0, base_yield)[0]
    tp = bond_full_price(base_yield, 10.0, y)
    up = bond_full_price(base_yield, 10.0, y + h)
    dn = bond_full_price(base_yield, 10.0, y - h)
    df["treasury_price_index"] = 100 * tp / t0
    df["treasury_duration"] = (dn - up) / (2 * h * tp)
    df["treasury_convexity"] = (up + dn - 2 * tp) / (h ** 2 * tp)
    return df


def stale_hedge_pnl(shifts_bp: np.ndarray, base_yield: float = 0.048, notional: float = 100e6,
                    **cpr_kw) -> pd.DataFrame:
    """$notional of MBS hedged with a 10-year Treasury sized by DV01 at the base yield and never
    adjusted. Instantaneous parallel shifts. Negative P&L in both directions = short convexity."""
    grid = np.round(np.arange(base_yield - 0.03, base_yield + 0.0301, 0.0005), 6)
    tab = scenario_table(grid, base_yield, **cpr_kw).set_index("treasury_yield_pct")
    y0 = round(100 * base_yield, 4)
    d0 = float(np.interp(y0, tab.index, tab["mbs_duration"]))
    dt0 = float(par_bond_modified_duration(base_yield, 10.0)[0])
    h0 = d0 / dt0
    rows = []
    for s in shifts_bp:
        yy = y0 + s / 100.0
        mbs_ret = np.interp(yy, tab.index, tab["mbs_price_index"]) / 100 - 1
        tr_ret = np.interp(yy, tab.index, tab["treasury_price_index"]) / 100 - 1
        d_new = np.interp(yy, tab.index, tab["mbs_duration"])
        rows.append({"shift_bp": s, "mbs_pnl_usd": notional * mbs_ret, "hedge_pnl_usd": -h0 * notional * tr_ret,
                     "hedged_pnl_usd": notional * (mbs_ret - h0 * tr_ret), "mbs_duration_after": d_new,
                     "required_hedge_ratio_after": d_new / par_bond_modified_duration(yy / 100, 10.0)[0],
                     "hedge_ratio_held": h0})
    out = pd.DataFrame(rows)
    out.attrs["initial_duration"] = d0
    out.attrs["initial_hedge_ratio"] = h0
    return out
