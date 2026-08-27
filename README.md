# Etown Voxel

First slice of a 1-meter voxel walk of downtown **Elizabethtown, Pennsylvania**. Separate from The Equation and Mara. No Google Maps tiles.

You spawn at the **Amtrak station** (50 S Wilson Ave) and walk the real path into **Center Square** (High Street & Market Street).

**SPAWN TEST:** the depot is a brick mass with slate gable, chimney, porch posts, limestone trim, rails/platforms, and a **S WILSON AVE** sign — not a gray box on a gray strip. (The real 1915 ELT is Holmesburg granite; this slice uses brick for immediate recognition per the brief.)

**Play:** [https://urbanrunnerx.github.io/etown-voxel/](https://urbanrunnerx.github.io/etown-voxel/)

## How to walk the path

1. Click to capture the mouse (pointer lock).
2. You are on South Wilson Avenue, just north of the limestone station building. Rails and platforms sit behind it.
3. Look northeast. Follow **S Wilson Ave** and the **Elizabethtown Bike and Pedestrian Pathway** (tan path voxels) toward town.
4. Streets are asphalt-width from OSM highway type. Green street signs name the roads.
5. Center Square is the intersection of **High St** and **Market St** (~530 m east, ~514 m north of the station). A **CENTER SQUARE** sign sits on the diamond.
6. First ten minutes: stay on that walk. There is no shop, hunger, loot, or combat in this slice.

Controls: `WASD` or arrows, mouse look, `space` jump, `shift` to move faster. Collide with buildings; stay on the ground.

Local: any static server from this folder (ES modules + `fetch` of `data/chunk.json`).

```bash
python3 -m http.server 8080
# open http://localhost:8080/
```

No CDN at play time. `vendor/three.module.js` is vendored.

## Data (not Google)

World is **OpenStreetMap** building footprints, highways, railway, parking, and the named bike/ped path.

- Heights: OSM `building:levels` × 3 m, or `height` tag, else a type default (~8 m).
- Roads: ~6–12 m wide from `highway` type / `lanes`. Sidewalks and the pathway if tagged.
- Rail and Amtrak platforms at the station.
- Nothing is invented: names and footprints come from OSM. Shop labels near the square are OSM `name` tags.

Baked into `data/chunk.json` so play does not hit Overpass. Source dump: `data/osm-raw.json`.

```bash
python3 scripts/fetch_osm.py   # Overpass, needs network
python3 scripts/bake.py        # 1 m voxels, greedy-mesh boxes
```

Projection: equirectangular meters, origin at the station `40.146889, -76.61222`.

Slice bbox (WGS84, bake clip):

- south `40.14617` west `-76.61340` north `40.15228` east `-76.60493`
- local meters from station: x east `[-100, 620]`, z north `[-80, 600]` (~720 × 680 m)

Query bbox in `scripts/fetch_osm.py` is slightly padded so long ways (High, Market, Keystone Corridor) still contribute geometry.

© OpenStreetMap contributors. [ODbL](https://www.openstreetmap.org/copyright). This is not Google, and it does not use Google tiles or Street View.

## Stack

Vanilla HTML + vendored three.js r170. First-person `PointerLockControls`. InstancedMesh boxes (greedy-merged 1 m columns). Daylight sky + fog.

Survival loop comes after the slice is recognizable.
