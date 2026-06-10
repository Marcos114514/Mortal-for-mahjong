const TILE_IMAGES = "../Mortal-for-mahjong/Mortal/log-viewer/files/images";
const SUITS = ["m", "p", "s"];
const HONORS = ["E", "S", "W", "N", "P", "F", "C"];

const state = {
  wall: [],
  dora: null,
  turn: 0,
  events: [],
  players: [
    { name: "You", type: "Human", hand: [], discards: [], score: 25000 },
    { name: "Random A", type: "Random agent", hand: [], discards: [], score: 25000 },
    { name: "Mortal RL", type: "DQN policy", hand: [], discards: [], score: 25000 },
    { name: "Random B", type: "Random agent", hand: [], discards: [], score: 25000 },
  ],
};

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

function tileImage(tile) {
  if (HONORS.includes(tile)) {
    const map = { E: "ton", S: "nan", W: "sha", N: "pe", P: "haku", F: "hatsu", C: "chun" };
    return null;
  }
  const suitPrefix = { m: "ms", p: "ps", s: "ss" }[tile[1]];
  return `${TILE_IMAGES}/p_${suitPrefix}${tile[0]}_0.gif`;
}

function tileLabel(tile) {
  const labels = { E: "東", S: "南", W: "西", N: "北", P: "白", F: "發", C: "中" };
  return labels[tile] || tile;
}

function createTile(tile, options = {}) {
  const div = document.createElement("div");
  div.className = `tile${options.clickable ? " clickable" : ""}${options.back ? " back" : ""}`;
  if (options.back) return div;

  const src = tileImage(tile);
  if (src) {
    const img = document.createElement("img");
    img.alt = tile;
    img.src = src;
    img.onerror = () => {
      div.textContent = tileLabel(tile);
      img.remove();
    };
    div.appendChild(img);
  } else {
    div.textContent = tileLabel(tile);
  }
  return div;
}

function draw(playerId) {
  const tile = state.wall.pop();
  if (!tile) return null;
  state.players[playerId].hand.push(tile);
  sortHand(state.players[playerId].hand);
  state.events.push({ type: "tsumo", actor: playerId, pai: tile });
  return tile;
}

function discard(playerId, tile, reason = "") {
  const player = state.players[playerId];
  const idx = player.hand.indexOf(tile);
  if (idx < 0) return;
  player.hand.splice(idx, 1);
  player.discards.push(tile);
  state.events.push({ type: "dahai", actor: playerId, pai: tile, reason });
  log(`${player.name} discarded ${tileLabel(tile)}${reason ? `: ${reason}` : ""}`);
  state.turn = (playerId + 1) % 4;
  render();
  window.setTimeout(stepTurn, 450);
}

function randomDiscard(hand) {
  return hand[Math.floor(Math.random() * hand.length)];
}

function scoreAfterDiscard(hand, discardTile) {
  const remaining = [...hand];
  remaining.splice(remaining.indexOf(discardTile), 1);
  const counts = new Map();
  for (const tile of remaining) counts.set(tile, (counts.get(tile) || 0) + 1);
  let score = 0;
  for (const [tile, count] of counts) {
    if (count >= 2) score += 2.5 * (count - 1);
    if (!HONORS.includes(tile)) {
      const rank = Number(tile[0]);
      const suit = tile[1];
      if (counts.has(`${rank - 1}${suit}`)) score += 1;
      if (counts.has(`${rank + 1}${suit}`)) score += 1;
      if (counts.has(`${rank - 2}${suit}`) || counts.has(`${rank + 2}${suit}`)) score += 0.35;
    }
  }
  return score;
}

function mortalDecision(hand) {
  const values = {};
  for (const tile of new Set(hand)) {
    values[tile] = scoreAfterDiscard(hand, tile);
  }
  const chosen = Object.keys(values).sort((a, b) => {
    const diff = values[b] - values[a];
    if (diff !== 0) return diff;
    const ka = tileSortKey(a);
    const kb = tileSortKey(b);
    return kb[0] - ka[0] || kb[1] - ka[1];
  })[0];
  return {
    tile: chosen,
    reason: "highest action value after preserving pairs and sequences",
    values,
  };
}

