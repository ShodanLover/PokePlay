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


def test_every_comedy_angle_comes_up_before_any_repeats():
    from pokeplay.brain import COMEDY_ANGLES, Brain

    b = Brain("http://x", "m")
    assert sorted(b._next_angle() for _ in COMEDY_ANGLES) == sorted(COMEDY_ANGLES)


def test_voice_never_holds_up_her_next_thought(tmp_path, monkeypatch):
    from pokeplay import agent as agent_module
    from pokeplay.brain import Decision

    monkeypatch.setattr(agent_module.random, "random", lambda: 0.0)

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
    assert pronounceable("A Poké Ball, a POKé MART, the Pokédex") == "A Pohkay Ball, a Pohkay Mart, the Poh-kay-decks"
    assert pronounceable("Should I poke it?") == "Should I poke it?"
    assert pronounceable("PROF. OAK said my HP is low") == "Prof. Oak said my HP is low"
    assert pronounceable("Lebron would run that") == "LeBron would run that"


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


def _menu_agent(tmp_path):
    from pokeplay.brain import Decision

    agent, _ = _named_agent(tmp_path)
    agent.pressed, agent.prompts = [], []
    agent.emu.press = lambda key, **kw: agent.pressed.append(key)
    agent.game.mode = lambda: "overworld"
    agent.game.message = lambda: ""
    agent._memory_text = lambda short=False: "MEMORY"
    agent.menus.choose = lambda menu, i: menu.all_options()[i]
    agent.brain.decide = lambda context, lines: agent.prompts.append(lines) or Decision("thinking", "", 0)
    return agent


def test_menu_circles_get_broken(tmp_path):
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    menu = Menu("start", "The main menu is open.", ["BAG", "SAVE"])
    agent._menu_turn(menu)
    agent._menu_turn(menu)
    assert agent.pressed == []
    agent._menu_turn(menu)                                  # third time: she's going in circles
    assert "already picked this 2 times" in agent.prompts[2][0]
    assert agent.pressed == ["B"] and agent._leaving_menus
    agent._menu_turn(menu)                                  # keeps backing out without asking her
    assert agent.pressed == ["B", "B"] and len(agent.prompts) == 3


def test_party_menu_circles_get_broken(tmp_path):
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    menu = Menu("party_action", "What to do with Pikachu?", ["SUMMARY", "SWITCH"])
    for _ in range(3):
        agent._menu_turn(menu)
    assert agent.pressed == ["B"] and agent._leaving_menus


def test_wandering_through_many_menus_gets_broken(tmp_path):
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    for i in range(12):
        agent._menu_turn(Menu("list", f"Screen {i}", ["Something"]))
    assert agent.pressed == ["B"] and agent._leaving_menus      # never the same choice twice, still lost


def test_questions_the_game_asks_are_never_cut_off(tmp_path):
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    question = Menu("multichoice", "Which one?", ["This", "That"])
    for _ in range(5):
        agent._menu_turn(question)
    assert agent.pressed == [] and not agent._leaving_menus and len(agent.prompts) == 5


def test_subtitle_appears_when_the_audio_starts(monkeypatch):
    import numpy as np
    from pokeplay import narrator as nar

    events = []

    class FakeKokoro:
        def create(self, text, **kw):
            events.append("generated")
            return np.zeros(10, dtype=float), 24000

    monkeypatch.setattr(nar, "_play_wav", lambda path: events.append("audio"))
    n = nar.Narrator("kokoro", on_speak=lambda text: events.append(f"subtitle: {text}"))
    n._kokoro = FakeKokoro()
    n.say("My first Pokémon")
    n.wait_until_quiet(5)
    assert events == ["generated", "subtitle: My first Pokémon", "audio"]     # real spelling on screen


def test_long_silence_relaxes_the_repeat_check(tmp_path):
    import time

    agent, _ = _named_agent(tmp_path)
    agent.narrator.say = lambda text: None
    assert agent._speak("Blinking bag! I wonder what the little red shelf is for.")
    similar = "Blinking bag! Maybe all those cupboards are secretly connected somehow."
    assert agent._speak(similar) is False                  # she only just spoke
    agent._last_said = time.time() - 30
    assert agent._speak(similar) is True                   # silence is worse than a similar line
    agent._last_said = time.time() - 30
    assert agent._speak(similar) is False                  # but never an actual copy


def test_speak_reports_whether_she_said_it(tmp_path):
    agent, _ = _named_agent(tmp_path)
    agent.narrator.say = lambda text: None
    assert agent._speak("That fence looks freshly painted.") is True
    assert agent._speak("That fence looks freshly painted.") is False


def _house_world():
    """A room like her house: a decoy warp tile listed before the real door mat, both going outside."""
    from types import SimpleNamespace
    from pokeplay.game import MapGrid, Warp
    from pokeplay.overworld import Overworld

    blocked = [[False] * 6 for _ in range(4)]
    behavior = [[0] * 6 for _ in range(4)]
    behavior[2][1] = 0x65                                   # the real door mat
    game = SimpleNamespace(map_grid=lambda: MapGrid(6, 4, blocked, behavior), npcs=lambda: [],
                           warps=lambda: [Warp(2, 2, 3, 0), Warp(1, 2, 3, 0)], connections=lambda: [])
    state = SimpleNamespace(x=4, y=0, map_group=4, map_num=0, surfing=False, party=[])
    return Overworld(None, game, None), state


def test_the_real_door_is_offered_instead_of_the_decoy():
    world, state = _house_world()
    options, _ = world.build_options(state)
    assert [o.target for o in options if o.kind == "warp"] == [(1, 2)]


def test_stairs_know_which_way_to_push():
    from pokeplay.game import ARROW_WARPS
    assert ARROW_WARPS[0x6C] == "right" and ARROW_WARPS[0x6F] == "left"     # the two stairs in her house
    assert ARROW_WARPS[0x65] == "down"                                      # front door mat


def test_retrying_the_same_thing_gets_taken_away(tmp_path):
    from types import SimpleNamespace as Opt

    agent, _ = _named_agent(tmp_path)
    door, person = Opt(key="door"), Opt(key="person")
    for _ in range(3):
        assert agent._drop_worn_out([door, person]) == [door, person]
        agent._note_pick("door")
    for _ in range(9):
        assert agent._drop_worn_out([door, person]) == [person]     # has to try something else
    assert agent._drop_worn_out([door, person]) == [door, person]   # and it comes back later
    agent._note_pick("door"), agent._note_pick("door"), agent._note_pick("door")
    assert agent._drop_worn_out([door]) == [door]                   # never left with nothing to do


def test_party_icon_is_read_from_the_rom():
    import base64
    import struct
    from pokeplay import addresses as A
    from test_core import make_game

    game = make_game()
    game.emu.write(A.gMonIconTable + 133 * 4, struct.pack("<I", 0x08800000))
    game.emu.write(0x08800000, bytes([0x01] * 512))
    game.emu.write(A.gMonIconPaletteIndices + 133, bytes([2]))
    game.emu.write(A.gMonIconPaletteTable + 16, struct.pack("<I", 0x08810000))
    game.emu.write(0x08810000, struct.pack("<16H", *range(16)))
    url = game.mon_icon(133)
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]).startswith(b"\x89PNG")
    assert game.mon_icon(133) == url                    # kept after the first read


def test_running_joke_is_only_occasional(monkeypatch):
    from pokeplay import brain as br

    b = br.Brain("http://x", "m")
    monkeypatch.setattr(br.random, "random", lambda: 0.0)
    assert b._obsession_line() == ""                        # off unless it's set
    b.obsession = "A Star"
    assert "A Star" in b._obsession_line()
    assert "A Star" not in b._system()                      # never part of how she decides
    b.remember_said("A Star would have made that shot.")
    assert b._obsession_line() == ""                        # not right after the last mention
    for i in range(br.OBSESSION_GAP):
        b.remember_said(f"line {i}")
    assert "A Star" in b._obsession_line()
    monkeypatch.setattr(br.random, "random", lambda: 0.9)
    assert b._obsession_line() == ""                        # most lines don't mention it at all


