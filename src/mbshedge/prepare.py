"""From raw tables to analysis panels, with availability-time alignment.

Key conventions
---------------
* Trading calendar: dates on which MBB has a close AND the 10-year yield is published.
  MBB returns across skipped days (for example Columbus Day, when the bond market is
  closed but the ETF trades) are compounded into the next calendar date, so returns and
  yield changes always cover the same interval.
* Units: yields in the panels are percent (as published); yield changes `dy10`, `dy5` are
  decimals (1 bp = 0.0001); returns are decimals; durations are years; the incentive is in
  percentage points.
* Excess returns subtract the 3-month bill accrual: rf = DGS3MO(previous date) / 100 * days / 365.
* Every state variable carries its economic observation date and its availability date.
  Joins use the availability date (`merge_asof`, direction="backward").
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from .instruments import par_bond_modified_duration, synthetic_bond_daily_returns

DATA_DICTIONARY = [
    # name, description, units, source, observation date, availability rule
    ("date", "Trading date: MBB close and 10-year yield both observed", "date", "Yahoo, FRED", "this date", "close of this date"),
    ("days", "Calendar days since the previous trading date", "days", "derived", "this date", "close"),
    ("tr_mbb", "MBB total return since the previous trading date, (close + distribution) / previous close - 1, compounded over skipped days", "decimal", "Yahoo closes and distributions", "this date", "close"),
    ("rf", "3-month bill accrual over the interval: DGS3MO(previous date) / 100 * days / 365", "decimal", "FRED DGS3MO", "previous date", "close"),
    ("r_mbb_ex", "MBB excess return: tr_mbb - rf", "decimal", "derived", "this date", "close"),
    ("y10, y5, y2, y3m", "Treasury constant-maturity yields", "percent", "FRED H.15", "this date", "market-observable at close"),
    ("dy10, dy5", "Change in the 10-year (5-year) yield since the previous trading date", "decimal (0.0001 = 1 bp)", "derived", "this date", "close"),
    ("r_h10, r_h5", "Total return of the daily-reset synthetic 10-year (5-year) par Treasury", "decimal", "derived from FRED yields", "this date", "close"),
    ("r_h10_ex, r_h5_ex", "Hedge-bond excess return over the bill accrual", "decimal", "derived", "this date", "close"),
    ("dur_h10, dur_h5", "Modified duration of a new par bond at the close", "years", "derived", "this date", "close"),
    ("tr_vmbs, r_vmbs_ex, tr_pmbs, r_pmbs_ex, tr_pdmix, r_pdmix_ex", "Same construction for VMBS, PMBS, and PIMCO's GNMA fund PDMIX (missing before inception). PDMIX is a mutual fund, so its close is the daily NAV", "decimal", "Yahoo", "this date", "close (NAV struck at 4 pm ET for PDMIX)"),
    ("pmms", "Latest Freddie Mac PMMS 30-year rate released on or before this date", "percent", "FRED MORTGAGE30US", "pmms_release_date", "Thursday release (12:00 ET), usable at that close"),
    ("stock_rate", "Average note rate on outstanding agency-eligible mortgages (UPB-weighted)", "percent", "FHFA NMDB, or the PMMS proxy before NMDB is available", "stock_rate_quarter_end", "stock_rate_available_from"),
    ("incentive", "Refinancing incentive: stock_rate - pmms", "percentage points", "derived", "this date", "max of input availability dates"),
    ("g", "Share of borrowers in the money: Phi((incentive - theta) / sigma)", "fraction 0 to 1", "derived", "this date", "as incentive"),
    ("incentive_source", "nmdb, or proxy_retrospective when the proxy (calibrated with 2013-2014 data) is used", "label", "derived", "this date", "n/a"),
]


def dictionary_frame() -> pd.DataFrame:
    return pd.DataFrame(DATA_DICTIONARY, columns=["column", "description", "units", "source",
                                                  "observation_date", "availability"])


def _dt(s) -> pd.Series:
    return pd.to_datetime(s).astype("datetime64[ns]")


# ----------------------------------------------------------------------------
# Prices -> total returns
# ----------------------------------------------------------------------------
def total_return_from_prices(prices: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Rebuild daily total returns from closes and ex-date distributions, and compare
    them with the provider's adjusted close (when present). Distributions are counted
    exactly once: we never add a distribution to an adjusted-close return."""
    p = prices.copy()
    n_before = len(p)
    p = p.drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
    dups = n_before - len(p)
    tr = (p["close"] + p["dividend"]) / p["close"].shift(1) - 1.0
    out = pd.DataFrame({"date": _dt(p["date"]), "close": p["close"], "dividend": p["dividend"], "tr": tr})
    info = {"rows": len(p), "duplicates_dropped": int(dups), "n_distributions": int((p["dividend"] > 0).sum()),
            "first_date": str(p["date"].min().date()), "last_date": str(p["date"].max().date())}
    if p["adj_close"].notna().sum() > 2:
        adj_ret = p["adj_close"] / p["adj_close"].shift(1) - 1.0
        both = tr.notna() & adj_ret.notna()           # compare like with like
        diff = (tr - adj_ret).abs()
        info.update({
            "adjclose_check_days_compared": int(both.sum()),
            "adjclose_check_max_abs_diff_bp": float(diff[both].max() * 1e4),
            "adjclose_check_days_over_1bp": int((diff[both] > 1e-4).sum()),
            "adjclose_check_dates_over_1bp": [str(x.date()) for x in p.loc[both & (diff > 1e-4), "date"].head(10)],
            "adjclose_check_cum_diff_bp_per_year": float(
                ((np.log1p(tr[both]).sum() - np.log1p(adj_ret[both]).sum()) / max(both.sum() / 252, 1e-9)) * 1e4),
        })
    big = tr.abs() > 0.03
    info["days_abs_return_over_3pct"] = int(big.sum())
    return out, info


