# Dynamic Treasury Hedging of Agency MBS

**Olti Myrtaj** · Erdős Institute Quantitative Finance Boot Camp, Fall 2026

> **When does refinancing information help a mortgage investor adjust a Treasury hedge beyond what a simple updating hedge already achieves, and how much improvement survives realistic trading costs?**

## Why this question

Agency mortgage-backed securities (MBS) are about a quarter of the U.S. core bond market. Every homeowner behind them can refinance, so an MBS shortens when rates fall and lengthens when rates rise. A Treasury hedge sized to last month's exposure is too large after a rally and too small after a selloff, and the error grows exactly when rates move most. Mortgage desks therefore re-hedge. The practical question is *what to re-hedge on*: a trailing statistical estimate of exposure, or that estimate plus what refinancing conditions imply about where exposure is heading.

This project builds on the author's 2025 project (hedging a Treasury portfolio whose cash flows are fixed) by moving to an asset whose exposure moves with the market.

## What the project does

1. **Measures** the empirical rate exposure (duration) of the iShares MBS ETF every month from daily data, with error bars, and tests whether it varies by more than noise (Q1).
2. **Builds the refinancing state** from public data: the average note rate on outstanding agency-eligible mortgages (FHFA National Mortgage Database) minus the current Freddie Mac 30-year rate, converted into the share of borrowers who can profitably refinance.
3. **Forecasts** next month's exposure walk-forward with a static rule, an updating (EWMA) estimate, persistence, AR(1), an economic state model, and a hybrid that adds the refinancing-implied change to the updating estimate (Q2).
4. **Hedges** a constant $100mm MBS position with a DV01-matched short in a synthetic 10-year Treasury, every rule through one backtest engine with the same timing, limits, and costs (Q3).
5. **Prices the decision**: risk reduced, risk left over, turnover, and cost per year, with paired block-bootstrap intervals, a declared cost verdict, rebalancing rules, regimes, and stress episodes (Q4).
6. **Validates** everything that can be validated: known-truth simulations of the estimators and of the full pipeline, look-ahead perturbation tests at observation and release times, accounting reconciliation, and external checks on a second MBS ETF (VMBS) and on PIMCO's GNMA fund (PDMIX), an actively managed mortgage fund with daily NAV since 1997.

The experiment is frozen (settings, code, and development choices hashed) before any test-period result is computed. The development period is April 2007 to December 2014. The final test runs from January 2015 to the last complete month.

## Results

Results are produced by running the project (see `RUN_ME_FIRST.md`). After a full run:

* `reports/figures/fig1_chain_state_exposure_hedge_outcome.png`: refinancing state, exposure, hedge, and outcome on one timeline
* `reports/tables/main_strategy_table.csv` and `reports/tables/cost_verdicts.csv`: the decision table
* `results/claims/claim_ledger.csv`: every headline number with its source and status
* `results/evaluation/outcome.json`: which pre-declared outcome applies (see `docs/outcome_interpretations.md`)

No empirical result is written into this README before the run.

## Quick start

```bash
conda env create -f environment.yml
conda activate mbshedge
python run_project.py --mode smoke
python run_project.py --mode full
```

The prompt should start with `(mbshedge)` after the second line. The smoke run (about 2 to 3 minutes) uses synthetic data and proves the setup works. The full run (about 12 minutes) downloads the data, freezes the experiment, evaluates it, and builds the return bundle. Paste commands without the explanations: the default macOS shell (zsh) passes text after `#` on to the command. A plain Python environment works too (see `RUN_ME_FIRST.md`).

Full instructions, troubleshooting, and the manual-data route are in `RUN_ME_FIRST.md`.

## Repository map

| Path | Contents |
|---|---|
| `notebooks/00_project_guide.ipynb` | The question, mechanism, glossary, frozen settings, run status |
| `notebooks/01_data_collection.ipynb` | Downloads with caching and a hashed manifest, access status |
| `notebooks/02_data_preparation.ipynb` | Trading calendar, total returns, hedge-bond pricing, refinancing state on release dates |
| `notebooks/03_mechanism_teaching_example.ipynb` | Why MBS duration moves and why a hedge goes stale (assumed behavior), plus development-only exploration |
| `notebooks/04_simulation_validation.ipynb` | Known-truth recovery, test calibration, full-pipeline power and false-positive rate |
| `notebooks/05_exposure_estimation.ipynb` | Monthly empirical duration and the variation test (development months shown) |
| `notebooks/06_forecasts_and_freeze.ipynb` | Development choices, the freeze, test-period forecasts, look-ahead check |
| `notebooks/07_hedge_backtest.ipynb` | The common backtest engine, hand-worked accounting, reconciliation, rule and cost grid |
| `notebooks/08_results_robustness_episodes.ipynb` | Q1 to Q4 results, bootstrap intervals, cost verdicts, regimes, episodes, robustness, outcome |
| `notebooks/09_external_validation.ipynb` | Recipe and coefficient transfer on VMBS and on PIMCO's GNMA fund, PIMCO-versus-index exposure comparison, PMBS descriptive comparison, and the pre-2024 PIMCO MBS fund when its history is supplied |
| `notebooks/10_figures_and_handoff.ipynb` | Final figures from saved results, claim ledger, limitations, run manifest, return bundle |
| `src/mbshedge/` | Shared code: sources, synthetic worlds, preparation, instruments, exposure, models, backtest, evaluation, simulation, freeze, claims, plotting, teaching, bundle |
| `tests/` | 89 tests: pricing, parsers, total returns, timing, estimators, accounting, metrics, look-ahead, freeze, the PIMCO file converter, and the fund comparison |
| `tools/` | `check_network.py` (a quick check of the data sources) and `convert_pimco_nav.py` (turns a CRSP, Bloomberg, or PIMCO NAV export into the PTRIX input file) |
| `config/project.yaml` | Every path, date, seed, source, and experiment choice |
| `docs/` | Research design, decision log, data sources and dictionary, limitations, freeze procedure, outcome interpretations, reference review, 2025 template notes |
| `communication/templates_2025/` | Byte-identical copies of the 2025 slides, executive summary, and talk script (kept local, excluded from the public repository) |
| `run_project.py` | Runs the tests and the notebooks in order with fresh kernels, writes logs, builds the return bundle |

## Data

All core inputs are free and public: FRED (Treasury yields from the Federal Reserve's H.15 release, and Freddie Mac's PMMS 30-year rate), the FHFA National Mortgage Database outstanding-mortgage statistics, and daily ETF prices and PIMCO's GNMA fund NAV, with distributions, from Yahoo Finance. Raw third-party files are excluded from version control. The manifest's hashes let anyone rebuild and verify them. Details, verification dates, and manual fallbacks are in `docs/data_sources.md`.

## Principal references

Breeden (1991, 1997) on mortgage hedging and empirical option costs. Hayre and Chang (1996) on effective versus empirical durations. Hanson (2014) and Malkhozov, Mueller, Vedolin, and Venter (2016) on mortgage convexity and the yield curve. Boyarchenko, Fuster, and Lucca (2019) on mortgage spreads. Dimson (1979) on asynchronous prices. Newey and West (1987), MacKinnon and White (1985), Politis and Romano (1994), Diebold and Mariano (1995), Clark and West (2007), Holm (1979), and DerSimonian and Laird (1986) for the statistics. Confirm volume and page details before quoting them.
