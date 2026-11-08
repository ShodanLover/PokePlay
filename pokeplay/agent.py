"""The main loop: watch the game, let her decide, act, and let her talk."""

from __future__ import annotations

import collections
import difflib
import json
import queue
import random
import threading
import time

from . import addresses as A
from .battle import BattlePilot, Choice, hp_bar
from .brain import COMMON_WORDS, GUESSWORK, OVERUSED_WORDS, Brain, BrainOffline, _words, clean_spoken
from .config import Config
from .emulator import Emulator
from .game import BattleInfo, Game, GameState, Mon
from .memory import Memory
from .menus import Menu, MenuReader
from .naming import MAX_CHARS, NamingScreen, clean_name
from .hints import hint_for, target_for
from .narrator import Narrator
from .news import Headlines
from .overlay.server import OverlayState, start_overlay
from .overworld import BLOCKED_EXIT, Overworld

KIND_ORDER = {"warp": 0, "exit": 1, "talk": 2, "train": 3, "explore": 4}
BATTLE_OUTCOMES = {1: "won", 2: "lost", 3: "drew", 4: "ran away", 5: "teleported away",
                   6: "the wild Pokémon fled", 7: "caught it"}
MAX_TALK_OPTIONS = 5
REFLECT_EVERY = 12          # decisions between reflections
JOURNAL_LIMIT = 40          # condense the journal when it gets this long
GAME_QUESTIONS = {"yesno", "multichoice", "forget_move", "quantity"}   # must be answered; every other menu she opened
MENU_STREAK_LIMIT = 12      # this many menu choices in a row means she's lost in there, however varied they are
NO_TURNING_BACK = 6         # map decisions in a new place before she may go back the way she came
GUIDED_UNTIL_BADGES = 2     # the opening is spelled out for her until she has this many badges
HINT_EVERY = 15           # map decisions between hints about what to do next
HINT_LASTS = 4              # how many map decisions each hint stays in her mind
GOAL_PATIENCE = 15         # decisions with no discovery before her current goal is dropped
EVENT_MAX_AGE = 6        # seconds after which something that happened is too old to react to
STALE_AFTER = 6            # map decisions with no new place, door or person before she must try what she's tried least
REPEAT_LIMIT = 3           # the same action this many times in her last 6 means it isn't working
REST_DECISIONS = 10         # map decisions before she's offered that action again
SPEAK_DECISION_CHANCE = 0.3 # the rest of her talking comes from comments, which vary far more
LONG_SILENCE = 15        # seconds without a spoken line before the repeat check relaxes
MENU_LOOP_LIMIT = 3        # picking the same thing this many times without leaving means she's going in circles
MENU_COOLDOWN = 8           # map decisions before the main menu is offered again after that


def _ideas(text: str) -> set[str]:
    return {w.removesuffix("'s") for w in _words(text) if len(w) >= 4 and w not in COMMON_WORDS}


def _same_idea(a: str, b: str) -> bool:
    """True if two sentences are about the same thing ("fix the nickname" / "Bulbasaur's nickname is wrong")."""
    x, y = _ideas(a), _ideas(b)
    return bool(x and y) and len(x & y) >= min(2, len(x), len(y))