MAX_ADJCLOSE_GAP_BP_PER_YEAR = 10.0

# Price series added to the daily panel next to MBB. A series that fails the total-return
# check is left out of the panel (and reported), never used.
SECONDARY_PRICE_SERIES = ["VMBS", "PMBS", "PDMIX"]


def check_total_return(info: dict, ticker: str, max_gap_bp_per_year: float = MAX_ADJCLOSE_GAP_BP_PER_YEAR) -> str | None:
    """Return a problem description when the rebuilt total return drifts away from the provider's
    adjusted close by more than `max_gap_bp_per_year` (about 1 bp a year is normal, because the
    two reinvest distributions at slightly different prices). A drift near the distribution yield
    (around 300 bp a year) means distributions were double counted or are missing."""
    gap = info.get("adjclose_check_cum_diff_bp_per_year")
    if gap is None or not np.isfinite(gap) or abs(gap) <= max_gap_bp_per_year:
        return None
    cause = ("the close already includes distributions (double counting)" if gap > 0
             else "distributions are missing from the file")
    return (f"{ticker}: the total return rebuilt from the close and distributions differs from the provider's "
            f"adjusted close by {gap:+.1f} bp per year (limit {max_gap_bp_per_year:g}). The likely cause is that {cause}. "
            f"Check the price file (see RUN_ME_FIRST.md, section 4) before using any result.")


