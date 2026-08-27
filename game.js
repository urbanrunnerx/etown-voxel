import * as THREE from "three";
import { PointerLockControls } from "three/addons/controls/PointerLockControls.js";

const GROUND = {
  1: 0x4f8a3a, // grass
  2: 0x3d3d42, // asphalt
  3: 0xc6c1b4, // sidewalk
  4: 0x6e5a45, // path (bike/ped)
  5: 0x45454c, // parking
  6: 0x1f1f24, // rail
  7: 0x6a6560, // ballast
  8: 0xb9b3a6, // platform
  9: 0x8a8a7a, // plaza
};
const WALL = {
  10: 0x8a4e3c, // brick (ELT depot + downtown)
  11: 0xa35a45, // brick2
  12: 0xd5cfc0, // limestone
  13: 0xc4b49a, // house
  14: 0x6b5a48, // shed
  15: 0x7a7a82, // industrial / metal
  16: 0xcfc6b8, // church
  17: 0x5c4020, // heavy timber
  18: 0x2e2a2c, // slate
  19: 0xe8e0d0, // Indiana limestone trim
};
const ROOF = 0x4a3a36;
const DETAIL = WALL;

const overlay = document.getElementById("overlay");
const params = new URLSearchParams(location.search);
const view = params.get("view"); // spawn | square | path — screenshot cameras

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.setClearColor(0x87b6d9, 1);
renderer.shadowMap.enabled = false;
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87b6d9);
scene.fog = new THREE.Fog(0x9ec4e0, 140, 720);

const camera = new THREE.PerspectiveCamera(72, innerWidth / innerHeight, 0.12, 900);
const controls = new PointerLockControls(camera, document.body);

const hemi = new THREE.HemisphereLight(0xd7e8ff, 0x4a5a32, 1.05);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff3d0, 1.15);
sun.position.set(-80, 140, 40);
scene.add(sun);
scene.add(new THREE.AmbientLight(0xffffff, 0.18));

const unit = new THREE.BoxGeometry(1, 1, 1);
const meshes = [];

function instanced(color, count, roughness = 0.92, metalness = 0.02) {
  if (count <= 0) return null;
  const mat = new THREE.MeshStandardMaterial({
    color,
    roughness,
    metalness,
    vertexColors: false,
  });
  const mesh = new THREE.InstancedMesh(unit, mat, count);
  mesh.frustumCulled = true;
  scene.add(mesh);
  meshes.push(mesh);
  return mesh;
}

const dummy = new THREE.Object3D();
function put(mesh, i, x, y, z, sx, sy, sz) {
  dummy.position.set(x, y, z);
  dummy.scale.set(sx, sy, sz);
  dummy.rotation.set(0, 0, 0);
  dummy.updateMatrix();
  mesh.setMatrixAt(i, dummy.matrix);
}

const keys = Object.create(null);
const vel = new THREE.Vector3();
let onGround = true;
let chunk = null;
let bins = new Map();
let lowBoxes = [];
let bounds = null;

const BIN = 16;
function bkey(ix, iz) {
  return (ix << 16) ^ (iz & 0xffff);
}
function binInsert(box) {
  const x0 = box[0], z0 = box[1], x1 = box[0] + box[2], z1 = box[1] + box[3];
  const i0 = Math.floor(x0 / BIN), i1 = Math.floor((x1 - 0.001) / BIN);
  const k0 = Math.floor(z0 / BIN), k1 = Math.floor((z1 - 0.001) / BIN);
  for (let iz = k0; iz <= k1; iz++) {
    for (let ix = i0; ix <= i1; ix++) {
      const k = bkey(ix, iz);
      let arr = bins.get(k);
      if (!arr) {
        arr = [];
        bins.set(k, arr);
      }
      arr.push(box);
    }
  }
}
function queryBoxes(px, pz) {
  const ix = Math.floor(px / BIN);
  const iz = Math.floor(pz / BIN);
  const out = [];
  const seen = new Set();
  for (let dz = -1; dz <= 1; dz++) {
    for (let dx = -1; dx <= 1; dx++) {
      const arr = bins.get(bkey(ix + dx, iz + dz));
      if (!arr) continue;
      for (const b of arr) {
        if (seen.has(b)) continue;
        seen.add(b);
        out.push(b);
      }
    }
  }
  return out;
}

