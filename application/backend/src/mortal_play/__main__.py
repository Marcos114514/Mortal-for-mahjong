"""CLI entry: `python -m mortal_play [--port 8001 ...]`"""
from .api import run_from_cli

if __name__ == "__main__":
    run_from_cli()
