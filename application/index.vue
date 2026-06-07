<template>
  <main class="app">
    <section class="table" aria-label="Mahjong table">
      <div class="wall wall-top" aria-hidden="true">
        <div class="wall-layer wall-layer-back">
          <TileView v-for="n in 14" :key="`wall-top-back-${n}`" tile="?" back wall-pose="horizontal" />
        </div>
        <div class="wall-layer wall-layer-front">
          <TileView v-for="n in 14" :key="`wall-top-front-${n}`" tile="?" back wall-pose="horizontal" />
        </div>
      </div>
      <div class="wall wall-left" aria-hidden="true">
        <div class="wall-layer wall-layer-back">
          <TileView v-for="n in 12" :key="`wall-left-back-${n}`" tile="?" back wall-pose="vertical" />
        </div>
        <div class="wall-layer wall-layer-front">
          <TileView v-for="n in 12" :key="`wall-left-front-${n}`" tile="?" back wall-pose="vertical" />
        </div>
      </div>
      <div class="wall wall-right" aria-hidden="true">
        <div class="wall-layer wall-layer-back">
          <TileView v-for="n in 12" :key="`wall-right-back-${n}`" tile="?" back wall-pose="vertical" />
        </div>
        <div class="wall-layer wall-layer-front">
          <TileView v-for="n in 12" :key="`wall-right-front-${n}`" tile="?" back wall-pose="vertical" />
        </div>
      </div>
      <div class="wall wall-bottom" aria-hidden="true">
        <div class="wall-layer wall-layer-back">
          <TileView v-for="n in 14" :key="`wall-bottom-back-${n}`" tile="?" back wall-pose="horizontal" />
        </div>
        <div class="wall-layer wall-layer-front">
          <TileView v-for="n in 14" :key="`wall-bottom-front-${n}`" tile="?" back wall-pose="horizontal" />
        </div>
      </div>

      <SeatBadge class="badge-top" :player="players[2]" :active="turn === 2" />
      <SeatBadge class="badge-left" :player="players[3]" :active="turn === 3" />
      <SeatBadge class="badge-right" :player="players[1]" :active="turn === 1" />

      <div class="opponent-hand opponent-hand-left" aria-label="Random B hand">
          <TileView v-for="(_, i) in players[3].hand" :key="`p3-hand-${i}`" tile="?" back player-tile />
      </div>

      <div class="opponent-hand opponent-hand-right" aria-label="Random A hand">
          <TileView v-for="(_, i) in players[1].hand" :key="`p1-hand-${i}`" tile="?" back player-tile />
      </div>

      <section class="seat seat-top" aria-label="Mortal RL hand and discards">
        <div class="hand">
          <TileView v-for="(_, i) in players[2].hand" :key="`p2-hand-${i}`" tile="?" back player-tile />
        </div>
        <div class="river river-top">
          <TileView v-for="(tile, i) in players[2].discards" :key="`p2-river-${i}`" :tile="tile" small />
        </div>
      </section>

      <section class="seat seat-left" aria-label="Random B discards">
        <div class="river river-side">
          <TileView v-for="(tile, i) in players[3].discards" :key="`p3-river-${i}`" :tile="tile" small />
        </div>
      </section>

      <section class="seat seat-right" aria-label="Random A discards">
        <div class="river river-side">
          <TileView v-for="(tile, i) in players[1].discards" :key="`p1-river-${i}`" :tile="tile" small />
        </div>
      </section>

      <section class="seat seat-bottom" aria-label="Your hand and discards">
        <div class="river river-bottom">
          <TileView v-for="(tile, i) in players[0].discards" :key="`p0-river-${i}`" :tile="tile" small />
        </div>
        <div class="hand hand-bottom">
          <TileView
            v-for="(tile, i) in players[0].hand"
            :key="`p0-hand-${i}-${tile}`"
            tile="?"
            back
            player-tile
            :clickable="turn === 0"
            @discard="discardHuman(tile)"
          />
        </div>
      </section>

      <section class="center-board" aria-label="Round status">
        <div class="dora">
          <span>Dora</span>
          <TileView :tile="dora" small />
        </div>
        <div class="score-board">
          <div v-for="seat in centerSeats" :key="seat.wind" class="score-card" :class="seat.className">
            <span>{{ seat.wind }}</span>
            <strong>{{ seat.score }}</strong>
          </div>
          <div class="round-core">
            <span class="wall-count">{{ wall.length }} tiles left</span>
            <strong>{{ roundName }}</strong>
            <span>{{ honba }} honba / {{ kyotaku }} riichi stick</span>
          </div>
        </div>
      </section>
    </section>

    <aside class="side-panel" aria-label="Agent details">
      <section class="panel-block intro">
        <h1>Mahjong RL Agent</h1>
        <p>Vue demo for one human player, two random baselines, and a Mortal-style action-value discard policy.</p>
        <div class="controls">
          <button type="button" @click="newRound">New Round</button>
          <button type="button" :disabled="turn !== 0" @click="autoHuman">Auto Discard</button>
        </div>
      </section>

      <section class="panel-block">
        <h2>Latest Agent Decision</h2>
        <p class="decision">{{ decisionText }}</p>
        <div class="q-list">
          <div v-for="row in rankedValues" :key="row.tile" class="q-row">
            <strong>{{ row.tile }}</strong>
            <div class="bar"><span :style="{ width: `${row.width}%` }" /></div>
            <span>{{ row.value.toFixed(2) }}</span>
          </div>
        </div>
      </section>

      <section class="panel-block log-block">
        <h2>Event Log</h2>
        <ol class="event-log">
          <li v-for="(event, i) in logMessages" :key="i">{{ event }}</li>
        </ol>
      </section>
    </aside>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from "vue";

