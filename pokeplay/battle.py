"""Plays battles and handles the menus that pop up around them."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import addresses as A
from .emulator import Emulator
from .game import PHYSICAL_TYPES, Game, Mon, Move

# Battle menus are 2x2 grids: 0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right.
ACTION_FIGHT, ACTION_BAG, ACTION_POKEMON, ACTION_RUN = 0, 1, 2, 3


def score_move(game: Game, move: Move, attacker: Mon, defender: Mon) -> float:
    """Rough expected damage of a move, good enough to pick the best one."""
    if move.pp == 0 or move.power == 0:
        return 0.0
    power = move.power
    if move.power == 1:  # fixed/variable damage moves (Seismic Toss, Night Shade...)
        power = attacker.level * 0.8
    eff = game.effectiveness(move.type, defender.types)
    stab = 1.5 if move.type in attacker.types else 1.0
    acc = (move.accuracy or 100) / 100.0
    if move.type in PHYSICAL_TYPES:
        ratio = max(attacker.attack, 1) / max(defender.defense, 1)
    else:
        ratio = max(attacker.sp_attack, 1) / max(defender.sp_defense, 1)
    return power * eff * stab * acc * ratio


def best_move(game: Game, attacker: Mon, defender: Mon) -> tuple[int, Move | None, float]:
    best_i, best_m, best_s = 0, None, -1.0
    for i, m in enumerate(attacker.moves):
        s = score_move(game, m, attacker, defender)
        if s > best_s:
            best_i, best_m, best_s = i, m, s
    if best_s == 0:
        # Nothing damaging: use any move that still has PP.
        for i, m in enumerate(attacker.moves):
            if m.pp > 0:
                return i, m, 0.0
    return best_i, best_m, best_s


def describe_effectiveness(mult: float) -> str:
    if mult == 0:
        return "it has no effect"
    if mult >= 2:
        return "super effective"
    if mult < 1:
        return "not very effective"
    return "normal damage"


@dataclass
class BattlePilot:
    emu: Emulator
    game: Game
    events: list[str] = field(default_factory=list)   # things worth narrating
    _party_attempts: int = 0
    _last_choice_turn: tuple = ()

    def _move_cursor(self, cursor_addr: int, target: int) -> None:
        for _ in range(4):
            cur = self.emu.u8(cursor_addr) & 3
            if cur == target:
                return
            if (cur & 1) != (target & 1):
                self.emu.press("RIGHT" if target & 1 else "LEFT", hold=2, wait=4)
            elif (cur >> 1) != (target >> 1):
                self.emu.press("DOWN" if target >> 1 else "UP", hold=2, wait=4)

    def step(self) -> None:
        """Do one small thing in battle. Called repeatedly while in battle mode."""
        want = self.game.battle_input()
        if want == "action":
            info = self.game.battle_info()
            me, foe = info.player, info.enemy
            action = ACTION_FIGHT
            if (me and foe and not info.is_trainer and me.max_hp
                    and me.hp / me.max_hp < 0.2 and any(not m.fainted for m in self.game.party()[1:])):
                # Low on HP in a wild battle: try to get away.
                action = ACTION_RUN
                self.events.append(f"{me.nickname} is low on HP, trying to run from the wild {foe.species_name}.")
            self._move_cursor(A.gActionSelectionCursor, action)
            self.emu.press("A", hold=2, wait=10)
        elif want == "move":
            info = self.game.battle_info()
            me, foe = info.player, info.enemy
            if not me or not foe:
                self.emu.press("A", hold=2, wait=10)
                return
            idx, move, _ = best_move(self.game, me, foe)
            if move is not None:
                eff = self.game.effectiveness(move.type, foe.types)
                key = (me.species, foe.species, me.hp, foe.hp)
                if key != self._last_choice_turn:
                    self._last_choice_turn = key
                    self.events.append(
                        f"{me.nickname} (HP {me.hp}/{me.max_hp}) vs {foe.species_name} Lv{foe.level} "
                        f"(HP {foe.hp}/{foe.max_hp}): using {move.name} ({move.type_name}, "
                        f"{describe_effectiveness(eff)})."
                    )
            self._move_cursor(A.gMoveSelectionCursor, idx)
            self.emu.press("A", hold=2, wait=10)
        elif want == "target":
            self.emu.press("A", hold=2, wait=10)
        else:
            # Text, animations, yes/no boxes ("Use next Pokémon?" defaults to YES).
            self.emu.press("A", hold=2, wait=12)

    def party_menu(self) -> None:
        """Pick the next healthy Pokemon when one faints."""
        party = self.game.party()
        active = self.game.battle_mon(0)
        alive = [i for i, m in enumerate(party)
                 if not m.fainted and not m.is_egg and not (active and m.species == active.species and m.hp == active.hp)]
        if not alive:
            self.emu.press("B", hold=2, wait=10)
            return
        target = alive[(self._party_attempts // 6) % len(alive)]
        self._party_attempts += 1
        if self._party_attempts % 6 == 0:
            self.emu.press("B", hold=2, wait=10)   # close a "no energy left" message
        slot = self.emu.u8(A.gPartyMenu_slotId)
        if slot != target:
            self.emu.press("DOWN" if slot < target or slot > 5 else "UP", hold=2, wait=6)
        else:
            self.emu.press("A", hold=2, wait=12)    # select, then "SHIFT"

    def reset(self) -> None:
        self._party_attempts = 0
