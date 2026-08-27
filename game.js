import * as THREE from "three";
import { PointerLockControls } from "three/addons/controls/PointerLockControls.js";

const GROUND = {
  1: 0x1a1814, // grass — dusk
  2: 0x3a3732, // asphalt
  3: 0x5c564c, // sidewalk
  4: 0x2c281f, // path
  5: 0x262420, // parking
  6: 0x8b9096, // rail
  7: 0x2c281f, // ballast
  8: 0x3a3732, // platform
  9: 0x6a6048, // plaza
};
const WALL = {
  10: 0x2c221c, // dark brick mass (depot)
  11: 0x32261e, // brick2
  12: 0x3a3732, // limestone / platform slab
  13: 0x241e18, // house mass
  14: 0x1c1a16, // shed
  15: 0x1a1816, // industrial
  16: 0x2a261f, // church
  17: 0x2a2218, // timber
  18: 0x141214, // slate
  19: 0x4a453c, // trim
};
const ROOF = 0x141214;
const DETAIL = WALL;

const overlay = document.getElementById("overlay");
const params = new URLSearchParams(location.search);
const view = params.get("view"); // spawn | square | path — screenshot cameras

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.setClearColor(0x0c1018, 1);
renderer.shadowMap.enabled = false;
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0c1018);
scene.fog = new THREE.FogExp2(0x121722, 0.00115);

const camera = new THREE.PerspectiveCamera(64, innerWidth / innerHeight, 0.12, 900);
const controls = new PointerLockControls(camera, document.body);

const skyGeo = new THREE.SphereGeometry(1600, 32, 16);
const skyMat = new THREE.ShaderMaterial({
  side: THREE.BackSide,
  depthWrite: false,
  fog: false,
  vertexShader: "varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
  fragmentShader: [
    "varying vec3 vP;",
    "void main(){",
    "  vec3 n = normalize(vP); float h = n.y;",
    "  vec3 zenith = vec3(0.04, 0.055, 0.09);",
    "  vec3 mid    = vec3(0.10, 0.13, 0.20);",
    "  vec3 horz   = vec3(0.72, 0.42, 0.28);",
    "  vec3 below  = vec3(0.08, 0.07, 0.07);",
    "  vec3 col = mix(mid, zenith, smoothstep(0.0, 0.75, h));",
    "  col = mix(horz, col, smoothstep(-0.05, 0.18, h));",
    "  col = mix(below, col, smoothstep(-0.25, 0.02, h));",
    "  float west = smoothstep(0.15, 0.8, -n.x) * (1.0 - abs(h));",
    "  col += vec3(0.18, 0.07, 0.02) * west * 0.45;",
    "  gl_FragColor = vec4(col, 1.0);",
    "}",
  ].join("\n"),
});
scene.add(new THREE.Mesh(skyGeo, skyMat));

scene.add(new THREE.HemisphereLight(0x6a7a99, 0x1a1612, 0.85));
const sun = new THREE.DirectionalLight(0xffb07a, 1.15);
sun.position.set(-400, 180, 120);
scene.add(sun);
const moon = new THREE.DirectionalLight(0x8aa0c4, 0.22);
moon.position.set(200, 300, -100);
scene.add(moon);
const stationLamp = new THREE.PointLight(0xffc27a, 1.4, 70, 2.0);
stationLamp.position.set(0, 8, 8);
scene.add(stationLamp);
const squareLamp = new THREE.PointLight(0xe8d0a0, 1.6, 90, 2.0);
squareLamp.position.set(531, 11, -514);
scene.add(squareLamp);

const unit = new THREE.BoxGeometry(1, 1, 1);
const meshes = [];

function instanced(color, count, roughness = 0.92, metalness = 0.02) {
  if (count <= 0) return null;
  const mat = new THREE.MeshLambertMaterial({ color });
  const mesh = new THREE.InstancedMesh(unit, mat, count);
  mesh.frustumCulled = true;
  scene.add(mesh);
  meshes.push(mesh);
  return mesh;
}

