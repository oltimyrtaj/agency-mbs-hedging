"""Teaching-example sanity checks and an end-to-end synthetic smoke test."""
import numpy as np
import pytest

from mbshedge import pipeline as pl
from mbshedge import teaching as tc


@pytest.mark.parametrize("cpr", [0.0, 0.06, 0.3, 0.6])
def test_pool_prices_at_par_when_discounted_at_coupon(cpr):
    m = tc.cashflow_measures(tc.pool_cashflows(cpr), tc.COUPON)
    assert m["price"] == pytest.approx(100.0, abs=1e-8)


def test_faster_prepayment_shortens_life_and_duration():
    slow = tc.cashflow_measures(tc.pool_cashflows(0.06), 0.06)
    fast = tc.cashflow_measures(tc.pool_cashflows(0.40), 0.06)
    assert fast["wal_years"] < slow["wal_years"] and fast["duration"] < slow["duration"]


def test_stale_hedge_loses_in_both_directions():
    s = tc.stale_hedge_pnl(np.array([-100, 100]))
    assert (s["hedged_pnl_usd"] < 0).all()


def test_end_to_end_synthetic_pipeline(tables, cfg, exp):
    out = pl.run_all(tables, cfg, exp, segment="test", reps=50)
    s = out["evaluation"]["summary"]
    assert set(["UNH", "S", "U", "P", "AR", "E", "H", "X"]) <= set(s.index)
    assert out["halflife"] in exp["exposure"]["ewma_halflife_grid_days"]
    assert s.loc["UNH", "turnover_per_year"] == 0.0
    # every hedge removes most of the rate risk of the unhedged portfolio in this synthetic world
    assert (s.drop(index="UNH")["var_reduction_vs_unhedged"] > 0.5).all()
