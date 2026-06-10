<template>
  <div class="game">
    <div class="stage" ref="stageEl">
      <canvas ref="canvasEl"></canvas>
      <div v-if="loading" class="loading">Loading 3D tiles…</div>

      <ActionOverlay
        :visible="showActionPrompt"
        :cans="lastCans"
        @ron="actRon"
        @tsumo="actTsumo"
        @riichi="actRiichi"
        @pon="actPon"
        @chi="actChi"
        @pass="actPass"
      />
    </div>

    <SidePanel
      :turn="turn"
      :cans="lastCans"
      :hint="myTurnHint"
      :decision-text="decisionText"
      :ranked-values="rankedValues"
      :log-messages="logMessages"
      @new-round="newRound"
      @auto-discard="autoHuman"
    />

    <ResultModal
      :state="modalState"
      @continue="onModalContinue"
      @quit="onModalQuit"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, nextTick } from "vue";
import * as THREE from "three";
import { buildTextures, makeSideMaterials, makeTile, makeFlatTile, TW, TH, TD } from "./three/tiles.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { createGameClient } from "./net/ws_client.js";
import ActionOverlay from "./components/ActionOverlay.vue";
import SidePanel from "./components/SidePanel.vue";
import ResultModal from "./components/ResultModal.vue";

/* ════════════ Game state ════════════ */
const SUITS = ["m", "p", "s"];
const HONORS = ["E", "S", "W", "N", "P", "F", "C"];
const tileNames = { E: "東", S: "南", W: "西", N: "北", P: "白", F: "發", C: "中" };

const players = ref([
  { name: "You", hand: [], drawn: null, discards: [], furo: [], score: 250 },
  { name: "P1", hand: [], drawn: null, discards: [], furo: [], score: 250 },
  { name: "Mortal", hand: [], drawn: null, discards: [], furo: [], score: 250 },
  { name: "P3", hand: [], drawn: null, discards: [], furo: [], score: 250 },
]);
const wall = ref([]);
const dora = ref("3s");
const bakaze = ref("E");
const turn = ref(0);
const kyoku = ref(1);
const honba = ref(0);
const kyotaku = ref(0);
const decisionText = ref("Waiting...");
const qValues = ref({});
const logMessages = ref([]);
const loading = ref(true);

// End-of-kyoku / end-of-game modal state.
//   modalState.value = null               → no modal
//   modalState.value = { kind: "kyoku", title, lines, deltas } → kyoku result
//   modalState.value = { kind: "game",  ranking } → final game result
const modalState = ref(null);

// Pending hora info captured from the hora event so end_kyoku can show
// the per-seat deltas in the modal.
let pendingKyokuResult = null;

function labelTile(t) { return tileNames[t] || t; }

const rankedValues = computed(() => {
  const rows = Object.entries(qValues.value).sort((a, b) => b[1] - a[1]);
  if (!rows.length) return [];
  const vs = rows.map(([, v]) => v);
  const mn = Math.min(...vs), mx = Math.max(...vs);
  return rows.slice(0, 6).map(([tile, value]) => ({
    tile, value, width: mx === mn ? 100 : Math.round(((value - mn) / (mx - mn)) * 100),
  }));
});

// ─── WebSocket-driven game state ───────────────────────────────────────────
// All game logic lives in the Python backend (server_play.py). The frontend
// just consumes mjai events and reflects them in `players`, `wall`, `dora`,
// `turn`, `kyoku`, `honba`, `kyotaku`, `qValues`. Player input goes back as
// mjai-format messages.

const HUMAN_SEAT = 0;            // we sit at seat 0
const WS_URL = "ws://127.0.0.1:8001/play";

const wsConnected = ref(false);
let gameClient = null;
const lastCans = ref(null);     // legal-action flags from backend (annotated _cans)
const lastEventForCalls = ref(null); // remember last dahai event so we can answer pon/chi/ron

// Initial-deal hands sent in start_kyoku for OPPONENT seats are face-down
// (e.g. ["?", "?", ...]). Our own hand is delivered face-up. We track each
// seat's open hand internally so we can render correctly.

function tileSortKey(t) { if (HONORS.includes(t)) return [3, HONORS.indexOf(t)]; return [SUITS.indexOf(t[1]), +t[0]]; }
function sortHand(h) { h.sort((a, b) => { const ka = tileSortKey(a), kb = tileSortKey(b); return ka[0] - kb[0] || ka[1] - kb[1]; }); }

function resetGameState() {
  for (const p of players.value) { p.hand = []; p.drawn = null; p.discards = []; p.furo = []; }
  wall.value = [];
  qValues.value = {};
  decisionText.value = "Waiting for backend…";
  lastCans.value = null;
  lastEventForCalls.value = null;
}

