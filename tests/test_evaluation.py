"""Metrics and inference on small known examples."""
import numpy as np
import pandas as pd
import pytest

from mbshedge import evaluation as ev


def test_basic_metrics():
    x = np.array([0.01, -0.02, 0.03, -0.01, 0.0])
    assert ev.ann_vol(x, 52) == pytest.approx(np.std(x, ddof=1) * np.sqrt(52))
    assert ev.max_drawdown([0.01, 0.02, -0.05, 0.01, -0.01]) == pytest.approx(0.05)
    assert ev.expected_shortfall(np.arange(-10, 10) / 100, 0.9) == pytest.approx(0.095)   # mean of -0.10, -0.09
    assert ev.variance_reduction(x / 2, x) == pytest.approx(0.75)


def test_stationary_bootstrap_indices():
    rng = np.random.default_rng(0)
    idx = ev.stationary_bootstrap_indices(500, 10, 200, rng)
    assert idx.shape == (200, 500) and idx.min() >= 0 and idx.max() < 500
    starts = (np.diff(idx, axis=1) != 1) & (np.diff(idx, axis=1) != -499)
    assert 1.0 / starts.mean() == pytest.approx(10, rel=0.15)


def test_paired_bootstrap_identical_series_gives_zero():
    rng = np.random.default_rng(1)
    a = rng.standard_normal(300)
    W = pd.DataFrame({"A": a, "B": a})
    b = ev.paired_bootstrap(W, [("A", "B")], 200, 13, seed=2)
    assert b["variance_reduction"].iloc[0] == 0.0
    assert b["vr_ci_low"].iloc[0] == 0.0 and b["vr_ci_high"].iloc[0] == 0.0


def test_paired_bootstrap_detects_large_reduction():
    rng = np.random.default_rng(2)
    common = rng.standard_normal(400)
    W = pd.DataFrame({"good": common * 0.5, "bad": common})
    b = ev.paired_bootstrap(W, [("good", "bad")], 300, 13, seed=3)
    assert b["variance_reduction"].iloc[0] == pytest.approx(0.75)
    assert b["vr_ci_low"].iloc[0] > 0.7


def test_holm():
    adj = ev.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.20})
    assert adj["a"] == pytest.approx(0.04)
    assert adj["c"] == pytest.approx(0.09)
    assert adj["b"] == pytest.approx(0.09)        # monotone step-down
    assert adj["d"] == pytest.approx(0.20)


def test_forecast_tests_behave():
    rng = np.random.default_rng(4)
    truth = rng.normal(4, 1, 300)
    y = truth + rng.normal(0, 0.3, 300)
    small = np.full(300, 4.0)
    big = truth
    cw = ev.clark_west(y, small, big, lags=3)
    assert cw["p_one_sided"] < 1e-6
    dm = ev.diebold_mariano(y, small, big, lags=3)
    assert dm["mean_loss_diff"] > 0 and dm["p_two_sided"] < 1e-6


def test_cost_verdict_breakeven():
    summary = pd.DataFrame({"vol_gross_ann_pct": [2.0, 1.8], "turnover_per_year": [0.5, 1.5],
                            "financing_bp_per_year": [0.0, 0.0]}, index=["U", "H"])
    boot = pd.DataFrame([{"challenger": "H", "comparator": "U", "variance_reduction": 0.19, "vr_ci_low": 0.05}])
    v = ev.cost_verdict(summary, boot, "H", "U", hurdle_ir=0.5, cost_bp=2.0, practical_vr=0.05)
    # value = 0.5 * 0.2% = 10 bp/yr; extra cost = 2 bp * 1.0 = 2 bp/yr; break-even = 10 bp per trade
    assert v["value_of_risk_reduction_bp_per_year"] == pytest.approx(10.0)
    assert v["extra_cost_bp_per_year"] == pytest.approx(2.0)
    assert v["breakeven_cost_bp_per_trade"] == pytest.approx(10.0)
    assert v["verdict"] == "survives costs"


