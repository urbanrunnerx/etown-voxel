#!/usr/bin/env python3
import json, math
from collections import Counter
from pathlib import Path

d = json.loads(Path("data/osm-raw.json").read_text())
els = d["elements"]
print("n", len(els), "meta", d.get("osm3s"))
print(Counter(e.get("type") for e in els))
ORIGIN_LAT, ORIGIN_LON = 40.146889, -76.61222

def mxy(lat, lon):
    mx = (lon - ORIGIN_LON) * 111320 * math.cos(math.radians(ORIGIN_LAT))
    my = (lat - ORIGIN_LAT) * 111320
    return mx, my

nodes = {e["id"]: (e["lat"], e["lon"]) for e in els if e.get("type") == "node" and "lat" in e}
print("nodes with coords", len(nodes))
lats = [p[0] for p in nodes.values()]
lons = [p[1] for p in nodes.values()]
print("node bbox", min(lats), min(lons), max(lats), max(lons))
print("span m", mxy(max(lats), max(lons)), mxy(min(lats), min(lons)))

print("\n=== NAMED FEATURES ===")
for e in els:
    t = e.get("tags") or {}
    n = t.get("name") or t.get("ref")
    if not n:
        continue
    kind = (
        t.get("highway")
        or t.get("railway")
        or t.get("building")
        or t.get("public_transport")
        or t.get("amenity")
        or t.get("place")
        or t.get("leisure")
        or t.get("landuse")
    )
    extra = {
        k: t[k]
        for k in ("addr:street", "addr:housenumber", "operator", "building:levels", "height")
        if k in t
    }
    print(f"{e['type']:8} {e['id']:<12} {n!r:40} {kind} {extra}")

print("\n=== HIGHWAYS ===")
print(Counter((e.get("tags") or {}).get("highway") for e in els if (e.get("tags") or {}).get("highway")))
print("\n=== RAILWAY ===")
print(Counter((e.get("tags") or {}).get("railway") for e in els if (e.get("tags") or {}).get("railway")))
print("\n=== BUILDING ===")
print(Counter((e.get("tags") or {}).get("building") for e in els if (e.get("tags") or {}).get("building")))
print("levels", sum(1 for e in els if (e.get("tags") or {}).get("building:levels")))
print("height", sum(1 for e in els if (e.get("tags") or {}).get("height")))
print("landuse", Counter((e.get("tags") or {}).get("landuse") for e in els if (e.get("tags") or {}).get("landuse")))
print("leisure", Counter((e.get("tags") or {}).get("leisure") for e in els if (e.get("tags") or {}).get("leisure")))
print("parking", sum(1 for e in els if (e.get("tags") or {}).get("amenity") == "parking"))
print("sidewalk", sum(1 for e in els if "sidewalk" in (e.get("tags") or {})))
print("tagged relations", [e.get("id") for e in els if e.get("type") == "relation" and e.get("tags")])

print("\n=== near origin nodes with tags ===")
for e in els:
    if e.get("type") != "node" or "lat" not in e:
        continue
    t = e.get("tags") or {}
    if not t:
        continue
    x, y = mxy(e["lat"], e["lon"])
    if abs(x) < 120 and abs(y) < 120:
        print(round(x, 1), round(y, 1), t)

print("\n=== buildings / parking near origin ===")
for e in els:
    if e.get("type") != "way":
        continue
    t = e.get("tags") or {}
    if "building" not in t and t.get("amenity") != "parking":
        continue
    nds = e.get("nodes") or []
    pts = [nodes[i] for i in nds if i in nodes]
    if not pts:
        continue
    clat = sum(p[0] for p in pts) / len(pts)
    clon = sum(p[1] for p in pts) / len(pts)
    x, y = mxy(clat, clon)
    if abs(x) < 150 and abs(y) < 150:
        print(
            "xy",
            round(x, 1),
            round(y, 1),
            "n",
            len(pts),
            t.get("name"),
            t.get("building"),
            t.get("amenity"),
            t.get("building:levels"),
            t.get("addr:housenumber"),
            t.get("addr:street"),
        )

print("\n=== HIGH / MARKET / WILSON WAYS ===")
high_nodes = set()
market_nodes = set()
wilson_nodes = set()
for e in els:
    t = e.get("tags") or {}
    n = t.get("name") or ""
    nds = set(e.get("nodes") or [])
    if "High Street" in n:
        high_nodes |= nds
        print("HIGH", e["id"], n, t.get("highway"), "nodes", len(nds), "lanes", t.get("lanes"), "width", t.get("width"), "sw", t.get("sidewalk"))
    if "Market Street" in n:
        market_nodes |= nds
        print("MARKET", e["id"], n, t.get("highway"), "nodes", len(nds), "lanes", t.get("lanes"), "width", t.get("width"), "sw", t.get("sidewalk"))
    if "Wilson" in n:
        wilson_nodes |= nds
        print("WILSON", e["id"], n, t.get("highway"), "nodes", len(nds), "lanes", t.get("lanes"), "width", t.get("width"))

inter = high_nodes & market_nodes
print("High∩Market nodes", len(inter))
for nid in inter:
    if nid in nodes:
        lat, lon = nodes[nid]
        x, y = mxy(lat, lon)
        print("  INTERSECTION", nid, lat, lon, "xy", round(x, 1), round(y, 1))

print("Wilson nodes", len(wilson_nodes))
for nid in list(wilson_nodes)[:12]:
    if nid in nodes:
        lat, lon = nodes[nid]
        x, y = mxy(lat, lon)
        print("  wilson pt", round(x, 1), round(y, 1), lat, lon)

print("\n=== RAIL WAYS ===")
for e in els:
    t = e.get("tags") or {}
    if "railway" not in t:
        continue
    nds = e.get("nodes") or []
    pts = [nodes[i] for i in nds if i in nodes]
    if not pts:
        print("rail", e["type"], e["id"], t.get("railway"), t.get("name"), "no pts")
        continue
    clat = sum(p[0] for p in pts) / len(pts)
    clon = sum(p[1] for p in pts) / len(pts)
    x, y = mxy(clat, clon)
    print("rail", e["type"], e["id"], t.get("railway"), t.get("name"), "n", len(pts), "mid", round(x, 1), round(y, 1))

print("\n=== PATHS near origin ===")
for e in els:
    t = e.get("tags") or {}
    if t.get("highway") not in ("footway", "path", "cycleway", "pedestrian", "steps"):
        continue
    nds = e.get("nodes") or []
    pts = [nodes[i] for i in nds if i in nodes]
    if not pts:
        continue
    clat = sum(p[0] for p in pts) / len(pts)
    clon = sum(p[1] for p in pts) / len(pts)
    x, y = mxy(clat, clon)
    if abs(x) < 250 and abs(y) < 250:
        print(round(x, 1), round(y, 1), t.get("highway"), t.get("name"), t.get("footway"), t.get("surface"), "n", len(pts))

print("\n=== ALL NAMED HIGHWAYS ===")
for e in els:
    t = e.get("tags") or {}
    if t.get("highway") and t.get("name"):
        print(t["name"], t["highway"], "lanes", t.get("lanes"), "w", t.get("width"), "sw", t.get("sidewalk"))

print("\nbuilding count", sum(1 for e in els if (e.get("tags") or {}).get("building")))
print("highway way count", sum(1 for e in els if (e.get("tags") or {}).get("highway")))
