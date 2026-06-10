"""
Pure-Python game master for a simplified 4-player riichi hanchan.

Comms with the world via two queues:
  * self.event_bus       — asyncio.Queue[dict]  GM → WebSocket → frontend
  * self.human_reactions — asyncio.Queue[dict]  WebSocket → GM (human seat only)

Each event the GM emits carries a `_your_turn` flag iff the GM is asking the
human to react to THAT specific event next. The frontend only sends a reply
when `_your_turn=True`, avoiding any unsolicited messages that could desync
the queue.

Simplified rules (v0):
  * Wins are flat 8000 + honba bonus (see core/scoring.py).
  * No ankan/kakan from agents (rare).
  * Renchan if oya wins, otherwise honba +1.
  * No tenpai/noten payments on ryukyoku.
  * libriichi PlayerState already enforces "must have a yaku" for can_*_agari,
    so we don't need an extra yaku check here.
"""
from __future__ import annotations
import asyncio
import json
import logging
import random
from typing import Optional

from ..agents import HumanAgent
from ..util.tiles import build_full_pool, sort_tiles, hand_to_tiles
from .scoring import hora_deltas

_HUMAN_TIMEOUT_SEC = 600.0
_DEFAULT_AI_DELAY_SEC = 0.6  # seconds between events; gives the user time to follow

log = logging.getLogger("mortal_play.core.game_master")


