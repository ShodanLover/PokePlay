"""What she should do next, based on how far she's got. The owner asked for the opening to be spelled out."""

from __future__ import annotations

from pathlib import Path

# The rest of the game, in our own words. For each badge count: (a place she hasn't reached yet, what to do), in order,
# then BY_BADGES once she's been everywhere on that list.
LATER_STEPS = {
    2: [("Route 25 - Sea Cottage", "From Cerulean City go north over the bridge on Route 24, then east along Route 25 to "
                                   "the Sea Cottage, and talk to Bill. He'll give you a ticket for a ship."),
        ("Vermilion City", "From Cerulean City go south through Route 5, the Underground Path and Route 6 to Vermilion City.")],
    3: [("Rock Tunnel - 1F", "From Cerulean City go east on Route 9, cutting down the small tree in the way, then follow "
                             "Route 10 to Rock Tunnel."),
        ("Lavender Town", "Go through Rock Tunnel and out the south side to Lavender Town."),
        ("Celadon City", "From Lavender Town go west along Route 8 and through the Underground Path to Celadon City.")],
    4: [("Rocket Hideout - B1F", "In Celadon City go into the Game Corner and press the switch behind the poster at the "
                                 "back. Go down and beat the villains' boss to get the Silph Scope."),
        ("Pokémon Tower - 1F", "Go to Lavender Town and climb Pokémon Tower to rescue Mr. Fuji. He gives you a flute."),
        ("Fuchsia City", "From Lavender Town go south along Routes 12 to 15, using the flute to wake the sleeping "
                         "creature blocking the road, to reach Fuchsia City.")],
    5: [("Safari Zone - Center", "In Fuchsia City enter the Safari Zone and reach the Secret House at the far end to "
                                 "get the move that crosses water. The Warden gives you the move that pushes boulders."),
        ("Saffron City", "Go to Saffron City. Get the drink from the mansion in Celadon City if the guards stop you."),
        ("Silph Co - 1F", "In Saffron City go into Silph Co and climb to the top, beating the villains' boss.")],
    6: [("Cinnabar Island", "Surf south from Pallet Town to Cinnabar Island."),
        ("Pokémon Mansion - 1F", "On Cinnabar Island go into the Pokémon Mansion and find the key to the Gym.")],
    8: [("Victory Road - 1F", "Heal up and buy potions, then go west from Viridian City along Routes 22 and 23 to Victory Road.")],
}
# What to do once she's been everywhere for that badge count. Index = number of badges.
BY_BADGES = [
    "",
    "",
    "In Vermilion City board the ship with your ticket, get the tree-cutting move from the captain and teach it to "
    "your team, then cut the small tree at the Gym and beat the leader, Lt. Surge.",
    "In Celadon City, heal at the Pokémon Center, then go into the Gym and beat the leader, Erika.",
    "In Fuchsia City, heal at the Pokémon Center, then go into the Gym and beat the leader, Koga.",
    "In Saffron City, heal at the Pokémon Center, then go into the Gym and beat the leader, Sabrina.",
    "On Cinnabar Island, heal at the Pokémon Center, then use the key to go into the Gym and beat the leader, Blaine.",
    "Go back to Viridian City, go into the Gym that used to be closed, and beat the leader, Giovanni.",
    "Go through Victory Road to the Indigo Plateau, heal, and beat the Elite Four and the Champion.",
]
HEAL = "Your team is badly hurt. Go into this town's Pokémon Center and talk to the person at the counter to heal them for free."
CENTER_CITIES = ("Viridian City", "Pewter City", "Cerulean City", "Lavender Town", "Vermilion City", "Celadon City",
                 "Fuchsia City", "Cinnabar Island", "Saffron City")
GUIDE_PATH = Path(__file__).resolve().parent.parent / "firered_walkthrough.md"
GUIDE_HEADINGS = ("Pallet Town to Pewter City", "Mt. Moon to Vermilion City", "Lavender Town to Fuchsia City",
                  "Saffron City to Viridian City", "Indigo Plateau")
