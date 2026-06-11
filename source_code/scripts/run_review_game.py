"""Run a single self-play hanchan to produce one mjai log file with meta.q_values.

The OneVsThree arena (libriichi/arena/one_vs_three.rs) writes mjai logs as
.json.gz files where every dahai/reach/pon/chi event is annotated with
meta.q_values, meta.mask_bits, etc. — exactly what the log-viewer expects.

Usage:
    cd source_code
    source .venv/bin/activate
    cd mortal
    MORTAL_CFG=../scripts/_review_config.toml python ../scripts/run_review_game.py

Outputs:
    source_code/scripts/out/review_logs/<seed>_<key>_a.json.gz
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import torch

# Make `import model`, `import engine`, etc. work no matter where we run from.
HERE = Path(__file__).resolve().parent
MORTAL_DIR = HERE.parent / "mortal"
sys.path.insert(0, str(MORTAL_DIR))
os.chdir(MORTAL_DIR)  # so relative paths in config resolve sensibly

from model import Brain, DQN  # noqa: E402
from engine import MortalEngine  # noqa: E402
from libriichi.arena import OneVsThree  # noqa: E402


def load_engine(weights_path: Path, device: torch.device, name: str) -> MortalEngine:
    state = torch.load(weights_path, weights_only=True, map_location="cpu")
    cfg = state["config"]
    version = cfg["control"].get("version", 1)
    brain = Brain(
        version=version,
        conv_channels=cfg["resnet"]["conv_channels"],
        num_blocks=cfg["resnet"]["num_blocks"],
    ).eval()
    dqn = DQN(version=version).eval()
    brain.load_state_dict(state["mortal"])
    dqn.load_state_dict(state["current_dqn"])
    return MortalEngine(
        brain,
        dqn,
        is_oracle=False,
        version=version,
        device=device,
        enable_amp=False,
        enable_rule_based_agari_guard=True,
        name=name,
    )


def main() -> None:
    repo_root = HERE.parent.parent  # Mortal-for-mahjong/
    weights = repo_root / "mortal_best.pth"
    if not weights.exists():
        sys.exit(f"weights not found: {weights}")

    out_dir = HERE / "out" / "review_logs"
    if out_dir.exists():
        for f in out_dir.iterdir():
            f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device(
        "mps" if torch.backends.mps.is_available()
        else "cuda" if torch.cuda.is_available()
        else "cpu"
    )
    print(f"device: {device}", flush=True)

    challenger = load_engine(weights, device, name="mortal-chal")
    champion = load_engine(weights, device, name="mortal-champ")

    env = OneVsThree(disable_progress_bar=False, log_dir=str(out_dir))
    env.py_vs_py(
        challenger=challenger,
        champion=champion,
        seed_start=(20260611, secrets.randbits(64)),
        seed_count=1,  # one hanchan
    )

    logs = sorted(out_dir.glob("*.json.gz"))
    if not logs:
        sys.exit("self-play produced no log files")
    print("\nWrote:")
    for p in logs:
        print(f"  {p}")
    print(f"\nNext step:\n  python {HERE / 'build_review_html.py'} {logs[0]}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
