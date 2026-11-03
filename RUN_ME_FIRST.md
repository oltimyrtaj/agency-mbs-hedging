# Run me first

This page takes you from a fresh download to the full results, packaged as a return bundle for the communication stage. Plan on about 20 minutes, most of it waiting.

## 1. Create a clean environment

Your 2025 notebooks ran on Python 3.7, which current scientific packages no longer support. Use a new environment so nothing old interferes.

**With conda (recommended on a Mac with Anaconda):**

```bash
cd "<path to>/agency-mbs-hedging"
conda env create -f environment.yml
conda activate mbshedge
```

After `conda activate`, the prompt should start with `(mbshedge)`, and `python --version` should report Python 3.13. Run every later command in this activated window. If `conda activate` reports that the shell is not configured, run `conda init zsh`, open a new Terminal window, `cd` back to the project folder, and activate again.

**With plain Python 3.11, 3.12, or 3.13:**

```bash
cd "<path to>/agency-mbs-hedging"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
```

On Windows the activation command is `.venv\Scripts\activate`. The lock file holds the exact tested versions and needs Python 3.13. On Python 3.11 or 3.12, install `requirements.txt` instead.

Tested combinations (2026-11-02): Python 3.13.18 with `requirements-lock.txt`, and Python 3.11.18 with numpy 1.26.4, pandas 2.2.3, scipy 1.11.4, statsmodels 0.14.4, matplotlib 3.9.4, pyarrow 15.0.2, and ipykernel 6.30.1. Python 3.12 lies inside the tested range and was not run separately. The conda file was not tested here (no conda was available), but it installs the same pinned versions through pip. matplotlib older than 3.9 fails with IPython 9 or newer.

## 2. Prove the installation (smoke run, synthetic data)

```bash
python run_project.py --mode smoke
```

This runs the 78 tests and then all eleven notebooks on a labeled synthetic world, in about 2 to 3 minutes. Every output goes to `outputs/smoke/` and every figure is watermarked SYNTHETIC. The log should end with `RUN COMPLETED`. Nothing in `outputs/smoke/` is an empirical result.

## 3. Run the real project

```bash
python run_project.py --mode full
```

What happens, in order:

| Step | Notebook | Time |
|---|---|---|
| Tests | `tests/` | 10 s |
| Downloads (FRED, FHFA NMDB, Yahoo) with a hashed manifest | 01 | about 1 min |
| Panels, total returns, hedge bond, refinancing state | 02 | 10 s |
| Teaching example and development-only exploration | 03 | 10 s |
| Simulation validation (180 synthetic worlds) | 04 | about 6 min |
| Monthly exposure (development months shown) | 05 | 15 s |
| Development choices, **freeze**, test forecasts, look-ahead check | 06 | 30 s |
| Backtests and grid | 07 | 30 s |
| Results, robustness, episodes, outcome | 08 | 1 to 3 min |
| VMBS and PIMCO funds | 09 | about 1 min |
| Final figures, claim ledger, bundle | 10 | 20 s |

If you want to read the development results before the test period is opened, run `python run_project.py --mode development` first (it stops after the freeze in notebook 06), then `--mode full`.

**When to run.** The test period ends with the last month whose final trading day is in the data. FRED usually posts Treasury yields one business day late, so October 2026 becomes complete once the October 30 yields appear, normally by Monday, November 2. Notebook 06 prints the data end date and the last month included. Downloads are cached and reused on later runs, so if a first download happened before those yields were posted, set `refresh: true` under `data:` in `config/project.yaml` for one run to fetch fresh files (the earlier files stay in the raw store and the manifest).

You can also open JupyterLab (`pip install jupyterlab`, then `jupyter lab`) and run the notebooks in order 00 to 10. Register the environment as a kernel first: `python -m ipykernel install --user --name mbshedge --display-name "Python (mbs hedging)"`, and pick that kernel. Each notebook reads only files written by earlier notebooks.

## 4. If a download fails

Notebook 01 prints the reason and the manual route. Place files in `data/local_inputs/` and rerun.

