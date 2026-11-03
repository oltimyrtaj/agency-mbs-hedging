"""The PIMCO NAV converter (tools/convert_pimco_nav.py) and the fund-comparison helper."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mbshedge.exposure import compare_exposure
from mbshedge.prepare import total_return_from_prices
from mbshedge.sources import parse_local_prices, parse_yahoo_chart_json, parse_yfinance_csv

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("convert_pimco_nav", ROOT / "tools" / "convert_pimco_nav.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)


def _fund(n=600, seed=3):
    """A NAV-priced fund with monthly distributions, and its exact daily total returns."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2012-01-03", periods=n)
    r = 0.0002 + 0.002 * rng.standard_normal(n)
    nav = np.empty(n); div = np.zeros(n); nav[0] = 10.5
    for i in range(1, n):
        if dates[i].month != dates[i - 1].month:
            div[i] = round(0.0025 * nav[i - 1], 4)
        nav[i] = nav[i - 1] * (1 + r[i]) - div[i]
    tr = (nav + div) / np.r_[np.nan, nav[:-1]] - 1
    return dates, nav, div, tr


def _roundtrip(out):
    """What notebook 09 does with the file: parse it and rebuild total returns."""
    parsed = parse_local_prices(out.to_csv(index=False).encode())
    tr, _ = total_return_from_prices(parsed)
    return tr.set_index("date")["tr"]


def test_crsp_layout_reproduces_daily_returns():
    dates, nav, div, tr = _fund()
    crsp = pd.DataFrame({"crsp_fundno": 12345, "caldt": dates.strftime("%Y%m%d").astype(int), "dnav": np.round(nav, 2), "dret": tr})
    out, rep = conv.convert(crsp)
    assert rep["layout"] == "daily total return" and rep["fund_id"] == "12345"
    got = _roundtrip(out)
    np.testing.assert_allclose(got.iloc[1:].to_numpy(), tr[1:], atol=1e-12)
    assert (out["dividend"] == 0).all()


def test_returns_in_percent_are_detected():
    dates, nav, div, tr = _fund()
    df = pd.DataFrame({"Date": dates, "NAV": nav, "Daily Total Return": 100 * tr})
    out, rep = conv.convert(df)
    assert any("percent" in x for x in rep["repairs"])
    np.testing.assert_allclose(_roundtrip(out).iloc[1:].to_numpy(), tr[1:], atol=1e-12)


def test_missing_return_uses_nav_change_and_is_reported():
    dates, nav, div, tr = _fund()
    tr2 = tr.copy(); tr2[100] = np.nan
    out, rep = conv.convert(pd.DataFrame({"caldt": dates, "dnav": nav, "dret": tr2}))
    assert any("NAV change" in x for x in rep["repairs"])
    got = _roundtrip(out)
    assert abs(got.iloc[100] - (nav[100] / nav[99] - 1)) < 1e-12


def test_nav_with_distributions_passes_through():
    dates, nav, div, tr = _fund()
    out, rep = conv.convert(pd.DataFrame({"date": dates, "nav": nav, "dividend": div}))
    assert rep["layout"] == "NAV with distributions" and rep["n_distributions"] == int((div > 0).sum())
    np.testing.assert_allclose(_roundtrip(out).iloc[1:].to_numpy(), tr[1:], atol=1e-12)


def test_separate_distribution_file_is_merged():
    dates, nav, div, tr = _fund()
    nav_df = pd.DataFrame({"Date": dates, "PX_LAST": nav})
    dist = pd.DataFrame({"Ex Date": dates[div > 0], "Amount": div[div > 0]})
    out, rep = conv.convert(nav_df, dist)
    np.testing.assert_allclose(_roundtrip(out).iloc[1:].to_numpy(), tr[1:], atol=1e-12)


def test_nav_alone_is_refused():
    dates, nav, _, _ = _fund()
    with pytest.raises(conv.ConversionError, match="misses every distribution"):
        conv.convert(pd.DataFrame({"date": dates, "nav": nav}))


def test_several_funds_need_a_choice():
    dates, nav, div, tr = _fund()
    a = pd.DataFrame({"crsp_fundno": 1, "caldt": dates, "dnav": nav, "dret": tr})
    both = pd.concat([a, a.assign(crsp_fundno=2)])
    with pytest.raises(conv.ConversionError, match="fund-id"):
        conv.convert(both)
    out, rep = conv.convert(both, fund_id="2")
    assert rep["output_rows"] == len(dates)


