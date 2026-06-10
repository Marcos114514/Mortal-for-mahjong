"""Human seat: state only, the actual reaction comes from the WebSocket."""
from __future__ import annotations
from typing import Optional

from ..util.paths import ensure_libriichi_importable
ensure_libriichi_importable()

from libriichi.state import PlayerState  # noqa: E402


class HumanAgent:
    def __init__(self, player_id: int):
        self.player_id = player_id
        self.state = PlayerState(player_id)

    def observe(self, event_json: str):
        return self.state.update(event_json)

    def flush(self) -> None:
        pass

    def decide(self, last_event: dict) -> Optional[dict]:
        # GM detects HumanAgent and awaits via gm.human_reactions.
        return None
