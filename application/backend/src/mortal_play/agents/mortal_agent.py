"""Mortal NN-driven seat (wraps libriichi.mjai.Bot)."""
from __future__ import annotations
import json
from typing import Optional

from ..util.paths import ensure_libriichi_importable
ensure_libriichi_importable()

from libriichi.state import PlayerState  # noqa: E402
from libriichi.mjai import Bot           # noqa: E402


class MortalAgent:
    """
    Owns a libriichi.mjai.Bot for decisions. Bot.react performs PlayerState
    updates internally, so we may call it at most once per event. We mirror
    the state into our own PlayerState so the GM can introspect last_cans.
    """

    def __init__(self, engine, player_id: int):
        self.player_id = player_id
        self.bot = Bot(engine, player_id)
        self.state = PlayerState(player_id)
        self._pending_event: Optional[str] = None

    def observe(self, event_json: str):
        cans = self.state.update(event_json)
        # Defer the Bot.react call: decide() (with can_act=True) or flush()
        # (with can_act=False) will feed it the event.
        self._pending_event = event_json
        return cans

    def decide(self, last_event: dict) -> Optional[dict]:
        if self._pending_event is None:
            return None
        result = self.bot.react(self._pending_event, can_act=True)
        self._pending_event = None
        return None if result is None else json.loads(result)

    def flush(self) -> None:
        if self._pending_event is not None:
            self.bot.react(self._pending_event, can_act=False)
            self._pending_event = None
