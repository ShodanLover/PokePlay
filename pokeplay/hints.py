"""What she should do next, based on how far she's got. The owner asked for the opening to be spelled out."""

from __future__ import annotations

from collections import deque
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
GUIDE_MAX_CHARS = 1500                              # keeps her prompt short, which keeps her fast
BACK_TO_CENTER = ("Your team is out of attacks, or nearly. Go straight back to the nearest town and heal at the Pokémon Center, which "
                  "refills every move for free. Don't go looking for battles until you've done that.")
TO_NEAREST_CENTER = {"Route 1": "north", "Route 2": "north", "Route 3": "west", "Route 22": "east", "Pallet Town": "north",
                     "Viridian Forest": "North Entrance", "Route 2 - Viridian Forest - North Entrance": "Route 2",
                     "Route 2 - Viridian Forest - South Entrance": "Viridian Forest"}
HM_TEACHING = ("To teach an HM: open the main menu, choose BAG, go to the key items pocket, open the TM CASE, pick the HM, "
               "choose USE, then pick a team member who can learn it.")
HM_NOTE = ("About HMs: when a step needs an HM move, a team member must have learned that move first, and you need the "
           "right badge to use it outside battle. Having the HM in your bag is not enough. " + HM_TEACHING + " Once "
           "learned, an HM move can't be forgotten like normal moves. To use one, walk up to the obstacle, check it, and "
           "say yes. Where they come from: CUT from the captain on the ship in Vermilion City (clears small thin trees, "
           "needs the second badge). FLY from a house on Route 16 (travel to towns you've visited, needs the third badge). "
           "SURF from the Secret House in the Safari Zone (crosses water, needs the fifth badge). STRENGTH from the Warden "
           "in Fuchsia City after returning his teeth (pushes boulders, needs the fourth badge). FLASH from the "
           "professor's aide on Route 2 once you've caught enough kinds of creature (lights dark caves, needs the first "
           "badge).")
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

# Gyms with tall grass right next door. Badges she has -> (leader, city, level her strongest should reach first,
# way out of the city to the grass, the route with the grass, way back). The leaders' best are 14, 21, 24, 29 and 43.
TRAINING = {
    0: ("Brock", "Pewter City", 12, "east", "Route 3", "west"),
    1: ("Misty", "Cerulean City", 18, "west", "Route 4", "east"),
    2: ("Lt. Surge", "Vermilion City", 21, "north", "Route 6", "south"),
    3: ("Erika", "Celadon City", 26, "east", "Route 7", "west"),
    4: ("Koga", "Fuchsia City", 33, "east", "Route 15", "west"),
}
# Later on there's no grass close by, or what lives in it is too weak to help, so she's only warned.
# Badges she has -> (who's next, level to reach). Their best are 43, 47, 50, and the League goes up to 65.
LATE_TARGETS = {5: ("Sabrina", 36), 6: ("Blaine", 40), 7: ("Giovanni", 42), 8: ("the Elite Four", 48)}
TRAIN_LIMIT = 60                                    # map decisions per badge spent training, so she can never stall here
TRAIN_STEPS = {badges: (f"Your team isn't strong enough to beat {leader} yet. Go to {route}, on the {way} side of {city}, "
                        f"walk around in the tall grass, and battle what you meet until your strongest team member "
                        f"reaches level {level}.")
               for badges, (leader, city, level, way, route, _) in TRAINING.items()}
RETURN_STEPS = {badges: f"Your team is badly hurt. Leave {route} by the {back} side, go back to {city}, and heal at the Pokémon Center."
                for badges, (_, city, _, _, route, back) in TRAINING.items()}


# For each step: where she is -> the exit direction or door name that moves her forward.
TO_PEWTER = {"Pallet Town": "north", "Route 1": "north", "Viridian City": "north", "Route 22": "east",   # losing a battle sends her back
             "Route 2 - Viridian Forest - South Entrance": "Viridian Forest", "Viridian Forest": "North Entrance",
             "Route 2 - Viridian Forest - North Entrance": "Route 2", "Route 2": "north"}
ROUTE = {
    TO_VIRIDIAN: {"Pallet Town": "north", "Route 1": "north"},
    GET_PARCEL: {"Viridian City": "Viridian City - Mart"},
    PARCEL: {"Viridian City": "south", "Route 1": "south", "Pallet Town": "Pallet Town - Professor Oak's Lab"},
    TO_FOREST: {"Pallet Town": "north", "Route 1": "north", "Viridian City": "north", "Route 22": "east",
                "Route 2": "Viridian Forest - South Entrance",
                "Route 2 - Viridian Forest - South Entrance": "Viridian Forest"},
    THROUGH_FOREST: TO_PEWTER,
    BROCK: {**TO_PEWTER, "Route 3": "west", "Pewter City": "Pewter City - Gym"},
    TO_ROUTE_3: {"Pewter City": "east", "Route 3": "east", "Route 4": "Mt Moon"},
    MISTY: {"Route 4": "east", "Cerulean City": "Cerulean City - Gym"},
}
for _badges, (_leader, _city, _level, _way, _route, _back) in TRAINING.items():
    ROUTE[TRAIN_STEPS[_badges]] = {_city: _way}
    ROUTE[RETURN_STEPS[_badges]] = {_route: _back}
