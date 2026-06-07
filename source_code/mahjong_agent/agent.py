"""Project Mahjong agents and Mortal CLI adapter.

This module is intentionally dependency-light so it can run in the course
submission even when the large Mortal model checkpoint is not included.
"""

from __future__ import annotations

import json
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

SUITS = ("m", "p", "s")
HONORS = ("E", "S", "W", "N", "P", "F", "C")


def tile_sort_key(tile: str) -> tuple[int, int]:
    if tile in HONORS:
        return (3, HONORS.index(tile))
    rank = int(tile[0])
    suit = tile[1]
    return (SUITS.index(suit), rank)


def normalize_hand(hand: Iterable[str]) -> list[str]:
    return sorted(hand, key=tile_sort_key)


def tile_neighbors(tile: str) -> int:
    if tile in HONORS:
        return 0
    rank = int(tile[0])
    return int(rank > 1) + int(rank < 9)


def hand_score_after_discard(hand: Sequence[str], discard: str) -> float:
    remaining = list(hand)
    remaining.remove(discard)
    counts = {tile: remaining.count(tile) for tile in set(remaining)}
    score = 0.0
    for tile, count in counts.items():
        if count >= 2:
            score += 2.5 * (count - 1)
        if tile not in HONORS:
            rank = int(tile[0])
            suit = tile[1]
            if f"{rank - 1}{suit}" in counts:
                score += 1.0
            if f"{rank + 1}{suit}" in counts:
                score += 1.0
            if f"{rank - 2}{suit}" in counts or f"{rank + 2}{suit}" in counts:
                score += 0.35
    return score


@dataclass
class AgentDecision:
    tile: str
    reason: str
    q_values: dict[str, float]


class RandomAgent:
    name = "Random"

    def choose_discard(self, hand: Sequence[str], events: Sequence[dict] | None = None) -> AgentDecision:
        tile = random.choice(list(hand))
        return AgentDecision(tile=tile, reason="random baseline discard", q_values={tile: 0.0})


class HeuristicMortalFallbackAgent:
    """A deterministic fallback used when Mortal weights cannot be shipped.

    The policy approximates the shape of a value-based agent: every legal
    discard receives a score and the highest-valued action is selected.
    """

    name = "Mortal fallback"

    def choose_discard(self, hand: Sequence[str], events: Sequence[dict] | None = None) -> AgentDecision:
        q_values = {}
        for tile in set(hand):
            q_values[tile] = hand_score_after_discard(hand, tile) - 0.15 * tile_neighbors(tile)
        tile = max(q_values, key=lambda t: (q_values[t], -tile_sort_key(t)[0], -tile_sort_key(t)[1]))
        return AgentDecision(
            tile=tile,
            reason="keeps pairs and connected tiles, discards the least useful tile",
            q_values=dict(sorted(q_values.items(), key=lambda item: tile_sort_key(item[0]))),
        )


class MortalCliAgent:
    """Adapter for Mortal's documented mjai CLI inference.

    The command expects the original Mortal source and a configured
    `mortal/config.toml` pointing to a trained checkpoint.
    """

    name = "Mortal"

    def __init__(self, mortal_dir: str | Path, player_id: int):
        self.mortal_dir = Path(mortal_dir)
        self.player_id = player_id
        self.fallback = HeuristicMortalFallbackAgent()

    def choose_discard(self, hand: Sequence[str], events: Sequence[dict] | None = None) -> AgentDecision:
        events = list(events or [])
        if not events:
            return self.fallback.choose_discard(hand, events)

        proc = subprocess.run(
            ["python", "mortal.py", str(self.player_id)],
            cwd=self.mortal_dir / "mortal",
            input="\n".join(json.dumps(event) for event in events) + "\n",
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            decision = self.fallback.choose_discard(hand, events)
            decision.reason = f"Mortal CLI unavailable; fallback used ({proc.stderr.strip()[:120]})"
            return decision

        actions = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        for action in reversed(actions):
            if action.get("type") == "dahai" and action.get("pai") in hand:
                q_values = {
                    tile: value for tile, value in zip(sorted(set(hand), key=tile_sort_key), action.get("meta", {}).get("q_values", []))
                }
                return AgentDecision(
                    tile=action["pai"],
                    reason="Mortal neural DQN action from mjai event stream",
                    q_values=q_values,
                )
        return self.fallback.choose_discard(hand, events)
