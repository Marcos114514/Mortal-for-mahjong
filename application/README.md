# Application — Deployment

This folder contains everything needed to run the playable demo: the backend
gameplay server, the Vue frontend, and convenience scripts.

```
application/
├── README.md          ← you are here
├── model_link.txt     ← where to get the trained model checkpoint
├── backend/           ← Python FastAPI + WebSocket gameplay server
│   ├── pyproject.toml
│   ├── README.md
│   └── src/mortal_play/
│       ├── api/                FastAPI app + WebSocket session
│       ├── core/               GameMaster (rules) + scoring
│       ├── agents/             MortalAgent / RandomAgent / HumanAgent
│       ├── ai/                 model loading
│       └── util/               tile helpers, path setup
├── frontend/          ← Vue 3 + Vite + Three.js UI
│   ├── package.json
│   ├── index.html
│   ├── public/tiles/           SVG tile assets
│   └── src/
│       ├── App.vue                3D scene + WebSocket client
│       ├── components/            ActionOverlay, SidePanel, ResultModal
│       ├── three/tiles.js         tile geometry and textures
│       └── net/ws_client.js       WebSocket wrapper
└── scripts/
    ├── setup.sh         one-time setup (Rust + Python venv + libriichi.so)
    ├── run-backend.sh   start the backend on 127.0.0.1:8001
    └── run-frontend.sh  start the Vite dev server on 127.0.0.1:5726
```

## Quick start

From the **repo root** (`Mortal-for-mahjong/`):

```bash
# 1) one-time setup (installs Rust, Python 3.10 venv, builds libriichi.so)
./application/scripts/setup.sh

# 2) place the trained model checkpoint at the repo root
#    (see model_link.txt for the download link)

# 3) start backend in one terminal
./application/scripts/run-backend.sh

# 4) start frontend in another terminal
./application/scripts/run-frontend.sh
# → http://127.0.0.1:5726/
```

## How it talks

```
┌────────────────────┐                                          ┌──────────────────────┐
│  frontend (Vue)    │ ── mjai events over WebSocket ──────────▶│  backend (FastAPI)   │
│  Vue 3 + Three.js  │ ◀────────────────────────────────────────│  GameMaster + Mortal │
│  WebSocket client  │                                          │  + libriichi rules   │
└────────────────────┘                                          └──────────────────────┘
                                                                          ↓
                                                        loads source_code/mortal/* + libriichi.so
                                                        loads ../mortal_best.pth (model checkpoint)
```

The backend imports trained-model code from `source_code/mortal/` (the
training pipeline) and uses the compiled `libriichi.so` for rules
enforcement. Both are produced by the data-science pipeline that lives in
`source_code/`.
