import pytest

from tile_math import (
    MAX_LAT,
    bbox_to_tiles,
    lonlat_to_tile,
    quadkey_to_tile,
    tile_bounds,
    tile_to_quadkey,
    tiles_to_geojson,
)
from tile_math.cli import main


def test_london_known_tile():
    # London (lon -0.1275, lat 51.5072): OSM tile 10/511/340. Swapped axes would fail.
    assert lonlat_to_tile(-0.1275, 51.5072, 10) == (511, 340, 10)


def test_sydney_southern_eastern_hemisphere():
    x, y, z = lonlat_to_tile(151.2093, -33.8688, 10)
    assert (x, y) == (942, 614)  # (151.2093+180)/360*1024 = 942.1


def test_zoom_zero_and_edges():
    assert lonlat_to_tile(0, 0, 0) == (0, 0, 0)
    assert lonlat_to_tile(180, 0, 2) == (3, 2, 2)
    assert lonlat_to_tile(-180, MAX_LAT, 3) == (0, 0, 3)
    assert lonlat_to_tile(0, -MAX_LAT, 3) == (4, 7, 3)


def test_quadkey_known_values():
    # Bing Maps documentation example: tile (3, 5) at level 3 is "213".
    assert tile_to_quadkey(3, 5, 3) == "213"
    assert quadkey_to_tile("213") == (3, 5, 3)
    assert tile_to_quadkey(0, 0, 0) == ""
    assert quadkey_to_tile("") == (0, 0, 0)


def test_quadkey_roundtrip():
    for z in (1, 5, 12, 20):
        t = (2**z - 1, 2 ** (z - 1), z)
        assert quadkey_to_tile(tile_to_quadkey(*t)) == t


def test_tile_bounds_contains_point():
    w, s, e, n = tile_bounds(511, 340, 10)
    assert w <= -0.1275 < e and s <= 51.5072 < n
    assert tile_bounds(0, 0, 0) == pytest.approx((-180, -MAX_LAT, 180, MAX_LAT))


def test_invalid_inputs():
    with pytest.raises(ValueError):
        lonlat_to_tile(0, 89, 5)
    with pytest.raises(ValueError):
        lonlat_to_tile(181, 0, 5)
    with pytest.raises(ValueError):
        lonlat_to_tile(0, 0, 31)
    with pytest.raises(ValueError):
        tile_bounds(4, 0, 2)
    with pytest.raises(ValueError):
        quadkey_to_tile("124")
    with pytest.raises(ValueError):
        bbox_to_tiles(0, 10, 5, 0, 3)


def test_bbox_tiles_exact_edges_not_spilled():
    # Exactly the tile 1/0/0: the neighbours that only touch the edge are excluded.
    assert bbox_to_tiles(-180, 0, 0, MAX_LAT, 1) == [(0, 0, 1)]
    assert len(bbox_to_tiles(-180, -90, 180, 90, 2)) == 16


def test_bbox_point_and_antimeridian():
    assert bbox_to_tiles(-0.1275, 51.5072, -0.1275, 51.5072, 10) == [(511, 340, 10)]
    tiles = bbox_to_tiles(170, -10, -170, 10, 3)
    assert {t[0] for t in tiles} == {0, 7}


def test_bbox_limit():
    with pytest.raises(ValueError):
        bbox_to_tiles(-180, -90, 180, 90, 10, max_tiles=100)


