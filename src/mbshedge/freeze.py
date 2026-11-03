"""Experiment freeze record and test-evaluation log.

Notebook 06 writes `results/freeze/freeze_record.json` after every development-period
choice is made and before any test-period result is computed. The record holds SHA-256
hashes of (a) the frozen configuration block, (b) the result-relevant source code,
(c) the code cells of the analysis notebooks (02, 05 to 09), which hold the regime,
episode, robustness, and comparison definitions, and (d) the raw-data manifest, plus the
development selections themselves.

Notebooks 07 to 10 call `require_freeze`, which stops with an explanation if the record
is missing or if the configuration, result-relevant code, or analysis notebook code
changed after the freeze. Until the first test-period evaluation is logged, a rerun of
notebook 06 simply replaces a record that no longer matches, because nothing about the
test period has been seen yet. The replacement is logged in `events.csv`.
Every test-period evaluation appends a row to `results/freeze/test_evaluation_log.csv`, so
the number of times the test sample was evaluated, and under which code, is on record.

This is a local, hash-based record. It is not a public, independently timestamped
preregistration. A git commit or tag can supplement it.

A deliberate post-freeze change: set the environment variable MBSHEDGE_ALLOW_POST_FREEZE=1,
describe the change in docs/post_freeze_changes.md, and rerun. The log then marks every
affected evaluation as post-freeze.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

RESULT_MODULES = ["config.py", "sources.py", "prepare.py", "instruments.py", "exposure.py", "models.py",
                  "backtest.py", "evaluation.py", "pipeline.py", "simulation.py", "synthetic.py"]
FROZEN_NOTEBOOKS = ["02_data_preparation.ipynb", "05_exposure_estimation.ipynb", "06_forecasts_and_freeze.ipynb",
                    "07_hedge_backtest.ipynb", "08_results_robustness_episodes.ipynb", "09_external_validation.ipynb"]


class FreezeError(RuntimeError):
    pass


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()


def experiment_hash(cfg: dict) -> str:
    frozen = {"experiment": cfg["experiment"], "timing": cfg["timing"],
              "nmdb": {k: cfg["data"]["nmdb"][k] for k in ("markets_core", "market_robustness", "value_column")}}
    return hashlib.sha256(_canonical(frozen)).hexdigest()


def code_hash(src_dir: Path) -> str:
    h = hashlib.sha256()
    for name in RESULT_MODULES:
        p = Path(src_dir) / "mbshedge" / name
        h.update(name.encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def notebook_code_hash(nb_dir: Path) -> str:
    """SHA-256 over the code cells of the analysis notebooks. Outputs and markdown are ignored,
    so executing a notebook or editing its prose does not change the hash."""
    h = hashlib.sha256()
    for name in FROZEN_NOTEBOOKS:
        p = Path(nb_dir) / name
        h.update(name.encode())
        if not p.exists():
            h.update(b"<missing>")
            continue
        nb = json.loads(p.read_text(encoding="utf-8"))
        for cell in nb.get("cells", []):
            if cell.get("cell_type") == "code":
                src = cell.get("source", "")
                src = src if isinstance(src, str) else "".join(src)
                h.update(src.replace("\r\n", "\n").strip().encode() + b"\x00")
    return h.hexdigest()


def manifest_hash(raw_dir: Path) -> str:
    p = Path(raw_dir) / "manifest.csv"
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


def freeze_dir(paths) -> Path:
    d = Path(paths.results) / "freeze"
    d.mkdir(parents=True, exist_ok=True)
    return d


def record_path(paths) -> Path:
    return freeze_dir(paths) / "freeze_record.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_or_verify(cfg: dict, paths, dev_choices: dict, mode: str) -> tuple[dict, str]:
    """Create the freeze record, or verify that a rerun reproduces it exactly."""
    rec_new = {
        "created_utc": _now(), "mode": mode, "project_version": cfg["project"]["version"],
        "experiment_sha256": experiment_hash(cfg), "code_sha256": code_hash(paths.src),
        "notebook_code_sha256": notebook_code_hash(paths.notebooks),
        "raw_manifest_sha256_at_freeze": manifest_hash(paths.raw), "development_choices": dev_choices,
        "statement": ("All development-period choices listed here were made using data dated on or before the "
                      "end of the development period. No test-period result had been computed when this "
                      "record was first written."),
    }
    p = record_path(paths)
    if not p.exists():
        p.write_text(json.dumps(rec_new, indent=2, default=str))
        _write_markdown(paths, rec_new)
        return rec_new, "created"
    old = json.loads(p.read_text())
    problems = _compare(old, rec_new)
    if problems and (mode == "smoke" or n_test_evaluations(paths) == 0):
        # Nothing about the real test period has been computed yet (or the data are synthetic),
        # so the record can be replaced.
        reason = "smoke run on synthetic data" if mode == "smoke" else "no test evaluation had been logged"
        p.write_text(json.dumps(rec_new, indent=2, default=str))
        _write_markdown(paths, rec_new)
        log_event(paths, "freeze_replaced", f"{reason}: " + "; ".join(problems))
        return rec_new, f"replaced ({reason})"
    if problems:
        if os.environ.get("MBSHEDGE_ALLOW_POST_FREEZE") == "1":
            log_event(paths, "post_freeze_change_acknowledged", "; ".join(problems))
            return old, "post_freeze_change"
        raise FreezeError("The frozen experiment does not match this run:\n  - " + "\n  - ".join(problems) +
                          "\nIf this change is deliberate, record it in docs/post_freeze_changes.md and rerun "
                          "with MBSHEDGE_ALLOW_POST_FREEZE=1. To start a new freeze, archive and delete "
                          f"{p} (this resets the test evaluation history).")
    return old, "verified"


def _compare(old: dict, new: dict) -> list[str]:
    out = []
    if old["experiment_sha256"] != new["experiment_sha256"]:
        out.append("the frozen configuration block changed")
    if old["code_sha256"] != new["code_sha256"]:
        out.append("result-relevant source code changed")
    if old.get("notebook_code_sha256") != new.get("notebook_code_sha256"):
        out.append("analysis notebook code changed")
    a, b = old["development_choices"], new["development_choices"]
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k), b.get(k)
        if isinstance(va, float) and isinstance(vb, float):
            if abs(va - vb) > 1e-9 * max(1.0, abs(va)):
                out.append(f"development choice {k}: frozen {va} vs now {vb}")
        elif _canonical(va) != _canonical(vb):
            out.append(f"development choice {k} differs")
    return out


def require_freeze(cfg: dict, paths) -> dict:
    p = record_path(paths)
    if not p.exists():
        raise FreezeError("No freeze record. Run notebook 06 (in development or full mode) before any "
                          "test-period evaluation.")
    rec = json.loads(p.read_text())
    problems = []
    if rec["experiment_sha256"] != experiment_hash(cfg):
        problems.append("the frozen configuration block changed after the freeze")
    if rec["code_sha256"] != code_hash(paths.src):
        problems.append("result-relevant source code changed after the freeze")
    if rec.get("notebook_code_sha256") != notebook_code_hash(paths.notebooks):
        problems.append("analysis notebook code (notebooks 02, 05 to 09) changed after the freeze")
    if problems and getattr(paths, "mode", "") == "smoke":
        print("[freeze] smoke run: the synthetic freeze record no longer matches (" + "; ".join(problems) +
              "). Rerun notebook 06 to refresh it. Continuing, because smoke results are synthetic.")
    elif problems and os.environ.get("MBSHEDGE_ALLOW_POST_FREEZE") != "1":
        raise FreezeError("; ".join(problems) + ". Record the change in docs/post_freeze_changes.md and rerun "
                          "with MBSHEDGE_ALLOW_POST_FREEZE=1.")
    rec["_post_freeze"] = bool(problems)
    return rec


def n_test_evaluations(paths) -> int:
    p = freeze_dir(paths) / "test_evaluation_log.csv"
    return int(len(pd.read_csv(p))) if p.exists() else 0


def log_test_evaluation(paths, rec: dict, notebook: str, what: str) -> None:
    row = {"utc": _now(), "notebook": notebook, "what": what, "freeze_created_utc": rec["created_utc"],
           "experiment_sha256": experiment_hash_safe(rec), "post_freeze": rec.get("_post_freeze", False)}
    p = freeze_dir(paths) / "test_evaluation_log.csv"
    df = pd.read_csv(p, dtype=str) if p.exists() else pd.DataFrame(columns=list(row))
    pd.concat([df, pd.DataFrame([row])], ignore_index=True).to_csv(p, index=False)


def experiment_hash_safe(rec: dict) -> str:
    return rec.get("experiment_sha256", "")


def log_event(paths, event: str, detail: str) -> None:
    p = freeze_dir(paths) / "events.csv"
    df = pd.read_csv(p, dtype=str) if p.exists() else pd.DataFrame(columns=["utc", "event", "detail"])
    pd.concat([df, pd.DataFrame([{"utc": _now(), "event": event, "detail": detail}])], ignore_index=True).to_csv(p, index=False)


def _write_markdown(paths, rec: dict) -> None:
    d = rec["development_choices"]
    lines = [
        "# Experiment freeze record", "",
        f"Created (UTC): {rec['created_utc']}  ",
        f"Run mode: {rec['mode']}  ",
        f"Project version: {rec['project_version']}", "",
        "| Item | Value |", "|---|---|",
        f"| Frozen configuration SHA-256 | `{rec['experiment_sha256']}` |",
        f"| Result-relevant code SHA-256 | `{rec['code_sha256']}` |",
        f"| Analysis notebook code SHA-256 | `{rec.get('notebook_code_sha256', '')}` |",
        f"| Raw manifest SHA-256 at freeze | `{rec['raw_manifest_sha256_at_freeze']}` |",
    ]
    for k, v in d.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, default=str)[:300]
        lines.append(f"| {k} | {v} |")
    lines += ["", rec["statement"], "",
              "This is a local hash record. It is not a public, independently timestamped preregistration."]
    (freeze_dir(paths) / "freeze_record.md").write_text("\n".join(lines))
