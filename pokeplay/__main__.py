"""Run with:  python -m pokeplay            (play)
            python -m pokeplay --inspect  (just print what the bot sees, to test the setup)"""

from __future__ import annotations

import argparse
import sys


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

    from .agent import Agent
    agent = Agent(cfg)
    try:
        agent.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