// ─ event handler dispatch ─
function onMjai(ev) {
  const t = ev.type;
  switch (t) {
    case "ready":
      logMessages.value.push(`Connected. AI = ${ev.ai_label}`);
      return;
    case "start_game":
      logMessages.value = ["=== Game start ==="];
      players.value[0].name = ev.names?.[0] || "You";
      players.value[1].name = ev.names?.[1] || "P1";
      players.value[2].name = ev.names?.[2] || "Mortal";
      players.value[3].name = ev.names?.[3] || "P3";
      return;
    case "start_kyoku":
      onStartKyoku(ev);
      return;
    case "tsumo":
      onTsumo(ev);
      return;
    case "dahai":
      onDahai(ev);
      return;
    case "chi":
    case "pon":
    case "daiminkan":
      onCall(ev);
      return;
    case "ankan":
    case "kakan":
      onKan(ev);
      return;
    case "reach":
      logMessages.value.push(`${players.value[ev.actor]?.name}: Riichi!`);
      return;
    case "reach_accepted":
      // riichi stick paid — backend already updated scores via deltas later;
      // we visually deduct here so the player sees the change immediately.
      players.value[ev.actor].score -= 10;
      kyotaku.value += 1;
      return;
    case "dora":
      // additional kan-dora (we just log it for now)
      logMessages.value.push(`New dora: ${labelTile(ev.dora_marker)}`);
      return;
    case "hora":
      onHora(ev);
      return;
    case "ryukyoku":
      logMessages.value.push("Ryukyoku (exhaustive draw)");
      onRyukyoku(ev);
      return;
    case "end_kyoku":
      onEndKyoku(ev);
      return;
    case "end_game":
      onEndGame();
      return;
    default:
      // Some events (e.g. our own _cans-annotated tsumo/dahai) we already handled.
      return;
  }
}

function onStartKyoku(ev) {
  // ev: { bakaze, kyoku, honba, kyotaku, oya, scores, tehais, dora_marker }
  resetGameState();
  bakaze.value = ev.bakaze;
  kyoku.value = ev.kyoku;
  honba.value = ev.honba;
  kyotaku.value = ev.kyotaku;
  dora.value = ev.dora_marker;
  // Initialize wall to 70 tiles' worth of placeholders (only .length matters).
  wall.value = new Array(70).fill("?");
  for (let i = 0; i < 4; i++) {
    players.value[i].score = Math.round((ev.scores?.[i] ?? 25000) / 100);
  }
  for (let i = 0; i < 4; i++) {
    const tehai = (ev.tehais && ev.tehais[i]) || [];
    players.value[i].hand = [...tehai];
    sortHand(players.value[i].hand);
  }
  logMessages.value.push(
    `${ev.bakaze}${ev.kyoku}  honba=${ev.honba}  oya=P${ev.oya}`,
  );
  rebuildScene();
}

function onTsumo(ev) {
  const p = players.value[ev.actor];
  p.drawn = ev.pai;
  // Pop one tile from the visual wall.
  if (wall.value.length > 0) wall.value.pop();
  if (ev.actor === HUMAN_SEAT) {
    decisionText.value = `Drew ${labelTile(ev.pai)} — your turn`;
  }
  rebuildScene();
}

function onDahai(ev) {
  const p = players.value[ev.actor];
  // If they discarded the tile they just drew, just clear drawn.
  if (p.drawn === ev.pai) {
    p.drawn = null;
  } else {
    // They discarded from hand — first merge the drawn tile in, then remove.
    if (p.drawn != null) {
      p.hand.push(p.drawn);
      p.drawn = null;
      sortHand(p.hand);
    }
    const i = p.hand.indexOf(ev.pai);
    if (i >= 0) p.hand.splice(i, 1);
  }
  p.discards.push(ev.pai);
  rebuildScene();
}

function onCall(ev) {
  // chi / pon / daiminkan: caller takes the called tile, removes consumed
  const caller = players.value[ev.actor];
  const target = players.value[ev.target];
  // remove the called tile from target's last discard
  if (target.discards.length && target.discards[target.discards.length - 1] === ev.pai) {
    target.discards.pop();
  }
  // remove the consumed tiles from caller's hand
  for (const c of ev.consumed || []) {
    const i = caller.hand.indexOf(c);
    if (i >= 0) caller.hand.splice(i, 1);
  }
  // Record the meld so it gets displayed face-up next to the hand.
  // For chi/pon/daiminkan: tiles = consumed + called (`pai`), with the
  // `pai` rotated 90° to indicate which seat it came from.
  const tiles = [...(ev.consumed || []), ev.pai];
  // Position of the rotated tile within the meld (which is `pai`):
  //   chi:        always taken from upstream (left/上家); rotated on the LEFT (idx 0)
  //   pon:        rotated based on which seat target is — we just use the offset
  //   daiminkan:  same idea
  // For simplicity: rotated = the called tile, idx based on (target - actor) mod 4.
  // From the actor's POV, upstream→idx 0, across→idx 1, downstream→idx 2.
  const dir = (4 + ev.target - ev.actor) % 4;
  const rotatedIdx = dir === 3 ? 0 : dir === 2 ? 1 : 2; // upstream/across/downstream
  caller.furo.push({
    type: ev.type,
    tiles,
    rotatedIdx,
    target: ev.target,
    pai: ev.pai,
  });
  turn.value = ev.actor;
  logMessages.value.push(`${caller.name}: ${ev.type} ${labelTile(ev.pai)}`);
  rebuildScene();
}