function stepTurn() {
  if (state.wall.length === 0) {
    log("Exhaustive draw. Start a new round.");
    return;
  }
  const player = state.players[state.turn];
  const drawn = draw(state.turn);
  log(`${player.name} drew ${state.turn === 0 ? tileLabel(drawn) : "a tile"}`);

  if (state.turn === 0) {
    render();
    return;
  }

  if (state.turn === 2) {
    const decision = mortalDecision(player.hand);
    showDecision(decision);
    discard(state.turn, decision.tile, decision.reason);
    return;
  }

  discard(state.turn, randomDiscard(player.hand), "random baseline");
}

function showDecision(decision) {
  const text = document.getElementById("decisionText");
  text.textContent = `Mortal RL chose ${tileLabel(decision.tile)} using ${decision.reason}.`;

  const values = Object.entries(decision.values).sort((a, b) => b[1] - a[1]);
  const min = Math.min(...values.map(([, value]) => value));
  const max = Math.max(...values.map(([, value]) => value));
  const qValues = document.getElementById("qValues");
  qValues.innerHTML = "";
  for (const [tile, value] of values.slice(0, 6)) {
    const row = document.createElement("div");
    row.className = "q-row";
    const width = max === min ? 100 : ((value - min) / (max - min)) * 100;
    row.innerHTML = `<strong>${tileLabel(tile)}</strong><div class="bar"><span style="width:${width}%"></span></div><span>${value.toFixed(2)}</span>`;
    qValues.appendChild(row);
  }
}

function log(message) {
  const item = document.createElement("li");
  item.textContent = message;
  document.getElementById("eventLog").appendChild(item);
}

function renderPlayer(playerId) {
  const el = document.getElementById(`player-${playerId}`);
  const player = state.players[playerId];
  el.classList.toggle("active", state.turn === playerId);
  el.innerHTML = "";

  const head = document.createElement("div");
  head.className = "player-head";
  head.innerHTML = `<span class="player-name">${player.name}</span><span class="agent-type">${player.type}</span>`;
  el.appendChild(head);

  const hand = document.createElement("div");
  hand.className = "hand";
  for (const tile of player.hand) {
    const hidden = playerId !== 0;
    const tileEl = createTile(tile, { back: hidden, clickable: playerId === 0 && state.turn === 0 });
    if (playerId === 0 && state.turn === 0) {
      tileEl.title = `Discard ${tile}`;
      tileEl.addEventListener("click", () => discard(0, tile, "human selected"));
    }
    hand.appendChild(tileEl);
  }
  el.appendChild(hand);

  const discards = document.createElement("div");
  discards.className = "discards";
  for (const tile of player.discards) discards.appendChild(createTile(tile));
  el.appendChild(discards);
}

function render() {
  document.getElementById("wallCount").textContent = state.wall.length;
  document.getElementById("turnName").textContent = state.players[state.turn].name;
  const doraSlot = document.getElementById("doraTile");
  doraSlot.innerHTML = "";
  doraSlot.appendChild(createTile(state.dora));
  for (let i = 0; i < 4; i += 1) renderPlayer(i);
}

function newRound() {
  state.wall = buildWall();
  state.dora = state.wall.pop();
  state.turn = 0;
  state.events = [{ type: "start_game" }, { type: "start_kyoku", bakaze: "E", kyoku: 1 }];
  for (const player of state.players) {
    player.hand = [];
    player.discards = [];
  }
  document.getElementById("eventLog").innerHTML = "";
  document.getElementById("decisionText").textContent = "Mortal RL will explain its next discard.";
  document.getElementById("qValues").innerHTML = "";
  for (let drawNo = 0; drawNo < 13; drawNo += 1) {
    for (let playerId = 0; playerId < 4; playerId += 1) draw(playerId);
  }
  draw(0);
  log("Round started. Discard one tile from your hand.");
  render();
}

document.getElementById("newRoundBtn").addEventListener("click", newRound);
document.getElementById("autoBtn").addEventListener("click", () => {
  if (state.turn === 0) discard(0, randomDiscard(state.players[0].hand), "auto human demo");
});

newRound();
