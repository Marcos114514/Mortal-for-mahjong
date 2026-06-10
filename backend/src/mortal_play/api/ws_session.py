"""
One WebSocket session = one game.

The session wires together:
  * a GameMaster running an east-only hanchan
  * an outbound task that forwards mjai events from the GM to the WebSocket
  * an inbound task that pushes the human's reactions back to the GM
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from ..core.game_master import GameMaster
from ..agents import HumanAgent, RandomAgent, MortalAgent

log = logging.getLogger("mortal_play.api.ws_session")


def _annotate_event(ev: dict, gm: GameMaster) -> dict:
    """Attach `_cans` (legal-action flags for the human seat) to an event.
    `_your_turn` is set by GameMaster._emit at emit time."""
    out = dict(ev)
    if gm.human_seat is not None:
        try:
            cans = gm.agents[gm.human_seat].state.last_cans
            out["_cans"] = {
                "can_discard": cans.can_discard,
                "can_riichi": cans.can_riichi,
                "can_tsumo_agari": cans.can_tsumo_agari,
                "can_ron_agari": cans.can_ron_agari,
                "can_chi_low": cans.can_chi_low,
                "can_chi_mid": cans.can_chi_mid,
                "can_chi_high": cans.can_chi_high,
                "can_chi": cans.can_chi,
                "can_pon": cans.can_pon,
                "can_kan": cans.can_kan,
                "can_ryukyoku": cans.can_ryukyoku,
                "can_pass": cans.can_pass,
                "can_act": cans.can_act,
            }
        except Exception:
            pass
    return out


async def _forward_events(ws: WebSocket, gm: GameMaster):
    while True:
        ev = await gm.event_bus.get()
        await ws.send_json(_annotate_event(ev, gm))
        if ev.get("type") == "end_game":
            return


async def _receive_reactions(ws: WebSocket, gm: GameMaster):
    while True:
        msg = await ws.receive_text()
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            continue
        await gm.human_reactions.put(data)


def _build_agents(engine):
    """Seats: human at 0, Mortal at 2 (or Random fallback), Random at 1 and 3."""
    human = HumanAgent(0)
    p1 = RandomAgent(1, seed=None)
    if engine is not None:
        p2 = MortalAgent(engine, 2)
        ai_label = "Mortal"
    else:
        p2 = RandomAgent(2, seed=None)
        ai_label = "Random (no model)"
    p3 = RandomAgent(3, seed=None)
    return [human, p1, p2, p3], ai_label


async def play_session(ws: WebSocket, engine: Optional[object]) -> None:
    """Run one full game session over a WebSocket."""
    log.info("client connected")

    agents, ai_label = _build_agents(engine)
    names = ["You", "Random A", ai_label, "Random B"]
    gm = GameMaster(agents, names, east_only=True)

    forward = asyncio.create_task(_forward_events(ws, gm), name="forward")
    receive = asyncio.create_task(_receive_reactions(ws, gm), name="receive")
    game = asyncio.create_task(gm.run(), name="game")

    try:
        await ws.send_json({
            "type": "ready", "human_seat": 0, "ai_label": ai_label,
        })
        done, pending = await asyncio.wait(
            {game, forward, receive},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        for t in done:
            exc = t.exception()
            if exc:
                log.error(f"task {t.get_name()} raised: {exc}")
    except WebSocketDisconnect:
        log.info("client disconnected")
    except Exception:
        log.exception("session error")
    finally:
        for t in (game, forward, receive):
            if not t.done():
                t.cancel()
        try:
            await ws.close()
        except Exception:
            pass
