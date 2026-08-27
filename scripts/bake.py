#!/usr/bin/env python3
"""Voxelize the Elizabethtown downtown OSM slice at 1 meter.

Reads data/osm-raw.json, writes data/chunk.json (baked, no Overpass at play).
Projection: equirectangular meters, origin at the Amtrak station.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ORIGIN_LAT = 40.146889
ORIGIN_LON = -76.61222
COS_LAT = math.cos(math.radians(ORIGIN_LAT))
M_PER_DEG_LAT = 111320.0
M_PER_DEG_LON = 111320.0 * COS_LAT

# Slice in local meters (x east, z north). Station at (0,0),
# Center Square ~ (531, 514). Tight around the walk, not the borough.
MIN_X, MAX_X = -100, 620
MIN_Z, MAX_Z = -80, 600

# Ground materials
G_GRASS, G_ASPHALT, G_SIDEWALK, G_PATH, G_PARKING, G_RAIL, G_BALLAST, G_PLATFORM, G_PLAZA = range(1, 10)

# Wall materials
W_BRICK, W_BRICK2, W_LIMESTONE, W_HOUSE, W_SHED, W_INDUSTRIAL, W_CHURCH, W_WOOD = range(10, 18)

ROAD_WIDTH = {
    "primary": 12.0,
    "secondary": 10.0,
    "tertiary": 9.0,
    "residential": 8.0,
    "unclassified": 7.0,
    "living_street": 6.0,
    "service": 4.0,
    "unclassified": 7.0,
}
PATH_WIDTH = {
    "footway": 2.0,
    "path": 3.0,
    "cycleway": 3.0,
    "steps": 2.0,
    "pedestrian": 6.0,
    "track": 3.0,
}


def lonlat_to_local(lat: float, lon: float) -> tuple[float, float]:
    x = (lon - ORIGIN_LON) * M_PER_DEG_LON
    z = (lat - ORIGIN_LAT) * M_PER_DEG_LAT
    return x, z


def parse_height(tags: dict, default: float) -> int:
    raw = tags.get("height")
    if raw:
        s = str(raw).strip().lower().replace("metres", "").replace("meters", "")
        s = s.replace("meter", "").replace("m", "").strip()
        try:
            if "ft" in s or "'" in s:
                s = s.replace("ft", "").replace("'", "").strip()
                return max(3, int(round(float(s) * 0.3048)))
            return max(3, int(round(float(s))))
        except ValueError:
            pass
    lv = tags.get("building:levels") or tags.get("levels")
    if lv:
        try:
            return max(3, int(round(float(str(lv).split(";")[0]) * 3.0)))
        except ValueError:
            pass
    return int(default)


def building_default_h(tags: dict) -> float:
    b = (tags.get("building") or "").lower()
    if b in ("shed", "garage", "carport", "roof"):
        return 3.0
    if b in ("church", "cathedral", "chapel"):
        return 16.0
    if b in ("apartments", "residential"):
        return 12.0
    if b in ("industrial", "warehouse"):
        return 10.0
    if b in ("train_station", "transportation"):
        return 9.0
    if b in ("retail", "commercial"):
        return 9.0
    if b in ("house", "detached", "semidetached_house", "terrace"):
        return 7.0
    return 8.0


def wall_mat_for(tags: dict) -> int:
    b = (tags.get("building") or "").lower()
    name = (tags.get("name") or "").lower()
    if "amtrak" in name or b == "train_station":
        return W_LIMESTONE
    if b in ("church", "cathedral", "chapel"):
        return W_CHURCH
    if b in ("industrial", "warehouse"):
        return W_INDUSTRIAL
    if b in ("shed", "garage", "carport"):
        return W_SHED
    if b in ("house", "detached", "semidetached_house"):
        return W_HOUSE
    if b in ("retail", "commercial", "yes") and "market" in (tags.get("addr:street") or "").lower():
        return W_BRICK2
    # hash id into two brick tones so rows aren't identical
    return W_BRICK if (hash(tags.get("name") or b) % 2 == 0) else W_BRICK2


def point_in_poly(px: float, pz: float, poly: np.ndarray) -> bool:
    # ray cast, poly shape (n, 2)
    x = poly[:, 0]
    z = poly[:, 1]
    n = len(poly)
    xj = np.roll(x, 1)
    zj = np.roll(z, 1)
    intersect = ((z > pz) != (zj > pz)) & (
        px < (xj - x) * (pz - z) / ((zj - z) + 1e-12) + x
    )
    return bool(intersect.sum() % 2 == 1)


def dist_point_seg(px, pz, x0, z0, x1, z1) -> float:
    vx, vz = x1 - x0, z1 - z0
    l2 = vx * vx + vz * vz
    if l2 < 1e-9:
        return math.hypot(px - x0, pz - z0)
    t = ((px - x0) * vx + (pz - z0) * vz) / l2
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return math.hypot(px - (x0 + t * vx), pz - (z0 + t * vz))


def stamp_polyline(grid: np.ndarray, pts: list[tuple[float, float]], half_w: float, mat: int, min_x: int, min_z: int) -> None:
    h, w = grid.shape
    hw = max(0.6, half_w)
    pad = int(math.ceil(hw)) + 1
    for i in range(len(pts) - 1):
        x0, z0 = pts[i]
        x1, z1 = pts[i + 1]
        xa, xb = min(x0, x1), max(x0, x1)
        za, zb = min(z0, z1), max(z0, z1)
        i0 = max(0, int(math.floor(xa - hw)) - min_x)
        i1 = min(w - 1, int(math.floor(xb + hw)) - min_x)
        j0 = max(0, int(math.floor(za - hw)) - min_z)
        j1 = min(h - 1, int(math.floor(zb + hw)) - min_z)
        if i1 < i0 or j1 < j0:
            continue
        for j in range(j0, j1 + 1):
            cz = min_z + j + 0.5
            for ii in range(i0, i1 + 1):
                cx = min_x + ii + 0.5
                if dist_point_seg(cx, cz, x0, z0, x1, z1) <= hw:
                    grid[j, ii] = mat


def fill_poly(grid: np.ndarray, pts: list[tuple[float, float]], mat: int, min_x: int, min_z: int) -> None:
    if len(pts) < 3:
        return
    poly = np.array(pts, dtype=np.float64)
    if np.allclose(poly[0], poly[-1]):
        poly = poly[:-1]
    if len(poly) < 3:
        return
    h, w = grid.shape
    xa, za = poly[:, 0].min(), poly[:, 1].min()
    xb, zb = poly[:, 0].max(), poly[:, 1].max()
    i0 = max(0, int(math.floor(xa)) - min_x)
    i1 = min(w - 1, int(math.floor(xb)) - min_x)
    j0 = max(0, int(math.floor(za)) - min_z)
    j1 = min(h - 1, int(math.floor(zb)) - min_z)
    for j in range(j0, j1 + 1):
        cz = min_z + j + 0.5
        for ii in range(i0, i1 + 1):
            cx = min_x + ii + 0.5
            if point_in_poly(cx, cz, poly):
                grid[j, ii] = mat


def fill_poly_into(hgt: np.ndarray, mats: np.ndarray, pts, height: int, mat: int, min_x: int, min_z: int) -> int:
    if len(pts) < 3:
        return 0
    poly = np.array(pts, dtype=np.float64)
    if np.allclose(poly[0], poly[-1]):
        poly = poly[:-1]
    if len(poly) < 3:
        return 0
    H, W = hgt.shape
    xa, za = poly[:, 0].min(), poly[:, 1].min()
    xb, zb = poly[:, 0].max(), poly[:, 1].max()
    i0 = max(0, int(math.floor(xa)) - min_x)
    i1 = min(W - 1, int(math.floor(xb)) - min_x)
    j0 = max(0, int(math.floor(za)) - min_z)
    j1 = min(H - 1, int(math.floor(zb)) - min_z)
    n = 0
    height = max(3, min(40, int(height)))
    for j in range(j0, j1 + 1):
        cz = min_z + j + 0.5
        for ii in range(i0, i1 + 1):
            cx = min_x + ii + 0.5
            if point_in_poly(cx, cz, poly):
                hgt[j, ii] = height
                mats[j, ii] = mat
                n += 1
    return n


def greedy_2d(grid: np.ndarray, min_x: int, min_z: int):
    """Merge equal cells into axis-aligned rects. Returns [x, z, w, d, mat] in OSM meters (z north)."""
    H, W = grid.shape
    used = np.zeros_like(grid, dtype=bool)
    rects = []
    for j in range(H):
        i = 0
        while i < W:
            if used[j, i] or grid[j, i] == 0:
                i += 1
                continue
            mat = int(grid[j, i])
            w = 1
            while i + w < W and (not used[j, i + w]) and grid[j, i + w] == mat:
                w += 1
            d = 1
            done = False
            while j + d < H and not done:
                row = grid[j + d, i : i + w]
                urow = used[j + d, i : i + w]
                if np.any(urow) or np.any(row != mat):
                    done = True
                else:
                    d += 1
            used[j : j + d, i : i + w] = True
            rects.append([min_x + i, min_z + j, w, d, mat])
            i += w
    return rects


def greedy_buildings(hgt: np.ndarray, mats: np.ndarray, min_x: int, min_z: int):
    """Merge equal (height, wall-mat) cells. Returns [x, z, w, d, h, mat]."""
    H, W = hgt.shape
    used = np.zeros_like(hgt, dtype=bool)
    boxes = []
    for j in range(H):
        i = 0
        while i < W:
            if used[j, i] or hgt[j, i] == 0:
                i += 1
                continue
            hh = int(hgt[j, i])
            mat = int(mats[j, i])
            w = 1
            while (
                i + w < W
                and (not used[j, i + w])
                and hgt[j, i + w] == hh
                and mats[j, i + w] == mat
            ):
                w += 1
            d = 1
            done = False
            while j + d < H and not done:
                if np.any(used[j + d, i : i + w]) or np.any(hgt[j + d, i : i + w] != hh) or np.any(
                    mats[j + d, i : i + w] != mat
                ):
                    done = True
                else:
                    d += 1
            used[j : j + d, i : i + w] = True
            boxes.append([min_x + i, min_z + j, w, d, hh, mat])
            i += w
    return boxes


def way_points(way, nodes):
    pts = []
    for nid in way.get("nodes") or []:
        ll = nodes.get(nid)
        if ll is None:
            continue
        pts.append(lonlat_to_local(ll[0], ll[1]))
    return pts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root / "data" / "osm-raw.json").read_text())
    els = raw["elements"]
    nodes = {e["id"]: (e["lat"], e["lon"]) for e in els if e.get("type") == "node" and "lat" in e}
    ways = [e for e in els if e.get("type") == "way" and e.get("tags")]

    W = MAX_X - MIN_X
    D = MAX_Z - MIN_Z
    ground = np.full((D, W), G_GRASS, dtype=np.uint8)
    hgt = np.zeros((D, W), dtype=np.uint8)
    wmats = np.zeros((D, W), dtype=np.uint8)

    # landuse / leisure underlay
    for way in ways:
        t = way["tags"]
        pts = way_points(way, nodes)
        if len(pts) < 3:
            continue
        if t.get("leisure") == "park" or t.get("landuse") in ("grass", "village_green", "meadow"):
            fill_poly(ground, pts, G_GRASS, MIN_X, MIN_Z)
        elif t.get("landuse") in ("retail", "commercial"):
            fill_poly(ground, pts, G_PLAZA, MIN_X, MIN_Z)
        elif t.get("landuse") in ("industrial", "railway"):
            fill_poly(ground, pts, G_BALLAST, MIN_X, MIN_Z)
        elif t.get("amenity") == "parking" or t.get("parking"):
            fill_poly(ground, pts, G_PARKING, MIN_X, MIN_Z)

    # roads: paint smaller first so primary/secondary overwrite
    order = ["service", "unclassified", "living_street", "residential", "tertiary", "secondary", "primary"]
    by_type = {k: [] for k in order}
    paths = []
    rails = []
    platforms = []
    named_highways = []
    buildings = []

    for way in ways:
        t = way["tags"]
        pts = way_points(way, nodes)
        if len(pts) < 2:
            continue
        hw = t.get("highway")
        if hw in by_type:
            by_type[hw].append((pts, t))
            if t.get("name"):
                named_highways.append((t["name"], hw, pts))
        elif hw in PATH_WIDTH:
            paths.append((pts, t, hw))
            if t.get("name") and "Pathway" in t["name"]:
                named_highways.append((t["name"], hw, pts))
        if t.get("railway") in ("rail", "light_rail", "tram"):
            rails.append((pts, t))
        if t.get("railway") == "platform" or t.get("highway") == "platform":
            platforms.append((pts, t))
        if t.get("building"):
            buildings.append((pts, t))

    for hw in order:
        width = ROAD_WIDTH[hw]
        for pts, t in by_type[hw]:
            if t.get("width"):
                try:
                    width = float(str(t["width"]).replace("m", "").strip())
                except ValueError:
                    pass
            elif t.get("lanes"):
                try:
                    width = float(str(t["lanes"]).split(";")[0]) * 3.5 + 1.5
                except ValueError:
                    pass
            else:
                width = ROAD_WIDTH[hw]
            stamp_polyline(ground, pts, width * 0.5, G_ASPHALT, MIN_X, MIN_Z)

    # footways / sidewalks / the bike-ped path into town
    for pts, t, hw in paths:
        w = PATH_WIDTH.get(hw, 2.0)
        mat = G_PATH
        if t.get("footway") == "sidewalk" or hw == "footway":
            mat = G_SIDEWALK
        if "Pathway" in (t.get("name") or ""):
            mat = G_PATH
        stamp_polyline(ground, pts, w * 0.5, mat, MIN_X, MIN_Z)

    # rail
    for pts, t in rails:
        stamp_polyline(ground, pts, 2.2, G_BALLAST, MIN_X, MIN_Z)
        stamp_polyline(ground, pts, 0.7, G_RAIL, MIN_X, MIN_Z)

    # platforms as 1 m slabs (also occupancy)
    plat_boxes = 0
    for pts, t in platforms:
        stamp_polyline(ground, pts, 2.0, G_PLATFORM, MIN_X, MIN_Z)
        # raise 1 m
        # stamp into height grid as 1 m (still collidable as a step)
        tmp = np.zeros_like(hgt)
        stamp_polyline(tmp, pts, 2.0, 1, MIN_X, MIN_Z)
        mask = tmp == 1
        hgt[mask] = np.maximum(hgt[mask], 1)
        wmats[mask] = W_LIMESTONE
        plat_boxes += int(mask.sum())

    # buildings
    bcells = 0
    named_buildings = []
    for pts, t in buildings:
        h = parse_height(t, building_default_h(t))
        mat = wall_mat_for(t)
        n = fill_poly_into(hgt, wmats, pts, h, mat, MIN_X, MIN_Z)
        bcells += n
        if t.get("name") and n > 0:
            cx = sum(p[0] for p in pts) / len(pts)
            cz = sum(p[1] for p in pts) / len(pts)
            if MIN_X <= cx < MAX_X and MIN_Z <= cz < MAX_Z:
                named_buildings.append((t["name"], cx, cz, t))

    ground_rects = greedy_2d(ground, MIN_X, MIN_Z)
    build_boxes = greedy_buildings(hgt, wmats, MIN_X, MIN_Z)

    # --- to three.js coords: x east, y up, z south (z = -north) ---
    def flip_ground(r):
        x, z, w, d, mat = r
        # OSM rect [x, x+w) x [z, z+d) north
        # three z = -north, so [-(z+d), -z)
        return [int(x), int(-(z + d)), int(w), int(d), int(mat)]

    def flip_build(b):
        x, z, w, d, h, mat = b
        return [int(x), int(-(z + d)), int(w), int(d), int(h), int(mat)]

    ground_out = [flip_ground(r) for r in ground_rects]
    builds_out = [flip_build(b) for b in build_boxes]

    # spawn: on S Wilson Ave just north of the station building, looking at Center Square
    # Station centroid ~ (2, 2); Wilson ~ (6, 36). Nudge if inside a building cell.
    sx, sz = 4.5, 28.0
    gi = int(sx) - MIN_X
    gj = int(sz) - MIN_Z
    if 0 <= gi < W and 0 <= gj < D and hgt[gj, gi] >= 2:
        sx, sz = -8.0, 22.0
    square = None
    # High ∩ Market from node coords in raw
    for e in els:
        if e.get("type") != "node" or "lat" not in e:
            continue
        # filled later via named ways
    # compute intersection from named ways
    high_ids = set()
    market_ids = set()
    for way in ways:
        n = way["tags"].get("name") or ""
        nds = set(way.get("nodes") or [])
        if "High Street" in n:
            high_ids |= nds
        if "Market Street" in n:
            market_ids |= nds
    inter = high_ids & market_ids
    sq_x, sq_z = 531.0, 514.0
    for nid in inter:
        if nid in nodes:
            sq_x, sq_z = lonlat_to_local(*nodes[nid])
            break
    square = {"x": sq_x, "z": -sq_z, "osmX": sq_x, "osmZ": sq_z}

    dx = sq_x - sx
    dz = sq_z - sz
    yaw = math.atan2(dx, dz)  # three.js yaw: 0 looks -Z = north

    spawn = {
        "x": round(sx, 2),
        "y": 1.7,
        "z": round(-sz, 2),
        "yaw": round(yaw, 4),
    }

    # labels: street names + station + center square
    labels = []
    # station
    labels.append({"x": 2.0, "y": 6.0, "z": -2.0, "text": "ELIZABETHTOWN STATION", "kind": "place"})
    labels.append({"x": 6.0, "y": 3.2, "z": -34.0, "text": "S WILSON AVE", "kind": "street"})
    labels.append({"x": square["x"], "y": 5.5, "z": square["z"], "text": "CENTER SQUARE", "kind": "place"})
    labels.append({"x": square["x"] + 8, "y": 3.2, "z": square["z"] - 14, "text": "MARKET ST", "kind": "street"})
    labels.append({"x": square["x"] - 16, "y": 3.2, "z": square["z"] + 8, "text": "HIGH ST", "kind": "street"})

    # extra street signs at midpoints of named ways, de-duped, inside bounds
    seen = {"south wilson avenue", "west high street", "east high street", "north market street", "south market street"}
    # we already added Wilson / High / Market at the square; still drop a couple along the walk
    along = []
    for name, hw, pts in named_highways:
        if hw in ("footway", "path", "cycleway", "steps", "service"):
            continue
        key = name.strip().lower()
        mid = pts[len(pts) // 2]
        if not (MIN_X + 10 <= mid[0] < MAX_X - 10 and MIN_Z + 10 <= mid[1] < MAX_Z - 10):
            continue
        along.append((key, name, mid[0], mid[1], hw))

    # pick one label per street name, prefer a point not too close to another
    placed = [(lab["x"], -lab["z"]) for lab in labels]
    for key, name, x, z, hw in along:
        if key in seen:
            # still allow a second High / Market along the approach if far from the square
            far = min(math.hypot(x - px, z - pz) for px, pz in placed)
            if far < 90:
                continue
        else:
            far = min((math.hypot(x - px, z - pz) for px, pz in placed), default=999)
            if far < 70:
                continue
        seen.add(key)
        placed.append((x, z))
        short = (
            name.replace("Street", "ST")
            .replace("Avenue", "AVE")
            .replace("Alley", "ALY")
            .upper()
        )
        labels.append({"x": round(x, 1), "y": 3.2, "z": round(-z, 1), "text": short, "kind": "street"})

    # a couple of real OSM shop names right on the square for recognition (not invented)
    for name, cx, cz, t in named_buildings:
        dist = math.hypot(cx - sq_x, cz - sq_z)
        if dist < 55 and name.lower() not in ("municipal parking", "muncipal parking"):
            labels.append(
                {
                    "x": round(cx, 1),
                    "y": 4.0,
                    "z": round(-cz, 1),
                    "text": name.upper()[:28],
                    "kind": "shop",
                }
            )

    bbox_used = {
        "south": ORIGIN_LAT + MIN_Z / M_PER_DEG_LAT,
        "west": ORIGIN_LON + MIN_X / M_PER_DEG_LON,
        "north": ORIGIN_LAT + MAX_Z / M_PER_DEG_LAT,
        "east": ORIGIN_LON + MAX_X / M_PER_DEG_LON,
        "minX": MIN_X,
        "maxX": MAX_X,
        "minZ": MIN_Z,
        "maxZ": MAX_Z,
    }

    has_station = any("amtrak" in (t.get("name") or "").lower() or t.get("building") == "train_station" for _, t in buildings)
    has_high = any("High Street" in n for n, _, _ in named_highways)
    has_market = any("Market Street" in n for n, _, _ in named_highways)
    has_wilson = any("Wilson" in n for n, _, _ in named_highways)


    details_out = []
    # --- Station recognition kit (Collegiate Gothic ELT depot) ---
    # OSM footprint alone is a 9 m flat box. Add gable, chimney, porch,
    # limestone trim bands so spawn reads as THAT station, not gray-on-gray.
    station_details = []
    station_aabb = None
    for pts, t in buildings:
        name = (t.get("name") or "").lower()
        if t.get("building") == "train_station" or "amtrak" in name:
            xs = [p[0] for p in pts]
            zs = [p[1] for p in pts]
            station_aabb = (min(xs), max(xs), min(zs), max(zs))
            break
    if station_aabb:
        xa, xb, za, zb = station_aabb
        # clear generic station cells and rebuild a recognizable massing
        i0 = max(0, int(math.floor(xa)) - MIN_X)
        i1 = min(W - 1, int(math.floor(xb)) - MIN_X)
        j0 = max(0, int(math.floor(za)) - MIN_Z)
        j1 = min(D - 1, int(math.floor(zb)) - MIN_Z)
        for j in range(j0, j1 + 1):
            for ii in range(i0, i1 + 1):
                if wmats[j, ii] == W_LIMESTONE and hgt[j, ii] >= 3:
                    hgt[j, ii] = 0
                    wmats[j, ii] = 0
        # main hall walls ~8 m granite mass (Holmesburg granite + limestone trim)
        # orient: footprint is ~23 m E-W by ~15 m N-S, long axis ~SE-NW
        # place axis-aligned hall covering the footprint
        hall_h = 8
        fill_poly_into(hgt, wmats, [
            (xa + 0.5, za + 0.5), (xb - 0.5, za + 0.5),
            (xb - 0.5, zb - 0.5), (xa + 0.5, zb - 0.5),
            (xa + 0.5, za + 0.5),
        ], hall_h, W_BRICK, MIN_X, MIN_Z)
        # limestone water table / window band (detail boxes, world meters OSM)
        cx = (xa + xb) * 0.5
        cz = (za + zb) * 0.5
        # porch posts + roof on the north (town) face — reads from Wilson
        porch_z0, porch_z1 = zb - 0.2, zb + 3.2
        porch_x0, porch_x1 = cx - 4.0, cx + 4.0
        for px, pz in (
            (porch_x0 + 0.3, porch_z0 + 0.3),
            (porch_x1 - 0.7, porch_z0 + 0.3),
            (porch_x0 + 0.3, porch_z1 - 0.7),
            (porch_x1 - 0.7, porch_z1 - 0.7),
        ):
            station_details.append({
                "kind": "porch_post",
                "x": px, "z": pz,
                "w": 0.35, "d": 0.35,
                "y": 0.0, "h": 3.2, "mat": 17,
            })
        station_details.append({
            "kind": "porch_roof",
            "x": porch_x0 - 0.3, "z": porch_z0 - 0.3,
            "w": (porch_x1 - porch_x0) + 0.6, "d": (porch_z1 - porch_z0) + 0.6,
            "y": 3.2, "h": 0.35, "mat": 18,
        })
        # tall chimney (west end) — signature of the 1915 depot
        ch_x = xa + 1.5
        ch_z = cz - 1.0
        station_details.append({
            "kind": "chimney",
            "x": ch_x, "z": ch_z,
            "w": 1.4, "d": 1.4,
            "y": hall_h, "h": 5.5, "mat": 10,
        })
        # steep gable roof: stepped ridge along long (x) axis
        # ridge runs roughly E-W across the footprint
        for step, rise in enumerate((0, 1, 2, 3, 2, 1, 0)):
            # seven bands N-S
            band_d = (zb - za) / 7.0
            z0 = za + step * band_d
            station_details.append({
                "kind": "gable",
                "x": xa - 0.4, "z": z0,
                "w": (xb - xa) + 0.8, "d": band_d + 0.05,
                "y": hall_h + rise * 0.55, "h": 0.55, "mat": 18,
            })
        # limestone door surround (north face)
        station_details.append({
            "kind": "door",
            "x": cx - 1.1, "z": zb - 0.35,
            "w": 2.2, "d": 0.5,
            "y": 0.0, "h": 3.0, "mat": 19,
        })
        # limestone window trim band
        station_details.append({
            "kind": "band",
            "x": xa - 0.15, "z": za - 0.15,
            "w": (xb - xa) + 0.3, "d": (zb - za) + 0.3,
            "y": 4.2, "h": 0.45, "mat": 19,
        })
        # AMTRAK platform canopy stubs near platforms (north of tracks / south of hall)
        for side, oz in (("n", za - 4.0), ("s", zb + 6.0)):
            station_details.append({
                "kind": "canopy",
                "x": cx - 8.0, "z": oz,
                "w": 16.0, "d": 2.2,
                "y": 3.6, "h": 0.25, "mat": 15,
            })

    # rebuild greedy after station rewrite
    if station_aabb:
        build_boxes = greedy_buildings(hgt, wmats, MIN_X, MIN_Z)
        builds_out = [flip_build(b) for b in build_boxes]

    def flip_detail(d):
        # OSM x east, z north -> three x east, z south
        return {
            "kind": d["kind"],
            "x": round(d["x"], 2),
            "y": round(d["y"], 2),
            "z": round(-(d["z"] + d["d"]), 2),
            "w": round(d["w"], 2),
            "h": round(d["h"], 2),
            "d": round(d["d"], 2),
            "mat": int(d["mat"]),
        }

    details_out = [flip_detail(d) for d in station_details]


    chunk = {
        "meta": {
            "voxelSize": 1,
            "originLat": ORIGIN_LAT,
            "originLon": ORIGIN_LON,
            "projection": "equirectangular-meters",
            "source": "OpenStreetMap via Overpass",
            "license": "ODbL",
            "bbox": bbox_used,
            "queryBbox": raw.get("_etown_meta", {}).get("bbox"),
            "stationInMesh": has_station,
            "highMarketInMesh": bool(inter) and has_high and has_market,
            "wilsonInMesh": has_wilson,
            "centerSquareLocal": {"x": round(sq_x, 2), "zNorth": round(sq_z, 2)},
            "groundRects": len(ground_out),
            "buildingBoxes": len(builds_out),
            "buildingCells": int(bcells),
            "platformCells": plat_boxes,
        },
        "spawn": spawn,
        "square": square,
        "ground": ground_out,
        "buildings": builds_out,
        "labels": labels,
        "details": details_out,
        "bounds": {
            "minX": MIN_X,
            "maxX": MAX_X,
            "minZ": int(-MAX_Z),
            "maxZ": int(-MIN_Z),
        },
    }

    out = root / "data" / "chunk.json"
    out.write_text(json.dumps(chunk, separators=(",", ":")), encoding="utf-8")
    print("wrote", out, "bytes", out.stat().st_size)
    print("ground rects", len(ground_out), "building boxes", len(builds_out), "cells", bcells)
    print("station", has_station, "high", has_high, "market", has_market, "wilson", has_wilson)
    print("square", square, "spawn", spawn)
    print("labels", len(labels))
    print("details", len(details_out))
    print("bbox", bbox_used)


if __name__ == "__main__":
    main()
