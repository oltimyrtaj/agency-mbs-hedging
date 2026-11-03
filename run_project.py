#!/usr/bin/env python
"""Run the project notebooks in dependency order, each in a fresh kernel.

Usage (from the project folder):
    python run_project.py --mode smoke          # synthetic data, about 2-3 minutes, proves the install works
    python run_project.py --mode development    # real data, stops after the experiment freeze (notebook 06)
    python run_project.py --mode full           # real data, freeze, test evaluation, return bundle

Options:
    --skip-tests            do not run pytest first
    --only 05 06            run only these notebook numbers (inputs must already exist)
    --timeout SECONDS       per-cell timeout (default 1800)

The run log, the pytest summary, and package versions go to logs/ (or outputs/smoke/logs/).
A core notebook failure stops the run. Notebook 09 (external validation) is optional: its
failure is logged and the run continues.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

NOTEBOOKS = [
    ("00_project_guide.ipynb", "core"),
    ("01_data_collection.ipynb", "core"),
    ("02_data_preparation.ipynb", "core"),
    ("03_mechanism_teaching_example.ipynb", "core"),
    ("04_simulation_validation.ipynb", "core"),
    ("05_exposure_estimation.ipynb", "core"),
    ("06_forecasts_and_freeze.ipynb", "core"),
    ("07_hedge_backtest.ipynb", "core"),
    ("08_results_robustness_episodes.ipynb", "core"),
    ("09_external_validation.ipynb", "optional"),
    ("10_figures_and_handoff.ipynb", "core"),
]
LAST_IN_DEVELOPMENT = "06_forecasts_and_freeze.ipynb"


def log(fh, msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


def environment_report() -> str:
    lines = [f"python {sys.version}", f"platform {platform.platform()}", f"executable {sys.executable}"]
    for name in ["numpy", "pandas", "scipy", "statsmodels", "matplotlib", "pyarrow", "yaml", "requests",
                 "yfinance", "nbformat", "nbclient", "ipykernel", "pytest"]:
        try:
            mod = __import__(name)
            lines.append(f"{name} {getattr(mod, '__version__', 'unknown')}")
        except Exception as exc:  # report, never fail here
            lines.append(f"{name} NOT AVAILABLE ({type(exc).__name__})")
    return "\n".join(lines) + "\n"


def runner_kernel() -> str:
    """Register a temporary kernel that uses THIS Python interpreter, so notebooks run in the
    same environment as the runner (an old Anaconda 'python3' kernel cannot be picked up by mistake)."""
    kroot = Path(tempfile.mkdtemp(prefix="mbshedge_kernel_"))
    kdir = kroot / "kernels" / "mbshedge-runner"
    kdir.mkdir(parents=True)
    spec = {"argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Python (mbshedge runner)", "language": "python"}
    (kdir / "kernel.json").write_text(json.dumps(spec))
    os.environ["JUPYTER_PATH"] = str(kroot) + (os.pathsep + os.environ["JUPYTER_PATH"] if os.environ.get("JUPYTER_PATH") else "")
    return "mbshedge-runner"


def check_packages() -> list[str]:
    missing = []
    for name in ["numpy", "pandas", "scipy", "statsmodels", "matplotlib", "pyarrow", "yaml", "requests",
                 "nbformat", "nbclient", "ipykernel"]:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    return missing


def main() -> int:
    print(f"run_project.py: Python {platform.python_version()} at {sys.executable}", flush=True)
    if sys.version_info < (3, 11):
        print("This project needs Python 3.11 or newer from its own environment, and this is a different Python.\n"
              "Activate the environment first (conda activate mbshedge, or source .venv/bin/activate),\n"
              "check that `python --version` reports 3.11 or newer, and run the command again.", flush=True)
        return 2
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["smoke", "development", "full"], required=True)
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="notebook numbers, e.g. 05 06")
    ap.add_argument("--timeout", type=int, default=1800)
    args, extra = ap.parse_known_args()
    if extra:
        if extra[0].startswith("#"):   # a note pasted after the command (zsh passes it on as words)
            print(f"Ignoring the note after the command: {' '.join(extra)}", flush=True)
        else:
            ap.error(f"unrecognized arguments: {' '.join(extra)}")

    missing = check_packages()
    if missing:
        print(f"Missing packages: {missing}. Activate the project environment (conda activate mbshedge) "
              "or install them with: pip install -r requirements.txt", flush=True)
        return 2
    import nbformat
    from nbclient import NotebookClient

    from mbshedge.config import load_config, make_paths

    os.environ["MBSHEDGE_MODE"] = args.mode
    kernel_name = runner_kernel()
    cfg = load_config(ROOT)
    paths = make_paths(cfg, args.mode, ROOT).ensure()
    base = paths.results.parent
    logs = base / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (logs / f"environment_{stamp}.txt").write_text(environment_report())
    fh = open(logs / f"run_log_{args.mode}_{stamp}.txt", "w", encoding="utf-8")
    log(fh, f"mode={args.mode} root={ROOT} python={sys.executable} ({platform.python_version()})")

    if not args.skip_tests:
        log(fh, "running pytest")
        res = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")], cwd=ROOT,
                             capture_output=True, text=True)
        (logs / f"pytest_{stamp}.txt").write_text(res.stdout + "\n" + res.stderr)
        summary = (res.stdout.strip().splitlines() or ["(no output)"])[-1]
        log(fh, f"pytest: {summary}")
        if res.returncode != 0:
            log(fh, "TESTS FAILED: fix the failures (see the pytest log) before trusting any result. Stopping.")
            return 1

    selected = NOTEBOOKS
    if args.only:
        selected = [nb for nb in NOTEBOOKS if nb[0][:2] in args.only]
    if args.mode == "development":
        names = [n for n, _ in NOTEBOOKS]
        selected = [nb for nb in selected if names.index(nb[0]) <= names.index(LAST_IN_DEVELOPMENT)]

    out_dir = ROOT / "notebooks" if args.mode == "full" else base / "executed_notebooks"
    out_dir.mkdir(parents=True, exist_ok=True)
    skipped_optional = []
    # The kernel process's own start-up and crash messages go to a log file so the console stays
    # readable. Cell output (including warnings raised inside cells) stays in the notebooks.
    kernel_log_path = logs / f"kernel_stderr_{stamp}.txt"
    kernel_log = open(kernel_log_path, "w", encoding="utf-8")
    for name, kind in selected:
        src = ROOT / "notebooks" / name
        nb = nbformat.read(src, as_version=4)
        t0 = time.time()
        log(fh, f"executing {name} ({kind})")
        kernel_log.write(f"===== {name} =====\n")
        kernel_log.flush()
        try:
            NotebookClient(nb, timeout=args.timeout, kernel_name=kernel_name,
                           resources={"metadata": {"path": str(ROOT / "notebooks")}}).execute(stderr=kernel_log)
            nbformat.write(nb, out_dir / name)
            log(fh, f"done {name} in {time.time() - t0:.1f}s")
        except Exception as exc:
            nbformat.write(nb, out_dir / name)  # keep the partial output for debugging
            msg = str(exc).strip().splitlines()
            log(fh, f"FAILED {name} after {time.time() - t0:.1f}s: {msg[-1] if msg else type(exc).__name__}")
            (logs / f"error_{name}_{stamp}.txt").write_text(
                traceback.format_exc() + "\n" + str(exc)
                + f"\n\nKernel process messages, if any: {kernel_log_path.name}\n")
            if kind == "optional":
                skipped_optional.append(name)
                continue
            log(fh, "Core notebook failed. Stopping. The partially executed notebook was saved for inspection.")
            kernel_log.close()
            return 1
    kernel_log.close()

    if args.mode != "development" and not args.only:
        try:
            from mbshedge.bundle import make_bundle
            log(fh, "RUN COMPLETED" + (f" (optional notebooks with problems: {skipped_optional})" if skipped_optional else ""))
            fh.flush()
            b = make_bundle(paths, args.mode)
            log(fh, f"return bundle: {b['zip'].relative_to(ROOT)} ({b['n_files']} files, {b['bytes'] / 1e6:.1f} MB)")
        except Exception as exc:
            log(fh, f"bundle step failed: {exc}")
    else:
        log(fh, "RUN COMPLETED" + (" (development mode stops at the freeze)" if args.mode == "development" else ""))
    fh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
