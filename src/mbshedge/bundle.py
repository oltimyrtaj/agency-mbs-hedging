"""Package the return bundle: the evidence the communication stage is built from.

Included: executed notebooks, results tables and JSON, figures (PNG, SVG, plotted data),
summary tables, the configuration and freeze record, the raw-data manifest (hashes only),
processed panels (optional), logs (run log, test summary, environment versions), the claim
ledger, docs, and a checksum manifest. Excluded: raw third-party downloads, caches,
checkpoints, and anything that looks like a secret.
"""
from __future__ import annotations

import hashlib
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

EXCLUDE_PARTS = {".ipynb_checkpoints", "__pycache__", ".git", ".pytest_cache"}
SECRET_HINTS = (".env", "secret", "token", "apikey", "api_key", "credentials")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(paths, include_processed: bool = True, mode: str = "full") -> list[Path]:
    root = Path(paths.root)
    base = Path(paths.results).parent
    files: list[Path] = []

    def add_tree(folder: Path, patterns=("*",)):
        if not folder.exists():
            return
        for pat in patterns:
            for p in folder.rglob(pat):
                if p.is_file() and not (set(p.parts) & EXCLUDE_PARTS) and not any(
                        h in p.name.lower() for h in SECRET_HINTS):
                    files.append(p)

    if mode == "full":
        add_tree(root / "notebooks", ("*.ipynb",))          # full runs execute the notebooks in place
    add_tree(base / "executed_notebooks", ("*.ipynb",))     # smoke and development runs save copies here
    add_tree(Path(paths.results))
    add_tree(Path(paths.figures))
    add_tree(Path(paths.tables))
    add_tree(root / "config", ("*.yaml",))
    add_tree(root / "docs", ("*.md",))
    add_tree(base / "logs")
    if (Path(paths.raw) / "manifest.csv").exists():
        files.append(Path(paths.raw) / "manifest.csv")
    if include_processed:
        add_tree(Path(paths.processed))
    for name in ("README.md", "RUN_ME_FIRST.md", "requirements.txt", "environment.yml"):
        if (root / name).exists():
            files.append(root / name)
    seen, out = set(), []
    for p in files:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def make_bundle(paths, mode: str, include_processed: bool = True) -> dict:
    root = Path(paths.root)
    files = collect(paths, include_processed, mode)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(paths.bundle)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_lines = ["path,bytes,sha256"]
    for p in files:
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        manifest_lines.append(f"{rel},{p.stat().st_size},{_sha256(p)}")
    manifest_txt = "\n".join(manifest_lines) + "\n"
    checklist = _checklist(mode, len(files))
    zpath = out_dir / f"mbs_hedging_return_bundle_{mode}_{stamp}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, os.path.relpath(p, root))
        zf.writestr("BUNDLE_MANIFEST.csv", manifest_txt)
        zf.writestr("BUNDLE_CHECKLIST.md", checklist)
    (out_dir / "BUNDLE_MANIFEST.csv").write_text(manifest_txt)
    (out_dir / "BUNDLE_CHECKLIST.md").write_text(checklist)
    return {"zip": zpath, "n_files": len(files), "bytes": zpath.stat().st_size}


def _checklist(mode: str, n_files: int) -> str:
    warn = ("\n**This bundle comes from a SMOKE run on synthetic data. Do not use it as evidence.**\n"
            if mode == "smoke" else "")
    return f"""# Checklist for the communication stage
{warn}
Bundle mode: {mode}. Files: {n_files}.

The single zip file in `return_bundle/` contains:

1. Executed notebooks 00 to 10 (with their outputs).
2. `results/`: every saved table, JSON summary, forecast, position and P&L ledger, the freeze
   record, the test-evaluation log, the claim ledger, and the access status of every data source.
3. `reports/figures/` (PNG, SVG, and the CSV behind each figure) and `reports/tables/`.
4. `config/project.yaml`, `docs/` (design, decision log, data dictionary, limitations, template notes).
5. `logs/`: the run log, the pytest summary, and the Python package versions.
6. `data/raw/manifest.csv` (hashes and sources only, no third-party raw files), and the processed
   panels if they were included.
7. `BUNDLE_MANIFEST.csv`: SHA-256 of every file, so anyone can confirm nothing changed.

Before using it:
- [ ] `logs/run_log_*.txt` ends with "RUN COMPLETED" (or lists which optional notebooks were skipped and why).
- [ ] `logs/pytest_*.txt` shows the tests passed.
- [ ] `results/freeze/freeze_record.json` exists and `results/freeze/test_evaluation_log.csv` lists the test evaluations.
- [ ] `results/data_status/access_status.csv` shows `verified_access` or `cached` for MBB, DGS10, DGS3MO, MORTGAGE30US, and NMDB.
- [ ] If you supplied local files (for example PIMCO NAV history), say where they came from.

API keys never go in the bundle. Raw Yahoo and PMMS files are excluded on purpose (licensing). The
manifest hashes let anyone rebuild and verify them.
"""
