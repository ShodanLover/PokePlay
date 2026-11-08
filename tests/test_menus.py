"""Fake FireRed menus in memory and check she can read and drive them."""

import struct

from pokeplay import addresses as A
from pokeplay.menus import BACK, MenuReader
from pokeplay.text import encode_simple

from test_core import build_mon, make_game

STR_BASE = 0x08700000


class MenuWorld:
    def __init__(self):
        self.g = make_game()
        self.e = self.g.emu
        self._str = STR_BASE
        self.presses = []
        self.e.press = self.press
        self.e.wait_frames = lambda n: None
        self.on_press = None

    def string(self, text):
        addr = self._str
        self.e.write(addr, encode_simple(text))
        self._str += 64
        return addr

    def task(self, slot, func, data=()):
        raw = bytearray(A.TASK_SIZE)
        struct.pack_into("<I", raw, 0, func | 1)
        raw[4] = 1
        for i, v in enumerate(data):
            struct.pack_into("<h", raw, 8 + i * 2, v)
        self.e.write(A.gTasks + slot * A.TASK_SIZE, bytes(raw))

    def menu_actions(self, addr, labels):
        for i, l in enumerate(labels):
            self.e.write(addr + i * 8, struct.pack("<II", self.string(l), 0))

    def press(self, key, hold=6, wait=6):
        self.presses.append(key)
        if self.on_press:
            self.on_press(key)


def small_cursor(w, maxpos):
    def move(key):
        cur = struct.unpack("<b", w.e.read(A.sMenu + 2, 1))[0]
        if key == "DOWN":
            cur = (cur + 1) % (maxpos + 1)
        elif key == "UP":
            cur = (cur - 1) % (maxpos + 1)
        w.e.write(A.sMenu + 2, struct.pack("<b", cur))
    return move


def test_nothing_open():
    w = MenuWorld()
    assert MenuReader(w.e, w.g).read() is None


def test_yes_no_uses_a_and_b():
    w = MenuWorld()
    w.task(3, A.Task_YesNoMenu_HandleInput)
    r = MenuReader(w.e, w.g)
    r.last_message = "Would you like to use CUT?"
    m = r.read()
    assert m.kind == "yesno" and m.options == ["YES", "NO"] and BACK not in m.all_options()
    r.choose(m, 1)
    assert w.presses == ["B"]


def test_start_menu_navigation():
    w = MenuWorld()
    w.menu_actions(A.sStartMenuActionTable, ["POKéDEX", "POKéMON", "BAG", "RED", "SAVE", "OPTION", "EXIT"])
    w.e.write(A.sNumStartMenuItems, bytes([5]))
    w.e.write(A.sStartMenuOrder, bytes([1, 2, 3, 4, 6]))
    w.e.write(A.sStartMenuCursorPos, bytes([0]))
    w.task(2, A.Task_StartMenuHandleInput)

    def move(key):
        cur = w.e.u8(A.sStartMenuCursorPos)
        w.e.write(A.sStartMenuCursorPos, bytes([(cur + (1 if key == "DOWN" else -1)) % 5]))
    w.on_press = move
    r = MenuReader(w.e, w.g)
    m = r.read()
    assert m.kind == "start"
    assert m.options == ["POKéMON", "BAG", "RED", "SAVE", "EXIT"]
    r.choose(m, 1)                       # BAG
    assert w.presses == ["DOWN", "A"]