const duskVert = [
  "varying vec3 vWPos;",
  "varying vec3 vN;",
  "varying vec3 vView;",
  "void main(){",
  "  vec4 wp = modelMatrix * instanceMatrix * vec4(position, 1.0);",
  "  vWPos = wp.xyz;",
  "  vN = normalize(mat3(modelMatrix) * mat3(instanceMatrix) * normal);",
  "  vView = cameraPosition - wp.xyz;",
  "  gl_Position = projectionMatrix * viewMatrix * wp;",
  "}",
].join("\n");
const duskFrag = [
  "uniform vec3 uColor;",
  "uniform float uLit;",
  "varying vec3 vWPos;",
  "varying vec3 vN;",
  "varying vec3 vView;",
  "void main(){",
  "  vec3 N = normalize(vN);",
  "  vec3 V = normalize(vView);",
  "  float up = N.y;",
  "  vec3 wall = uColor;",
  "  vec3 roof = uColor * 0.32;",
  "  float fu = mix(fract(vWPos.x * 0.52), fract(vWPos.z * 0.52), step(abs(N.x), abs(N.z)));",
  "  float wy = fract(vWPos.y * 0.46 + 0.08);",
  "  float windowPane = step(0.40, fu) * step(0.34, wy);",
  "  windowPane *= step(1.2, vWPos.y);",
  "  windowPane *= 1.0 - smoothstep(0.42, 0.72, abs(up));",
  "  float id = floor(vWPos.x * 0.52) + floor(vWPos.y * 0.46) * 17.0 + floor(vWPos.z * 0.52) * 9.0;",
  "  float hash = fract(sin(id * 127.13) * 43758.5453);",
  "  float occupied = step(0.38, hash) * uLit;",
  "  vec3 winCol = mix(vec3(0.06, 0.07, 0.09), vec3(1.0, 0.70, 0.36), occupied);",
  "  vec3 base = mix(wall, roof, smoothstep(0.55, 0.88, up));",
  "  base = mix(base, winCol, windowPane);",
  "  vec3 L = normalize(vec3(-0.62, 0.38, 0.28));",
  "  float ndl = max(dot(N, L), 0.0);",
  "  vec3 hemi = mix(vec3(0.16, 0.13, 0.11), vec3(0.32, 0.36, 0.44), N.y * 0.5 + 0.5);",
  "  vec3 col = base * (hemi + vec3(1.0, 0.72, 0.48) * ndl * 0.62 + vec3(0.16, 0.20, 0.28) * 0.28);",
  "  col += winCol * windowPane * occupied * 0.9;",
  "  float rim = pow(1.0 - max(dot(N, V), 0.0), 2.8) * 0.14;",
  "  col += vec3(0.65, 0.42, 0.28) * rim * (1.0 - abs(up));",
  "  gl_FragColor = vec4(col, 1.0);",
  "}",
].join("\n");

function instancedDusk(color, count, lit) {
  if (count <= 0) return null;
  const c = new THREE.Color(color);
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Vector3(c.r, c.g, c.b) },
      uLit: { value: lit },
    },
    vertexShader: duskVert,
    fragmentShader: duskFrag,
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
    const tall = list.filter((b) => b[4] > 1);
    const low = list.filter((b) => b[4] <= 1);
    if (low.length) {
      const mesh = instanced(WALL[matId] || 0x333333, low.length);
      low.forEach((b, i) => {
        const h = b[4];
        const x = b[0] + b[2] * 0.5;
        const z = b[1] + b[3] * 0.5;
        put(mesh, i, x, h * 0.5, z, b[2], h, b[3]);
      });
      mesh.instanceMatrix.needsUpdate = true;
    }
    if (tall.length) {
      const lit = matId === 10 ? 0.4 : 0.85;
      const mesh = instancedDusk(WALL[matId] || 0x241e18, tall.length, lit);
      tall.forEach((b, i) => {
        const h = b[4];
        const x = b[0] + b[2] * 0.5;
        const z = b[1] + b[3] * 0.5;
        put(mesh, i, x, h * 0.5, z, b[2], h, b[3]);
      });
      mesh.instanceMatrix.needsUpdate = true;
    }
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
  if (name === "station") {
    camera.position.set(10, 2.6, 34);
    camera.lookAt(0, 5.0, 5);
  } else if (name === "spawn") {
    camera.position.set(st.x, 1.7, st.z);
    camera.lookAt(st.x + 28, 2.2, st.z - 36);
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