# Done training at a gym with no ROUTE entry: the way back to town. Kept apart because a ROUTE entry would also walk her
# out of every building on the way, like the ship or the Gym itself.
# Route 2 is cut in two by the forest: from the south half the north exit can't be reached, so she takes the forest door.
BACKUP_TARGET = {step: {"Route 2": "Viridian Forest - South Entrance"} for step in (THROUGH_FOREST, BROCK)}
AFTER_TRAINING = {BY_BADGES[badges]: {TRAINING[badges][4]: TRAINING[badges][5]} for badges in (2, 3, 4)}


# The buildings where a step's job gets done, by the game's full map names.
DESTINATIONS = {GET_PARCEL: "Viridian City - Mart", PARCEL: "Pallet Town - Professor Oak's Lab",
                BROCK: "Pewter City - Gym", MISTY: "Cerulean City - Gym"}


def target_for(step: str, place: str) -> str:
    """The exit direction or door name she should take now, or "" to leave it up to her."""
    if place in AFTER_TRAINING.get(step, {}):
        return AFTER_TRAINING[step][place]
    if step == BACK_TO_CENTER:
        return TO_NEAREST_CENTER.get(place, "")
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


def guide_hms(path: Path = GUIDE_PATH) -> str:
    """The HMs part of the owner's route notes, or "" if it isn't there."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    start = text.find("## HMs")
    if start == -1:
        return ""
    body = text[start + len("## HMs"):]
    end = body.find("\n#")
    return (body if end == -1 else body[:end]).strip()[:GUIDE_MAX_CHARS]


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


def backup_target(step: str, place: str) -> str:
    """Where to go instead if the usual exit for this step can't be reached from where she's standing, or ""."""
    return BACKUP_TARGET.get(step, {}).get(place, "")


def way_to_center(place: str, links: dict[str, str], places: dict[str, str]) -> str:
    """The remembered door or exit that starts the shortest walk she knows to a town with a Pokémon Center, or ""."""
    routes: dict[str, list[tuple[str, str]]] = {}
    for key, destination in links.items():
        origin = places.get(key.split("|")[0], "")
        if origin and destination and not destination.startswith("("):      # "(blocked)" and the like aren't places
            routes.setdefault(origin, []).append((key, destination))
    walks = deque(routes.get(place, []))
    seen = {place}
    while walks:
        first_step, at = walks.popleft()
        if at.split(" - ")[0] in CENTER_CITIES:
            return first_step
        if at not in seen:
            seen.add(at)
            walks.extend((first_step, onward) for _, onward in routes.get(at, []))
    return ""


def is_training(step: str) -> bool:
    """This step means going to the tall grass to level up."""
    return step in TRAIN_STEPS.values()


def _ready_for_gym(step: str, badges: int, place: str, strongest: int, can_train: bool, needs_healing: bool) -> str:
    """The gym step, unless her team is too weak for it and she's right by the grass. Never interrupts her travels."""
    if not strongest:                               # her team's level isn't known
        return step
    if badges in LATE_TARGETS:
        who, level = LATE_TARGETS[badges]
        if strongest >= level:
            return step
        return f"{step} Your team looks weak for {who}: try to get your strongest team member to level {level} first."
    if badges not in TRAINING or not can_train or strongest >= TRAINING[badges][2]:
        return step
    _, city, _, _, route, _ = TRAINING[badges]
    area = place.split(" - ")[0]
    if area == route:
        return RETURN_STEPS[badges] if needs_healing else TRAIN_STEPS[badges]
    return TRAIN_STEPS[badges] if area == city else step


def hint_for(badges: int, has_team: bool, key_items: list[str], places: list[str], delivered: bool,
             want_balls: bool = False, place: str = "", needs_healing: bool = False, heal_anywhere: bool = False,
             strongest: int = 0, can_train: bool = False) -> str:
    def been(name: str) -> bool:
        return any(name in visited for visited in places)

    def gym(step: str, badge_count: int) -> str:
        return _ready_for_gym(step, badge_count, place, strongest, can_train, needs_healing)

    if not has_team:
        return NO_TEAM
    if heal_anywhere and place.split(" - ")[0] not in CENTER_CITIES:
        return BACK_TO_CENTER
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
        return gym(BY_BADGES[badges], badges)
    if badges == 1:
        if been("Cerulean City"):
            return gym(MISTY, 1)
        return THROUGH_MT_MOON if been("Mt Moon") else TO_ROUTE_3
    if been("Pewter City"):
        return gym(BROCK, 0)
    if "Viridian Forest" in places:             # the forest itself, not the gate buildings named after it
        return THROUGH_FOREST
    if delivered:
        return TO_FOREST
    return GET_PARCEL if been("Viridian City") else TO_VIRIDIAN
