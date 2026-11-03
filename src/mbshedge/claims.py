"""Machine-readable claim ledger.

Every headline number that may appear in the executive summary, slides, or talk must be a
row here, traceable to the notebook and the saved output it came from.

Status vocabulary
-----------------
pending_execution   the source output does not exist yet (the notebook has not run)
synthetic_only      produced in smoke mode from synthetic data; never quote as a market result
verified_empirical  produced from real data in a full run under a verified freeze
unavailable         the input data could not be obtained (see access_status.csv)
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

STATUSES = ("pending_execution", "synthetic_only", "verified_empirical", "unavailable")


@dataclass
class Claim:
    claim_id: str
    question: str
    asset: str
    sample: str
    strategy: str
    comparator: str
    cost_assumption: str
    metric: str
    units: str
    result: str
    uncertainty: str
    source_notebook: str
    source_function: str
    source_output_path: str
    status: str
    note: str = ""

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")


@dataclass
class ClaimLedger:
    claims: list = field(default_factory=list)

    def add(self, **kw) -> None:
        self.claims.append(Claim(**kw))

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(c) for c in self.claims])

    def save(self, folder: Path) -> list[Path]:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        df = self.frame()
        p_csv, p_json = folder / "claim_ledger.csv", folder / "claim_ledger.json"
        df.to_csv(p_csv, index=False)
        p_json.write_text(json.dumps(df.to_dict(orient="records"), indent=2, default=str))
        return [p_csv, p_json]


def status_for(path: Path, mode: str, freeze_verified: bool, data_available: bool = True) -> str:
    if not data_available:
        return "unavailable"
    if not Path(path).exists():
        return "pending_execution"
    if mode == "smoke":
        return "synthetic_only"
    return "verified_empirical" if freeze_verified else "pending_execution"
