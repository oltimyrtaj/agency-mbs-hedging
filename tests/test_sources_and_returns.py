"""Parsers on real-format fixtures, and total-return reconstruction without double counting."""
import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from mbshedge import prepare as pr
from mbshedge import sources as src


def test_fred_csv_parser_handles_blank_and_dot_and_header_variants():
    new = b"observation_date,DGS10\n2026-10-09,5.24\n2026-10-12,\n2026-10-13,5.21\n"
    old = b"DATE,DGS10\n2026-10-09,5.24\n2026-10-12,.\n2026-10-13,5.21\n"
    for content in (new, old):
        df = src.parse_fred_csv(content, "DGS10")
        assert list(df.columns) == ["date", "value"]
        assert df["value"].isna().sum() == 1
        assert df["value"].iloc[-1] == pytest.approx(5.21)


def test_nmdb_parser_on_verified_layout():
    # rows copied in the exact layout verified on 2026-11-02
    csv = (
        "SOURCE,FREQUENCY,GEOLEVEL,GEOID,GEONAME,MARKET,PERIOD,YEAR,QUARTER,MONTH,SUPPRESSED,SERIESID,VALUE1,VALUE2\n"
        "NMDB,Quarterly,Census Division,DENC,East North Central,All Mortgages,2013Q1,2013,1,3,0,TOT_LOANS,8228,\n"
        "NMDB,Quarterly,National,USA,United States,All Mortgages,2013Q1,2013,1,3,0,AVE_INTRATE,5.4,5.1\n"
        "NMDB,Quarterly,National,USA,United States,Enterprise Acquisitions,2013Q1,2013,1,3,0,AVE_INTRATE,5,4.7\n"
        "NMDB,Quarterly,National,USA,United States,Enterprise Acquisitions,2013Q1,2013,1,3,0,TOT_UPB,4557.5,4557.5\n"
    ).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("nmdb.csv", csv)
    df = src.parse_nmdb(buf.getvalue())
    assert set(df["series"]) == {"AVE_INTRATE", "TOT_UPB"}           # the Census Division row is dropped
    row = df[(df["market"] == "Enterprise Acquisitions") & (df["series"] == "AVE_INTRATE")].iloc[0]
    assert row["value2"] == pytest.approx(4.7) and row["value1"] == pytest.approx(5.0)
    assert row["quarter_end"] == pd.Timestamp("2013-03-31")


def test_yahoo_chart_parser_maps_dividends_to_ex_dates():
    ts = [1759325400, 1759411800]                     # 2025-10-01 and 2025-10-02 at 13:30 UTC (9:30 ET)
    obj = {"chart": {"result": [{"meta": {"exchangeTimezoneName": "America/New_York"}, "timestamp": ts,
                                 "events": {"dividends": {"1759325400": {"amount": 0.336, "date": 1759325400}}},
                                 "indicators": {"quote": [{"close": [95.12, 95.24]}],
                                                "adjclose": [{"adjclose": [91.10, 91.21]}]}}], "error": None}}
    df = src.parse_yahoo_chart_json(json.dumps(obj).encode())
    assert list(df["date"].dt.strftime("%Y-%m-%d")) == ["2025-10-01", "2025-10-02"]
    assert df["dividend"].tolist() == [0.336, 0.0]


def test_total_return_counts_distributions_once_and_ignores_adjusted_close():
    p = pd.DataFrame({"date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"]),
                      "close": [100.0, 99.8, 100.1], "adj_close": [1.0, 5.0, 2.0],   # deliberately garbage
                      "dividend": [0.0, 0.3, 0.0], "split_factor": 1.0})
    out, info = pr.total_return_from_prices(p)
    assert out["tr"].iloc[1] == pytest.approx((99.8 + 0.3) / 100.0 - 1)
    assert out["tr"].iloc[2] == pytest.approx(100.1 / 99.8 - 1)
    assert info["adjclose_check_days_over_1bp"] >= 1               # the check notices the bad adjusted close


def test_duplicate_dates_are_dropped_and_counted():
    p = pd.DataFrame({"date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-03"]),
                      "close": [100.0, 101.0, 101.0], "adj_close": np.nan, "dividend": 0.0, "split_factor": 1.0})
    out, info = pr.total_return_from_prices(p)
    assert len(out) == 2 and info["duplicates_dropped"] == 1


def test_returns_compound_across_a_bond_market_holiday():
    tr = pd.DataFrame({"date": pd.to_datetime(["2020-10-09", "2020-10-12", "2020-10-13"]),
                       "tr": [np.nan, 0.01, 0.02]})
    cal = pd.DatetimeIndex(pd.to_datetime(["2020-10-09", "2020-10-13"]))   # Columbus Day 10-12 has no yield
    ret = pr._compound_to_calendar(tr, cal)
    assert ret.iloc[1] == pytest.approx(1.01 * 1.02 - 1)


def test_double_counted_distributions_are_caught():
    # a provider whose "close" already includes distributions: adding them again inflates returns
    days = pd.bdate_range("2020-01-01", periods=504)
    adj = 100.0 * np.cumprod(np.r_[1.0, np.full(len(days) - 1, 1.0001)])
    div = np.where(np.arange(len(days)) % 21 == 20, 0.25, 0.0)
    p = pd.DataFrame({"date": days, "close": adj, "adj_close": adj, "dividend": div, "split_factor": 1.0})
    _, info = pr.total_return_from_prices(p)
    problem = pr.check_total_return(info, "MBB")
    assert problem is not None and "double counting" in problem
    # the same file with the distributions left out of the close passes
    _, info_ok = pr.total_return_from_prices(p.assign(dividend=0.0))
    assert pr.check_total_return(info_ok, "MBB") is None


def test_a_stalled_server_is_skipped_and_the_local_file_is_used(tmp_path, monkeypatch, cfg):
    import copy
    import requests
    from mbshedge import sources as src

    calls = {"n": 0}

    def stall(*args, **kwargs):
        calls["n"] += 1
        raise requests.exceptions.ReadTimeout("no reply")

    monkeypatch.setattr(requests, "get", stall)
    monkeypatch.setattr(src, "curl_get", lambda *a, **k: (_ for _ in ()).throw(src.SourceError("curl stalled too")))
    monkeypatch.setattr(src, "_STALLED_HOSTS", set())
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    c = copy.deepcopy(cfg)
    c["network"].update({"backoff_seconds": 0.0, "max_retries": 2})
    local = tmp_path / "local"
    local.mkdir()
    (local / "DGS10.csv").write_text("observation_date,DGS10\n2026-10-28,5.05\n2026-10-29,4.98\n")
    store = src.RawStore(tmp_path / "raw")
    df = src.fetch_fred("DGS10", store, c, local, "2026-10-01", "2026-10-30", refresh=True, role="core")
    assert df["value"].tolist() == [5.05, 4.98]
    assert calls["n"] == 2                                   # two tries, then the host is marked as stalled
    with pytest.raises(src.SourceError, match="did not answer earlier"):
        src.http_get(src.FRED_GRAPH_URL, c)
    assert calls["n"] == 2                                   # no further waiting on the same host
