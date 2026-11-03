# Data dictionary

Units: yields in percent, yield changes in decimals (0.0001 = 1 bp), returns in decimals, durations in years, the incentive in percentage points, hedge ratios in dollars of hedge notional per dollar of MBS. Every field has an observation date and an availability rule (see `docs/data_sources.md`). The same table is written by notebook 02 to `results/state/data_dictionary.csv`.

## Daily panel: `data/processed/daily_panel.parquet`

Index `date`: trading dates on which MBB has a close and the 10-year yield is published.

| Column | Description | Units | Usable from |
|---|---|---|---|
| days | Calendar days since the previous trading date | days | close |
| tr_mbb | MBB total return, (close + distribution) / previous close - 1, compounded over skipped days | decimal | close |
| rf | 3-month bill accrual: DGS3MO(previous date) / 100 × days / 365 | decimal | close |
| r_mbb_ex | MBB excess return: tr_mbb - rf | decimal | close |
| y10, y5, y2, y3m | Treasury constant-maturity yields | percent | close |
| dy10, dy5 | Change in the 10-year (5-year) yield since the previous trading date | decimal | close |
| r_h10, r_h5 | Total return of the daily-reset synthetic 10-year (5-year) par Treasury | decimal | close |
| r_h10_ex, r_h5_ex | Hedge-bond excess return | decimal | close |
| dur_h10, dur_h5 | Modified duration of a new par bond at the close | years | close |
| tr_vmbs, r_vmbs_ex, tr_pmbs, r_pmbs_ex, tr_pdmix, r_pdmix_ex | Same construction for VMBS, PMBS, and PIMCO's GNMA fund PDMIX (missing before inception). PDMIX is a mutual fund, so its close is the daily NAV | decimal | close (NAV struck at 4 pm ET for PDMIX) |
| pmms, pmms_release_date | Latest PMMS 30-year rate released on or before the date, and its release date | percent, date | release date |
| stock_rate | Average note rate on outstanding agency-eligible mortgages (UPB-weighted Enterprise and Government markets), or the proxy before NMDB is available | percent | stock_rate_available_from |
| stock_rate_quarter_end, stock_rate_available_from | The NMDB quarter in use and the date it became usable | dates | n/a |
| incentive | stock_rate - pmms | percentage points | latest input date |
| g | Share of borrowers in the money: Φ((incentive - θ)/σ), θ = 0.5 pp, σ from development NMDB buckets | 0 to 1 | as incentive |
| incentive_source | `nmdb` or `proxy_retrospective` | label | n/a |

## Monthly panel: `data/processed/monthly_panel.parquet`

Index `month`. One row per calendar month, valued at its last trading date (the decision date).

| Column | Description | Units |
|---|---|---|
| decision_date | Last trading date of the month | date |
| D, se | Realized empirical duration of the month and its Newey-West (2 lags, HC3 leverage-adjusted) standard error | years |
| n_days, r2, valid, flag | Days used, regression R², usable flag, reason when unusable | |
| U_h, gbar_h | Updating (EWMA) duration with half-life h trading days at the decision date, and the share in the money averaged with that regression's information weights | years, share |
| g, incentive, incentive_source, pmms, stock_rate, y10 | State at the decision date | as above |

## Forecast records: `results/forecasts/forecasts_{dev,test}.csv`

| Column | Description |
|---|---|
| model | S, U, P, AR, E, H, or X (X is infeasible: it uses the target month's realized duration) |
| decision_month, decision_date | Month whose close is the decision time |
| target_month | Month whose exposure is forecast (decision_month + 1) |
| available_at | Close after which every input was public (the decision date's close) |
| training_cutoff_month | Last month whose realized duration could enter training (equal to decision_month) |
| execution_date | Close at which the hedge trade is executed (test file) |
| n_train | Training pairs used by AR, E, and H |
| forecast | Forecast duration in years |
| c0, c1, tau2, ar_a, ar_rho | Fitted parameters at that decision |
| incentive_source | Source of the incentive at the decision date |
| fallback | True only in the NMDB-only robustness run, at decisions where the state model had fewer than 24 training pairs (E then uses the static duration and H the updating estimate) |
| realized, realized_se, realized_valid | Target month's realized duration (for evaluation only) |

## Backtest outputs: `results/backtest/`

| File | Contents |
|---|---|
| `ledger_test_base_<S>.parquet` | Daily ledger per strategy: h_held, trade, mbs_pnl, hedge_pnl, cost, financing, gross_pnl, net_pnl (per $1 of MBS) |
| `weekly_test_base.parquet` | Friday-ending weekly sums by strategy, plus the weekly yield change. Weeks with fewer than 3 trading days are left out of the risk measures, and their costs are carried into the adjacent kept week so weekly costs add up to the ledger |
| `trades_test_base.csv` | Every decision: forecast, hedge duration, target hedge ratio, executed or not, and why |
| `info_test_base.csv` | Window, turnover per year, cost per year, financing per year, position-limit hits |
| `weekly_test_grid.parquet` | Weekly gross P&L and 1 bp cost for every strategy × rebalancing rule × delay (and financing sensitivity) |

## Evaluation outputs: `results/evaluation/`

`main_table_test.csv`, `bootstrap_test.csv`, `verdicts_test.csv`, `forecast_table_test.csv`, `forecast_tests_test.json`, `grid_metrics_test.csv`, `cost_grid_verdicts_test.csv`, `regimes_test.csv`, `episodes_test.csv`, `robustness_test.csv`, `convexity_test.csv`, `q1_variation.json`, `expost_gap_share.csv`, `outcome.json`. Column meanings follow the notebook 08 headings and `src/mbshedge/evaluation.py` docstrings. The columns most often quoted:

| File | Column or key | Meaning |
|---|---|---|
| `bootstrap_test.csv` | p_one_sided, p_holm, primary | One-sided bootstrap p-value for "no variance reduction" (the share of resamples with no reduction), its Holm adjustment over the four declared comparisons (blank outside them), and whether the row is one of the four |
| `verdicts_test.csv` | statistical_support, support_rule | Whether the statistical requirement of the survives-costs verdict holds, and which rule applied (95% interval above zero, plus a Holm-adjusted p below 0.025 for the four declared comparisons) |
| `verdicts_test.csv` | breakeven_cost_bp_per_trade, net_gain_positive_when | The cost per unit traded at which the net gain changes sign, and on which side of it the challenger wins (below, above, at every cost, or at no cost). Blank when the gain never changes sign |
| `outcome.json` | outcome, inconclusive, rules_out_practical_gain, ci_high | The pre-declared outcome, and for a no-gain outcome whether the 95% interval still reaches the 5% target (inconclusive) or lies below it |
| `robustness_test.csv` | weeks, fallback_decisions | Weeks compared in each check, and decisions at which the NMDB-only run used the fallback |

Exposure and simulation outputs: `results/exposure/lead_lag_development.json` holds the development-period timing check (lead and lag effects in years, and the change in average duration when the lead is added). `results/simulation/worlds_{state,constant,unrelated}.csv` hold one row per synthetic world, and `power_summary.json` holds, per comparison, the reference null, its false-positive rate, and the power at the state worlds' effect size.