function onKan(ev) {
  const caller = players.value[ev.actor];
  for (const c of ev.consumed || []) {
    const i = caller.hand.indexOf(c);
    if (i >= 0) caller.hand.splice(i, 1);
  }
  if (ev.type === "ankan") {
    // 暗杠: 4 张面朝下,中间两张面朝上(标准画法)
    caller.furo.push({
      type: "ankan",
      tiles: ev.consumed || [],
      hidden: true,
    });
  } else if (ev.type === "kakan") {
    // 加杠: 在已有 pon 上叠加被加的 pai
    const existing = caller.furo.find(
      (f) => f.type === "pon" && f.pai && stripAka(f.pai) === stripAka(ev.pai),
    );
    if (existing) {
      existing.type = "kakan";
      existing.kakanTile = ev.pai;
    } else {
      caller.furo.push({ type: "kakan", tiles: [ev.pai, ...(ev.consumed || [])] });
    }
  }
  logMessages.value.push(`${caller.name}: ${ev.type}`);
  rebuildScene();
}

function stripAka(t) {
  return t && t.endsWith("r") ? t.slice(0, -1) : t;
}

function onHora(ev) {
  const winner = players.value[ev.actor];
  const isTsumo = ev.actor === ev.target;
  logMessages.value.push(
    `${winner.name} ${isTsumo ? "Tsumo" : "Ron"}!  ${ev.deltas?.join(" ")}`,
  );
  if (ev.deltas) {
    for (let i = 0; i < 4; i++) {
      players.value[i].score += Math.round(ev.deltas[i] / 100);
    }
  }
  // Record so the end_kyoku modal can show details.
  pendingKyokuResult = {
    title: isTsumo
      ? `${winner.name} — Tsumo!`
      : `${winner.name} — Ron on ${players.value[ev.target].name}`,
    deltas: ev.deltas || [0, 0, 0, 0],
  };
}

function onRyukyoku(ev) {
  pendingKyokuResult = {
    title: "Exhaustive draw (ryukyoku)",
    deltas: ev.deltas || [0, 0, 0, 0],
  };
}

function onEndKyoku(ev) {
  // If we have a pending hora/ryukyoku result, show it as a modal.
  // The backend pauses while we decide via the modal (we don't actually
  // pause it — it'll start the next kyoku in 0.6s due to ai_delay).
  // So we display the modal but allow the next start_kyoku to proceed.
  if (pendingKyokuResult) {
    modalState.value = {
      kind: "kyoku",
      title: pendingKyokuResult.title,
      deltas: pendingKyokuResult.deltas,
      scores: players.value.map((p) => p.score * 100),
      names: players.value.map((p) => p.name),
    };
    pendingKyokuResult = null;
  }
}

function onEndGame() {
  logMessages.value.push("=== Game over ===");
  decisionText.value = "Game over.";
  // Build final ranking from current scores.
  const ranking = players.value
    .map((p, i) => ({ i, name: p.name, score: p.score * 100 }))
    .sort((a, b) => b.score - a.score);
  modalState.value = {
    kind: "game",
    title: "Game over",
    ranking,
  };
}

// ─ player actions (sent to backend) ─
//
// We act only when GM tells us via `_your_turn`. The frontend tracks
// `myTurn` (a ref): true when the most recent event has `_your_turn=true`,
// false otherwise. While `myTurn=false` we ignore clicks to avoid sending
// unsolicited messages.

const myTurn = ref(false);
const lastDahaiEvent = ref(null);  // remember the dahai we may pon/chi/ron on

const showActionPrompt = computed(() => {
  if (!myTurn.value || !lastCans.value) return false;
  // If we can discard, the action is "click a tile" — don't show overlay.
  if (lastCans.value.can_discard) {
    // Show only if there's also a riichi/tsumo option as a button alternative.
    return !!(lastCans.value.can_riichi || lastCans.value.can_tsumo_agari);
  }
  // Otherwise show the overlay if any non-discard action is available.
  return !!(
    lastCans.value.can_ron_agari ||
    lastCans.value.can_pon ||
    lastCans.value.can_chi ||
    lastCans.value.can_kan ||
    lastCans.value.can_pass
  );
});

const myTurnHint = computed(() => {
  if (!myTurn.value) return "";
  if (!lastCans.value) return "";
  if (lastCans.value.can_discard) return "Your turn — click a tile to discard.";
  if (lastCans.value.can_ron_agari) return "Ron available!";
  if (lastCans.value.can_pon || lastCans.value.can_chi) return "You can call.";
  return "";
});

function send(obj) {
  if (gameClient) gameClient.send(obj);
}

// Send a reaction and lock the local UI until next prompt.
function reactWith(obj) {
  if (!myTurn.value) return;
  send(obj);
  myTurn.value = false;
}

function discardHuman(tile) {
  if (!myTurn.value || !lastCans.value?.can_discard) return;
  const p = players.value[HUMAN_SEAT];
  const tsumogiri = p.drawn === tile;
  reactWith({ type: "dahai", actor: HUMAN_SEAT, pai: tile, tsumogiri });
}

function autoHuman() {
  if (!myTurn.value || !lastCans.value?.can_discard) return;
  const p = players.value[HUMAN_SEAT];
  if (p.drawn != null) {
    reactWith({ type: "dahai", actor: HUMAN_SEAT, pai: p.drawn, tsumogiri: true });
  } else if (p.hand.length) {
    reactWith({ type: "dahai", actor: HUMAN_SEAT, pai: p.hand[p.hand.length - 1], tsumogiri: false });
  }
}

function actTsumo() {
  reactWith({ type: "hora", actor: HUMAN_SEAT, target: HUMAN_SEAT });
}

