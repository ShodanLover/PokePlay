"""Run with:  python -m pokeplay            (play)
            python -m pokeplay --inspect  (just print what the bot sees, to test the setup)"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import time


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
    parser.add_argument("--list-voices", action="store_true", help="show the voices you can use")
    parser.add_argument("--get-voice", metavar="NAME", help="download a free Piper voice and switch to it")
    parser.add_argument("--test-voice", action="store_true", help="say a test line with your current voice settings")
    args = parser.parse_args()

    if args.list_voices:
        from .voices import list_voices
        return list_voices()
    if args.get_voice:
        from .voices import get_voice
        return get_voice(args.get_voice, args.config)

    from .config import load_config
    cfg = load_config(args.config)

    if args.test_voice:
        from .narrator import Narrator
        v = cfg.voice
        n = Narrator(v.engine, v.piper_model, v.rate, gender=v.gender, volume=v.volume,
                     voice_name=v.voice_name, piper_exe=v.piper_exe)
        n.say("Hi! This is what I sound like. Is this too loud, or just right?")
        time.sleep(0.5)
        n.wait_until_quiet(30)
        return 0

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