class GameMaster:
    def __init__(
        self,
        agents,
        names,
        *,
        seed: Optional[int] = None,
        east_only: bool = False,
        ai_delay_sec: float = _DEFAULT_AI_DELAY_SEC,
    ):
        assert len(agents) == 4
        self.agents = agents
        self.names = list(names)
        self.rng = random.Random(seed)
        self.east_only = east_only
        self.ai_delay_sec = ai_delay_sec
        self.scores = [25000, 25000, 25000, 25000]
        self.bakaze_idx = 0           # 0=East, 1=South
        self.kyoku_num = 1            # 1..4
        self.honba = 0
        self.kyotaku = 0
        self.event_bus: asyncio.Queue[dict] = asyncio.Queue()
        self.human_reactions: asyncio.Queue[dict] = asyncio.Queue()
        # Set by the server when the human clicks "Continue" on the
        # end-of-kyoku modal. Pre-set so the very first kyoku doesn't wait.
        self.continue_event: asyncio.Event = asyncio.Event()
        self.continue_event.set()
        self.human_seat: Optional[int] = next(
            (i for i, a in enumerate(agents) if isinstance(a, HumanAgent)), None,
        )
        self._renchan = False

    # ── public entry ───────────────────────────────────────────────────────
    async def run(self):
        try:
            await self._emit({"type": "start_game", "names": list(self.names)})
            while True:
                await self._run_kyoku()
                if self._is_game_over():
                    break
                self._advance_kyoku()
                # Wait for the human to click "Continue" before starting the
                # next kyoku. The server sets `continue_event` when it
                # receives a {"type": "continue"} message from the client.
                # Skip if there's no human seat (full AI run).
                if self.human_seat is not None:
                    self.continue_event.clear()
                    await self.continue_event.wait()
            await self._emit({"type": "end_game"})
        except Exception:
            log.exception("game master crashed")
            raise

    # ── helpers ────────────────────────────────────────────────────────────
    async def _emit(self, event: dict, *, asking_seat: Optional[int] = None):
        """
        Push `event` to all agents, then to the event bus. `asking_seat` (if
        given) is the seat the GM will ask immediately after this emission;
        the event is tagged with `_your_turn` accordingly.
        """
        ev_json = json.dumps(event)
        for ag in self.agents:
            try:
                ag.observe(ev_json)
            except Exception as e:
                raise RuntimeError(
                    f"agent {ag.player_id} observe failed on {event}: {e}",
                ) from e
        out_event = dict(event)
        out_event["_your_turn"] = (asking_seat == self.human_seat)
        await self.event_bus.put(out_event)
        if self.ai_delay_sec > 0:
            await asyncio.sleep(self.ai_delay_sec)

    def _flush_pending(self) -> None:
        for ag in self.agents:
            ag.flush()

    async def _ask_seat(self, seat: int, last_event: dict) -> Optional[dict]:
        ag = self.agents[seat]
        if seat == self.human_seat:
            try:
                resp = await asyncio.wait_for(
                    self.human_reactions.get(), timeout=_HUMAN_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                return None
            try:
                ag.state.validate_reaction(json.dumps(resp))
                return resp
            except Exception as e:
                # Invalid action from human. Don't deadlock: log it and treat
                # it as a pass / fallback, so the game continues. The user
                # will see the actual outcome (e.g. their fallback discard)
                # and can react to the next prompt.
                log.warning(
                    f"human seat {seat} sent invalid action {resp}: {e}; "
                    f"treating as pass",
                )
                return None
        return ag.decide(last_event)

    # ── kyoku ──────────────────────────────────────────────────────────────
    async def _run_kyoku(self):
        pool = build_full_pool()
        self.rng.shuffle(pool)
        tehais = [sort_tiles(pool[i*13:(i+1)*13]) for i in range(4)]
        idx = 52
        rinshan = pool[idx:idx+4]; idx += 4
        dora_indicators = pool[idx:idx+5]; idx += 5
        ura_indicators = pool[idx:idx+5]; idx += 5
        yama = pool[idx:idx+70]
        oya = (self.kyoku_num - 1) % 4
        bakaze = "E" if self.bakaze_idx == 0 else "S"

        await self._emit({
            "type": "start_kyoku",
            "bakaze": bakaze,
            "dora_marker": dora_indicators[0],
            "kyoku": self.kyoku_num,
            "honba": self.honba,
            "kyotaku": self.kyotaku,
            "oya": oya,
            "scores": list(self.scores),
            "tehais": tehais,
        })
        self._flush_pending()

        result = await self._play_loop(yama)

        renchan = False
        if result["type"] == "hora":
            deltas = hora_deltas(result["actor"], result["target"], self.honba)
            deltas[result["actor"]] += self.kyotaku * 1000
            for i in range(4):
                self.scores[i] += deltas[i]
            self.kyotaku = 0
            await self._emit({
                "type": "hora", "actor": result["actor"], "target": result["target"],
                "deltas": deltas, "ura_markers": [],
            })
            renchan = (result["actor"] == oya)
            self.honba = self.honba + 1 if renchan else 0
        else:
            await self._emit({"type": "ryukyoku", "deltas": [0, 0, 0, 0]})
            self.honba += 1
        self._flush_pending()

        await self._emit({"type": "end_kyoku"})
        self._flush_pending()
        self._renchan = renchan

    async def _play_loop(self, yama: list[str]) -> dict:
        actor = (self.kyoku_num - 1) % 4
        while True:
            if not yama:
                return {"type": "ryukyoku"}

            # ── tsumo ──
            tile = yama.pop()
            tsumo = {"type": "tsumo", "actor": actor, "pai": tile}
            await self._emit(tsumo, asking_seat=actor)

            resp = await self._ask_seat(actor, tsumo)
            self._flush_pending()
            outcome = await self._handle_actor_response(actor, resp)
            if outcome["kind"] == "agari":
                return {"type": "hora", "actor": actor, "target": actor}
            if outcome["kind"] == "ryukyoku":
                return {"type": "ryukyoku"}
            discarded = outcome["discarded"]

            # ── inner: collect calls (chain through if a call happens) ──
            while True:
                call = await self._collect_calls(actor, discarded)
                if call is None:
                    actor = (actor + 1) % 4
                    break
                if call["type"] == "hora":
                    return {"type": "hora", "actor": call["actor"], "target": actor}
                await self._emit(call, asking_seat=call["actor"])
                actor = call["actor"]
                forced = await self._ask_seat(actor, call)
                self._flush_pending()
                forced_outcome = await self._handle_actor_response(
                    actor, forced, must_discard=True,
                )
                discarded = forced_outcome["discarded"]

    async def _handle_actor_response(self, actor: int, resp: Optional[dict],
                                     *, must_discard: bool = False) -> dict:
        if resp is None:
            resp = self._fallback_dahai(actor)

        rtype = resp.get("type")
        if rtype == "hora" and not must_discard:
            return {"kind": "agari"}
        if rtype == "ryukyoku" and not must_discard:
            return {"kind": "ryukyoku"}

        if rtype == "reach":
            await self._emit({"type": "reach", "actor": actor}, asking_seat=actor)
            self._flush_pending()
            resp2 = await self._ask_seat(actor, {"type": "reach", "actor": actor})
            self._flush_pending()
            if resp2 is None or resp2.get("type") != "dahai":
                resp2 = self._fallback_dahai(actor)
            asking_after = self.human_seat if (
                self.human_seat is not None and self.human_seat != actor
            ) else None
            await self._emit(resp2, asking_seat=asking_after)
            self._flush_pending()
            await self._emit({"type": "reach_accepted", "actor": actor})
            self._flush_pending()
            self.scores[actor] -= 1000
            self.kyotaku += 1
            return {"kind": "discard", "discarded": resp2["pai"]}

        if rtype == "dahai":
            asking = self.human_seat if (
                self.human_seat is not None and self.human_seat != actor
            ) else None
            await self._emit(resp, asking_seat=asking)
            self._flush_pending()
            return {"kind": "discard", "discarded": resp["pai"]}

        # unknown response → fallback discard
        fb = self._fallback_dahai(actor)
        asking = self.human_seat if (
            self.human_seat is not None and self.human_seat != actor
        ) else None
        await self._emit(fb, asking_seat=asking)
        self._flush_pending()
        return {"kind": "discard", "discarded": fb["pai"]}

    async def _collect_calls(self, last_actor: int, discarded: str) -> Optional[dict]:
        last_event = {"type": "dahai", "actor": last_actor, "pai": discarded,
                      "tsumogiri": False}
        calls: dict[int, dict] = {}
        for seat in range(4):
            if seat == last_actor:
                continue
            ag = self.agents[seat]
            cans = ag.state.last_cans if hasattr(ag, "state") else None
            if cans is not None and not cans.can_act:
                continue
            resp = await self._ask_seat(seat, last_event)
            if resp is not None and resp.get("type") not in (None, "none"):
                calls[seat] = resp
        self._flush_pending()
        if not calls:
            return None

        # Priority: ron > pon/daiminkan > chi (chi from upstream seat only).
        rons = [(s, c) for s, c in calls.items() if c.get("type") == "hora"]
        if rons:
            rons.sort(key=lambda x: (x[0] - last_actor) % 4)
            return rons[0][1]
        pons = [(s, c) for s, c in calls.items()
                if c.get("type") in ("pon", "daiminkan")]
        if pons:
            return pons[0][1]
        chis = [(s, c) for s, c in calls.items() if c.get("type") == "chi"]
        if chis:
            chi_seat = (last_actor + 1) % 4
            for s, c in chis:
                if s == chi_seat:
                    return c
        return None

    # ── fallbacks / utils ──────────────────────────────────────────────────
    def _fallback_dahai(self, actor: int) -> dict:
        ag = self.agents[actor]
        last_tsumo = ag.state.last_self_tsumo()
        if last_tsumo is not None:
            return {"type": "dahai", "actor": actor, "pai": last_tsumo,
                    "tsumogiri": True}
        tiles = hand_to_tiles(ag.state.tehai, ag.state.akas_in_hand)
        if not tiles:
            return {"type": "dahai", "actor": actor, "pai": "1m", "tsumogiri": False}
        return {"type": "dahai", "actor": actor, "pai": tiles[-1], "tsumogiri": False}

    def _is_game_over(self) -> bool:
        if any(s < 0 for s in self.scores):
            return True
        if self.east_only:
            return self.bakaze_idx == 0 and self.kyoku_num >= 4 and not self._renchan
        return self.bakaze_idx == 1 and self.kyoku_num >= 4 and not self._renchan

    def _advance_kyoku(self) -> None:
        if self._renchan:
            return
        if self.kyoku_num < 4:
            self.kyoku_num += 1
        else:
            self.kyoku_num = 1
            self.bakaze_idx = 1  # → South
