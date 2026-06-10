"""
Load a Mortal checkpoint (mortal_best.pth) and wrap it in a MortalEngine.

The Mortal NN code (`Brain` ResNet + `DQN` head + `MortalEngine` adapter)
lives in the data-science pipeline at `source_code/mortal/`. We add it to
sys.path on first import so the flat module names work.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path

import torch

from ..util.paths import ensure_libriichi_importable

log = logging.getLogger("mortal_play.ai")


def select_device() -> torch.device:
    """Pick a torch device. Honor MORTAL_DEVICE env var, else auto."""
    pref = os.environ.get("MORTAL_DEVICE", "").lower()
    if pref == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    if pref == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    if pref == "cpu":
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_mortal_engine(weights_path: str | Path):
    """Read a Mortal checkpoint → instantiate Brain+DQN → wrap in MortalEngine."""
    ensure_libriichi_importable()
    # Late imports — these flat modules live in `source_code/mortal/`.
    from model import Brain, DQN          # type: ignore  # noqa: E402
    from engine import MortalEngine       # type: ignore  # noqa: E402

    device = select_device()
    log.info(f"loading Mortal weights from {weights_path} (device={device})")
    ckpt = torch.load(str(weights_path), weights_only=True, map_location="cpu")
    cfg = ckpt["config"]
    version = cfg["control"].get("version", 1)
    num_blocks = cfg["resnet"]["num_blocks"]
    conv_channels = cfg["resnet"]["conv_channels"]

    brain = Brain(
        version=version, num_blocks=num_blocks, conv_channels=conv_channels,
    ).eval()
    dqn = DQN(version=version).eval()
    brain.load_state_dict(ckpt["mortal"])
    dqn.load_state_dict(ckpt["current_dqn"])

    engine = MortalEngine(
        brain, dqn,
        version=version,
        is_oracle=False,
        device=device,
        enable_amp=False,
        enable_quick_eval=True,
        enable_rule_based_agari_guard=True,
        name="mortal",
    )
    log.info(
        f"Mortal engine ready (v{version}, blocks={num_blocks}, ch={conv_channels})",
    )
    return engine
