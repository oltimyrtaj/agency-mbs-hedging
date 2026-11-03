"""Exposure estimators: HAC regression, monthly realized duration, EWMA duration, Cochran's Q."""
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from mbshedge import exposure as ex


def test_ols_hac_matches_statsmodels():
    rng = np.random.default_rng(0)
    n = 200
    X = np.column_stack([np.ones(n), rng.standard_normal(n), rng.standard_normal(n)])
    e = rng.standard_normal(n)
    e[1:] += 0.5 * e[:-1]
    y = X @ np.array([0.1, -4.0, -0.5]) + e
    ours = ex.ols_hac(y, X, lags=3)
    ref = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 3, "use_correction": True})
    np.testing.assert_allclose(ours["beta"], ref.params, rtol=1e-10)
    np.testing.assert_allclose(np.sqrt(np.diag(ours["cov"])), ref.bse, rtol=1e-8)


def _daily(dur_by_month: dict, seed=1, noise_bp=5.0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", "2020-12-31")
    dy = 0.0006 * rng.standard_normal(len(idx))
    d = np.array([dur_by_month[t.month] for t in idx])
    r = -0.88 * d * dy - 0.12 * d * np.r_[0.0, dy[:-1]] + noise_bp / 1e4 * rng.standard_normal(len(idx))
    return pd.DataFrame({"r_mbb_ex": r, "dy10": dy}, index=idx)


def test_monthly_realized_duration_recovers_known_values():
    truth = {m: 2.0 + 0.4 * m for m in range(1, 13)}
    rd = ex.monthly_realized_durations(_daily(truth), min_days=15)
    z = (rd["D"] - pd.Series({p: truth[p.month] for p in rd.index})) / rd["se"]
    assert rd["valid"].all()
    assert (z.abs() < 4).all()
    assert abs(z.mean()) < 1.0


def test_short_month_is_flagged_unavailable():
    d = _daily({m: 4.0 for m in range(1, 13)})
    d = d.drop(d.loc["2020-02-05":"2020-02-28"].index)
    rd = ex.monthly_realized_durations(d, min_days=15)
    assert not rd.loc[pd.Period("2020-02", "M"), "valid"]
    assert "too few days" in rd.loc[pd.Period("2020-02", "M"), "flag"]


def test_ewma_duration_uses_only_past_data():
    d = _daily({m: 3.0 + 0.2 * m for m in range(1, 13)})
    d["g"] = np.linspace(0, 1, len(d))
    a = ex.ewma_duration(d, 42)
    d2 = d.copy()
    d2.loc["2020-07-01":, ["r_mbb_ex", "dy10", "g"]] = 99.0          # corrupt the future
    b = ex.ewma_duration(d2, 42)
    early = a.index < "2020-07-01"
    np.testing.assert_array_equal(a.loc[early, "U"].to_numpy(), b.loc[early, "U"].to_numpy())
    np.testing.assert_array_equal(a.loc[early, "gbar"].to_numpy(), b.loc[early, "gbar"].to_numpy())


def test_ewma_with_long_halflife_approaches_pooled_regression():
    d = _daily({m: 4.0 for m in range(1, 13)}, noise_bp=1.0)
    u = ex.ewma_duration(d, 1e7, state_col=None)["U"].iloc[-1]
    assert u == pytest.approx(4.0, abs=0.05)


def test_cochran_q_null_and_heterogeneity():
    same = ex.cochran_q(np.full(30, 4.0), np.full(30, 0.5))
    assert same["Q"] == pytest.approx(0.0) and same["tau"] == 0.0
    rng = np.random.default_rng(3)
    truth = rng.normal(4.0, 1.0, 400)
    est = truth + rng.normal(0, 0.5, 400)
    het = ex.cochran_q(est, np.full(400, 0.5))
    assert het["p_value"] < 1e-6
    assert het["tau"] == pytest.approx(1.0, abs=0.15)


def test_leverage_adjusted_errors_match_statsmodels_hc3_without_lags():
    rng = np.random.default_rng(5)
    n = 25
    X = np.column_stack([np.ones(n), rng.standard_normal(n), rng.standard_normal(n)])
    y = X @ np.array([0.0, -4.0, -0.5]) + rng.standard_t(5, n)
    ours = ex.ols_hac(y, X, lags=0, leverage=True)
    ref = sm.OLS(y, X).fit(cov_type="HC3")
    np.testing.assert_allclose(np.sqrt(np.diag(ours["cov"])), ref.bse, rtol=1e-8)


def test_null_bootstrap_does_not_reject_a_constant_duration():
    d = _daily({m: 4.0 for m in range(1, 13)}, seed=9)
    out = ex.null_bootstrap_variation(d, "2020-01", "2020-12", reps=200, seed=1)
    assert out["p_bootstrap"] > 0.05
    assert out["tau_robust"] < 0.5


def test_null_bootstrap_detects_large_variation():
    d = _daily({m: (2.0 if m % 2 else 6.0) for m in range(1, 13)}, seed=10)
    out = ex.null_bootstrap_variation(d, "2020-01", "2020-12", reps=200, seed=2)
    assert out["p_bootstrap"] < 0.01
    assert out["tau_robust"] == pytest.approx(2.0, abs=0.6)


def test_lead_lag_diagnostic_recovers_a_known_lead():
    # 10% of each day's rate response arrives in the next day's yield change (yield fixed before the ETF close)
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2010-01-01", "2012-12-31")
    dy = rng.normal(0, 0.0006, len(idx))
    lead = np.concatenate([dy[1:], [0.0]])
    r = -5.0 * (0.9 * dy + 0.1 * lead) + rng.normal(0, 0.0005, len(idx))
    out = ex.lead_lag_diagnostic(pd.DataFrame({"r_mbb_ex": r, "dy10": dy}, index=idx), "2010-01", "2012-12")
    assert out["months"] == 36
    assert abs(out["mean_lead_years"] - 0.5) < 3 * out["mean_lead_se"]
    assert abs(out["mean_lag_years"]) < 3 * out["mean_lag_se"]
    assert out["mean_duration_lag_only"] == pytest.approx(4.5, abs=0.2)
