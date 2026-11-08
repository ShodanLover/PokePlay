"""A simple FireRed walkthrough: picks the current goal from the game's story flags."""

from __future__ import annotations

from . import addresses as A
from .game import Game, GameState

TEAM_TIP = ("Keep your team healthy: if your Pokémon are hurt, go to a Pokémon Center "
            "and talk to the nurse behind the counter.")


def current_objective(game: Game, s: GameState) -> str:
    badges = s.badges
    key_items = {k.upper() for k in s.key_items}

    if not game.flag(A.FLAG_SYS_POKEMON_GET):
        return ("Get your first Pokémon. If you're in your house, go downstairs and out the front door. "
                "In Pallet Town, walk north toward Route 1; Professor Oak will stop you and take you to his lab. "
                "In the lab, talk to one of the three Poké Balls on the table to choose a starter: "
                "Bulbasaur (Grass), Squirtle (Water) or Charmander (Fire). Your rival battles you right after.")
    if not game.flag(A.FLAG_SYS_POKEDEX_GET):
        if "OAK'S PARCEL" in key_items:
            return ("You have Oak's Parcel. Go south from Viridian City along Route 1 back to Pallet Town "
                    "and deliver it to Professor Oak in his lab.")
        return ("Go north from Pallet Town along Route 1 to Viridian City. Enter the Poké Mart there; "
                "the clerk will give you Oak's Parcel to deliver.")
    if badges == 0:
        return ("Head north from Viridian City to Route 2 and go through Viridian Forest to reach Pewter City. "
                "Train your team to around level 12-14, then beat Brock at the Pewter City Gym. "
                "Brock uses Rock/Ground Pokémon: Water, Grass and Fighting moves are strong against them. " + TEAM_TIP)
    if badges == 1:
        return ("Go east from Pewter City along Route 3 to Mt. Moon. Make your way through Mt. Moon "
                "(Team Rocket is inside) and follow Route 4 to Cerulean City. Then beat Misty at the "
                "Cerulean City Gym. She uses Water Pokémon: Grass and Electric moves work well. " + TEAM_TIP)
    if badges == 2:
        if not game.flag(A.FLAG_HELPED_BILL_IN_SEA_COTTAGE):
            return ("Go north from Cerulean City across Nugget Bridge (Route 24), then east along Route 25 "
                    "to Bill's Sea Cottage. Help Bill and he'll give you the S.S. Ticket.")
        if not game.flag(A.FLAG_GOT_HM01):
            return ("Travel south from Cerulean City: Route 5, the Underground Path, Route 6, then Vermilion City. "
                    "Show your S.S. Ticket at the harbor, board the S.S. Anne, find the captain's cabin and "
                    "talk to the captain to get HM01 (Cut).")
        return ("Teach Cut to a Pokémon, cut the small tree blocking Vermilion City Gym, and beat Lt. Surge. "
                "He uses Electric Pokémon: Ground-types are immune to Electric moves. " + TEAM_TIP)
    if badges == 3:
        return ("Head to Celadon City (Route 9 east of Cerulean, Rock Tunnel, Lavender Town, then west via "
                "Route 8 and the Underground Path to Route 7). Beat Erika at the Celadon Gym. She uses "
                "Grass Pokémon: Fire, Flying, Ice and Poison moves are strong. " + TEAM_TIP)
    if badges == 4:
        if not game.flag(A.FLAG_RESCUED_MR_FUJI):
            return ("Find Team Rocket's hideout under the Celadon Game Corner and get the Silph Scope from "
                    "Giovanni. Then climb Pokémon Tower in Lavender Town and rescue Mr. Fuji at the top.")
        return ("Use the Poké Flute to wake the sleeping Snorlax, then travel to Fuchsia City and beat Koga. "
                "He uses Poison Pokémon: Psychic and Ground moves work well. " + TEAM_TIP)
    if badges == 5:
        if not game.flag(A.FLAG_GOT_TEA):
            return ("Get the Tea from the old lady in Celadon Mansion so the guards will let you into "
                    "Saffron City. Also find Surf (HM03) in the Safari Zone and Strength (HM04) from the "
                    "Fuchsia warden.")
        return ("Enter Saffron City, free Silph Co. from Team Rocket, then beat Sabrina at the Saffron Gym. "
                "She uses Psychic Pokémon: Bug, Ghost and Dark moves are strong. " + TEAM_TIP)
    if badges == 6:
        return ("Surf south from Pallet Town to Cinnabar Island. Find the Secret Key in the Pokémon Mansion, "
                "then beat Blaine at the Cinnabar Gym. He uses Fire Pokémon: Water, Ground and Rock moves "
                "work well. " + TEAM_TIP)
    if badges == 7:
        return ("Return to Viridian City and beat Giovanni at the Viridian Gym. He uses Ground Pokémon: "
                "Water, Grass and Ice moves are strong. " + TEAM_TIP)
    if not game.flag(A.FLAG_SYS_GAME_CLEAR):
        return ("Go west from Viridian City along Route 22, north on Route 23 through Victory Road, and "
                "challenge the Elite Four at Indigo Plateau. Stock up on healing items first.")
    return "You're the Champion! Explore, catch Pokémon and have fun."