def test_cost_verdict_breakeven_when_challenger_trades_less():
    # The challenger is slightly riskier but trades much less: it wins only when costs are high.
    summary = pd.DataFrame({"vol_gross_ann_pct": [2.0, 2.02], "turnover_per_year": [2.0, 0.5],
                            "financing_bp_per_year": [0.0, 0.0]}, index=["U", "E"])
    boot = pd.DataFrame([{"challenger": "E", "comparator": "U", "variance_reduction": -0.02, "vr_ci_low": -0.06}])
    v = ev.cost_verdict(summary, boot, "E", "U", hurdle_ir=0.5, cost_bp=2.0, practical_vr=0.05)
    # value = 0.5 * (-0.02%) = -1 bp/yr; extra turnover = -1.5; gain(k) = -1 + 1.5 k > 0 for k > 0.667 bp
    assert v["breakeven_cost_bp_per_trade"] == pytest.approx(1.0 / 1.5)
    assert v["net_gain_positive_when"] == "above break-even cost"
    gain_at = lambda k: ev.cost_verdict(summary, boot, "E", "U", 0.5, k, 0.05)["net_gain_bp_per_year"]
    assert gain_at(0.5) < 0 < gain_at(1.0)
    assert "above" in ev.breakeven_text(v)


def test_cost_verdict_breakeven_never_and_always():
    boot = pd.DataFrame([{"challenger": "H", "comparator": "U", "variance_reduction": 0.0, "vr_ci_low": -0.01}])
    worse_and_busier = pd.DataFrame({"vol_gross_ann_pct": [2.0, 2.1], "turnover_per_year": [0.5, 1.5],
                                     "financing_bp_per_year": [0.0, 0.0]}, index=["U", "H"])
    v = ev.cost_verdict(worse_and_busier, boot, "H", "U", 0.5, 2.0, 0.05)
    assert v["net_gain_positive_when"] == "at no cost" and np.isnan(v["breakeven_cost_bp_per_trade"])
    better_and_quieter = pd.DataFrame({"vol_gross_ann_pct": [2.0, 1.9], "turnover_per_year": [1.5, 0.5],
                                       "financing_bp_per_year": [0.0, 0.0]}, index=["U", "H"])
    v = ev.cost_verdict(better_and_quieter, boot, "H", "U", 0.5, 2.0, 0.05)
    assert v["net_gain_positive_when"] == "at every cost" and np.isnan(v["breakeven_cost_bp_per_trade"])


def test_bootstrap_p_value_agrees_with_the_interval():
    rng = np.random.default_rng(11)
    base = rng.normal(0, 1.0, 400)
    for scale in [1.0, 0.97, 0.9, 0.8]:              # challenger noise relative to comparator
        W = pd.DataFrame({"U": base + rng.normal(0, 0.3, 400), "H": scale * base + rng.normal(0, 0.3, 400)})
        b = ev.paired_bootstrap(W, [("H", "U")], 999, 13, seed=3).iloc[0]
        assert (b["p_one_sided"] < 0.025) == (b["vr_ci_low"] > 0) or abs(b["vr_ci_low"]) < 1e-3


def test_support_requires_the_interval_above_zero():
    summary = pd.DataFrame({"vol_gross_ann_pct": [2.0, 1.9], "turnover_per_year": [0.5, 0.6],
                            "financing_bp_per_year": [0.0, 0.0]}, index=["U", "H"])
    boot = pd.DataFrame([{"challenger": "H", "comparator": "U", "variance_reduction": 0.1, "vr_ci_low": -0.01,
                          "vr_ci_high": 0.2, "p_one_sided": 0.01, "p_holm": 0.01}])
    v = ev.cost_verdict(summary, boot, "H", "U", 0.5, 2.0, 0.05)
    assert not v["statistical_support"] and v["verdict"] != "survives costs"
