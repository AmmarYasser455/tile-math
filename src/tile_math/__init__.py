"""Convert between lat/lon, XYZ web-map tiles and quadkeys."""

from .core import (
    MAX_LAT,
    MAX_ZOOM,
    bbox_to_tiles,
    child_tiles,
    lonlat_to_tile,
    parent_tile,
    quadkey_to_tile,
    tile_bounds,
    tile_to_quadkey,
    tiles_to_geojson,
)

__version__ = "0.1.0"
__all__ = [
    "MAX_LAT",
    "MAX_ZOOM",
    "bbox_to_tiles",
    "child_tiles",
    "lonlat_to_tile",
    "parent_tile",
    "quadkey_to_tile",
    "tile_bounds",
    "tile_to_quadkey",
    "tiles_to_geojson",
]
