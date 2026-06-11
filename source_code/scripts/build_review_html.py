"""Inject one mjai log (with meta.q_values) into the log-viewer template.

The viewer at source_code/log-viewer/index.example.html already renders Q
values for every dahai/reach/pon/chi automatically. It expects the log to
sit inside a JS template literal: `allActions = \`...\``.

Usage:
    python source_code/scripts/build_review_html.py <path-to-mjai.json.gz>

Output:
    source_code/scripts/out/review.html  (open in any browser, no server)
    source_code/scripts/out/files/...    (copied viewer assets)
"""
from __future__ import annotations

import gzip
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEWER_DIR = HERE.parent / "log-viewer"
TEMPLATE = VIEWER_DIR / "index.example.html"


def read_mjai(log_path: Path) -> str:
    """Return the raw mjai text (one JSON event per line)."""
    if log_path.suffix == ".gz":
        with gzip.open(log_path, "rt", encoding="utf-8") as f:
            return f.read().rstrip("\n")
    return log_path.read_text(encoding="utf-8").rstrip("\n")


# Injected before </head> in the rendered review.html. Two goals:
#   1. Replace the upstream `body { transform: scale(2.3) }` with a JS-driven
#      auto-fit so the table never exceeds the viewport.
#   2. Bind ArrowLeft / ArrowRight (and PageDown / PageUp / Space) to the
#      same goBack / goNext functions the existing buttons use.
ENHANCEMENTS = r"""
<style>
  /* Disable the original 2.3x scale and recenter via a stage wrapper. */
  html, body {
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
    background: #1b1b1b;
    color: #ddd;
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
  }
  body {
    transform: none !important;
    height: 100vh;
    width: 100vw;
  }

  /* Wrap the original absolute-positioned .board + .controller-container
     into a single fixed-size stage that we then scale to fit the viewport. */
  #stage {
    position: relative;
    width: 900px;        /* board (550) + controller (~330) + margin */
    height: 600px;       /* board height (550) + a little headroom */
    transform-origin: top left;
  }

  /* Keep absolute coordinates (player rotations rely on them) but place
     them relative to #stage instead of the body. */
  #stage .board { left: 0 !important; top: 0 !important; }
  #stage .controller-container {
    left: 560px !important;
    top: 0 !important;
    width: 330px;
    color: #ddd;
    background: #232323;
    border-radius: 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
  }
  #stage .controller-container button,
  #stage .controller-container select,
  #stage .controller-container input {
    background: #2d2d2d;
    color: #eee;
    border: 1px solid #444;
    border-radius: 3px;
    padding: 3px 8px;
    margin: 2px;
  }
  #stage .controller-container button:hover { background: #3a3a3a; }
  #stage .controller-container table { color: #ddd; }
  #stage .controller-container table th { color: #999; }

  #help {
    position: fixed;
    right: 12px;
    bottom: 8px;
    font-size: 11px;
    color: #777;
    pointer-events: none;
    z-index: 999;
  }
</style>

<script>
  // Wrap the board + controller into #stage and auto-fit to viewport.
  function _setupStage() {
    if (document.getElementById('stage')) return;
    var board = document.querySelector('.board');
    var controller = document.querySelector('.controller-container');
    if (!board || !controller) return;
    var stage = document.createElement('div');
    stage.id = 'stage';
    board.parentNode.insertBefore(stage, board);
    stage.appendChild(board);
    stage.appendChild(controller);

    function fit() {
      var sw = window.innerWidth - 24;
      var sh = window.innerHeight - 24;
      var s = Math.min(sw / 900, sh / 600);
      // Don't blow it up too much on very large monitors.
      s = Math.min(s, 1.6);
      stage.style.transform = 'scale(' + s + ')';
      stage.style.left = Math.max(0, (window.innerWidth - 900 * s) / 2) + 'px';
      stage.style.top = Math.max(0, (window.innerHeight - 600 * s) / 2) + 'px';
      stage.style.position = 'absolute';
    }
    window.addEventListener('resize', fit);
    fit();

    var help = document.createElement('div');
    help.id = 'help';
    help.textContent = '← prev   → next   space=next   home/end=jump';
    document.body.appendChild(help);
  }

  // Keyboard navigation. archive_player.js exposes goNext / goBack as
  // globals (CoffeeScript output declares them with `var` at module scope),
  // so we can reach them through window.
  function _setupKeys() {
    document.addEventListener('keydown', function(e) {
      // Ignore typing inside the "Go" input box.
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
      if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown' || e.key === 'l') {
        e.preventDefault();
        if (typeof goNext === 'function') goNext();
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp' || e.key === 'h') {
        e.preventDefault();
        if (typeof goBack === 'function') goBack();
      } else if (e.key === 'Home') {
        e.preventDefault();
        var sel = document.getElementById('kyokuSelector');
        if (sel) { sel.selectedIndex = 0; sel.dispatchEvent(new Event('change')); }
      } else if (e.key === 'End') {
        e.preventDefault();
        var btn = document.getElementById('last-button');
        if (btn) btn.click();
      }
    });
  }

  // archive_player.js does its DOM setup inside jQuery's $(function(){...}).
  // Run ours after jQuery's, by piggy-backing on the same ready event.
  document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() { _setupStage(); _setupKeys(); }, 0);
  });
</script>
"""


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <log.json[.gz]>")
    log_path = Path(sys.argv[1]).resolve()
    if not log_path.exists():
        sys.exit(f"log not found: {log_path}")
    if not TEMPLATE.exists():
        sys.exit(f"viewer template missing: {TEMPLATE}")

    out_root = HERE / "out"
    out_root.mkdir(parents=True, exist_ok=True)
    out_html = out_root / "review.html"

    # Copy viewer asset folder so relative `files/...` URLs work.
    out_files = out_root / "files"
    if out_files.exists():
        shutil.rmtree(out_files)
    shutil.copytree(VIEWER_DIR / "files", out_files)

    template = TEMPLATE.read_text(encoding="utf-8")
    log_text = read_mjai(log_path)

    # The template has exactly one block of the form:
    #   allActions = `
    #   <events...>
    #   `.trim().split(...)
    # Replace whatever is between the backticks with our log.
    pattern = re.compile(r"(allActions\s*=\s*`)([\s\S]*?)(`)")
    if not pattern.search(template):
        sys.exit("could not locate `allActions = \\`...\\`` in template")
    rendered = pattern.sub(
        lambda m: f"{m.group(1)}\n{log_text}\n{m.group(3)}",
        template,
        count=1,
    )

    # Inject our overrides right before </head>.
    if "</head>" in rendered:
        rendered = rendered.replace("</head>", ENHANCEMENTS + "\n</head>", 1)
    else:
        rendered = ENHANCEMENTS + "\n" + rendered

    out_html.write_text(rendered, encoding="utf-8")
    print(f"wrote {out_html}")
    print(f"open file://{out_html} in a browser")


if __name__ == "__main__":
    main()
