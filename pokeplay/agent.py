"""The main loop: watch the game, decide, act, narrate."""

from __future__ import annotations

import collections
import json
import queue
import threading
import time

from . import addresses as A
from .battle import BattlePilot
from .brain import Brain
from .config import Config
from .emulator import Emulator
from .game import Game, GameState
from .naming import MAX_CHARS, NamingScreen
from .narrator import Narrator
from .objectives import current_objective
from .overlay.server import OverlayState, start_overlay
from .overworld import Overworld

KIND_ORDER = {"warp": 0, "exit": 1, "talk": 2, "train": 3, "explore": 4}
BATTLE_OUTCOMES = {1: "won", 2: "lost", 3: "drew", 4: "ran away", 5: "teleported away",
                   6: "the wild Pokémon fled", 7: "caught it"}
MAX_TALK_OPTIONS = 5


class Agent:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.emu = Emulator(cfg.emulator.host, cfg.emulator.port)
        self.game = Game(self.emu)
        self.brain = Brain(cfg.brain.ollama_url, cfg.brain.model, cfg.brain.streamer_name,
                           cfg.brain.temperature, cfg.brain.context_tokens)
        self.overlay = OverlayState()
        self.narrator = Narrator(cfg.voice.engine, cfg.voice.piper_model, cfg.voice.rate,
                                 on_speak=lambda t: self.overlay.update(say=t, subtitle=t),
                                 on_done=lambda: self.overlay.update(subtitle=""),
                                 gender=cfg.voice.gender)
        self.naming = NamingScreen(self.emu)
        self._named_this_screen = False
        self.world = Overworld(self.emu, self.game)
        self.pilot = BattlePilot(self.emu, self.game)

        self.history: collections.deque[str] = collections.deque(maxlen=10)
        self.notes: collections.deque[str] = collections.deque(maxlen=8)
        self.pick_counts: collections.Counter[str] = collections.Counter()
        self._events: queue.Queue[str] = queue.Queue()
        self._context = ""
        self._last_message = ""
        self._dialog_presses = 0
        self._other_loops = 0
        self._prev_mode = ""
        self._in_battle = False
        self._party_before_battle: list = []
        self._last_autosave = time.time()
        self._last_overlay = 0.0
        self._last_map = None

    # ------------------------------------------------------------------ startup
    def start(self) -> None:
        print("Connecting to mGBA...")
        self.emu.connect()
        print(f"Found {self.game.check_rom()}")
        self.game.load_tables()
        print("Read species, move and item data from the ROM.")
        self.brain.check()
        print(f"Ollama model '{self.cfg.brain.model}' is ready.")
        self._load_persona()
        start_overlay(self.overlay, self.cfg.overlay.port)
        print(f"Overlay: http://127.0.0.1:{self.cfg.overlay.port}  (add it to OBS as a Browser Source)")
        if self.cfg.commentary.enabled:
            threading.Thread(target=self._commentary_worker, daemon=True).start()
        hello = self.brain.greet()
        if hello:
            self.narrator.say(hello)

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
        self.brain.personality = " ".join(x for x in (persona.get("personality", ""),
                                                      f"Your catchphrase: {persona.get('catchphrase', '')}") if x)
        self.overlay.update(streamer=persona["name"])
        print(f"She is: {persona['name']} - {persona.get('personality', '')}")

    def run(self) -> None:
        self.start()
        while True:
            try:
                self.tick()
            except KeyboardInterrupt:
                raise
            except Exception as e:  # noqa: BLE001 - keep the stream alive
                print(f"[agent] error: {e!r}; retrying in 2s")
                time.sleep(2)
                try:
                    self.emu.command("PING")
                except Exception:  # noqa: BLE001
                    self.emu.close()
                    self.emu.connect(retry_seconds=600)

    # ------------------------------------------------------------------ main tick
    def tick(self) -> None:
        mode = self.game.mode()
        if mode != self._prev_mode:
            self._on_mode_change(self._prev_mode, mode)
            self._prev_mode = mode

        if mode == "battle":
            self.pilot.step()
            self._drain_pilot_events()
        elif mode == "party_menu":
            self.pilot.party_menu()
        elif mode == "dialog":
            self._dialog()
        elif mode == "overworld":
            self._dialog_presses = 0
            self._overworld_turn()
        elif mode in ("summary", "bag"):
            self.emu.press("B", hold=2, wait=12)
        elif mode == "naming":
            self._name_something()
        else:
            # Screen transitions, title screen, evolution, etc.
            self._other_loops += 1
            if self._other_loops % 6 == 0:
                self.emu.press("A", hold=2, wait=10)
            else:
                self.emu.wait_frames(10)

        if mode != "other":
            self._other_loops = 0
        if mode != "naming":
            self._named_this_screen = False
        self._periodic(mode)

    def _periodic(self, mode: str) -> None:
        now = time.time()
        if now - self._last_overlay > 2:
            self._last_overlay = now
            try:
                party = self.game.party()
                self.overlay.update(mode=mode, party=[
                    {"name": m.nickname, "level": m.level, "hp": m.hp, "max_hp": m.max_hp, "status": m.status}
                    for m in party])
            except Exception:  # noqa: BLE001
                pass
        minutes = self.cfg.emulator.autosave_minutes
        if minutes and mode == "overworld" and now - self._last_autosave > minutes * 60:
            self._last_autosave = now
            self.emu.save_state(self.cfg.emulator.autosave_slot)
            print(f"[agent] saved state to slot {self.cfg.emulator.autosave_slot}")

    # ------------------------------------------------------------------ events
    def _on_mode_change(self, old: str, new: str) -> None:
        if new == "battle" and not self._in_battle:
            self._in_battle = True
            self.pilot.reset()
            self._party_before_battle = self.game.party()
            # Wait a moment for the battle data to be filled in.
            self.emu.wait_frames(30)
            info = self.game.battle_info()
            foe = self.game.decode_mon(self.emu.read(A.gEnemyParty, 100)) or info.enemy
            if foe:
                if info.is_trainer:
                    self._event(f"A trainer battle started! The opponent leads with {foe.species_name} Lv{foe.level}.")
                else:
                    self._event(f"A wild {foe.species_name} Lv{foe.level} appeared!")
        elif self._in_battle and new not in ("battle", "party_menu"):
            self._in_battle = False
            outcome = BATTLE_OUTCOMES.get(self.emu.u8(A.gBattleOutcome), "")
            after = self.game.party()
            lines = []
            for b, a in zip(self._party_before_battle, after):
                if a.species != b.species and a.level >= b.level:
                    lines.append(f"{b.nickname} evolved into {a.species_name}!")
                elif a.level > b.level:
                    lines.append(f"{a.nickname} grew to level {a.level}!")
            if outcome:
                self.history.append(f"Battle ended: {outcome}.")
                lines.insert(0, f"The battle is over: we {outcome}." if outcome in ("won", "lost", "drew", "ran away")
                             else f"The battle is over: {outcome}.")
            if lines:
                self._event(" ".join(lines))
            self.overlay.log(lines[0] if lines else "Battle over")

    def _event(self, text: str) -> None:
        print(f"[event] {text}")
        self.overlay.log(text)
        if self.cfg.commentary.enabled:
            self._events.put(text)

    def _drain_pilot_events(self) -> None:
        while self.pilot.events:
            text = self.pilot.events.pop(0)
            self.overlay.update(thought=text)
            self.history.append(text)
            if self.cfg.commentary.enabled:
                self._events.put(text)      # she reacts to the battle in her own words

    def _name_something(self) -> None:
        if self._named_this_screen:
            # Already typed; if we're still here, confirm with OK.
            self.emu.press("START", hold=2, wait=10)
            self.emu.press("A", hold=2, wait=20)
            return
        self._named_this_screen = True
        self.emu.wait_frames(40)    # let the screen fade in
        kind, species_id = self.naming.info()
        species = self.game.species_name(species_id) if kind in ("nickname", "caught") else ""
        if self.cfg.voice.wait_for_voice:
            self.narrator.wait_until_quiet()
        self.overlay.update(thought="Thinking of a name...")
        name, say = self.brain.choose_name(kind, MAX_CHARS.get(kind, 7), species, self._context)
        if say:
            self.narrator.say(say)
        self.overlay.update(thought=f"Typing the name: {name}")
        if name and self.naming.type_name(name):
            self.history.append(f"Named {kind} {species}: {name}".replace("  ", " "))
            self._event(f"Named {kind} {species} '{name}'.".replace("  ", " "))
        else:
            self.emu.press("START", hold=2, wait=10)   # fall back to the game's default name
            self.emu.press("A", hold=2, wait=20)

    def _commentary_worker(self) -> None:
        last = 0.0
        while True:
            batch = [self._events.get()]
            # Group things that happen close together into one comment.
            time.sleep(1.0)
            while not self._events.empty():
                batch.append(self._events.get_nowait())
            wait = self.cfg.commentary.min_seconds_between - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            line = self.brain.comment(batch[-3:], self._context)
            if line:
                self.narrator.say(line)
                last = time.time()

    # ------------------------------------------------------------------ dialog
    def _dialog(self) -> None:
        msg = self.game.message()
        if msg and msg != self._last_message:
            self._last_message = msg
            short = msg if len(msg) <= 160 else msg[:157] + "..."
            self.history.append(f'Message on screen: "{short}"')
            self.overlay.log(f'💬 {short}')
            if self.cfg.commentary.enabled:
                self._events.put(f'Someone in the game says: "{short}"')
            self._dialog_presses = 0
        self._dialog_presses += 1
        # Mostly A to advance text; an occasional B closes menus we didn't mean to open.
        if self._dialog_presses % 12 == 0:
            self.emu.press("B", hold=2, wait=15)
        else:
            self.emu.press("A", hold=2, wait=15)

    # ------------------------------------------------------------------ overworld
    def _context_text(self, s: GameState, objective: str) -> str:
        team = "\n".join(f"- {m.summary()}; moves: {', '.join(f'{mv.name} ({mv.pp} PP)' for mv in m.moves)}"
                         for m in s.party) or "- (no Pokémon yet)"
        bag = ", ".join(f"{n} x{q}" for n, q in (s.items + s.balls)[:10]) or "empty"
        parts = [
            f"CURRENT OBJECTIVE: {objective}",
            f"LOCATION: {s.map_name}, standing at ({s.x},{s.y}). Badges: {s.badges}. Money: ₽{s.money}.",
            f"TEAM:\n{team}",
            f"BAG: {bag}" + (f". KEY ITEMS: {', '.join(s.key_items)}" if s.key_items else ""),
        ]
        if self.notes:
            parts.append("YOUR NOTES:\n" + "\n".join(f"- {n}" for n in self.notes))
        if self.history:
            parts.append("RECENT HISTORY (oldest first):\n" + "\n".join(f"- {h}" for h in self.history))
        return "\n\n".join(parts)

    def _overworld_turn(self) -> None:
        s = self.game.state()
        self.world.mark_visited(s)
        if self._last_map != (s.map_group, s.map_num):
            self._last_map = (s.map_group, s.map_num)
            self.overlay.log(f"📍 {s.map_name}")
        objective = current_objective(self.game, s)
        self.overlay.update(objective=objective, location=s.map_name, badges=s.badges, money=s.money)

        options, _grid = self.world.build_options(s)
        if not options:
            self.history.append("Couldn't find anywhere to go, wiggling around.")
            for d in ("UP", "DOWN", "LEFT", "RIGHT"):
                self.emu.press(d, hold=10, wait=6)
            return
        talks = sorted((o for o in options if o.kind == "talk"), key=lambda o: o.distance)[:MAX_TALK_OPTIONS]
        options = [o for o in options if o.kind != "talk"] + talks
        options.sort(key=lambda o: (KIND_ORDER.get(o.kind, 9), o.distance))

        lines = []
        for o in options:
            line = f"{o.label} ({o.distance} steps away)"
            n = self.pick_counts[o.key]
            if n:
                line += f" [you've picked this {n} time{'s' if n > 1 else ''}]"
            lines.append(line)

        self._context = self._context_text(s, objective)
        if self.cfg.voice.wait_for_voice:
            self.narrator.wait_until_quiet()
        self.overlay.update(thought="Thinking...")
        decision = self.brain.decide(self._context, lines)
        opt = options[decision.choice]
        print(f"[brain] {decision.thought}  ->  {opt.label}")
        self.overlay.update(thought=decision.thought, action=opt.label)
        self.overlay.log(f"▶ {opt.label}")
        if decision.say:
            self.narrator.say(decision.say)
        if decision.note:
            self.notes.append(decision.note[:150])
        self.pick_counts[opt.key] += 1

        result = self.world.execute(opt, s)
        detail = f" ({result.detail})" if result.detail else ""
        self.history.append(f"{opt.label} -> {result.outcome}{detail}")
        print(f"[agent] {opt.label} -> {result.outcome}{detail}")
