"""Accounting on a hand-worked path: positions, trades, costs, delay, rules, aggregation."""
import numpy as np
import pandas as pd
import pytest

from mbshedge import backtest as bt


@pytest.fixture
def toy():
    idx = pd.to_datetime(["2021-01-29", "2021-02-01", "2021-02-02", "2021-02-26", "2021-03-01", "2021-03-02",
                          "2021-03-31", "2021-04-01", "2021-04-02"])
    return pd.DataFrame({
        "r_mbb_ex": [0.0, -0.004, 0.002, 0.001, -0.003, 0.001, 0.002, -0.001, 0.0005],
        "r_h10_ex": [0.0, -0.008, 0.004, 0.002, -0.006, 0.0015, 0.003, -0.002, 0.001],
        "dur_h10": [8.0] * 9, "days": [1, 3, 1, 1, 3, 1, 1, 1, 1], "dy10": [0.0] * 9}, index=idx)


def decisions(dates, forecasts):
    return pd.DataFrame({"decision_month": [pd.Timestamp(d).to_period("M") for d in dates],
                         "decision_date": pd.to_datetime(dates), "forecast": forecasts})


def test_hand_worked_ledger(toy):
    dec = decisions(["2021-01-29", "2021-02-26", "2021-03-31"], [4.0, 6.0, 6.0])
    res = bt.run_backtest(toy, dec, end_date="2021-04-02", delay=1, rule="monthly", cost_bp=2.0)
    L = res["ledger"]
    # decision 2021-01-29 executes at the 2021-02-01 close; the hedge earns from 2021-02-02
    assert L.index[0] == pd.Timestamp("2021-02-02")
    assert L.loc["2021-02-02", "h_held"] == pytest.approx(0.5)            # 4 / 8
    # second decision (2021-02-26) executes 2021-03-01: day 03-01 still uses 0.5, 03-02 uses 0.75
    assert L.loc["2021-03-01", "h_held"] == pytest.approx(0.5)
    assert L.loc["2021-03-02", "h_held"] == pytest.approx(0.75)
    # trades: establishment 0.5 booked on the first ledger day, +0.25 on 03-01, liquidation -0.75 at the end
    assert L.loc["2021-02-02", "trade"] == pytest.approx(0.5)
    assert L.loc["2021-03-01", "trade"] == pytest.approx(0.25)
    assert L.loc["2021-04-02", "trade"] == pytest.approx(-0.75)
    assert L["cost"].sum() == pytest.approx(2e-4 * (0.5 + 0.25 + 0.75))
    # hand calculation of one day's P&L: 2021-03-02, h = 0.75
    assert L.loc["2021-03-02", "gross_pnl"] == pytest.approx(0.001 - 0.75 * 0.0015)
    assert (L["net_pnl"] == L["gross_pnl"] - L["cost"] - L["financing"]).all()


def test_zero_hedge_reproduces_unhedged(toy):
    dec = decisions(["2021-01-29", "2021-02-26"], [0.0, 0.0])
    L = bt.run_backtest(toy, dec, end_date="2021-04-02", cost_bp=5.0)["ledger"]
    np.testing.assert_allclose(L["net_pnl"], L["mbs_pnl"])
    assert L["cost"].sum() == 0.0


def test_costs_scale_linearly(toy):
    dec = decisions(["2021-01-29", "2021-02-26", "2021-03-31"], [4.0, 6.0, 2.0])
    c1 = bt.run_backtest(toy, dec, end_date="2021-04-02", cost_bp=1.0)["ledger"]["cost"].sum()
    c5 = bt.run_backtest(toy, dec, end_date="2021-04-02", cost_bp=5.0)["ledger"]["cost"].sum()
    assert c5 == pytest.approx(5 * c1)


def test_band_rule_skips_small_changes(toy):
    dec = decisions(["2021-01-29", "2021-02-26", "2021-03-31"], [4.0, 4.2, 6.0])
    res = bt.run_backtest(toy, dec, end_date="2021-04-02", rule="band_0.25", cost_bp=0.0)
    t = res["trades"].set_index("decision_month")
    assert not t.loc[pd.Period("2021-02", "M"), "executed"]      # |4.2 - 4.0| < 0.25
    assert t.loc[pd.Period("2021-03", "M"), "executed"]          # |6.0 - 4.0| > 0.25


def test_position_limit_is_logged(toy):
    dec = decisions(["2021-01-29"], [20.0])
    res = bt.run_backtest(toy, dec, end_date="2021-04-02", max_h=1.5)
    assert res["info"]["position_limit_hits"] == 1
    assert res["ledger"]["h_held"].max() == pytest.approx(1.5)


def test_weekly_sums_match_daily(toy):
    dec = decisions(["2021-01-29", "2021-02-26"], [4.0, 6.0])
    res = bt.run_backtest(toy, dec, end_date="2021-04-02")
    w = bt.weekly(res["ledger"], toy, min_days=1)
    assert w["net_pnl"].sum() == pytest.approx(res["ledger"]["net_pnl"].sum())


def test_weekly_keeps_costs_of_partial_weeks():
    # 25 business days; the first ledger week and the last week are short and get dropped
    idx = pd.bdate_range("2021-01-06", "2021-02-09")
    n = len(idx)
    rng = np.random.default_rng(3)
    daily = pd.DataFrame({"r_mbb_ex": rng.normal(0, 0.003, n), "r_h10_ex": rng.normal(0, 0.006, n),
                          "dur_h10": 8.0, "days": 1, "dy10": rng.normal(0, 0.0005, n)}, index=idx)
    dec = decisions(["2021-01-06", "2021-01-29"], [4.0, 6.0])
    res = bt.run_backtest(daily, dec, end_date="2021-02-09", delay=1, cost_bp=2.0)
    L = res["ledger"]
    w = bt.weekly(L, daily, min_days=3)
    assert (w["n_days"] >= 3).all()
    assert len(w) < len(L.groupby(pd.Grouper(freq="W-FRI")))          # some weeks were dropped
    assert w["cost"].sum() == pytest.approx(L["cost"].sum())            # establishment and liquidation kept
    np.testing.assert_allclose(w["net_pnl"], w["gross_pnl"] - w["cost"] - w["financing"])


def test_alignment_keeps_costs_of_weeks_other_strategies_lack():
    from mbshedge import pipeline as pl
    idx = pd.bdate_range("2021-01-04", "2021-03-31")
    n = len(idx)
    rng = np.random.default_rng(5)
    daily = pd.DataFrame({"r_mbb_ex": rng.normal(0, 0.003, n), "r_h10_ex": rng.normal(0, 0.006, n),
                          "dur_h10": 8.0, "days": 1, "dy10": rng.normal(0, 0.0005, n)}, index=idx)
    months = [pd.Period("2021-01", "M"), pd.Period("2021-02", "M")]
    dates = pd.to_datetime(["2021-01-29", "2021-02-26"])
    fc = pd.concat([pd.DataFrame({"model": "U", "decision_month": months, "decision_date": dates, "forecast": [4.0, 5.0]}),
                    pd.DataFrame({"model": "E", "decision_month": months, "decision_date": dates, "forecast": [np.nan, 5.0]})])
    res = pl.run_strategies(daily, fc, ["U", "E"], "2021-03-31", delay=1, rule="monthly", cost_bp=2.0,
                            financing_bp=0.0, max_h=1.5)
    assert res["U"]["weekly"].index.equals(res["E"]["weekly"].index)   # E starts a month later, U's early weeks are dropped
    for s in ("U", "E"):
        assert res[s]["weekly"]["cost"].sum() == pytest.approx(res[s]["ledger"]["cost"].sum())
