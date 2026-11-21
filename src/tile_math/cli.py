"""Command-line interface: tile-math {tile,bounds,quadkey,bbox}."""

import argparse
import json
import sys

from . import core


def _build_parser():
    p = argparse.ArgumentParser(prog="tile-math", description="lat/lon <-> XYZ tile <-> quadkey maths.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("tile", help="tile containing a point (lon first)")
    s.add_argument("lon", type=float)
    s.add_argument("lat", type=float)
    s.add_argument("zoom", type=int)

    s = sub.add_parser("bounds", help="bounds (west south east north) and quadkey of a tile")
    s.add_argument("z", type=int)
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)
    s.add_argument("--geojson", action="store_true", help="output the tile polygon as GeoJSON")

    s = sub.add_parser("quadkey", help="decode a quadkey to z/x/y")
    s.add_argument("quadkey")

    s = sub.add_parser("encode", help="quadkey of a tile (inverse of quadkey)")
    s.add_argument("z", type=int)
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)

    s = sub.add_parser("parent", help="ancestor tile of a tile")
    s.add_argument("z", type=int)
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)
    s.add_argument("--levels", type=int, default=1, help="zoom levels up (default 1)")

    s = sub.add_parser("children", help="the four child tiles of a tile")
    s.add_argument("z", type=int)
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)

    s = sub.add_parser("bbox", help="tiles covering a bbox")
    s.add_argument("west", type=float)
    s.add_argument("south", type=float)
    s.add_argument("east", type=float)
    s.add_argument("north", type=float)
    s.add_argument("zoom", type=int)
    s.add_argument("--geojson", action="store_true", help="output tile polygons as GeoJSON")
    s.add_argument("--count", action="store_true", help="print only the number of tiles")
    s.add_argument("--max-tiles", type=int, default=1_000_000)
    return p


def _run(args):
    if args.cmd == "tile":
        x, y, z = core.lonlat_to_tile(args.lon, args.lat, args.zoom)
        return f"{z}/{x}/{y} quadkey={core.tile_to_quadkey(x, y, z)}"
    if args.cmd == "bounds":
        if args.geojson:
            return json.dumps(core.tiles_to_geojson([(args.x, args.y, args.z)]), indent=2)
        b = core.tile_bounds(args.x, args.y, args.z)
        qk = core.tile_to_quadkey(args.x, args.y, args.z)
        return "west=%r south=%r east=%r north=%r quadkey=%s" % (*b, qk)
    if args.cmd == "quadkey":
        x, y, z = core.quadkey_to_tile(args.quadkey)
        return f"{z}/{x}/{y}"
    if args.cmd == "encode":
        return core.tile_to_quadkey(args.x, args.y, args.z)
    if args.cmd == "parent":
        x, y, z = core.parent_tile(args.x, args.y, args.z, args.levels)
        return f"{z}/{x}/{y}"
    if args.cmd == "children":
        return "\n".join(f"{z}/{x}/{y}" for x, y, z in core.child_tiles(args.x, args.y, args.z))
    tiles = core.bbox_to_tiles(
        args.west, args.south, args.east, args.north, args.zoom, max_tiles=args.max_tiles
    )
    if args.count:
        return str(len(tiles))
    if args.geojson:
        return json.dumps(core.tiles_to_geojson(tiles), indent=2)
    return "\n".join(f"{z}/{x}/{y}" for x, y, z in tiles)


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        print(_run(args))
    except ValueError as exc:
        print(f"tile-math: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
