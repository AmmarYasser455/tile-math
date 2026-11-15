"""Build the tile-math showcase: which web-map tiles are needed to cover Egypt?

Run from the repository root, offline:  python showcase/make_showcase.py

Reads showcase/data/egypt.geojson (Natural Earth, public domain) and writes
map.geojson, map.png and index.html into showcase/ (or into the directory given
as the first argument). All coordinates are lon/lat (x first), EPSG:4326.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from tile_math import (  # noqa: E402
    bbox_to_tiles,
    tile_bounds,
    tile_to_quadkey,
    tiles_to_geojson,
)

MAP_ZOOM = 8
ZOOMS = (5, 6, 7, 8, 9)
CREDIT = "Data: Natural Earth (public domain). Tiles: tile-math, Web Mercator XYZ"
COLORS = {"border": "#d95f02", "interior": "#1b9e77", "outside": "#cfcfcf"}


def load_egypt(data_dir=HERE / "data"):
    """Return the Egypt exterior ring as a list of (lon, lat), counter-clockwise."""
    with open(Path(data_dir) / "egypt.geojson", encoding="utf-8") as fh:
        return ring_from_geojson(json.load(fh))


def _is_real(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


def ring_from_geojson(doc):
    """Validate a FeatureCollection holding one Polygon (no holes); return its ring.

    Raises ValueError for anything else (wrong types, empty collections,
    MultiPolygon, holes, open or too-short rings, NaN or out-of-range lon/lat).
    The ring is returned as (lon, lat) tuples, closed and counter-clockwise.
    """
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection":
        raise ValueError("expected a GeoJSON FeatureCollection")
    feats = doc.get("features")
    if not isinstance(feats, list) or len(feats) != 1 or not isinstance(feats[0], dict):
        raise ValueError("expected exactly one feature")
    geom = feats[0].get("geometry")
    if not isinstance(geom, dict) or geom.get("type") != "Polygon":
        raise ValueError("expected a Polygon geometry")
    rings = geom.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1:
        raise ValueError("expected a Polygon with one exterior ring and no holes")
    ring = []
    for p in rings[0] if isinstance(rings[0], list) else [None]:
        if (not isinstance(p, (list, tuple)) or len(p) < 2
                or not _is_real(p[0]) or not _is_real(p[1])):
            raise ValueError(f"invalid position {p!r}")
        lon, lat = float(p[0]), float(p[1])
        if not (-180 <= lon <= 180 and -85.0511 <= lat <= 85.0511):
            raise ValueError(f"position {p!r} outside lon/lat range of Web Mercator")
        ring.append((lon, lat))
    if len(ring) < 4 or ring[0] != ring[-1]:
        raise ValueError("ring must be closed and have at least 4 positions")
    area = _signed_area(ring)
    if area == 0:
        raise ValueError("ring has zero area")
    if area < 0:
        ring.reverse()
    return ring


def _signed_area(ring):
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:]))


def ring_bbox(ring):
    xs, ys = zip(*ring)
    return min(xs), min(ys), max(xs), max(ys)


def point_in_ring(lon, lat, ring):
    """Ray-casting test in lon/lat (fine here: Egypt is far from the antimeridian)."""
    inside = False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        if (y0 > lat) != (y1 > lat) and lon < x0 + (lat - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def segment_crosses_box(p0, p1, box):
    """True if segment p0-p1 passes through the open interior of box (w, s, e, n).

    Exact Liang-Barsky clipping in lon/lat (the segment is a straight line in
    lon/lat, as GeoJSON edges are). Touching only an edge or corner is False.
    """
    (x0, y0), (x1, y1) = p0, p1
    w, s, e, n = box
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - w), (dx, e - x0), (-dy, y0 - s), (dy, n - y0)):
        if p == 0:
            if q <= 0:  # parallel to this side and outside it or on it
                return False
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 >= t1:
            return False
    tm = (t0 + t1) / 2
    mx, my = x0 + tm * dx, y0 + tm * dy
    return w < mx < e and s < my < n


def border_tiles(ring, z):
    """Set of (x, y, z) tiles whose interior the border passes through (exact)."""
    found = set()
    for p0, p1 in zip(ring, ring[1:]):
        if p0 == p1:
            continue
        cands = bbox_to_tiles(min(p0[0], p1[0]), min(p0[1], p1[1]),
                              max(p0[0], p1[0]), max(p0[1], p1[1]), z)
        for t in cands:
            if t not in found and segment_crosses_box(p0, p1, tile_bounds(*t)):
                found.add(t)
    return found


def classify(ring, z):
    """Tiles covering Egypt's bbox at zoom z, each marked border/interior/outside.

    A tile the border does not cross is entirely inside or entirely outside the
    polygon, so testing its centre classifies it exactly.
    """
    west, south, east, north = ring_bbox(ring)
    tiles = bbox_to_tiles(west, south, east, north, z)
    edge = border_tiles(ring, z)
    rows = []
    for t in tiles:
        w, s, e, n = tile_bounds(*t)
        if t in edge:
            status = "border"
        elif point_in_ring((w + e) / 2, (s + n) / 2, ring):
            status = "interior"
        else:
            status = "outside"
        rows.append({"x": t[0], "y": t[1], "z": z, "quadkey": tile_to_quadkey(*t), "status": status})
    return rows


def summary(ring, zooms=ZOOMS):
    """Per-zoom counts: tiles in the bbox, tiles holding Egypt, and the share."""
    out = []
    for z in zooms:
        rows = classify(ring, z)
        n_b = sum(r["status"] == "border" for r in rows)
        n_i = sum(r["status"] == "interior" for r in rows)
        out.append({"zoom": z, "bbox_tiles": len(rows), "border": n_b, "interior": n_i,
                    "needed": n_b + n_i, "needed_share": round((n_b + n_i) / len(rows), 3)})
    return out


def build_geojson(ring, z=MAP_ZOOM):
    rows = classify(ring, z)
    fc = tiles_to_geojson([(r["x"], r["y"], r["z"]) for r in rows])
    for feat, r in zip(fc["features"], rows):
        feat["properties"]["status"] = r["status"]
        feat["properties"]["kind"] = "tile"
    w, s, e, n = ring_bbox(ring)
    fc["features"].append({
        "type": "Feature",
        "properties": {"kind": "border", "name": "Egypt", "source": "Natural Earth 1:50m admin-0",
                       "bbox_west_south_east_north": [w, s, e, n]},
        "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in ring]]},
    })
    return fc


def draw_map(fc, path, ring):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Polygon

    fig, ax = plt.subplots(figsize=(8.5, 7.0), dpi=150)
    for feat in fc["features"]:
        if feat["properties"]["kind"] != "tile":
            continue
        p = feat["properties"]
        c = COLORS[p["status"]]
        ax.add_patch(Polygon(feat["geometry"]["coordinates"][0], closed=True, fc=c,
                             ec="white", lw=0.8, alpha=0.75 if p["status"] != "outside" else 0.6))
    xs, ys = zip(*ring)
    ax.plot(xs, ys, color="black", lw=1.0)
    ax.autoscale_view()
    ax.set_aspect(1 / math.cos(math.radians(27)))  # keep shapes near Egypt's latitude
    ax.set_xlabel("Longitude (degrees east, EPSG:4326)")
    ax.set_ylabel("Latitude (degrees north)")
    ax.set_title(f"Web-map tiles covering Egypt at zoom {MAP_ZOOM}\n(north up, lon/lat axes)")
    counts = {k: sum(f["properties"].get("status") == k for f in fc["features"]) for k in COLORS}
    ax.legend(handles=[
        Patch(fc=COLORS["border"], alpha=0.75, label=f"Border tile ({counts['border']})"),
        Patch(fc=COLORS["interior"], alpha=0.75, label=f"Fully inland tile ({counts['interior']})"),
        Patch(fc=COLORS["outside"], alpha=0.6, label=f"In bbox, no Egypt ({counts['outside']})"),
    ], loc="lower left", fontsize=8)
    fig.text(0.99, 0.01, CREDIT, ha="right", va="bottom", fontsize=7, color="#444")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tile-math showcase: tiles covering Egypt</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
body{margin:0;font-family:system-ui,sans-serif}
header{padding:8px 14px}
h1{font-size:1.2rem;margin:0 0 4px}
p{margin:2px 0;font-size:.9rem}
#map{height:calc(100vh - 110px)}
</style></head><body>
<header>
<h1>Which web-map tiles cover Egypt at zoom 8?</h1>
<p>Tiles are the Web Mercator XYZ tiles in Egypt's bounding box, computed with tile-math. Orange tiles are crossed by the border or coast, green tiles lie fully inland, grey tiles are in the box but outside Egypt.</p>
<p>Border data: Natural Earth (public domain). Source code: <a href="https://github.com/AmmarYasser455/tile-math">AmmarYasser455/tile-math</a>.</p>
</header>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
var colors = %(colors)s;
fetch('map.geojson').then(function (r) { return r.json(); }).then(function (data) {
  var layer = L.geoJSON(data, {
    style: function (f) {
      var p = f.properties;
      if (p.kind === 'border') { return {color: '#000', weight: 2, fill: false}; }
      return {color: '#fff', weight: 1, fillColor: colors[p.status], fillOpacity: 0.55};
    },
    onEachFeature: function (f, l) {
      var rows = Object.keys(f.properties).map(function (k) {
        return '<b>' + k + '</b>: ' + JSON.stringify(f.properties[k]);
      });
      l.bindPopup(rows.join('<br>'));
    }
  }).addTo(map);
  map.fitBounds(layer.getBounds());
});
</script></body></html>
"""


def main(out_dir=HERE, data_dir=HERE / "data", png=True):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ring = load_egypt(data_dir)
    fc = build_geojson(ring)
    (out_dir / "map.geojson").write_text(json.dumps(fc, separators=(",", ":")) + "\n", encoding="utf-8")
    (out_dir / "index.html").write_text(INDEX_HTML % {"colors": json.dumps(COLORS)}, encoding="utf-8")
    if png:
        draw_map(fc, out_dir / "map.png", ring)
    return fc


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else HERE)
