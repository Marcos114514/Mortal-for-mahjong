// mahjong3d.js — Three.js 3D mahjong table renderer
// High-res tiles built from FluffyStuff SVG faces composited onto a white tile body.
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

const TILES_DIR = "/tiles";

// Tile geometry proportions (real tile ≈ 26W × 34H × 19D mm)
export const TW = 0.72; // width  (x)
export const TH = 0.96; // height (y) — the printed face long dimension
export const TD = 0.52; // depth  (z) — thickness

const SUITS = ["m", "p", "s"];
const HONORS = ["E", "S", "W", "N", "P", "F", "C"];
const FACE_FILE = {
  E: "Ton", S: "Nan", W: "Shaa", N: "Pei",
  P: "Haku", F: "Hatsu", C: "Chun",
};

function symbolFile(tile) {
  if (HONORS.includes(tile)) return FACE_FILE[tile];
  const suit = { m: "Man", p: "Pin", s: "Sou" }[tile[1]];
  return `${suit}${tile[0]}`;
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

// Composite Front.svg (white body) + symbol SVG into a high-res CanvasTexture
function compositeTexture(frontImg, symbolImg, renderer) {
  const S = 512; // high-res
  const c = document.createElement("canvas");
  c.width = S;
  c.height = Math.round(S * (TH / TW));
  const ctx = c.getContext("2d");
  ctx.drawImage(frontImg, 0, 0, c.width, c.height);
  if (symbolImg) ctx.drawImage(symbolImg, 0, 0, c.width, c.height);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  tex.needsUpdate = true;
  return tex;
}

// Build all textures we need; returns { faces: Map<tileId, Texture>, back, side }
export async function buildTextures(renderer) {
  const allTiles = [];
  for (const s of SUITS) for (let r = 1; r <= 9; r++) allTiles.push(`${r}${s}`);
  for (const h of HONORS) allTiles.push(h);

  const [frontImg, backImg] = await Promise.all([
    loadImage(`${TILES_DIR}/Front.svg`),
    loadImage(`${TILES_DIR}/Back.svg`),
  ]);

  const uniqueSymbols = [...new Set(allTiles.map(symbolFile))];
  const symbolImgs = {};
  await Promise.all(
    uniqueSymbols.map(async (name) => {
      symbolImgs[name] = await loadImage(`${TILES_DIR}/${name}.svg`);
    }),
  );

  const faces = new Map();
  for (const tile of allTiles) {
    faces.set(tile, compositeTexture(frontImg, symbolImgs[symbolFile(tile)], renderer));
  }

  // Back texture (green tile back) — composite onto a tinted body
  const backTex = compositeTexture(frontImg, backImg, renderer);

  return { faces, back: backTex };
}

// Materials for the tile body (ivory, glossy with env reflection)
export function makeSideMaterials(envMap) {
  return new THREE.MeshStandardMaterial({
    color: 0xf6efe0,
    roughness: 0.55,
    metalness: 0.0,
    envMap: envMap || null,
    envMapIntensity: 0.35,
  });
}

// Shared rounded geometries (cached per orientation)
let _standGeo = null;
let _decalGeo = null;

function standGeo() {
  if (!_standGeo) _standGeo = new RoundedBoxGeometry(TW, TH, TD, 4, Math.min(TW, TD) * 0.16);
  return _standGeo;
}

// Build a tile as a Group: rounded ivory body + face decal (+z) + back decal (-z).
// showFace=false → front shows the green back instead of the symbol.
export function makeTile(faceTex, backTex, bodyMat, showFace = true) {
  const group = new THREE.Group();

  const body = new THREE.Mesh(standGeo(), bodyMat);
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);

  // face decal slightly inset within rounded edges, raised just above the surface
  const fw = TW * 0.9, fh = TH * 0.9;
  const decalGeo = new THREE.PlaneGeometry(fw, fh);

  const frontTex = showFace ? faceTex : backTex;
  const frontMat = new THREE.MeshStandardMaterial({
    map: frontTex, roughness: 0.4, metalness: 0.0, transparent: true,
  });
  const front = new THREE.Mesh(decalGeo, frontMat);
  front.position.set(0, 0, TD / 2 + 0.002);
  group.add(front);

  const backMat = new THREE.MeshStandardMaterial({
    map: backTex, roughness: 0.5, metalness: 0.0, transparent: true,
  });
  const back = new THREE.Mesh(decalGeo, backMat);
  back.position.set(0, 0, -TD / 2 - 0.002);
  back.rotation.y = Math.PI;
  group.add(back);

  group.userData.isTile = true;
  return group;
}

// Build a flat (lying) tile: rounded body laid down + face decal on top (+y).
export function makeFlatTile(faceTex, backTex, bodyMat, faceUp = true) {
  const group = new THREE.Group();
  const geo = new RoundedBoxGeometry(TW, TD, TH, 4, Math.min(TW, TD) * 0.16);
  const body = new THREE.Mesh(geo, bodyMat);
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);

  const fw = TW * 0.9, fh = TH * 0.9;
  const decalGeo = new THREE.PlaneGeometry(fw, fh);
  const topMat = new THREE.MeshStandardMaterial({
    map: faceUp ? faceTex : backTex, roughness: 0.4, transparent: true,
  });
  const top = new THREE.Mesh(decalGeo, topMat);
  top.rotation.x = -Math.PI / 2;
  top.position.set(0, TD / 2 + 0.002, 0);
  group.add(top);

  group.userData.isTile = true;
  return group;
}