GUIDE_FOR_BADGES = (0, 1, 1, 2, 2, 3, 3, 3, 4)      # which part of the owner's route notes applies at each badge count
GUIDE_MAX_CHARS = 900                               # keeps her prompt short, which keeps her fast
HM_NOTE = ("About HMs: an HM is a disc from your bag that teaches a move to a team member. A team member has to know the "
           "move, and you need the right badge, before you can use it outside battle. Once learned, an HM move can't be "
           "forgotten like normal moves. Cut clears small thin trees, Rock Smash breaks cracked rocks, Strength pushes big "
           "boulders, Surf crosses water, Waterfall climbs waterfalls, Flash lights dark caves, and Fly travels to towns "
           "you've visited. To use one, walk up to the obstacle, check it, and say yes.")
BUY_BALLS = "You're out of POKé BALLs. Go into this town's Mart, talk to the clerk, choose BUY, and buy 5 POKé BALLs."
MART_CITIES = ("Viridian City", "Pewter City", "Cerulean City", "Lavender Town", "Vermilion City", "Fuchsia City",
               "Cinnabar Island", "Saffron City")
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
    TO_FOREST: {"Pallet Town": "north", "Route 1": "north", "Viridian City": "north", "Route 22": "east",
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
    if step == HEAL:
        if arrived(step, place):
            return ""
        return f"{place} - Pokémon Center - 1F" if place in CENTER_CITIES else place.split(" - ")[0]
    if step == BUY_BALLS:
        if arrived(step, place):
            return ""
        return f"{place} - Mart" if place in MART_CITIES else place.split(" - ")[0]
    route = ROUTE.get(step)
    if not route or arrived(step, place):       # no route for this step, or she's arrived: talk, fight, explore
        return ""
    if place in route:
        return route[place]
    return place.split(" - ")[0] if " - " in place else ""      # inside the wrong building: back outside


def arrived(step: str, place: str) -> bool:
    """She's at the place this step needs, so the job now is talking or fighting, not leaving."""
    if step == HEAL:
        return place.endswith("Pokémon Center - 1F")
    if step == BUY_BALLS:
        return place.endswith(" - Mart")
    return DESTINATIONS.get(step) == place


def guide_section(badges: int, path: Path = GUIDE_PATH) -> str:
    """The part of the owner's route notes for this stage of the game, or "" if the file isn't there."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    heading = GUIDE_HEADINGS[GUIDE_FOR_BADGES[max(0, min(badges, len(GUIDE_FOR_BADGES) - 1))]]
    start = text.find(f"### {heading}")
    if start == -1:
        return ""
    body = text[start + len(heading) + 4:]
    end = body.find("\n#")
    return (body if end == -1 else body[:end]).strip()[:GUIDE_MAX_CHARS]


def hint_for(badges: int, has_team: bool, key_items: list[str], places: list[str], delivered: bool,
             want_balls: bool = False, place: str = "", needs_healing: bool = False) -> str:
    def been(name: str) -> bool:
        return any(name in visited for visited in places)

    if not has_team:
        return NO_TEAM
    if needs_healing and place.split(" - ")[0] in CENTER_CITIES:    # only while she's in a town that has a Center
        return HEAL
    if any("PARCEL" in item.upper() for item in key_items):
        return PARCEL
    if want_balls and place.split(" - ")[0] in MART_CITIES:     # only while she's in a town that has a Mart
        return BUY_BALLS
    if badges >= 2:
        badges = min(badges, len(BY_BADGES) - 1)
        for marker, step in LATER_STEPS.get(badges, []):
            if not been(marker):
                return step
        return BY_BADGES[badges]
    if badges == 1:
        if been("Cerulean City"):
            return MISTY
        return THROUGH_MT_MOON if been("Mt Moon") else TO_ROUTE_3
    if been("Pewter City"):
        return BROCK
    if "Viridian Forest" in places:             # the forest itself, not the gate buildings named after it
        return THROUGH_FOREST
    if delivered:
        return TO_FOREST
    return GET_PARCEL if been("Viridian City") else TO_VIRIDIAN