function actRon() {
  const target = lastDahaiEvent.value?.actor ?? HUMAN_SEAT;
  reactWith({ type: "hora", actor: HUMAN_SEAT, target });
}

function actRiichi() {
  reactWith({ type: "reach", actor: HUMAN_SEAT });
}

function actPass() {
  reactWith({ type: "none" });
}

// Build consumed pair for pon based on our hand counts.
function _ponConsumed(pai) {
  const stripped = pai.endsWith("r") ? pai.slice(0, -1) : pai;
  const p = players.value[HUMAN_SEAT];
  const tiles = [...p.hand];
  if (p.drawn) tiles.push(p.drawn);  // drawn could be in hand if we mid-call (unlikely)
  const same = tiles.filter((t) => (t.endsWith("r") ? t.slice(0, -1) : t) === stripped);
  if (same.length < 2) return null;
  // Prefer non-aka first to keep aka in hand
  const nonAka = same.filter((t) => !t.endsWith("r"));
  const aka = same.filter((t) => t.endsWith("r"));
  return [...nonAka, ...aka].slice(0, 2);
}

function actPon() {
  const ev = lastDahaiEvent.value;
  if (!ev) return;
  const consumed = _ponConsumed(ev.pai);
  if (!consumed) return;
  reactWith({
    type: "pon",
    actor: HUMAN_SEAT,
    target: ev.actor,
    pai: ev.pai,
    consumed,
  });
}

// Build consumed pair for chi (kind ∈ low/mid/high).
function _chiConsumed(pai, kind) {
  const stripped = pai.endsWith("r") ? pai.slice(0, -1) : pai;
  if (!/^\d/.test(stripped)) return null;
  const rank = +stripped[0];
  const suit = stripped[1];
  let needed;
  if (kind === "low") needed = [rank + 1, rank + 2];
  else if (kind === "mid") needed = [rank - 1, rank + 1];
  else needed = [rank - 2, rank - 1];
  if (needed.some((r) => r < 1 || r > 9)) return null;

  const p = players.value[HUMAN_SEAT];
  const tiles = [...p.hand];
  if (p.drawn) tiles.push(p.drawn);
  const consumed = [];
  const remaining = [...tiles];
  for (const r of needed) {
    const t = `${r}${suit}`;
    let idx = remaining.indexOf(t);
    if (idx < 0) idx = remaining.indexOf(t + "r");
    if (idx < 0) return null;
    consumed.push(remaining.splice(idx, 1)[0]);
  }
  return consumed;
}

function actChi(kind) {
  const ev = lastDahaiEvent.value;
  if (!ev) return;
  const consumed = _chiConsumed(ev.pai, kind);
  if (!consumed) return;
  reactWith({
    type: "chi",
    actor: HUMAN_SEAT,
    target: ev.actor,
    pai: ev.pai,
    consumed,
  });
}

function newRound() {
  // Restart the WebSocket session = new game.
  if (gameClient) gameClient.disconnect();
  modalState.value = null;
  pendingKyokuResult = null;
  connectWs();
}

function onModalContinue() {
  // For an end-of-kyoku modal, the backend has already started the next
  // kyoku in the background — we just dismiss the modal.
  // For an end-of-game modal, we restart with a fresh session.
  if (modalState.value?.kind === "game") {
    newRound();
    return;
  }
  modalState.value = null;
}

function onModalQuit() {
  // Drop the connection; user can click "New Round" to start a new game.
  if (gameClient) gameClient.disconnect();
  modalState.value = null;
  myTurn.value = false;
  decisionText.value = "Disconnected. Click New Round to play again.";
  logMessages.value.push("Disconnected by user");
}

function connectWs() {
  resetGameState();
  myTurn.value = false;
  lastDahaiEvent.value = null;
  gameClient = createGameClient({
    url: WS_URL,
    onOpen: () => {
      wsConnected.value = true;
      logMessages.value.push("WebSocket connected");
    },
    onClose: () => {
      wsConnected.value = false;
      logMessages.value.push("WebSocket closed");
      myTurn.value = false;
    },
    onError: () => {
      logMessages.value.push("WebSocket error");
    },
    onEvent: (ev) => {
      if (ev._cans) lastCans.value = ev._cans;
      if (ev.type === "dahai") lastDahaiEvent.value = ev;
      // `myTurn` is sticky: once true, stays true until we send a reaction
      // (or the round ends). This avoids losing it when GM emits an
      // "informational" event right after the prompt event but before
      // entering its asyncio.wait_for on our reaction.
      if (ev._your_turn) {
        myTurn.value = true;
        console.log(
          `[your_turn ON] type=${ev.type} actor=${ev.actor ?? "-"} ` +
          `pai=${ev.pai ?? "-"} can_discard=${ev._cans?.can_discard} ` +
          `can_pon=${ev._cans?.can_pon} can_chi=${ev._cans?.can_chi} ` +
          `can_ron=${ev._cans?.can_ron_agari} can_riichi=${ev._cans?.can_riichi}`,
        );
      } else if (
        // Reset on round/game boundaries so a stale myTurn doesn't carry over.
        ev.type === "end_kyoku" ||
        ev.type === "end_game" ||
        ev.type === "hora" ||
        ev.type === "ryukyoku"
      ) {
        myTurn.value = false;
      }
      onMjai(ev);
    },
  });
  gameClient.connect();
}

