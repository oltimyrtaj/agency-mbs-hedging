"""Availability-time alignment: nothing is used before it was released."""
import numpy as np
import pandas as pd
import pytest

from mbshedge import prepare as pr


def test_nmdb_availability_dates():
    q = pd.Series(pd.to_datetime(["2026-06-30", "2013-03-31"]))
    assert list(pr.availability_dates(q, 1)) == [pd.Timestamp("2026-09-30"), pd.Timestamp("2013-06-30")]
    assert list(pr.availability_dates(q, 2)) == [pd.Timestamp("2026-12-31"), pd.Timestamp("2013-09-30")]


def _nmdb_rows(values):
    rows = []
    for qe, v in values:
        per = pd.Timestamp(qe).to_period("Q")
        for m, val in [("Enterprise Acquisitions", v), ("Government / Non-Conventional", v)]:
            rows.append({"period": str(per), "market": m, "series": "AVE_INTRATE", "value1": val, "value2": val,
                         "suppressed": 0, "quarter_end": pd.Timestamp(qe)})
            rows.append({"period": str(per), "market": m, "series": "TOT_UPB", "value1": 1000.0, "value2": 1000.0,
                         "suppressed": 0, "quarter_end": pd.Timestamp(qe)})
    return pd.DataFrame(rows)


def test_state_uses_nmdb_only_after_release_and_pmms_from_release_day():
    cal = pd.bdate_range("2013-05-01", "2013-10-31")
    pmms = pd.DataFrame({"date": pd.to_datetime(["2013-04-25", "2013-05-02", "2013-06-27", "2013-07-03"]),
                         "value": [3.40, 3.35, 4.46, 4.29]})
    nmdb = _nmdb_rows([("2013-03-31", 4.7), ("2013-06-30", 4.6)])
    st, info = pr.build_state(cal, pmms, nmdb, markets=["Enterprise Acquisitions", "Government / Non-Conventional"],
                              lag_quarters=1, theta=0.5, sigma=1.0, development_end=pd.Timestamp("2014-12-31"),
                              proxy_grid_years=[3], sigma_default=1.0, use_proxy=False)
    # 2013Q1 (quarter end March 31) is usable only from June 30; 2013Q2 only from September 30
    assert np.isnan(st.loc["2013-06-28", "stock_rate"])
    assert st.loc["2013-07-01", "stock_rate"] == pytest.approx(4.7)
    assert st.loc["2013-09-27", "stock_rate"] == pytest.approx(4.7)
    assert st.loc["2013-09-30", "stock_rate"] == pytest.approx(4.6)
    # PMMS released Thursday 2013-06-27 is usable from that day, not the day before
    assert st.loc["2013-06-26", "pmms"] == pytest.approx(3.35)
    assert st.loc["2013-06-27", "pmms"] == pytest.approx(4.46)
    assert st.loc["2013-07-01", "incentive"] == pytest.approx(4.7 - 4.46)


def test_proxy_is_labeled_retrospective_before_nmdb():
    cal = pd.bdate_range("2012-01-02", "2013-12-31")
    weeks = pd.date_range("2005-01-06", "2013-12-26", freq="W-THU")
    pmms = pd.DataFrame({"date": weeks, "value": np.linspace(6.0, 4.0, len(weeks))})
    nmdb = _nmdb_rows([(q, 4.7 - 0.05 * i) for i, q in enumerate(pd.date_range("2013-03-31", "2014-09-30", freq="QE"))])
    st, info = pr.build_state(cal, pmms, nmdb, markets=["Enterprise Acquisitions", "Government / Non-Conventional"],
                              lag_quarters=1, theta=0.5, sigma=1.0, development_end=pd.Timestamp("2014-12-31"),
                              proxy_grid_years=[2, 4], sigma_default=1.0)
    assert (st.loc[:"2013-06-28", "incentive_source"] == "proxy_retrospective").all()
    assert (st.loc["2013-07-01":, "incentive_source"] == "nmdb").all()
    assert info["proxy"]["status"] == "ok"


def test_last_complete_month_requires_the_final_trading_day():
    from mbshedge.pipeline import last_complete_month
    assert str(last_complete_month(pd.bdate_range("2026-09-01", "2026-10-29"))) == "2026-09"  # Fri Oct 30 missing
    assert str(last_complete_month(pd.bdate_range("2026-09-01", "2026-10-27"))) == "2026-09"
    assert str(last_complete_month(pd.bdate_range("2026-09-01", "2026-10-30"))) == "2026-10"
    assert str(last_complete_month(pd.bdate_range("2026-09-01", "2026-11-03"))) == "2026-10"
    assert str(last_complete_month(pd.bdate_range("2021-05-03", "2021-05-28"))) == "2021-05"  # May 31 Memorial Day
    assert str(last_complete_month(pd.bdate_range("2024-03-01", "2024-03-28"))) == "2024-03"  # Mar 29 Good Friday


def test_stock_rate_skips_quarters_with_a_missing_market():
    markets = ["Enterprise Acquisitions", "Government / Non-Conventional"]
    n = _nmdb_rows([("2024-03-31", 4.0), ("2024-06-30", 4.1), ("2024-09-30", 4.2)])
    n.loc[(n["quarter_end"] == "2024-06-30") & (n["market"] == markets[1]) & (n["series"] == "AVE_INTRATE"),
          ["value1", "value2"]] = np.nan
    out = pr.nmdb_stock_rate(n, markets)
    assert list(out["quarter_end"]) == [pd.Timestamp("2024-03-31"), pd.Timestamp("2024-09-30")]
    assert out["stock_rate"].tolist() == pytest.approx([4.0, 4.2])
    with pytest.raises(ValueError, match="no AVE_INTRATE rows"):
        pr.nmdb_stock_rate(n, markets + ["All Mortgages"])


def test_december_31_is_a_trading_day_even_when_new_year_falls_on_saturday():
    from mbshedge.pipeline import last_complete_month, market_holidays
    assert pd.Timestamp("2021-12-31") not in market_holidays("2021-12-01", "2022-01-31")
    assert str(last_complete_month(pd.bdate_range("2021-12-01", "2021-12-30"))) == "2021-11"
    assert str(last_complete_month(pd.bdate_range("2021-12-01", "2021-12-31"))) == "2021-12"
    assert str(last_complete_month(pd.bdate_range("2027-12-01", "2027-12-30"))) == "2027-11"
