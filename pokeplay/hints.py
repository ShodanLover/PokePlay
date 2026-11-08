"""Occasional nudges about what to do next, based on how far she's got. Added at the owner's request."""

from __future__ import annotations

# Index = number of badges. Written for this project, in plain directions she can match to her action list.
BY_BADGES = [
    "Head north out of town to the next town and visit its shop. After that, keep going north through the forest "
    "to the city beyond it, and challenge the gym there.",
    "Go east from the city with the first gym, through the mountain cave, to the next city with a gym.",
    "Go south to the port city and get on the big ship there. Learn the move that cuts small trees, then "
    "challenge the port city's gym.",
    "Go east through the dark tunnel to the small town, then west to the big city with the department store, "
    "and challenge the gym there.",
    "Clear out the villains hiding under the game corner, then visit the haunted tower in the small town. After "
    "that, head south to the city by the sea and challenge its gym.",
    "Go to the big city in the middle of the map, rescue the office tower from the villains, and challenge the gym there.",
    "Learn to cross water, then surf south to the volcano island and challenge the gym there.",
    "Go back to the first city with the gym that used to be closed, and challenge it.",
    "Go west of the first city through the road of gates, through the long cave, and challenge the final four trainers.",
]
NO_TEAM = ("Try leaving your town by the north side. Someone will stop you and take you to the lab. Then choose "
           "one of the balls on the table to get your first partner.")
PARCEL = "You're carrying a parcel. Take it back to the professor in your home town."


def hint_for(badges: int, has_team: bool, key_items: list[str]) -> str:
    if not has_team:
        return NO_TEAM
    if any("PARCEL" in item.upper() for item in key_items):
        return PARCEL
    return BY_BADGES[max(0, min(badges, len(BY_BADGES) - 1))]