def test_headline_filter_allows_politics_but_not_the_worst():
    from pokeplay.news import MAX_HEADLINES, Headlines, parse_headlines

    feed = b"""<rss><channel>
      <item><title>Team wins cup after dramatic final</title></item>
      <item><title>Man killed in city centre attack</title></item>
      <item><title>Minister faces questions over budget</title></item>
      <item><title>Star convicted after long case</title></item>
      <item><title>Watch the Trailer</title></item>
    </channel></rss>"""
    titles = parse_headlines(feed)
    assert titles == ["Team wins cup after dramatic final", "Minister faces questions over budget"]

    news = Headlines([])
    news.add(titles + titles)                               # the same story never comes up twice
    assert {news.take(), news.take()} == set(titles) and news.take() == ""

    news.add([f"Story number {i} happened today" for i in range(100)])
    assert sum(1 for _ in iter(news.take, "")) == MAX_HEADLINES


def test_headline_is_an_occasional_aside(monkeypatch):
    from pokeplay import brain as br

    b = br.Brain("http://x", "m")
    assert b._headline_line() == ""                         # off unless there's a source
    b.headlines = lambda: 'Team "wins" cup'
    monkeypatch.setattr(br.random, "random", lambda: 0.9)
    assert b._headline_line() == ""                         # most lines don't mention it
    monkeypatch.setattr(br.random, "random", lambda: 0.0)
    assert "Team 'wins' cup" in b._headline_line()
    assert "Team" not in b._system()                        # never part of how she decides


def test_no_progress_forces_what_she_has_tried_least(tmp_path):
    from types import SimpleNamespace as Opt

    agent, _ = _named_agent(tmp_path)
    door, person, menu = Opt(key="door", kind="warp"), Opt(key="person", kind="talk"), Opt(key="menu", kind="menu")
    agent.pick_counts.update({"door": 4, "person": 1})
    assert agent._prefer_untried([door, person, menu]) == [door, person, menu]      # free choice while she's progressing
    agent._actions_since_discovery = 6
    assert agent._prefer_untried([door, person, menu]) == [person]


def test_overused_words_are_named_and_blocked():
    from pokeplay.brain import Brain

    b = Brain("http://x", "m")
    for line in ("My turnip is weird.", "Still thinking about that turnip.", "One more turnip thought."):
        b.remember_said(line)
    assert b.worn_topics() == {"turnip"}
    assert b.is_repeat("That turnip again, honestly.")
    assert not b.is_repeat("There's a sign by the fence over here.")
    assert b.is_repeat("That turnip again, honestly.", lenient=True)        # even after a long silence


def test_lines_that_waited_too_long_are_not_said():
    import time
    from pokeplay.narrator import Narrator

    said = []
    n = Narrator("none", on_speak=said.append)
    n._q.put((time.time() - 60, "That level up a minute ago!", False))
    n.wait_until_quiet(1)
    time.sleep(0.2)
    assert said == []
    n.say("Something just happened.")
    time.sleep(0.2)
    assert said == ["Something just happened."]


def test_old_events_get_no_reaction(tmp_path):
    import threading
    import time

    agent, _ = _named_agent(tmp_path)
    agent.cfg.commentary.max_silence_seconds = 0
    agent.cfg.commentary.min_seconds_between = 0
    asked = []
    agent.brain.comment = lambda events, ctx: asked.append(events) or ""
    agent._events.put((time.time() - 60, "Grew to level 6 a minute ago."))
    threading.Thread(target=agent._commentary_worker, daemon=True).start()
    time.sleep(1.5)
    assert asked == []
    agent._queue_comment("Just grew to level 7.")
    time.sleep(3.5)
    assert asked and asked[0] == ["Just grew to level 7."]


def test_stale_goal_is_dropped_with_its_notes(tmp_path):
    from pokeplay.agent import GOAL_PATIENCE
    from pokeplay.brain import Decision

    agent, _ = _named_agent(tmp_path)
    agent.memory.goal = "Fix Bulbasaur's nickname"
    agent.memory.journal[:] = ["Bulbasaur's nickname is wrong.", "The shop sells potions."]
    for _ in range(GOAL_PATIENCE):
        agent._apply_decision(Decision("t", "", 0), "Go north")
    assert agent.memory.goal == "" and agent.memory.journal == ["The shop sells potions."]
    agent._set_goal("Sort out that nickname on Bulbasaur")      # can't go straight back to it
    assert agent.memory.goal == ""
    agent._set_goal("Reach the next town")
    assert agent.memory.goal == "Reach the next town"


def test_discoveries_keep_her_goal_alive(tmp_path):
    from pokeplay.agent import GOAL_PATIENCE
    from pokeplay.brain import Decision

    agent, _ = _named_agent(tmp_path)
    agent.memory.goal = "Reach the next town"
    for _ in range(GOAL_PATIENCE - 1):
        agent._apply_decision(Decision("t", "", 0), "Go north")
    agent._discovered()
    agent._apply_decision(Decision("t", "", 0), "Go north")
    assert agent.memory.goal == "Reach the next town"


def test_hints_follow_her_progress():
    from pokeplay import hints as h

    assert h.hint_for(0, False, [], [], False) == h.NO_TEAM
    assert h.hint_for(0, True, [], ["Pallet Town", "Route 1"], False) == h.TO_VIRIDIAN
    assert h.hint_for(0, True, [], ["Viridian City"], False) == h.GET_PARCEL
    assert h.hint_for(0, True, ["OAK'S PARCEL"], ["Viridian City"], False) == h.PARCEL
    assert h.hint_for(0, True, [], ["Viridian City"], True) == h.TO_FOREST
    assert h.hint_for(0, True, [], ["Viridian Forest"], True) == h.THROUGH_FOREST
    assert h.hint_for(0, True, [], ["Pewter City"], True) == h.BROCK
    assert h.hint_for(1, True, [], ["Pewter City"], True) == h.TO_ROUTE_3
    assert h.hint_for(1, True, [], ["Mt Moon - 1F"], True) == h.THROUGH_MT_MOON
    assert h.hint_for(1, True, [], ["Cerulean City"], True) == h.MISTY
    assert h.hint_for(8, True, [], ["Victory Road - 1F"], True) == h.BY_BADGES[8]
    assert h.hint_for(99, True, [], ["Victory Road - 1F"], True) == h.BY_BADGES[8]
    assert "Victory Road" in h.hint_for(8, True, [], [], True)
    assert "Sea Cottage" in h.hint_for(2, True, [], [], True)
    assert h.hint_for(2, True, [], ["Route 25 - Sea Cottage", "Vermilion City"], True) == h.BY_BADGES[2]


