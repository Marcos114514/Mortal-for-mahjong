"""
FastAPI app. Two endpoints:
  GET  /ping   sanity check
  WS   /play   one-game session (see ws_session.py)
"""
from __future__ import annotations
import argparse
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from ..ai import load_mortal_engine
from ..util.paths import default_weights_path
from .ws_session import play_session

log = logging.getLogger("mortal_play.api.server")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)


_engine = None  # populated on app startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    weights = app.state.weights_path
    if weights and Path(weights).exists():
        try:
            _engine = load_mortal_engine(weights)
        except Exception:
            log.exception(f"failed to load weights at {weights}; AI seat will be Random")
            _engine = None
    else:
        log.warning(f"weights file not found at {weights}; AI seat will be Random")
        _engine = None
    yield
    _engine = None


app = FastAPI(title="Mortal Play API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
async def ping():
    return {"ok": True, "mortal_loaded": _engine is not None}


@app.websocket("/play")
async def play(ws: WebSocket):
    await ws.accept()
    await play_session(ws, _engine)


# ─── CLI entry ───────────────────────────────────────────────────────────────

def run_from_cli(argv: list[str] | None = None):
    parser = argparse.ArgumentParser("mortal_play")
    parser.add_argument(
        "--weights",
        default=os.environ.get("MORTAL_WEIGHTS", str(default_weights_path())),
        help="path to mortal_best.pth",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args(argv)

    app.state.weights_path = args.weights
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