class Agent:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.emu = Emulator(cfg.emulator.host, cfg.emulator.port)
        self.game = Game(self.emu)
        self.brain = Brain(cfg.brain.ollama_url, cfg.brain.model, cfg.brain.streamer_name,
                           cfg.brain.temperature, cfg.brain.context_tokens)
        self.memory = Memory.load(cfg.brain.memory_file)
        self.overlay = OverlayState()
        self.overlay.update(twitch_channel=cfg.overlay.twitch_channel.strip().lower().rsplit("/", 1)[-1].lstrip("#"))
        self.brain.obsession = cfg.brain.obsession
        self.news = Headlines(cfg.brain.news_feeds)
        self.brain.headlines = self.news.take
        self.narrator = Narrator(cfg.voice.engine, cfg.voice.piper_model, cfg.voice.rate,
                                 on_speak=lambda t: self.overlay.update(say=t, subtitle=t),
                                 on_done=lambda: self.overlay.update(subtitle=""),
                                 gender=cfg.voice.gender, volume=cfg.voice.volume,
                                 voice_name=cfg.voice.voice_name, piper_exe=cfg.voice.piper_exe,
                                 kokoro_voice=cfg.voice.kokoro_voice, speed=cfg.voice.speed)
        self.naming = NamingScreen(self.emu)
        self.world = Overworld(self.emu, self.game, self.memory)
        self.pilot = BattlePilot(self.emu, self.game, chooser=self._choose_battle_action,
                                 party_chooser=self._choose_next_pokemon, yesno_chooser=self._answer_battle_question)
        self.menus = MenuReader(self.emu, self.game)
        self._in_menus = False          # she opened something; escape unknown screens with B
        self._think_seconds = 3.0       # how long her last decision took (keeps the gap between thoughts short)
        self._think_started = time.time()

        self.history: collections.deque[str] = collections.deque(maxlen=10)
        self.pick_counts: collections.Counter[str] = collections.Counter()
        self._menu_picks: collections.Counter[tuple[str, str]] = collections.Counter()   # since she last left the menus
        self._leaving_menus = False
        self._failed_options: set[str] = set()      # map actions that just didn't work
        self._recent_picks: collections.deque[str] = collections.deque(maxlen=6)
        self._worn_out: dict[str, int] = {}         # options set aside: decisions left until they come back
        self._hint_clock = -1
        self._came_from = ""                        # the place she was in before this one
        self._decisions_here = 0
        self._snapshot: dict | None = None          # what she last knew about, to spot what changed
        self._changes: list[str] = []
        self._decisions_on_goal = 0                 # decisions since her goal changed or she found something new
        self._abandoned_goals: collections.deque[str] = collections.deque(maxlen=5)
        self._last_said = time.time()
        self._menu_cooldown = 0        # map decisions until the main menu is offered again
        self._events: queue.Queue[str] = queue.Queue()
        self._context = ""
        self._last_message = ""
        self._dialog_presses = 0
        self._dialog_lines: list[str] = []
        self._talking_to: str | None = None
        self._other_loops = 0
        self._prev_mode = ""
        self._in_battle = False
        self._named_this_screen = False
        self._party_before_battle: list = []
        self._last_autosave = time.time()
        self._last_overlay = 0.0
        self._last_tick = time.time()
        self._last_map = None
        self._decisions_since_reflect = 0
        self._actions_since_discovery = 0
        self._last_state: GameState | None = None
        self._activity = "just getting started"

    # ------------------------------------------------------------------ startup
    def start(self) -> None:
        print("Connecting to mGBA...")
        self.emu.connect(retry_seconds=600)
        print(f"Found {self.game.check_rom()}")
        self.game.load_tables()
        print("Read species, move and item data from the ROM.")
        self._wait_for_brain(first=True)
        self._load_persona()
        start_overlay(self.overlay, self.cfg.overlay.port)
        print(f"Overlay: http://127.0.0.1:{self.cfg.overlay.port}  Subtitles: http://127.0.0.1:{self.cfg.overlay.port}/subtitles")
        self.memory.bump("sessions")
        self.memory.save()
        self.overlay.update(goal=self.memory.goal, mood=self.memory.mood)
        self.news.start()
        if self.cfg.commentary.enabled:
            threading.Thread(target=self._commentary_worker, daemon=True).start()

    def _wait_for_brain(self, first: bool = False) -> None:
        delay = 10
        while True:
            try:
                self.brain.check()
                if first:
                    print(f"Ollama model '{self.cfg.brain.model}' is ready.")
                return
            except Exception as e:  # noqa: BLE001
                print(f"[agent] AI not available ({e}); retrying in {delay}s")
                self.overlay.update(thought="(my brain is rebooting... one sec)")
                time.sleep(delay)
                delay = min(delay * 2, 120)

    def _load_persona(self) -> None:
        """She picks her own name and personality the first time, then keeps them."""
        path = self.cfg.brain.persona_file
        try:
            with open(path, encoding="utf-8") as f:
                persona = json.load(f)
        except (OSError, ValueError):
            print("First launch: letting the AI choose who she wants to be...")
            persona = self.brain.create_persona(self.cfg.brain.persona_hint)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(persona, f, indent=2, ensure_ascii=False)
        if self.cfg.brain.streamer_name:          # manual override, if you ever want one
            persona["name"] = self.cfg.brain.streamer_name
        self.brain.name = persona["name"]
        # The catchphrase is NOT in every prompt (a small model would repeat it constantly).
        self.brain.personality = persona.get("personality", "")
        self.brain.catchphrase = persona.get("catchphrase", "")
        if self.cfg.brain.speaking_style:
            self.brain.style = self.cfg.brain.speaking_style
        self.overlay.update(streamer=persona["name"])
        print(f"She is: {persona['name']} - {persona.get('personality', '')}")

    def _take_name(self, name: str) -> None:
        """The name she gives her character becomes her name (unless streamer_name is set in config.toml)."""
        if not name or self.cfg.brain.streamer_name:
            return
        path = self.cfg.brain.persona_file
        try:
            with open(path, encoding="utf-8") as f:
                persona = json.load(f)
        except (OSError, ValueError):
            persona = {}
        old = persona.get("name", "")
        if old:                                   # e.g. a catchphrase that mentions her old name
            persona = {k: v.replace(old, name) if isinstance(v, str) else v for k, v in persona.items()}
        persona["name"] = name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(persona, f, indent=2, ensure_ascii=False)
        self.brain.name = name
        self.brain.personality = persona.get("personality", "")
        self.brain.catchphrase = persona.get("catchphrase", "")
        self.overlay.update(streamer=name)
        print(f"She now goes by: {name}")

    def run(self) -> None:
        self.start()
        while True:
            try:
                self.tick()
            except KeyboardInterrupt:
                raise
            except BrainOffline as e:
                print(f"[agent] {e}")
                self._wait_for_brain()
            except Exception as e:  # noqa: BLE001 - keep the stream alive
                print(f"[agent] error: {e!r}; retrying in 2s")
                time.sleep(2)
                try:
                    self.emu.command("PING")
                except Exception:  # noqa: BLE001
                    self.emu.close()
                    self.emu.connect(retry_seconds=3600)

    # ------------------------------------------------------------------ main tick
    def tick(self) -> None:
        mode = self.game.mode()
        if mode != self._prev_mode:
            self._on_mode_change(self._prev_mode, mode)
            self._prev_mode = mode

        menu = self.menus.read() if mode != "naming" else None
        if menu is not None:
            self._menu_turn(menu)
        elif mode == "battle":
            self.pilot.step()
            self._absorb_battle_lessons()
        elif mode == "party_menu":
            if self._leaving_menus and not self._in_battle:
                self.emu.press("B", hold=2, wait=20)
            else:
                self.pilot.party_menu()  # fallback if the party screen isn't readable yet
        elif mode == "dialog":
            self._dialog()
        elif mode == "overworld":
            self._dialog_presses = 0
            self._in_menus = False
            self._overworld_turn()
        elif mode in ("summary", "bag"):
            self.emu.wait_frames(20)
            self._other_loops += 1
            if self._other_loops % 4 == 0:
                self.emu.press("B", hold=2, wait=12)
        elif mode == "naming":
            self._name_something()
        else:
            # Screen transitions, title screen, evolution, or a screen she opened (Pokédex, trainer card...).
            self._other_loops += 1
            if self._other_loops % 6 == 0:
                # Inside menus she opened: B backs out. Otherwise A moves things along
                # (never B by default: B would cancel an evolution).
                self.emu.press("B" if self._in_menus else "A", hold=2, wait=10)
            else:
                self.emu.wait_frames(10)

        if mode not in ("other", "summary", "bag"):
            self._other_loops = 0
        if mode != "naming":
            self._named_this_screen = False
        self._periodic(mode)

    def _periodic(self, mode: str) -> None:
        now = time.time()
        self.memory.bump("play_seconds", min(now - self._last_tick, 60))
        self._last_tick = now
        if now - self._last_overlay > 2:
            self._last_overlay = now
            try:
                party = self.game.party()
                self.overlay.update(mode=mode, party=[
                    {"name": m.nickname, "level": m.level, "hp": m.hp, "max_hp": m.max_hp, "status": m.status,
                     "sprite": self.game.mon_icon(m.species)}
                    for m in party])
            except Exception:  # noqa: BLE001
                pass
            st = self.memory.stats
            self.memory.stats["steps"] = st.get("steps", 0)
            self.overlay.update(stats={
                "day": self.memory.days_since_start(),
                "hours": round(st.get("play_seconds", 0) / 3600, 1),
                "steps": int(st.get("steps", 0)),
                "battles": int(st.get("battles", 0)),
                "won": int(st.get("battles_won", 0)),
                "lost": int(st.get("battles_lost", 0)),
                "fainted": int(st.get("pokemon_fainted", 0)),
                "places": len(self.memory.places),
            })
        minutes = self.cfg.emulator.autosave_minutes
        if minutes and mode == "overworld" and now - self._last_autosave > minutes * 60:
            self._last_autosave = now
            self.emu.save_state(self.cfg.emulator.autosave_slot)
            self.memory.save()
            print(f"[agent] backup saved (state slot {self.cfg.emulator.autosave_slot} + memory)")

    # ------------------------------------------------------------------ events
    def _on_mode_change(self, old: str, new: str) -> None:
        if old == "dialog" and new != "dialog":
            self._finish_conversation()
        if new == "battle" and not self._in_battle:
            self._in_battle = True
            self.memory.bump("battles")
            self.pilot.reset()
            self._party_before_battle = self.game.party()
            self.emu.wait_frames(30)   # let the battle data fill in
            info = self.game.battle_info()
            foe = self.game.decode_mon(self.emu.read(A.gEnemyParty, 100)) or info.enemy
            if foe:
                who = "Someone challenged you to a battle" if info.is_trainer else "A wild creature jumped out"
                self._event(f"{who}! It's called {foe.species_name}, level {foe.level}.")
        elif self._in_battle and new not in ("battle", "party_menu"):
            self._in_battle = False
            outcome = BATTLE_OUTCOMES.get(self.emu.u8(A.gBattleOutcome), "")
            if outcome == "won":
                self.memory.bump("battles_won")
            elif outcome == "lost":
                self.memory.bump("battles_lost")
            after = self.game.party()
            lines = []
            for b, a in zip(self._party_before_battle, after):
                if a.species != b.species and a.level >= b.level:
                    lines.append(f"{b.nickname} changed form and is now a {a.species_name}!")
                elif a.level > b.level:
                    lines.append(f"{a.nickname} grew to level {a.level}!")
                if a.fainted and not b.fainted:
                    self.memory.bump("pokemon_fainted")
            if outcome:
                self.history.append(f"Battle ended: {outcome}.")
                lines.insert(0, f"The battle is over: you {outcome}." if outcome in ("won", "lost", "drew", "ran away")
                             else f"The battle is over: {outcome}.")
            if lines:
                self._event(" ".join(lines))
            self.memory.save()
            self._decisions_since_reflect = REFLECT_EVERY   # reflect after each battle

    def _event(self, text: str) -> None:
        print(f"[event] {text}")
        self.overlay.log(text)
        self.history.append(text)
        if self.cfg.commentary.enabled:
            self._queue_comment(text)

    def _queue_comment(self, text: str) -> None:
        self._events.put((time.time(), text))

    def _commentary_worker(self) -> None:
        last = 0.0
        silence = self.cfg.commentary.max_silence_seconds
        while True:
            try:
                batch = [self._events.get(timeout=2)]
            except queue.Empty:
                quiet_for = time.time() - self.narrator.last_spoke
                if silence and quiet_for >= silence and not self.narrator.is_speaking():
                    for _ in range(3):              # a line can be dropped as a repeat: try again
                        line = self.brain.comment(
                            [f"It's been quiet for a bit. Right now you're: {self._activity}. Think out loud about "
                             "whatever is on your mind: what you're doing, your team, your plan, something you "
                             "noticed, or how it's going. Say something you haven't said yet."],
                            self._context or "You've only just started playing.")
                        if line and self._speak(line):
                            break
                    self.narrator.last_spoke = time.time()   # don't retry instantly if it failed
                continue
            time.sleep(1.0)    # group things that happen close together
            while not self._events.empty():
                batch.append(self._events.get_nowait())
            wait = self.cfg.commentary.min_seconds_between - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            fresh = [text for when, text in batch if time.time() - when <= EVENT_MAX_AGE]
            if not fresh:                       # reacting now would be talking about something long over
                continue
            line = self.brain.comment(fresh[-3:], self._context)
            if line:
                self._speak(line)
                last = time.time()

    def _speak(self, text: str) -> bool:
        """Say a line out loud, unless it's basically a repeat of something she just said. True if it was said."""
        text = clean_spoken(text, self.brain.name)
        if not text:
            return False
        if OVERUSED_WORDS.search(text):
            print(f"[voice] (skipped overused word) {text}")
            return False
        quiet_too_long = time.time() - self._last_said > LONG_SILENCE     # silence is worse than a similar line
        if self.brain.is_repeat(text, lenient=quiet_too_long):
            print(f"[voice] (skipped repeat) {text}")
            return False
        self.brain.remember_said(text)
        self._last_said = time.time()
        self.narrator.say(text)
        return True

    # ------------------------------------------------------------------ battle choices (hers)
    def _battle_context(self, info: BattleInfo) -> str:
        me, foe = info.player, info.enemy
        words = [foe.species_name if foe else "", me.species_name if me else ""] + \
                [m.name for m in (me.moves if me else [])]
        lessons = self.memory.relevant_lessons(words)
        parts = [
            "YOU ARE IN A BATTLE" + (" against another trainer (you can't run away)." if info.is_trainer else
                                     " with a wild creature."),
            f"Your Pokémon: {me.summary() if me else '?'}",
            f"Opponent: {foe.species_name} level {foe.level}, its HP bar is {hp_bar(foe)}"
            + (f" [{foe.status}]" if foe and foe.status else "") if foe else "Opponent: ?",
            f"Latest battle message: {info.message}" if info.message else "",
            ("Things you've noticed in past battles:\n" + "\n".join(f"- {l}" for l in lessons)) if lessons
            else "You haven't learned anything about how battles work yet.",
        ]
        return "\n".join(p for p in parts if p)      # only the battle: her notes and goal just distract her here

    def _choose_battle_action(self, info: BattleInfo, labels: list[str], choices: list[Choice]) -> int:
        context = self._battle_context(info)
        self._context = context
        self._wait_for_voice()
        self.overlay.update(thought="Thinking...")
        shown = self._usable_battle_labels(labels)
        d = self.brain.decide(context, [labels[i] for i in shown])
        chosen = shown[d.choice]
        self._apply_decision(d, labels[chosen])
        self.history.append(f"In battle: {labels[chosen]}")
        return chosen

    def _usable_battle_labels(self, labels: list[str]) -> list[int]:
        """Positions of the battle choices worth offering: an empty bag has nothing to use."""
        everything = list(range(len(labels)))
        try:
            s = self.game.state()
        except Exception:  # noqa: BLE001 - never let this get in the way of a battle
            return everything
        if s.items or s.balls:
            return everything
        return [i for i in everything if "your Bag" not in labels[i]] or everything

    def _choose_next_pokemon(self, alive: list[tuple[int, Mon]]) -> int:
        labels = [f"Send out {m.summary()}" for _, m in alive]
        context = self._memory_text(short=True) + "\n\nYour Pokémon fainted! Choose who to send out next."
        self._wait_for_voice()
        d = self.brain.decide(context, labels)
        self._apply_decision(d, labels[d.choice])
        return d.choice

    def _answer_battle_question(self, question: str) -> bool:
        context = self._memory_text(short=True) + f"\n\nIN BATTLE, the game asks: \"{question}\""
        self._wait_for_voice()
        d = self.brain.decide(context, ["YES", "NO"])
        self._apply_decision(d, f"Answered {'YES' if d.choice == 0 else 'NO'} to: {question}")
        return d.choice == 0

    # ------------------------------------------------------------------ menus (hers)
    def _menu_turn(self, menu: Menu) -> None:
        self._in_menus = True
        browsing = menu.kind not in GAME_QUESTIONS and not self._in_battle
        if browsing and self._leaving_menus:
            self.emu.press("B", hold=2, wait=20)
            return
        if self.game.mode() == "battle" or self._in_battle:
            msg = self.pilot._last_msg or self._last_message
        else:
            msg = self.game.message() or self._last_message
        self.menus.last_message = msg
        if menu.kind in ("yesno", "multichoice") and msg:
            menu.title = f'The game asks: "{msg}"'
        options = menu.all_options()
        cursor = f" (the cursor is on: {options[menu.cursor]})" if 0 <= menu.cursor < len(options) else ""
        context = (self._memory_text(short=True) + f"\n\nON SCREEN: {menu.title}{cursor}\n"
                   "You navigate menus one choice at a time, like using a controller.")
        lines = list(options)
        if browsing:
            for i, option in enumerate(options):
                n = self._menu_picks[(menu.title[:60], option)]
                if n:
                    lines[i] += f" [you've already picked this {n} time{'s' if n > 1 else ''} just now]"
        self._wait_for_voice()
        self.overlay.update(thought="Thinking...")
        d = self.brain.decide(context, lines)
        label = options[d.choice]
        self._apply_decision(d, f"{menu.title[:60]} -> {label}")
        if browsing:
            self._menu_picks[(menu.title[:60], label)] += 1
            if (self._menu_picks[(menu.title[:60], label)] >= MENU_LOOP_LIMIT
                    or sum(self._menu_picks.values()) >= MENU_STREAK_LIMIT):
                print("[agent] going round in circles in the menus; closing them")
                self.history.append("You kept going round in circles in the menus, so you closed them.")
                self._leaving_menus = True
                self._menu_cooldown = MENU_COOLDOWN
                self.emu.press("B", hold=2, wait=20)
                return
        done = self.menus.choose(menu, d.choice)
        self.history.append(f"Menu ({menu.title[:70]}): chose {done}")
        if menu.kind == "yesno" and "?" in msg:
            self.memory.add_journal(f'When asked "{msg[:100]}", you answered {label}.')

    def _absorb_battle_lessons(self) -> None:
        while self.pilot.lessons:
            lesson = self.pilot.lessons.pop(0)
            if self.memory.add_lesson(lesson):
                self._event(f"You noticed: {lesson}")

    # ------------------------------------------------------------------ naming (hers)
    def _name_something(self) -> None:
        if self._named_this_screen:
            self.emu.press("START", hold=2, wait=10)   # already typed: confirm with OK
            self.emu.press("A", hold=2, wait=20)
            return
        self._named_this_screen = True
        self.emu.wait_frames(40)    # let the screen fade in
        kind, species_id = self.naming.info()
        species = self.game.species_name(species_id) if kind in ("nickname", "caught") else ""
        self._wait_for_voice()
        self.overlay.update(thought="Thinking of a name...")
        name, say = self.brain.choose_name(kind, MAX_CHARS.get(kind, 7), species, self._memory_text(short=True))
        if say:
            self._speak(say)
        self.overlay.update(thought=f"Typing the name: {name}")
        if name and self.naming.type_name(name):
            if kind == "player":
                self._take_name(clean_name(name, MAX_CHARS["player"]))
            what = {"player": "yourself", "rival": "your rival"}.get(kind, f"your {species}")
            self.memory.add_journal(f"You named {what} '{name}'.")
            self._event(f"You named {what} '{name}'.")
        else:
            self.emu.press("START", hold=2, wait=10)   # fall back to the game's default name
            self.emu.press("A", hold=2, wait=20)

    # ------------------------------------------------------------------ dialog
    def _dialog(self) -> None:
        msg = self.game.message()
        if msg and msg != self._last_message:
            self._last_message = msg
            short = msg if len(msg) <= 200 else msg[:197] + "..."
            self._dialog_lines.append(short)
            self.history.append(f'On screen: "{short}"')
            self.overlay.log(f'💬 {short}')
            if self.cfg.commentary.enabled:
                self._queue_comment(f'Text on screen: "{short}"')
            self._dialog_presses = 0
        self._dialog_presses += 1
        # Mostly A to advance text; an occasional B closes menus we didn't mean to open.
        if self._dialog_presses % 12 == 0:
            self.emu.press("B", hold=2, wait=15)
        else:
            self.emu.press("A", hold=2, wait=15)

    def _finish_conversation(self) -> None:
        if self._dialog_lines:
            said = " ".join(self._dialog_lines)[:300]
            if self._talking_to:
                if self._talking_to not in self.memory.people:
                    self._discovered()
                self.memory.people[self._talking_to] = said
        self._dialog_lines = []
        self._talking_to = None

    # ------------------------------------------------------------------ memory text
    def _memory_text(self, short: bool = False) -> str:
        m = self.memory
        parts = []
        if m.goal:
            parts.append(f"YOUR CURRENT GOAL (you chose it): {m.goal}")
        if m.mood:
            parts.append(f"HOW YOU FEEL: {m.mood}")
        journal = m.journal[-(5 if short else 8):]      # a shorter prompt is a faster decision
        if journal:
            parts.append("YOUR JOURNAL (what you've learned so far):\n" + "\n".join(f"- {j}" for j in journal))
        else:
            parts.append("YOUR JOURNAL is empty. You've just started.")
        if not short and m.lessons:
            parts.append("THINGS YOU'VE NOTICED:\n" + "\n".join(f"- {l}" for l in m.lessons[-6:]))
        return "\n\n".join(parts)

    def _context_text(self, s: GameState) -> str:
        team = "\n".join(f"- {mon.summary()}; moves: " +
                         ", ".join(f"{mv.name} ({mv.type_name}, {mv.pp} PP)" for mv in mon.moves)
                         for mon in s.party) or "- (you don't have any Pokémon)"
        bag = ", ".join(f"{n} x{q}" for n, q in (s.items + s.balls)[:10]) or "empty"
        here = f"{s.map_group}.{s.map_num}|"
        people_here = [said for key, said in self.memory.people.items() if key.startswith(here)]
        places = list(dict.fromkeys(self.memory.places.values()))[-15:]
        parts = [
            self._memory_text(),
            f"WHERE YOU ARE: {s.map_name}.",
            "PLACES YOU'VE BEEN: " + (", ".join(places) if places else "just here"),
            f"YOUR POKÉMON:\n{team}",
            f"BAG: {bag}" + (f". KEY ITEMS: {', '.join(s.key_items)}" if s.key_items else "")
            + f". MONEY: ₽{s.money}. BADGES: {s.badges}.",
        ]
        if people_here:
            parts.append("WHAT PEOPLE HERE TOLD YOU:\n" + "\n".join(f'- "{p[:160]}"' for p in people_here[-5:]))
        if self.history:
            parts.append("RECENTLY (oldest first):\n" + "\n".join(f"- {h}" for h in self.history))
        parts.append("WHAT JUST CHANGED (this is real, so react to it):\n" + "\n".join(f"- {c}" for c in self._changes)
                     if self._changes else "WHAT JUST CHANGED: nothing since your last action.")
        if self._team_badly_hurt(s):
            parts.append("YOUR TEAM IS BADLY HURT: go to the nearest Pokémon Center and talk to the person at the "
                         "counter, or go home and talk to Mom, before doing anything else.")
        self._hint_clock += 1
        if s.badges < GUIDED_UNTIL_BADGES or self._hint_clock % HINT_EVERY < HINT_LASTS:
            parts.append("YOUR NEXT STEP (do this): " + self._next_step(s))
        if self._actions_since_discovery >= 8:
            parts.append(f"You've done {self._actions_since_discovery} things in a row without discovering "
                         "anything new.")
        return "\n\n".join(parts)

    def _discovered(self) -> None:
        self._actions_since_discovery = 0
        self._decisions_on_goal = 0

    def _set_goal(self, goal: str) -> None:
        """Her choice, unless it's an idea she just had to abandon. A really new goal gets a fresh chance."""
        goal = goal[:200]
        if any(_same_idea(goal, old) for old in self._abandoned_goals):
            return
        if not _same_idea(goal, self.memory.goal):
            self._decisions_on_goal = 0
        self.memory.goal = goal
        self.overlay.update(goal=goal)

    def _give_up_on_goal(self) -> None:
        """A goal that's gone nowhere for a while goes away, with the notes feeding it, so one idea can't take over."""
        old = self.memory.goal
        print(f"[agent] no progress for a while; dropping her goal: {old}")
        self._abandoned_goals.append(old)
        self.memory.journal = [note for note in self.memory.journal if not _same_idea(note, old)]
        self.memory.goal = ""
        self.memory.mood = ""
        self.history.clear()
        self._decisions_on_goal = 0
        self.overlay.update(goal="", mood="")

    # ------------------------------------------------------------------ her decisions
    def _wait_for_voice(self) -> None:
        """Let her finish talking, but never so long that she goes too long between thoughts."""
        if self.cfg.voice.wait_for_voice:
            # One second of slack: thinking time varies from one decision to the next.
            self.narrator.wait_until_quiet(max(0.0, self.cfg.brain.max_seconds_between_thoughts - self._think_seconds - 1))
        self._think_started = time.time()

    def _apply_decision(self, d, action_label: str) -> None:
        self._think_seconds = time.time() - self._think_started
        print(f"[brain] {d.thought}  ->  {action_label}")
        self._activity = action_label[:120]
        self.memory.bump("decisions")
        self.overlay.update(thought=d.thought, action=action_label)
        self.overlay.log(f"▶ {action_label}")
        # Most decision lines are just "here's what I'm doing", so she usually keeps these to herself.
        if d.say and not self.narrator.is_speaking() and random.random() < SPEAK_DECISION_CHANCE:
            self._speak(d.say)
        if d.note and self._worth_noting(d.note):
            self.memory.add_journal(d.note)
        if d.goal:
            self._set_goal(d.goal)
        if not self._in_battle:
            self._decisions_on_goal += 1
        if self.memory.goal and self._decisions_on_goal >= GOAL_PATIENCE:
            self._give_up_on_goal()
        self._decisions_since_reflect += 1

    def _maybe_reflect(self, s: GameState) -> None:
        if self._decisions_since_reflect < REFLECT_EVERY:
            return
        self._decisions_since_reflect = 0
        r = self.brain.reflect(self._context_text(s))
        if r.get("goal"):
            self._set_goal(r["goal"])
        if r.get("mood"):
            self.memory.mood = r["mood"][:40]
        if r.get("journal") and self._worth_noting(r["journal"]):
            self.memory.add_journal(r["journal"])
        if len(self.memory.journal) > JOURNAL_LIMIT:
            self.memory.journal = self.brain.condense(self.memory.journal)
        self.overlay.update(goal=self.memory.goal, mood=self.memory.mood)
        self.memory.save()

    @staticmethod
    def _team_badly_hurt(s: GameState) -> bool:
        return bool(s.party) and sum(m.hp for m in s.party) * 3 < sum(m.max_hp for m in s.party)

    def _note_changes(self, s: GameState) -> list[str]:
        """Exactly what changed since her last look: she can't see the screen, so this is what she reacts to."""
        now = {"place": s.map_name, "money": s.money, "team": {m.nickname: (m.hp, m.level) for m in s.party},
               "items": dict(s.items + s.balls)}
        old, self._snapshot = self._snapshot, now
        if old is None:
            return []
        changes = []
        if now["place"] != old["place"]:
            changes.append(f"You moved from {old['place']} to {now['place']}.")
        if now["money"] != old["money"]:
            changes.append(f"Your money went from ₽{old['money']} to ₽{now['money']}.")
        for name, (hp, level) in now["team"].items():
            if name not in old["team"]:
                changes.append(f"{name} joined your team.")
                continue
            old_hp, old_level = old["team"][name]
            if level > old_level:
                changes.append(f"{name} went from level {old_level} to level {level}.")
            if hp != old_hp:
                changes.append(f"{name}'s HP went from {old_hp} to {hp}.")
        for item in set(now["items"]) | set(old["items"]):
            before, after = old["items"].get(item, 0), now["items"].get(item, 0)
            if after > before:
                changes.append(f"You got {item} (now {after}).")
            elif after < before:
                changes.append(f"You used or lost {item} (now {after}).")
        return changes

    def _next_step(self, s: GameState) -> str:
        carrying_parcel = any("PARCEL" in item.upper() for item in s.key_items)
        if carrying_parcel:
            self.memory.stats["carried_parcel"] = 1
        delivered = bool(self.memory.stats.get("carried_parcel")) and not carrying_parcel
        return hint_for(s.badges, bool(s.party), s.key_items, list(self.memory.places.values()), delivered)

    def _follow_route(self, options: list, s: GameState) -> list:
        """In the guided opening, the exit or door for her next step is the one she takes. [] if there isn't one."""
        if s.badges >= GUIDED_UNTIL_BADGES:
            return []
        want = target_for(self._next_step(s), s.map_name)
        if not want:
            return []
        return [o for o in options if (o.kind == "exit" and o.label.startswith(f"Leave this area by the {want} side"))
                or (o.kind == "warp" and want in o.dest)]

    def _no_turning_back(self, options: list) -> list:
        """Just arrived somewhere? She has to give it a go before heading straight back the way she came."""
        if self._decisions_here >= NO_TURNING_BACK or not self._came_from:
            return options
        return [o for o in options if self.memory.links.get(o.key) != self._came_from] or options

    def _prefer_untried(self, options: list) -> list:
        """No progress for a while? Then she can only pick from what she's tried least, so she works through it all."""
        if self._actions_since_discovery < STALE_AFTER:
            return options
        choices = [o for o in options if o.kind != "menu"] or options
        fewest = min(self.pick_counts[o.key] for o in choices)
        return [o for o in choices if self.pick_counts[o.key] == fewest]

    def _record_outcome(self, key: str, outcome: str) -> None:
        """If something couldn't be done at all (like walking into water), stop offering it for a while."""
        if outcome in ("stuck", "no_path"):
            self._failed_options.add(key)
            self._worn_out[key] = REST_DECISIONS
        else:
            self._failed_options.discard(key)

    def _worth_noting(self, note: str) -> bool:
        """Her journal is for new facts: guesses and near-copies of recent notes make her talk in circles."""
        if GUESSWORK.search(note) or any(_same_idea(note, old) for old in self._abandoned_goals):
            return False
        return not any(difflib.SequenceMatcher(None, note.lower(), old.lower()).ratio() > 0.6
                       for old in self.memory.journal[-15:])

    def _note_pick(self, key: str) -> None:
        """Doing the same thing again and again means it isn't working, wherever she is in the game."""
        self._recent_picks.append(key)
        if self._recent_picks.count(key) >= REPEAT_LIMIT:
            self._worn_out[key] = REST_DECISIONS
            self._recent_picks.clear()

    def _drop_worn_out(self, options: list) -> list:
        """Take away what she keeps retrying for a while, so she has to try something else."""
        self._worn_out = {k: n - 1 for k, n in self._worn_out.items() if n > 1}
        return [o for o in options if o.key not in self._worn_out] or options

    def _overworld_turn(self) -> None:
        self._menu_picks.clear()
        self._leaving_menus = False
        s = self.game.state()
        self._changes = self._note_changes(s)
        self.world.mark_visited(s)
        map_key = f"{s.map_group}.{s.map_num}"
        if self.memory.visit(map_key, s.map_name):
            self._discovered()
            self._event(f"You arrived somewhere new: {s.map_name}.")
        self._decisions_here += 1
        if self._last_map != map_key:
            self._came_from = self.memory.places.get(self._last_map, "")
            self._decisions_here = 0
            self._last_map = map_key
            self.overlay.log(f"📍 {s.map_name}")
        self.overlay.update(location=s.map_name, badges=s.badges, money=s.money)
        self._maybe_reflect(s)

        self.world.show_destinations = s.badges < GUIDED_UNTIL_BADGES
        options, _grid = self.world.build_options(s)
        if not options:
            self.history.append("Couldn't find anywhere to go, wiggling around.")
            for d in ("UP", "DOWN", "LEFT", "RIGHT"):
                self.emu.press(d, hold=10, wait=6)
            return
        talks = sorted((o for o in options if o.kind == "talk"), key=lambda o: o.distance)[:MAX_TALK_OPTIONS]
        options = [o for o in options if o.kind != "talk"] + talks
        options.sort(key=lambda o: (KIND_ORDER.get(o.kind, 9), o.key in self.memory.links, o.distance))   # new doors first
        hide_menu = self._menu_cooldown > 0 or not self.game.party()   # stuck in there, or nothing to use yet
        if self._menu_cooldown > 0:
            self._menu_cooldown -= 1
        if hide_menu:
            options = [o for o in options if o.kind != "menu"] or options
        options = self._drop_worn_out(options)
        options = self._follow_route(options, s) or self._prefer_untried(self._no_turning_back(options))

        lines = []
        for o in options:
            line = f"{o.label}, {o.distance} {'step' if o.distance == 1 else 'steps'} away"
            n = self.pick_counts[o.key]
            if n:
                line += f" [you've picked this {n} time{'s' if n > 1 else ''} recently]"
            if o.key in self._failed_options:
                line += " [this didn't work last time, so try something else]"
            lines.append(line)

        self._context = self._context_text(s)
        self._wait_for_voice()
        self.overlay.update(thought="Thinking...")
        decision = self.brain.decide(self._context, lines)
        opt = options[decision.choice]
        self._apply_decision(decision, opt.label)
        self.pick_counts[opt.key] += 1
        self._note_pick(opt.key)
        self._actions_since_discovery += 1

        steps_before = self.world.steps_taken
        if opt.kind == "talk":
            self._talking_to = opt.key
        result = self.world.execute(opt, s)
        self.memory.bump("steps", self.world.steps_taken - steps_before)
        self._record_outcome(opt.key, result.outcome)
        if opt.kind == "exit" and result.outcome == "stuck":     # a proven fact, not a guess, so it's worth keeping
            self.memory.links[opt.key] = BLOCKED_EXIT
            self.memory.add_lesson(f"{s.map_name}: you can't leave by the {opt.label.split(' side')[0].split()[-1]} side.")
        if opt.kind in ("warp", "exit") and result.outcome == "warped":
            if opt.key not in self.memory.links:
                self._discovered()
            self.memory.links[opt.key] = result.detail
        detail = f" ({result.detail})" if result.detail else ""
        self.history.append(f"{opt.label} -> {result.outcome}{detail}")
        print(f"[agent] {opt.label} -> {result.outcome}{detail}")
        if self.memory.stats.get("decisions", 0) % 5 == 0:
            self.memory.save()
