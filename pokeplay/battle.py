"""Battles: she chooses every move herself; this module just works the menus.

She only sees what the battle screen shows (move names, types, PP, the foe's HP bar) and
learns matchups by watching messages like "It's super effective!".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from . import addresses as A
from .emulator import Emulator
from .game import BattleInfo, Game, Mon

# Battle menus are 2x2 grids: 0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right.
ACTION_FIGHT, ACTION_BAG, ACTION_POKEMON, ACTION_RUN = 0, 1, 2, 3

USED_RE = re.compile(r"^(?:(?:Foe|Wild) )?(.+?) used (.+?)!")
EFFECT_PHRASES = [
    ("super effective", "was super effective against"),
    ("not very effective", "was not very effective against"),
    ("doesn't affect", "had no effect on"),
    ("It doesn't affect", "had no effect on"),
]


@dataclass
class Choice:
    kind: str            # "move" or "run"
    index: int = 0       # move slot


# chooser(info, labels) -> index into labels
Chooser = Callable[[BattleInfo, list[str], list[Choice]], int]
PartyChooser = Callable[[list[tuple[int, Mon]]], int]


@dataclass
class BattlePilot:
    emu: Emulator
    game: Game
    chooser: Chooser | None = None
    party_chooser: PartyChooser | None = None
    lessons: list[str] = field(default_factory=list)   # observations for her journal
    events: list[str] = field(default_factory=list)
    _pending: Choice | None = None
    _last_msg: str = ""
    _last_user: str = ""
    _last_move: str = ""
    _party_target: int | None = None
    _party_attempts: int = 0

    def reset(self) -> None:
        self._pending = None
        self._party_target = None
        self._party_attempts = 0
        self._last_msg = ""

    # ------------------------------------------------------------------ menus
    def _move_cursor(self, cursor_addr: int, target: int) -> None:
        for _ in range(4):
            cur = self.emu.u8(cursor_addr) & 3
            if cur == target:
                return
            if (cur & 1) != (target & 1):
                self.emu.press("RIGHT" if target & 1 else "LEFT", hold=2, wait=4)
            elif (cur >> 1) != (target >> 1):
                self.emu.press("DOWN" if target >> 1 else "UP", hold=2, wait=4)

    def _choices(self, info: BattleInfo, allow_run: bool) -> tuple[list[str], list[Choice]]:
        labels, choices = [], []
        for i, m in enumerate(info.player.moves if info.player else []):
            if m.pp > 0:
                labels.append(f"Use {m.name} ({m.type_name} type, {m.pp} PP left)")
                choices.append(Choice("move", i))
        if not choices and info.player:
            labels.append("Fight (no PP left on any move)")
            choices.append(Choice("move", 0))
        if allow_run:
            labels.append("Try to run away")
            choices.append(Choice("run"))
        return labels, choices

    def _decide(self, allow_run: bool) -> Choice:
        info = self.game.battle_info()
        labels, choices = self._choices(info, allow_run and not info.is_trainer)
        if self.chooser is None or len(choices) == 1:
            return choices[0]
        idx = self.chooser(info, labels, choices)
        return choices[idx] if 0 <= idx < len(choices) else choices[0]

    # ------------------------------------------------------------------ main step
    def step(self) -> None:
        self._watch_messages()
        want = self.game.battle_input()
        if want == "action":
            if self._pending is None:
                self._pending = self._decide(allow_run=True)
            target = ACTION_RUN if self._pending.kind == "run" else ACTION_FIGHT
            self._move_cursor(A.gActionSelectionCursor, target)
            self.emu.press("A", hold=2, wait=10)
            if self._pending.kind == "run":
                self._pending = None
        elif want == "move":
            if self._pending is None or self._pending.kind != "move":
                self._pending = self._decide(allow_run=False)
            self._move_cursor(A.gMoveSelectionCursor, self._pending.index)
            self.emu.press("A", hold=2, wait=10)
            self._pending = None
        elif want == "target":
            self.emu.press("A", hold=2, wait=10)
        else:
            # Text, animations, yes/no boxes.
            self.emu.press("A", hold=2, wait=12)

    # ------------------------------------------------------------------ learning
    def _watch_messages(self) -> None:
        msg = self.game.battle_info().message
        if not msg or msg == self._last_msg:
            return
        self._last_msg = msg
        m = USED_RE.search(msg)
        if m:
            self._last_user, self._last_move = m.group(1).strip(), m.group(2).strip()
        for phrase, verb in EFFECT_PHRASES:
            if phrase.lower() in msg.lower() and self._last_move:
                info = self.game.battle_info()
                me, foe = info.player, info.enemy
                if not me or not foe:
                    break
                attacker_is_me = self._last_user.upper() in (me.nickname.upper(), me.species_name.upper())
                target = foe.species_name if attacker_is_me else me.species_name
                move_type = ""
                for mv in (me.moves if attacker_is_me else foe.moves):
                    if mv.name.upper() == self._last_move.upper():
                        move_type = f" ({mv.type_name})"
                lesson = f"{self._last_move}{move_type} {verb} {target}."
                self.lessons.append(lesson)
                break

    # ------------------------------------------------------------------ fainted -> pick next
    def party_menu(self) -> None:
        party = self.game.party()
        active = self.game.battle_mon(0)
        alive = [(i, m) for i, m in enumerate(party)
                 if not m.fainted and not m.is_egg and not (active and m.species == active.species and m.hp == active.hp)]
        if not alive:
            self.emu.press("B", hold=2, wait=10)
            return
        if self._party_target is None:
            pick = self.party_chooser(alive) if self.party_chooser and len(alive) > 1 else 0
            self._party_target = alive[pick if 0 <= pick < len(alive) else 0][0]
        self._party_attempts += 1
        if self._party_attempts % 8 == 0:
            # That slot didn't work (layout differs mid-battle): try the next healthy one.
            self.emu.press("B", hold=2, wait=10)
            idxs = [i for i, _ in alive]
            self._party_target = idxs[(idxs.index(self._party_target) + 1) % len(idxs)] \
                if self._party_target in idxs else idxs[0]
        slot = self.emu.u8(A.gPartyMenu_slotId)
        if slot != self._party_target:
            self.emu.press("DOWN" if slot < self._party_target or slot > 5 else "UP", hold=2, wait=6)
        else:
            self.emu.press("A", hold=2, wait=12)    # select, then "SHIFT"


def hp_bar(mon: Mon) -> str:
    """What the HP bar looks like, as a player would describe it."""
    if not mon.max_hp:
        return "unknown"
    pct = mon.hp / mon.max_hp
    if pct == 0:
        return "empty"
    for limit, text in ((0.9, "nearly full"), (0.6, "more than half"), (0.4, "about half"),
                        (0.2, "low"), (0.0, "almost empty")):
        if pct > limit:
            return text
    return "almost empty"
