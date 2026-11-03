import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mbshedge import config, synthetic  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    return config.load_config(ROOT)


@pytest.fixture(scope="session")
def exp(cfg):
    return config.experiment(cfg, "smoke")


@pytest.fixture(scope="session")
def world():
    return synthetic.make_world(seed=7, scenario="state")


@pytest.fixture(scope="session")
def tables(world):
    return {"fred": world["fred"], "prices": world["prices"], "nmdb": world["nmdb"]}
