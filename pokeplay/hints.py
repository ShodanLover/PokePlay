"""What she should do next, based on how far she's got. The owner asked for the opening to be spelled out."""

from __future__ import annotations

# After the first two badges these are only occasional nudges. Index = number of badges.
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
        return THROUGH_MT_MOON if been("Mt. Moon") else TO_ROUTE_3
    if been("Pewter City"):
        return BROCK
    if been("Viridian Forest"):
        return THROUGH_FOREST
    if delivered:
        return TO_FOREST
    return GET_PARCEL if been("Viridian City") else TO_VIRIDIAN