def test_she_is_told_exactly_what_changed(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    mon = lambda hp, level: NS(nickname="Sprout", hp=hp, level=level)      # noqa: E731
    before = NS(map_name="Town", money=100, party=[mon(20, 5)], items=[("Potion", 2)], balls=[])
    after = NS(map_name="Route", money=150, party=[mon(14, 6), NS(nickname="Bud", hp=9, level=3)],
               items=[("Potion", 1)], balls=[("Ball", 1)])
    assert agent._note_changes(before) == []                # first look: nothing to compare with
    assert agent._note_changes(before) == []                # nothing changed
    changes = agent._note_changes(after)
    for expected in ("You moved from Town to Route.", "Your money went from ₽100 to ₽150.",
                     "Sprout went from level 5 to level 6.", "Sprout's HP went from 20 to 14.", "Bud joined your team.",
                     "You used or lost Potion (now 1).", "You got Ball (now 1)."):
        assert expected in changes


def test_blocked_exit_is_never_offered_again_on_foot():
    from types import SimpleNamespace as NS
    from pokeplay.overworld import BLOCKED_EXIT

    world, state = _house_world()
    world.game.connections = lambda: [NS(direction="south")]
    world.memory = NS(links={}, people={})
    options, _ = world.build_options(state)
    assert any(o.kind == "exit" for o in options)
    world.memory.links["4.0|edge:south"] = BLOCKED_EXIT
    options, _ = world.build_options(state)
    assert not any(o.kind == "exit" for o in options)
    state.surfing = True
    world.game.map_grid().behavior                          # still reachable once she can cross water
    options, _ = world.build_options(state)
    assert any(o.kind == "exit" and "haven't been" in o.label for o in options)


def test_no_turning_straight_back(tmp_path):
    from types import SimpleNamespace as Opt
    from pokeplay.agent import NO_TURNING_BACK

    agent, _ = _named_agent(tmp_path)
    back, onward = Opt(key="back"), Opt(key="onward")
    agent.memory.links["back"] = "Old Town"
    agent._came_from = "Old Town"
    assert agent._no_turning_back([back, onward]) == [onward]
    assert agent._no_turning_back([back]) == [back]                 # never left with nothing to do
    agent._decisions_here = NO_TURNING_BACK
    assert agent._no_turning_back([back, onward]) == [back, onward]


def test_badly_hurt_team_is_noticed():
    from types import SimpleNamespace as NS
    from pokeplay.agent import Agent

    assert Agent._team_badly_hurt(NS(party=[NS(hp=3, max_hp=24)]))
    assert not Agent._team_badly_hurt(NS(party=[NS(hp=20, max_hp=24)]))
    assert not Agent._team_badly_hurt(NS(party=[]))


def test_battle_context_is_only_the_battle(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    agent.memory.goal = "Find the door to Route 1"
    agent.memory.journal.append("The north door is risky.")
    foe = NS(species_name="PIDGEY", level=3, hp=10, max_hp=12, status="")
    me = NS(species_name="BULBASAUR", moves=[], summary=lambda: "Sprout Lv8 HP 20/26")
    context = agent._battle_context(NS(player=me, enemy=foe, is_trainer=False, message=""))
    assert "HP 20/26" in context and "door" not in context.lower() and "Route 1" not in context


def test_empty_bag_is_not_offered_in_battle(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    labels = ["Use TACKLE", "Open your Bag (items, Poké Balls)", "Run away"]
    agent.game.state = lambda: NS(items=[], balls=[])
    assert agent._usable_battle_labels(labels) == [0, 2]
    agent.game.state = lambda: NS(items=[("Potion", 1)], balls=[])
    assert agent._usable_battle_labels(labels) == [0, 1, 2]


def test_hp_numbers_stay_out_of_her_journal(tmp_path):
    agent, _ = _named_agent(tmp_path)
    assert not agent._worth_noting("Sprout is at 3/24 and needs help.")
    assert not agent._worth_noting("Sprout's HP is really low.")


def test_route_targets_for_the_opening():
    from pokeplay import hints as h

    assert h.target_for(h.GET_PARCEL, "Viridian City") == "Viridian City - Mart"
    assert h.target_for(h.GET_PARCEL, "Viridian City - House") == "Viridian City"      # wrong building: back out
    assert h.target_for(h.GET_PARCEL, "Viridian City - Mart") == ""                    # arrived
    assert h.target_for(h.PARCEL, "Pallet Town") == "Pallet Town - Professor Oak's Lab"
    assert h.target_for(h.PARCEL, "Pallet Town - Professor Oak's Lab") == ""           # arrived, so she stays
    assert h.target_for(h.THROUGH_FOREST, "Route 2") == "north"                        # passing through, not arrived
    assert h.target_for(h.TO_VIRIDIAN, "Pallet Town - Player's House - 2F") == "Pallet Town"
    assert h.target_for(h.MISTY, "Cerulean City") == "Cerulean City - Gym"
    assert h.target_for(h.THROUGH_MT_MOON, "Mt Moon - 1F") == ""                       # caves are left to her


def test_she_takes_the_door_for_her_next_step(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    house = NS(kind="warp", label="door", dest="Viridian City - House", key="a")
    mart = NS(kind="warp", label="door", dest="Viridian City - Mart", key="b")
    north = NS(kind="exit", label="Leave this area by the north side (x)", dest="", key="c")
    agent.memory.places["3.1"] = "Viridian City"
    state = NS(badges=0, party=[NS(hp=10, max_hp=10, level=5)], key_items=[], map_name="Viridian City", balls=[], money=0)
    assert agent._follow_route([house, mart, north], state) == [mart]
    assert agent._follow_route([house, north], state) == []                             # door not reachable: her call
    state.badges = 2
    assert agent._follow_route([house, mart, north], state) == []                       # guided part is over


def test_once_at_the_destination_she_talks_instead_of_leaving(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    door = NS(kind="warp", label="door", dest="Pallet Town", key="out")
    oak, aide = NS(kind="talk", label="t", dest="", key="oak"), NS(kind="talk", label="t", dest="", key="aide")
    state = NS(badges=0, party=[NS(hp=10, max_hp=10, level=5)], key_items=["OAK'S PARCEL"],
               map_name="Pallet Town - Professor Oak's Lab", balls=[], money=0)
    assert agent._follow_route([door, oak, aide], state) == [oak, aide]
    agent.pick_counts["aide"] = 2
    assert agent._follow_route([door, oak, aide], state) == [oak]


def test_unsuitable_lines_are_not_spoken(tmp_path):
    agent, _ = _named_agent(tmp_path)
    said = []
    agent.narrator.say = said.append
    assert agent._speak("I think I'm having a baby with the door.") is False
    assert agent._speak("That door is shamelessly handsome and I'm furious about it.") is True
    assert len(said) == 1


def test_gate_building_does_not_count_as_the_forest():
    from pokeplay import hints as h

    gate = ["Viridian City", "Route 2", "Route 2 - Viridian Forest - South Entrance"]
    assert h.hint_for(0, True, [], gate, True) == h.TO_FOREST
    assert h.target_for(h.TO_FOREST, gate[2]) == "Viridian Forest"
    assert h.target_for(h.TO_FOREST, "Route 22") == "east"


def test_comments_are_mostly_about_the_game(monkeypatch):
    from pokeplay import brain as br

    b = br.Brain("http://x", "m")
    monkeypatch.setattr(br.random, "random", lambda: 0.9)
    assert "random subject" not in b._style_line() and "actually just happened" in b._style_line()
    monkeypatch.setattr(br, "SUBJECT_CHANCE", 1.0)
    assert "Your random subject" in b._style_line()


def test_read_trees_are_not_offered_without_cut():
    from types import SimpleNamespace as NS
    from pokeplay import addresses as A

    world, state = _house_world()
    tree = NS(local_id=7, x=3, y=0, graphics_id=A.OBJ_EVENT_GFX_CUT_TREE)
    world.game.npcs = lambda: [tree]
    world.memory = NS(links={}, people={"4.0|7": "This tree looks like it can be CUT down!"})
    assert not any(o.kind == "talk" for o in world.build_options(state)[0])
    state.party = [NS(moves=[NS(name="CUT")])]
    assert any(o.kind == "talk" for o in world.build_options(state)[0])


def test_her_guide_stays_secret(tmp_path):
    agent, _ = _named_agent(tmp_path)
    agent.narrator.say = lambda text: None
    assert agent._speak("My walkthrough says to go north.") is False
    assert agent._speak("That hint was useless.") is False
    assert not agent._worth_noting("The rubber duck told me things.")


def test_battle_math_labels_each_move():
    from types import SimpleNamespace as NS
    from pokeplay.battle import rate_moves

    GRASS, FIRE, NORMAL = 12, 10, 0
    game = NS(effectiveness=lambda move_type, defender: {GRASS: 0.5, NORMAL: 1.0}[move_type])
    moves = [NS(pp=25, power=45, type=GRASS, accuracy=100), NS(pp=35, power=40, type=NORMAL, accuracy=100),
             NS(pp=40, power=0, type=NORMAL, accuracy=100), NS(pp=0, power=200, type=NORMAL, accuracy=100)]
    info = NS(player=NS(moves=moves, types=(GRASS, GRASS)), enemy=NS(types=(FIRE, FIRE)))
    notes = rate_moves(game, info)
    assert "not very effective" in notes[0] and "STRONGEST" not in notes[0]      # 45 x 0.5 x 1.5 = 33.75
    assert "normal damage" in notes[1] and "STRONGEST" in notes[1]               # 40
    assert "no direct damage" in notes[2]
    assert 3 not in notes                                                        # out of PP
    assert rate_moves(game, NS(player=None, enemy=None)) == {}


def test_battles_use_the_strongest_move_without_stopping_to_think(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    asked = []
    agent.brain.decide = lambda context, lines: asked.append(lines)
    agent.game.state = lambda: NS(items=[], balls=[], party=[1])
    info = NS(player=NS(species_name="X", moves=[], summary=lambda: "X"), is_trainer=False, message="",
              enemy=NS(species_name="Y", level=3, hp=9, max_hp=12, status=""))
    labels = ["Use A (normal damage)", "Use B (super effective, THE STRONGEST CHOICE)", "Try to run away"]
    assert agent._choose_battle_action(info, labels, []) == 1 and asked == []


def test_straight_paths_are_walked_in_one_stretch():
    from pokeplay.overworld import stretches

    assert stretches(["up", "up", "up", "left", "up"]) == [("up", 3), ("left", 1), ("up", 1)]
    assert stretches([]) == []


def _strider(positions, modes=None):
    from types import SimpleNamespace as NS
    from pokeplay.overworld import Overworld

    states = iter([("overworld", 3, 0, *p) for p in positions])
    presses = []
    game = NS(state_light=lambda: next(states))
    emu = NS(press=lambda keys, hold=0, wait=0: presses.append((keys, hold)), u8=lambda a: 0, wait_frames=lambda n: None)
    return Overworld(emu, game, None), presses


def test_stride_holds_the_direction_until_it_gets_there():
    world, presses = _strider([(5, 9), (5, 9), (5, 8), (5, 7), (5, 7), (5, 6)])
    assert world.stride("up", 3) == "moved"
    assert world.steps_taken == 3
    assert all(keys == "up+B" for keys, _ in presses) and len(presses) == 5


def test_stride_notices_it_cannot_move():
    world, presses = _strider([(5, 9)] * 40)
    assert world.stride("up", 3) == "blocked"


def test_bag_is_spelled_out_in_battle(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    agent.game.state = lambda: NS(balls=[("POKé BALL", 5)], items=[("POTION", 1)])
    assert agent._bag_line() == "IN YOUR BAG RIGHT NOW: POKé BALL x5, POTION x1."
    agent.game.state = lambda: NS(balls=[], items=[])
    assert agent._bag_line() == "YOUR BAG IS EMPTY."


def test_catching_goes_for_new_species_and_low_hp(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    weedle = NS(species=13, hp=20, max_hp=20)
    agent.game.state = lambda: NS(balls=[("POKé BALL", 3)], party=[NS(species=1)])
    assert "weaken it" in agent._catch_nudge(NS(is_trainer=False, enemy=weedle))
    assert "Throw a ball now" in agent._catch_nudge(NS(is_trainer=False, enemy=NS(species=13, hp=4, max_hp=20)))
    assert agent._catch_nudge(NS(is_trainer=True, enemy=weedle)) == ""
    agent.game.state = lambda: NS(balls=[("POKé BALL", 3)], party=[NS(species=1), NS(species=13)])
    assert agent._catch_nudge(NS(is_trainer=False, enemy=weedle)) == ""     # already has one


def test_buying_balls_only_in_towns_with_a_mart():
    from pokeplay import hints as h

    assert h.hint_for(0, True, [], ["Viridian City"], True, want_balls=True, place="Viridian City") == h.BUY_BALLS
    assert h.hint_for(0, True, [], ["Viridian Forest"], True, want_balls=True, place="Viridian Forest") != h.BUY_BALLS
    assert h.target_for(h.BUY_BALLS, "Pewter City") == "Pewter City - Mart"
    assert h.target_for(h.BUY_BALLS, "Pewter City - Mart") == ""
    assert h.arrived(h.BUY_BALLS, "Pewter City - Mart")


def test_healing_comes_first_in_towns(tmp_path):
    from pokeplay import hints as h

    assert h.hint_for(0, True, [], ["Viridian City"], True, place="Pewter City", needs_healing=True) == h.HEAL
    assert h.hint_for(0, True, [], ["Viridian Forest"], True, place="Viridian Forest", needs_healing=True) != h.HEAL
    assert h.target_for(h.HEAL, "Pewter City") == "Pewter City - Pokémon Center - 1F"
    assert h.target_for(h.HEAL, "Pewter City - Pokémon Center - 1F") == ""
    assert h.arrived(h.HEAL, "Pewter City - Pokémon Center - 1F")


def test_guide_section_follows_her_progress(tmp_path):
    from pokeplay.hints import guide_section

    guide = tmp_path / "guide.md"
    guide.write_text("# Notes\n### Pallet Town to Pewter City\nGo north.\n### Mt. Moon to Vermilion City\nGo east.\n",
                     encoding="utf-8")
    assert guide_section(0, guide) == "Go north."
    assert guide_section(2, guide) == "Go east."
    assert guide_section(0, tmp_path / "missing.md") == ""


def _move_game():
    from types import SimpleNamespace as NS

    table = {0: ("-", 0), 1: ("RAZOR LEAF", 55), 2: ("SLEEP POWDER", 0), 3: ("POUND", 40)}
    return NS(move_data=[(table[i][1], 0, 100, 10) for i in table], move_name=lambda i: table[i][0])


def test_new_moves_replace_the_right_one():
    from types import SimpleNamespace as NS
    from pokeplay.menus import forget_choice

    game = _move_game()
    tackle, vine, growl, poison = NS(power=35), NS(power=45), NS(power=0), NS(power=15)
    assert forget_choice(game, [tackle, vine, growl, poison], "RAZOR LEAF") == 2     # no-damage move goes first
    assert forget_choice(game, [tackle, vine, poison, NS(power=50)], "RAZOR LEAF") == 2   # otherwise the weakest
    assert forget_choice(game, [tackle, vine, growl, poison], "SLEEP POWDER") == 4   # not worth an attack
    assert forget_choice(game, [NS(power=60), NS(power=70), NS(power=80), NS(power=90)], "POUND") == 4   # worse than all
    assert forget_choice(game, [tackle, vine, poison, NS(power=50)], "") == 2        # unknown: still drop the weakest


def test_learning_question_is_answered_by_the_math(tmp_path):
    agent, _ = _named_agent(tmp_path)
    agent.game.move_data, agent.game.move_name = _move_game().move_data, _move_game().move_name
    assert agent._answer_battle_question("Delete a move to make room for RAZOR LEAF?") is True
    assert agent._answer_battle_question("Delete a move to make room for SLEEP POWDER?") is False


def test_highlights_keep_only_what_is_worth_clipping(tmp_path):
    import time
    from pokeplay.highlights import Highlights

    h = Highlights(tmp_path)
    h.event("A wild creature jumped out!")                      # routine
    h.spoken("Just a normal line.", "LeBron James")
    assert not list(tmp_path.glob("*.md"))
    h.event("The battle is over: you lost.")
    h.spoken("I hate this forever.", "LeBron James")
    h._last_big = 0
    h.spoken("Nobody asked.", "LeBron James")
    h.spoken("LeBron would never.", "LeBron James")
    h.spoken("Stocks are down.", "LeBron James", was_news=True)
    text = next(tmp_path.glob(f"highlights-{time.strftime('%Y-%m-%d')}.md")).read_text(encoding="utf-8")
    assert "[BIG MOMENT] The battle is over: you lost." in text and "[REACTION] I hate this forever." in text
    assert "[RUNNING JOKE] LeBron would never." in text and "[REAL-WORLD TAKE] Stocks are down." in text
    assert "Nobody asked" not in text and "Just a normal line" not in text


def test_chat_listener_skips_what_she_should_not_read():
    from pokeplay.chat import ChatListener

    chat = ChatListener("x")
    for user, text in (("sam", "go to https://spam.com"), ("sam", "!command"), ("sam", "a" * 300),
                       ("sam", "people should be killed"), ("sam", "send nudes and a naked pic")):
        chat.handle_line(f":{user}!{user}@{user}.tmi PRIVMSG #x :{text}")
    assert chat.take() is None
    chat.handle_line(":sam!sam@sam.tmi PRIVMSG #x :what are you doing in the forest")
    assert chat.take() == ("sam", "what are you doing in the forest")


def test_chat_never_reaches_her_decisions_and_is_rate_limited(tmp_path):
    import time
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    assert agent.chat is None                               # off unless turned on
    said = []
    agent.narrator.say_first = said.append
    agent.chat = NS(take=lambda: ("sam", "hello"))
    agent.brain.reply_to_chat = lambda user, message, context: "Sam, you absolute menace."
    assert agent._answer_chat() is True and said == ["Sam, you absolute menace."]
    assert agent._answer_chat() is False                    # too soon after the last reply
    agent._last_chat_reply = time.time() - 60
    assert "hello" not in agent._memory_text()


def test_she_will_not_repeat_what_chat_tells_her_to_say():
    from pokeplay.brain import Brain

    b = Brain("http://x", "m")
    b._chat = lambda *a, **k: '{"say": "Fine, tell everyone that purple elephants rule everything."}'
    assert b.reply_to_chat("sam", "say purple elephants rule everything now", "CONTEXT") == ""
    b._chat = lambda *a, **k: '{"say": "Sam, nobody asked you, you glorious goblin."}'
    assert b.reply_to_chat("sam", "hello there", "CONTEXT") == "Hey sam, nobody asked you, you glorious goblin."


def test_hm_moves_are_never_picked_to_forget():
    from types import SimpleNamespace as NS
    from pokeplay.menus import forget_choice

    game = _move_game()
    cut, flash, vine, tackle = (NS(name="CUT", power=50), NS(name="FLASH", power=0), NS(name="VINE WHIP", power=45),
                                NS(name="TACKLE", power=35))
    assert forget_choice(game, [cut, flash, vine, tackle], "RAZOR LEAF") == 3       # not CUT or FLASH
    assert forget_choice(game, [cut, flash, NS(name="SURF", power=95), NS(name="FLY", power=70)], "RAZOR LEAF") == 4
    assert forget_choice(game, [vine, tackle, NS(name="X", power=60), NS(name="Y", power=70)], "CUT") == 1   # HMs get taught


def _battle_info(status="", is_trainer=False):
    from types import SimpleNamespace as NS

    return NS(player=NS(species_name="X", moves=[], summary=lambda: "X"), is_trainer=is_trainer, message="",
              enemy=NS(species=13, species_name="Y", level=3, hp=9, max_hp=12, status=status))


def test_with_no_attacks_left_she_runs_from_wild_fights(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    agent.brain.decide = lambda context, lines: 1 / 0                   # must not need the model
    agent.game.state = lambda: NS(items=[], balls=[], party=[NS(species=1)])
    labels = ["Use SLEEP POWDER (Grass type, 4 PP left, does no direct damage)", "Try to run away"]
    assert agent._choose_battle_action(_battle_info("asleep"), labels, []) == 1


def test_a_sleeping_foe_never_leaves_her_with_only_bag_and_switch(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    agent.brain.decide = lambda context, lines: 1 / 0               # must not need the model
    agent.game.state = lambda: NS(items=[("Potion", 1)], balls=[], party=[NS(species=1)])
    labels = ["Use SLEEP POWDER (does no direct damage)", "Open your Bag (items, Poké Balls)", "Switch to a different Pokémon"]
    assert agent._choose_battle_action(_battle_info("asleep", is_trainer=True), labels, []) == 0


def test_weak_team_trains_next_to_the_gym():
    from pokeplay import hints as h

    def hint(badges, places, place, level, can_train=True, **kw):
        return h.hint_for(badges, True, [], places, True, place=place, strongest=level, can_train=can_train, **kw)

    # Too weak in the gym's city or on the grass next door: train. Strong enough, or out of training time: the gym.
    assert hint(0, ["Pewter City"], "Pewter City", 9) == h.TRAIN_STEPS[0]
    assert hint(0, ["Pewter City"], "Pewter City - Gym", 9) == h.TRAIN_STEPS[0]
    assert hint(0, ["Pewter City"], "Route 3", 9) == h.TRAIN_STEPS[0]
    assert hint(0, ["Pewter City"], "Pewter City", 12) == h.BROCK
    assert hint(0, ["Pewter City"], "Pewter City", 9, can_train=False) == h.BROCK
    assert hint(1, ["Cerulean City"], "Cerulean City", 15) == h.TRAIN_STEPS[1]

    # Never interrupts travel, and never happens before she's finished that stretch of the story.
    assert hint(0, ["Pewter City"], "Route 2", 9) == h.BROCK
    assert hint(1, ["Pewter City"], "Pewter City", 9) == h.TO_ROUTE_3
    assert "Sea Cottage" in hint(2, [], "Vermilion City", 9)

    # Hurt on the grass: back to town. In town: the Center comes first.
    assert hint(0, ["Pewter City"], "Route 3", 9, needs_healing=True) == h.RETURN_STEPS[0]
    assert hint(0, ["Pewter City"], "Pewter City", 9, needs_healing=True) == h.HEAL

    # Later gyms only get a warning, and the level isn't known in the older calls.
    done = [marker for marker, _ in h.LATER_STEPS[5]]
    assert hint(5, done, "Saffron City", 30).startswith(h.BY_BADGES[5] + " ")
    assert hint(5, done, "Saffron City", 36) == h.BY_BADGES[5]
    assert hint(0, ["Pewter City"], "Pewter City", 0) == h.BROCK


def test_training_routes_there_and_back():
    from pokeplay import hints as h

    assert h.target_for(h.TRAIN_STEPS[0], "Pewter City") == "east"
    assert h.target_for(h.TRAIN_STEPS[0], "Route 3") == ""                         # on the grass, so she stays
    assert h.target_for(h.TRAIN_STEPS[0], "Pewter City - Gym") == "Pewter City"
    assert h.target_for(h.RETURN_STEPS[0], "Route 3") == "west"
    assert h.target_for(h.BROCK, "Route 3") == "west"                              # finished, so back to the Gym
    assert h.target_for(h.MISTY, "Route 4") == "east"
    for badges in (2, 3, 4):
        route, back = h.TRAINING[badges][4], h.TRAINING[badges][5]
        assert h.target_for(h.BY_BADGES[badges], route) == back
        assert h.target_for(h.BY_BADGES[badges], f"{h.TRAINING[badges][1]} - Gym") == ""   # she isn't pulled out of the Gym


def test_training_picks_the_grass_and_has_a_limit(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay import hints as h

    agent, _ = _named_agent(tmp_path)
    agent.memory.places = {"1.1": "Pewter City"}
    mon = NS(hp=30, max_hp=30, level=9, moves=[NS(power=35, pp=20)], nickname="A")
    state = NS(badges=0, party=[mon], key_items=[], balls=[("POKé BALL", 3)], money=500, map_name="Route 3")
    grass = NS(kind="train", label="grass", dest="", key="grass:1.2")
    west = NS(kind="exit", label="Leave this area by the west side (x)", dest="", key="w")

    assert agent._follow_route([west, grass], state) == [grass]
    assert agent._train_turns == 1
    agent._next_step(state)                                                     # the prompt asks too, without counting
    assert agent._train_turns == 1

    agent._train_turns = h.TRAIN_LIMIT                                          # time's up: on to the gym
    assert agent._next_step(state) == h.BROCK
    assert agent._follow_route([west, grass], state) == [west]

    state.badges = 1                                                            # a new gym gets its own time
    agent._next_step(state)
    assert agent._train_turns == 0


def test_out_of_attacks_sends_her_back_to_heal(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay import hints as h
    from pokeplay.agent import Agent

    mon = NS(hp=25, max_hp=42, moves=[NS(power=0, pp=4), NS(power=35, pp=0)])
    assert Agent._lead_out_of_attacks(NS(party=[mon]))
    assert not Agent._lead_out_of_attacks(NS(party=[NS(hp=9, moves=[NS(power=15, pp=4)])]))
    assert Agent._lead_out_of_attacks(NS(party=[NS(hp=9, moves=[NS(power=15, pp=3), NS(power=0, pp=30)])]))     # nearly out
    assert h.hint_for(1, True, [], [], True, place="Route 3", needs_healing=True, heal_anywhere=True) == h.BACK_TO_CENTER
    assert h.target_for(h.BACK_TO_CENTER, "Route 3") == "west"


def test_a_chat_reply_is_never_dropped_as_a_repeat(tmp_path):
    agent, _ = _named_agent(tmp_path)
    said = []
    agent.narrator.say = agent.narrator.say_first = said.append
    assert agent._speak("That fence looks freshly painted, Sam.")
    assert agent._speak("That fence looks freshly painted, Sam.", always_fresh=True)
    assert len(said) == 2


def test_a_move_that_isnt_working_gets_dropped(tmp_path):
    agent, _ = _named_agent(tmp_path)
    info = _battle_info()
    label = "Use GROWL (Normal type, 40 PP left, does no direct damage)"
    agent._remember_move(label, info)
    assert not agent._move_not_working(label, info)
    agent._remember_move(label.replace("40 PP", "39 PP"), info)
    assert agent._move_not_working(label, info)
    info.enemy.hp -= 3                                      # it did something, so it's fine again
    assert not agent._move_not_working(label, info)


def test_toaster_talk_is_not_spoken(tmp_path):
    agent, _ = _named_agent(tmp_path)
    agent.narrator.say = lambda text: None
    assert agent._speak("My brain is a broken toaster.") is False


def test_chat_replies_always_open_with_hey_and_the_name():
    from pokeplay.brain import Brain, clean_spoken

    b = Brain("http://x", "m")
    expected = "Hey bigelephantjumps, Nobody asked, but thanks."
    for said in ("Nobody asked, but thanks.", "BigElephantJumps, Nobody asked, but thanks.", "Hey bigelephantjumps! Nobody asked, but thanks."):
        b._chat = lambda *a, **k: json.dumps({"say": said})
        assert b.reply_to_chat("bigelephantjumps", "hello there", "walking") == expected
    assert clean_spoken(expected, "Fuzz") == expected                   # nothing later strips the greeting
    b._chat = lambda *a, **k: '{"say": "bigelephantjumps"}'
    assert b.reply_to_chat("bigelephantjumps", "hello there", "walking") == ""     # just a name is no reply


def test_switching_pokemon_is_not_an_evolution():
    from types import SimpleNamespace as NS
    from pokeplay.agent import _same_mon

    pikachu = NS(nickname="Pikachu", species_name="BULBASAUR")
    weedle = NS(nickname="WEEDLE", species_name="WEEDLE")
    kakuna = NS(nickname="KAKUNA", species_name="KAKUNA")
    assert not _same_mon(weedle, pikachu)                   # swapped places
    assert _same_mon(weedle, kakuna)                        # really evolved
    assert _same_mon(pikachu, NS(nickname="Pikachu", species_name="IVYSAUR"))


def _team():
    from types import SimpleNamespace as NS

    return [NS(hp=25, moves=[NS(power=0, pp=4), NS(power=35, pp=0)]), NS(hp=0, moves=[NS(power=15, pp=9)]),
            NS(hp=12, moves=[NS(power=15, pp=9)])]


def test_trainer_fight_with_no_attacks_switches_to_someone_who_can(tmp_path):
    agent, _ = _named_agent(tmp_path)
    agent.brain.decide = lambda context, lines: 1 / 0               # must not need the model
    agent.game.party = _team
    labels = ["Use GROWL (does no direct damage)", "Open your Bag (items, Poké Balls)", "Switch to a different Pokémon"]
    assert agent._attacker_slot(skip_active=True) == 2              # skips the fainted one
    assert agent._choose_battle_action(_battle_info(is_trainer=True), labels, []) == 2


def test_battle_team_menus_are_handled_by_code(tmp_path):
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    agent._in_battle = True
    agent.game.party = _team
    chosen = []
    agent.menus.choose = lambda menu, slot: chosen.append(slot)
    agent._menu_turn(Menu("party_choose", "Choose a Pokémon.", ["A", "B", "C"]))
    agent._menu_turn(Menu("party_action", "What to do?", ["SUMMARY", "SHIFT", "CANCEL"]))
    assert chosen == [2, 1] and agent.prompts == []


def test_a_viewer_reply_is_never_dropped_by_the_voice(monkeypatch, capsys):
    import time
    from pokeplay import narrator as voice

    waiting = voice.Narrator(engine="none")
    monkeypatch.setattr(waiting, "_q", voice.queue.Queue())         # nothing is taking lines off this one
    waiting.say("first comment")
    waiting.say_first("Sam, hello.")
    waiting.say("second comment")
    assert [item[1] for item in waiting._q.queue] == ["Sam, hello.", "second comment"]

    speaking = voice.Narrator(engine="none")
    long_ago = time.time() - 9999
    speaking._q.put((long_ago, "old comment", False))
    speaking._q.put((long_ago, "Sam, hello.", True))
    time.sleep(0.5)
    out = capsys.readouterr().out
    assert "(skipped, too late) old comment" in out and "[voice] Sam, hello." in out


def test_moves_are_labeled_by_what_kind_they_are():
    from types import SimpleNamespace as NS
    from pokeplay.battle import rate_moves

    def move(name, power):
        return NS(name=name, pp=5, power=power, type=1, accuracy=100)

    moves = [move("VINE WHIP", 35), move("GROWL", 0), move("LEECH SEED", 0), move("WRAP", 15)]
    info = NS(player=NS(moves=moves, types=(1, 1)), enemy=NS(types=(2, 2)))
    notes = rate_moves(NS(effectiveness=lambda move_type, types: 1.0), info)
    assert "direct damage" in notes[0] and "THE STRONGEST CHOICE" in notes[0]
    assert "status move" in notes[1] and "does no direct damage" in notes[1]
    assert "damage over time" in notes[2] and "does no direct damage" not in notes[2]
    assert "direct damage" in notes[3] and "plus damage over time" in notes[3]


def test_last_resort_prefers_damage_over_time():
    from pokeplay.agent import Agent

    labels = ["Use SLEEP POWDER (Grass type, 1 PP left, status move, does no direct damage)",
              "Use LEECH SEED (Grass type, 9 PP left, damage over time: nothing right away)"]
    assert Agent._last_resort_move(labels) == 1


def test_she_finds_a_center_from_anywhere_she_has_been():
    from pokeplay.hints import way_to_center

    places = {"3.1": "Route 9", "3.2": "Route 10", "1.5": "Rock Tunnel - 1F"}
    links = {"3.2|edge:north": "Route 9", "3.2|door@1,1": "Rock Tunnel - 1F", "3.1|edge:west": "Cerulean City",
             "1.5|door@2,2": "Route 10", "3.2|edge:east": "(blocked)"}
    assert way_to_center("Route 10", links, places) == "3.2|edge:north"
    assert way_to_center("Rock Tunnel - 1F", links, places) == "1.5|door@2,2"
    assert way_to_center("Somewhere New", links, places) == ""


def test_out_of_attacks_she_heads_for_the_center_not_the_grass(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay import hints as h

    agent, _ = _named_agent(tmp_path)
    agent._next_step = lambda s: h.BACK_TO_CENTER
    agent.memory.places = {"3.1": "Route 9"}
    agent.memory.links = {"3.1|edge:west": "Cerulean City"}
    home, grass = NS(key="3.1|edge:west", kind="exit", label="Leave", dest=""), NS(key="grass:3.1", kind="train", label="Grass", dest="")
    assert agent._follow_route([grass, home], NS(map_name="Route 9")) == [home]


def test_no_poke_balls_in_a_trainer_battle(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay.brain import Decision
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    agent.game.battle_info = lambda: NS(is_trainer=True)
    seen, chosen = [], []
    agent.brain.decide = lambda context, lines: seen.append((context, lines)) or Decision("t", "", 0)
    agent.menus.choose = lambda menu, i: chosen.append(i) or menu.all_options()[i]
    agent._menu_turn(Menu("bag", "Your Bag is open on the POKé BALLS pocket.", ["POKé BALL", "GREAT BALL", "CANCEL"]))
    assert "only work on wild" in seen[0][0]
    assert not any("BALL" in line for line in seen[0][1]) and chosen == [2]     # still lands on the right entry

    agent.game.state = lambda: NS(items=[], balls=[("POKé BALL", 3)], party=[])
    labels = ["Use GROWL", "Open your Bag (items, Poké Balls)"]
    assert agent._usable_battle_labels(labels, is_trainer=True) == [0]
    assert agent._usable_battle_labels(labels, is_trainer=False) == [0, 1]


def test_wild_creatures_can_still_be_caught(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay.brain import Decision
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    agent.game.battle_info = lambda: NS(is_trainer=False)
    seen = []
    agent.brain.decide = lambda context, lines: seen.append(lines) or Decision("t", "", 0)
    agent.menus.choose = lambda menu, i: menu.all_options()[i]
    agent._menu_turn(Menu("bag", "Your Bag is open on the POKé BALLS pocket.", ["POKé BALL", "CANCEL"]))
    assert "POKé BALL" in seen[0]


def test_going_round_in_a_loop_counts_as_stuck():
    from pokeplay.watchdog import Watchdog

    dog = Watchdog()
    results = [dog.observe(("A",) if t % 4 else ("B",), "battle", float(t)) for t in range(0, 124, 2)]
    assert results[:30] == [0] * 30                         # nothing for the first minute
    assert [(t * 2, r) for t, r in enumerate(results) if r] == [(62, 1), (92, 2), (122, 3)]
    assert dog.observe(("C",), "battle", 124.0) == 0 and dog.level == 0     # something new: all is well again


def test_watchdog_leaves_normal_play_alone():
    from pokeplay.watchdog import Watchdog

    walking = Watchdog()
    assert not any(walking.observe((t % 8,), "overworld", float(t * 2)) for t in range(60))     # pacing for 2 minutes is fine
    assert any(walking.observe((t % 8,), "overworld", float(t * 2)) for t in range(60, 90))     # but not forever

    progress = Watchdog()
    assert not any(progress.observe((t,), "battle", float(t * 2)) for t in range(200))          # always something new

    slow_ai = Watchdog()
    assert slow_ai.observe(("A",), "battle", 0.0) == 0
    assert slow_ai.observe(("A",), "battle", 90.0) == 0                                         # one slow answer isn't stuck


def test_watchdog_picks_a_safe_escape():
    from pokeplay.watchdog import ESCAPES, escape_keys, escape_kind

    assert escape_kind("party_menu", True, True) == "send_out"
    assert escape_kind("party_menu", True, False) == "menu"
    assert escape_kind("battle", False, False) == "battle"
    assert escape_kind("other", False, False) == "other"
    assert not any("B" in row for row in ESCAPES["other"])          # B would cancel an evolution
    assert escape_keys("battle", 1) == [] and escape_keys("battle", 5) == []    # goes round again


def test_when_stuck_the_code_steps_in_and_keeps_a_record(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    mon = NS(species=1, level=16, hp=0, status="", moves=[NS(name="GROWL", pp=4)], summary=lambda: "Pikachu Lv16")
    agent.game.state = lambda: NS(map_group=1, map_num=2, x=3, y=4, money=5, badges=0, party=[mon], items=[], balls=[],
                                  key_items=[], message="Choose.", map_name="Viridian Forest")
    agent.game.battle_info = lambda: NS(enemy=NS(species=10, hp=9, status="asleep", summary=lambda: "Caterpie"))
    agent.game.party = lambda: [mon]
    agent.game.team_menu_in_battle = lambda: True
    menu = Menu("party_choose", "Choose a Pokémon.", ["Pikachu"])
    agent.watchdog.observe = lambda state, mode, now: 1
    agent.pressed.clear()
    assert agent._stepped_in("party_menu", menu) is True
    assert agent.pressed == ["B", "DOWN", "A", "A"]
    assert "Caterpie" in agent._stuck_log.read_text(encoding="utf-8")


def test_when_stuck_in_battle_the_ai_is_not_asked(tmp_path):
    agent, _ = _named_agent(tmp_path)
    agent.brain.decide = lambda context, lines: 1 / 0
    agent.game.party = _team
    labels = ["Use TACKLE (Normal type, 9 PP left, THE STRONGEST CHOICE)", "Use GROWL (Normal type, 40 PP left, does no direct damage)",
              "Open your Bag (items, Poké Balls)"]
    agent._catch_nudge = lambda info: "catch it"
    agent.watchdog.level = 1
    assert agent._choose_battle_action(_battle_info(), labels, []) == 0
    agent.watchdog.level = 2
    assert agent._choose_battle_action(_battle_info(), labels, []) in (0, 1)


def test_lines_must_be_about_what_is_happening(tmp_path):
    import time

    agent, _ = _named_agent(tmp_path)
    agent.narrator.say = lambda text: None
    agent._activity = "Use GROWL (Normal type, 24 PP left, does no direct damage)"
    agent._on_screen = ("PIDGEY used GUST!", time.time())
    lines, prompts = ["Did you know the Earth's climate is a very simple guide?", "That GUST nearly took my hat off."], []
    agent.brain.comment = lambda events, ctx: prompts.append(events) or lines.pop(0)
    assert agent._comment_on(["Something happened."], 2) is True
    assert list(agent.brain.recent_said) == ["That GUST nearly took my hat off."]   # the gibberish was thrown out
    assert 'Text on screen: "PIDGEY used GUST!"' in prompts[0]

    agent._on_screen = ("PIDGEY used GUST!", time.time() - 60)
    assert agent._on_screen_now() == ""                                 # long gone from the screen


def test_her_planned_asides_are_still_allowed(tmp_path):
    agent, _ = _named_agent(tmp_path)
    agent.brain.obsession = "LeBron James"
    assert agent._about_the_game("LeBron James would have dodged that.", ["PIDGEY used GUST!"])
    assert not agent._about_the_game("Soup is a state of mind.", ["PIDGEY used GUST!"])
    assert agent._about_the_game("Pidgey's wings are personally offensive.", ["PIDGEY used GUST!"])
    assert agent._about_the_game("Just me and a screen that says Welcome to Pokémon.", ["Choose a name."])     # the game itself counts
    assert agent._about_the_game("Why are there so many Pokémon in here?", [])


def test_comment_prompt_asks_for_the_game_not_for_weirdness():
    from pokeplay.brain import Brain

    b = Brain("http://x", "m")
    prompts = []
    b._chat = lambda messages, **k: prompts.append(messages[-1]["content"]) or '{"say": "Fine."}'
    b.comment(["PIDGEY used GUST!"], "CONTEXT")
    assert "weirdest" not in prompts[0] and "must name something specific" in prompts[0]


def test_she_keeps_quiet_between_comments_but_still_answers_viewers(tmp_path):
    import threading
    import time
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    agent.cfg.commentary.max_silence_seconds = 0
    agent.cfg.commentary.min_seconds_between = 30
    agent.narrator.last_spoke = time.time()
    commented, replied = [], []
    agent.brain.comment = lambda events, ctx: commented.append(events) or ""
    agent.brain.reply_to_chat = lambda user, message, context: replied.append(user) or "Sam, you absolute menace."
    agent._queue_comment("Someone challenged you to a battle!")
    threading.Thread(target=agent._commentary_worker, daemon=True).start()
    time.sleep(1.5)
    messages = [("sam", "hello")]
    agent.chat = NS(take=lambda: messages.pop() if messages else None)
    time.sleep(2.5)
    assert commented == [] and replied == ["sam"]


def test_a_busy_game_cannot_drown_out_a_viewer(tmp_path):
    import threading
    import time
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    agent.cfg.commentary.max_silence_seconds = 0
    agent.narrator.say = lambda text: None
    agent.brain.comment = lambda events, ctx: ""
    messages, replied = [("sam", "hello")], []
    agent.chat = NS(take=lambda: messages.pop() if messages else None)
    agent.brain.reply_to_chat = lambda user, message, context: replied.append(user) or "Sam, you absolute menace."
    for _ in range(50):
        agent._queue_comment("Someone challenged you to a battle!")
    threading.Thread(target=agent._commentary_worker, daemon=True).start()
    time.sleep(1)
    assert replied == ["sam"]


def test_a_battle_is_announced_once_until_she_is_back_on_the_map(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    agent.game = NS(party=lambda: [], decode_mon=lambda raw: None,
                    battle_info=lambda: NS(is_trainer=True, enemy=NS(species_name="CATERPIE", level=10)))
    agent.emu = NS(wait_frames=lambda frames: None, read=lambda address, size: b"", u8=lambda address: 0)
    agent.pilot.reset = lambda: None
    events = []
    agent._event = events.append
    agent._on_mode_change("other", "battle")
    agent._in_battle = False                                        # what a screen change mid-battle does
    agent._on_mode_change("other", "battle")
    assert len(events) == 1 and agent.memory.stats["battles"] == 1


def test_no_attacks_and_nobody_to_swap_to_plays_it_out(tmp_path):
    from types import SimpleNamespace as NS

    agent, _ = _named_agent(tmp_path)
    agent.brain.decide = lambda context, lines: 1 / 0               # must not need the model
    agent.game.party = lambda: [NS(hp=28, moves=[NS(power=0, pp=9), NS(power=35, pp=0)]), NS(hp=0, moves=[NS(power=15, pp=9)])]
    labels = ["Use GROWL (Normal type, 40 PP left, does no direct damage)",
              "Use LEECH SEED (Grass type, 9 PP left, does no direct damage)",
              "Open your Bag (items, Poké Balls)", "Switch to a different Pokémon"]
    assert not agent._someone_to_switch_to()
    assert agent._choose_battle_action(_battle_info(is_trainer=True), labels, []) == 1
    assert agent._last_resort_move(["Fight (no PP left on any move)", "Open your Bag (items, Poké Balls)"]) == 0


def test_forced_send_out_uses_whoever_is_left(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    agent._in_battle = False                                        # lost during the screen change into this menu
    agent._leaving_menus = True                                     # and this made her press B forever
    agent._party_menu_tries = 99
    agent.game.team_menu_in_battle = lambda: True
    agent.game.party = lambda: [NS(hp=0, moves=[NS(power=15, pp=32)]), NS(hp=0, moves=[NS(power=15, pp=35)]),
                                NS(hp=22, moves=[NS(power=0, pp=2), NS(power=35, pp=0)])]
    chosen = []
    agent.menus.choose = lambda menu, slot: chosen.append(slot)
    agent.pressed.clear()
    agent._menu_turn(Menu("party_choose", "Choose a Pokémon.", ["A", "B", "C"]))
    agent._menu_turn(Menu("party_action", "What to do?", ["SHIFT", "SUMMARY", "CANCEL"]))
    assert chosen == [2, 0] and agent.pressed == [] and agent.prompts == []


def test_switching_gives_up_instead_of_looping(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay.brain import Decision
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    agent._in_battle = True
    agent.game.party = _team
    agent.game.state = lambda: NS(items=[("Potion", 1)], balls=[], party=[NS(species=1)])
    agent.brain.decide = lambda context, lines: agent.prompts.append(lines) or Decision("t", "", 0)
    labels = ["Use GROWL (does no direct damage)", "Switch to a different Pokémon"]
    picks = [agent._choose_battle_action(_battle_info(is_trainer=True), labels, []) for _ in range(4)]
    assert picks == [1, 1, 1, 0] and agent.prompts == []            # after three tries it stops forcing the switch

    agent.game.party = lambda: [NS(hp=0, moves=[NS(power=15, pp=9)]), NS(hp=0, moves=[NS(power=15, pp=9)])]
    agent.pressed.clear()
    agent._party_menu_tries = 0
    agent._menu_turn(Menu("party_choose", "Choose a Pokémon.", ["A", "B"]))
    assert agent.pressed == ["B"]                                   # never picks a fainted one


def test_hm_notes_explain_teaching_and_sources(tmp_path):
    from pokeplay import hints as h

    for needed in ("TM CASE", "must have learned", "CUT from", "FLY from", "SURF from", "STRENGTH from", "FLASH from"):
        assert needed in h.HM_NOTE
    notes = tmp_path / "guide.md"
    notes.write_text("# Notes\n## Badges\nStuff.\n## HMs\nCut: ship.\n## Main story\nGo.\n", encoding="utf-8")
    assert h.guide_hms(notes) == "Cut: ship."
    assert h.guide_hms(tmp_path / "missing.md") == ""


def test_bag_menus_explain_teaching_an_hm(tmp_path):
    from pokeplay.hints import HM_TEACHING
    from pokeplay.menus import Menu

    agent = _menu_agent(tmp_path)
    contexts = []
    decide = agent.brain.decide
    agent.brain.decide = lambda context, lines: contexts.append(context) or decide(context, lines)
    agent._menu_turn(Menu("bag", "Your Bag is open on the ITEMS pocket.", ["POTION"]))
    assert HM_TEACHING in contexts[0]


def test_impossible_actions_stop_being_offered(tmp_path):
    from types import SimpleNamespace as Opt

    agent, _ = _named_agent(tmp_path)
    south, north = Opt(key="south"), Opt(key="north")
    agent._record_outcome("south", "stuck")
    assert agent._drop_worn_out([south, north]) == [north]      # gone after one failure, not three
    agent._record_outcome("north", "warped")
    assert agent._drop_worn_out([south, north]) == [north]


def test_near_copies_stay_out_of_her_journal(tmp_path):
    agent, _ = _named_agent(tmp_path)
    agent.memory.journal.append("A patch of grass appeared near the northwest corner of the room.")
    assert not agent._worth_noting("A grass patch appeared near the northwest corner of the room.")
    assert agent._worth_noting("The man by the fence sells potions.")


def test_nicknames_are_not_pokemon_names():
    from pokeplay.brain import Brain

    b = Brain("http://x", "m")
    replies = iter(['{"name": "Pikachu", "say": "no"}', '{"name": "Sprout", "say": "yes"}'])
    b._chat = lambda messages, **k: next(replies)
    assert b.choose_name("nickname", 10, "BULBASAUR") == ("Sprout", "yes")


def test_a_fresh_mgba_picks_up_her_saved_game(tmp_path):
    from types import SimpleNamespace as NS

    def agent_at(mode, party):
        agent, _ = _named_agent(tmp_path)
        agent.loaded = []
        team = list(party)

        def load(slot):
            agent.loaded.append(slot)
            team.append(NS(hp=20))
        agent.emu.load_state = load
        agent.emu.wait_frames = lambda frames: None
        agent.game.mode = lambda: mode
        agent.game.party = lambda: team
        return agent

    title = agent_at("other", [])
    title._resume_saved_game()
    assert title.loaded == [9]
    for mode, party in (("overworld", [NS(hp=20)]), ("other", [NS(hp=20)]), ("naming", []), ("dialog", [])):
        running = agent_at(mode, party)                     # never yank her out of a game that's under way
        running._resume_saved_game()
        assert running.loaded == []

    no_autosave = agent_at("other", [])
    no_autosave.cfg.emulator.autosave_minutes = 0
    no_autosave._resume_saved_game()
    assert no_autosave.loaded == []


def test_she_gives_everything_its_own_name(tmp_path):
    from types import SimpleNamespace as NS
    from pokeplay.brain import Brain

    b = Brain("http://x", "m", streamer_name="Zorblax")
    replies = iter(['{"name": "ZORBLAX", "say": "no"}', '{"name": "Zorblax2", "say": "no"}', '{"name": "Mildew", "say": "yes"}'])
    sent = []
    b._chat = lambda messages, **k: sent.append(messages) or next(replies)
    assert b.choose_name("caught", 10, "RATTATA", "", ["Zorblax"]) == ("Mildew", "yes")
    assert "Zorblax" not in sent[0][0]["content"] and "already used" in sent[1][1]["content"]

    b._chat = lambda messages, **k: '{"name": "Zorblax", "say": "again"}'
    assert b.choose_name("caught", 10, "RATTATA", "", ["Zorblax"]) == ("", "")      # the game's own name beats a repeat
    assert b.choose_name("player", 7, "", "", ["Zorblax"]) == ("Zorblax", "again")  # only her own character may keep it

    agent, _ = _named_agent(tmp_path)
    agent.memory.journal = ["You named your rival 'Blorp'.", "A tree blocked the way."]
    agent.game.party = lambda: [NS(nickname="Mildew")]
    assert agent._names_in_use() == ["Oldname", "Blorp", "Mildew"]


def test_guesses_stay_out_of_her_journal(tmp_path):
    from pokeplay.brain import Decision

    agent, _ = _named_agent(tmp_path)
    agent._apply_decision(Decision("t", "", 0, note="The corner might have a hidden ball."), "Go north")
    agent._apply_decision(Decision("t", "", 0, note="Resetting the game could help."), "Go north")
    assert agent.memory.journal == []
    agent._apply_decision(Decision("t", "", 0, note="The stairs lead to the first floor."), "Go north")
    assert agent.memory.journal == ["The stairs lead to the first floor."]


def test_she_has_general_game_sense_but_no_game_knowledge():
    from pokeplay.brain import GAME_SENSE, Brain
    assert GAME_SENSE in Brain("http://x", "m")._system()
    for word in ("Pallet", "Oak", "starter", "gym", "badge"):
        assert word.lower() not in GAME_SENSE.lower()


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


def test_reused_phrases_and_openings_count_as_repeats():
    from pokeplay.brain import Brain
    b = Brain("http://x", "m")
    b.remember_said("Blinking bag! I think this pocket has the ball. Hope it's not a weird rock this time!")
    assert b.is_repeat("Off we go to the next pocket, hope it's not a weird rock again.")     # same phrase
    assert b.is_repeat("Blinking bag! Maybe it wants something from me.")                     # same opening
    # Ordinary sentence pieces shouldn't silence her.
    assert not b.is_repeat("I think I need to talk to that person by the fence.")
    for i in range(29):
        b.remember_said(f"filler {i}")
    assert any("Blinking" in s for s in b.recent_said)      # remembered well past her last few lines


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
    agent.brain.comment = lambda events, ctx: asked.append(events[0]) or "This forest all looks the same."
    agent.narrator.last_spoke = time.time() - 5
    threading.Thread(target=agent._commentary_worker, daemon=True).start()
    time.sleep(3)
    assert asked and "walking north through the forest" in asked[0]
    assert "This forest all looks the same." in agent.brain.recent_said