def test_cli_keeps_existing_output(tmp_path):
    dates, nav, div, tr = _fund()
    src = tmp_path / "crsp.csv"
    pd.DataFrame({"caldt": dates.strftime("%Y-%m-%d"), "dnav": nav, "dret": tr}).to_csv(src, index=False)
    dest = tmp_path / "pimco_ptrix_nav.csv"
    assert conv.main([str(src), "--out", str(dest), "--source", "test"]) == 0
    assert "Source: test" in (tmp_path / "pimco_ptrix_nav_SOURCE.txt").read_text()
    first = dest.read_bytes()
    assert conv.main([str(src), "--out", str(dest)]) == 1            # refuses without --force
    assert dest.read_bytes() == first
    assert conv.main([str(src), "--out", str(dest), "--force"]) == 0
    assert len(list(tmp_path.glob("pimco_ptrix_nav_backup_*.csv"))) == 1


def test_capital_gains_count_as_distributions():
    csv = ("Date,Open,High,Low,Close,Adj Close,Volume,Dividends,Stock Splits,Capital Gains\n"
           "2020-12-01,10,10,10,10.00,9.0,0,0.0,0.0,0.0\n"
           "2020-12-02,10,10,10,9.80,8.9,0,0.03,0.0,0.15\n").encode()
    assert abs(parse_yfinance_csv(csv)["dividend"].iloc[1] - 0.18) < 1e-12
    js = ('{"chart":{"result":[{"meta":{"exchangeTimezoneName":"America/New_York"},"timestamp":[1606833000,1606919400],'
          '"indicators":{"quote":[{"close":[10.0,9.8]}],"adjclose":[{"adjclose":[9.0,8.9]}]},'
          '"events":{"dividends":{"1606919400":{"amount":0.03,"date":1606919400}},'
          '"capitalGains":{"1606919400":{"amount":0.15,"date":1606919400}}}}],"error":null}}').encode()
    assert abs(parse_yahoo_chart_json(js)["dividend"].iloc[1] - 0.18) < 1e-12


def _panel(months, D, g, valid=None):
    idx = pd.period_range("2010-01", periods=months, freq="M")
    return pd.DataFrame({"D": D, "valid": True if valid is None else valid, "g": g}, index=idx)


def test_compare_exposure_recovers_slopes():
    rng = np.random.default_rng(0)
    n = 240
    g = np.clip(0.5 + 0.3 * np.sin(np.arange(n) / 9.0) + 0.05 * rng.standard_normal(n), 0, 1)
    g_start = np.r_[np.nan, g[:-1]]
    d_ref = 5.0 - 3.0 * np.nan_to_num(g_start, nan=0.5) + 0.3 * rng.standard_normal(n)
    d_x = 4.0 - 2.0 * np.nan_to_num(g_start, nan=0.5) + 0.3 * rng.standard_normal(n)
    ref, x = _panel(n, d_ref, g), _panel(n, d_x, g)
    c = compare_exposure(x, ref, "2010-01", "2029-12", 3)
    assert c["status"] == "ok" and c["months"] == n - 1           # the first month has no starting share
    assert abs(c["slope_ref_years"] + 3.0) < 0.3 and abs(c["slope_x_years"] + 2.0) < 0.3
    assert abs(c["slope_diff_years"] - 1.0) < 0.35 and c["slope_diff_ci_low"] < 1.0 < c["slope_diff_ci_high"]
    assert abs(c["mean_diff_years"] - (d_x[1:] - d_ref[1:]).mean()) < 1e-9


def test_compare_exposure_uses_only_months_valid_in_both():
    n = 60
    g = np.linspace(0.1, 0.9, n)
    valid = np.ones(n, bool); valid[10:20] = False
    ref, x = _panel(n, 4 - g, g), _panel(n, 3 - g, g, valid)
    c = compare_exposure(x, ref, "2010-01", "2014-12", 2)
    assert c["months"] == n - 1 - 10
    short = compare_exposure(x, ref, "2010-01", "2010-08", 2)
    assert short["status"].startswith("too few")
