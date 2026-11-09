"""Her long-term memory: everything she has learned on stream, saved to disk.

In first-timer mode this is the ONLY game knowledge she gets: what she has seen,
what people told her, and what she figured out herself.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field


@dataclass
class Memory:
    journal: list[str] = field(default_factory=list)        # notes she wrote herself
    lessons: list[str] = field(default_factory=list)        # things she observed (e.g. matchups)
    places: dict[str, str] = field(default_factory=dict)    # "group.num" -> place name, once visited
    links: dict[str, str] = field(default_factory=dict)     # "group.num|door@x,y" -> where it leads
    people: dict[str, str] = field(default_factory=dict)    # "group.num|localId" -> what they said
    bosses: dict[str, dict] = field(default_factory=dict)   # boss name -> attempts, losses, beaten (see showcase.py)
    cave_doors: dict[str, int] = field(default_factory=dict)    # ladder -> times used, for getting through caves
    goal: str = ""                                          # her own current goal
    mood: str = ""
    stats: dict[str, float] = field(default_factory=lambda: {
        "first_started": time.time(), "play_seconds": 0, "sessions": 0, "steps": 0, "battles": 0,
        "battles_won": 0, "battles_lost": 0, "pokemon_fainted": 0, "decisions": 0,
    })
    path: str = field(default="memory.json", repr=False)

    # ---------------------------------------------------------------- disk
    @classmethod
    def load(cls, path: str) -> "Memory":
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return cls(path=path)
        mem = cls(path=path)
        for k, v in data.items():
            if hasattr(mem, k) and k != "path":
                if k == "stats":
                    mem.stats.update(v)
                else:
                    setattr(mem, k, v)
        return mem

    def save(self) -> None:
        data = asdict(self)
        data.pop("path", None)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)   # atomic: never leaves a half-written file

    # ---------------------------------------------------------------- updates
    def add_journal(self, entry: str) -> None:
        entry = " ".join(entry.split())[:200]
        if entry and entry not in self.journal[-10:]:
            self.journal.append(entry)

    def add_lesson(self, lesson: str) -> bool:
        if lesson in self.lessons:
            return False
        self.lessons.append(lesson)
        self.lessons = self.lessons[-80:]
        return True

    def visit(self, map_key: str, name: str) -> bool:
        new = map_key not in self.places
        self.places[map_key] = name
        return new

    def bump(self, stat: str, amount: float = 1) -> None:
        self.stats[stat] = self.stats.get(stat, 0) + amount

    # ---------------------------------------------------------------- views
    def relevant_lessons(self, words: list[str], limit: int = 8) -> list[str]:
        words = [w.upper() for w in words if w]
        hits = [l for l in self.lessons if any(w in l.upper() for w in words)]
        return hits[-limit:]

    def days_since_start(self) -> int:
        return int((time.time() - self.stats.get("first_started", time.time())) // 86400) + 1
