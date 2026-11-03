"""Walk-forward models use only past targets, and the full pipeline cannot see the future."""
import numpy as np
import pandas as pd
import pytest

from mbshedge import models as md
from mbshedge import pipeline as pl


def _monthly(n=60, seed=0):
    rng = np.random.default_rng(seed)
    months = pd.period_range("2010-01", periods=n, freq="M")
    g = rng.uniform(0, 1, n)
    # next month's duration responds to this month's share in the money: D[k+1] = 6 - 4 g[k] + noise
    D = 6 - 4 * np.r_[0.5, g[:-1]] + rng.normal(0, 0.3, n)
    return pd.DataFrame({"D": D, "se": 0.3, "valid": True, "g": g, "U_21": D + 0.1, "gbar_21": g,
                         "decision_date": months.to_timestamp(how="end").normalize(),
                         "incentive_source": "nmdb"}, index=months)


def test_forecast_at_m_does_not_use_target_month():
    mo = _monthly()
    a = md.walk_forward(mo, first_decision="2013-01", last_decision="2014-11", static_d=4.0,
                        u_col="U_21", gbar_col="gbar_21")
    mo2 = mo.copy()
    mo2.loc[pd.Period("2014-06", "M"):, "D"] = 50.0
    b = md.walk_forward(mo2, first_decision="2013-01", last_decision="2014-11", static_d=4.0,
                        u_col="U_21", gbar_col="gbar_21")
    early = a["decision_month"] < pd.Period("2014-06", "M")
    feasible = a["model"] != "X"
    np.testing.assert_array_equal(a.loc[early & feasible, "forecast"].to_numpy(), b.loc[early & feasible, "forecast"].to_numpy())


def test_hybrid_equals_updating_when_state_unchanged():
    mo = _monthly()
    fc = md.walk_forward(mo, first_decision="2013-01", last_decision="2013-06", static_d=4.0,
                         u_col="U_21", gbar_col="gbar_21")
    w = fc.pivot(index="decision_month", columns="model", values="forecast")
    np.testing.assert_allclose(w["H"], w["U"])                 # g == gbar in this fixture


def test_economic_model_recovers_slope():
    mo = _monthly(n=200)
    fc = md.walk_forward(mo, first_decision="2025-07", last_decision="2026-07", static_d=4.0,
                         u_col="U_21", gbar_col="gbar_21")
    c1 = fc[fc["model"] == "E"]["c1"].iloc[-1]
    assert c1 == pytest.approx(-4.0, abs=0.3)


def test_pipeline_perturbation_test_passes_in_test_period(tables, cfg, exp):
    res = pl.perturbation_check(tables, cfg, exp, pd.Timestamp("2019-06-14"), seed=11, halflife=63)
    assert res["passed"], res
    assert res["n_early_forecasts"] > 100
    assert res["share_late_forecasts_changed"] > 0.5            # the perturbation really changed later inputs


def test_nmdb_release_time_matters(tables, cfg, exp):
    # 2019Q1 (quarter end 2019-03-31) is released 2019-06-30. A cut on 2019-05-31 must ignore its value.
    res = pl.perturbation_check(tables, cfg, exp, pd.Timestamp("2019-05-31"), seed=12, halflife=63)
    assert res["passed"], res


def test_change_between_treats_missing_values_as_changes():
    from mbshedge.pipeline import change_between
    out = change_between([1.0, np.nan, np.nan, 2.0], [1.0, np.nan, 3.0, 2.5])
    assert out[0] == 0.0 and out[1] == 0.0          # equal, and missing on both sides
    assert np.isinf(out[2])                          # appeared in one run only
    assert out[3] == pytest.approx(0.5)
