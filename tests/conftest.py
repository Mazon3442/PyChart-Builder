import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def projects(tmp_path, monkeypatch):
    """An empty projects folder, so tests never touch the real one."""
    folder = tmp_path / "projects"
    folder.mkdir()
    monkeypatch.setenv("PYGANTT_PROJECTS", str(folder))
    return folder


@pytest.fixture(scope="session", autouse=True)
def headless_matplotlib():
    os.environ.setdefault("MPLBACKEND", "Agg")
