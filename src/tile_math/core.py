"""Core tile maths for the Web Mercator (EPSG:3857) XYZ scheme.

Conventions: coordinates are (lon, lat) in degrees (EPSG:4326, x first);
tiles are (x, y, z) with y counted from the top (north), as in OpenStreetMap
and Google; bounding boxes are (west, south, east, north).
"""

import math
import numbers
from collections.abc import Mapping, Set

from pyproj import Transformer

MAX_ZOOM = 30
# Latitude at which the Web Mercator square ends: atan(sinh(pi)) in degrees.
MAX_LAT = 85.0511287798066


def _is_int(v):
    return isinstance(v, numbers.Integral) and not isinstance(v, bool)


def _check_num(v, name):
    """Return v as a finite float; reject bool, str, None, containers and NaN/inf."""
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        raise ValueError(f"{name} must be a real number, got {v!r}")
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite, got {v!r}")
    return f


def _check_zoom(z):
    if not _is_int(z) or not 0 <= z <= MAX_ZOOM:
        raise ValueError(f"zoom must be an integer in 0..{MAX_ZOOM}, got {z!r}")
    return int(z)


def _check_tile(x, y, z):
    z = _check_zoom(z)
    n = 1 << z
    if not (_is_int(x) and _is_int(y) and 0 <= x < n and 0 <= y < n):
        raise ValueError(f"tile {z}/{x!r}/{y!r}: x and y must be integers in 0..{n - 1}")
    return int(x), int(y), z


def _check_lon(lon, name="longitude"):
    lon = _check_num(lon, name)
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"{name} must be within [-180, 180], got {lon!r}")
    return lon


def _snap(v, n):
    """Snap a tile-unit coordinate to the nearest integer if within roundoff of it.

    A forward/inverse projection round trip of a tile edge (tile_bounds then
    back to tile units) is off by a few float ulps of the Mercator metres
    (~1e-8 m out of 2e7 m), so an edge may come back as 340.0000000001.
    The tolerance is a fixed fraction of the world width, 1e-13 (n * 1e-13
    tile units), which is about 4 micrometres on the ground at every zoom:
    far above that roundoff and far below any meaningful distance.
    """
    r = round(v)
    return float(r) if abs(v - r) <= n * _SNAP_WORLD else v


# Snapping tolerance as a fraction of the world width (~4 micrometres).
_SNAP_WORLD = 1e-13


def _lon_to_x(lon, n):
    return (lon + 180.0) / 360.0 * n


# EPSG:4326 (lon, lat) <-> EPSG:3857 (x, y metres); always_xy keeps lon/lat order.
_TO_MERCATOR = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
_FROM_MERCATOR = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
# Half the width of the Web Mercator square in metres (pi * WGS84 semi-major axis).
_HALF = 20037508.342789244


def _lat_to_y(lat, n):
    _, my = _TO_MERCATOR.transform(0.0, lat)
    return (_HALF - my) / (2.0 * _HALF) * n


def _row_lat(row, n):
    _, lat = _FROM_MERCATOR.transform(0.0, _HALF * (1 - 2 * row / n))
    return lat


def lonlat_to_tile(lon, lat, z):
    """Return the (x, y, z) tile containing a lon/lat point.

    Raises ValueError for latitudes beyond +-85.0511 (outside Web Mercator).
    Points on a tile edge belong to the tile east/south of it; lon=180 and the
    southern limit fall in the last column/row.
    """
    z = _check_zoom(z)
    lon = _check_lon(lon)
    lat = _check_num(lat, "latitude")
    if not -MAX_LAT <= lat <= MAX_LAT:
        raise ValueError(f"latitude must be within +-{MAX_LAT:.4f} for Web Mercator, got {lat!r}")
    n = 1 << z
    x = min(max(int(math.floor(_snap(_lon_to_x(lon, n), n))), 0), n - 1)
    y = min(max(int(math.floor(_snap(_lat_to_y(lat, n), n))), 0), n - 1)
    return x, y, z


def tile_bounds(x, y, z):
    """Return (west, south, east, north) in degrees for a tile."""
    x, y, z = _check_tile(x, y, z)
    n = 1 << z

    return (x / n * 360.0 - 180.0, _row_lat(y + 1, n), (x + 1) / n * 360.0 - 180.0, _row_lat(y, n))


def tile_to_quadkey(x, y, z):
    """Return the Bing-style quadkey string for a tile ('' at zoom 0)."""
    x, y, z = _check_tile(x, y, z)
    digits = []
    for i in range(z, 0, -1):
        mask = 1 << (i - 1)
        digits.append(str((1 if x & mask else 0) + (2 if y & mask else 0)))
    return "".join(digits)


