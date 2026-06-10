"""
mortal_play — gameplay backend for the Mortal mahjong AI.

Layered:
  api/     FastAPI / WebSocket layer (entry point: api.server.app)
  core/    GameMaster (rules, scoring) — orchestrates a hanchan
  agents/  Per-seat decision makers (MortalAgent / RandomAgent / HumanAgent)
  ai/      Mortal NN engine loading
  util/    Tile name helpers, path setup
"""
__version__ = "0.1.0"
