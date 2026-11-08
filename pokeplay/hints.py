"""What she should do next, based on how far she's got. The owner asked for the opening to be spelled out."""

from __future__ import annotations

# What to do after the first two badges. Index = number of badges.
BY_BADGES = [
    "",
    "",
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
NO_TEAM = ("Leave Pallet Town by the north side. Someone will stop you and take you to the lab. Then choose one of "
           "the balls on the table to get your first partner.")
PARCEL = "You're carrying Oak's Parcel. Go south down Route 1 to Pallet Town, go into Professor Oak's Lab, and talk to him."
TO_VIRIDIAN = "Leave Pallet Town by the north side and walk north up Route 1 until you reach Viridian City."
GET_PARCEL = "In Viridian City, go into the Mart (the shop) and talk to the clerk. He'll give you a parcel for Professor Oak."
TO_FOREST = "Go north through Viridian City to Route 2, then keep going north and enter Viridian Forest."
THROUGH_FOREST = "Keep going north through Viridian Forest to Pewter City. Battle what you meet so your team levels up."
BROCK = "In Pewter City, heal at the Pokémon Center, then go into the Gym and beat the leader, Brock."
TO_ROUTE_3 = "Heal at the Pewter City Pokémon Center, then leave by the east side onto Route 3 and keep going east to Mt. Moon."
THROUGH_MT_MOON = "Go all the way through Mt. Moon and out the far side onto Route 4, then east to Cerulean City."
MISTY = "In Cerulean City, heal at the Pokémon Center, then go into the Gym and beat the leader, Misty."


# For each step: where she is -> the exit direction or door name that moves her forward.
ROUTE = {
    TO_VIRIDIAN: {"Pallet Town": "north", "Route 1": "north"},
    GET_PARCEL: {"Viridian City": "Viridian City - Mart"},
    PARCEL: {"Viridian City": "south", "Route 1": "south", "Pallet Town": "Pallet Town - Professor Oak's Lab"},
    TO_FOREST: {"Pallet Town": "north", "Route 1": "north", "Viridian City": "north",
                "Route 2": "Viridian Forest - South Entrance",
                "Route 2 - Viridian Forest - South Entrance": "Viridian Forest"},
    THROUGH_FOREST: {"Viridian Forest": "North Entrance", "Route 2 - Viridian Forest - North Entrance": "Route 2",
                     "Route 2": "north"},
    BROCK: {"Route 2": "north", "Pewter City": "Pewter City - Gym"},
    TO_ROUTE_3: {"Pewter City": "east", "Route 3": "east", "Route 4": "Mt Moon"},
    MISTY: {"Route 4": "east", "Cerulean City": "Cerulean City - Gym"},
}


# The buildings where a step's job gets done, by the game's full map names.
DESTINATIONS = {GET_PARCEL: "Viridian City - Mart", PARCEL: "Pallet Town - Professor Oak's Lab",
                BROCK: "Pewter City - Gym", MISTY: "Cerulean City - Gym"}


def target_for(step: str, place: str) -> str:
    """The exit direction or door name she should take now, or "" to leave it up to her."""
    route = ROUTE.get(step)
    if not route or arrived(step, place):       # no route for this step, or she's arrived: talk, fight, explore
        return ""
    if place in route:
        return route[place]
    return place.split(" - ")[0] if " - " in place else ""      # inside the wrong building: back outside


def arrived(step: str, place: str) -> bool:
    """She's at the place this step needs, so the job now is talking or fighting, not leaving."""
    return DESTINATIONS.get(step) == place


def hint_for(badges: int, has_team: bool, key_items: list[str], places: list[str], delivered: bool) -> str:
    def been(name: str) -> bool:
        return any(name in place for place in places)

    if not has_team:
        return NO_TEAM
    if any("PARCEL" in item.upper() for item in key_items):
        return PARCEL
    if badges >= 2:
        return BY_BADGES[min(badges, len(BY_BADGES) - 1)]
    if badges == 1:
        if been("Cerulean City"):
            return MISTY
        return THROUGH_MT_MOON if been("Mt Moon") else TO_ROUTE_3
    if been("Pewter City"):
        return BROCK
    if been("Viridian Forest"):
        return THROUGH_FOREST
    if delivered:
        return TO_FOREST
    return GET_PARCEL if been("Viridian City") else TO_VIRIDIAN
