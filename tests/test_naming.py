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
    cfg.brain.memory_file = str(tmp_path / "memory.json")
    agent = Agent(cfg)
    calls = []

    def fake_create(hint):
        calls.append(hint)
        return {"name": "Nova", "personality": "dry wit", "catchphrase": "Onward"}

    monkeypatch.setattr(agent.brain, "create_persona", fake_create)
    agent._load_persona()
    agent._load_persona()
    assert calls == [cfg.brain.persona_hint]            # only invented once
    assert agent.brain.name == "Nova"
    assert json.loads((tmp_path / "persona.json").read_text())["name"] == "Nova"
    assert agent.brain.catchphrase == "Onward" and "Onward" not in agent.brain.personality
    assert json.loads(agent.overlay.snapshot())["streamer"] == "Nova"


def _named_agent(tmp_path, streamer_name=""):
    from pokeplay.agent import Agent
    from pokeplay.config import Config

    cfg = Config()
    cfg.voice.engine = "none"
    cfg.brain.streamer_name = streamer_name
    cfg.brain.persona_file = str(tmp_path / "persona.json")
    cfg.brain.memory_file = str(tmp_path / "memory.json")
    (tmp_path / "persona.json").write_text(
        json.dumps({"name": "Oldname", "personality": "dry wit", "catchphrase": "Oldname says hi"}))
    agent = Agent(cfg)
    agent._load_persona()
    return agent, tmp_path / "persona.json"


def test_character_name_becomes_her_name(tmp_path):
    agent, path = _named_agent(tmp_path)
    agent._take_name("Flare")
    saved = json.loads(path.read_text())
    assert saved["name"] == "Flare" and saved["catchphrase"] == "Flare says hi"
    assert agent.brain.name == "Flare" and agent.brain.catchphrase == "Flare says hi"
    assert json.loads(agent.overlay.snapshot())["streamer"] == "Flare"


def test_owner_chosen_name_is_not_replaced(tmp_path):
    agent, path = _named_agent(tmp_path, streamer_name="Fixed")
    agent._take_name("Flare")
    assert agent.brain.name == "Fixed" and json.loads(path.read_text())["name"] == "Oldname"


def test_character_name_is_not_pokemon_derived():
    from pokeplay.brain import Brain
    b = Brain("http://x", "m", "Oldname")
    replies = iter(['{"name": "Pikachu", "say": "no"}', '{"name": "Flare", "say": "yes"}'])
    sent = []
    b._chat = lambda messages, **k: sent.append(messages) or next(replies)
    assert b.choose_name("player", 7) == ("Flare", "yes")
    assert "Oldname" not in sent[0][0]["content"]       # her old name doesn't anchor the choice
    assert "can't use 'Pikachu'" in sent[1][1]["content"]


def test_leaked_instructions_are_not_spoken():
    from pokeplay.brain import Brain
    b = Brain("http://x", "m")
    b._chat = lambda *a, **k: '{"say": "The user wants me to react in 1-2 short sentences."}'
    assert b.comment(["We won"], "CONTEXT") == ""
    b._chat = lambda *a, **k: '{"say": "That went better than expected."}'
    assert b.comment(["We won"], "CONTEXT") == "That went better than expected."


def test_voice_never_holds_up_her_next_thought(tmp_path):
    from pokeplay.brain import Decision

    agent, _ = _named_agent(tmp_path)
    agent._think_seconds = 4.0
    waited, said = [], []
    agent.narrator.wait_until_quiet = lambda timeout: waited.append(timeout)
    agent._speak = said.append
    agent._wait_for_voice()
    assert waited == [2.0]                              # 7 seconds, minus thinking time and a second of slack

    agent.narrator.is_speaking = lambda: True
    agent._apply_decision(Decision("hmm", "I wonder", 0), "Go north")
    assert said == [] and json.loads(agent.overlay.snapshot())["thought"] == "hmm"   # thought, no speech
    agent.narrator.is_speaking = lambda: False
    agent._apply_decision(Decision("hmm", "I wonder", 0), "Go north")
    assert said == ["I wonder"]


