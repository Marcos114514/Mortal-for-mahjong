"""
Simplified scoring for v0.

Real Tenhou symbol/han + fu scoring is not implemented. Every win is a flat
8000-point base, plus a 100×3 honba bonus. This is enough for the demo to
have meaningful score deltas without dragging in the full point engine.
"""
from __future__ import annotations

BASE_HAND = 8000


def hora_deltas(winner: int, target: int, honba: int) -> list[int]:
    """
    Return per-seat point deltas after a win.
      Tsumo (winner == target): non-winners each pay BASE_HAND/3 + honba bonus.
      Ron   (winner != target): the discarder alone pays BASE_HAND + honba bonus.
    """
    deltas = [0, 0, 0, 0]
    bonus = honba * 100
    if winner == target:
        per = -(BASE_HAND // 3)
        for i in range(4):
            if i != winner:
                deltas[i] = per - bonus
        deltas[winner] = -sum(deltas)
    else:
        deltas[target] = -BASE_HAND - bonus * 3
        deltas[winner] = BASE_HAND + bonus * 3
    return deltas
