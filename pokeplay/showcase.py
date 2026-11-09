"""The scoreboard viewers see: boss fights, how many tries they've taken, and the story so far in one glance.

Everything here comes from what really happened, so it stays true without asking the AI. It never affects her decisions.
"""

from __future__ import annotations

BOSS_RESULT_SECONDS = 20        # how long a win or loss stays on the banner
RECAP_EVERY = 30 * 60           # a crash and restart shouldn't make her recap the story all over again

# Where a boss fight happens -> (who it is, the level of their strongest). Gyms also have ordinary trainers, all below
# that level, so the leader is the trainer there with a team that strong. League rooms hold one trainer each: no level needed.
BOSSES = {
    "Pewter City - Gym": ("Brock", 14),
    "Cerulean City - Gym": ("Misty", 21),
    "Vermilion City - Gym": ("Lt. Surge", 24),
    "Celadon City - Gym": ("Erika", 29),
    "Fuchsia City - Gym": ("Koga", 43),
    "Saffron City - Gym": ("Sabrina", 43),
    "Cinnabar Island - Gym": ("Blaine", 47),
    "Viridian City - Gym": ("Giovanni", 50),
    "Pokémon League - Loreleis Room": ("Lorelei", 0),
    "Pokémon League - Brunos Room": ("Bruno", 0),
    "Pokémon League - Agathas Room": ("Agatha", 0),
    "Pokémon League - Lances Room": ("Lance", 0),
    "Pokémon League - Champions Room": ("the Champion", 0),
}
GYM_LEADERS = {name for place, (name, _) in BOSSES.items() if place.endswith(" - Gym")}


def boss_for(place: str, is_trainer: bool, top_level: int) -> str:
    """Who this fight is against if it's a boss, or ""."""
    if not is_trainer or place not in BOSSES:
        return ""
    name, level = BOSSES[place]
    return name if top_level >= level and top_level else ""


def begin_fight(bosses: dict, name: str) -> int:
    """Count a new attempt and return its number."""
    record = bosses.setdefault(name, {"attempts": 0, "lost": 0, "beaten": False})
    record["attempts"] += 1
    return record["attempts"]


def end_fight(bosses: dict, name: str, outcome: str) -> None:
    record = bosses[name]
    if outcome == "lost":
        record["lost"] += 1
    elif outcome == "won":
        record["beaten"] = True
        bosses[name] = bosses.pop(name)             # the newest win goes last, so it's the one shown


def fight_banner(who: str, name: str, attempt: int) -> dict:
    return {"state": "fight", "tag": "Boss fight", "title": f"{who} vs. {name}",
            "detail": "First attempt" if attempt == 1 else f"Attempt {attempt}"}


def result_banner(who: str, name: str, attempt: int, outcome: str) -> dict | None:
    """What the banner shows afterwards, or None if the fight ended some other way."""
    if outcome == "won":
        detail = "First try" if attempt == 1 else f"On attempt {attempt}"
        return {"state": "won", "tag": "Victory", "title": f"{who} beat {name}",
                "detail": detail + (" · Badge earned" if name in GYM_LEADERS else "")}
    if outcome == "lost":
        return {"state": "lost", "tag": "Defeated", "title": f"{name} wins this one", "detail": f"Attempt {attempt} failed"}
    return None


def _count(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes}m"


def headline(bosses: dict, wipes: int) -> str:
    """The one thing to know: who's beating her, or else the last boss she beat."""
    for name, record in reversed(list(bosses.items())):
        if record["lost"] and not record["beaten"]:
            return f"Lost to {name} {_count(record['lost'], 'time')} so far."
    for name, record in reversed(list(bosses.items())):
        if record["beaten"]:
            return f"Beat {name} first try." if record["attempts"] == 1 else f"Beat {name} on attempt {record['attempts']}."
    return f"{_count(wipes, 'team wipe')}, no Gym Leader yet." if wipes else "Hasn't reached a Gym Leader yet."


def catch_up(day: int, bosses: dict, wipes: int, badges: int, since_badge: float) -> dict:
    """The corner panel, so someone just arriving knows what's going on."""
    clock = f"{_duration(since_badge)} since last badge" if badges else f"{_duration(since_badge)} with no badge"
    return {"tag": f"Day {day} so far", "headline": headline(bosses, wipes),
            "numbers": f"{clock} · {_count(wipes, 'wipe')}"}


def recap_prompt(day: int, bosses: dict, wipes: int, badges: int, place: str) -> str:
    """What she's told to sum up when she comes back on air. The words are still her own."""
    return (f"You just came back on air. In one line, give a dramatic 'previously on' of your own story, without greeting "
            f"anyone. Day {day}. {_count(badges, 'badge')}. {headline(bosses, wipes)} {_count(wipes, 'team wipe')}. "
            f"You're in {place}.")
