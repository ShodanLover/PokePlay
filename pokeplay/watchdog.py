"""Notices when the game has stopped moving forward, whatever the reason, so a new kind of wall can't freeze the stream.

Progress means reaching a state of the game she hasn't been in lately. Going round in a loop (swap, fail, swap, fail)
keeps revisiting the same few states, so it counts as stuck even though she's busy. It's all code: no AI involved.
"""

from __future__ import annotations

SAMPLE_EVERY = 2.0          # seconds between looks at the game
FIRST_ACT_AFTER = 60.0      # seconds without progress before stepping in
FIRST_ACT_OVERWORLD = 150.0 # walking around a known area for a while is normal, so give it longer
ACT_AGAIN_AFTER = 30.0      # seconds between escapes if the last one didn't work
MIN_SAMPLES = 10            # looks at the game needed first, so one slow AI answer can't look like being stuck
REMEMBER_SECONDS = 300.0    # a state she hasn't been in for this long counts as new again

STORY_PATIENCE = 20 * 60.0  # seconds with no new area, badge, key item or team member before the code takes over the walking
STORY_ACT_AGAIN = 10 * 60.0 # seconds between further attempts if that didn't help
PUSH_DECISIONS = 20         # map decisions the code makes itself each time

WALK = "WALK"              # a few random steps
# What to press for each kind of situation. Each failed attempt moves on to the next row, then starts over.
ESCAPES = {
    "battle": [[], ["B", "B"], ["A", "A"], ["B", "B", "A"]],     # the first row just stops asking the AI
    "send_out": [["B", "DOWN", "A", "A"]],                       # the game demands a Pokémon, and B can't leave
    "menu": [["B", "B", "B"], ["A", "B"], ["B", "B", "B"], ["DOWN", "A", "B"]],
    "dialog": [["A", "A"], ["B", "B"], ["A", "A", "A", "A"], ["DOWN", "A"]],
    "overworld": [["B", "B"], [WALK], ["A", WALK], [WALK]],
    "other": [["A"], ["A"], ["A"], ["A"]],                       # never B here: it would cancel an evolution
}


def fingerprint(game, mode: str, menu=None) -> tuple:
    """Everything that changes when something has really happened."""
    s = game.state()
    foe = game.battle_info().enemy if mode in ("battle", "party_menu") else None
    return (s.map_group, s.map_num, s.x, s.y, s.money, s.badges,
            tuple((m.species, m.level, m.hp, m.status, tuple(mv.pp for mv in m.moves)) for m in s.party),
            tuple(s.items), tuple(s.balls), tuple(s.key_items), s.message,
            (foe.species, foe.hp, foe.status) if foe else None,
            (menu.kind, menu.title) if menu else None)


def escape_kind(mode: str, has_menu: bool, must_send_out: bool) -> str:
    if must_send_out:
        return "send_out"
    if has_menu or mode in ("party_menu", "summary", "bag"):
        return "menu"
    return mode if mode in ("battle", "dialog", "overworld") else "other"


def escape_keys(kind: str, level: int) -> list[str]:
    rows = ESCAPES[kind]
    return rows[(level - 1) % len(rows)]


class StoryWatch:
    """The slower kind of stuck: she's busy and winning battles, but getting nowhere in the game."""

    def __init__(self) -> None:
        self.level = 0
        self.last_progress = 0.0
        self._best: tuple[int, int, int] | None = None
        self._key_items: set[str] = set()

    def reset(self, now: float) -> None:
        self.last_progress = now
        self.level = 0

    def observe(self, badges: int, places: int, key_items: list[str], team_size: int, busy: bool, now: float) -> int:
        """Take one look at her progress. Returns the attempt number to carry out now, or 0 for nothing to do."""
        current = (badges, places, team_size)
        new_items = set(key_items) - self._key_items
        self._key_items |= new_items
        better = self._best is None or bool(new_items) or any(c > b for c, b in zip(current, self._best))
        self._best = current if self._best is None else tuple(max(c, b) for c, b in zip(current, self._best))
        if better or busy:                  # busy: time-limited training, which is meant to stay in one place
            self.reset(now)
            return 0
        stalled = now - self.last_progress
        if stalled < STORY_PATIENCE:
            return 0
        reached = 1 + int((stalled - STORY_PATIENCE) // STORY_ACT_AGAIN)
        if reached <= self.level:
            return 0
        self.level = reached
        return reached


class Watchdog:
    def __init__(self) -> None:
        self.level = 0              # how many escapes she's needed since the last real progress; 0 means all is well
        self.last_sample = 0.0
        self._seen: dict[tuple, float] = {}
        self._last_new = 0.0
        self._samples = 0

    def reset(self) -> None:
        """Something outside the game held things up (the AI went offline, say), so start the clock again."""
        self.level = 0
        self.last_sample = 0.0
        self._seen.clear()
        self._samples = 0

    def stuck_for(self, now: float) -> float:
        return now - self._last_new

    def observe(self, state: tuple, mode: str, now: float) -> int:
        """Take one look at the game. Returns the escape level to carry out now, or 0 for nothing to do."""
        self._seen = {old: when for old, when in self._seen.items() if now - when <= REMEMBER_SECONDS}
        is_new = state not in self._seen
        self._seen[state] = now
        if is_new:
            self._last_new = now
            self._samples = 0
            self.level = 0
            return 0
        self._samples += 1
        first = FIRST_ACT_OVERWORLD if mode == "overworld" else FIRST_ACT_AFTER
        stuck = self.stuck_for(now)
        if stuck < first or self._samples < MIN_SAMPLES:
            return 0
        reached = 1 + int((stuck - first) // ACT_AGAIN_AFTER)
        if reached <= self.level:
            return 0
        self.level = reached
        return reached
