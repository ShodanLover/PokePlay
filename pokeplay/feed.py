"""Turns what she really did into short lines for the on-stream feed. Her reasoning and her guide never go in it."""

from __future__ import annotations

import re

FIXED = (("Walk around in the tall grass", "Training in the tall grass"), ("Talk to the person", "Talking to someone"),
         ("Explore ", "Exploring"), ("Check the ", "Checking something nearby"), ("Try to run away", "Trying to run away"),
         ("Switch to a different", "Switching Pokémon"), ("Open your Bag", "Opening the Bag"),
         ("Fight (no PP", "Out of moves: fighting anyway"))


def action_line(label: str) -> str:
    """A short description of a choice she made, or "" if it isn't worth showing (menus and the like)."""
    label = " ".join(label.split())
    move = re.match(r"Use (.+?) \(", label)
    if move:
        return f"Used {move[1]}" + (" (strongest move)" if "THE STRONGEST CHOICE" in label else "")
    leads_to = re.search(r"\(leads to ([^)]+)\)", label)
    side = re.match(r"Leave this area by the (\w+) side", label)
    if side:
        return f"Heading {side[1]}" + (f" to {leads_to[1]}" if leads_to else "")
    if label.startswith("Go through the doorway"):
        return f"Going to {leads_to[1]}" if leads_to else "Trying a new door"
    return next((line for start, line in FIXED if label.startswith(start)), "")


def event_line(text: str) -> str:
    """A short description of something that happened, or "" if viewers wouldn't need it."""
    meeting = re.match(r"(Someone challenged you to a battle|A wild creature jumped out)! It's called (.+), level (\d+)\.", text)
    if meeting:
        return f"{'Trainer battle' if meeting[1].startswith('Someone') else 'Wild encounter'}: {meeting[2]} (Lv {meeting[3]})"
    if text.startswith("The battle is over: "):
        return "Battle over: " + text.removeprefix("The battle is over: ")
    if text.startswith("You arrived somewhere new: "):
        return "New area: " + text.removeprefix("You arrived somewhere new: ").rstrip(".")
    return ""