const IMAGE_DIR = "/mahjong-assets/images";
const SUITS = ["m", "p", "s"];
const HONORS = ["E", "S", "W", "N", "P", "F", "C"];

const tileNames = {
  E: "East",
  S: "South",
  W: "West",
  N: "North",
  P: "White",
  F: "Green",
  C: "Red",
};

const players = ref([
  { name: "You", rating: "R2000", hand: [], discards: [], score: 26000 },
  { name: "Random A", rating: "R1942", hand: [], discards: [], score: 28300 },
  { name: "Mortal RL", rating: "R1953", hand: [], discards: [], score: 22000 },
  { name: "Random B", rating: "R1912", hand: [], discards: [], score: 23700 },
]);

const wall = ref([]);
const dora = ref("3s");
const turn = ref(0);
const kyoku = ref(3);
const honba = ref(0);
const kyotaku = ref(1);
const decisionText = ref("Mortal RL will evaluate its next discard.");
const qValues = ref({});
const logMessages = ref([]);

function tileImage(tile, back = false, wallPose = "player") {
  if (back || tile === "?") {
    const pose = wallPose === "horizontal" ? 3 : wallPose === "vertical" ? 1 : 0;
    return `${IMAGE_DIR}/p_bk_${pose}.gif`;
  }
  if (HONORS.includes(tile)) {
    const map = { E: "ji_e", S: "ji_s", W: "ji_w", N: "ji_n", P: "no", F: "ji_h", C: "ji_c" };
    return `${IMAGE_DIR}/p_${map[tile]}_0.gif`;
  }
  const suitPrefix = { m: "ms", p: "ps", s: "ss" }[tile[1]];
  return `${IMAGE_DIR}/p_${suitPrefix}${tile[0]}_0.gif`;
}

function labelTile(tile) {
  return tileNames[tile] || tile;
}

const TileView = defineComponent({
  props: {
    tile: { type: String, required: true },
    back: { type: Boolean, default: false },
    small: { type: Boolean, default: false },
    clickable: { type: Boolean, default: false },
    playerTile: { type: Boolean, default: false },
    wallPose: { type: String, default: "player" },
  },
  emits: ["discard"],
  setup(props, { emit }) {
    return () => {
      const content = h("img", {
        src: tileImage(props.tile, props.back, props.wallPose),
        alt: props.back ? "Face-down tile" : labelTile(props.tile),
      });

      if (props.clickable) {
        return h(
          "button",
          {
            class: ["tile", "tile-button"],
            type: "button",
            title: `Discard ${labelTile(props.tile)}`,
            onClick: () => emit("discard"),
          },
          content,
        );
      }

      return h("span", { class: ["tile", { small: props.small }] }, content);
    };
  },
});

const SeatBadge = defineComponent({
  props: {
    player: { type: Object, required: true },
    active: { type: Boolean, default: false },
  },
  setup(props, { attrs }) {
    return () =>
      h("div", { ...attrs, class: ["seat-badge", attrs.class, { active: props.active }] }, [
        h("span", props.player.rating),
        h("strong", props.player.name),
      ]);
  },
});

