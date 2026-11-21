import json

import pytest

from tile_math import child_tiles, lonlat_to_tile, parent_tile
from tile_math.cli import main


def test_parent_and_children_london():
    # London (-0.1275, 51.5072) is tile 10/511/340; its ancestor contains the same point.
    assert parent_tile(511, 340, 10) == (255, 170, 9)
    assert parent_tile(511, 340, 10, levels=10) == (0, 0, 0)
    assert parent_tile(511, 340, 10, levels=0) == (511, 340, 10)
    assert lonlat_to_tile(-0.1275, 51.5072, 9) == (255, 170, 9)
    assert (511, 340, 10) in child_tiles(255, 170, 9)
    assert child_tiles(0, 0, 0) == [(0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
    for c in child_tiles(255, 170, 9):
        assert parent_tile(*c) == (255, 170, 9)


@pytest.mark.parametrize(
    "call",
    [
        lambda: parent_tile(0, 0, 0),
        lambda: parent_tile(1, 1, 2, levels=3),
        lambda: parent_tile(1, 1, 2, levels=-1),
        lambda: parent_tile(1, 1, 2, levels=True),
        lambda: child_tiles(0, 0, 30),
        lambda: child_tiles(5, 0, 2),
    ],
)
def test_parent_children_invalid(call):
    with pytest.raises(ValueError):
        call()


def test_cli_parent_children(capsys):
    assert main(["parent", "10", "511", "340"]) == 0
    assert capsys.readouterr().out.strip() == "9/255/170"
    assert main(["children", "9", "255", "170"]) == 0
    assert capsys.readouterr().out.split() == ["10/510/340", "10/511/340", "10/510/341", "10/511/341"]
    assert main(["parent", "0", "0", "0"]) == 2


def test_cli_encode_roundtrip(capsys):
    assert main(["encode", "10", "511", "340"]) == 0
    qk = capsys.readouterr().out.strip()
    assert qk == "0313131311"  # London tile
    assert main(["quadkey", qk]) == 0
    assert capsys.readouterr().out.strip() == "10/511/340"
    assert main(["encode", "3", "8", "0"]) == 2  # x out of range


def test_cli_bounds_geojson_london(capsys):
    assert main(["bounds", "10", "511", "340", "--geojson"]) == 0
    (feat,) = json.loads(capsys.readouterr().out)["features"]
    assert feat["properties"] == {"x": 511, "y": 340, "z": 10, "quadkey": "0313131311"}
    ring = feat["geometry"]["coordinates"][0]
    # lon first: the London tile spans lon -0.35..0.0, lat 51.40..51.62
    assert ring[0] == [-0.3515625, pytest.approx(51.39920565355377)]
    assert ring[2] == [0.0, pytest.approx(51.6180165487737)]
    assert main(["bounds", "10", "511", "340"]) == 0
    assert capsys.readouterr().out.startswith("west=")
