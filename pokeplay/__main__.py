"""Run with:  python -m pokeplay            (play)
            python -m pokeplay --inspect  (just print what the bot sees, to test the setup)"""

from __future__ import annotations

import argparse
import datetime
import os
import sys


class _Tee:
    """Copy everything printed to a log file, so you can see what happened while you were away."""

    def __init__(self, stream, path):
        self.stream = stream
        self.file = open(path, "a", encoding="utf-8", buffering=1)

    def write(self, text):
        try:
            self.stream.write(text)
        except UnicodeEncodeError:
            self.stream.write(text.encode("ascii", "replace").decode())
        if text.strip():
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            text = "".join(f"[{stamp}] {line}" if line.strip() else line for line in text.splitlines(True))
        self.file.write(text)

    def flush(self):
        self.stream.flush()
        self.file.flush()


def _keep_awake() -> None:
    """Stop Windows from sleeping while she plays."""
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)


def main() -> int:
    parser = argparse.ArgumentParser(prog="pokeplay", description="An AI that plays Pokémon FireRed and narrates.")
    parser.add_argument("--config", default="config.toml", help="path to config file (default: config.toml)")
    parser.add_argument("--inspect", action="store_true",
                        help="print the game state the bot can see, then exit (no AI needed)")
    args = parser.parse_args()

    from .config import load_config
    cfg = load_config(args.config)

    if args.inspect:
        from .inspect_state import inspect
        return inspect(cfg)

    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"pokeplay-{datetime.date.today()}.log")
    sys.stdout = _Tee(sys.stdout, log_path)
    sys.stderr = _Tee(sys.stderr, log_path)
    _keep_awake()

    from .agent import Agent
    agent = Agent(cfg)
    try:
        agent.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