const rankedValues = computed(() => {
  const rows = Object.entries(qValues.value).sort((a, b) => b[1] - a[1]);
  if (!rows.length) return [];
  const values = rows.map(([, value]) => value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  return rows.slice(0, 7).map(([tile, value]) => ({
    tile,
    value,
    width: max === min ? 100 : Math.round(((value - min) / (max - min)) * 100),
  }));
});

const roundName = computed(() => `East ${kyoku.value}`);

const centerSeats = computed(() => [
  { wind: "West", score: players.value[2].score, className: "score-card-top" },
  { wind: "South", score: players.value[1].score, className: "score-card-right" },
  { wind: "East", score: players.value[0].score, className: "score-card-bottom" },
  { wind: "North", score: players.value[3].score, className: "score-card-left" },
]);

function buildWall() {
  const tiles = [];
  for (const suit of SUITS) {
    for (let rank = 1; rank <= 9; rank += 1) {
      for (let copy = 0; copy < 4; copy += 1) tiles.push(`${rank}${suit}`);
    }
  }
  for (const honor of HONORS) {
    for (let copy = 0; copy < 4; copy += 1) tiles.push(honor);
  }
  for (let i = tiles.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [tiles[i], tiles[j]] = [tiles[j], tiles[i]];
  }
  return tiles;
}

function tileSortKey(tile) {
  if (HONORS.includes(tile)) return [3, HONORS.indexOf(tile)];
  return [SUITS.indexOf(tile[1]), Number(tile[0])];
}

function sortHand(hand) {
  hand.sort((a, b) => {
    const ka = tileSortKey(a);
    const kb = tileSortKey(b);
    return ka[0] - kb[0] || ka[1] - kb[1];
  });
}

function scoreAfterDiscard(hand, discardTile) {
  const remaining = [...hand];
  remaining.splice(remaining.indexOf(discardTile), 1);
  const counts = new Map();
  for (const tile of remaining) counts.set(tile, (counts.get(tile) || 0) + 1);

  let score = 0;
  for (const [tile, count] of counts) {
    if (count >= 2) score += 2.5 * (count - 1);
    if (HONORS.includes(tile)) continue;

    const rank = Number(tile[0]);
    const suit = tile[1];
    if (counts.has(`${rank - 1}${suit}`)) score += 1;
    if (counts.has(`${rank + 1}${suit}`)) score += 1;
    if (counts.has(`${rank - 2}${suit}`) || counts.has(`${rank + 2}${suit}`)) score += 0.35;
  }
  return score;
}

function randomTile(hand) {
  return hand[Math.floor(Math.random() * hand.length)];
}

function draw(playerId) {
  const tile = wall.value.pop();
  if (!tile) return null;
  players.value[playerId].hand.push(tile);
  sortHand(players.value[playerId].hand);
  return tile;
}

function discard(playerId, tile, reason = "") {
  const player = players.value[playerId];
  const index = player.hand.indexOf(tile);
  if (index < 0) return;
  player.hand.splice(index, 1);
  player.discards.push(tile);
  logMessages.value.push(`${player.name} discarded ${labelTile(tile)}${reason ? `, ${reason}` : ""}.`);
  turn.value = (playerId + 1) % 4;
  window.setTimeout(stepTurn, 420);
}

function discardHuman(tile) {
  if (turn.value !== 0) return;
  discard(0, tile, "human selected");
}

function autoHuman() {
  if (turn.value === 0) discard(0, randomTile(players.value[0].hand), "auto demo");
}

function mortalDecision(hand) {
  const values = {};
  for (const tile of new Set(hand)) values[tile] = scoreAfterDiscard(hand, tile);
  const tile = Object.keys(values).sort((a, b) => {
    const diff = values[b] - values[a];
    if (diff !== 0) return diff;
    const ka = tileSortKey(a);
    const kb = tileSortKey(b);
    return kb[0] - ka[0] || kb[1] - ka[1];
  })[0];
  return { tile, values };
}

function stepTurn() {
  if (!wall.value.length) {
    logMessages.value.push("Exhaustive draw. Start a new round.");
    return;
  }

  const player = players.value[turn.value];
  const drawn = draw(turn.value);
  logMessages.value.push(`${player.name} drew ${turn.value === 0 ? labelTile(drawn) : "a tile"}.`);

  if (turn.value === 0) return;
  if (turn.value === 2) {
    const decision = mortalDecision(player.hand);
    qValues.value = decision.values;
    decisionText.value = `Mortal RL chose ${labelTile(decision.tile)} by preserving the strongest pairs and sequences.`;
    discard(2, decision.tile, "highest action value");
    return;
  }

  discard(turn.value, randomTile(player.hand), "random baseline");
}

function newRound() {
  wall.value = buildWall();
  dora.value = wall.value.pop();
  turn.value = 0;
  qValues.value = {};
  decisionText.value = "Mortal RL will evaluate its next discard.";
  logMessages.value = ["Round started. Choose one tile from your hand."];

  for (const player of players.value) {
    player.hand = [];
    player.discards = [];
  }
  for (let drawNo = 0; drawNo < 13; drawNo += 1) {
    for (let playerId = 0; playerId < 4; playerId += 1) draw(playerId);
  }
  draw(0);
}

onMounted(newRound);
</script>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  background: #090c0b;
  color: #f4f2e8;
  font-family: Georgia, "Times New Roman", serif;
}

