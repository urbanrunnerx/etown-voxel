#!/usr/bin/env python3
"""Quick isometric of the Amtrak station slice from baked 1m voxels."""
import json
from PIL import Image, ImageDraw, ImageFont

d = json.load(open("/workspace/etown-voxel/data/chunk.json"))
GROUND = {
  1: (79, 138, 58), 2: (61, 61, 66), 3: (198, 193, 180), 4: (110, 90, 69),
  5: (69, 69, 76), 6: (31, 31, 36), 7: (106, 101, 96), 8: (185, 179, 166), 9: (138, 138, 122),
}
WALL = {
  10: (138, 78, 60), 11: (163, 90, 69), 12: (213, 207, 192), 13: (196, 180, 154),
  14: (107, 90, 72), 15: (122, 122, 130), 16: (207, 198, 184), 17: (139, 105, 20),
}

X0, X1, Z0, Z1 = -80, 90, -90, 50
W, H = 1280, 800
img = Image.new("RGB", (W, H), (135, 182, 217))
px = img.load()
for y in range(H):
    t = y / H
    r = int(135 + 25 * t)
    g = int(182 + 10 * t)
    b = int(217 - 40 * t)
    for x in range(W):
        px[x, y] = (r, g, min(255, b))

def shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)

def project(x, y, z):
    dx, dz = x - 8, z + 8
    sx = 640 + dx * 4.2 - dz * 2.6
    sy = 430 - y * 4.0 - dz * 2.4 - dx * 0.9
    return sx, sy

draw = ImageDraw.Draw(img)

for gx in range(X0, X1, 10):
    for gz in range(Z0, Z1, 10):
        pts = [project(gx, 0, gz), project(gx + 10, 0, gz), project(gx + 10, 0, gz + 10), project(gx, 0, gz + 10)]
        draw.polygon(pts, fill=(72, 118, 52))

for g in d["ground"]:
    x, z, w, dpth, mat = g
    cx, cz = x + w * 0.5, z + dpth * 0.5
    if cx < X0 or cx > X1 or cz < Z0 or cz > Z1:
        continue
    col = GROUND.get(mat, (90, 90, 90))
    foot = [(x, z), (x + w, z), (x + w, z + dpth), (x, z + dpth)]
    pts = [project(px_, 0.05, pz) for px_, pz in foot]
    draw.polygon(pts, fill=col)

bld = []
for b in d["buildings"]:
    x, z, w, dpth, h, mat = b
    cx, cz = x + w * 0.5, z + dpth * 0.5
    if cx < X0 or cx > X1 or cz < Z0 or cz > Z1:
        continue
    bld.append((cz + cx * 0.2, b))
bld.sort()
for _, b in bld:
    x, z, w, dpth, h, mat = b
    col = WALL.get(mat, (140, 140, 140))
    c1 = shade(col, 0.55)
    pts = [project(x + w, 0, z), project(x + w, 0, z + dpth), project(x + w, h, z + dpth), project(x + w, h, z)]
    draw.polygon(pts, fill=c1)
    c2 = shade(col, 0.78)
    pts = [project(x, 0, z + dpth), project(x + w, 0, z + dpth), project(x + w, h, z + dpth), project(x, h, z + dpth)]
    draw.polygon(pts, fill=c2)
    roof = shade((74, 58, 54), 0.95)
    pts = [project(x, h, z), project(x + w, h, z), project(x + w, h, z + dpth), project(x, h, z + dpth)]
    draw.polygon(pts, fill=roof)

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    font2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
except Exception:
    font = font2 = ImageFont.load_default()

for lab in d["labels"]:
    if lab["x"] < X0 or lab["x"] > X1 or lab["z"] < Z0 or lab["z"] > Z1:
        continue
    sx, sy = project(lab["x"], lab["y"], lab["z"])
    text = lab["text"]
    fnt = font if lab["kind"] == "place" else font2
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x0, y0 = sx - tw / 2, sy - th - 10
    draw.rectangle([x0 - 8, y0 - 4, x0 + tw + 8, y0 + th + 4], fill=(20, 22, 28))
    draw.text((x0, y0), text, font=fnt, fill=(244, 239, 224))

cap = "WIP — Elizabethtown Amtrak  ·  1 m OSM voxels  ·  not done"
draw.rectangle([0, H - 48, W, H], fill=(18, 22, 28))
draw.text((24, H - 34), cap, font=font2, fill=(220, 210, 190))

out = "/workspace/etown-voxel/shots/station-wip.png"
img.save(out, "PNG")
print("wrote", out, img.size)
