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
gMonIconTable = 0x083D37A0          # pointer per species: 32x32 party icon, 4bpp tiles
gMonIconPaletteIndices = 0x083D3E80 # one byte per species
gMonIconPaletteTable = 0x083D4038   # 8 bytes each, palette pointer first
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

# --- menus (all from pret/pokefirered) ---
gTasks = 0x03005090                 # 16 tasks x 0x28: func, isActive, prev, next, priority, s16 data[16]
TASK_SIZE = 0x28
NUM_TASKS = 16
sMenu = 0x0203ADE4                  # struct Menu (small box menus): cursorPos at +2, maxCursorPos at +4
sStartMenuCursorPos = 0x020370F4
sNumStartMenuItems = 0x020370F5
sStartMenuOrder = 0x020370F6
sStartMenuActionTable = 0x083A7344  # MenuAction[] {text*, func}
sContextMenuItemsPtr = 0x0203AD24
sContextMenuNumItems = 0x0203AD28
sItemMenuContextActions = 0x08452EB8
gBagMenuState = 0x0203ACFC          # pocket (u16) at +6
sPartyMenuInternal = 0x0203B09C     # pointer; actions[8] at +0xF, numActions at +0x17
sCursorOptions = 0x0845A618         # party menu action names
sMultichoiceLists = 0x083E04B0      # {MenuAction *list; u8 count}
sShopMenuActions_BuySellQuit = 0x083DF09C
sTMCaseMenuActions = 0x08463150     # USE / GIVE / EXIT
sMoveSelectionCursorPos = 0x0203B16D
sLastViewedMonIndex = 0x0203B16C
gItems_PRICE_OFFSET = 16

# Task functions that tell us which menu is on screen
Task_YesNoMenu_HandleInput = 0x0809CE54
Task_MultichoiceMenu_HandleInput = 0x0809CC98
Task_FieldItemContextMenuHandleInput = 0x08109BE4
Task_TMCaseContextMenu_HandleInput = 0x08132568
Task_TMCaseHandleListInput = 0x081322D4
Task_HandleSelectionMenuInput = 0x08122C5C
Task_HandleChooseMonInput = 0x0811FB28
Task_ShopMenu = 0x0809AC10
Task_BuyMenu = 0x0809BBC0
Task_BuyHowManyDialogueHandleInput = 0x0809BD8C
Task_InputHandler_SelectOrForgetMove = 0x081393D4
Task_StartMenuHandleInput = 0x0806F1F0
Task_BagMenu_HandleInput = 0x08108F0C
ListMenuDummyTask = 0x08106ECC

# Object graphics ids for field obstacles
OBJ_EVENT_GFX_ITEM_BALL = 92
OBJ_EVENT_GFX_CUT_TREE = 95
OBJ_EVENT_GFX_ROCK_SMASH_ROCK = 96
OBJ_EVENT_GFX_PUSHABLE_BOULDER = 97

# Every other yes/no handler in the game (party menu, TM Case, shops...). Any of these
# being active while the yes/no window exists means a YES/NO question is on screen.
YESNO_TASKS = {
    0x080BF560,  # Task_CallYesOrNoCallback (generic, used by TM Case / shops)
    0x080EC324,  # Task_MoveToBagYesNoMenuHandleInput
    0x080F5708,  # Task_HandleYesNoMenu
    0x0811FEA4,  # Task_HandleCancelChooseMonYesNoInput
    0x08120AC4,  # Task_HandleCancelParticipationYesNoInput
    0x08123930,  # Task_HandleSwitchItemsYesNoInput
    0x08123E8C,  # Task_HandleSendMailToPCYesNoInput
    0x08123F80,  # Task_HandleLoseMailMessageYesNoInput
    0x08124828,  # Task_HandleFieldMoveExitAreaYesNoInput
    0x08125DBC,  # Task_HandleReplaceMoveYesNoInput ("delete a move?")
    0x08126170,  # Task_HandleStopLearningMoveYesNoInput ("stop learning?")
    0x08127268,  # Task_HandleSwitchItemsFromBagYesNoInput
}
sYesNoWindowId = 0x0203ADF3         # 0xFF when no yes/no box exists
