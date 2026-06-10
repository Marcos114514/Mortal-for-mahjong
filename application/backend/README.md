# Backend — Mortal Gameplay Server

```
backend/
├── pyproject.toml
└── src/
    └── mortal_play/
        ├── __main__.py            ← `python -m mortal_play`
        ├── api/                   FastAPI + WebSocket layer
        │   ├── server.py             app, lifespan, /ping, /play
        │   └── ws_session.py         one game session per connection
        ├── core/                  Rules-aware game driver
        │   ├── game_master.py        GameMaster (turn driver)
        │   └── scoring.py            simplified hora deltas
        ├── agents/                Per-seat decision makers
        │   ├── base.py               Agent protocol
        │   ├── mortal_agent.py       wraps libriichi.mjai.Bot (Mortal NN)
        │   ├── random_agent.py       uniform legal-action picker
        │   └── human_agent.py        state only; reactions via WebSocket
        ├── ai/                    Mortal NN engine loading
        │   └── engine_loader.py      load mortal_best.pth → MortalEngine
        └── util/
            ├── paths.py              locate libriichi.so / training modules
            └── tiles.py              tile names, sort key, hand_to_tiles
```

## Run

From the repo root:

```bash
./application/scripts/run-backend.sh                 # uses source_code/.venv
# or directly:
PYTHONPATH=application/backend/src \
  source_code/.venv/bin/python -m mortal_play --port 8001
```

(The Python venv lives at `source_code/.venv/`. See top-level `README.md` for
one-time setup.)

## Endpoints

- `GET /ping` — `{"ok": true, "mortal_loaded": bool}`
- `WS /play` — open a game session

Each event sent on the WebSocket is a standard mjai event plus two extras:

- `_cans` — legal-action flags from the human seat's `PlayerState.last_cans`
- `_your_turn` — `true` iff the GM is awaiting a reaction *for this event*

The frontend must only send a reaction when `_your_turn=true`. Sending
unsolicited messages will end up consumed by a later prompt and desync the game.
