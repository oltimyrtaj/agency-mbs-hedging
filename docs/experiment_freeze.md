# The experiment freeze

## What is frozen

Notebook 06 writes `results/freeze/freeze_record.json` (and a readable `freeze_record.md`) after all development choices are made and before any test-period result is computed. The record holds:

| Item | How it is pinned |
|---|---|
| The `experiment` block of `config/project.yaml` (models, comparisons, headline challenger, windows, costs, rules, delays, evaluation settings, episode dates, seed), plus the timing rules and NMDB market choices | SHA-256 of a canonical JSON dump |
| Result-relevant code: `config.py`, `sources.py`, `prepare.py`, `instruments.py`, `exposure.py`, `models.py`, `backtest.py`, `evaluation.py` (including the outcome mapping in `classify_outcome`), `pipeline.py`, `simulation.py`, `synthetic.py` | SHA-256 over the files. Plotting, teaching, and packaging code are excluded so cosmetic fixes do not break the freeze |
| Analysis notebook code: the code cells of notebooks 02, 05, 06, 07, 08, and 09, which hold the regime, episode, robustness, and comparison definitions | SHA-256 over the code cells only, so executing a notebook or editing its prose does not change it |
| The raw-data manifest at freeze time | SHA-256 (recorded for information, data refreshes do not block) |
| Development choices: static duration, EWMA half-life with the full selection table, proxy half-life and offset, note-rate dispersion σ, θ, NMDB markets and lag, first development and test decisions | stored values |

## What happens on reruns

* A rerun recomputes the development choices. If they and all the hashes match, the run proceeds and the record is reported as `verified`.
* Until the first test-period computation is logged (notebook 06 logs the test forecasts in full mode), a record that no longer matches is simply replaced, because nothing about the test period has been seen yet. The replacement is logged in `results/freeze/events.csv`. A development-mode run therefore never locks you in.
* After that, notebooks 06 to 10 stop with an explanation if the configuration, the result-relevant code, the analysis notebook code, or a development choice changed.
* Smoke runs replace their synthetic record whenever it no longer matches, because nothing in them is real.
* Every test-period evaluation appends a row to `results/freeze/test_evaluation_log.csv` (time, notebook, what was computed, and whether it ran after a post-freeze change). The log shows how many times the test sample was evaluated.

## Deliberate changes after the freeze

1. Describe the change, the reason, and the files in `docs/post_freeze_changes.md`.
2. Rerun with `MBSHEDGE_ALLOW_POST_FREEZE=1`.
3. Report results before and after the change. Later evaluations are marked `post_freeze` in the log, and `results/run_manifest.json` records `post_freeze: true`.

Starting a completely new freeze means archiving and deleting `results/freeze/`, which resets the evaluation history. Say so if you do it.

## What this record is and is not

It is a local, hash-based commitment that makes later changes visible. It is not a public, independently timestamped preregistration. A git commit or tag, or posting the hashes somewhere public before the full run, would add independent timestamping.

## Design-stage commitments made before any real data were seen

Recorded on 2026-11-02 in `docs/research_design.md` and `docs/decision_log.md`: the question, the four primary comparisons, the headline challenger (H), the effect-size targets, the survives-costs definition, the outcome mapping (`docs/outcome_interpretations.md`), the episode windows, the regime thresholds, and the robustness list.
