"""Build data/local_inputs/pimco_ptrix_nav.csv from a daily NAV export of the PIMCO Mortgage-Backed
Securities Fund before its 2024 ETF conversion (for example the Institutional class, PTRIX).

Run from the project folder, with the environment active:
    python tools/convert_pimco_nav.py EXPORT.csv --source "CRSP via WRDS, Institutional class"
    python tools/convert_pimco_nav.py NAV.csv --distributions DIVIDENDS.csv --source "Bloomberg PTRIX US Equity"

Accepted layouts (column names are matched ignoring case, spaces, and punctuation):
  1. NAV with distributions: a date column, a NAV column, and a cash distribution column on the
     ex-date (PIMCO's NAV history, or a Bloomberg export). Distributions can also come from a
     separate file with --distributions (columns: an ex-date and an amount).
  2. NAV with a daily total return: CRSP's mutual fund daily file (caldt, dnav, dret), or any file
     with a date and a daily total-return column. Returns in percent are detected and converted.
  3. A total-return index: a date column and a total-return index column (for example Bloomberg's
     TOT_RETURN_INDEX_GROSS_DVDS).
For layouts 2 and 3 the output's `close` column is a total-return index (starting at the first NAV
when one is given) and `dividend` is 0, so the daily total returns notebook 09 rebuilds equal the
source's returns exactly. Layout 1 keeps the NAV and the distributions as they are.

The input file is never modified. An existing output is kept as a timestamped backup when you pass
--force. A provenance note (source, input SHA-256, layout, date range, row counts, and any repairs)
is written next to the output. CRSP and Bloomberg data are licensed: they stay in
data/local_inputs/, which .gitignore keeps out of the public repository.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "local_inputs" / "pimco_ptrix_nav.csv"

DATE_NAMES = ["date", "caldt", "navdate", "asofdate", "pricedate", "exdate", "dates", "day"]
NAV_NAMES = ["nav", "dnav", "navpershare", "close", "pxlast", "price", "fundnetassetval", "netassetvalue"]
DIST_NAMES = ["dividend", "dividends", "distribution", "distributions", "disamt", "dvdamount", "div",
              "amount", "cashdistribution", "eqydvdsh"]
RET_NAMES = ["dret", "totalreturn", "dailytotalreturn", "dailyreturn", "return", "ret", "daytodaytotreturngrossdvds"]
TRI_NAMES = ["totreturnindexgrossdvds", "totalreturnindex", "trindex", "tri"]
FUND_ID_NAMES = ["crspfundno", "fundno", "fundid", "ticker"]


class ConversionError(ValueError):
    pass


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _find(columns, candidates):
    keys = {_key(c): c for c in columns}
    for cand in candidates:
        if cand in keys:
            return keys[cand]
    return None


def _parse_dates(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s) and s.dropna().between(19000101, 21001231).all():
        return pd.to_datetime(s.astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
    txt = s.astype(str).str.strip()
    if txt.str.fullmatch(r"\d{8}").all():
        return pd.to_datetime(txt, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(txt, errors="coerce")


def _returns_in_percent(r: pd.Series) -> bool:
    """Daily returns of a bond fund in decimals have a median size near 0.001. In percent they are
    100 times larger."""
    a = r.dropna().abs()
    return bool(len(a) and a.median() > 0.02)


def read_table(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        try:
            return pd.read_excel(path)
        except ImportError as exc:
            raise ConversionError(f"Reading Excel needs openpyxl ({exc}). Save the sheet as CSV and rerun.") from exc
    return pd.read_csv(path)


def convert(df: pd.DataFrame, distributions: pd.DataFrame | None = None, fund_id: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Return the project's local price table (date, close, dividend) and a report of what was done."""
    rep = {"input_rows": int(len(df)), "repairs": []}
    df = df.copy()
    fid_col = _find(df.columns, FUND_ID_NAMES)
    if fid_col is not None:
        ids = df[fid_col].dropna().astype(str).str.strip().unique()
        if fund_id is not None:
            df = df[df[fid_col].astype(str).str.strip() == str(fund_id)]
            rep["fund_id"] = str(fund_id)
            if df.empty:
                raise ConversionError(f"No rows for fund id {fund_id}. Ids in the file: {', '.join(ids[:20])}")
        elif len(ids) > 1:
            raise ConversionError(f"The file holds {len(ids)} funds or share classes ({', '.join(ids[:10])}). "
                                  "Pass --fund-id with the one you want.")
        elif len(ids) == 1:
            rep["fund_id"] = ids[0]
    dcol = _find(df.columns, DATE_NAMES)
    if dcol is None:
        raise ConversionError(f"No date column found among {list(df.columns)}")
    nav_col, dist_col = _find(df.columns, NAV_NAMES), _find(df.columns, DIST_NAMES)
    ret_col, tri_col = _find(df.columns, RET_NAMES), _find(df.columns, TRI_NAMES)
    df["_date"] = _parse_dates(df[dcol])
    bad = int(df["_date"].isna().sum())
    if bad:
        rep["repairs"].append(f"dropped {bad} rows with unreadable dates")
    df = df.dropna(subset=["_date"]).sort_values("_date")
    dups = int(df["_date"].duplicated(keep="last").sum())
    if dups:
        rep["repairs"].append(f"dropped {dups} duplicate dates (kept the last row of each)")
    df = df.drop_duplicates("_date", keep="last").reset_index(drop=True)
    num = lambda c: pd.to_numeric(df[c], errors="coerce") if c is not None else None

    if tri_col is not None and ret_col is None and dist_col is None and distributions is None:
        layout = "total-return index"
        tri = num(tri_col)
        keep = tri.notna() & (tri > 0)
        out = pd.DataFrame({"date": df.loc[keep, "_date"], "close": tri[keep], "dividend": 0.0})
        rep["columns_used"] = {"date": dcol, "total_return_index": tri_col}
    elif ret_col is not None and distributions is None and dist_col is None:
        layout = "daily total return"
        r = num(ret_col)
        if _returns_in_percent(r):
            r = r / 100.0
            rep["repairs"].append("returns were in percent and were divided by 100")
        nav = num(nav_col) if nav_col is not None else None
        if nav is not None:
            nav_ratio = nav / nav.shift(1) - 1.0
            fill = r.isna() & nav_ratio.notna()
            fill.iloc[0] = False
            if fill.any():
                r = r.where(~fill, nav_ratio)
                rep["repairs"].append(f"{int(fill.sum())} days without a return used the NAV change (any distribution on those days is missed)")
        first = 0
        while first < len(r) and (nav is None or not np.isfinite(nav.iloc[first])) and not np.isfinite(r.iloc[first]):
            first += 1
        r = r.iloc[first:]
        dates = df["_date"].iloc[first:]
        missing = r.iloc[1:].isna()
        if missing.any():
            rep["repairs"].append(f"{int(missing.sum())} days had no return and no NAV change. They were dropped, so the next day's "
                                  "return covers only its own day")
        keep = r.notna()
        keep.iloc[0] = True
        r, dates = r[keep], dates[keep]
        start = float(nav.iloc[first]) if nav is not None and np.isfinite(nav.iloc[first]) else 10.0
        steps = r.fillna(0.0).to_numpy().copy()
        steps[0] = 0.0
        idx = start * np.cumprod(1.0 + steps)
        out = pd.DataFrame({"date": dates.to_numpy(), "close": idx, "dividend": 0.0})
        rep["columns_used"] = {"date": dcol, "daily_total_return": ret_col, "nav": nav_col}
    elif nav_col is not None:
        layout = "NAV with distributions"
        nav = num(nav_col)
        div = num(dist_col).fillna(0.0) if dist_col is not None else pd.Series(0.0, index=df.index)
        out = pd.DataFrame({"date": df["_date"], "close": nav, "dividend": div})
        out = out[out["close"].notna() & (out["close"] > 0)].reset_index(drop=True)
        if distributions is not None:
            ddate = _find(distributions.columns, DATE_NAMES)
            damt = _find(distributions.columns, DIST_NAMES)
            if ddate is None or damt is None:
                raise ConversionError(f"The distributions file needs a date and an amount column, found {list(distributions.columns)}")
            dd = pd.DataFrame({"date": _parse_dates(distributions[ddate]), "amt": pd.to_numeric(distributions[damt], errors="coerce")}).dropna()
            dd = dd[dd["amt"] != 0]
            pos = np.searchsorted(out["date"].to_numpy(), dd["date"].to_numpy())
            moved = int((out["date"].to_numpy()[np.clip(pos, 0, len(out) - 1)] != dd["date"].to_numpy()).sum())
            ok = pos < len(out)
            for p_, a in zip(pos[ok], dd["amt"].to_numpy()[ok]):
                out.loc[p_, "dividend"] += a
            if moved:
                rep["repairs"].append(f"{moved} distribution dates were not NAV dates and were moved to the next NAV date")
            if (~ok).any():
                rep["repairs"].append(f"{int((~ok).sum())} distributions after the last NAV date were ignored")
            rep["distributions_file_rows"] = int(len(dd))
        if dist_col is None and distributions is None:
            raise ConversionError("Only a NAV column was found. NAV alone misses every distribution, so it cannot give total "
                                  "returns. Add a distribution column, pass --distributions, or export a daily total return.")
        rep["columns_used"] = {"date": dcol, "nav": nav_col, "distribution": dist_col or "separate file"}
    else:
        raise ConversionError(f"Could not recognize the layout of columns {list(df.columns)}. See the docstring for accepted layouts.")

    out = out.reset_index(drop=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    if len(out) < 250:
        raise ConversionError(f"Only {len(out)} usable rows. Notebook 09 needs years of daily history.")
    tr = (out["close"] + out["dividend"]) / out["close"].shift(1) - 1.0
    rep.update({"layout": layout, "output_rows": int(len(out)), "first_date": out["date"].iloc[0], "last_date": out["date"].iloc[-1],
                "n_distributions": int((out["dividend"] > 0).sum()), "max_abs_daily_return_pct": float(100 * tr.abs().max()),
                "days_abs_return_over_3pct": int((tr.abs() > 0.03).sum())})
    return out, rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="the export (CSV, or Excel if openpyxl is installed)")
    ap.add_argument("--distributions", help="optional separate file of distributions (ex-date and amount)")
    ap.add_argument("--fund-id", help="CRSP fund number or ticker to keep when the file holds several")
    ap.add_argument("--source", default="", help='where the data came from, e.g. "CRSP via WRDS, Institutional class"')
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--force", action="store_true", help="replace an existing output (the old file is kept as a backup)")
    a = ap.parse_args(argv)
    src = Path(a.input)
    try:
        df = read_table(src)
        dist = read_table(Path(a.distributions)) if a.distributions else None
        out, rep = convert(df, dist, a.fund_id)
    except (ConversionError, FileNotFoundError) as exc:
        print(f"Not converted: {exc}")
        return 1
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if not a.force:
            print(f"{dest} already exists. Rerun with --force to replace it (the old file is kept as a backup).")
            return 1
        backup = dest.with_name(dest.stem + f"_backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}" + dest.suffix)
        dest.rename(backup)
        print(f"Kept the previous file as {backup.name}")
    out.to_csv(dest, index=False, float_format="%.8f")
    note = dest.with_name(dest.stem + "_SOURCE.txt")
    lines = [f"Created (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
             f"Source: {a.source or '(not stated: rerun with --source)'}",
             f"Input file: {src.name}, SHA-256 {hashlib.sha256(src.read_bytes()).hexdigest()}"]
    if a.distributions:
        lines.append(f"Distributions file: {Path(a.distributions).name}, SHA-256 {hashlib.sha256(Path(a.distributions).read_bytes()).hexdigest()}")
    lines += [f"{k}: {v}" for k, v in rep.items() if k != "repairs"]
    lines += ["Repairs: " + ("; ".join(rep["repairs"]) if rep["repairs"] else "none")]
    if rep["layout"] != "NAV with distributions":
        lines.append("Note: the close column is a total-return index, and the dividend column is 0.")
    note.write_text("\n".join(lines) + "\n")
    print(f"Wrote {dest} ({rep['output_rows']} rows, {rep['first_date']} to {rep['last_date']}, layout: {rep['layout']}).")
    for r in rep["repairs"]:
        print("  repair:", r)
    if rep["days_abs_return_over_3pct"]:
        print(f"  check: {rep['days_abs_return_over_3pct']} days move more than 3%, unusual for a mortgage fund. Look at them before using the file.")
    print(f"Provenance note: {note}")
    print("Next: python run_project.py --mode full --only 09 10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