| Source | Manual file | Format |
|---|---|---|
| A FRED series (for example DGS10) | `data/local_inputs/DGS10.csv` | Save the CSV from `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10` unchanged |
| FHFA NMDB | `data/local_inputs/nmdb-outstanding-mortgage-statistics-national-census-areas-quarterly.zip` | The "National, Census Regions, and Census Divisions [CSV]" zip from `https://www.fhfa.gov/data/nmdb`, unchanged |
| ETF and fund prices (MBB, VMBS, PMBS, PDMIX) | `data/local_inputs/MBB_prices.csv` | Columns `date,close,dividend`: the close not adjusted for distributions, and the cash distribution on its ex-date (0 on other days). An adjusted price alone is not accepted. |

Optional credentials: set `FRED_API_KEY` (free from FRED) or `TIINGO_API_KEY` as environment variables before running. Never write keys into files in this project.

If Yahoo blocks yfinance, the code tries Yahoo's chart API directly, then Tiingo (if a key is set), then the local file.

## 5. PIMCO data

PIMCO's GNMA fund (PDMIX) downloads automatically with the other prices. Nothing is needed for it.

PIMCO's Mortgage-Backed Securities Fund was converted into the PMBS ETF in September 2024, and Yahoo no longer has the fund's earlier daily history (verified 2026-11-02). To add it, export its daily history (the Institutional class, PTRIX, if you can) from one of these:

* **CRSP through WRDS.** In CRSP's mutual fund data, find the fund's CRSP fund number by name, then download its daily returns and NAV (variables `caldt`, `dnav`, `dret`) as CSV. Check first that your institution's subscription includes CRSP's mutual fund database.
* **A Bloomberg Terminal.** Export daily NAV with the daily total return, or NAV with the distribution history, to Excel and save it as CSV.
* **PIMCO.** PIMCO's fund shareholder services (listed on pimco.com) can supply historical daily NAVs and distributions.

Then convert the export (it is never modified) and rerun notebooks 09 and 10:

```bash
python tools/convert_pimco_nav.py ~/Downloads/your_export.csv --source "CRSP via WRDS, Institutional class"
python run_project.py --mode full --only 09 10
```

The converter recognizes CRSP, Bloomberg, and NAV-with-distributions layouts, writes `data/local_inputs/pimco_ptrix_nav.csv` with a provenance note next to it, and refuses to overwrite an existing file unless you pass `--force` (the old file is then kept as a backup). The PTRIX analysis is part of the frozen notebook 09, so adding the file after the full run is fine. CRSP and Bloomberg data are licensed: they stay in `data/local_inputs/`, which `.gitignore` keeps out of the public repository.

## 6. The return bundle

After the full run, the newest zip in `return_bundle/` holds the executed notebooks, results, figures, tables, the freeze record and test log, the claim ledger, the logs, package versions, and a checksum manifest. `return_bundle/BUNDLE_CHECKLIST.md` lists what to confirm before using it. The raw third-party files are deliberately left out, and their hashes are in the manifest.

## 7. If something goes wrong

* **A core notebook fails**: the run stops and saves the partly executed notebook. The error is in `logs/error_<notebook>_<time>.txt`. Send that file with the bundle or the log.
* **"The frozen experiment does not match this run"**: something in `config/project.yaml` (frozen block), a result-relevant file in `src/mbshedge/`, or a code cell of notebooks 02 or 05 to 09 changed after the test period was first computed. If the change is deliberate, describe it in `docs/post_freeze_changes.md` and rerun with `MBSHEDGE_ALLOW_POST_FREEZE=1 python run_project.py --mode full`. The test log will mark those evaluations as post-freeze. Changes made before the first full run (for example after a development-mode run) do not trigger this: the freeze is simply replaced and the replacement is logged.
* **Different numbers on a rerun with fresh downloads**: providers occasionally revise history. Compare the manifest hashes in `data/raw/manifest.csv` between runs.
* **Kernel messages**: the notebook kernel's own start-up and crash messages go to `logs/kernel_stderr_<time>.txt` so the console stays readable. Recent ipykernel versions write a notice there that the kernel connection is unencrypted. That connection stays on your own machine (127.0.0.1), so the notice needs no action.
