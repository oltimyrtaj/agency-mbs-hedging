# Data sources, access status, and manual routes

## Access status vocabulary

| Status | Meaning |
|---|---|
| verified access | Format and access checked live, or downloaded and parsed in a run |
| documented but untested | Implemented from the provider's documentation, never exercised against the live service here |
| user-provided | Read from `data/local_inputs/` |
| unavailable | No free route works |

## What was verified (2026-11-02)

Each source was checked through a web browser by reading a small live sample. The full histories are downloaded when notebook 01 runs.

| Source | Status | What was checked |
|---|---|---|
| FRED graph CSV (`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>&cosd=..&coed=..`) for DGS10, DGS5, DGS3MO, MORTGAGE30US | verified access | `application/csv`, header `observation_date,<ID>`, a row with an empty value on the 2026-10-12 bond-market holiday, MORTGAGE30US dated on Thursdays (latest 7.24 on 2026-10-29) |
| FRED series pages | verified access | DGS10: daily, percent, H.15, "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity, Quoted on an Investment Basis". MORTGAGE30US: weekly ending Thursday, percent, copyrighted (citation required), methodology change on 2022-11-17 |
| Freddie Mac PMMS page | verified access | Released Thursdays at 12:00 ET (Wednesday when Thursday is a holiday). Survey week runs from Thursday 00:00 ET through Wednesday 23:59 ET. Historical file `https://www.freddiemac.com/pmms/docs/historicalweeklydata.xlsx` (not used by the code) |
| FHFA NMDB outstanding statistics zip (`https://www.fhfa.gov/document/d/nmdb/nmdb-outstanding-mortgage-statistics-national-census-areas-quarterly.zip`) | verified access | Downloaded and decompressed in the browser. One CSV (14.4 MB), 127,872 rows, 14 columns `SOURCE, FREQUENCY, GEOLEVEL, GEOID, GEONAME, MARKET, PERIOD, YEAR, QUARTER, MONTH, SUPPRESSED, SERIESID, VALUE1, VALUE2`. National rows have `GEOLEVEL = National`, `GEOID = USA`. Markets: All Mortgages, Enterprise Acquisitions, Government / Non-Conventional, Other Conventional Market. 37 national series, including AVE_INTRATE, TOT_UPB, TOT_LOANS, and PCT_INTRATE_LT_3, _3_4, _4_5, _5_6, _GE_6. PERIOD 2013Q1 to 2026Q2. Rates in percent with one decimal. No quoted fields. No suppressed national rows in 2013–2014 |
| NMDB page and data dictionary | verified access | Quarterly data 2013 Q1 to 2026 Q2, released 9/30/2026. Dictionary (2026Q1 edition): VALUE1 weighted by loan count, VALUE2 by unpaid balance for outstanding loans. AVE_INTRATE is the average contract rate set at origination. The data are a 1-in-20 sample of closed-end first-lien mortgages from credit-bureau records, government loans included. Values refer to loans active at quarter end. No publication schedule or revision policy for the outstanding series is stated |
| Yahoo chart API (`https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>`) | verified access | MBB: ETF, first trade 2007-03-16, quote close (split-adjusted), `adjclose`, dividend events dated at the ex-date open (for example 0.336 on 2025-10-01). VMBS: first trade 2009-11-23, 203 distributions. PMBS: first trade 2024-09-23 |
| yfinance 1.7.0 | verified access | Same Yahoo endpoints. `Ticker.history(auto_adjust=False, actions=True)` returns Close, Adj Close, Dividends, and, for mutual funds, Capital Gains. Every price download in the development runs of 2026-11-02 used it |
| PDMIX (PIMCO GNMA and Government Securities Fund, Institutional class) on Yahoo | verified access | Checked through a browser on 2026-11-02 with the same chart API: instrument type MUTUALFUND, 7,359 daily NAVs from 1997-07-31 to 2026-10-30 with no missing closes, 373 distributions, all on trading days (including large December distributions in 2001–2012, up to 0.607 in 2010), no separate capital-gain events. The adjusted close and the rebuilt total return differ by at most 4.2 bp in any year. Its largest daily moves fall on known market days (2013-07-05, 2020-03-20, 2022-06-13, 2022-09-26, 2022-11-10, 2023-11-14). Benchmark: Bloomberg GNMA Index. Duration normally 1 to 7 years (2020 summary prospectus). Net assets about $554 million (Zacks, 2026-09-30) |
| PTRIX, PMRPX (PIMCO Mortgage-Backed Securities Fund share classes) on Yahoo | **unavailable** | Both symbols now resolve to "PIMCO ETF Trust - PIMCO Mortgage-Backed Securities Active Exchange-Traded Fund" with zero observations |
| iShares MBB product page | verified access | Inception 2007-03-13, Bloomberg U.S. MBS Index, 0.04% expense ratio, effective duration 5.71 years, weighted-average coupon 3.64, OAS 30.28 bp (as of 2026-10-29), monthly distributions. Used only as a present-day sanity check |
| SEC N-14 for the PMBS conversion | verified access (partial read) | Reorganization of PIMCO Mortgage-Backed Securities Fund into the PIMCO Mortgage-Backed Securities Active ETF, closing on or about 2024-09-20, ETF trading from 2024-09-23, same portfolio managers and objective. The performance-survivor share class was not in the portion read |
| Tiingo daily prices | documented but untested | Needs `TIINGO_API_KEY`. Fields `close` (unadjusted), `divCash`, `splitFactor` |
| FRED API (JSON) | documented but untested | Needs `FRED_API_KEY`. Missing values are `.` |