.app {
  --tile-h: 6.15vh;
  --tile-w: 4.45vh;
  --small-h: 5vh;
  --small-w: 3.65vh;
  --gap: 0.18vh;
  --wall-lift: 1.05vh;
  --panel: rgba(10, 13, 12, 0.78);
  --line: rgba(255, 255, 255, 0.15);
  --muted: rgba(244, 242, 232, 0.68);
  --gold: #d5b060;
  --blue: #dce6ff;
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(320px, 44vh, 430px);
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #090c0b;
}

.table {
  position: relative;
  height: 100vh;
  min-width: 0;
  overflow: hidden;
  perspective: 120vh;
  background:
    linear-gradient(rgba(255, 255, 255, 0.024) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
    radial-gradient(circle at 50% 50%, #252b28 0, #151917 51%, #080b0a 100%);
  background-size: 9vh 9vh, 9vh 9vh, auto;
}

.table::before {
  position: absolute;
  inset: 7vh 7.4vh 9.2vh;
  border-radius: 2.2vh;
  background:
    radial-gradient(circle at center, rgba(255, 255, 255, 0.055), transparent 45%),
    rgba(255, 255, 255, 0.018);
  box-shadow:
    inset 0 0 8vh rgba(255, 255, 255, 0.025),
    0 0 0 1px rgba(255, 255, 255, 0.035);
  content: "";
  pointer-events: none;
}

.hand {
  display: flex;
  gap: var(--gap);
}

.wall {
  position: absolute;
  z-index: 1;
  display: grid;
  gap: 0;
  filter: drop-shadow(0 1.4vh 1.2vh rgba(0, 0, 0, 0.42));
  transform-style: preserve-3d;
}

.wall-layer {
  display: flex;
  gap: var(--gap);
}

.wall-left .wall-layer,
.wall-right .wall-layer {
  flex-direction: column;
}

.wall .tile {
  filter:
    drop-shadow(0 0.45vh 0.22vh rgba(0, 0, 0, 0.5))
    saturate(0.95);
}

.wall-top .tile,
.wall-bottom .tile {
  width: 5.15vh;
  height: 5.75vh;
}

.wall-left .tile,
.wall-right .tile {
  width: 3.95vh;
  height: 6.9vh;
}

.wall-layer-back {
  opacity: 0.94;
  transform: translate3d(0, 0, 0);
}

.wall-layer-front {
  z-index: 2;
}

.wall-top {
  top: 0.9vh;
  left: 50%;
  transform: translateX(-50%) rotateX(8deg);
  transform-origin: center top;
}

.wall-top .wall-layer-front {
  transform: translate3d(1.35vh, calc(-1 * var(--wall-lift)), 1.6vh);
}

.wall-left,
.wall-right {
  top: 15.2vh;
  grid-template-columns: repeat(2, auto);
}

.wall-left {
  left: 5.2vh;
  transform: rotateY(-8deg);
  transform-origin: left center;
}

.wall-left .wall-layer-front {
  transform: translate3d(calc(-1 * var(--wall-lift)), 1.35vh, 1.6vh);
}

.wall-right {
  right: 5.2vh;
  transform: rotateY(8deg);
  transform-origin: right center;
}

.wall-right .wall-layer-front {
  transform: translate3d(var(--wall-lift), 1.35vh, 1.6vh);
}

.wall-bottom {
  bottom: 17vh;
  left: 50%;
  transform: translateX(-50%) rotateX(-8deg);
  transform-origin: center bottom;
}

.wall-bottom .wall-layer-front {
  transform: translate3d(1.35vh, var(--wall-lift), 1.6vh);
}

.seat {
  position: absolute;
  z-index: 3;
  display: grid;
  gap: 1vh;
}

.seat-top {
  top: 13.5vh;
  left: 50%;
  transform: translateX(-50%);
}

.seat-left {
  left: 29vh;
  top: 43vh;
  transform: rotate(90deg);
  transform-origin: center;
}

.seat-right {
  right: 29vh;
  top: 43vh;
  transform: rotate(-90deg);
  transform-origin: center;
}

.seat-bottom {
  left: 50%;
  bottom: 0.5vh;
  transform: translateX(-50%);
  place-items: center;
}

.hand-bottom {
  padding-bottom: 0.5vh;
}

.hand-bottom .tile {
  width: 5.15vh;
  height: 7.05vh;
}

.seat-bottom .river {
  margin-bottom: 1.6vh;
}

.seat-top .hand {
  justify-self: center;
}

.seat-top .hand .tile {
  width: 5vh;
  height: 5.6vh;
}

.opponent-hand {
  position: absolute;
  z-index: 3;
  display: flex;
  gap: var(--gap);
}

.opponent-hand .tile {
  width: 3.8vh;
  height: 6.65vh;
}

.opponent-hand-left {
  top: 16.4vh;
  left: 13.2vh;
  flex-direction: column;
}

.opponent-hand-right {
  top: 16.4vh;
  right: 13.2vh;
  flex-direction: column;
}

.river {
  display: grid;
  grid-template-columns: repeat(6, var(--small-w));
  grid-auto-rows: var(--small-h);
  gap: var(--gap);
  min-height: calc(var(--small-h) * 2 + var(--gap));
}

.river-side {
  grid-template-columns: repeat(5, var(--small-w));
}

.river-top,
.river-bottom {
  justify-self: center;
}

.tile {
  display: grid;
  place-items: center;
  width: var(--tile-w);
  height: var(--tile-h);
  border: 0;
  border-radius: 0.45vh;
  background: transparent;
  filter: drop-shadow(0 0.35vh 0.25vh rgba(0, 0, 0, 0.45));
  padding: 0;
  user-select: none;
}

.tile.small {
  width: var(--small-w);
  height: var(--small-h);
}

.tile img {
  display: block;
  width: 100%;
  height: 100%;
}


.tile-button {
  cursor: pointer;
  transition: transform 140ms ease, filter 140ms ease;
}

.tile-button:hover {
  transform: translateY(-1.2vh) scale(1.04);
  filter: drop-shadow(0 1vh 0.8vh rgba(213, 176, 96, 0.35));
}

.seat-badge {
  position: absolute;
  z-index: 2;
  min-width: 15vh;
  padding: 1.4vh 1.7vh;
  border-radius: 0.8vh;
  background: rgba(255, 255, 255, 0.055);
  color: rgba(244, 242, 232, 0.52);
  text-align: center;
  font-size: 1.55vh;
}

.seat-badge strong {
  display: block;
  margin-top: 0.3vh;
  color: rgba(244, 242, 232, 0.74);
  font-size: 3.2vh;
  font-weight: 400;
  line-height: 1;
}

.seat-badge.active strong {
  color: var(--gold);
}

.badge-top {
  top: 26.5vh;
  left: 50%;
  transform: translateX(-50%);
}

.badge-left {
  left: 17vh;
  top: 64vh;
  transform: rotate(90deg);
}

.badge-right {
  right: 17vh;
  top: 24vh;
  transform: rotate(-90deg);
}

.center-board {
  position: absolute;
  top: 52vh;
  left: 50%;
  width: 36vh;
  height: 32vh;
  transform: translate(-50%, -50%);
}

.dora {
  position: absolute;
  top: 0;
  left: 50%;
  display: flex;
  align-items: center;
  gap: 0.9vh;
  transform: translateX(-50%);
  color: var(--muted);
  font: 700 1.45vh/1 Arial, sans-serif;
  text-transform: uppercase;
}

.score-board {
  position: absolute;
  inset: 6.2vh 0 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1vh;
  background:
    radial-gradient(circle at center, rgba(244, 242, 232, 0.07), transparent 58%),
    rgba(0, 0, 0, 0.36);
  box-shadow:
    inset 0 0 5vh rgba(255, 255, 255, 0.035),
    0 1.4vh 2.8vh rgba(0, 0, 0, 0.22);
}

.round-core {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 16.8vh;
  min-height: 11.2vh;
  transform: translate(-50%, -50%);
  display: grid;
  place-items: center;
  align-content: center;
  gap: 0.8vh;
  border-radius: 1vh;
  background: rgba(6, 9, 8, 0.52);
  text-align: center;
  padding: 1.5vh 1.2vh;
}

.round-core strong {
  color: var(--blue);
  font-size: 4vh;
  line-height: 1;
  text-shadow: 0 0 1.3vh rgba(95, 121, 255, 0.55);
}

.round-core span {
  color: #f4f2e8;
  font-family: Arial, sans-serif;
  font-size: 1.55vh;
  line-height: 1;
}

.round-core .wall-count {
  color: rgba(244, 242, 232, 0.72);
  font-size: 1.45vh;
}

.score-card {
  position: absolute;
  display: grid;
  grid-template-columns: auto auto;
  align-items: baseline;
  gap: 0.7vh;
  min-width: 10vh;
  border-radius: 0.7vh;
  background: rgba(255, 255, 255, 0.055);
  color: rgba(244, 242, 232, 0.78);
  font-family: Arial, sans-serif;
  font-size: 1.35vh;
  line-height: 1;
  padding: 0.75vh 1vh;
}

.score-card strong {
  color: #f4f2e8;
  font-size: 1.9vh;
  line-height: 1;
}

.score-card-top {
  top: 1.5vh;
  left: 50%;
  transform: translateX(-50%);
}

.score-card-bottom {
  bottom: 1.5vh;
  left: 50%;
  transform: translateX(-50%);
}

.score-card-left {
  top: 50%;
  left: 1.2vh;
  transform: translateY(-50%);
}

.score-card-right {
  top: 50%;
  right: 1.2vh;
  transform: translateY(-50%);
}

.side-panel {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 2.6vh;
  height: 100vh;
  border-left: 1px solid var(--line);
  background: #0d1110;
  padding: 2.8vh;
  overflow: hidden;
  font-family: Arial, sans-serif;
}

.panel-block {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 0.9vh;
  background: var(--panel);
  padding: 2.2vh;
}

.intro {
  padding-top: 2.4vh;
}

h1,
h2,
p,
ol {
  margin: 0;
}

h1 {
  font-size: 2.65vh;
  line-height: 1.15;
}

h2 {
  margin-bottom: 1.8vh;
  color: var(--muted);
  font-size: 1.55vh;
  line-height: 1;
  text-transform: uppercase;
}

p,
.event-log {
  color: rgba(244, 242, 232, 0.78);
  font-size: 1.78vh;
  line-height: 1.35;
}

.controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.4vh;
  margin-top: 2.4vh;
}

button {
  min-height: 5.4vh;
  border: 1px solid var(--line);
  border-radius: 0.7vh;
  background: rgba(255, 255, 255, 0.1);
  color: #f4f2e8;
  cursor: pointer;
  font: 700 1.65vh/1 Arial, sans-serif;
  padding: 0 1.4vh;
}

button:hover {
  border-color: var(--gold);
}

button:disabled {
  cursor: default;
  opacity: 0.45;
}

.q-list {
  display: grid;
  gap: 1vh;
  margin-top: 1.8vh;
}

.q-row {
  display: grid;
  grid-template-columns: 4.5vh 1fr 5.2vh;
  align-items: center;
  gap: 1vh;
  font-size: 1.45vh;
}

.bar {
  height: 0.8vh;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.bar span {
  display: block;
  height: 100%;
  background: #d43f45;
}

.log-block {
  min-height: 0;
}

.event-log {
  display: flex;
  flex-direction: column-reverse;
  gap: 1.1vh;
  height: calc(100% - 3.2vh);
  overflow: auto;
  padding-left: 2.5vh;
}

@media (max-aspect-ratio: 4 / 3) {
  .app {
    grid-template-columns: 1fr;
    grid-template-rows: 100vh auto;
    height: auto;
    overflow: auto;
  }

  .side-panel {
    height: auto;
    min-height: 48vh;
    border-left: 0;
    border-top: 1px solid var(--line);
  }
}
</style>
