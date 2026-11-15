import json
from pathlib import Path

from tile_math import bbox_to_tiles, lonlat_to_tile, tiles_to_geojson

ROOT = Path(__file__).resolve().parent.parent


def _cities():
    data = json.loads((ROOT / "examples" / "cities.geojson").read_text(encoding="utf-8"))
    return {f["properties"]["name"]: f["geometry"]["coordinates"] for f in data["features"]}


def demo_tiles():
    coords = list(_cities().values())
    lons, lats = [c[0] for c in coords], [c[1] for c in coords]
    return bbox_to_tiles(min(lons), min(lats), max(lons), max(lats), 6)


def test_known_city_tiles():
    c = _cities()
    assert lonlat_to_tile(*c["London"], 10) == (511, 340, 10)
    assert lonlat_to_tile(*c["Paris"], 10) == (518, 352, 10)
    # London is just west of Greenwich, Paris is east of it
    assert lonlat_to_tile(*c["London"], 6)[0] == 31
    assert lonlat_to_tile(*c["Paris"], 6)[0] == 32


def test_demo_covers_all_cities():
    tiles = set(demo_tiles())
    assert len(tiles) == 12
    for lon_lat in _cities().values():
        assert lonlat_to_tile(*lon_lat, 6) in tiles


def test_demo_geojson_is_current():
    stored = json.loads((ROOT / "docs" / "demo.geojson").read_text(encoding="utf-8"))
    assert stored == tiles_to_geojson(demo_tiles())