def quadkey_to_tile(quadkey):
    """Return (x, y, z) for a quadkey string of digits 0-3."""
    if not isinstance(quadkey, str) or any(c not in "0123" for c in quadkey):
        raise ValueError(f"invalid quadkey {quadkey!r}: only digits 0-3 are allowed")
    z = len(quadkey)
    _check_zoom(z)
    x = y = 0
    for c in quadkey:
        d = int(c)
        x = (x << 1) | (d & 1)
        y = (y << 1) | (d >> 1)
    return x, y, z


def parent_tile(x, y, z, levels=1):
    """Return the (x, y, z) ancestor tile `levels` zoom levels up (default: the direct parent)."""
    x, y, z = _check_tile(x, y, z)
    if not _is_int(levels) or not 0 <= levels <= z:
        raise ValueError(f"levels must be an integer in 0..{z} for zoom {z}, got {levels!r}")
    return x >> levels, y >> levels, z - levels


def child_tiles(x, y, z):
    """Return the four (x, y, z+1) child tiles, north-west first, row by row."""
    x, y, z = _check_tile(x, y, z)
    if z >= MAX_ZOOM:
        raise ValueError(f"tile at zoom {z} has no children (maximum zoom is {MAX_ZOOM})")
    return [(2 * x + dx, 2 * y + dy, z + 1) for dy in (0, 1) for dx in (0, 1)]


def _span(lo, hi, n):
    """Tile index range covering [lo, hi] (tile units); exact edges don't spill over."""
    lo, hi = _snap(lo, n), _snap(hi, n)
    first = min(max(int(math.floor(lo)), 0), n - 1)
    last = min(max(int(math.ceil(hi)) - 1, first), n - 1)
    return first, last


def _merge(ranges):
    """Merge overlapping or adjacent inclusive (first, last) ranges."""
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def bbox_to_tiles(west, south, east, north, z, max_tiles=1_000_000):
    """List the (x, y, z) tiles covering a bbox, row by row from the north.

    Latitudes beyond +-85.0511 are clamped to the Web Mercator limit (they must
    still be within +-90). If west > east the box is treated as crossing the
    antimeridian and the tiles on both sides are returned. A tile whose edge
    merely touches the box is not included. Raises ValueError if the result
    would exceed max_tiles.
    """
    z = _check_zoom(z)
    west = _check_lon(west, "west")
    east = _check_lon(east, "east")
    south = _check_num(south, "south")
    north = _check_num(north, "north")
    if not _is_int(max_tiles) or max_tiles < 0:
        raise ValueError(f"max_tiles must be a non-negative integer, got {max_tiles!r}")
    if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
        raise ValueError("latitude must be within [-90, 90]")
    if south > north:
        raise ValueError(f"south ({south}) must not exceed north ({north})")
    n = 1 << z
    south, north = (min(max(v, -MAX_LAT), MAX_LAT) for v in (south, north))
    y0, y1 = _span(_lat_to_y(north, n), _lat_to_y(south, n), n)
    if west <= east:
        x_ranges = [_span(_lon_to_x(west, n), _lon_to_x(east, n), n)]
    else:
        # Antimeridian: [west, 180] and [-180, east]; skip zero-width pieces.
        x_ranges = []
        if west < 180.0:
            x_ranges.append(_span(_lon_to_x(west, n), n, n))
        if east > -180.0:
            x_ranges.append(_span(0, _lon_to_x(east, n), n))
        if not x_ranges:  # degenerate line on the antimeridian
            x_ranges = [(n - 1, n - 1)]
        x_ranges = _merge(x_ranges)
    count = (y1 - y0 + 1) * sum(b - a + 1 for a, b in x_ranges)
    if count > max_tiles:
        raise ValueError(f"bbox covers {count} tiles at zoom {z}, more than max_tiles={max_tiles}")
    return [(x, y, z) for y in range(y0, y1 + 1) for a, b in x_ranges for x in range(a, b + 1)]


def tiles_to_geojson(tiles):
    """Return a GeoJSON FeatureCollection (EPSG:4326, lon/lat) of tile polygons.

    Rings are counter-clockwise (RFC 7946). Properties: x, y, z, quadkey.
    """
    msg = f"tiles must be an iterable of (x, y, z) tuples, got {tiles!r}"
    if isinstance(tiles, (str, bytes, bytearray, Mapping)):
        raise ValueError(msg)
    try:
        items = iter(tiles)
    except TypeError:  # None, bool, numbers, NaN and other non-iterables
        raise ValueError(msg) from None
    features = []
    for t in items:
        if (
            isinstance(t, (str, bytes, bytearray, Mapping, Set))
            or not hasattr(t, "__len__")
            or not hasattr(t, "__getitem__")
            or len(t) != 3
        ):
            raise ValueError(f"each tile must be an (x, y, z) sequence, got {t!r}")
        x, y, z = _check_tile(*t)
        w, s, e, n = tile_bounds(x, y, z)
        features.append(
            {
                "type": "Feature",
                "properties": {"x": x, "y": y, "z": z, "quadkey": tile_to_quadkey(x, y, z)},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}
