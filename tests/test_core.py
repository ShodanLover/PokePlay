import struct

from pokeplay.battle import best_move
from pokeplay.game import SUBSTRUCT_ORDER, Game, MapGrid, Mon
from pokeplay.pathfinding import find_path, reachable
from pokeplay.text import decode, encode_simple


class FakeEmu:
    def __init__(self):
        self.mem = {}

    def write(self, addr, data):
        for i, b in enumerate(data):
            self.mem[addr + i] = b

    def read(self, addr, n):
        return bytes(self.mem.get(addr + i, 0) for i in range(n))

    def u8(self, a):
        return self.read(a, 1)[0]

    def u16(self, a):
        return struct.unpack("<H", self.read(a, 2))[0]

    def u32(self, a):
        return struct.unpack("<I", self.read(a, 4))[0]


def test_text_decode():
    assert decode(encode_simple("BULBASAUR")) == "BULBASAUR"
    assert decode(encode_simple("Hello, world!")) == "Hello, world!"
    # Control codes and line breaks are skipped / turned into spaces.
    assert decode(bytes([0xBB, 0xFC, 0x01, 0x02, 0xBC, 0xFE, 0xBD, 0xFF, 0xBE])) == "AB C"


def build_mon(personality, ot_id, species, moves, pps, level, hp, max_hp, nickname="PIKA"):
    growth = struct.pack("<HHIBBH", species, 0, 1000, 0, 70, 0)
    attacks = struct.pack("<4H4B", *moves, *pps)
    evs = bytes(12)
    misc = bytes(12)
    parts = {"G": growth, "A": attacks, "E": evs, "M": misc}
    order = SUBSTRUCT_ORDER[personality % 24]
    plain = b"".join(parts[c] for c in order)
    checksum = sum(struct.unpack("<24H", plain)) & 0xFFFF
    key = personality ^ ot_id
    enc = b"".join(struct.pack("<I", struct.unpack_from("<I", plain, i)[0] ^ key) for i in range(0, 48, 4))
    raw = bytearray(100)
    struct.pack_into("<II", raw, 0, personality, ot_id)
    raw[8:18] = encode_simple(nickname).ljust(10, b"\xff")
    struct.pack_into("<H", raw, 28, checksum)
    raw[32:80] = enc
    raw[84] = level
    struct.pack_into("<7H", raw, 86, hp, max_hp, 20, 20, 20, 20, 20)
    return bytes(raw)


def make_game():
    g = Game(FakeEmu())
    g.species_names = ["??????????", "BULBASAUR"] + [f"MON{i}" for i in range(2, 412)]
    g.species_types = [(0, 0)] * 412
    g.species_types[1] = (12, 3)   # Grass/Poison
    g.species_types[25] = (13, 13)  # Electric
    g.move_names = [f"MOVE{i}" for i in range(355)]
    g.move_data = [(0, 0, 100, 10)] * 355
    g.move_data[33] = (35, 0, 95, 35)    # Tackle: Normal
    g.move_data[55] = (40, 11, 100, 25)  # Water Gun: Water
    g.move_data[84] = (40, 13, 100, 30)  # Thundershock: Electric
    g.move_data[45] = (0, 0, 100, 40)    # Growl: status
    g.type_chart = {(11, 10): 2.0, (11, 12): 0.5, (13, 11): 2.0, (13, 12): 0.5, (13, 4): 0.0}
    return g


def test_decode_mon_all_orders():
    g = make_game()
    for pid in range(24):
        personality = 0x12345600 + pid * 1  # covers every substructure order
        raw = build_mon(personality, 0xBEEF1234, 25, (84, 45, 0, 0), (30, 40, 0, 0), 12, 30, 35)
        mon = g.decode_mon(raw)
        assert mon is not None, pid
        assert mon.species == 25 and mon.level == 12 and mon.hp == 30 and mon.max_hp == 35
        assert [m.id for m in mon.moves] == [84, 45]
        assert [m.pp for m in mon.moves] == [30, 40]
        assert mon.nickname == "PIKA"


def test_decode_mon_rejects_bad_checksum():
    g = make_game()
    raw = bytearray(build_mon(7, 9, 25, (84, 0, 0, 0), (30, 0, 0, 0), 5, 10, 10))
    raw[40] ^= 0xFF
    assert g.decode_mon(bytes(raw)) is None


def test_best_move_prefers_super_effective():
    g = make_game()
    me = Mon(25, "PIKACHU", "PIKA", 10, 30, 30, "", (13, 13),
             [g.make_move(33, 35), g.make_move(84, 30), g.make_move(45, 40)], 20, 20, 20, 20, 20)
    water_foe = Mon(7, "SQUIRTLE", "SQUIRTLE", 10, 30, 30, "", (11, 11), [], 20, 20, 20, 20, 20)
    ground_foe = Mon(50, "DIGLETT", "DIGLETT", 10, 30, 30, "", (4, 4), [], 20, 20, 20, 20, 20)
    idx, move, _ = best_move(g, me, water_foe)
    assert move.id == 84  # Thundershock vs Water
    idx, move, _ = best_move(g, me, ground_foe)
    assert move.id == 33  # Electric does nothing to Ground; use Tackle


def test_best_move_skips_empty_pp():
    g = make_game()
    me = Mon(25, "PIKACHU", "PIKA", 10, 30, 30, "", (13, 13),
             [g.make_move(33, 35), g.make_move(84, 0)], 20, 20, 20, 20, 20)
    foe = Mon(7, "SQUIRTLE", "SQUIRTLE", 10, 30, 30, "", (11, 11), [], 20, 20, 20, 20, 20)
    assert best_move(g, me, foe)[1].id == 33


def grid_from(rows):
    h, w = len(rows), len(rows[0])
    blocked = [[c == "#" for c in r] for r in rows]
    beh = {".": 0, "#": 0, "~": 0x10, "v": 0x3B, '"': 0x02, ">": 0x38}
    behavior = [[beh.get(c, 0) for c in r] for r in rows]
    return MapGrid(w, h, blocked, behavior)


def test_path_around_walls():
    grid = grid_from([
        ".....",
        ".###.",
        ".#...",
        ".#.#.",
        ".....",
    ])
    path = find_path(grid, (2, 2), {(0, 0)})
    assert path is not None
    x, y = 2, 2
    steps = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
    for d in path:
        x, y = x + steps[d][0], y + steps[d][1]
        assert not grid.blocked[y][x]
    assert (x, y) == (0, 0)


def test_ledges_one_way():
    grid = grid_from([
        "...",
        "vvv",
        "...",
    ])
    down = find_path(grid, (1, 0), {(1, 2)})
    assert down == ["down"]                          # hop the ledge
    assert find_path(grid, (1, 2), {(1, 0)}) is None  # can't climb back up


def test_water_needs_surf():
    grid = grid_from([
        "..~..",
    ])
    assert find_path(grid, (0, 0), {(4, 0)}) is None
    assert find_path(grid, (0, 0), {(4, 0)}, surfing=True) is not None


def test_goal_can_be_blocked_door():
    grid = grid_from([
        "#.#",
        "...",
    ])
    grid.blocked[0][1] = True  # a door tile that reads as blocked
    assert find_path(grid, (1, 1), {(1, 0)}) == ["up"]


def test_avoid_npcs():
    grid = grid_from([
        "...",
        "...",
    ])
    dist = reachable(grid, (0, 0), avoid={(1, 0), (1, 1)})
    assert (2, 0) not in dist
