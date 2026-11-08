"""Memory addresses for Pokemon FireRed (US, version 1.0, game code BPRE).

Taken from the pret/pokefirered decompilation symbol file
(https://github.com/pret/pokefirered, `symbols` branch).
RAM addresses start with 0x02/0x03, ROM addresses with 0x08.
"""

# --- game identification (ROM header) ---
ROM_GAME_CODE = 0x080000AC          # 4 ASCII chars, "BPRE" for FireRed US
ROM_VERSION = 0x080000BC            # 0 = v1.0, 1 = v1.1

# --- RAM ---
gMain = 0x030030F0
gMain_callback2 = gMain + 0x04
gSaveBlock1Ptr = 0x03005008
gSaveBlock2Ptr = 0x0300500C
VMap = 0x03005040                   # {s32 width; s32 height; u16 *map}
sLockFieldControls = 0x03000F9C     # non-zero while a script/message has control
gMapHeader = 0x02036DFC
gObjectEvents = 0x02036E38          # 16 x 0x24 bytes
gPlayerAvatar = 0x02037078
gStringVar4 = 0x02021D18            # last expanded overworld message
gDisplayedStringBattle = 0x0202298C # current battle message

gPlayerPartyCount = 0x02024029
gPlayerParty = 0x02024284           # 6 x 100 bytes
gEnemyPartyCount = 0x0202402A
gEnemyParty = 0x0202402C

gBattleTypeFlags = 0x02022B4C
gBattleMons = 0x02023BE4            # 4 x 0x58 bytes
gBattlersCount = 0x02023BCC
gBattlerControllerFuncs = 0x03004FE0
gActionSelectionCursor = 0x02023FF8
gMoveSelectionCursor = 0x02023FFC
gBattleOutcome = 0x02023E8A
gPartyMenu = 0x0203B0A0
gPartyMenu_slotId = gPartyMenu + 0x09

# --- ROM functions (compared against gMain.callback2 etc.) ---
CB2_Overworld = 0x080565B4
BattleMainCB2 = 0x08011100
CB2_UpdatePartyMenu = 0x0811EBA0
CB2_NamingScreen = 0x0809FB70
CB2_RunPokemonSummaryScreen = 0x08137EE8
CB2_BagMenuRun = 0x08107EE0
HandleInputChooseAction = 0x0802E438
HandleInputChooseMove = 0x0802EA10
HandleInputChooseTarget = 0x0802E674

# --- ROM data tables ---
gSpeciesNames = 0x08245EE0          # 11 bytes each
gMoveNames = 0x08247094             # 13 bytes each
gBattleMoves = 0x08250C04           # 12 bytes each
gSpeciesInfo = 0x08254784           # 28 bytes each
gTypeEffectiveness = 0x0824F050     # (attacker, defender, x10) triples, 0xFF ends
gItems = 0x083DB028                 # 44 bytes each, name first
gMapGroups = 0x083526A8

NUM_SPECIES = 412
NUM_MOVES = 355
NUM_ITEMS = 375

# --- SaveBlock1 offsets ---
SB1_POS = 0x0000
SB1_LOCATION = 0x0004               # s8 group, s8 num, s8 warp, pad, s16 x, s16 y
SB1_MONEY = 0x0290
SB1_BAG_ITEMS = 0x0310              # 42 slots
SB1_BAG_KEY_ITEMS = 0x03B8          # 30 slots
SB1_BAG_BALLS = 0x0430              # 13 slots
SB1_BAG_TMHM = 0x0464               # 58 slots
SB1_BAG_BERRIES = 0x054C            # 43 slots
SB1_FLAGS = 0x0EE0
SB1_VARS = 0x1000

# --- SaveBlock2 offsets ---
SB2_PLAYER_NAME = 0x000
SB2_ENCRYPTION_KEY = 0xF20

# --- flags / vars ---
SYS_FLAGS = 0x800
FLAG_BADGE01_GET = SYS_FLAGS + 0x20
FLAG_SYS_POKEMON_GET = SYS_FLAGS + 0x28
FLAG_SYS_POKEDEX_GET = SYS_FLAGS + 0x29
FLAG_SYS_GAME_CLEAR = SYS_FLAGS + 0x2C
FLAG_GOT_SS_TICKET = 0x234
FLAG_GOT_HM01 = 0x237
FLAG_GOT_HM02 = 0x238
FLAG_GOT_HM03 = 0x239
FLAG_GOT_HM04 = 0x23A
FLAG_GOT_HM05 = 0x23B
FLAG_RESCUED_MR_FUJI = 0x23C
FLAG_GOT_POKE_FLUTE = 0x23D
FLAG_HELPED_BILL_IN_SEA_COTTAGE = 0x233
FLAG_GOT_BICYCLE = 0x271
FLAG_GOT_TEA = 0x2A6

# --- map grid ---
MAP_OFFSET = 7
MAPGRID_METATILE_ID_MASK = 0x03FF
MAPGRID_COLLISION_MASK = 0x0C00
MAPGRID_UNDEFINED = 0x03FF
NUM_METATILES_IN_PRIMARY = 640
METATILE_BEHAVIOR_MASK = 0x000001FF

PLAYER_AVATAR_FLAG_SURFING = 1 << 3

# --- naming screen (keyboard) ---
sNamingScreen = 0x0203998C          # pointer to struct NamingScreenData
gSprites = 0x0202063C               # 0x44 bytes each; data[] at +0x2E
NS_TEXT_BUFFER = 0x1800
NS_CURRENT_PAGE = 0x1E22
NS_CURSOR_SPRITE_ID = 0x1E23
NS_TEMPLATE_NUM = 0x1E2C
NS_MON_SPECIES = 0x1E34
