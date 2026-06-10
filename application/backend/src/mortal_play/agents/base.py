"""
Common agent contract.

Each seat-agent obeys this interface:

    agent.player_id : int

    agent.observe(event_json: str) -> ActionCandidate
        Update the seat's PlayerState with one mjai event. MUST be called
        exactly once per event, for every agent (so the four PlayerStates
        stay in lock-step with the global game master).

    agent.decide(last_event: dict) -> Optional[dict]
        Choose a reaction. None = "no reaction / pass". For HumanAgent,
        this returns None — the GM awaits the WebSocket instead.

    agent.flush() -> None
        Tidy up after a decision phase. MortalAgent uses this to feed its
        wrapped Bot exactly once per event when no decision was needed.
"""
from __future__ import annotations
from typing import Protocol, Optional, Any


class Agent(Protocol):
    player_id: int

    def observe(self, event_json: str) -> Any: ...
    def decide(self, last_event: dict) -> Optional[dict]: ...
    def flush(self) -> None: ...
