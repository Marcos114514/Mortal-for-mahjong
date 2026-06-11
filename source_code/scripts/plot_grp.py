"""Plot per-player rank probability over the course of one mjai log.

There are two modes; the script picks automatically based on what's available.

Mode A (preferred) — uses a trained GRP checkpoint:
    For each kyoku boundary, feed the running [grand_kyoku, honba, kyotaku,
    score x4] sequence through the GRU and compute P(player i finishes 1st).
    This is what reward_calculator.py uses internally to shape rewards.

Mode B (fallback) — no GRP weights:
    Plot raw point trajectories per seat. Still useful, just not the same
    quantity.

Usage:
    cd source_code/mortal
    source ../.venv/bin/activate
    pip install matplotlib  # one-time
    python ../scripts/plot_grp.py <log.json[.gz]> [--grp /path/to/grp.pth]

Output:
    source_code/scripts/out/grp_<logname>.png
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
MORTAL_DIR = HERE.parent / "mortal"
sys.path.insert(0, str(MORTAL_DIR))
os.chdir(MORTAL_DIR)  # so libriichi.so resolves


def read_lines(path: Path) -> list[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return [ln for ln in (l.strip() for l in f) if ln]
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def extract_grp_feature(lines: list[str]) -> np.ndarray:
    """Use libriichi.dataset.Grp to recover the per-kyoku feature sequence.

    Each row is [grand_kyoku, honba, kyotaku, s0, s1, s2, s3] (scores in 1e4).
    """
    from libriichi.dataset import Grp  # type: ignore

    raw = "\n".join(lines)
    # Grp.load_log expects a single hanchan's mjai stream.
    games = Grp.load_log(raw)
    if not games:
        raise ValueError("Grp.load_log returned no games — is this a complete hanchan?")
    return games[0].take_feature()


def grp_rank_probs(feature: np.ndarray, grp_state_path: Path) -> np.ndarray:
    """Return matrix[t, player, rank] of P(rank | up to time t)."""
    from model import GRP  # type: ignore

    state = torch.load(grp_state_path, weights_only=True, map_location="cpu")
    # GRP signature must match training; fall back to defaults if config absent.
    network_kwargs = state.get("config", {}).get("grp", {}).get("network", {})
    grp = GRP(**network_kwargs).eval() if network_kwargs else GRP().eval()
    grp.load_state_dict(state["model"])

    seq = [torch.as_tensor(feature[: i + 1]) for i in range(len(feature))]
    with torch.inference_mode():
        logits = grp(seq)
    matrix = grp.calc_matrix(logits)  # (T, 4, 4)
    return matrix.cpu().numpy()


def player_names(lines: list[str]) -> list[str]:
    for ln in lines:
        ev = json.loads(ln)
        if ev.get("type") == "start_game":
            return [n or f"P{i}" for i, n in enumerate(ev.get("names", ["P0", "P1", "P2", "P3"]))]
    return ["P0", "P1", "P2", "P3"]


def plot_rank_prob(matrix: np.ndarray, names: list[str], out_path: Path) -> None:
    import matplotlib.pyplot as plt

    T = matrix.shape[0]
    xs = np.arange(T)

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)

    ax = axes[0]
    for p in range(4):
        ax.plot(xs, matrix[:, p, 0], label=f"{names[p]}", linewidth=2)
    ax.set_ylabel("P(rank = 1st)")
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title("GRP-predicted rank probability over kyoku")

    ax = axes[1]
    for p in range(4):
        expected_rank = (matrix[:, p, :] * np.arange(1, 5)).sum(axis=1)
        ax.plot(xs, expected_rank, label=f"{names[p]}", linewidth=2)
    ax.set_ylabel("E[rank]")
    ax.set_xlabel("kyoku index")
    ax.set_ylim(1, 4)
    ax.invert_yaxis()  # rank 1 on top
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"wrote {out_path}")


def plot_scores_fallback(feature: np.ndarray, names: list[str], out_path: Path) -> None:
    import matplotlib.pyplot as plt

    scores = feature[:, 3:] * 1e4  # (T, 4) raw points
    xs = np.arange(scores.shape[0])

    fig, ax = plt.subplots(figsize=(9, 4))
    for p in range(4):
        ax.plot(xs, scores[:, p], label=names[p], linewidth=2)
    ax.axhline(25000, color="gray", linestyle="--", alpha=0.4, label="start (25000)")
    ax.set_xlabel("kyoku index")
    ax.set_ylabel("points")
    ax.set_title("Per-seat score trajectory (no GRP weights — fallback)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path, help="path to mjai .json or .json.gz")
    parser.add_argument(
        "--grp",
        type=Path,
        default=None,
        help="path to grp.pth checkpoint (optional; falls back to score plot)",
    )
    args = parser.parse_args()
    if not args.log.exists():
        sys.exit(f"log not found: {args.log}")

    lines = read_lines(args.log)
    feature = extract_grp_feature(lines)
    names = player_names(lines)

    out_dir = HERE / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.log.stem.replace(".json", "")
    out_path = out_dir / f"grp_{stem}.png"

    if args.grp and args.grp.exists():
        matrix = grp_rank_probs(feature, args.grp)
        plot_rank_prob(matrix, names, out_path)
    else:
        if args.grp:
            print(f"warn: grp file not found at {args.grp}; using score fallback", file=sys.stderr)
        plot_scores_fallback(feature, names, out_path)


if __name__ == "__main__":
    main()
