"""Reads Pokemon FireRed's memory and turns it into plain Python objects."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from . import addresses as A
from .emulator import Emulator
from .maps import map_name
from .text import decode

TYPE_NAMES = [
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost",
    "Steel", "???", "Fire", "Water", "Grass", "Electric", "Psychic", "Ice",
    "Dragon", "Dark",
]
# In Gen 3, a move is physical or special based only on its type.
PHYSICAL_TYPES = {0, 1, 2, 3, 4, 5, 6, 7, 8}

DIRECTIONS = {1: "down", 2: "up", 3: "left", 4: "right"}
CONNECTION_DIRS = {1: "south", 2: "north", 3: "west", 4: "east"}

# Order of the four 12-byte substructures inside a Pokemon's encrypted data,
# indexed by personality % 24. G=growth, A=attacks, E=EVs, M=misc.
SUBSTRUCT_ORDER = [
    "GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA", "AGEM", "AGME",
    "AEGM", "AEMG", "AMGE", "AMEG", "EGAM", "EGMA", "EAGM", "EAMG",
    "EMGA", "EMAG", "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG",
]

BEHAVIOR_TALL_GRASS = 0x02
WATER_BEHAVIORS = {0x10, 0x11, 0x12, 0x13, 0x15, 0x1A, 0x1B}
LEDGE_BEHAVIORS = {0x38: (1, 0), 0x39: (-1, 0), 0x3A: (0, -1), 0x3B: (0, 1)}  # jump direction
ARROW_WARPS = {0x62: "right", 0x63: "left", 0x64: "up", 0x65: "down"}
BEHAVIOR_COUNTER = 0x80


def status_text(status: int) -> str:
    if status & 0x7:
        return "asleep"
    if status & 0x80:
        return "badly poisoned"
    if status & 0x08:
        return "poisoned"
    if status & 0x10:
        return "burned"
    if status & 0x20:
        return "frozen"
    if status & 0x40:
        return "paralyzed"
    return ""


@dataclass
class Move:
    id: int
    name: str
    pp: int
    power: int
    type: int
    accuracy: int

    @property
    def type_name(self) -> str:
        return TYPE_NAMES[self.type] if self.type < len(TYPE_NAMES) else "?"


@dataclass
class Mon:
    species: int
    species_name: str
    nickname: str
    level: int
    hp: int
    max_hp: int
    status: str
    types: tuple[int, int]
    moves: list[Move]
    attack: int = 0
    defense: int = 0
    sp_attack: int = 0
    sp_defense: int = 0
    speed: int = 0
    is_egg: bool = False

    @property
    def fainted(self) -> bool:
        return self.hp == 0

    def type_names(self) -> str:
        t1, t2 = self.types
        names = [TYPE_NAMES[t1]] if t1 < len(TYPE_NAMES) else []
        if t2 != t1 and t2 < len(TYPE_NAMES):
            names.append(TYPE_NAMES[t2])
        return "/".join(names)

    def summary(self) -> str:
        label = self.nickname if self.nickname.upper() == self.species_name.upper() else f"{self.nickname} ({self.species_name})"
        s = f"{label} Lv{self.level} {self.type_names()} HP {self.hp}/{self.max_hp}"
        if self.status:
            s += f" [{self.status}]"
        if self.fainted:
            s += " [fainted]"
        return s


@dataclass
class Warp:
    x: int
    y: int
    dest_group: int
    dest_num: int

    @property
    def dest_name(self) -> str:
        return map_name(self.dest_group, self.dest_num)


@dataclass
class Connection:
    direction: str
    dest_group: int
    dest_num: int

    @property
    def dest_name(self) -> str:
        return map_name(self.dest_group, self.dest_num)


@dataclass
class NPC:
    local_id: int
    x: int
    y: int
    graphics_id: int
    is_trainer: bool


@dataclass
class MapGrid:
    """Collision/behavior info for the current map, in map coordinates."""
    width: int
    height: int
    blocked: list[list[bool]]      # [y][x]
    behavior: list[list[int]]      # [y][x]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height


@dataclass
class BattleInfo:
    is_trainer: bool
    player: Mon | None
    enemy: Mon | None
    message: str


@dataclass
class GameState:
    mode: str                      # overworld | dialog | battle | party_menu | naming | summary | bag | other
    map_group: int = 0
    map_num: int = 0
    x: int = 0
    y: int = 0
    facing: str = "down"
    surfing: bool = False
    party: list[Mon] = field(default_factory=list)
    money: int = 0
    badges: int = 0
    items: list[tuple[str, int]] = field(default_factory=list)
    key_items: list[str] = field(default_factory=list)
    balls: list[tuple[str, int]] = field(default_factory=list)
    message: str = ""

    @property
    def map_name(self) -> str:
        return map_name(self.map_group, self.map_num)


class Game:
    def __init__(self, emu: Emulator):
        self.emu = emu
        self.species_names: list[str] = []
        self.move_names: list[str] = []
        self.move_data: list[tuple[int, int, int, int]] = []   # power, type, accuracy, pp
        self.species_types: list[tuple[int, int]] = []
        self.item_names: list[str] = []
        self.type_chart: dict[tuple[int, int], float] = {}
        self._attr_cache: dict[tuple[int, int], tuple[list[int], list[int]]] = {}

    # ---- setup ------------------------------------------------------
    def check_rom(self) -> str:
        code = self.emu.read(A.ROM_GAME_CODE, 4).decode("ascii", "replace")
        version = self.emu.u8(A.ROM_VERSION)
        if code != "BPRE":
            raise RuntimeError(
                f"This ROM's game code is {code!r}. PokePlay currently supports "
                "Pokemon FireRed (US), game code BPRE."
            )
        if version != 0:
            print(
                f"WARNING: this is FireRed v1.{version}. PokePlay's addresses are for v1.0; "
                "some features (battle/menu detection) may not work."
            )
        return f"FireRed (US) v1.{version}"

    def load_tables(self) -> None:
        """Read names, move data and the type chart from the ROM itself."""
        raw = self.emu.read(A.gSpeciesNames, A.NUM_SPECIES * 11)
        self.species_names = [decode(raw[i * 11:(i + 1) * 11]) for i in range(A.NUM_SPECIES)]
        if self.species_names[1].upper() != "BULBASAUR":
            raise RuntimeError(
                f"Species table check failed (got {self.species_names[1]!r}). "
                "This ROM doesn't match the expected FireRed v1.0 layout."
            )
        raw = self.emu.read(A.gMoveNames, A.NUM_MOVES * 13)
        self.move_names = [decode(raw[i * 13:(i + 1) * 13]) for i in range(A.NUM_MOVES)]
        raw = self.emu.read(A.gBattleMoves, A.NUM_MOVES * 12)
        self.move_data = [(raw[i * 12 + 1], raw[i * 12 + 2], raw[i * 12 + 3], raw[i * 12 + 4]) for i in range(A.NUM_MOVES)]
        raw = self.emu.read(A.gSpeciesInfo, A.NUM_SPECIES * 28)
        self.species_types = [(raw[i * 28 + 6], raw[i * 28 + 7]) for i in range(A.NUM_SPECIES)]
        raw = self.emu.read(A.gItems, A.NUM_ITEMS * 44)
        self.item_names = [decode(raw[i * 44:i * 44 + 14]) for i in range(A.NUM_ITEMS)]
        raw = self.emu.read(A.gTypeEffectiveness, 0x150)
        for i in range(0, len(raw) - 2, 3):
            atk, dfn, mult = raw[i], raw[i + 1], raw[i + 2]
            if atk == 0xFF:
                break
            if atk == 0xFE:  # Foresight marker; entries after it are Ghost immunities
                continue
            self.type_chart[(atk, dfn)] = mult / 10.0

    # ---- small helpers ------------------------------------------------
    def species_name(self, sid: int) -> str:
        return self.species_names[sid] if 0 <= sid < len(self.species_names) else f"#{sid}"

    def move_name(self, mid: int) -> str:
        return self.move_names[mid] if 0 <= mid < len(self.move_names) else f"move {mid}"

    def item_name(self, iid: int) -> str:
        return self.item_names[iid] if 0 <= iid < len(self.item_names) else f"item {iid}"

    def make_move(self, mid: int, pp: int) -> Move:
        power, mtype, acc, _ = self.move_data[mid] if mid < len(self.move_data) else (0, 0, 100, 0)
        return Move(mid, self.move_name(mid), pp, power, mtype, acc)

    def effectiveness(self, move_type: int, defender_types: tuple[int, int]) -> float:
        t1, t2 = defender_types
        m = self.type_chart.get((move_type, t1), 1.0)
        if t2 != t1:
            m *= self.type_chart.get((move_type, t2), 1.0)
        return m

    def sb1(self) -> int:
        return self.emu.u32(A.gSaveBlock1Ptr)

    def sb2(self) -> int:
        return self.emu.u32(A.gSaveBlock2Ptr)

    def flag(self, flag_id: int) -> bool:
        b = self.emu.u8(self.sb1() + A.SB1_FLAGS + flag_id // 8)
        return bool(b >> (flag_id % 8) & 1)

    def var(self, var_id: int) -> int:
        return self.emu.u16(self.sb1() + A.SB1_VARS + (var_id - 0x4000) * 2)

    # ---- mode -------------------------------------------------------------
    def mode(self) -> str:
        cb2 = self.emu.u32(A.gMain_callback2) & ~1
        if cb2 == A.BattleMainCB2:
            return "battle"
        if cb2 == A.CB2_Overworld:
            return "dialog" if self.emu.u8(A.sLockFieldControls) else "overworld"
        if cb2 == A.CB2_UpdatePartyMenu:
            return "party_menu"
        if cb2 == A.CB2_NamingScreen:
            return "naming"
        if cb2 == A.CB2_RunPokemonSummaryScreen:
            return "summary"
        if cb2 == A.CB2_BagMenuRun:
            return "bag"
        return "other"

    def battle_input(self) -> str:
        """What the battle is waiting for: 'action', 'move', 'target' or ''."""
        func = self.emu.u32(A.gBattlerControllerFuncs) & ~1
        if func == A.HandleInputChooseAction:
            return "action"
        if func == A.HandleInputChooseMove:
            return "move"
        if func == A.HandleInputChooseTarget:
            return "target"
        return ""

    # ---- pokemon ----------------------------------------------------------
    def decode_mon(self, raw: bytes) -> Mon | None:
        personality, ot_id = struct.unpack_from("<II", raw, 0)
        if personality == 0 and ot_id == 0:
            return None
        nickname = decode(raw[8:18])
        checksum = struct.unpack_from("<H", raw, 28)[0]
        key = personality ^ ot_id
        secure = bytearray(raw[32:80])
        for i in range(0, 48, 4):
            word = struct.unpack_from("<I", secure, i)[0] ^ key
            struct.pack_into("<I", secure, i, word)
        if sum(struct.unpack("<24H", secure)) & 0xFFFF != checksum:
            return None
        order = SUBSTRUCT_ORDER[personality % 24]
        growth = secure[order.index("G") * 12:][:12]
        attacks = secure[order.index("A") * 12:][:12]
        misc = secure[order.index("M") * 12:][:12]
        species = struct.unpack_from("<H", growth, 0)[0]
        move_ids = struct.unpack_from("<4H", attacks, 0)
        pps = attacks[8:12]
        is_egg = bool(struct.unpack_from("<I", misc, 4)[0] >> 30 & 1)
        status, = struct.unpack_from("<I", raw, 80)
        level = raw[84]
        hp, max_hp, atk, dfn, spe, spa, spd = struct.unpack_from("<7H", raw, 86)
        types = self.species_types[species] if species < len(self.species_types) else (0, 0)
        moves = [self.make_move(m, pps[i]) for i, m in enumerate(move_ids) if m]
        return Mon(species, self.species_name(species), nickname or self.species_name(species), level, hp,
                   max_hp, status_text(status), types, moves, atk, dfn, spa, spd, spe, is_egg)

    def party(self) -> list[Mon]:
        count = min(self.emu.u8(A.gPlayerPartyCount), 6)
        raw = self.emu.read(A.gPlayerParty, 100 * count)
        mons = []
        for i in range(count):
            mon = self.decode_mon(raw[i * 100:(i + 1) * 100])
            if mon:
                mons.append(mon)
        return mons

    def battle_mon(self, index: int) -> Mon | None:
        raw = self.emu.read(A.gBattleMons + index * 0x58, 0x58)
        species = struct.unpack_from("<H", raw, 0)[0]
        if species == 0:
            return None
        atk, dfn, spe, spa, spd = struct.unpack_from("<5H", raw, 2)
        move_ids = struct.unpack_from("<4H", raw, 0x0C)
        pps = raw[0x24:0x28]
        hp = struct.unpack_from("<H", raw, 0x28)[0]
        max_hp = struct.unpack_from("<H", raw, 0x2C)[0]
        status = struct.unpack_from("<I", raw, 0x4C)[0]
        moves = [self.make_move(m, pps[i]) for i, m in enumerate(move_ids) if m]
        return Mon(species, self.species_name(species), decode(raw[0x30:0x3B]) or self.species_name(species),
                   raw[0x2A], hp, max_hp, status_text(status), (raw[0x21], raw[0x22]), moves,
                   atk, dfn, spa, spd, spe)

    def battle_info(self) -> BattleInfo:
        flags = self.emu.u32(A.gBattleTypeFlags)
        return BattleInfo(
            is_trainer=bool(flags & (1 << 3)),
            player=self.battle_mon(0),
            enemy=self.battle_mon(1),
            message=decode(self.emu.read(A.gDisplayedStringBattle, 0x12C)),
        )

    # ---- bag / money / badges --------------------------------------------
    def _pocket(self, sb1: int, offset: int, slots: int, key: int) -> list[tuple[str, int]]:
        raw = self.emu.read(sb1 + offset, slots * 4)
        out = []
        for i in range(slots):
            item, qty = struct.unpack_from("<HH", raw, i * 4)
            if item:
                out.append((self.item_name(item), qty ^ (key & 0xFFFF)))
        return out

    # ---- map ----------------------------------------------------------------
    def player_object(self) -> tuple[int, int, str]:
        obj_id = self.emu.u8(A.gPlayerAvatar + 5)
        raw = self.emu.read(A.gObjectEvents + obj_id * 0x24, 0x24)
        x, y = struct.unpack_from("<hh", raw, 0x10)
        facing = DIRECTIONS.get(raw[0x18] & 0x0F, "down")
        return x - A.MAP_OFFSET, y - A.MAP_OFFSET, facing

    def npcs(self) -> list[NPC]:
        raw = self.emu.read(A.gObjectEvents, 16 * 0x24)
        out = []
        for i in range(16):
            o = raw[i * 0x24:(i + 1) * 0x24]
            active = o[0] & 1
            invisible = o[1] >> 5 & 1
            is_player = o[2] & 1
            if not active or invisible or is_player:
                continue
            x, y = struct.unpack_from("<hh", o, 0x10)
            out.append(NPC(local_id=o[8], x=x - A.MAP_OFFSET, y=y - A.MAP_OFFSET,
                           graphics_id=o[5], is_trainer=o[7] != 0))
        return out

    def warps(self) -> list[Warp]:
        events = self.emu.u32(A.gMapHeader + 0x04)
        if not events:
            return []
        header = self.emu.read(events, 12)
        count = header[1]
        ptr = struct.unpack_from("<I", header, 8)[0]
        if not count or not ptr:
            return []
        raw = self.emu.read(ptr, count * 8)
        out = []
        for i in range(count):
            x, y, _elev, _warp_id, num, group = struct.unpack_from("<hhBBBB", raw, i * 8)
            out.append(Warp(x, y, group, num))
        return out

    def connections(self) -> list[Connection]:
        conn = self.emu.u32(A.gMapHeader + 0x0C)
        if not conn:
            return []
        count, ptr = struct.unpack("<iI", self.emu.read(conn, 8))
        if count <= 0 or not ptr:
            return []
        raw = self.emu.read(ptr, count * 12)
        out = []
        for i in range(min(count, 8)):
            d = raw[i * 12]
            if d in CONNECTION_DIRS:
                out.append(Connection(CONNECTION_DIRS[d], raw[i * 12 + 8], raw[i * 12 + 9]))
        return out

    def _metatile_attributes(self) -> tuple[list[int], list[int]]:
        layout = self.emu.u32(A.gMapHeader)
        primary, secondary = struct.unpack("<II", self.emu.read(layout + 0x10, 8))
        key = (primary, secondary)
        if key not in self._attr_cache:
            def attrs(tileset: int, count: int) -> list[int]:
                if not tileset:
                    return [0] * count
                ptr = self.emu.u32(tileset + 0x14)
                if not ptr:
                    return [0] * count
                return list(struct.unpack(f"<{count}I", self.emu.read(ptr, count * 4)))
            self._attr_cache[key] = (attrs(primary, A.NUM_METATILES_IN_PRIMARY),
                                     attrs(secondary, 1024 - A.NUM_METATILES_IN_PRIMARY))
        return self._attr_cache[key]

    def map_grid(self) -> MapGrid:
        xsize, ysize, ptr = struct.unpack("<iiI", self.emu.read(A.VMap, 12))
        raw = self.emu.read(ptr, xsize * ysize * 2)
        cells = struct.unpack(f"<{xsize * ysize}H", raw)
        primary, secondary = self._metatile_attributes()
        width = xsize - (2 * A.MAP_OFFSET + 1)
        height = ysize - 2 * A.MAP_OFFSET
        blocked = [[True] * width for _ in range(height)]
        behavior = [[0] * width for _ in range(height)]
        for y in range(height):
            for x in range(width):
                cell = cells[(y + A.MAP_OFFSET) * xsize + x + A.MAP_OFFSET]
                metatile = cell & A.MAPGRID_METATILE_ID_MASK
                if metatile < A.NUM_METATILES_IN_PRIMARY:
                    attr = primary[metatile]
                else:
                    idx = metatile - A.NUM_METATILES_IN_PRIMARY
                    attr = secondary[idx] if idx < len(secondary) else 0
                behavior[y][x] = attr & A.METATILE_BEHAVIOR_MASK
                blocked[y][x] = metatile == A.MAPGRID_UNDEFINED or bool(cell & A.MAPGRID_COLLISION_MASK)
        return MapGrid(width, height, blocked, behavior)

    # ---- everything ----------------------------------------------------------
    def message(self) -> str:
        return decode(self.emu.read(A.gStringVar4, 0x3E8))

    def state_light(self) -> tuple[str, int, int, int, int]:
        """Fast check used while walking: (mode, map group, map num, x, y)."""
        loc = self.emu.read(self.sb1() + A.SB1_LOCATION, 2)
        x, y, _ = self.player_object()
        return self.mode(), loc[0], loc[1], x, y

    def state(self) -> GameState:
        mode = self.mode()
        sb1 = self.sb1()
        sb2 = self.sb2()
        key = self.emu.u32(sb2 + A.SB2_ENCRYPTION_KEY)
        loc = self.emu.read(sb1 + A.SB1_LOCATION, 2)
        s = GameState(mode=mode, map_group=loc[0], map_num=loc[1])
        try:
            s.x, s.y, s.facing = self.player_object()
        except Exception:
            pos = self.emu.read(sb1 + A.SB1_POS, 4)
            s.x, s.y = struct.unpack("<hh", pos)
        s.surfing = bool(self.emu.u8(A.gPlayerAvatar) & A.PLAYER_AVATAR_FLAG_SURFING)
        s.party = self.party()
        s.money = self.emu.u32(sb1 + A.SB1_MONEY) ^ key
        badge_byte = self.emu.u8(sb1 + A.SB1_FLAGS + A.FLAG_BADGE01_GET // 8)
        s.badges = bin(badge_byte).count("1")
        s.items = self._pocket(sb1, A.SB1_BAG_ITEMS, 42, key)
        s.key_items = [name for name, _ in self._pocket(sb1, A.SB1_BAG_KEY_ITEMS, 30, key)]
        s.balls = self._pocket(sb1, A.SB1_BAG_BALLS, 13, key)
        s.message = decode(self.emu.read(A.gStringVar4, 0x3E8))
        return s
