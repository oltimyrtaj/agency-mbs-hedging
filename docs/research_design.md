# Research design

**Project:** Dynamic Treasury hedging of Agency MBS
**Author:** Olti Myrtaj (Erdős Institute Quantitative Finance Boot Camp, Fall 2026)
**Design date:** 2026-11-02, written before any real-data run. Every choice below is encoded in `config/project.yaml`, and the `experiment` block is frozen by notebook 06 before any test-period evaluation.

## 1. The question

> **When does refinancing information help a mortgage investor adjust a Treasury hedge beyond what a simple updating hedge already achieves, and how much improvement survives realistic trading costs?**

Four connected questions carry the answer:

| # | Question | Kind of evidence | Notebook |
|---|---|---|---|
| Q1 | Does measured MBS rate exposure change meaningfully through time? | Measurement with error bars | 05 |
| Q2 | Does observable refinancing information forecast next month's exposure beyond persistence or rolling estimation? | Walk-forward forecast comparison | 06, 08 |
| Q3 | Does that information lower out-of-sample hedged risk relative to static and updating hedges? | Walk-forward hedge backtest | 07, 08 |
| Q4 | In which environments does any improvement justify its turnover and cost? | Cost grid, rebalancing rules, regimes, episodes | 08 |

## 2. What a mortgage-risk professional would add

**The decision.** A portfolio manager holds $100 million of Agency MBS pass-throughs and wants to keep the mortgage basis (spread and carry) while removing outright interest-rate exposure. At each month-end the manager sets the size of a short Treasury hedge for the next month.

| Element | Choice in this project |
|---|---|
| Portfolio | Constant $100mm exposure to the iShares MBS ETF (MBB) total return, a public proxy for the Bloomberg U.S. MBS Index. Gains and losses are swept to cash each day, so the exposure stays at $100mm. |
| Hedge instrument | A synthetic 10-year constant-maturity par Treasury priced from H.15 yields. It is reset to a new par bond every day, so its maturity stays at 10 years. It is a research approximation of a 10-year futures or cash hedge, and the project never calls it an actual futures position. |
| Objective | Minimize the variance of hedged excess returns, net of trading costs. Rate risk is the target. Basis risk is kept on purpose. |
| Hedge sizing | DV01 matching: hedge notional per $1 of MBS equals forecast MBS duration divided by the hedge bond's modified duration. |
| Information set | Only data whose availability time precedes the decision: closes through the decision day, PMMS releases through that day, and NMDB quarters whose (approximate) release date has passed. |
| Timing | Signal at the month-end close. Execution at the next trading day's close (base case). Delays of 0 and 5 days are sensitivity runs. |
| Constraints | Position limit of 1.5 times MBS notional (every limit hit is logged). Monthly rebalancing in the base case, with quarterly and duration-band alternatives. |
| Costs | One-way cost per dollar of hedge notional traded, on establishment, every rebalance, and final liquidation: 0, 1, 2 (base), 5, and 10 bp. These are declared assumptions, not measured market costs. A separate financing-spread sensitivity charges 10 bp per year on the short notional. |
| Accounting | Excess-return accounting relative to the 3-month bill: hedged P&L = MBS excess return minus hedge ratio times hedge excess return, minus costs. A short bond financed in repo (or a futures position) earns this excess return. Notebook 07 works one path by hand. |

**Explanation versus forecasting value.** Showing that duration moves with refinancing conditions (Q1 and the state relationship) explains the drift. It does not show that a forecast built on that relationship improves a hedge. The project keeps the two claims separate: Q2 and Q3 use only walk-forward forecasts, and they are judged against an updating statistical hedge as well as a static one.

**What the manager learns under each outcome.** If the hybrid hedge beats the updating hedge after costs, refinancing information earns a place in the re-hedging process. If the advantage appears only in fast transitions (2020, 2022), the result supports a conditional policy: update mechanically, and act on refinancing signals when they move sharply. If the hybrid and updating hedges are indistinguishable, a trailing estimate captures the usable information, and the refinancing model's role is explanation and risk communication. All three outcomes are useful to a mortgage desk.

## 3. The rawest useful starting material

A desk would start from holdings, pool characteristics, scheduled and unscheduled principal, prices, and risk reports. A public-data project can reach the following primary records, and each is stored unmodified with a manifest entry:

| Record | Source (verified 2026-11-02) | Why this level |
|---|---|---|
| MBB, VMBS, and PMBS daily closes, and the daily NAV of PIMCO's GNMA fund (PDMIX), with distribution amounts | Yahoo chart API (yfinance, or the direct API as fallback) | Closing prices plus ex-date distributions let us rebuild total returns ourselves and check them against Yahoo's adjusted close. |
| Treasury yields (DGS10, DGS5, DGS2, DGS3MO) | FRED CSV (Federal Reserve H.15) | Official daily observations. Bond-market holidays appear as blank rows. |
| 30-year mortgage rate | FRED MORTGAGE30US (Freddie Mac PMMS) | Dated by Thursday release. Freddie Mac's own spreadsheet is an optional cross-check. |
| Outstanding-mortgage note rates and rate-bucket shares | FHFA NMDB quarterly CSV (zip) and its data dictionary | The measured stock note rate, by market segment, weighted by unpaid balance. |