/* ════════════ Three.js scene ════════════ */
const stageEl = ref(null);
const canvasEl = ref(null);
let renderer, scene, camera, raf;
let textures = null;
let sideMat = null;
let centerBoard = null;       // 3D 中央信息板
let centerCanvas = null, centerCtx = null, centerTex = null;
const dynamicGroup = new THREE.Group(); // holds all tile meshes we rebuild each turn
const pickTargets = []; // { mesh, tile } for raycasting my hand
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

// table dimensions
const TABLE = 16;        // half-extent of the table plane
const HAND_Z = 9.2;      // z position of my hand (near camera)
const RIVER_R = 3.3;     // inner radius for discards

async function initThree() {
  const canvas = canvasEl.value;
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x10231a);

  // Environment map for subtle reflections on the glossy tiles
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  camera = new THREE.PerspectiveCamera(42, 1, 0.1, 200);
  // sit at player's seat, look down at table — Tenhou angle
  camera.position.set(0, 17.5, 19.5);
  camera.lookAt(0, 0, -0.5);

  // Lighting
  const amb = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(amb);
  const key = new THREE.DirectionalLight(0xffffff, 0.8);
  key.position.set(6, 20, 10);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = -TABLE; key.shadow.camera.right = TABLE;
  key.shadow.camera.top = TABLE; key.shadow.camera.bottom = -TABLE;
  key.shadow.camera.near = 1; key.shadow.camera.far = 60;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xaaccff, 0.25);
  fill.position.set(-8, 10, -6);
  scene.add(fill);

  // Table surface
  const tableGeo = new THREE.PlaneGeometry(TABLE * 2, TABLE * 2);
  const tableMat = new THREE.MeshStandardMaterial({ color: 0x12402c, roughness: 0.95 });
  const table = new THREE.Mesh(tableGeo, tableMat);
  table.rotation.x = -Math.PI / 2;
  table.receiveShadow = true;
  scene.add(table);
  // subtle center square
  const centerGeo = new THREE.PlaneGeometry(7.5, 7.5);
  const centerMat = new THREE.MeshStandardMaterial({ color: 0x0c2c1d, roughness: 1 });
  const centerSq = new THREE.Mesh(centerGeo, centerMat);
  centerSq.rotation.x = -Math.PI / 2;
  centerSq.position.y = 0.01;
  scene.add(centerSq);

  // 3D 中央信息板(平放在桌面上的薄盒,canvas 贴图)
  // 用 MeshBasicMaterial 而非 StandardMaterial,确保贴图不被光照/阴影模糊
  centerCanvas = document.createElement("canvas");
  centerCanvas.width = 1024; centerCanvas.height = 1024;   // 更高分辨率
  centerCtx = centerCanvas.getContext("2d");
  centerTex = new THREE.CanvasTexture(centerCanvas);
  centerTex.colorSpace = THREE.SRGBColorSpace;
  centerTex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  centerTex.minFilter = THREE.LinearMipmapLinearFilter;
  centerTex.magFilter = THREE.LinearFilter;
  centerTex.generateMipmaps = true;
  const cbGeo = new THREE.BoxGeometry(3.6, 0.16, 3.6);
  const cbDark = new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.9 });
  // Top face: MeshBasic = no lighting, no env reflection → full crispness
  const cbTopMat = new THREE.MeshBasicMaterial({ map: centerTex });
  centerBoard = new THREE.Mesh(cbGeo, [cbDark, cbDark, cbTopMat, cbDark, cbDark, cbDark]);
  centerBoard.position.set(0, 0.085, 0);
  centerBoard.castShadow = false;
  centerBoard.receiveShadow = false;
  scene.add(centerBoard);

  scene.add(dynamicGroup);

  textures = await buildTextures(renderer);
  sideMat = makeSideMaterials(scene.environment);
  loading.value = false;

  resize();
  window.addEventListener("resize", resize);
  canvas.addEventListener("click", onClick);

  rebuildScene();
  animate();
}

function clearGroup() {
  for (let i = dynamicGroup.children.length - 1; i >= 0; i--) {
    dynamicGroup.remove(dynamicGroup.children[i]);
  }
  pickTargets.length = 0;
}