## Timing rules used by the pipeline

| Series | Economic observation date | Usable from | Basis |
|---|---|---|---|
| ETF closes and distributions | trading date | that day's 4 pm ET close | exchange close |
| Treasury yields (H.15) | trading date | that day's close | market-observable in real time. The official release follows within hours |
| PMMS 30-year rate | survey week ending Wednesday | the Thursday release date's close | Freddie Mac releases at 12:00 ET |
| NMDB stock note rate | quarter end | end of the following quarter | matches FHFA's current release (2026Q2 on 2026-09-30). The series was published years after 2013, so this is an availability approximation, not a true real-time vintage. Two quarters is a declared robustness check |
| Stock-rate proxy before mid-2013 | each PMMS release | that release's close | its half-life and level were fitted to 2013–2014 NMDB, so these values are labeled `proxy_retrospective` |

## Manual and local-file routes

Put files in `data/local_inputs/`. They are used only when the online routes fail, or for the history of PIMCO's Mortgage-Backed Securities Fund before its ETF conversion. For FRED the online routes are tried in this order: the graph CSV through Python, the same request through the system's `curl`, and the FRED API when `FRED_API_KEY` is set. A server that times out on every attempt is skipped for the rest of the run, so a stalled source costs well under a minute before the local file is used. On 2026-11-02 FRED answered browsers within a second but stalled Python's requests from the author's Mac, so this order matters.

| File | Contents |
|---|---|
| `<SERIES_ID>.csv` | A FRED graph CSV saved unchanged (header `observation_date,<ID>` or the older `DATE,<ID>`) |
| any file whose name contains `nmdb` and ends in `.zip` or `.csv` | The NMDB "National, Census Regions, and Census Divisions" download, unchanged |
| `<TICKER>_prices.csv` | Columns `date, close, dividend` (optional `adj_close`). `close` must not be adjusted for distributions. `dividend` is the cash amount on its ex-date |
| `pimco_ptrix_nav.csv` | Optional: daily history of PIMCO's Mortgage-Backed Securities Fund before its 2024 ETF conversion, with NAV (or a total-return index) in `close` and distributions in `dividend`. Build it with `tools/convert_pimco_nav.py` from a CRSP (`caldt, dnav, dret`), Bloomberg, or PIMCO export. The converter writes a provenance note next to it |

Capital-gain distributions, which mutual funds can pay, count as distributions in every parser (yfinance's `Capital Gains` column and the chart API's `capitalGains` events).

An alternate provider must supply economically equivalent fields. An adjusted price without distributions is rejected, because total returns are rebuilt from closes and distributions and checked against the provider's adjusted close.

## Licensing

Freddie Mac PMMS data are copyrighted (citation required). Yahoo data are subject to Yahoo's terms. FHFA and Federal Reserve data are public. Raw downloads and daily derived ledgers are excluded from version control by `.gitignore`. The manifest records each file's source, retrieval time, and SHA-256 hash.
