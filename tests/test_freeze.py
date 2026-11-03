"""The experiment freeze: what it pins, when it may be replaced, and when it must stop a run."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from mbshedge import freeze as fz

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fake_paths(tmp_path):
    nb_dir = tmp_path / "notebooks"
    nb_dir.mkdir()
    for name in fz.FROZEN_NOTEBOOKS:
        nb = {"cells": [{"cell_type": "markdown", "source": "# title"},
                        {"cell_type": "code", "source": "x = 1\n", "outputs": []}],
              "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        (nb_dir / name).write_text(json.dumps(nb))
    src = tmp_path / "src"
    shutil.copytree(ROOT / "src" / "mbshedge", src / "mbshedge")
    (tmp_path / "raw").mkdir()
    return SimpleNamespace(results=tmp_path / "results", src=src, raw=tmp_path / "raw", notebooks=nb_dir, mode="full")


def _edit_notebook(paths, name, new_code):
    p = Path(paths.notebooks) / name
    nb = json.loads(p.read_text())
    nb["cells"][1]["source"] = new_code
    p.write_text(json.dumps(nb))


def test_notebook_hash_ignores_outputs_and_markdown(fake_paths):
    h0 = fz.notebook_code_hash(fake_paths.notebooks)
    p = Path(fake_paths.notebooks) / fz.FROZEN_NOTEBOOKS[0]
    nb = json.loads(p.read_text())
    nb["cells"][0]["source"] = "# a different title"
    nb["cells"][1]["outputs"] = [{"output_type": "stream", "name": "stdout", "text": "1"}]
    p.write_text(json.dumps(nb))
    assert fz.notebook_code_hash(fake_paths.notebooks) == h0
    _edit_notebook(fake_paths, fz.FROZEN_NOTEBOOKS[0], "x = 2\n")
    assert fz.notebook_code_hash(fake_paths.notebooks) != h0


def test_freeze_can_be_replaced_only_before_test_evaluation(cfg, fake_paths, monkeypatch):
    monkeypatch.delenv("MBSHEDGE_ALLOW_POST_FREEZE", raising=False)
    choices = {"static_duration_years": 4.0}
    rec, status = fz.write_or_verify(cfg, fake_paths, choices, "full")
    assert status == "created"
    assert fz.write_or_verify(cfg, fake_paths, choices, "full")[1] == "verified"

    # an analysis-notebook edit before any test evaluation: the record is replaced and logged
    _edit_notebook(fake_paths, "08_results_robustness_episodes.ipynb", "rule = 'changed'\n")
    rec, status = fz.write_or_verify(cfg, fake_paths, choices, "full")
    assert status.startswith("replaced")

    # after a test evaluation, any change stops the run
    fz.log_test_evaluation(fake_paths, rec, "07", "test-period backtests")
    _edit_notebook(fake_paths, "08_results_robustness_episodes.ipynb", "rule = 'changed again'\n")
    with pytest.raises(fz.FreezeError, match="analysis notebook code"):
        fz.write_or_verify(cfg, fake_paths, choices, "full")
    with pytest.raises(fz.FreezeError, match="analysis notebook code"):
        fz.require_freeze(cfg, fake_paths)
    with pytest.raises(fz.FreezeError, match="development choice"):
        _edit_notebook(fake_paths, "08_results_robustness_episodes.ipynb", "rule = 'changed'\n")
        fz.write_or_verify(cfg, fake_paths, {"static_duration_years": 4.1}, "full")

    # a deliberate, recorded change is allowed and flagged
    _edit_notebook(fake_paths, "08_results_robustness_episodes.ipynb", "rule = 'changed again'\n")
    monkeypatch.setenv("MBSHEDGE_ALLOW_POST_FREEZE", "1")
    assert fz.require_freeze(cfg, fake_paths)["_post_freeze"] is True


def test_source_changes_are_detected(cfg, fake_paths, monkeypatch):
    monkeypatch.delenv("MBSHEDGE_ALLOW_POST_FREEZE", raising=False)
    rec, _ = fz.write_or_verify(cfg, fake_paths, {}, "full")
    fz.log_test_evaluation(fake_paths, rec, "06", "test-period forecasts")
    for module in ("evaluation.py", "simulation.py", "config.py"):
        assert module in fz.RESULT_MODULES
    p = Path(fake_paths.src) / "mbshedge" / "evaluation.py"
    p.write_text(p.read_text() + "\n# edited after the freeze\n")
    with pytest.raises(fz.FreezeError, match="source code"):
        fz.require_freeze(cfg, fake_paths)
