"""Labeled synthetic worlds for the smoke run and for simulation studies.

Nothing generated here is market data. A synthetic world mimics the *formats* and the
broad *shape* of 2006-2026 rate history (a stylized yield path through rough historical
anchor levels) so the whole pipeline can be exercised without network access, and so
estimators can be checked against a known truth.

What is known by construction (saved as `truth`):
* the true daily empirical duration of the MBS portfolio,
* the true stock note rate, incentive, and share of borrowers in the money.

Scenarios
---------
"state"      duration responds to refinancing conditions with a lag of a few weeks
"constant"   duration is constant (4.5 years), so no hedge should beat the static one
             ("null" is accepted as an older name for this scenario)
"unrelated"  duration moves about as much, and as persistently, as in "state", but along
             its own random path that is independent of rates and refinancing. Updating
             helps, and refinancing information should add nothing beyond updating.

Every file written by `write_raw_files` is recorded in the manifest with provider
"synthetic" and synthetic=True, and every figure made in smoke mode is watermarked.
"""
from __future__ import annotations

import io
import zipfile

import numpy as np
import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, GoodFriday, Holiday, USColumbusDay,
                                    USFederalHolidayCalendar, USMartinLutherKingJr, USMemorialDay,
                                    USPresidentsDay, USLaborDay, USThanksgivingDay, nearest_workday)
from scipy.interpolate import PchipInterpolator
from scipy.stats import norm

# ----------------------------------------------------------------------------
# Calendars (approximations, adequate for synthetic data)
# ----------------------------------------------------------------------------


