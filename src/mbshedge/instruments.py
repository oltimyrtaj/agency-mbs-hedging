"""Synthetic constant-maturity par Treasury: pricing, duration, DV01, and daily returns.

Convention
----------
* Yields are decimals with semiannual compounding (bond-equivalent basis), as for
  H.15 constant-maturity yields. A 4.25% yield is 0.0425.
* The hedge bond is a T-year par bond. Each day it is reset: at the close of day t-1
  we hold a new T-year bond with coupon equal to that day's yield y_{t-1}, so it prices
  at 100. At the close of day t the bond has aged by dt years and is revalued at the new
  yield y_t. Its total return over the day is P_t / 100 - 1 (no coupon is paid within
  a day, and the price is the full price including accrued interest).
* Time is measured in years with dt = calendar days / 365.25.
* The flat-curve approximation: the aged bond (maturity T - dt) is discounted at the
  T-year yield. For dt of a few days the error is negligible.

This is a research approximation of a rolling 10-year Treasury position. It ignores
futures basis, cheapest-to-deliver switches, and roll costs (see docs/assumptions_limitations.md).
"""
from __future__ import annotations

import numpy as np

FREQ = 2  # coupons per year


def cashflow_times(tenor_years: float, dt_years: np.ndarray | float = 0.0) -> np.ndarray:
    """Times (years) of the coupon dates of a bond issued dt_years ago. Shape (n_days, n_cf)."""
    n_cf = int(round(tenor_years * FREQ))
    k = np.arange(1, n_cf + 1) / FREQ
    dt = np.atleast_1d(np.asarray(dt_years, dtype=float))
    return k[None, :] - dt[:, None]


def bond_full_price(coupon: np.ndarray | float, tenor_years: float, yld: np.ndarray | float,
                    dt_years: np.ndarray | float = 0.0) -> np.ndarray:
    """Full (dirty) price per 100 face of a bond with annual coupon rate `coupon`,
    original tenor `tenor_years`, issued `dt_years` ago, discounted at yield `yld`.

    Inputs broadcast against each other. `dt_years` must be shorter than one coupon
    period (true for daily ageing), so no coupon has been paid yet.
    """
    coupon, yld, dt = np.broadcast_arrays(
        np.atleast_1d(np.asarray(coupon, dtype=float)),
        np.atleast_1d(np.asarray(yld, dtype=float)),
        np.atleast_1d(np.asarray(dt_years, dtype=float)),
    )
    if np.any(dt >= 1.0 / FREQ):
        raise ValueError("dt_years must be shorter than one coupon period for this pricer")
    n_cf = int(round(tenor_years * FREQ))
    k = np.arange(1, n_cf + 1) / FREQ
    times = k[None, :] - dt[:, None]
    cf = np.broadcast_to((100.0 * coupon / FREQ)[:, None], times.shape).copy()
    cf[:, -1] += 100.0
    disc = (1.0 + yld[:, None] / FREQ) ** (-FREQ * times)
    return (cf * disc).sum(axis=1)


def par_bond_modified_duration(yld: np.ndarray | float, tenor_years: float) -> np.ndarray:
    """Modified duration (years) of a new T-year par bond at yield `yld`, from its cash flows."""
    yld = np.atleast_1d(np.asarray(yld, dtype=float))
    times = cashflow_times(tenor_years, 0.0)[0]
    cf = np.full((len(yld), len(times)), 0.0)
    cf[:] = 100.0 * yld[:, None] / FREQ
    cf[:, -1] += 100.0
    disc = (1.0 + yld[:, None] / FREQ) ** (-FREQ * times[None, :])
    pv = cf * disc
    price = pv.sum(axis=1)
    macaulay = (pv * times[None, :]).sum(axis=1) / price
    return macaulay / (1.0 + yld / FREQ)


def par_bond_modified_duration_closed_form(yld: np.ndarray | float, tenor_years: float) -> np.ndarray:
    """Closed form for a par bond: (1/y) * (1 - (1 + y/2)^(-2T)). Used to check the cash-flow version."""
    yld = np.atleast_1d(np.asarray(yld, dtype=float))
    return (1.0 - (1.0 + yld / FREQ) ** (-FREQ * tenor_years)) / yld


def dv01_per_100(coupon: float, tenor_years: float, yld: float, dt_years: float = 0.0, bump: float = 1e-4) -> float:
    """Price change per 100 face for a 1 bp fall in yield, by central finite difference."""
    up = bond_full_price(coupon, tenor_years, yld + bump, dt_years)[0]
    dn = bond_full_price(coupon, tenor_years, yld - bump, dt_years)[0]
    return (dn - up) / 2.0


def synthetic_bond_daily_returns(yields: np.ndarray, day_gaps: np.ndarray, tenor_years: float) -> np.ndarray:
    """Daily total returns of the daily-reset constant-maturity par bond.

    Parameters
    ----------
    yields : decimal yields on consecutive observation dates, shape (n,)
    day_gaps : calendar days between observation i-1 and i, shape (n,) (element 0 ignored)
    tenor_years : constant maturity, e.g. 10

    Returns
    -------
    returns : shape (n,), element 0 is NaN
    """
    yields = np.asarray(yields, dtype=float)
    gaps = np.asarray(day_gaps, dtype=float)
    out = np.full(len(yields), np.nan)
    if len(yields) < 2:
        return out
    coupon = yields[:-1]
    dt = gaps[1:] / 365.25
    price = bond_full_price(coupon, tenor_years, yields[1:], dt)
    out[1:] = price / 100.0 - 1.0
    return out
