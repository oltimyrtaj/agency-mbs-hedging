"""Hedge-instrument pricing: par at issue, duration, DV01 against finite differences, daily returns."""
import numpy as np
import pytest

from mbshedge import instruments as ins


@pytest.mark.parametrize("y", [0.005, 0.02, 0.0425, 0.08])
@pytest.mark.parametrize("tenor", [5, 10, 30])
def test_par_bond_prices_at_100_at_issue(y, tenor):
    assert ins.bond_full_price(y, tenor, y)[0] == pytest.approx(100.0, abs=1e-10)


@pytest.mark.parametrize("y", [0.01, 0.0425, 0.07])
def test_cashflow_duration_matches_closed_form(y):
    a = ins.par_bond_modified_duration(y, 10)[0]
    b = ins.par_bond_modified_duration_closed_form(y, 10)[0]
    assert a == pytest.approx(b, rel=1e-12)


@pytest.mark.parametrize("y", [0.015, 0.045])
def test_analytic_dv01_matches_finite_difference(y):
    analytic = ins.par_bond_modified_duration(y, 10)[0] * 100 * 1e-4
    fd = ins.dv01_per_100(y, 10, y)            # central difference, 1 bp bump
    # central difference with a 1 bp bump: truncation error is of order bump^2 * third derivative
    assert fd == pytest.approx(analytic, rel=1e-6)


def test_unchanged_yield_return_is_pure_carry():
    # a par bond aged dt at an unchanged yield is worth 100 * (1 + y/2)^(2 dt) exactly
    y, days = 0.04, 3
    r = ins.synthetic_bond_daily_returns(np.array([y * 100, y * 100]) / 100, np.array([0, days]), 10)[1]
    assert r == pytest.approx((1 + y / 2) ** (2 * days / 365.25) - 1, abs=1e-14)


def test_return_approximates_duration_times_yield_change():
    y0, dy = 0.04, 0.0010
    r = ins.synthetic_bond_daily_returns(np.array([y0, y0 + dy]), np.array([0, 1]), 10)[1]
    d = ins.par_bond_modified_duration(y0, 10)[0]
    carry = y0 / 365.25
    assert r == pytest.approx(-d * dy + carry, abs=6e-5)   # remaining gap is convexity, about 0.5*C*dy^2