def test_geojson_ccw_ring():
    ring = tiles_to_geojson([(511, 340, 10)])["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
    assert area2 > 0


def test_cli(capsys):
    assert main(["tile", "-0.1275", "51.5072", "10"]) == 0
    assert capsys.readouterr().out.startswith("10/511/340 quadkey=")
    assert main(["tile", "0", "89", "3"]) == 2


def test_antimeridian_touching_edge_and_zoom0():
    assert {x for x, _, _ in bbox_to_tiles(180, -10, -170, 10, 3)} == {0}
    assert bbox_to_tiles(170, -10, -170, 10, 0, max_tiles=1) == [(0, 0, 0)]
    assert {x for x, _, _ in bbox_to_tiles(170, -10, -170, 10, 3)} == {0, 7}


def test_cli_bounds_keep_precision_at_zoom_30(capsys):
    assert main(["bounds", "30", "536870912", "536870912"]) == 0
    out = capsys.readouterr().out.split()
    vals = {k: float(v) for k, v in (p.split("=") for p in out[:4])}
    assert vals["east"] > vals["west"] and vals["north"] > vals["south"]


def test_mercator_limits_and_containment():
    w, s, e, n = tile_bounds(0, 0, 0)
    assert (w, e) == (-180.0, 180.0)
    assert n == pytest.approx(MAX_LAT, abs=1e-9) and s == pytest.approx(-MAX_LAT, abs=1e-9)
    x, y, z = lonlat_to_tile(-0.1275, 51.5072, 12)
    w, s, e, n = tile_bounds(x, y, z)
    assert w <= -0.1275 < e and s <= 51.5072 < n


@pytest.mark.parametrize("z", [1, 3, 7, 10, 14, 18, 22, 26, 30])
def test_tile_bounds_roundtrip_at_non_equatorial_rows(z):
    # Projection roundoff must not pull in a neighbouring row/column at tile edges.
    n = 1 << z
    for y in sorted({0, 1, n // 7, n // 3, n // 2 - 1, n // 2 + 1, (5 * n) // 6, n - 2, n - 1}):
        y = min(max(y, 0), n - 1)
        x = (y * 7 + 3) % n
        w, s, e, north = tile_bounds(x, y, z)
        assert bbox_to_tiles(w, s, e, north, z) == [(x, y, z)]
        assert lonlat_to_tile(w, north, z) == (x, y, z)  # NW corner belongs to the tile


@pytest.mark.parametrize(
    "args, expected",
    [
        # Just west of Greenwich (1e-7 deg ~ 1 cm): column 0, not column 1.
        ((-1e-7, 10, -5e-8, 11, 1), [(0, 0, 1)]),
        ((-1e-9, 10, -1e-9, 11, 1), [(0, 0, 1)]),
        # Just east of Greenwich: column 1 only.
        ((5e-8, 10, 1e-7, 11, 1), [(1, 0, 1)]),
        # Just south / north of the equator at zoom 1.
        ((10, -1e-7, 11, -5e-8, 1), [(1, 1, 1)]),
        ((10, 5e-8, 11, 1e-7, 1), [(1, 0, 1)]),
        # High zoom: 1e-9 deg (~0.1 mm) west of a zoom-30 column edge.
        ((-1e-9, 0.0001, -1e-9, 0.0001, 30), None),
    ],
)
def test_coordinates_near_edges_are_not_snapped_across(args, expected):
    tiles = bbox_to_tiles(*args)
    w, s, e, n, z = args
    if expected is None:
        # Must agree with the point lookup and lie west of Greenwich.
        assert tiles == [lonlat_to_tile(w, s, z)]
        assert tiles[0][0] == (1 << 29) - 1
    else:
        assert tiles == expected
    for lon in (w, e):
        for lat in (s, n):
            tx, ty, _ = lonlat_to_tile(lon, lat, z)
            assert any(t[0] == tx and t[1] == ty for t in tiles)


NAN, INF = float("nan"), float("inf")
INVALID_CALLS = [
    # lonlat_to_tile(lon, lat, z)
    (lonlat_to_tile, (None, 0, 1)),
    (lonlat_to_tile, ("1", 0, 1)),
    (lonlat_to_tile, (NAN, 0, 1)),
    (lonlat_to_tile, (0, NAN, 1)),
    (lonlat_to_tile, (0, INF, 1)),
    (lonlat_to_tile, (True, 0, 1)),
    (lonlat_to_tile, ([0], 0, 1)),
    (lonlat_to_tile, ({"lon": 0}, 0, 1)),
    (lonlat_to_tile, (0, 0, 1.0)),
    (lonlat_to_tile, (0, 0, True)),
    (lonlat_to_tile, (0, 0, "3")),
    (lonlat_to_tile, (0, 0, -1)),
    (lonlat_to_tile, (0, 0, None)),
    # tile_bounds / tile_to_quadkey(x, y, z)
    (tile_bounds, (0.5, 0, 1)),
    (tile_bounds, (True, 0, 1)),
    (tile_bounds, (0, False, 1)),
    (tile_bounds, (None, 0, 1)),
    (tile_bounds, ("0", 0, 1)),
    (tile_bounds, (0, NAN, 1)),
    (tile_bounds, (-1, 0, 1)),
    (tile_bounds, (0, 2, 1)),
    (tile_to_quadkey, (0.5, 0, 1)),
    (tile_to_quadkey, (True, 0, 1)),
    (tile_to_quadkey, (0, None, 1)),
    (tile_to_quadkey, ({}, 0, 1)),
    (tile_to_quadkey, (0, 0, 2.0)),
    # quadkey_to_tile(quadkey)
    (quadkey_to_tile, (None,)),
    (quadkey_to_tile, (123,)),
    (quadkey_to_tile, (["1"],)),
    (quadkey_to_tile, ("12a",)),
    (quadkey_to_tile, (" 12",)),
    (quadkey_to_tile, ("0" * 31,)),
    # bbox_to_tiles(west, south, east, north, z)
    (bbox_to_tiles, (None, 0, 1, 1, 3)),
    (bbox_to_tiles, (0, "0", 1, 1, 3)),
    (bbox_to_tiles, (0, 0, NAN, 1, 3)),
    (bbox_to_tiles, (0, 0, 1, NAN, 3)),
    (bbox_to_tiles, (0, -INF, 1, 1, 3)),
    (bbox_to_tiles, (0, 0, 1, 1, 3.0)),
    (bbox_to_tiles, (0, 0, 1, 1, False)),
    (bbox_to_tiles, (0, 0, 1, 95, 3)),
    (bbox_to_tiles, (-181, 0, 1, 1, 3)),
    # tiles_to_geojson(tiles)
    (tiles_to_geojson, (None,)),
    (tiles_to_geojson, ("0/0/0",)),
    (tiles_to_geojson, ({"x": 0, "y": 0, "z": 0},)),
    (tiles_to_geojson, ([(0, 0)],)),
    (tiles_to_geojson, ([(0.5, 0, 1)],)),
    (tiles_to_geojson, ([None],)),
    (tiles_to_geojson, (["000"],)),
    (tiles_to_geojson, (True,)),
    (tiles_to_geojson, (0,)),
    (tiles_to_geojson, (1.5,)),
    (tiles_to_geojson, (NAN,)),
    (tiles_to_geojson, (INF,)),
    (tiles_to_geojson, (b"000",)),
    (tiles_to_geojson, ([{0, 1, 2}],)),
    (tiles_to_geojson, ([{"x": 0, "y": 0, "z": 0}],)),
    (tiles_to_geojson, ([(0, 0, 0, 0)],)),
    (tiles_to_geojson, ([(0, 0, NAN)],)),
    (tiles_to_geojson, ([(True, 0, 1)],)),
    (tiles_to_geojson, ([1.5],)),
]


@pytest.mark.parametrize("func,args", INVALID_CALLS)
def test_invalid_input_types_raise_value_error(func, args):
    with pytest.raises(ValueError):
        func(*args)


def test_bbox_max_tiles_validated():
    for bad in (None, 1.5, True, -1, "10"):
        with pytest.raises(ValueError):
            bbox_to_tiles(0, 0, 1, 1, 3, max_tiles=bad)
    assert tiles_to_geojson([]) == {"type": "FeatureCollection", "features": []}


@pytest.mark.parametrize(
    "argv",
    [
        ["tile", "nan", "0", "3"],
        ["tile", "0", "inf", "3"],
        ["bbox", "0", "0", "nan", "1", "3"],
        ["bbox", "0", "0", "1", "1", "3", "--max-tiles", "-5"],
        ["quadkey", "12x"],
        ["bounds", "1", "2", "0"],
    ],
)
def test_cli_rejects_invalid_values(argv, capsys):
    assert main(argv) == 2
    assert "tile-math: error:" in capsys.readouterr().err


def test_cli_bbox_count_matches_listing(capsys):
    box = ["-0.1275", "48.8567", "13.3833", "52.5167", "6"]
    assert main(["bbox", *box]) == 0
    listed = capsys.readouterr().out.strip().splitlines()
    assert main(["bbox", *box, "--count"]) == 0
    assert capsys.readouterr().out.strip() == str(len(listed))
    assert len(listed) == len(bbox_to_tiles(-0.1275, 48.8567, 13.3833, 52.5167, 6))


def test_cli_bbox_antimeridian_fiji(capsys):
    # Fiji spans the antimeridian (about 177E to 178W): tiles on both the
    # easternmost (x=63) and westernmost (x=0) columns at zoom 6.
    assert main(["bbox", "177", "-19", "-178", "-16", "6"]) == 0
    lines = capsys.readouterr().out.split()
    assert lines == ["6/0/34", "6/63/34", "6/0/35", "6/63/35"]
    assert main(["bbox", "177", "-19", "-178", "-16", "6", "--count"]) == 0
    assert capsys.readouterr().out.strip() == "4"