class _EquityHolidays(AbstractHolidayCalendar):
    rules = [
        Holiday("NewYearsDay", month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-06-19", observance=nearest_workday),
        Holiday("July4th", month=7, day=4, observance=nearest_workday),
        USLaborDay, USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


class _GoodFridayOnly(AbstractHolidayCalendar):
    rules = [GoodFriday]


def calendars(start: str, end: str) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex, pd.DatetimeIndex]:
    """(all weekdays, bond-market days, equity-market days). Bond holidays include
    Columbus Day and Veterans Day, when the stock market is open."""
    weekdays = pd.bdate_range(start, end)
    fed = USFederalHolidayCalendar().holidays(start, end)
    good_friday = _GoodFridayOnly().holidays(start, end)
    bond_days = weekdays.difference(fed.union(good_friday))
    eq_days = weekdays.difference(_EquityHolidays().holidays(start, end))
    return weekdays, bond_days, eq_days


# ----------------------------------------------------------------------------
# Stylized anchor paths (percent). Loosely shaped like history, then perturbed.
# ----------------------------------------------------------------------------
Y10_ANCHORS = [("2006-01-01", 4.4), ("2007-06-15", 5.1), ("2008-06-15", 4.0), ("2008-12-20", 2.3),
               ("2009-06-10", 3.8), ("2010-10-10", 2.5), ("2011-03-01", 3.5), ("2012-07-20", 1.5),
               ("2013-05-01", 1.7), ("2013-09-05", 2.95), ("2015-01-30", 1.7), ("2016-07-05", 1.4),
               ("2016-12-15", 2.55), ("2018-11-08", 3.2), ("2019-09-01", 1.5), ("2020-01-15", 1.8),
               ("2020-03-09", 0.55), ("2020-08-04", 0.55), ("2021-03-31", 1.7), ("2021-12-01", 1.45),
               ("2022-06-14", 3.45), ("2022-10-21", 4.25), ("2023-04-05", 3.3), ("2023-10-19", 4.95),
               ("2024-04-25", 4.7), ("2024-09-16", 3.65), ("2025-01-14", 4.8), ("2025-09-15", 4.05),
               ("2026-05-15", 4.6), ("2026-10-30", 5.1)]
S5_ANCHORS = [("2006-01-01", 0.05), ("2009-06-01", 1.2), ("2013-09-01", 1.2), ("2016-07-01", 0.4),
              ("2019-09-01", 0.1), ("2021-03-31", 0.8), ("2022-10-21", 0.0), ("2023-10-19", 0.1),
              ("2024-09-16", 0.25), ("2026-10-30", 0.25)]
S2_ANCHORS = [("2006-01-01", 0.0), ("2008-12-20", 1.5), ("2010-10-10", 2.1), ("2013-09-05", 2.5),
              ("2016-07-01", 0.8), ("2019-09-01", 0.0), ("2021-03-31", 1.55), ("2022-10-21", -0.4),
              ("2023-04-05", -0.6), ("2024-09-16", 0.1), ("2026-10-30", 0.45)]
BILL_ANCHORS = [("2006-01-01", 4.1), ("2007-07-15", 4.9), ("2008-03-20", 1.3), ("2009-01-01", 0.1),
                ("2015-11-01", 0.1), ("2016-12-20", 0.5), ("2018-12-20", 2.4), ("2019-10-30", 1.6),
                ("2020-03-20", 0.05), ("2022-02-28", 0.35), ("2022-12-20", 4.4), ("2023-07-30", 5.45),
                ("2024-08-01", 5.25), ("2024-12-20", 4.3), ("2025-10-30", 3.9), ("2026-10-30", 4.2)]
PMMS_SPREAD_ANCHORS = [("1990-01-01", 1.7), ("2006-01-01", 1.8), ("2008-12-20", 2.6), ("2010-06-01", 1.7),
                       ("2013-06-01", 1.6), ("2016-06-01", 1.8), ("2020-03-20", 2.35), ("2020-12-20", 1.85),
                       ("2022-06-14", 2.5), ("2023-06-15", 3.0), ("2025-01-14", 2.35), ("2026-10-30", 2.2)]
PRE_2006_Y10 = [("1995-01-01", 7.6), ("1998-10-01", 4.6), ("2000-01-15", 6.6), ("2003-06-13", 3.2),
                ("2004-06-01", 4.8), ("2006-01-01", 4.4)]


def _days(dates) -> np.ndarray:
    """Days since 1970-01-01 as floats, independent of the datetime resolution (ns or us)."""
    return np.asarray((pd.DatetimeIndex(dates) - pd.Timestamp("1970-01-01")) / pd.Timedelta(days=1), dtype=float)


def _anchor_path(anchors, dates: pd.DatetimeIndex) -> np.ndarray:
    ax = _days(pd.to_datetime([a[0] for a in anchors]))
    ay = np.array([a[1] for a in anchors], dtype=float)
    x = _days(dates)
    x = np.clip(x, ax.min(), ax.max())
    return PchipInterpolator(ax, ay)(x)


def _vol_regime(dates: pd.DatetimeIndex, spikes: list[tuple[str, str, float]]) -> np.ndarray:
    v = np.ones(len(dates))
    for a, b, mult in spikes:
        v[(dates >= a) & (dates <= b)] = mult
    return v


def _t_noise(rng: np.random.Generator, n: int, df: float = 5.0) -> np.ndarray:
    return rng.standard_t(df, size=n) / np.sqrt(df / (df - 2.0))


def _smooth_random_path(rng: np.random.Generator, n: int, halflife_ar: float = 250.0,
                        halflife_smooth: float = 30.0) -> np.ndarray:
    """A standardized, smooth, persistent random path: an AR(1) with a half-life of
    `halflife_ar` trading days, smoothed by an EWMA with a half-life of `halflife_smooth` days.
    With the defaults, the duration path built from it matches the 'state' scenario's
    standard deviation (about 1.2 years), the size of its month-to-month changes (about
    0.21 years), and its autocorrelation at 1 and 12 months (about 0.98 and 0.45)."""
    phi = 0.5 ** (1.0 / halflife_ar)
    e = rng.standard_normal(n)
    z = np.zeros(n)
    for i in range(1, n):
        z[i] = phi * z[i - 1] + np.sqrt(1.0 - phi ** 2) * e[i]
    lam = 0.5 ** (1.0 / halflife_smooth)
    s = np.empty(n)
    s[0] = z[0]
    for i in range(1, n):
        s[i] = lam * s[i - 1] + (1.0 - lam) * z[i]
    return (s - s.mean()) / s.std()


# ----------------------------------------------------------------------------
# World generation
# ----------------------------------------------------------------------------
def make_world(seed: int, scenario: str = "state", start: str = "2006-01-02", end: str = "2026-10-30",
               mbs_first_trade: str = "2007-03-16", lag_halflife_days: float = 15.0,
               d_out: float = 6.0, d_in: float = 1.7, null_duration: float = 4.5,
               unrelated_mean: float = 5.0, unrelated_sd: float = 1.15,
               spread_noise_bp: float = 7.0) -> dict:
    """Generate one synthetic world. Returns parsed tables in the same layout that
    `sources.load_raw_tables` produces, plus `truth`."""
    if scenario == "null":
        scenario = "constant"
    if scenario not in ("state", "constant", "unrelated"):
        raise ValueError("scenario must be 'state', 'constant', or 'unrelated'")
    rng = np.random.default_rng(seed)
    weekdays, bond_days, eq_days = calendars(start, end)

    # --- yields on all weekdays (true values), observed on bond days ---------------
    yvol = _vol_regime(weekdays, [("2008-09-01", "2009-06-30", 2.0), ("2020-03-01", "2020-05-31", 1.8),
                                  ("2022-01-01", "2022-12-31", 1.6), ("2023-01-01", "2023-12-31", 1.3)])
    shocks = 0.045 * yvol * _t_noise(rng, len(weekdays))
    x = np.zeros(len(weekdays))
    for i in range(1, len(weekdays)):
        x[i] = 0.985 * x[i - 1] + shocks[i]
    y10 = _anchor_path(Y10_ANCHORS, weekdays) + x
    closed = ~weekdays.isin(bond_days)
    # when the bond market is closed the true yield does not move
    for i in np.where(closed)[0]:
        if i > 0:
            y10[i] = y10[i - 1]
    e5 = np.zeros(len(weekdays))
    z5 = 0.01 * rng.standard_normal(len(weekdays))
    for i in range(1, len(weekdays)):
        e5[i] = 0.9 * e5[i - 1] + z5[i]
    y5 = y10 - _anchor_path(S5_ANCHORS, weekdays) + e5
    y2 = y10 - _anchor_path(S2_ANCHORS, weekdays) + 0.03 * rng.standard_normal(len(weekdays))
    bill = np.maximum(_anchor_path(BILL_ANCHORS, weekdays) + 0.02 * rng.standard_normal(len(weekdays)), 0.0)

    # --- PMMS weekly (Thursday release), from 1995 for the stock-rate history -------
    thursdays = pd.date_range("1995-01-05", end, freq="W-THU")
    pre = _anchor_path(PRE_2006_Y10, thursdays)
    y10_s = pd.Series(y10, index=weekdays)
    weekly_avg = y10_s.rolling(5, min_periods=1).mean().reindex(thursdays, method="ffill").to_numpy()
    y10_thu = np.where(thursdays < weekdays[0], pre, weekly_avg)
    pmms = y10_thu + _anchor_path(PMMS_SPREAD_ANCHORS, thursdays) + 0.04 * rng.standard_normal(len(thursdays))
    pmms = np.round(pmms, 2)

    # --- true stock note rate: refinancing pulls it toward PMMS, lock-in slows it ----
    stock = np.empty(len(thursdays))
    stock[0] = 8.0
    for w in range(1, len(thursdays)):
        inc = stock[w - 1] - pmms[w - 1]
        replace_per_year = 0.06 + 0.45 * norm.cdf((inc - 0.75) / 0.5)
        stock[w] = stock[w - 1] + (replace_per_year / 52.0) * (pmms[w - 1] - stock[w - 1])
    stock_s = pd.Series(stock, index=thursdays)
    pmms_s = pd.Series(pmms, index=thursdays)

    # --- true duration path on weekdays ---------------------------------------------
    inc_daily = (stock_s - pmms_s).reindex(weekdays, method="ffill").bfill().to_numpy()
    rs_true = norm.cdf((inc_daily - 0.6) / 1.0)
    lam = 0.5 ** (1.0 / lag_halflife_days)
    rs_lag = np.empty_like(rs_true)
    rs_lag[0] = rs_true[0]
    for i in range(1, len(rs_true)):
        rs_lag[i] = lam * rs_lag[i - 1] + (1 - lam) * rs_true[i]
    drift = np.zeros(len(weekdays))
    dz = 0.012 * rng.standard_normal(len(weekdays))
    for i in range(1, len(weekdays)):
        drift[i] = 0.999 * drift[i - 1] + dz[i]
    if scenario == "state":
        d_true = d_out - (d_out - d_in) * rs_lag + drift + 0.3
    elif scenario == "unrelated":
        # a separate generator keeps every other random draw identical to the other scenarios
        path = _smooth_random_path(np.random.default_rng([seed, 17]), len(weekdays))
        d_true = unrelated_mean + unrelated_sd * path + drift
    else:
        d_true = np.full(len(weekdays), null_duration)
    convexity = -3.0 * norm.pdf((inc_daily - 0.6) / 1.0) / norm.pdf(0.0)

    # --- MBS excess returns on weekdays, observed on equity days ---------------------
    dy = np.diff(y10, prepend=y10[0]) / 100.0
    dy_lag = np.concatenate([[0.0], dy[:-1]])
    d_prev = np.concatenate([[d_true[0]], d_true[:-1]])
    d_prev2 = np.concatenate([[d_true[0]], d_prev[:-1]])
    svol = _vol_regime(weekdays, [("2008-09-01", "2009-06-30", 3.0), ("2020-03-01", "2020-04-30", 4.0),
                                  ("2022-01-01", "2022-12-31", 1.5)])
    eps = (spread_noise_bp / 1e4) * svol * _t_noise(rng, len(weekdays))
    a_lag = 0.12
    carry = 0.006 / 252
    r_ex = -(1 - a_lag) * d_prev * dy - a_lag * d_prev2 * dy_lag + 0.5 * convexity * dy ** 2 + eps + carry

    # VMBS and PMBS: correlated portfolios with their own noise (PDMIX is added after the price loop)
    eps_v = 0.9 * eps + np.sqrt(1 - 0.81) * (spread_noise_bp / 1e4) * svol * _t_noise(rng, len(weekdays))
    r_ex_v = -(1 - a_lag) * (1.02 * d_prev + 0.1) * dy - a_lag * (1.02 * d_prev2 + 0.1) * dy_lag + eps_v + carry
    eps_p = 0.8 * eps + 0.6 * (spread_noise_bp / 1e4) * svol * _t_noise(rng, len(weekdays))
    r_ex_p = -(1 - a_lag) * (0.9 * d_prev) * dy - a_lag * (0.9 * d_prev2) * dy_lag + eps_p + carry

    # daily bill accrual (for total returns) and price construction on equity days
    gaps = np.diff(_days(weekdays), prepend=_days(weekdays)[0])
    rf = np.concatenate([[0.0], bill[:-1] / 100.0 * gaps[1:] / 365.0])

    prices = {}
    for ticker, rex, first, p0, extra_dup in [("MBB", r_ex, mbs_first_trade, 100.86, False),
                                              ("VMBS", r_ex_v, "2009-11-23", 50.0, True),
                                              ("PMBS", r_ex_p, "2024-09-23", 50.0, False)]:
        prices[ticker] = _price_table(weekdays, eq_days, rex + rf, first, p0, stock_s, rng, extra_dup)
    # PIMCO GNMA fund (PDMIX): a mutual fund priced at NAV, so no premium or discount. A separate
    # generator keeps every draw above, and therefore every other series, unchanged.
    rng_g = np.random.default_rng([seed, 23])
    eps_g = 0.7 * eps + 0.7 * (spread_noise_bp / 1e4) * svol * _t_noise(rng_g, len(weekdays))
    r_ex_g = (-(1 - a_lag) * (0.85 * d_prev) * dy - a_lag * (0.85 * d_prev2) * dy_lag
              + 0.4 * convexity * dy ** 2 + eps_g + carry)
    prices["PDMIX"] = _price_table(weekdays, eq_days, r_ex_g + rf, "1997-07-31", 10.5, stock_s, rng_g, False, etf=False)

    # --- FRED-style tables -------------------------------------------------------------
    obs = pd.Index(weekdays).isin(bond_days)
    fred = {}
    for sid, vals in [("DGS10", y10), ("DGS5", y5), ("DGS2", y2), ("DGS3MO", bill)]:
        v = np.where(obs, np.round(vals, 2), np.nan)
        fred[sid] = pd.DataFrame({"date": weekdays.astype("datetime64[ns]"), "value": v})
    pm_dates = pd.DatetimeIndex([d if d in bond_days or d < weekdays[0] else d - pd.Timedelta(days=1)
                                 for d in thursdays])
    fred["MORTGAGE30US"] = pd.DataFrame({"date": pm_dates.astype("datetime64[ns]"), "value": pmms})

    nmdb = _nmdb_table(stock_s, end, rng)

    truth = pd.DataFrame({
        "y10": y10, "dy10_true": dy, "duration_true": d_true, "share_in_money_true": rs_true,
        "share_in_money_lagged_true": rs_lag, "incentive_true_pp": inc_daily,
        "stock_rate_true": stock_s.reindex(weekdays, method="ffill").to_numpy(),
        "bond_market_open": obs, "equity_market_open": pd.Index(weekdays).isin(eq_days),
    }, index=weekdays.rename("date"))
    return {"fred": fred, "prices": prices, "nmdb": nmdb, "truth": truth,
            "meta": {"seed": seed, "scenario": scenario, "start": start, "end": end}}


def _price_table(weekdays, eq_days, total_ret, first_trade, p0, stock_s, rng, add_duplicate,
                 etf: bool = True) -> pd.DataFrame:
    """Build a Yahoo-style table: close (split-adjusted, not distribution-adjusted),
    monthly distributions on the first trading day of each month, Yahoo-style adjusted close,
    and, for an ETF, a small premium/discount around NAV (with a March 2020 dislocation).
    A mutual fund (etf=False) is priced at its NAV."""
    s = pd.Series(total_ret, index=weekdays)
    # compound weekday returns into equity-day returns (days the ETF does not trade are skipped)
    idx = (1.0 + s).cumprod()
    days = eq_days[eq_days >= first_trade]
    tr = idx.reindex(days).pct_change().fillna(0.0).to_numpy()
    n = len(days)
    month = days.to_period("M")
    first_of_month = np.r_[False, month[1:] != month[:-1]]
    first_of_month[:20] = False
    coupon = stock_s.reindex(days, method="ffill").bfill().to_numpy() - 1.0
    nav = np.empty(n)
    div = np.zeros(n)
    nav[0] = p0
    for i in range(1, n):
        gross = nav[i - 1] * (1.0 + tr[i])
        if first_of_month[i]:
            div[i] = round(nav[i - 1] * max(coupon[i], 0.5) / 100.0 / 12.0, 4)
        nav[i] = gross - div[i]
    prem = np.zeros(n)
    if etf:
        z = 0.0004 * rng.standard_normal(n)
        for i in range(1, n):
            prem[i] = 0.6 * prem[i - 1] + z[i]
        dis = (days >= "2020-03-09") & (days <= "2020-03-20")
        prem[dis] -= np.linspace(0.005, 0.035, dis.sum())
        rec = (days > "2020-03-20") & (days <= "2020-04-15")
        prem[rec] -= np.linspace(0.02, 0.0, rec.sum())
    close = np.round(nav * (1.0 + prem), 2)
    # Yahoo-style adjustment: each distribution scales all earlier prices by (1 - div / prior close)
    factor = np.ones(n)
    for i in range(n - 1, 0, -1):
        if div[i] > 0:
            factor[:i] *= (1.0 - div[i] / close[i - 1])
    adj = close * factor
    df = pd.DataFrame({"date": days.astype("datetime64[ns]"), "close": close, "adj_close": adj,
                       "dividend": div, "split_factor": 1.0})
    if add_duplicate and n > 100:
        df = pd.concat([df, df.iloc[[100]]]).sort_values("date", kind="stable").reset_index(drop=True)
    return df


def _nmdb_table(stock_s: pd.Series, end: str, rng: np.random.Generator) -> pd.DataFrame:
    """NMDB-style national rows (long format) for 2013Q1 through the last released quarter."""
    last_q = (pd.Timestamp(end).to_period("Q") - 2)
    quarters = pd.period_range("2013Q1", last_q, freq="Q")
    q_end = quarters.to_timestamp(how="end").normalize()
    s_q = stock_s.reindex(q_end, method="ffill").to_numpy()
    rows = []
    markets = {"All Mortgages": 0.3, "Enterprise Acquisitions": -0.05, "Government / Non-Conventional": 0.0,
               "Other Conventional Market": 1.0}
    upb0 = {"Enterprise Acquisitions": 4560.0, "Government / Non-Conventional": 1490.0,
            "Other Conventional Market": 2560.0}
    growth = {"Enterprise Acquisitions": 0.02, "Government / Non-Conventional": 0.03,
              "Other Conventional Market": -0.01}
    edges = [(-np.inf, 3.0, "PCT_INTRATE_LT_3"), (3.0, 4.0, "PCT_INTRATE_3_4"), (4.0, 5.0, "PCT_INTRATE_4_5"),
             (5.0, 6.0, "PCT_INTRATE_5_6"), (6.0, np.inf, "PCT_INTRATE_GE_6")]
    for j, (q, qe) in enumerate(zip(quarters, q_end)):
        t = j / 4.0
        upb = {m: upb0[m] * (1 + growth[m]) ** t for m in upb0}
        upb["All Mortgages"] = sum(upb.values())
        for m, off in markets.items():
            mean2 = s_q[j] + off + 0.02 * rng.standard_normal()
            mean1 = mean2 + 0.3
            base = {"period": str(q), "market": m, "suppressed": 0, "quarter_end": qe}
            rows.append({**base, "series": "AVE_INTRATE", "value1": round(mean1, 1), "value2": round(mean2, 1)})
            rows.append({**base, "series": "TOT_UPB", "value1": round(upb[m], 1), "value2": round(upb[m], 1)})
            for lo, hi, sid in edges:
                p2 = (norm.cdf((hi - mean2) / 1.1) - norm.cdf((lo - mean2) / 1.1)) * 100
                p1 = (norm.cdf((hi - mean1) / 1.1) - norm.cdf((lo - mean1) / 1.1)) * 100
                rows.append({**base, "series": sid, "value1": round(p1, 1), "value2": round(p2, 1)})
    df = pd.DataFrame(rows)
    df["quarter_end"] = pd.to_datetime(df["quarter_end"]).astype("datetime64[ns]")
    return df.sort_values(["series", "market", "quarter_end"]).reset_index(drop=True)


# ----------------------------------------------------------------------------
# Writing a world to disk in the exact raw formats of the real sources
# ----------------------------------------------------------------------------
def fred_csv_bytes(df: pd.DataFrame, series_id: str) -> bytes:
    out = pd.DataFrame({"observation_date": df["date"].dt.strftime("%Y-%m-%d"),
                        series_id: df["value"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")})
    return out.to_csv(index=False).encode()


def yfinance_csv_bytes(df: pd.DataFrame, rng: np.random.Generator) -> bytes:
    close = df["close"].to_numpy()
    opn = np.r_[close[0], close[:-1]]
    out = pd.DataFrame({
        "Date": df["date"].dt.strftime("%Y-%m-%d"), "Open": opn,
        "High": np.maximum(opn, close) * 1.001, "Low": np.minimum(opn, close) * 0.999,
        "Close": close, "Adj Close": df["adj_close"].to_numpy(),
        "Volume": rng.integers(2e5, 3e6, size=len(df)), "Dividends": df["dividend"].to_numpy(),
        "Stock Splits": 0.0, "Capital Gains": 0.0,
    })
    return out.to_csv(index=False).encode()


def nmdb_zip_bytes(nmdb: pd.DataFrame) -> bytes:
    """Write NMDB-style rows in the verified 14-column layout, plus a few Census rows that
    the parser must ignore."""
    recs = []
    for _, r in nmdb.iterrows():
        year, qtr = int(r["period"][:4]), int(r["period"][-1])
        for geolevel, geoid, geoname in [("National", "USA", "United States")] + (
                [("Census Division", "DENC", "East North Central")] if r["series"] == "AVE_INTRATE" else []):
            recs.append(["NMDB", "Quarterly", geolevel, geoid, geoname, r["market"], r["period"], year, qtr,
                         qtr * 3, int(r["suppressed"]), r["series"],
                         _fmt(r["value1"]), "" if r["series"] == "TOT_LOANS" else _fmt(r["value2"])])
    csv = pd.DataFrame(recs, columns=["SOURCE", "FREQUENCY", "GEOLEVEL", "GEOID", "GEONAME", "MARKET", "PERIOD",
                                      "YEAR", "QUARTER", "MONTH", "SUPPRESSED", "SERIESID", "VALUE1", "VALUE2"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("nmdb-outstanding-mortgage-statistics-national-census-areas-quarterly.csv",
                    csv.to_csv(index=False))
    return buf.getvalue()


def _fmt(v) -> str:
    if pd.isna(v):
        return ""
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def write_raw_files(world: dict, store, cfg: dict) -> None:
    """Save a synthetic world through the RawStore so the rest of the pipeline reads it
    exactly like real downloads. Every manifest row is marked synthetic."""
    rng = np.random.default_rng(world["meta"]["seed"] + 1)
    tag = f"SYNTHETIC seed={world['meta']['seed']} scenario={world['meta']['scenario']}"
    for sid, df in world["fred"].items():
        content = fred_csv_bytes(df, sid)
        store.save(f"fred_{sid}", "synthetic", tag, content, "csv", len(df), df["date"].min().date(),
                   df["date"].max().date(), "percent", "synthetic, FRED graph CSV layout", "as real", synthetic=True)
        store.add_status(f"fred_{sid}", "synthetic", "synthetic", tag)
    for ticker, df in world["prices"].items():
        content = yfinance_csv_bytes(df, rng)
        store.save(f"prices_{ticker}", "synthetic", tag, content, "csv", len(df), df["date"].min().date(),
                   df["date"].max().date(), "USD", "synthetic, yfinance CSV layout", "as real", synthetic=True)
        store.add_status(f"prices_{ticker}", "synthetic", "synthetic", tag)
    content = nmdb_zip_bytes(world["nmdb"])
    store.save("fhfa_nmdb_outstanding_national_census", "synthetic", tag, content, "zip", len(world["nmdb"]),
               world["nmdb"]["period"].min(), world["nmdb"]["period"].max(), "percent; $bn",
               "synthetic, verified NMDB 14-column layout", "as real", synthetic=True)
    store.add_status("fhfa_nmdb_outstanding_national_census", "synthetic", "synthetic", tag)
