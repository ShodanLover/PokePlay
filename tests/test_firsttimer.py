"""First-timer mode: she picks battle moves herself and learns from what happens."""

import struct

from pokeplay import addresses as A
from pokeplay.battle import BattlePilot
from pokeplay.memory import Memory
from pokeplay.text import encode_simple

from test_core import make_game


def battle_world(message="", player_moves=(33, 55), pps=(35, 25)):
    g = make_game()
    e = g.emu
    e.write(A.gMain_callback2, struct.pack("<I", A.BattleMainCB2 | 1))
    for idx, (species, moves, pp, hp, types) in enumerate([
        (7, player_moves, pps, 30, (11, 11)),        # her Squirtle-like mon
        (74, (33, 0), (35, 0), 40, (5, 4)),          # foe: Rock/Ground
    ]):
        raw = bytearray(0x58)
        struct.pack_into("<H5H", raw, 0, species, 20, 20, 20, 20, 20)
        struct.pack_into("<4H", raw, 0x0C, *(list(moves) + [0] * (4 - len(moves))))
        raw[0x21], raw[0x22] = types
        raw[0x24:0x24 + len(pp)] = bytes(pp)
        struct.pack_into("<H", raw, 0x28, hp)
        raw[0x2A] = 8
        struct.pack_into("<H", raw, 0x2C, 40)
        e.write(A.gBattleMons + idx * 0x58, bytes(raw))
    g.species_names[7] = "SQUIRTLE"
    g.species_names[74] = "GEODUDE"
    g.species_types[74] = (5, 4)
    g.type_chart[(11, 5)] = 2.0
    g.type_chart[(11, 4)] = 2.0
    e.write(A.gDisplayedStringBattle, encode_simple(message) if message else b"\xff")
    return g


def set_input(g, func):
    g.emu.write(A.gBattlerControllerFuncs, struct.pack("<I", func | 1))


def test_she_chooses_the_move():
    g = battle_world()
    seen = {}

    def chooser(info, labels, choices):
        seen["labels"] = labels
        return 1          # pick the second option

    pilot = BattlePilot(g.emu, g, chooser=chooser)
    presses = []
    g.emu.press = lambda k, hold=6, wait=6: presses.append(k)
    set_input(g, A.HandleInputChooseAction)
    pilot.step()
    # She sees names, types and PP, but no power or effectiveness hints.
    assert seen["labels"][0] == "Use MOVE33 (Normal type, 35 PP left)"
    assert seen["labels"][1] == "Use MOVE55 (Water type, 25 PP left)"
    assert seen["labels"][2].startswith("Open your Bag")
    assert seen["labels"][3] == "Switch to a different Pokémon"
    assert seen["labels"][4] == "Try to run away"
    assert not any("effective" in l for l in seen["labels"])
    assert presses[-1] == "A"
    set_input(g, A.HandleInputChooseMove)
    g.emu.write(A.gMoveSelectionCursor, bytes([0]))
    pilot.step()
    assert "RIGHT" in presses       # moved the cursor to slot 1 (top-right)


def test_learns_from_effectiveness_message():
    g = battle_world()
    g.move_names[55] = "WATER GUN"
    pilot = BattlePilot(g.emu, g)
    g.emu.press = lambda *a, **k: None
    g.emu.write(A.gDisplayedStringBattle, encode_simple("SQUIRTLE used WATER GUN!"))
    pilot.step()
    g.emu.write(A.gDisplayedStringBattle, encode_simple("It's super effective!"))
    pilot.step()
    assert pilot.lessons == ["WATER GUN (Water) was super effective against GEODUDE."]


def test_memory_roundtrip(tmp_path):
    m = Memory.load(str(tmp_path / "m.json"))
    m.add_journal("Mom said to visit the professor.")
    m.add_lesson("WATER GUN (Water) was super effective against GEODUDE.")
    m.links["3.0|door@5,5"] = "Professor Oak's Lab"
    m.bump("steps", 12)
    m.save()
    m2 = Memory.load(str(tmp_path / "m.json"))
    assert m2.journal == ["Mom said to visit the professor."]
    assert m2.links["3.0|door@5,5"] == "Professor Oak's Lab"
    assert m2.stats["steps"] == 12
    assert m2.relevant_lessons(["GEODUDE"]) == m.lessons
    assert not m2.add_lesson(m.lessons[0])      # no duplicates
