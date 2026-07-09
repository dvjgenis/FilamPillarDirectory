import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _default_csv_data_source(monkeypatch):
    """Keep unit tests on local CSV unless a test opts into Google Sheets."""
    monkeypatch.setenv("CHURCH_DATA_SOURCE", "csv")
