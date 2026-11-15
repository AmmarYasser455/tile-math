# Examples

- `cities.geojson` – five European capitals (London, Paris, Brussels, Amsterdam, Berlin) as
  points, `[lon, lat]` in EPSG:4326 (WGS84). Source: Wikidata, property P625 ("coordinate
  location") of items London Q84, Paris Q90, Brussels Q239, Amsterdam Q727 and Berlin Q64,
  copied unrounded from
  `https://www.wikidata.org/w/api.php?action=wbgetclaims&entity=<Q-id>&property=P625&format=json`
  on 2026-11-15. Wikidata structured data is released under CC0 1.0 (public domain
  dedication, https://www.wikidata.org/wiki/Wikidata:Licensing). These are city reference
  points (most of them given to the arc-minute), not survey-grade positions.
- `demo.ipynb` – walkthrough of the Python API on this file.

`docs/demo.geojson` is the output of `tile-math` for this example: the zoom 6 tiles
covering the bounding box of the five cities (see `tests/test_examples.py`).
