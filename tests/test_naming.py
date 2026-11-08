"""Simulates FireRed's naming keyboard and checks the AI can type names on it."""

import json
import struct

from pokeplay import addresses as A
from pokeplay.naming import PAGE_COLUMNS, PAGES, NamingScreen, clean_name
from pokeplay.text import _TABLE, decode

from test_core import FakeEmu

BASE = 0x02030000
CURSOR_SPRITE = 5
ENCODE = {v: k for k, v in _TABLE.items() if len(v) == 1 and k not in (0xFA, 0xFB, 0xFE, 0xB2, 0xB4)}


class KeyboardSim(FakeEmu):
    """Follows the cursor rules in pokefirered's naming_screen.c."""

    def __init__(self, template=0, species=0):
        super().__init__()
        self.page, self.x, self.y, self.text, self.confirmed = 1, 0, 0, "", None
        self.write(A.sNamingScreen, struct.pack("<I", BASE))
        self.write(BASE + A.NS_TEMPLATE_NUM, bytes([template]))
        self.write(BASE + A.NS_MON_SPECIES, struct.pack("<H", species))
        self.write(BASE + A.NS_CURSOR_SPRITE_ID, bytes([CURSOR_SPRITE]))
        self.sync()

    def sync(self):
        self.write(BASE + A.NS_CURRENT_PAGE, bytes([self.page]))
        self.write(A.gSprites + CURSOR_SPRITE * 0x44 + 0x2E, struct.pack("<hh", self.x, self.y))
        self.write(BASE + A.NS_TEXT_BUFFER, bytes(ENCODE[c] for c in self.text) + b"\xff" * (16 - len(self.text)))

    def press(self, key, hold=6, wait=6):
        cols = PAGE_COLUMNS[self.page]
        if key == "RIGHT":
            self.x = 0 if self.x >= cols else self.x + 1
        elif key == "LEFT":
            self.x = cols if self.x <= 0 else self.x - 1
        elif key in ("UP", "DOWN") and self.x < cols:
            self.y = (self.y + (1 if key == "DOWN" else -1)) % 4
        elif key == "SELECT":
            self.page = (self.page + 1) % 3
            self.x = min(self.x, PAGE_COLUMNS[self.page])
        elif key == "B":
            self.text = self.text[:-1]
        elif key == "START":
            self.x, self.y = cols, 2
        elif key == "A":
            if self.x == cols:
                self.confirmed = self.text
            else:
                row = PAGES[self.page][self.y]
                if self.x < len(row):
                    self.text += row[self.x]
        self.sync()

    def wait_frames(self, n):
        pass


def test_types_mixed_case_name():
    emu = KeyboardSim(template=0)
    assert NamingScreen(emu).type_name("Nova")
    assert emu.confirmed == "Nova"


def test_types_digits_and_clears_old_text():
    emu = KeyboardSim(template=3, species=25)
    emu.text = "OLD"
    emu.sync()
    ns = NamingScreen(emu)
    assert ns.info() == ("nickname", 25)
    assert ns.type_name("Zap 2!")
    assert emu.confirmed == "Zap 2!"


def test_name_is_trimmed_to_limit():
    emu = KeyboardSim(template=4)          # rival: 7 characters max
    NamingScreen(emu).type_name("Bartholomew")
    assert emu.confirmed == "Barthol"
    assert decode(emu.read(BASE + A.NS_TEXT_BUFFER, 16)) == "Barthol"


def test_clean_name():
    assert clean_name("  Sky   😀 Blue ", 10) == "Sky Blue"


def test_persona_created_once(tmp_path, monkeypatch):
    from pokeplay.agent import Agent
    from pokeplay.config import Config

    cfg = Config()
    cfg.voice.engine = "none"
    cfg.brain.persona_file = str(tmp_path / "persona.json")
    agent = Agent(cfg)
    calls = []

    def fake_create(hint):
        calls.append(hint)
        return {"name": "Nova", "personality": "dry wit", "catchphrase": "Onward"}

    monkeypatch.setattr(agent.brain, "create_persona", fake_create)
    agent._load_persona()
    agent._load_persona()
    assert calls == ["a female AI"]                     # only invented once
    assert agent.brain.name == "Nova"
    assert json.loads((tmp_path / "persona.json").read_text())["name"] == "Nova"
    assert "Onward" in agent.brain.personality
    assert json.loads(agent.overlay.snapshot())["streamer"] == "Nova"


def test_subtitles_follow_voice():
    import time
    from pokeplay.narrator import Narrator
    from pokeplay.overlay.server import OverlayState

    ov = OverlayState()
    n = Narrator("none", on_speak=lambda t: ov.update(subtitle=t), on_done=lambda: ov.update(subtitle=""))
    n.say("Hi chat!")
    time.sleep(0.2)
    assert json.loads(ov.snapshot())["subtitle"] == "Hi chat!"
    n.wait_until_quiet()
    time.sleep(0.1)
    assert json.loads(ov.snapshot())["subtitle"] == ""