// 在中央信息板的 canvas 上绘制:四家点数/风位绕四边,中央局数
function drawCenterBoard() {
  if (!centerCtx) return;
  const S = 1024, ctx = centerCtx;
  ctx.clearRect(0, 0, S, S);

  // 背景:深色立方体表面 + 内描边
  ctx.fillStyle = "#0a0a0a";
  ctx.fillRect(0, 0, S, S);
  ctx.strokeStyle = "#3a3a3a"; ctx.lineWidth = 8;
  ctx.strokeRect(12, 12, S - 24, S - 24);
  // 内细线分隔(对角线分四块,呼应天凤布局)
  ctx.strokeStyle = "rgba(255,255,255,0.06)"; ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, 0); ctx.lineTo(S, S);
  ctx.moveTo(S, 0); ctx.lineTo(0, S);
  ctx.stroke();

  // 字体:抗锯齿
  ctx.imageSmoothingEnabled = true;

  // Center: round name + meta info
  ctx.save();
  ctx.translate(S / 2, S / 2);
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  // Round name (East/South 1..4)
  const roundLabel = `${bakaze.value}-${kyoku.value}`;
  ctx.fillStyle = "#ffd700";
  ctx.shadowColor = "rgba(255, 215, 0, 0.4)";
  ctx.shadowBlur = 18;
  ctx.font = "bold 150px 'Helvetica Neue', sans-serif";
  ctx.fillText(roundLabel, 0, -42);
  ctx.shadowBlur = 0;
  // Sub line
  ctx.fillStyle = "#cccccc";
  ctx.font = "500 44px 'Helvetica Neue', monospace";
  ctx.fillText(
    `wall ${wall.value.length}   honba ${honba.value}   sticks ${kyotaku.value}`,
    0, 80,
  );
  ctx.restore();

  // Per-seat info: wind + score, rotated to face each seat.
  // The canvas is mapped onto the +y face; player 0 sits at +z (bottom).
  const seatRot = [0, Math.PI / 2, Math.PI, -Math.PI / 2]; // 0=bottom, 1=right, 2=top, 3=left
  // Self-wind for each seat (the dealer rotates over the four kyoku;
  // seat 0 is dealer at kyoku 1, seat 1 at kyoku 2, etc.). Compute it from
  // kyoku so the labels match the actual dealer.
  const dealerOf = (kyoku.value - 1) % 4;
  const winds = ["E", "S", "W", "N"];
  const seatWind = (p) => winds[(p - dealerOf + 4) % 4];

  for (let p = 0; p < 4; p++) {
    ctx.save();
    ctx.translate(S / 2, S / 2);
    ctx.rotate(seatRot[p]);
    ctx.textAlign = "center"; ctx.textBaseline = "middle";

    const isActive = turn.value === p;
    const isDealer = p === dealerOf;
    const windY = S / 2 - 200;
    const scoreY = S / 2 - 120;

    // Wind label
    ctx.fillStyle = isActive ? "#ffd700" : (isDealer ? "#ff6b6b" : "#dddddd");
    if (isActive) {
      ctx.shadowColor = "#ffd700";
      ctx.shadowBlur = 24;
    }
    ctx.font = "bold 96px 'Helvetica Neue', sans-serif";
    ctx.fillText(seatWind(p), 0, windY);
    ctx.shadowBlur = 0;

    // Score
    ctx.fillStyle = "#ffffff";
    ctx.font = "600 64px 'Helvetica Neue', monospace";
    ctx.fillText(`${players.value[p].score}00`, 0, scoreY);

    ctx.restore();
  }
  centerTex.needsUpdate = true;
}

// place a tile flat on table (lying down, face up) — for discards
function placeFlat(tile, x, z, rotY, faceUp = true) {
  const t = makeFlatTile(textures.faces.get(tile), textures.back, sideMat, faceUp);
  t.position.set(x, TD / 2, z);
  t.rotation.y = rotY;
  dynamicGroup.add(t);
  return t;
}

// place a standing tile (face toward a direction) — for hands
function placeStanding(tile, x, z, faceYaw, showFace, pickable = false, scale = 1) {
  const faceTex = textures.faces.get(tile);
  const t = makeTile(faceTex, textures.back, sideMat, showFace);
  if (scale !== 1) t.scale.setScalar(scale);
  // standing tile leans back slightly
  t.position.set(x, (TH * scale) / 2, z);
  t.rotation.y = faceYaw;
  t.rotation.x = faceYaw === 0 ? -0.18 : 0; // my hand leans toward me
  dynamicGroup.add(t);
  if (pickable) pickTargets.push({ mesh: t, tile });
  return t;
}

function rebuildScene() {
  if (!textures) return;
  clearGroup();
  drawCenterBoard();

  // ── My hand (bottom, facing me, large) ──
  const myHand = players.value[0].hand;
  const gap = TW + 0.06;
  const startX = -((myHand.length - 1) * gap) / 2;
  myHand.forEach((tile, i) => {
    placeStanding(tile, startX + i * gap, HAND_Z, 0, true, true);
  });
  // 摸到的牌:放在手牌最右边,留一个间隔
  if (players.value[0].drawn != null) {
    const drawnX = startX + (myHand.length - 1) * gap + gap + 0.45;
    placeStanding(players.value[0].drawn, drawnX, HAND_Z, 0, true, true);
  }

  // ── Opponent hands (face away, show back) ──
  // top player (2): facing down toward center, we see backs
  layoutOppHand(players.value[2].hand, "top");
  layoutOppHand(players.value[1].hand, "right");
  layoutOppHand(players.value[3].hand, "left");

  // ── Discards (rivers) ──
  layoutRiver(players.value[0].discards, "bottom");
  layoutRiver(players.value[1].discards, "right");
  layoutRiver(players.value[2].discards, "top");
  layoutRiver(players.value[3].discards, "left");

  // ── Furo (declared melds: chi/pon/kan, face-up beside each hand) ──
  for (let pid = 0; pid < 4; pid++) {
    layoutFuro(players.value[pid].furo, pid);
  }

  // ── Walls (牌山) two layers around the edges ──
  buildWalls();
}

