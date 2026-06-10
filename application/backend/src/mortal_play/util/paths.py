"""
Path helpers.

The backend depends on two artifacts that live inside the data-science pipeline
folder `source_code/`:
  1. `source_code/mortal/libriichi.so` — the compiled Rust→Python extension
  2. `source_code/mortal/{model,engine,prelude}.py` — the NN training modules
     we reuse for inference

Both must be resolvable via `sys.path` before we `import libriichi` /
`from model import Brain`. This module locates them relative to the
repository layout and exposes helpers.
"""
from __future__ import annotations
import sys
from pathlib import Path


def repo_root() -> Path:
    """Path to the top-level `Mortal-for-mahjong/` checkout."""
    # application/backend/src/mortal_play/util/paths.py
    # → ../../../../../  (5 levels up: util → mortal_play → src → backend → application → repo_root)
    return Path(__file__).resolve().parents[5]


def mortal_python_dir() -> Path:
    """Path to `source_code/mortal/`, the training-side Python directory."""
    return repo_root() / "source_code" / "mortal"


def default_weights_path() -> Path:
    return repo_root() / "mortal_best.pth"


def ensure_libriichi_importable() -> None:
    """Add the training Python dir to sys.path so `import libriichi`
    (and `model`, `engine`) work. Idempotent."""
    p = str(mortal_python_dir())
    if p not in sys.path:
        sys.path.insert(0, p)