Loan-level data (Freddie Mac Single-Family) and N-PORT holdings would sharpen the refinancing measure, but they require registration or heavy parsing and do not change the decision question. They are listed as extensions.

## 4. Methods, and the question each answers

| Method | Implementation | Question it answers |
|---|---|---|
| Monthly realized empirical duration | Within-month OLS of daily MBB excess returns on same-day and previous-day 10-year yield changes, D = −(b₀ + b₁), Newey–West (2 lags) standard error with the HC3 leverage adjustment, at least 15 trading days. A development-period check adds the next day's yield change, because the yields are fixed around 3:30 pm and the ETF closes at 4 pm. | Q1: how large is exposure, and how precisely is it measured each month? |
| Variation beyond noise | Cochran's Q with a constant-duration residual bootstrap p-value, and a robust between-month standard deviation τ (observed variance of the monthly estimates minus their variance under the null). The textbook χ² p-value is shown only as a naive reference, because notebook 04 found it rejects a constant duration far too often. | Q1: is the variation real? |
| Updating statistical hedge (U) | Exponentially weighted daily regression at each month-end. The half-life is chosen on development data from {5, 10, 21, 42, 63, 126, 252} trading days. | Benchmark: what simple updating achieves |
| Refinancing state | Incentive I = agency stock note rate (NMDB) − PMMS rate, in percentage points. Share of borrowers in the money g(I) = Φ((I − θ)/σ), with θ = 0.5 pp fixed and σ estimated from NMDB rate buckets available in the development period. | Mechanism variable with saturation at both ends |
| Economic state model (E) | D̂ = c₀ + c₁ g(I), walk-forward weighted least squares | Q2 and Q3: does economics alone forecast exposure? |
| Hybrid (H, headline) | D̂ = U + ĉ₁ (g(I) − ḡ), where ḡ is the refinancing share averaged with the same weights the updating regression puts on each day. It starts from the updating estimate and adds only the refinancing-implied change since that estimate's effective date. With ĉ₁ = 0 it equals U. | The incremental-information question, with no extra free parameter |
| Forecast comparison | Squared error against next month's realized duration, noise-adjusted MSE, Clark–West test for the nested pair H vs U, Diebold–Mariano for E vs U | Q2 |
| Common backtest engine | One daily ledger for every strategy: positions, trades, costs, P&L, with identical windows, limits, delays, and costs | Q3 and Q4 |
| Uncertainty | Paired stationary block bootstrap of aligned weekly hedged returns (13-week mean block, 4 and 26 as checks). One-sided p-values read from the same bootstrap distribution as the intervals, with the Holm adjustment across the four declared comparisons, decide statistical support. | Q3 |
| Simulation | Known-truth recovery of the duration estimators, and full-pipeline refits in three kinds of synthetic world: duration driven by refinancing, constant duration, and duration that moves independently of refinancing | Validity of the estimators, power, and false-positive rate |

Tools: Python with NumPy, pandas, SciPy, and statsmodels (used to cross-check the hand-written HAC regressions), Matplotlib, PyArrow for Parquet, requests and yfinance for downloads, nbformat and nbclient for notebook execution, and pytest. No machine learning is used, because about 140 test months cannot support it and it would not answer the question better.

## 5. Sample split and the proxy timing trap

| Period | Months | Use |
|---|---|---|
| Measurement start | 2007-04 | First full month of MBB trading |
| Development | 2007-04 to 2014-12 | Static hedge, EWMA half-life, proxy calibration, dispersion σ. Walk-forward development forecasts start in 2010-04 after a 36-month burn-in. |
| Final test | 2015-01 to the last complete month | Run after the freeze. Every forecast uses an expanding window that ends at its decision date. |

NMDB begins in 2013Q1 and its first quarter is usable at the end of June 2013 under the base availability rule. Before that, the stock note rate comes from an exponentially weighted average of past PMMS rates whose half-life and level are fitted to the NMDB quarters available by December 2014. That calibration uses 2013–2014 information, so **every development-period forecast that uses the pre-2013 proxy is retrospective**. Those forecasts are labeled `incentive_source = proxy_retrospective` and serve only for teaching and development. They never count as historical trading evidence. Test-period decisions use information dated before each decision. A declared robustness run removes the proxy from test-period models entirely: the state model trains only on NMDB-measured months (from mid-2013), and the hybrid's average share ḡ uses only NMDB-era days. Until 24 NMDB training pairs exist, that run's economic model uses the static duration and its hybrid equals the updating hedge, and the number of such decisions is reported.

NMDB statistics were published years after 2013, so even the NMDB-based incentive is an availability approximation: the stock note rate was knowable at the time from agency pool disclosures, and the one-quarter lag matches FHFA's current release timing. The two-quarter lag is a declared robustness run.

## 6. Benchmarks, fairness, and the ex-post diagnostic

