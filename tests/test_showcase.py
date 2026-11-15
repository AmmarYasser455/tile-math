import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHOW = ROOT / "showcase"


def _load():
    spec = importlib.util.spec_from_file_location("make_showcase", SHOW / "make_showcase.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_geojson_matches_committed(tmp_path):
    _load().main(tmp_path, png=False)
    fresh = json.loads((tmp_path / "map.geojson").read_text(encoding="utf-8"))
    committed = json.loads((SHOW / "map.geojson").read_text(encoding="utf-8"))
    assert fresh == committed
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == (SHOW / "index.html").read_text(encoding="utf-8")


def test_known_values():
    ms = _load()
    ring = ms.load_egypt()
    west, south, east, north = ms.ring_bbox(ring)
    # Real extent of Egypt: ~25E..37E, ~22N..32N (a swapped axis would fail)
    assert 24 < west < 26 and 36 < east < 37.5
    assert 21.5 < south < 22.5 and 31 < north < 32
    rows = {r["zoom"]: r for r in ms.summary(ring)}
    assert rows[8]["bbox_tiles"] == 80 and rows[8]["needed"] == 68
    # Cairo is inside a needed tile
    from tile_math import lonlat_to_tile
    x, y, z = lonlat_to_tile(31.2357, 30.0444, 8)
    status = {(r["x"], r["y"]): r["status"] for r in ms.classify(ring, 8)}
    assert status[(x, y)] in ("border", "interior")


BOX = (0.0, 0.0, 1.0, 1.0)


@pytest.mark.parametrize("p0,p1,expected", [
    ((0.5, 0.5), (0.6, 0.6), True),            # fully inside
    ((-1, 0.5), (2, 0.5), True),               # passes straight through
    ((0.998, -0.001), (1.001, 0.002), True),   # clips the south-east corner by ~1e-3
    ((-1, -1), (2, 2), True),                  # diagonal through two corners
    ((-1, 0.0), (2, 0.0), False),              # runs along the south edge
    ((1.0, -1), (1.0, 2), False),              # runs along the east edge
    ((0.5, -0.5), (1.5, 0.5), False),          # touches only at corner (1, 0)
    ((1.0, -0.5), (1.5, 0.0), False),          # outside, near corner
    ((2, 2), (3, 3), False),                   # far away
    ((0.5, 2), (0.5, 1.0), False),             # ends on the north edge
])
def test_segment_crosses_box(p0, p1, expected):
    ms = _load()
    assert ms.segment_crosses_box(p0, p1, BOX) is expected
    assert ms.segment_crosses_box(p1, p0, BOX) is expected


def test_corner_clip_found_without_sampling():
    """A ring edge that cuts a tile corner by a few metres is still a border tile."""
    ms = _load()
    from tile_math import tile_bounds
    w, s, e, n = tile_bounds(150, 105, 8)  # Cairo's zoom-8 tile
    d = 1e-4  # ~10 m
    # 45-degree line through (e - d, s) and (e, s + d): cuts the SE corner off the tile
    a, b = (e - d - 1.0, s - 1.0), (e - d + 1.0, s + 1.0)
    ring = [a, (e + 1.0, s - 1.0), b, a]
    assert (150, 105, 8) in ms.border_tiles(ring, 8)
    # a sampler at 0.02 degrees would miss it: no sample point falls in the tile
    k = 100
    pts = [(a[0] + i / k * (b[0] - a[0]), a[1] + i / k * (b[1] - a[1])) for i in range(k + 1)]
    assert not any(w < x < e and s < y < n for x, y in pts)


def _fc(geom):
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": geom}]}


_SQ = [[30, 25], [31, 25], [31, 26], [30, 26], [30, 25]]


@pytest.mark.parametrize("doc", [
    None, "egypt", 42, [], {}, {"type": "Feature"},
    {"type": "FeatureCollection"},
    {"type": "FeatureCollection", "features": []},
    {"type": "FeatureCollection", "features": None},
    {"type": "FeatureCollection", "features": "x"},
    {"type": "FeatureCollection", "features": [None]},
    {"type": "FeatureCollection", "features": [_fc(None)["features"][0]] * 2},
    _fc(None),
    _fc({"type": "MultiPolygon", "coordinates": [[_SQ]]}),
    _fc({"type": "Point", "coordinates": [31, 30]}),
    _fc({"type": "Polygon"}),
    _fc({"type": "Polygon", "coordinates": []}),
    _fc({"type": "Polygon", "coordinates": [[]]}),
    _fc({"type": "Polygon", "coordinates": "abc"}),
    _fc({"type": "Polygon", "coordinates": ["abc"]}),
    _fc({"type": "Polygon", "coordinates": [{"a": 1}]}),
    _fc({"type": "Polygon", "coordinates": [_SQ, _SQ]}),                  # hole
    _fc({"type": "Polygon", "coordinates": [_SQ[:-1]]}),                  # open ring
    _fc({"type": "Polygon", "coordinates": [[[30, 25], [31, 25], [30, 25]]]}),  # too short
    _fc({"type": "Polygon", "coordinates": [[[30, 25], [31, 25], [32, 25], [30, 25]]]}),  # zero area
    _fc({"type": "Polygon", "coordinates": [[[float("nan"), 25]] + _SQ[1:]]}),
    _fc({"type": "Polygon", "coordinates": [[[30, float("inf")]] + _SQ[1:]]}),
    _fc({"type": "Polygon", "coordinates": [[["30", 25]] + _SQ[1:]]}),
    _fc({"type": "Polygon", "coordinates": [[[True, 25]] + _SQ[1:]]}),
    _fc({"type": "Polygon", "coordinates": [[None] + _SQ[1:]]}),
    _fc({"type": "Polygon", "coordinates": [[[30]] + _SQ[1:]]}),
    _fc({"type": "Polygon", "coordinates": [[{"lon": 30, "lat": 25}] + _SQ[1:]]}),
    _fc({"type": "Polygon", "coordinates": [[[200, 25]] + _SQ[1:]]}),
    _fc({"type": "Polygon", "coordinates": [[[30, 89]] + _SQ[1:]]}),
])
def test_ring_from_geojson_rejects(doc):
    with pytest.raises(ValueError):
        _load().ring_from_geojson(doc)


def test_ring_from_geojson_orients_ccw():
    ms = _load()
    ring = ms.ring_from_geojson(_fc({"type": "Polygon", "coordinates": [_SQ[::-1]]}))
    assert ms._signed_area(ring) > 0 and ring[0] == ring[-1]


def test_non_border_tiles_are_uniform():
    """Independent check: every non-border zoom-8 tile is wholly in or out of Egypt."""
    ms = _load()
    from tile_math import tile_bounds
    ring = ms.load_egypt()
    for r in ms.classify(ring, 8):
        if r["status"] == "border":
            continue
        w, s, e, n = tile_bounds(r["x"], r["y"], 8)
        for i in range(1, 12):
            for j in range(1, 12):
                inside = ms.point_in_ring(w + (e - w) * i / 12, s + (n - s) * j / 12, ring)
                assert inside == (r["status"] == "interior")


def test_notebook_executes(tmp_path):
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    pytest.importorskip("matplotlib")
    pytest.importorskip("ipykernel")
    nb = nbformat.read(SHOW / "showcase.ipynb", as_version=4)
    # executed in memory only; the committed notebook is not modified
    client = nbclient.NotebookClient(
        nb, timeout=300, kernel_name="python3",
        resources={"metadata": {"path": str(SHOW)}},
    )
    try:
        client.execute()
    except nbclient.exceptions.CellExecutionError as exc:  # pragma: no cover
        pytest.fail(f"notebook raised: {exc}")
    outputs = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])]
    assert not [o for o in outputs if o.output_type == "error"]
    assert any(
        o.output_type in ("display_data", "execute_result") and "image/png" in o.get("data", {})
        for o in outputs
    )


def test_png_produced(tmp_path):
    pytest.importorskip("matplotlib")
    _load().main(tmp_path, png=True)
    png = tmp_path / "map.png"
    assert png.exists() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
