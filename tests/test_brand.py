import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
ALLOWED = {
    "logo.svg": {"#121417", "#f2552c"},
    "logo-dark.svg": {"#f3eee4", "#f2552c"},
}


@pytest.mark.parametrize("name", sorted(ALLOWED))
def test_logo_valid(name):
    path = BRAND / name
    assert path.exists()
    root = ET.parse(path).getroot()
    assert root.get("viewBox") == "0 0 100 100"
    assert root.get("width") == "100" and root.get("height") == "100"
    text = path.read_text(encoding="utf-8").lower()
    assert set(re.findall(r"#[0-9a-f]{6}\b", text)) == ALLOWED[name]
    for bad in ("opacity", "gradient", "filter", "<image", "<text"):
        assert bad not in text


def test_readme_mentions_openterra():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[OpenTerra](https://github.com/AmmarYasser455)" in readme