// 把副露(亮牌的吃/碰/杠)铺在每个玩家手牌的右端外侧,沿玩家边的方向往外走。
// 锚点根据手牌的实际长度动态计算,避免与手牌重叠;同时一组面子向外铺,
// 一组接着一组继续往外。
function layoutFuro(furo, pid) {
  if (!furo || !furo.length) return;

  // 一组面子的横向 footprint = 3 张立牌 + 1 张横放 ≈ 3*TW + TH
  const groupGap = 0.18;
  const groupWidth = 3 * (TW + 0.03) + TH + 0.05;

  // 每个玩家的手牌占用宽度:
  //   pid 0 (我): 立牌实宽 = (n-1)*(TW+0.06) + TW + drawn? + 间隔
  //   其他玩家:    立牌实宽 = (n-1)*(TW+0.05) + TW
  const p = players.value[pid];
  const handCount = p.hand.length;
  const handGap = pid === 0 ? TW + 0.06 : TW + 0.05;
  // half-width of the centered hand block
  let handHalf = ((handCount - 1) * handGap) / 2 + TW / 2;
  if (pid === 0 && p.drawn != null) {
    // drawn 牌往右多伸出 (gap + 0.45)
    handHalf += (TW + 0.06) + 0.45;
  }

  // furo 第一组的中心 = 手牌右端 + groupWidth/2 + 一点边距
  const furoMargin = 0.25;
  const firstCenter = handHalf + furoMargin + groupWidth / 2;

  // 各玩家:沿 "玩家面前" 的右方向向外延伸。
  //   pid 0 (下): 手牌中心在 (0, HAND_Z=9.2),沿 +x 向外
  //   pid 1 (右): 手牌中心在 (10.6, 0),沿 -z 向外(远离我们的视角)
  //   pid 2 (上): 手牌中心在 (0, -10.6),沿 -x 向外
  //   pid 3 (左): 手牌中心在 (-10.6, 0),沿 +z 向外
  let cx, cz, dirX, dirZ, yaw;
  if (pid === 0) {
    cx = firstCenter; cz = HAND_Z; dirX = 1; dirZ = 0; yaw = 0;
  } else if (pid === 1) {
    cx = 10.6; cz = -firstCenter; dirX = 0; dirZ = -1; yaw = -Math.PI / 2;
  } else if (pid === 2) {
    cx = -firstCenter; cz = -10.6; dirX = -1; dirZ = 0; yaw = Math.PI;
  } else {
    cx = -10.6; cz = firstCenter; dirX = 0; dirZ = 1; yaw = Math.PI / 2;
  }

  let cursor = 0;
  for (const meld of furo) {
    placeFuroGroup(meld, cx + dirX * cursor, cz + dirZ * cursor, yaw);
    cursor += groupWidth + groupGap;
  }
}

// 渲染一组副露
function placeFuroGroup(meld, cx, cz, yaw) {
  const step = TW + 0.02;
  // 局部坐标系(沿 yaw 方向"右为正"):
  //   在世界坐标里:沿 yaw 方向的前进 = (sin yaw, cos yaw)
  // 不过简化处理:我们直接按 yaw 旋转每张牌并按面子方向相对位移
  const cosY = Math.cos(yaw), sinY = Math.sin(yaw);
  const advance = (offset) => [cosY * offset, -sinY * offset];

  const tiles = meld.tiles || [];
  const isAnkan = meld.type === "ankan";
  const rotatedIdx = meld.rotatedIdx ?? -1;

  let ofs = -((tiles.length - 1) * step) / 2;  // center the meld
  for (let i = 0; i < tiles.length; i++) {
    const tile = tiles[i];
    const showFace = !(isAnkan && (i === 0 || i === 3));  // ankan: 中两张面朝上
    const [dx, dz] = advance(ofs);
    if (i === rotatedIdx) {
      // 横放被叫的牌:用 placeFlat 横放,同时 yaw 加 90° 表示旋转
      // 用 yaw + 90° 让牌的"长边"朝向 yaw 方向
      placeFlat(tile, cx + dx, cz + dz, yaw + Math.PI / 2, true);
    } else {
      placeStanding(tile, cx + dx, cz + dz, yaw, showFace, false);
    }
    ofs += step;
  }
  // kakan: 在原先旋转牌的位置上方再叠一张(旋转 90°)
  if (meld.type === "kakan" && meld.kakanTile != null && rotatedIdx >= 0) {
    const ofs2 = -((tiles.length - 1) * step) / 2 + rotatedIdx * step;
    const [dx, dz] = advance(ofs2);
    // 叠一张同方向的横放,Y 抬高一点(简化:沿用 placeFlat 的 y=TD/2 + TD)
    placeFlat(meld.kakanTile, cx + dx, cz + dz, yaw + Math.PI / 2, true);
  }
}

function layoutOppHand(hand, side) {
  const gap = TW + 0.05;
  const n = hand.length;
  const start = -((n - 1) * gap) / 2;
  const edge = 10.6;
  hand.forEach((tile, i) => {
    let x, z, yaw;
    if (side === "top") { x = start + i * gap; z = -edge; yaw = Math.PI; }
    else if (side === "right") { x = edge; z = start + i * gap; yaw = -Math.PI / 2; }
    else { x = -edge; z = start + i * gap; yaw = Math.PI / 2; }
    placeStanding(tile, x, z, yaw, false, false);
  });
}

