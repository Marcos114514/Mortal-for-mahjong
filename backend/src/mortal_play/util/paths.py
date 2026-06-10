"""
Path helpers.

The backend depends on two artifacts that live inside the upstream `Mortal/`
checkout:
  1. `mortal/libriichi.so` — the compiled Rust → Python extension
  2. `mortal/{model,engine,prelude}.py` — the NN training modules we reuse

Both have to be resolvable via `sys.path` before we `import libriichi` /
`from model import Brain`. This module finds the `Mortal/mortal/` directory
relative to this repository's layout and exposes a function to add it.
"""
from __future__ import annotations
import sys
from pathlib import Path


def repo_root() -> Path:
    """Path to the top-level `Mortal-for-mahjong/` checkout."""
    # backend/src/mortal_play/util/paths.py → ../../../../
    return Path(__file__).resolve().parents[4]


def mortal_python_dir() -> Path:
    """Path to `Mortal/mortal/`, the upstream training-side Python directory."""
    return repo_root() / "Mortal" / "mortal"


def default_weights_path() -> Path:
    return repo_root() / "mortal_best.pth"


def ensure_libriichi_importable() -> None:
    """Add `Mortal/mortal/` to sys.path so `import libriichi` (and `model`,
    `engine`) work. Idempotent."""
    p = str(mortal_python_dir())
    if p not in sys.path:
        sys.path.insert(0, p)
