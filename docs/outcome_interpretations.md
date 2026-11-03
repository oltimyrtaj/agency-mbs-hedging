# Pre-declared outcome interpretations

Written on 2026-11-02, before any real-data run, and revised the same day (still before any real-data run) after an independent code review: the inconclusive rule now uses the test period's own interval, and statistical support uses the Holm adjustment. Notebook 08 applies the mapping below mechanically and records the result in `results/evaluation/outcome.json`. The summary, slides, and talk should use the interpretation that applies, filled in with numbers from the claim ledger. The bracketed items are placeholders for ledger values.

## The mapping

| Outcome | Rule (H = hybrid, U = updating hedge, base settings) |
|---|---|
| 1. Useful improvement | H passes the survives-costs verdict against U at 2 bp and its variance reduction is at least 5% |
| 2. Small but statistically supported improvement | H passes the survives-costs verdict against U, but its variance reduction is below 5% |
| 3. Advantage limited to particular environments | Neither of the above, the overall point estimate favors H, and in at least one declared regime slice with at least 52 weeks H reduces variance by at least 5% with a bootstrap interval above zero |
| 4. No demonstrated gain over the simple updating hedge | Otherwise. It is called inconclusive if the 95% interval for the variance reduction still reaches the 5% practical target, and it rules out a useful gain if the whole interval lies below 5% |

## Interpretations

**1. Useful improvement.** Refinancing information earns a place in the re-hedging process. Starting from a trailing estimate of exposure and adding the duration change implied by how many borrowers can refinance cut weekly hedged variance by [VR] relative to the updating hedge over [test window], for an extra [cost] bp a year, and the improvement would survive trading costs up to [break-even] bp per trade. For a mortgage desk this means re-hedging on refinancing signals adds value beyond mechanical updating, especially when the incentive moves quickly.

**2. Small but statistically supported improvement.** The refinancing signal reliably improves on the updating hedge, but the gain ([VR]) is below the 5% level a desk would usually notice. It pays for its trading cost at the assumed hurdle, so it is a refinement to an updating process rather than a reason to rebuild one.

**3. Advantage limited to particular environments.** Refinancing information helps when the refinancing state moves fast, for example [slice or episode], and adds little in locked-in or stable periods. A practical policy is to update the hedge mechanically and act on refinancing signals when the incentive crosses into or out of the money. The overall result is not statistically decisive, so this is a conditional, descriptive conclusion.

**4. No demonstrated gain over the simple updating hedge.** Exposure moves (Q1 shows by how much), and updating the hedge [does / does not] beat a static hedge, but a trailing estimate already captures the usable information. The refinancing model still explains *why* duration moved and is useful for risk communication, scenario analysis, and setting tolerance bands. If the result is inconclusive, say that the data cannot rule out a gain as large as [CI upper end] in variance, and cite notebook 04's power for an effect of the size the simulated refinancing worlds produce. If the interval lies below 5%, say that a gain of 5% or more is ruled out over this test period.

## Always report alongside the outcome

* Q1: how much exposure varies (robust τ) and its range.
* Whether updating beats static (U vs S), because that sets the value of any re-hedging.
* Residual exposure left by each hedge, and the share of risk that is basis risk no duration hedge can remove (strategy X).
* Concentration: the largest single-episode share of the gain and the leave-one-out result.
* The VMBS check, and that VMBS is not an independent market.
* PIMCO's GNMA fund (and the PIMCO Mortgage-Backed Securities Fund before its 2024 conversion, if its history was supplied): the same comparisons on a fund with a different mortgage pool and active management. Agreement with MBB supports the recipe beyond one index fund. A difference describes that fund, and it cannot be attributed to PIMCO's management alone, because the fund also holds a different mortgage pool. None of it measures PIMCO's trades or skill.
* The descriptive exposure comparison, read by its 95% interval: a slope difference above zero means the PIMCO fund's duration fell by less than the index's as more borrowers could refinance, below zero means by more, and an interval covering zero means no measurable difference over the test period.