def test_voice_respells_only_what_it_gets_wrong():
    from pokeplay.narrator import pronounceable
    assert pronounceable("My first Pokémon!") == "My first Pokemon!"
    assert pronounceable("POKéMON and Pokémons") == "Pokemon and Pokemons"
    assert pronounceable("A Poké Ball, a POKé MART, the Pokédex") == "A Pohkay Ball, a Pohkay MART, the Poh-kay-decks"
    assert pronounceable("Should I poke it?") == "Should I poke it?"


def test_overused_words_are_not_spoken(tmp_path):
    from pokeplay.brain import clean_spoken

    assert clean_spoken("Ugh, why is this door locked?", "Ziggy") == "Why is this door locked?"
    assert clean_spoken("Well, ugh... fine.", "Ziggy") == "Well, fine."
    assert clean_spoken("Ugh!", "Ziggy") == ""

    agent, _ = _named_agent(tmp_path)
    said = []
    agent.narrator.say = said.append
    agent._speak("This is pure chaos.")
    agent._speak("That door looks suspicious.")
    assert said == ["That door looks suspicious."]


def test_twitch_channel_reaches_overlay(tmp_path):
    agent, _ = _named_agent(tmp_path)
    assert json.loads(agent.overlay.snapshot())["twitch_channel"] == ""

    from pokeplay.agent import Agent
    agent.cfg.overlay.twitch_channel = " https://www.twitch.tv/#MyChannel "
    assert json.loads(Agent(agent.cfg).overlay.snapshot())["twitch_channel"] == "mychannel"


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


def test_repeats_are_filtered():
    from pokeplay.brain import Brain
    b = Brain("http://x", "m")
    b.remember_said("Happy Monday, chaos gremlins! Let's do this!")
    assert b.is_repeat("Happy Monday chaos gremlins, let's do this!")
    assert not b.is_repeat("Ooh, a door. What could possibly go wrong?")
    assert "Happy Monday" in b._recent_block()


def test_clean_spoken_removes_name_labels():
    from pokeplay.brain import clean_spoken, looks_pokemon_derived
    assert clean_spoken("PikaPunch: Let's open that door!", "PikaPunch") == "Let's open that door!"
    assert clean_spoken("**PikaPunch:** *gasps* A DOOR!", "PikaPunch") == "gasps A DOOR!"
    assert clean_spoken('"Ooh, shiny."', "Nova") == "Ooh, shiny."
    assert clean_spoken("Say: hi chat", "Nova") == "hi chat"
    # Her name in the middle of a sentence is left alone.
    assert clean_spoken("They call me Nova for a reason.", "Nova") == "They call me Nova for a reason."
    assert looks_pokemon_derived("PikaPunch") and looks_pokemon_derived("Poke Queen")
    assert not looks_pokemon_derived("Nova Static")


def test_clean_spoken_more_label_styles():
    from pokeplay.brain import clean_spoken
    assert clean_spoken("PikaPunch says: 'Hmm, so confusing!'", "PikaPunch") == "Hmm, so confusing!"
    assert clean_spoken('**PikaPunch** yells: "A DOOR!"', "PikaPunch") == "A DOOR!"


def test_she_fills_long_silences(tmp_path):
    import threading
    import time
    from pokeplay.agent import Agent
    from pokeplay.config import Config

    cfg = Config()
    cfg.voice.engine = "none"
    cfg.brain.memory_file = str(tmp_path / "memory.json")
    cfg.commentary.max_silence_seconds = 1
    agent = Agent(cfg)
    agent._context = "WHERE YOU ARE: a forest."
    agent._activity = "walking north through the forest"
    asked = []
    agent.brain.comment = lambda events, ctx: asked.append(events[0]) or "These trees all look the same."
    agent.narrator.last_spoke = time.time() - 5
    threading.Thread(target=agent._commentary_worker, daemon=True).start()
    time.sleep(3)
    assert asked and "walking north through the forest" in asked[0]
    assert "These trees all look the same." in agent.brain.recent_said