def _compound_to_calendar(tr: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.Series:
    """Total return between consecutive calendar dates, compounding any skipped days."""
    idx = (1.0 + tr.set_index("date")["tr"].fillna(0.0)).cumprod()
    on_cal = idx.reindex(calendar)
    ret = on_cal / on_cal.shift(1) - 1.0
    first_obs = tr["date"].min()
    ret[calendar <= first_obs] = np.nan
    return ret


# ----------------------------------------------------------------------------
# Daily market panel
# ----------------------------------------------------------------------------
def build_daily_panel(tables: dict, primary: str = "MBB") -> tuple[pd.DataFrame, dict]:
    fred = tables["fred"]
    for sid in ["DGS10", "DGS3MO"]:
        if sid not in fred:
            raise ValueError(f"Essential series {sid} is missing. Run notebook 01.")
    if primary not in tables["prices"]:
        raise ValueError(f"Essential price series {primary} is missing. Run notebook 01.")
    quality = {}

    ylev = {}
    for sid in ["DGS10", "DGS5", "DGS2", "DGS3MO"]:
        if sid in fred:
            s = fred[sid].dropna(subset=["value"]).set_index("date")["value"]
            s.index = _dt(s.index)
            ylev[sid] = s
    tr_primary, info = total_return_from_prices(tables["prices"][primary])
    quality[f"prices_{primary}"] = info
    problem = check_total_return(info, primary)
    if problem:
        raise ValueError(problem)

    cal = pd.DatetimeIndex(sorted(set(tr_primary["date"]) & set(ylev["DGS10"].index)))
    cal = cal[cal >= tr_primary["date"].min()]
    quality["calendar"] = {"n_dates": len(cal), "first": str(cal.min().date()), "last": str(cal.max().date()),
                           f"{primary}_days_not_in_calendar": int(len(set(tr_primary['date']) - set(cal))),
                           "DGS10_days_not_in_calendar": int(len(set(ylev['DGS10'].index[ylev['DGS10'].index >= cal.min()]) - set(cal)))}

    d = pd.DataFrame(index=cal)
    d.index.name = "date"
    d["days"] = np.r_[np.nan, np.diff(np.asarray((cal - pd.Timestamp("1970-01-01")) / pd.Timedelta(days=1), dtype=float))]
    d["tr_mbb"] = _compound_to_calendar(tr_primary, cal)

    def on_cal(series: pd.Series, limit: int = 5) -> pd.Series:
        full = series.reindex(series.index.union(cal)).sort_index().ffill(limit=limit)
        return full.reindex(cal)

    d["y10"] = ylev["DGS10"].reindex(cal)
    d["y3m"] = on_cal(ylev["DGS3MO"])
    for sid, col in [("DGS5", "y5"), ("DGS2", "y2")]:
        if sid in ylev:
            d[col] = on_cal(ylev[sid])
    d["rf"] = d["y3m"].shift(1) / 100.0 * d["days"] / 365.0
    d["r_mbb_ex"] = d["tr_mbb"] - d["rf"]
    d["dy10"] = d["y10"].diff() / 100.0
    for tenor, col in [(10, "y10"), (5, "y5")]:
        if col not in d:
            continue
        y = d[col].to_numpy() / 100.0
        d[f"r_h{tenor}"] = synthetic_bond_daily_returns(y, d["days"].fillna(0).to_numpy(), tenor)
        d[f"r_h{tenor}_ex"] = d[f"r_h{tenor}"] - d["rf"]
        d[f"dur_h{tenor}"] = par_bond_modified_duration(y, tenor)
        d[f"dy{tenor}"] = d[col].diff() / 100.0

    for ticker in SECONDARY_PRICE_SERIES:
        if ticker in tables["prices"]:
            tr_t, info_t = total_return_from_prices(tables["prices"][ticker])
            quality[f"prices_{ticker}"] = info_t
            problem = check_total_return(info_t, ticker)
            if problem:   # a secondary series is dropped, not trusted
                info_t["excluded"] = problem
                continue
            col = ticker.lower()
            d[f"tr_{col}"] = _compound_to_calendar(tr_t, cal)
            d[f"r_{col}_ex"] = d[f"tr_{col}"] - d["rf"]

    d = d.iloc[1:]  # the first date has no return
    quality["missing_counts"] = {c: int(d[c].isna().sum()) for c in d.columns}
    return d, quality


# ----------------------------------------------------------------------------
# Refinancing state: PMMS, NMDB stock rate, proxy, incentive, share in the money
# ----------------------------------------------------------------------------
def nmdb_stock_rate(nmdb: pd.DataFrame, markets: list[str], value_col: str = "value2") -> pd.DataFrame:
    """Quarterly stock note rate for the chosen markets, combined by total unpaid balance."""
    rate = nmdb[(nmdb["series"] == "AVE_INTRATE") & (nmdb["market"].isin(markets))]
    upb = nmdb[(nmdb["series"] == "TOT_UPB") & (nmdb["market"].isin(markets))]
    if rate.empty:
        raise ValueError(f"NMDB has no AVE_INTRATE rows for markets {markets}. "
                         f"Available markets: {sorted(nmdb['market'].unique())}")
    absent = sorted(set(markets) - set(rate["market"].unique()))
    if absent:
        raise ValueError(f"NMDB has no AVE_INTRATE rows for markets {absent}. "
                         f"Available markets: {sorted(nmdb['market'].unique())}")
    r = rate.pivot_table(index="quarter_end", columns="market", values=value_col).reindex(columns=markets)
    if len(markets) == 1:
        s = r[markets[0]]
    else:
        w = upb.pivot_table(index="quarter_end", columns="market", values="value1").reindex(index=r.index, columns=markets)
        # A quarter counts only if every chosen market has both a rate and a positive balance.
        # Averaging over whichever markets happen to be present would change the mix and make
        # the rate jump for reasons unrelated to refinancing.
        complete = r.notna().all(axis=1) & w.notna().all(axis=1) & (w > 0).all(axis=1)
        s = ((r * w).sum(axis=1) / w.sum(axis=1)).where(complete)
    out = pd.DataFrame({"quarter_end": _dt(s.index), "stock_rate": s.to_numpy()}).dropna()
    if out["stock_rate"].between(0.5, 20).mean() < 0.99:
        raise ValueError("NMDB AVE_INTRATE values are not in percent as expected. Check the file layout.")
    return out


def nmdb_bucket_dispersion(nmdb: pd.DataFrame, markets: list[str], value_col: str = "value2") -> pd.DataFrame:
    """Standard deviation of note rates implied by the NMDB rate buckets, per quarter.
    Assumes rates are uniform within buckets, with the open buckets set to [2, 3) and [6, 8]."""
    buckets = {"PCT_INTRATE_LT_3": (2.0, 3.0), "PCT_INTRATE_3_4": (3.0, 4.0), "PCT_INTRATE_4_5": (4.0, 5.0),
               "PCT_INTRATE_5_6": (5.0, 6.0), "PCT_INTRATE_GE_6": (6.0, 8.0)}
    sub = nmdb[nmdb["series"].isin(buckets) & nmdb["market"].isin(markets)]
    if sub.empty:
        return pd.DataFrame(columns=["quarter_end", "mean_from_buckets", "sd_from_buckets"])
    upb = nmdb[(nmdb["series"] == "TOT_UPB") & (nmdb["market"].isin(markets))].pivot_table(
        index="quarter_end", columns="market", values="value1")
    rows = []
    for qe, g in sub.groupby("quarter_end"):
        shares = {}
        for b in buckets:
            gb = g[g["series"] == b].set_index("market")[value_col].reindex(markets)
            if len(markets) > 1 and qe in upb.index:
                w = upb.loc[qe].reindex(markets)
                ok = gb.notna().all() and w.notna().all() and (w > 0).all()
                shares[b] = float((gb * w).sum() / w.sum()) if ok else np.nan
            else:
                shares[b] = float(gb.mean()) if gb.notna().all() else np.nan
        p = np.array([shares[b] for b in buckets]) / 100.0
        if not np.isfinite(p).all() or p.sum() <= 0:
            continue
        p = p / p.sum()
        lo = np.array([buckets[b][0] for b in buckets])
        hi = np.array([buckets[b][1] for b in buckets])
        mid, var_in = (lo + hi) / 2.0, (hi - lo) ** 2 / 12.0
        mu = float((p * mid).sum())
        var = float((p * (var_in + mid ** 2)).sum() - mu ** 2)
        rows.append({"quarter_end": qe, "mean_from_buckets": mu, "sd_from_buckets": float(np.sqrt(max(var, 0)))})
    return pd.DataFrame(rows)


def pmms_ewma(pmms: pd.DataFrame, halflife_years: float) -> pd.Series:
    """Exponentially weighted average of past weekly PMMS releases (by release date)."""
    s = pmms.dropna(subset=["value"]).set_index("date")["value"].sort_index()
    lam = 0.5 ** (1.0 / (52.0 * halflife_years))
    vals = s.to_numpy()
    out = np.empty(len(vals))
    out[0] = vals[0]
    for i in range(1, len(vals)):
        out[i] = lam * out[i - 1] + (1 - lam) * vals[i]
    return pd.Series(out, index=_dt(s.index))


def calibrate_proxy(pmms: pd.DataFrame, stock_q: pd.DataFrame, available_by: pd.Timestamp,
                    lag_quarters: int, grid_years: list[float]) -> dict:
    """Choose the proxy half-life and level offset using only NMDB quarters whose
    availability date is on or before `available_by` (the end of development)."""
    sq = stock_q.copy()
    sq["available_from"] = availability_dates(sq["quarter_end"], lag_quarters)
    cal = sq[sq["available_from"] <= available_by]
    if len(cal) < 3:
        return {"status": "insufficient NMDB quarters for calibration", "halflife_years": None, "offset": None}
    best = None
    table = []
    for h in grid_years:
        e = pmms_ewma(pmms, h)
        at_q = e.reindex(e.index.union(cal["quarter_end"])).sort_index().ffill().reindex(cal["quarter_end"]).to_numpy()
        diff = cal["stock_rate"].to_numpy() - at_q
        offset = float(np.mean(diff))
        rmse = float(np.sqrt(np.mean((diff - offset) ** 2)))
        table.append({"halflife_years": h, "offset_pp": offset, "rmse_pp": rmse})
        if best is None or rmse < best["rmse_pp"]:
            best = {"halflife_years": h, "offset_pp": offset, "rmse_pp": rmse}
    return {"status": "ok", "halflife_years": best["halflife_years"], "offset": best["offset_pp"],
            "rmse_pp": best["rmse_pp"], "n_quarters": len(cal),
            "calibration_quarters": [str(q.date()) for q in cal["quarter_end"]], "grid": table}


def availability_dates(quarter_end: pd.Series, lag_quarters: int) -> pd.Series:
    """Quarter q becomes usable at the end of quarter q + lag (e.g. 2026Q2 -> 2026-09-30)."""
    per = pd.PeriodIndex(pd.to_datetime(quarter_end), freq="Q") + lag_quarters
    return pd.Series(per.to_timestamp(how="end").normalize().astype("datetime64[ns]"), index=quarter_end.index)


def build_state(calendar: pd.DatetimeIndex, pmms: pd.DataFrame, nmdb: pd.DataFrame | None, *,
                markets: list[str], lag_quarters: int, theta: float, sigma: float | None,
                development_end: pd.Timestamp, proxy_grid_years: list[float], sigma_default: float,
                proxy_params: dict | None = None, use_proxy: bool = True) -> tuple[pd.DataFrame, dict]:
    """Daily refinancing state on the trading calendar, using only information available
    at each date. Returns the state panel and a dict of the choices made (proxy calibration,
    sigma), which notebook 06 records in the freeze."""
    info = {"markets": markets, "lag_quarters": lag_quarters, "theta_pp": theta}
    cal = pd.DataFrame({"date": _dt(pd.Series(calendar))})

    pm = pmms.dropna(subset=["value"]).sort_values("date")
    pm = pd.DataFrame({"pmms_release_date": _dt(pm["date"]), "pmms": pm["value"].to_numpy()})
    st = pd.merge_asof(cal, pm, left_on="date", right_on="pmms_release_date", direction="backward")

    if nmdb is not None:
        sq = nmdb_stock_rate(nmdb, markets)
        sq["stock_rate_available_from"] = availability_dates(sq["quarter_end"], lag_quarters)
        sq = sq.sort_values("stock_rate_available_from")
        st = pd.merge_asof(st, sq.rename(columns={"quarter_end": "stock_rate_quarter_end",
                                                  "stock_rate": "stock_rate_nmdb"}),
                           left_on="date", right_on="stock_rate_available_from", direction="backward")
        if proxy_params is None:
            proxy_params = calibrate_proxy(pmms, sq, development_end, lag_quarters, proxy_grid_years)
        info["proxy"] = proxy_params
        disp = nmdb_bucket_dispersion(nmdb, markets)
        if sigma is None:
            if not disp.empty:
                disp["available_from"] = availability_dates(disp["quarter_end"], lag_quarters)
                dev = disp[disp["available_from"] <= development_end]
                sigma = round(float(dev["sd_from_buckets"].mean()), 1) if len(dev) else sigma_default
                info["sigma_source"] = f"NMDB rate buckets, {len(dev)} quarters available by {development_end.date()}"
            else:
                sigma = sigma_default
                info["sigma_source"] = "default (no bucket data)"
        else:
            info["sigma_source"] = "given"
        info["bucket_dispersion"] = disp
    else:
        st["stock_rate_nmdb"] = np.nan
        st["stock_rate_quarter_end"] = pd.NaT
        st["stock_rate_available_from"] = pd.NaT
        sigma = sigma if sigma is not None else sigma_default
        info["sigma_source"] = "default (NMDB unavailable)"
        info["proxy"] = proxy_params or {"status": "NMDB unavailable"}
    info["sigma_pp"] = sigma

    st["stock_rate"] = st["stock_rate_nmdb"]
    st["incentive_source"] = np.where(st["stock_rate"].notna(), "nmdb", "none")
    pp = info.get("proxy") or {}
    if use_proxy and pp.get("halflife_years") is not None:
        e = pmms_ewma(pmms, pp["halflife_years"]) + pp["offset"]
        prox = pd.DataFrame({"proxy_date": e.index, "stock_rate_proxy": e.to_numpy()})
        st = pd.merge_asof(st, prox, left_on="date", right_on="proxy_date", direction="backward")
        fill = st["stock_rate"].isna() & st["stock_rate_proxy"].notna()
        st.loc[fill, "stock_rate"] = st.loc[fill, "stock_rate_proxy"]
        st.loc[fill, "incentive_source"] = "proxy_retrospective"
        st = st.drop(columns=["proxy_date"])
    st["incentive"] = st["stock_rate"] - st["pmms"]
    st["g"] = norm.cdf((st["incentive"] - theta) / sigma)
    st = st.set_index("date")
    return st, info


# ----------------------------------------------------------------------------
# Monthly decision table
# ----------------------------------------------------------------------------
def month_end_table(daily: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Values at the last trading date of each calendar month (the decision date)."""
    month = daily.index.to_period("M")
    last = daily.groupby(month).tail(1)
    out = last[cols].copy()
    out["decision_date"] = last.index
    out.index = last.index.to_period("M")
    out.index.name = "month"
    return out


def weekly_sum(daily: pd.Series | pd.DataFrame, min_days: int = 1):
    """Sum over Friday-ending weeks; weeks with fewer than `min_days` observations are dropped."""
    g = daily.groupby(pd.Grouper(freq="W-FRI"))
    out = g.sum(min_count=1)
    cnt = g.count()
    if isinstance(cnt, pd.DataFrame):
        cnt = cnt.max(axis=1)
    return out[cnt >= min_days]