function layoutRiver(discards, side) {
  const cols = 6;
  const stepX = TW + 0.04;
  const stepZ = TH + 0.04;
  discards.forEach((tile, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    let x, z, rotY;
    if (side === "bottom") { x = (col - 2.5) * stepX; z = RIVER_R + row * stepZ; rotY = 0; }
    else if (side === "top") { x = -(col - 2.5) * stepX; z = -(RIVER_R + row * stepZ); rotY = Math.PI; }
    else if (side === "right") { x = RIVER_R + row * stepZ; z = -(col - 2.5) * stepX; rotY = Math.PI / 2; }
    else { x = -(RIVER_R + row * stepZ); z = (col - 2.5) * stepX; rotY = -Math.PI / 2; }
    placeFlat(tile, x, z, rotY, true);
  });
}

// 牌山:风车式(pinwheel)四面,四角咬合不重叠,整体外移
function buildWalls() {
  const perWall = 17;
  const w = TW + 0.02;            // 沿墙方向每墩间距
  const len = perWall * w;        // 每面长度
  const D = len / 2 + 0.9 + TH / 2; // 方框中线到中心的距离(外移半个牌长)
  const half = len / 2;

  // 风车式:每面沿一个方向铺满 perWall 墩,并朝"前进方向"的角偏移半墩,
  // 使本面末端正好让位给下一面的起点,四角无重叠。
  // 顺时针环绕:top(→) right(↓) bottom(←) left(↑)
  const off = w / 2; // 朝前进方向偏移半墩,形成风车咬合
  const walls = [
    // top: 沿 +x,固定 z=-D,起点偏移 -half+off
    { build: (i) => ({ x: -half + off + i * w, z: -D }), rotY: 0 },
    // right: 沿 +z,固定 x=+D
    { build: (i) => ({ x: D, z: -half + off + i * w }), rotY: Math.PI / 2 },
    // bottom: 沿 -x,固定 z=+D
    { build: (i) => ({ x: half - off - i * w, z: D }), rotY: 0 },
    // left: 沿 -z,固定 x=-D
    { build: (i) => ({ x: -D, z: half - off - i * w }), rotY: Math.PI / 2 },
  ];

  const positions = [];
  for (const s of walls) {
    for (let i = 0; i < perWall; i++) {
      const p = s.build(i);
      for (let layer = 1; layer >= 0; layer--) {  // 先上层后下层,从顶端消耗
        positions.push({ x: p.x, y: TD / 2 + layer * TD, z: p.z, rotY: s.rotY });
      }
    }
  }

  const remaining = Math.max(0, Math.min(positions.length, wall.value.length));
  const startIdx = positions.length - remaining;
  for (let i = startIdx; i < positions.length; i++) {
    const p = positions[i];
    addWallTile(p.x, p.y, p.z, p.rotY);
  }
}

function addWallTile(x, y, z, rotY) {
  // 牌山的牌:横躺,背面朝上(绿色),用圆角牌
  const t = makeFlatTile(textures.back, textures.back, sideMat, true);
  t.position.set(x, y, z);
  t.rotation.y = rotY;
  dynamicGroup.add(t);
}

function onClick(e) {
  if (loading.value) return;

  const rect = canvasEl.value.getBoundingClientRect();
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(pickTargets.map((p) => p.mesh), true);

  if (!hits.length) {
    // No tile under cursor.
    return;
  }

  // Walk up from the hit child mesh to find the matching pickTarget group.
  let obj = hits[0].object;
  let hit = null;
  while (obj && !hit) {
    hit = pickTargets.find((p) => p.mesh === obj);
    obj = obj.parent;
  }
  if (!hit) return;

  // Now check whether we're allowed to act on this click.
  if (!myTurn.value || !lastCans.value?.can_discard) {
    console.warn(
      `[click ignored] tile=${hit.tile} myTurn=${myTurn.value} ` +
      `can_discard=${lastCans.value?.can_discard ?? "n/a"} ` +
      `can_act=${lastCans.value?.can_act ?? "n/a"}`,
    );
    return;
  }
  console.log(`[discard] ${hit.tile}`);
  discardHuman(hit.tile);
}

function resize() {
  if (!stageEl.value) return;
  const w = stageEl.value.clientWidth;
  const h = stageEl.value.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function animate() {
  raf = requestAnimationFrame(animate);
  renderer.render(scene, camera);
}

onMounted(async () => {
  await nextTick();
  await initThree();
  // Connect to backend; the backend will push start_game/start_kyoku and game flow.
  connectWs();
});

onBeforeUnmount(() => {
  cancelAnimationFrame(raf);
  window.removeEventListener("resize", resize);
  if (canvasEl.value) canvasEl.value.removeEventListener("click", onClick);
  if (gameClient) gameClient.disconnect();
  renderer?.dispose();
});
</script>

<style scoped>
:global(*) { box-sizing: border-box; margin: 0; padding: 0; }
:global(body) { background: #0a0a0a; font-family: 'Segoe UI', sans-serif; color: #eee; overflow: hidden; }

.game { display: grid; grid-template-columns: 1fr 220px; height: 100vh; width: 100vw; }

.stage { position: relative; grid-column: 1; overflow: hidden; background: #10231a; }
.stage canvas { display: block; width: 100%; height: 100%; }

.loading {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 16px; color: #888; background: #10231a;
}
</style>