def test_bag_list_with_pockets_and_context_menu():
    w = MenuWorld()
    items = 0x02010000
    for i, name in enumerate(["POTION", "ANTIDOTE", "CLOSE BAG"]):
        w.e.write(items + i * 8, struct.pack("<Ii", w.string(name), i))
    tmpl = bytearray(32)
    struct.pack_into("<I", tmpl, 0, items)
    struct.pack_into("<H", tmpl, 0x0C, 3)
    w.task(4, A.ListMenuDummyTask, struct.unpack("<16h", bytes(tmpl)))
    w.task(1, A.Task_BagMenu_HandleInput, [4])
    w.e.write(A.gBagMenuState + 6, struct.pack("<H", 0))
    r = MenuReader(w.e, w.g)
    m = r.read()
    assert m.kind == "bag" and m.options[:3] == ["POTION", "ANTIDOTE", "CLOSE BAG"]
    assert "Switch to the KEY ITEMS pocket" in m.options

    def move(key):
        base = A.gTasks + 4 * A.TASK_SIZE + 8 + 0x18
        c = w.e.u16(base)
        if key == "DOWN":
            w.e.write(base, struct.pack("<H", c + 1))
        if key == "RIGHT":
            w.e.write(A.gBagMenuState + 6, struct.pack("<H", w.e.u16(A.gBagMenuState + 6) + 1))
    w.on_press = move
    r.choose(m, 1)
    assert w.presses == ["DOWN", "A"]
    w.presses.clear()
    r.choose(m, m.options.index("Switch to the KEY ITEMS pocket"))
    assert w.presses == ["RIGHT"]

    # Now the USE / GIVE / TOSS box opens on top of the list.
    w.menu_actions(A.sItemMenuContextActions, ["USE", "GIVE", "TOSS", "CANCEL"])
    w.e.write(0x02011000, bytes([0, 1, 2, 3]))
    w.e.write(A.sContextMenuItemsPtr, struct.pack("<I", 0x02011000))
    w.e.write(A.sContextMenuNumItems, bytes([4]))
    w.task(6, A.Task_FieldItemContextMenuHandleInput)
    m = r.read()
    assert m.kind == "bag_context" and m.options == ["USE", "GIVE", "TOSS", "CANCEL"]


def test_party_action_menu_and_choose():
    w = MenuWorld()
    w.e.write(A.gPlayerPartyCount, bytes([2]))
    w.e.write(A.gPlayerParty, build_mon(1, 2, 1, (33, 0, 0, 0), (35, 0, 0, 0), 9, 20, 25, "SPROUT"))
    w.e.write(A.gPlayerParty + 100, build_mon(3, 4, 25, (84, 0, 0, 0), (30, 0, 0, 0), 7, 0, 20, "ZAP"))
    w.menu_actions(A.sCursorOptions, ["SUMMARY", "SWITCH", "CANCEL", "ITEM", "CUT"])
    base = 0x02012000
    w.e.write(A.sPartyMenuInternal, struct.pack("<I", base))
    w.e.write(base + 0x0F, bytes([4, 0, 1, 3, 2, 0, 0, 0, 4]))
    w.task(5, A.Task_HandleSelectionMenuInput)
    r = MenuReader(w.e, w.g)
    m = r.read()
    assert m.kind == "party_action" and m.options == ["CUT", "SUMMARY", "SWITCH", "ITEM"]
    assert "SPROUT" in m.title

    w.task(5, A.Task_HandleChooseMonInput)
    m = r.read()
    assert m.kind == "party_choose" and m.options[1].startswith("ZAP") and "fainted" in m.options[1]


def test_multichoice_labels_from_rom():
    w = MenuWorld()
    lst = 0x08710000
    w.menu_actions(lst, ["BUY", "SELL", "SEE YA"])
    w.e.write(A.sMultichoiceLists + 7 * 8, struct.pack("<IB", lst, 3))
    w.task(2, A.Task_MultichoiceMenu_HandleInput, [0, 0, 0, 0, 0, 0, 0, 7])
    w.e.write(A.sMenu + 2, struct.pack("<b", 0))
    w.on_press = small_cursor(w, 2)
    r = MenuReader(w.e, w.g)
    m = r.read()
    assert m.options == ["BUY", "SELL", "SEE YA"]
    r.choose(m, 2)
    assert w.presses == ["DOWN", "DOWN", "A"]


def test_forget_move_screen():
    w = MenuWorld()
    w.e.write(A.gPlayerPartyCount, bytes([1]))
    w.e.write(A.gPlayerParty, build_mon(1, 2, 1, (33, 45, 55, 84), (35, 40, 25, 30), 9, 20, 25, "SPROUT"))
    w.e.write(A.sLastViewedMonIndex, bytes([0]))
    w.task(9, A.Task_InputHandler_SelectOrForgetMove)
    r = MenuReader(w.e, w.g)
    r.last_message = "SPROUT wants to learn the move VINE WHIP."
    m = r.read()
    assert m.kind == "forget_move" and len(m.options) == 5
    assert m.options[0].startswith("Forget MOVE33") and "VINE WHIP" in m.options[4]


def test_other_yes_no_boxes_detected_only_when_window_open():
    w = MenuWorld()
    w.task(2, 0x08125DBC)                    # "delete a move?" handler
    w.e.write(A.sYesNoWindowId, bytes([0xFF]))
    r = MenuReader(w.e, w.g)
    assert r.read() is None                  # handler alive but no box yet
    w.e.write(A.sYesNoWindowId, bytes([3]))
    assert r.read().kind == "yesno"
