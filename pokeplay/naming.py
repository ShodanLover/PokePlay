"""Types a name on FireRed's on-screen keyboard, one key at a time (viewers see it typed)."""

from __future__ import annotations

import re
import struct

from . import addresses as A
from .emulator import Emulator
from .text import decode

# Keyboard pages, indexed by sNamingScreen->currentPage. SELECT cycles 1 -> 2 -> 0 -> 1.
PAGES = {
    1: ["ABCDEF .", "GHIJKL ,", "MNOPQRS", "TUVWXYZ"],
    2: ["abcdef .", "ghijkl ,", "mnopqrs", "tuvwxyz"],
    0: ["01234", "56789", "!?♂♀/-", "…“”‘'"],
}
PAGE_COLUMNS = {1: 8, 2: 8, 0: 6}

TYPEABLE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?/-'")

KIND_BY_TEMPLATE = {0: "player", 1: "box", 2: "caught", 3: "nickname", 4: "rival"}
MAX_CHARS = {"player": 7, "rival": 7, "box": 8, "caught": 10, "nickname": 10}


def key_position(ch: str, prefer_page: int = 1) -> tuple[int, int, int] | None:
    """(page, x, y) of a character on the keyboard, or None if it can't be typed."""
    for page in sorted(PAGES, key=lambda p: p != prefer_page):
        rows = PAGES[page]
        for y, row in enumerate(rows):
            x = row.find(ch)
            if x != -1:
                return page, x, y
    return None


def clean_name(name: str, max_chars: int) -> str:
    name = "".join(c for c in name if c in TYPEABLE or c.isspace())
    name = re.sub(r"\s+", " ", name).strip()
    return name[:max_chars].strip()


class NamingScreen:
    def __init__(self, emu: Emulator):
        self.emu = emu

    def _base(self) -> int:
        return self.emu.u32(A.sNamingScreen)

    def info(self) -> tuple[str, int]:
        """(kind of name, species for nicknames)."""
        base = self._base()
        template = self.emu.u8(base + A.NS_TEMPLATE_NUM)
        species = self.emu.u16(base + A.NS_MON_SPECIES)
        return KIND_BY_TEMPLATE.get(template, "player"), species

    def typed(self) -> str:
        return decode(self.emu.read(self._base() + A.NS_TEXT_BUFFER, 0x10))

    def _typed_count(self) -> int:
        raw = self.emu.read(self._base() + A.NS_TEXT_BUFFER, 0x10)
        return raw.index(0xFF) if 0xFF in raw else len(raw)

    def _page(self) -> int:
        return self.emu.u8(self._base() + A.NS_CURRENT_PAGE)

    def _cursor(self) -> tuple[int, int]:
        sprite_id = self.emu.u8(self._base() + A.NS_CURSOR_SPRITE_ID)
        x, y = struct.unpack("<hh", self.emu.read(A.gSprites + sprite_id * 0x44 + 0x2E, 4))
        return x, y

    def _move_to(self, page: int, tx: int, ty: int) -> bool:
        width = PAGE_COLUMNS[page] + 1          # +1 for the BACK/OK button column
        for _ in range(24):
            x, y = self._cursor()
            if (x, y) == (tx, ty):
                return True
            if x != tx:
                right = (tx - x) % width
                self.emu.press("RIGHT" if right <= width - right else "LEFT", hold=2, wait=5)
            else:
                down = (ty - y) % 4
                self.emu.press("DOWN" if down <= 4 - down else "UP", hold=2, wait=5)
        return False

    def type_name(self, name: str) -> bool:
        kind, _ = self.info()
        name = clean_name(name, MAX_CHARS.get(kind, 7)) or "RED"
        # Clear anything already typed.
        for _ in range(12):
            if not self._typed_count():
                break
            self.emu.press("B", hold=2, wait=8)
        for ch in name:
            pos = key_position(ch, self._page())
            if pos is None:
                continue
            page, x, y = pos
            for _ in range(4):
                if self._page() == page:
                    break
                self.emu.press("SELECT", hold=2, wait=24)   # page swap animation
            if not self._move_to(page, x, y):
                return False
            before = self._typed_count()
            self.emu.press("A", hold=2, wait=10)
            if self._typed_count() == before:
                self.emu.press("A", hold=2, wait=10)
        self.emu.wait_frames(30)                            # let viewers read it
        self.emu.press("START", hold=2, wait=12)            # jump to OK
        self.emu.press("A", hold=2, wait=30)
        return True