All strategies share the same eligible dates, $100mm notional, position limit, execution delay, cost treatment, and backtest engine. The headline challenger (H) and the four primary comparisons (H vs U, E vs U, U vs S, H vs S) are declared here, before any test result exists. Persistence (P) and AR(1) are the forecasting benchmarks.

Strategy X hedges with next month's realized duration. It is infeasible, it is labeled as a diagnostic, and it is never called an upper bound or a basis-risk floor, because it is estimated with noise from the same month it hedges. Ratios that use it as a denominator are reported only when the denominator is clearly positive.

## 7. What counts as success

| Term | Definition (declared before evaluation) |
|---|---|
| Primary risk metric | Annualized standard deviation of weekly gross hedged excess returns over the test period, and the variance reduction 1 − Var(challenger)/Var(comparator) |
| Practical effect-size targets | At least 5% variance reduction against U and at least 10% against S. These are targets for economic relevance, separate from statistical tests. |
| Statistical support | The 95% paired-bootstrap interval for the variance reduction lies above zero, and for the four declared comparisons the Holm-adjusted one-sided p-value for "no variance reduction" is also below 0.025 (the one-sided level that matches a two-sided 95% interval). The p-value comes from the same bootstrap distribution as the interval, so a supported result never sits next to an interval that includes zero, and the Holm adjustment keeps the chance of any false pass across the four comparisons at that level. Outside the family (regime slices, for example) results are descriptive only. A wide interval means the evidence is inconclusive. It does not show that the effect is zero. |
| Survives costs | At the 2 bp base cost, the value of the volatility reduction, priced at a hurdle information ratio of 0.5, exceeds the extra annual cost: 0.5 × (σ_comparator − σ_challenger) > cost_challenger − cost_comparator. Statistical support is also required. The break-even cost per trade is reported so readers can apply their own hurdle. |
| Residual exposure | Slope of weekly hedged returns on weekly 10-year yield changes, reported in years of duration with HAC errors |

Lower volatility after subtracting costs is not used as evidence of cost effectiveness, because a near-constant cost drag lowers the mean without changing the volatility.

**Outcome mapping.** Notebook 08 classifies the headline result mechanically into one of four outcomes declared in `docs/outcome_interpretations.md`: a useful improvement, a small but statistically supported improvement, an advantage limited to particular environments, or no demonstrated gain over the simple updating hedge. A no-gain result is called inconclusive when its 95% interval still reaches the 5% practical target, and is said to rule out a useful gain when the whole interval lies below 5%. The rule is coded in `evaluation.classify_outcome`, which the freeze covers.

## 8. Validation matched to each claim

| Claim | Validation | Label |
|---|---|---|
| The realized-duration estimator is unbiased with honest error bars | Known-truth simulation (bias, interval coverage) | Simulation |
| The variation test has the right false-positive rate | Constant-duration worlds: rejection rates of the naive χ² and the bootstrap p-values | Simulation |
| The cost verdict rarely reports a gain that is not there, and its power at a realistic effect is known | Full-pipeline refits in reference null worlds (duration that moves independently of refinancing for the hybrid against the updating hedge, constant duration for comparisons against the static hedge) and in worlds where refinancing drives duration | Simulation |
| The pipeline cannot see the future | Perturbation test: corrupt every input unavailable at a decision and confirm earlier signals and positions are unchanged, at both observation and release times | Unit test and notebook check |
| The accounting is right | Hand-worked ledger, zero-hedge identity, cost reconciliation, daily-to-weekly aggregation | Unit test and notebook 07 |
| The hedge instrument is priced correctly | Par at issue, analytic DV01 against finite differences | Unit test |
| Refinancing information improves hedging | Walk-forward test-period backtest with bootstrap intervals | Historical out-of-sample |
| The result is not specific to MBB | Same frozen recipe re-estimated on VMBS's own history and on PIMCO's GNMA fund (a different mortgage pool under active management), plus MBB's coefficients applied to each unchanged | External validation |
| How a PIMCO fund's exposure differs from the index's | Monthly durations compared over the test period: correlation, mean difference, and the slope of the difference on the refinancing share at the start of the month, with Newey–West errors | Descriptive |

## 9. Scope boundaries

In the core: data adapters, the teaching example, exposure estimation, static, updating, persistence, AR, economic, and hybrid hedges, the walk-forward backtest with costs, simulation validation, external validation on VMBS and on PIMCO's GNMA fund, and the evidence exports.

Deferred with reasons: N-PORT effective-duration decomposition (heavy parsing, and it explains rather than tests), loan-level prepayment estimation (registration and scale), OAS-model durations and swaption hedging (subscription data), a two-instrument curve hedge (the 5-year single-instrument run answers the tenor question first), and machine learning (sample size). PIMCO converted its Mortgage-Backed Securities Fund into the PMBS ETF in September 2024, and the fund's earlier daily history is no longer available from free sources, so that run needs a user-supplied NAV file. PIMCO's GNMA fund, with free daily NAV since 1997, is the PIMCO fund in the core, and PMBS gets a short descriptive comparison.
