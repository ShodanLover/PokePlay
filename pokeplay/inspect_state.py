"""`python -m pokeplay --inspect`: prints everything the bot can read, to check the setup."""

from __future__ import annotations

from .config import Config
from .emulator import Emulator
from .game import Game
from .overworld import Overworld


def inspect(cfg: Config) -> int:
    emu = Emulator(cfg.emulator.host, cfg.emulator.port)
    print("Connecting to mGBA...")
    emu.connect(retry_seconds=10)
    game = Game(emu)
    print("ROM:", game.check_rom())
    game.load_tables()
    print("Data tables OK (species #1 =", game.species_name(1) + ", #4 =", game.species_name(4) + ")")

    s = game.state()
    print(f"\nMode: {s.mode}")
    print(f"Map: {s.map_name} ({s.map_group}.{s.map_num}) at ({s.x},{s.y}) facing {s.facing}")
    print(f"Badges: {s.badges}  Money: {s.money}")
    print("Party:")
    for m in s.party:
        print("  ", m.summary(), "|", ", ".join(f"{mv.name} {mv.pp}pp" for mv in m.moves))
    print("Items:", s.items, "Balls:", s.balls, "Key items:", s.key_items)
    print("Last message:", s.message[:200])

    if s.mode == "overworld":
        world = Overworld(emu, game)
        options, grid = world.build_options(s)
        print(f"\nMap grid {grid.width}x{grid.height} (# = blocked, @ = you, ~ = water, \" = tall grass)")
        npcs = {(n.x, n.y) for n in game.npcs()}
        warps = {(w.x, w.y) for w in game.warps()}
        for y in range(grid.height):
            row = ""
            for x in range(grid.width):
                b = grid.behavior[y][x]
                if (x, y) == (s.x, s.y):
                    row += "@"
                elif (x, y) in npcs:
                    row += "N"
                elif (x, y) in warps:
                    row += "D"
                elif grid.blocked[y][x]:
                    row += "#"
                elif b in (0x10, 0x11, 0x12, 0x13, 0x15):
                    row += "~"
                elif b == 0x02:
                    row += '"'
                else:
                    row += "."
            print("  " + row)
        print("\nOptions the AI would get:")
        for i, o in enumerate(options, 1):
            print(f"  {i}. {o.label} ({o.distance} steps)")
    elif s.mode == "battle":
        info = game.battle_info()
        print("\nBattle:", "trainer" if info.is_trainer else "wild")
        print("  You:", info.player.summary() if info.player else "?")
        print("  Foe:", info.enemy.summary() if info.enemy else "?")
        print("  Waiting for:", game.battle_input() or "(animation/text)")
    emu.close()
    return 0
