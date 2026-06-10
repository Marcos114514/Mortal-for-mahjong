"""Random seat: picks uniformly from legal mjai actions."""
from __future__ import annotations
import random
from typing import Optional

from ..util.paths import ensure_libriichi_importable
ensure_libriichi_importable()

from libriichi.state import PlayerState  # noqa: E402

from ..util.tiles import (
    hand_to_tiles, pon_consumed, chi_consumed,
)


class RandomAgent:
    def __init__(self, player_id: int, *, seed: Optional[int] = None,
                 riichi_prob: float = 0.3):
        self.player_id = player_id
        self.state = PlayerState(player_id)
        self.rng = random.Random(seed)
        self.riichi_prob = riichi_prob

    def observe(self, event_json: str):
        return self.state.update(event_json)

    def flush(self) -> None:
        pass

    def decide(self, last_event: dict) -> Optional[dict]:
        cans = self.state.last_cans
        if not cans.can_act:
            return None

        # Always agari if possible — random takes the free win.
        if cans.can_tsumo_agari:
            return {"type": "hora", "actor": self.player_id, "target": self.player_id}
        if cans.can_ron_agari:
            return {"type": "hora", "actor": self.player_id,
                    "target": last_event.get("actor", 0)}

        choices: list[dict] = []
        if cans.can_pass:
            choices.append({"type": "none"})

        if cans.can_discard:
            tiles_in_hand = hand_to_tiles(self.state.tehai, self.state.akas_in_hand)
            last_tsumo = self.state.last_self_tsumo()
            for t in set(tiles_in_hand):
                tsumogiri = (last_tsumo is not None and last_tsumo == t)
                choices.append({"type": "dahai", "actor": self.player_id,
                                "pai": t, "tsumogiri": tsumogiri})

        if cans.can_chi_low or cans.can_chi_mid or cans.can_chi_high:
            target = last_event["actor"]
            pai = last_event["pai"]
            tiles = hand_to_tiles(self.state.tehai, self.state.akas_in_hand)
            for kind, ok in [("low", cans.can_chi_low),
                             ("mid", cans.can_chi_mid),
                             ("high", cans.can_chi_high)]:
                if not ok:
                    continue
                consumed = chi_consumed(pai, kind, tiles)
                if consumed:
                    choices.append({"type": "chi", "actor": self.player_id,
                                    "target": target, "pai": pai,
                                    "consumed": consumed})

        if cans.can_pon:
            target = last_event["actor"]
            pai = last_event["pai"]
            tiles = hand_to_tiles(self.state.tehai, self.state.akas_in_hand)
            consumed = pon_consumed(pai, tiles)
            if consumed:
                choices.append({"type": "pon", "actor": self.player_id,
                                "target": target, "pai": pai,
                                "consumed": consumed})

        if cans.can_riichi and self.rng.random() < self.riichi_prob:
            choices.append({"type": "reach", "actor": self.player_id})

        if not choices:
            return None
        return self.rng.choice(choices)