function groundY(px, pz) {
  let y = 0;
  for (const b of lowBoxes) {
    if (px >= b[0] && px <= b[0] + b[2] && pz >= b[1] && pz <= b[1] + b[3]) {
      y = Math.max(y, b[4]);
    }
  }
  return y;
}

function collide(px, py, pz, radius, height) {
  const feet = py - height;
  let nx = px, nz = pz;
  const nearby = queryBoxes(px, pz);
  for (let pass = 0; pass < 2; pass++) {
    for (const b of nearby) {
      const top = b[4];
      if (feet >= top - 0.02) continue; // standing on / above
      if (py < 0.05) continue;
      const minX = b[0], maxX = b[0] + b[2];
      const minZ = b[1], maxZ = b[1] + b[3];
      const pminx = nx - radius, pmaxx = nx + radius;
      const pminz = nz - radius, pmaxz = nz + radius;
      if (pmaxx <= minX || pminx >= maxX || pmaxz <= minZ || pminz >= maxZ) continue;
      const overlapX = Math.min(pmaxx - minX, maxX - pminx);
      const overlapZ = Math.min(pmaxz - minZ, maxZ - pminz);
      if (overlapX < overlapZ) {
        if (nx < (minX + maxX) * 0.5) nx -= overlapX;
        else nx += overlapX;
      } else {
        if (nz < (minZ + maxZ) * 0.5) nz -= overlapZ;
        else nz += overlapZ;
      }
    }
  }
  return { x: nx, z: nz };
}

function makeSignTexture(text, kind) {
  const c = document.createElement("canvas");
  const ctx = c.getContext("2d");
  const pad = 18;
  ctx.font = kind === "place" ? "bold 42px Georgia, serif" : kind === "shop" ? "600 28px Georgia, serif" : "bold 32px Georgia, serif";
  const tw = Math.ceil(ctx.measureText(text).width);
  c.width = Math.min(1024, tw + pad * 2);
  c.height = kind === "place" ? 88 : 64;
  ctx.font = kind === "place" ? "bold 42px Georgia, serif" : kind === "shop" ? "600 28px Georgia, serif" : "bold 32px Georgia, serif";
  if (kind === "street") {
    ctx.fillStyle = "#2e4a32";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.strokeStyle = "#e8e0c8";
    ctx.lineWidth = 4;
    ctx.strokeRect(3, 3, c.width - 6, c.height - 6);
    ctx.fillStyle = "#f4efe0";
  } else if (kind === "place") {
    ctx.fillStyle = "#3a2a1c";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.fillStyle = "#f0e6c8";
  } else {
    ctx.fillStyle = "rgba(28,24,20,0.72)";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.fillStyle = "#f6f1e4";
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, c.width / 2, c.height / 2 + 1);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  tex.colorSpace = THREE.SRGBColorSpace;
  return { tex, aspect: c.width / c.height };
}


function addDetails(details) {
  if (!details || !details.length) return;
  const by = new Map();
  for (const d of details) {
    if (!by.has(d.mat)) by.set(d.mat, []);
    by.get(d.mat).push(d);
  }
  for (const [matId, list] of by) {
    const color = DETAIL[matId] || 0x888888;
    const rough = matId === 18 ? 0.98 : matId === 19 ? 0.72 : 0.88;
    const metal = matId === 15 ? 0.55 : 0.03;
    const mesh = instanced(color, list.length, rough, metal);
    list.forEach((d, i) => {
      put(mesh, i, d.x + d.w * 0.5, d.y + d.h * 0.5, d.z + d.d * 0.5, d.w, d.h, d.d);
    });
    if (mesh) mesh.instanceMatrix.needsUpdate = true;
  }
}

