"""
Tile-name helpers.

mjai uses string tile names: "1m"…"9m", "1p"…, "1s"…, plus "E","S","W","N",
"P" (haku), "F" (hatsu), "C" (chun). A red five is "5mr"/"5pr"/"5sr".

PlayerState.tehai is a length-34 vector of counts in this order:
    0..8   = 1m..9m
    9..17  = 1p..9p
    18..26 = 1s..9s
    27..33 = E S W N P F C
"""
from __future__ import annotations

SUITS: tuple[str, ...] = ("m", "p", "s")
HONORS: tuple[str, ...] = ("E", "S", "W", "N", "P", "F", "C")

TILE_NAMES: tuple[str, ...] = tuple(
    [f"{i+1}m" for i in range(9)]
    + [f"{i+1}p" for i in range(9)]
    + [f"{i+1}s" for i in range(9)]
    + list(HONORS)
)


def strip_aka(t: str) -> str:
    """Return tile name without the trailing 'r' marker (red 5 → 5)."""
    return t[:-1] if t.endswith("r") else t


def hand_to_tiles(tehai_counts, akas_in_hand) -> list[str]:
    """
    PlayerState.tehai (counts[34]) + akas_in_hand ([aka5m, aka5p, aka5s])
    → list of mjai tile strings, with "5mr"/"5pr"/"5sr" for the aka 5s.
    """
    out: list[str] = []
    aka_left = list(akas_in_hand)
    for tid, cnt in enumerate(tehai_counts):
        if cnt <= 0:
            continue
        name = TILE_NAMES[tid]
        if name in ("5m", "5p", "5s"):
            ai = ("5m", "5p", "5s").index(name)
            if aka_left[ai]:
                out.extend([name + "r"] + [name] * (cnt - 1))
                aka_left[ai] = False
                continue
        out.extend([name] * cnt)
    return out


def sort_key(t: str):
    """Stable sort key for an mjai tile string."""
    base = strip_aka(t)
    if base[0].isdigit():
        return (SUITS.index(base[1]), int(base[0]), 0 if t.endswith("r") else 1)
    return (3, HONORS.index(base), 0)


def sort_tiles(tiles: list[str]) -> list[str]:
    return sorted(tiles, key=sort_key)


def pon_consumed(pai: str, tiles_in_hand: list[str]) -> list[str] | None:
    """Pick two tiles from `tiles_in_hand` matching `pai` (ignoring aka mark)."""
    base = strip_aka(pai)
    same = [t for t in tiles_in_hand if strip_aka(t) == base]
    if len(same) < 2:
        return None
    non_aka = [t for t in same if not t.endswith("r")]
    aka = [t for t in same if t.endswith("r")]
    return (non_aka + aka)[:2]


def chi_consumed(pai: str, kind: str, tiles_in_hand: list[str]) -> list[str] | None:
    """
    Pick two tiles forming a chi with `pai`, where kind ∈ {"low","mid","high"}.
      low:  pai is the lowest of the run  (need pai+1, pai+2)
      mid:  pai is the middle              (need pai-1, pai+1)
      high: pai is the highest             (need pai-2, pai-1)
    """
    base = strip_aka(pai)
    if not base[0].isdigit():
        return None
    rank = int(base[0])
    suit = base[1]
    if kind == "low":
        needed = (rank + 1, rank + 2)
    elif kind == "mid":
        needed = (rank - 1, rank + 1)
    elif kind == "high":
        needed = (rank - 2, rank - 1)
    else:
        return None
    if any(r < 1 or r > 9 for r in needed):
        return None

    remaining = list(tiles_in_hand)
    consumed: list[str] = []
    for r in needed:
        target = f"{r}{suit}"
        idx = next((i for i, t in enumerate(remaining) if t == target), None)
        if idx is None:
            idx = next((i for i, t in enumerate(remaining) if t == target + "r"), None)
        if idx is None:
            return None
        consumed.append(remaining.pop(idx))
    return consumed


def build_full_pool() -> list[str]:
    """The 136-tile pool with one red 5 per numbered suit."""
    pool: list[str] = []
    for suit in SUITS:
        for rank in range(1, 10):
            for copy in range(4):
                pool.append(f"5{suit}r" if rank == 5 and copy == 0 else f"{rank}{suit}")
    for h in HONORS:
        pool.extend([h] * 4)
    return pool
