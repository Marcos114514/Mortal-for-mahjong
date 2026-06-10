# Mortal for Mahjong — Interactive 4-Player Riichi Demo

A web-based playable demo of [Mortal](https://github.com/Equim-chan/Mortal),
a deep-RL Japanese Riichi mahjong AI. You sit at the bottom seat. Mortal sits
across from you. The other two seats are simple random bots. Real Tenhou
rules are enforced by **libriichi** (the Rust engine that backs Mortal); the
AI decisions come from a real Mortal checkpoint loaded into PyTorch.

The frontend renders the table in WebGL with Three.js — proper 3D tiles,
real lighting, environment reflections — and talks to the Python backend
over a single WebSocket.

```
┌────────────────────┐         WebSocket / mjai events          ┌──────────────────────┐
│  frontend/         │ ───────────────────────────────────────▶ │  backend/            │
│  Vue 3 + Three.js  │                                          │  FastAPI / asyncio   │
│  (Vite dev server) │ ◀─────────────────────────────────────── │  GameMaster (rules)  │
│                    │                                          │  ↓                   │
│  3D tiles, hand    │                                          │  libriichi.so (Rust) │
│  click → action    │                                          │  PlayerState × 4     │
│                    │                                          │  ↓ obs/mask          │
│                    │                                          │  Mortal NN (PyTorch  │
│                    │                                          │  on MPS / CUDA / CPU)│
└────────────────────┘                                          └──────────────────────┘
```

---

## Repository layout

```
Mortal-for-mahjong/
├── README.md                       ← you are here
├── mortal_best.pth                 ← Mortal v4 checkpoint (40 blocks × 192 ch)
│
├── scripts/                        ← top-level helpers
│   ├── setup.sh                       one-shot first-time setup
│   ├── run-backend.sh                 starts backend on 8001
│   └── run-frontend.sh                starts vite dev server
│
├── backend/                        ← gameplay backend (Python)
│   ├── pyproject.toml
│   ├── README.md
│   └── src/mortal_play/
│       ├── __main__.py                python -m mortal_play
│       ├── api/                       FastAPI + WebSocket
│       │   ├── server.py
│       │   └── ws_session.py
│       ├── core/                      rules + scoring
│       │   ├── game_master.py
│       │   └── scoring.py
│       ├── agents/                    per-seat decision makers
│       │   ├── base.py
│       │   ├── mortal_agent.py
│       │   ├── random_agent.py
│       │   └── human_agent.py
│       ├── ai/
│       │   └── engine_loader.py       load mortal_best.pth → MortalEngine
│       └── util/
│           ├── paths.py
│           └── tiles.py
│
├── frontend/                       ← Vue 3 + Vite frontend
│   ├── package.json
│   ├── index.html
│   ├── vite.config.js
│   ├── public/tiles/                  FluffyStuff SVG tiles (CC-BY)
│   └── src/
│       ├── main.js
│       ├── App.vue                    Three.js scene + state reducer
│       ├── three/
│       │   └── tiles.js               tile geometry & textures
│       ├── net/
│       │   └── ws_client.js           thin WebSocket wrapper
│       ├── components/
│       │   ├── ActionOverlay.vue      ron / tsumo / pon / chi / pass buttons
│       │   └── SidePanel.vue          turn indicator, log, agent decision
│       └── style/                     (reserved)
│
└── Mortal/                         ← upstream Mortal project (mostly untouched)
    ├── libriichi/                     Rust engine source
    ├── target/release/libriichi.dylib (built by setup.sh)
    ├── mortal/                        upstream Python: model.py, engine.py, ...
    │   └── libriichi.so               Rust→Python extension (built by setup.sh)
    ├── .venv/                         Python 3.10 venv (created by setup.sh)
    └── ...                            unchanged training scripts and docs
```

The original Mortal project lives in `Mortal/` and is treated as a vendored
dependency — its training scripts (`train.py`, `client.py`, `server.py`,
etc.) are **untouched**. The new gameplay backend lives in `backend/`,
imports `Brain` / `DQN` / `MortalEngine` from `Mortal/mortal/`, and uses
the compiled `libriichi.so` for rules enforcement.

---

## Tech stack

| Layer            | Tech                                                                 |
|------------------|----------------------------------------------------------------------|
| Frontend         | Vue 3 (Composition API) · Vite 6 · Three.js 0.184 (WebGL)            |
| Tile assets      | [FluffyStuff/riichi-mahjong-tiles](https://github.com/FluffyStuff/riichi-mahjong-tiles) (SVG, CC-BY) |
| 3D effects       | RoundedBoxGeometry + RoomEnvironment for soft reflections            |
| Frontend↔backend | WebSocket, [mjai protocol](https://gimite.net/pukiwiki/index.php?Mjai%20protocol) (JSON events) |
| Backend          | Python 3.10 · FastAPI · uvicorn · asyncio                            |
| Rules engine     | **libriichi** (Rust 2024 edition, PyO3 0.25, compiled cdylib)        |
| AI model         | Mortal v4 (ResNet 40×192 channels) · PyTorch 2.x                     |
| Device           | Apple Silicon → MPS · NVIDIA → CUDA · otherwise CPU                  |
| Env management   | [uv](https://docs.astral.sh/uv/) (Python 3.10 venv)                  |

---

## Prerequisites

* macOS / Linux (Windows works but the setup script is bash)
* `curl`
* Node 20+ for the frontend (Homebrew, NVM, etc.)

You do **not** need to pre-install Rust, Python 3.10, or PyTorch — the
setup script installs them locally without touching system Python.

---

## First-time setup

```bash
git clone <this repo>
cd Mortal-for-mahjong

./scripts/setup.sh
```

That installs Rust (rustup), uv, Python 3.10 + venv (in `Mortal/.venv`) and
builds `libriichi.so`. Then drop the model checkpoint at the repo root:

```
Mortal-for-mahjong/mortal_best.pth
```

(or pass `--weights /path/to/...` to the backend.)

---

## Run

Two terminals.

**Backend**:
```bash
./scripts/run-backend.sh                # listens on 127.0.0.1:8001
```

You should see:
```
... loading Mortal weights from .../mortal_best.pth (device=mps)
... Mortal engine ready (v4, blocks=40, ch=192)
INFO:     Uvicorn running on http://127.0.0.1:8001
```

```bash
curl http://127.0.0.1:8001/ping
# → {"ok":true,"mortal_loaded":true}
```

**Frontend**:
```bash
./scripts/run-frontend.sh               # serves on 127.0.0.1:5726
```

Open http://127.0.0.1:5726/ in a browser.

**Production build** of the frontend:
```bash
cd frontend && npm run build            # → dist/
```

---

## How it works

### Game loop (`backend/src/mortal_play/core/game_master.py`)

`GameMaster.run()` is an async coroutine that drives a **simplified
hanchan** (East 1 → East 4 by default; flip `east_only=False` for full E+S).
Per kyoku:

1. Build the wall, deal 13 tiles per seat, emit `start_kyoku`.
2. Loop: tsumo → actor reaction (`dahai` / `reach` / `hora` / `ryukyoku`)
   → collect calls (`pon` / `chi` / `daiminkan` / `hora`-ron) from the
   other 3 seats → resolve priority (ron > pon ≈ kan > chi).
3. On `hora`: simplified scoring (`scoring.hora_deltas`) — flat 8000 base
   + 100×3 honba bonus + kyotaku (riichi sticks) → winner.
4. On wall exhaustion: ryukyoku (no tenpai/noten payments in v0).
5. Renchan if oya wins, else honba +1, advance kyoku.

> All these decisions happen in pure Python. Only the **legal-action
> detection, agari/yaku enforcement, hand validation, and shanten
> calculation** are delegated to libriichi via `PlayerState`.

### Per-seat agents (`backend/src/mortal_play/agents/`)

Three flavors implementing the same minimal contract
(`observe(event)` → state update, `decide(last_event)` → reaction or None,
`flush()` → cleanup):

* **`MortalAgent`** wraps `libriichi.mjai.Bot`, which feeds the state into
  a `MortalEngine` (PyTorch `Brain` ResNet + `DQN` head) and returns an
  action index that libriichi maps back to a concrete mjai event (with
  dora/aka/kan selection logic).
* **`RandomAgent`** picks uniformly from the legal actions reported by
  `PlayerState.last_cans` — discards, chi/pon, riichi (30%), free hora.
* **`HumanAgent`** doesn't decide on its own — `decide()` returns None and
  the GM awaits a reaction from `gm.human_reactions` (the WebSocket).

### `_your_turn` flag — desync protection

The backend tags each event before sending it down the WebSocket:

```jsonc
{
  "type": "tsumo", "actor": 0, "pai": "5p",
  "_cans": {"can_discard": true, "can_riichi": false, ...},
  "_your_turn": true     // GM is awaiting a human reaction to THIS event
}
```

The frontend only sends a reaction when `_your_turn=true`. This avoids a
desync where unsolicited frontend messages would queue up in
`gm.human_reactions` and get consumed by the next legitimate prompt.

### Frontend state (`frontend/src/App.vue`)

A single Vue 3 component:

* On mount, builds the Three.js scene (table, lights, env reflections) and
  preloads SVG textures into 512px composited tile faces.
* Connects via `createGameClient` (`net/ws_client.js`) and feeds each
  event through `onMjai(ev)`, which mutates `players[i].hand` /
  `discards`, `wall`, `dora`, `turn`, scores, etc.
* `rebuildScene()` re-creates the Three.js tile meshes whenever state
  changes.
* Pointer events: a 3D raycaster identifies which hand-tile group was
  clicked → calls `discardHuman(tile)`.
* `<ActionOverlay>` is shown when `_your_turn=true` and a non-discard
  action is available (Ron / Tsumo / Riichi / Pon / Chi-low/mid/high /
  Pass). Clicking emits an event the parent translates into an mjai
  message.

### mjai protocol (what flows over the WS)

Standard mjai event types: `start_game`, `start_kyoku`, `tsumo`, `dahai`,
`chi`, `pon`, `daiminkan`, `kakan`, `ankan`, `dora`, `reach`,
`reach_accepted`, `hora`, `ryukyoku`, `end_kyoku`, `end_game`. The backend
decorates each event with `_cans` and `_your_turn`; the frontend strips
those before treating the rest as a normal mjai event.

---

## Simplifications vs. real Tenhou rules (current)

| Feature                | Current state                                        |
|------------------------|------------------------------------------------------|
| Yaku enforcement       | ✅ libriichi rejects no-yaku wins (built-in)         |
| Score calculation      | ⚠️ flat 8000 + honba bonus, no real fu/han          |
| Dora indicators        | ⚠️ shown but not added to score                     |
| Aka dora (red 5)       | ⚠️ shown but not added to score                     |
| Riichi (1000-pt stick) | ✅ paid, kyotaku tracked                             |
| Ippatsu / ura dora     | ❌ not yet                                           |
| Ankan / kakan          | ⚠️ skipped by AI seats; backend has no UI yet       |
| Multi-ron (head bump)  | ⚠️ first seat clockwise wins                        |
| Tenpai/noten payments  | ❌ ryukyoku is just 0/0/0/0                          |
| Hanchan structure      | East-only (4 kyoku) by default; toggle in GameMaster |
| West sudden-death (西入)| ❌                                                  |
| Furiten                | ✅ libriichi handles it                              |

These are tracked as future work. None block the game from being playable.

---

## Troubleshooting

**`libriichi.so` import fails** — make sure it was compiled with the same
Python you're running:

```bash
PYO3_PYTHON=$PWD/Mortal/.venv/bin/python \
  cargo build --manifest-path Mortal/Cargo.toml -p libriichi --lib --release
cp Mortal/target/release/libriichi.dylib Mortal/mortal/libriichi.so
```

**Backend says `weights file not found`** — drop `mortal_best.pth` at the
repo root, or pass `--weights /path/to/file` when starting the backend.

**Frontend connects but never sees events** — Open browser devtools →
Network → WS → `play` → Frames. You should see `ready`, `start_game`,
`start_kyoku`, ... If nothing arrives, check the backend log for
exceptions.

**"Address already in use" on 8001** — Either stop the running process or
pass `8002` to `run-backend.sh` and update `WS_URL` in
`frontend/src/App.vue`.

**Game pace too fast / too slow** — Edit `_DEFAULT_AI_DELAY_SEC` in
`backend/src/mortal_play/core/game_master.py` (default 0.6 s between
events).

---

## License

* **Mortal** (Rust + Python training code in `Mortal/`) — AGPL-3.0, ©
  Equim, see `Mortal/LICENSE`.
* **FluffyStuff tile SVGs** in `frontend/public/tiles/` — CC-BY 4.0.
* **Mortal logo and other assets** under `Mortal/docs/` — CC BY-SA 4.0.
* **mj-king.net GIF tiles** in `Mortal/log-viewer/` — see
  `Mortal/log-viewer/files/images/README.txt`.
* **Code added by this project** (`backend/`, `frontend/`, `scripts/`) —
  consider AGPL-3.0 to match upstream.
