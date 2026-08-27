#!/usr/bin/env python3
"""Fetch downtown Elizabethtown OSM slice (station → Center Square).

Does not hit Google. Source: OpenStreetMap via Overpass (ODbL).
Run from repo root: python3 scripts/fetch_osm.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Origin: Elizabethtown Amtrak station, 50 S Wilson Ave
ORIGIN_LAT = 40.146889
ORIGIN_LON = -76.61222

# Slice bbox in WGS84. Tuned so station + High/Market (Center Square) fit
# inside ~650–750 m on a side without the rest of the borough.
# Overpass order: south, west, north, east
BBOX = {
    "south": 40.14620,
    "west": -76.61340,
    "north": 40.15270,
    "east": -76.60490,
}

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

UA = "etown-voxel/0.1 (https://github.com/urbanrunnerx/etown-voxel; OSM voxel walk; ODbL)"

QUERY = """
[out:json][timeout:90];
(
  way["building"]({s},{w},{n},{e});
  relation["building"]({s},{w},{n},{e});
  way["highway"]({s},{w},{n},{e});
  way["railway"]({s},{w},{n},{e});
  node["railway"]({s},{w},{n},{e});
  way["landuse"]({s},{w},{n},{e});
  way["amenity"="parking"]({s},{w},{n},{e});
  way["leisure"]({s},{w},{n},{e});
  node["place"]({s},{w},{n},{e});
  node["name"]({s},{w},{n},{e});
  node["public_transport"]({s},{w},{n},{e});
  node["railway"="station"]({s},{w},{n},{e});
  node["amenity"="bus_station"]({s},{w},{n},{e});
  node["addr:housenumber"]({s},{w},{n},{e});
);
out body;
>;
out skel qt;
""".format(
    s=BBOX["south"], w=BBOX["west"], n=BBOX["north"], e=BBOX["east"]
)


def fetch(query: str) -> dict:
    body = query.encode("utf-8")
    last_err = None
    for url in ENDPOINTS:
        print(f"POST {url} ({len(body)} bytes query)", flush=True)
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent": UA,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
            if raw[:1] != b"{":
                preview = raw[:400].decode("utf-8", "replace")
                print(f"  non-JSON from {url}: {preview[:200]!r}")
                last_err = RuntimeError(preview[:200])
                time.sleep(2)
                continue
            data = json.loads(raw)
            print(f"  ok: {len(data.get('elements', []))} elements, {len(raw)} bytes")
            return data
        except Exception as exc:  # noqa: BLE001 — try next mirror
            print(f"  fail: {type(exc).__name__}: {exc}")
            last_err = exc
            time.sleep(2)
    raise SystemExit(f"all Overpass endpoints failed: {last_err}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "data" / "osm-raw.json"
    print("bbox", BBOX)
    print("origin", ORIGIN_LAT, ORIGIN_LON)
    data = fetch(QUERY)
    data["_etown_meta"] = {
        "origin_lat": ORIGIN_LAT,
        "origin_lon": ORIGIN_LON,
        "bbox": BBOX,
        "source": "OpenStreetMap via Overpass",
        "license": "ODbL",
    }
    out.write_text(json.dumps(data), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    sys.exit(main())
