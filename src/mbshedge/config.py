"""Project root discovery, configuration loading, run modes, and paths.

Every notebook starts with::

    from mbshedge.config import setup
    cfg, paths, mode = setup()

The run mode decides where outputs go:

* ``smoke``        synthetic data, fast settings, everything under ``outputs/smoke/``
* ``development``  real data, stops at the experiment freeze (notebook 06)
* ``full``         real data, freeze and then test-period evaluation

The mode comes from the environment variable ``MBSHEDGE_MODE`` (set by
``run_project.py``) or else from ``project.default_mode`` in the config file.
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_RELATIVE = Path("config") / "project.yaml"
VALID_MODES = ("smoke", "development", "full")


def find_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` (default: cwd) to the folder that holds config/project.yaml."""
    start = Path(start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / CONFIG_RELATIVE).exists():
            return candidate
    raise FileNotFoundError(
        "Could not find config/project.yaml in this folder or any parent. "
        "Open the notebooks from inside the project folder."
    )


def load_config(root: Path | None = None) -> dict:
    root = root or find_root()
    with open(root / CONFIG_RELATIVE, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict) -> None:
    """Fail early and clearly when a required setting is missing or inconsistent."""
    required_top = ["project", "paths", "data", "timing", "experiment", "smoke", "simulation"]
    missing = [k for k in required_top if k not in cfg]
    if missing:
        raise ValueError(f"config/project.yaml is missing sections: {missing}")
    exp = cfg["experiment"]
    for key in ["sample", "exposure", "incentive", "models", "hedging", "evaluation", "episodes", "seed"]:
        if key not in exp:
            raise ValueError(f"experiment.{key} is missing from config/project.yaml")
    s = exp["sample"]
    if not (s["first_month"] < s["development_end"] < s["test_start"]):
        raise ValueError("Sample months must satisfy first_month < development_end < test_start")
    h = exp["hedging"]
    if h["base_cost_bp"] not in h["cost_grid_bp"]:
        raise ValueError("hedging.base_cost_bp must be one of hedging.cost_grid_bp")
    if h["base_delay_days"] not in h["execution_delay_days"]:
        raise ValueError("hedging.base_delay_days must be one of hedging.execution_delay_days")
    if h["base_rule"] not in h["rebalance_rules"]:
        raise ValueError("hedging.base_rule must be one of hedging.rebalance_rules")
    models = exp["models"]["list"]
    for pair in exp["models"]["primary_comparisons"]:
        if pair[0] not in models or pair[1] not in models:
            raise ValueError(f"Primary comparison {pair} uses a model that is not in models.list")
    if exp["models"]["headline_challenger"] not in models:
        raise ValueError("headline_challenger must be in models.list")
    mode = cfg["project"].get("default_mode", "full")
    if mode not in VALID_MODES:
        raise ValueError(f"project.default_mode must be one of {VALID_MODES}")


def get_mode(cfg: dict) -> str:
    mode = os.environ.get("MBSHEDGE_MODE", cfg["project"].get("default_mode", "full")).strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"MBSHEDGE_MODE must be one of {VALID_MODES}, got {mode!r}")
    return mode


@dataclass(frozen=True)
class Paths:
    root: Path
    mode: str
    raw: Path
    interim: Path
    processed: Path
    local_inputs: Path
    results: Path
    figures: Path
    tables: Path
    bundle: Path
    docs: Path
    notebooks: Path
    src: Path

    @property
    def is_smoke(self) -> bool:
        return self.mode == "smoke"

    def ensure(self) -> "Paths":
        for p in [self.raw, self.interim, self.processed, self.local_inputs, self.results,
                  self.figures, self.tables, self.bundle]:
            p.mkdir(parents=True, exist_ok=True)
        return self

    def rel(self, path: Path) -> str:
        """Path relative to the project root, for manifests and the claim ledger."""
        try:
            return str(Path(path).resolve().relative_to(self.root)).replace(os.sep, "/")
        except ValueError:
            return str(path)


def make_paths(cfg: dict, mode: str, root: Path | None = None) -> Paths:
    root = (root or find_root()).resolve()
    p = cfg["paths"]
    base = root / p["smoke_root"] if mode == "smoke" else root
    return Paths(
        root=root,
        mode=mode,
        raw=base / p["raw"],
        interim=base / p["interim"],
        processed=base / p["processed"],
        local_inputs=root / p["local_inputs"],       # user inputs are shared by every mode
        results=base / p["results"],
        figures=base / p["figures"],
        tables=base / p["tables"],
        bundle=base / p["bundle"],
        docs=root / "docs",
        notebooks=root / "notebooks",
        src=root / "src",
    )


def experiment(cfg: dict, mode: str) -> dict:
    """The experiment settings for this mode. Smoke mode swaps in fast settings."""
    exp = copy.deepcopy(cfg["experiment"])
    if mode == "smoke":
        sm = cfg["smoke"]
        exp["evaluation"]["bootstrap_reps"] = sm["bootstrap_reps"]
        exp["exposure"]["ewma_halflife_grid_days"] = sm["ewma_halflife_grid_days"]
        exp["exposure"]["q_bootstrap_reps"] = sm["q_bootstrap_reps"]
    return exp


def setup(start: Path | None = None, mode: str | None = None, quiet: bool = False):
    """Load config, resolve the run mode and paths, and create output folders."""
    root = find_root(start)
    cfg = load_config(root)
    mode = mode or get_mode(cfg)
    paths = make_paths(cfg, mode, root).ensure()
    if not quiet:
        banner = {
            "smoke": "SMOKE RUN: synthetic data only. Nothing here is an empirical result.",
            "development": "DEVELOPMENT RUN: real data, stops at the experiment freeze.",
            "full": "FULL RUN: real data, freeze, then test-period evaluation.",
        }[mode]
        print(f"[mbshedge] project root: {root}")
        print(f"[mbshedge] mode: {mode} | {banner}")
    return cfg, paths, mode
