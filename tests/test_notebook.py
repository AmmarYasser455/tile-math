import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_notebook_runs(monkeypatch):
    nb = json.loads((ROOT / "examples" / "demo.ipynb").read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    monkeypatch.chdir(ROOT)
    ns = {"__name__": "__notebook__"}
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            exec("".join(cell["source"]), ns)
    assert os.path.exists("examples/cities.geojson")
    assert len(ns["tiles"]) == 12