function addLabels(labels) {
  const postMat = new THREE.MeshStandardMaterial({ color: 0x3a2c22, roughness: 0.9 });
  const postGeo = new THREE.BoxGeometry(0.12, 2.8, 0.12);
  for (const lab of labels) {
    const { tex, aspect } = makeSignTexture(lab.text, lab.kind);
    const h = lab.kind === "place" ? 2.2 : lab.kind === "shop" ? 0.85 : 1.15;
    const w = h * aspect;
    const mat = new THREE.MeshBasicMaterial({
      map: tex,
      transparent: true,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const board = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
    board.position.set(lab.x, lab.y, lab.z);
    scene.add(board);
    board.userData.billboard = true;

    if (lab.kind === "street") {
      const post = new THREE.Mesh(postGeo, postMat);
      post.position.set(lab.x, 1.4, lab.z);
      scene.add(post);
    }
  }
}

async function loadWorld() {
  const res = await fetch("./data/chunk.json");
  chunk = await res.json();
  bounds = chunk.bounds;

  const groundBy = new Map();
  for (const g of chunk.ground) {
    const mat = g[4];
    if (!groundBy.has(mat)) groundBy.set(mat, []);
    groundBy.get(mat).push(g);
  }
  for (const [matId, list] of groundBy) {
    const mesh = instanced(GROUND[matId] || 0x666666, list.length, 0.95, matId === 6 ? 0.4 : 0.02);
    list.forEach((g, i) => {
      const x = g[0] + g[2] * 0.5;
      const z = g[1] + g[3] * 0.5;
      put(mesh, i, x, -0.5, z, g[2], 1, g[3]);
    });
    mesh.instanceMatrix.needsUpdate = true;
  }

  const wallBy = new Map();
  const roofs = [];
  for (const b of chunk.buildings) {
    const h = b[4];
    const mat = b[5];
    if (h <= 1) {
      lowBoxes.push(b);
      // still draw as a 1 m slab (platforms)
      if (!wallBy.has(mat)) wallBy.set(mat, []);
      wallBy.get(mat).push(b);
      continue;
    }
    if (!wallBy.has(mat)) wallBy.set(mat, []);
    wallBy.get(mat).push(b);
    if (mat !== 10) roofs.push(b); // depot brick gable is the roof (any hall height)
    binInsert(b);
  }
  for (const [matId, list] of wallBy) {
    const mesh = instanced(WALL[matId] || 0x888888, list.length, 0.88, 0.04);
    list.forEach((b, i) => {
      const h = b[4];
      const x = b[0] + b[2] * 0.5;
      const z = b[1] + b[3] * 0.5;
      put(mesh, i, x, h * 0.5, z, b[2], h, b[3]);
    });
    mesh.instanceMatrix.needsUpdate = true;
  }
  const roofMesh = instanced(ROOF, roofs.length, 0.96, 0.0);
  roofs.forEach((b, i) => {
    const h = b[4];
    const x = b[0] + b[2] * 0.5;
    const z = b[1] + b[3] * 0.5;
    put(roofMesh, i, x, h + 0.12, z, b[2] + 0.12, 0.24, b[3] + 0.12);
  });
  if (roofMesh) roofMesh.instanceMatrix.needsUpdate = true;

  addLabels(chunk.labels || []);
  addDetails(chunk.details || []);

  const sp = chunk.spawn;
  camera.position.set(sp.x, sp.y, sp.z);
  camera.rotation.order = "YXZ";
  // PointerLockControls reads the camera; set yaw by looking
  camera.rotation.set(0, sp.yaw, 0);

  if (view) applyView(view);
  requestAnimationFrame(() => {
    renderer.render(scene, camera);
    window.__ETOWN_READY = true;
  });
}

function applyView(name) {
  overlay.classList.add("hidden");
  const sq = chunk.square;
  const st = chunk.spawn;
  if (name === "spawn") {
    // south of the limestone station, rails/platforms in the foreground
    camera.position.set(16, 5.8, 18);
    camera.lookAt(1, 5.2, -2);
  } else if (name === "square") {
    camera.position.set(sq.x - 22, 12, sq.z + 40);
    camera.lookAt(sq.x, 3.5, sq.z);
  } else if (name === "path") {
    camera.position.set(st.x, 3.2, st.z);
    camera.lookAt(sq.x, 6, sq.z);
  }
}

overlay.addEventListener("click", () => {
  if (view) return;
  controls.lock();
});
controls.addEventListener("lock", () => overlay.classList.add("hidden"));
controls.addEventListener("unlock", () => overlay.classList.remove("hidden"));

addEventListener("keydown", (e) => {
  keys[e.code] = true;
  if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) e.preventDefault();
});
addEventListener("keyup", (e) => {
  keys[e.code] = false;
});
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

const clock = new THREE.Clock();
const forward = new THREE.Vector3();
const right = new THREE.Vector3();
const up = new THREE.Vector3(0, 1, 0);

function playerEye() {
  return 1.7;
}

function tick() {
  requestAnimationFrame(tick);
  const dt = Math.min(0.05, clock.getDelta());

  for (const obj of scene.children) {
    if (obj.userData && obj.userData.billboard) {
      obj.quaternion.copy(camera.quaternion);
    }
  }

  if (!view && controls.isLocked && chunk) {
    const sprint = keys.ShiftLeft || keys.ShiftRight;
    const speed = sprint ? 6.4 : 3.7;
    forward.set(0, 0, -1).applyQuaternion(camera.quaternion);
    forward.y = 0;
    if (forward.lengthSq() < 1e-6) forward.set(0, 0, -1);
    forward.normalize();
    right.crossVectors(forward, up).normalize();

    let mx = 0, mz = 0;
    if (keys.KeyW || keys.ArrowUp) {
      mx += forward.x;
      mz += forward.z;
    }
    if (keys.KeyS || keys.ArrowDown) {
      mx -= forward.x;
      mz -= forward.z;
    }
    if (keys.KeyD || keys.ArrowRight) {
      mx += right.x;
      mz += right.z;
    }
    if (keys.KeyA || keys.ArrowLeft) {
      mx -= right.x;
      mz -= right.z;
    }
    const mag = Math.hypot(mx, mz);
    if (mag > 0) {
      mx = (mx / mag) * speed * dt;
      mz = (mz / mag) * speed * dt;
    }

    if ((keys.Space || keys.KeyJ) && onGround) {
      vel.y = 7.4;
      onGround = false;
    }
    vel.y -= 22 * dt;

    let px = camera.position.x + mx;
    let pz = camera.position.z + mz;
    let py = camera.position.y + vel.y * dt;

    const gy = groundY(px, pz);
    const eye = playerEye();
    const feet = py - eye;
    if (feet <= gy) {
      py = gy + eye;
      vel.y = 0;
      onGround = true;
    } else {
      onGround = false;
    }

    const hit = collide(px, py, pz, 0.28, eye);
    px = hit.x;
    pz = hit.z;

    if (bounds) {
      px = Math.min(bounds.maxX - 1.2, Math.max(bounds.minX + 1.2, px));
      pz = Math.min(bounds.maxZ - 1.2, Math.max(bounds.minZ + 1.2, pz));
    }
    camera.position.set(px, py, pz);
  }

  renderer.render(scene, camera);
}

loadWorld()
  .then(() => {
    tick();
    if (view) {
      document.getElementById("hud").textContent =
        view === "square" ? "Center Square — High & Market" : "Elizabethtown station — S Wilson Ave";
    }
  })
  .catch((err) => {
    overlay.querySelector(".hint").textContent = "Failed to load slice: " + err.message;
  });
