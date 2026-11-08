"""Reads whatever menu is on screen (options + cursor) and moves through it like a player would.

FireRed has two kinds of menus, both readable from memory:
- list menus (bag items, shop items, TM Case): a game "task" holds the item labels and cursor;
- small box menus (Start menu, YES/NO, USE/GIVE/TOSS, script choices): one shared cursor,
  with option labels in ROM tables.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from . import addresses as A
from .emulator import Emulator
from .game import Game
from .text import decode

BAG_POCKETS = ["ITEMS", "KEY ITEMS", "POKé BALLS"]
BACK = "Back out / close this (B button)"


@dataclass
class Menu:
    kind: str                       # yesno | multichoice | start | bag_context | tm_context | party_action |
                                    # shop | quantity | forget_move | list | party_choose
    title: str
    options: list[str]
    cursor: int = 0
    cancel_with_b: bool = True      # a "Back out" option is offered, done with B
    data: dict = field(default_factory=dict)

    def all_options(self) -> list[str]:
        return self.options + ([BACK] if self.cancel_with_b else [])


class MenuReader:
    def __init__(self, emu: Emulator, game: Game):
        self.emu = emu
        self.game = game
        self.last_message = ""      # set by the agent: helps label yes/no questions

    # ------------------------------------------------------------------ helpers
    def _text(self, ptr: int, length: int = 40) -> str:
        if not (0x02000000 <= ptr < 0x0A000000):
            return ""
        return decode(self.emu.read(ptr, length))

    def _menu_actions(self, table: int, indices: list[int]) -> list[str]:
        out = []
        for i in indices:
            ptr = self.emu.u32(table + i * 8)
            out.append(self._text(ptr) or f"option {i + 1}")
        return out

    def _tasks(self) -> list[tuple[int, int, bytes]]:
        raw = self.emu.read(A.gTasks, A.TASK_SIZE * A.NUM_TASKS)
        out = []
        for i in range(A.NUM_TASKS):
            t = raw[i * A.TASK_SIZE:(i + 1) * A.TASK_SIZE]
            func = struct.unpack_from("<I", t, 0)[0] & ~1
            if t[4]:   # isActive
                out.append((i, func, t[8:]))
        return out

    def _small_cursor(self) -> int:
        return struct.unpack("<b", self.emu.read(A.sMenu + 2, 1))[0]

    # ------------------------------------------------------------------ reading
    def read(self) -> Menu | None:
        tasks = self._tasks()
        funcs = {func: (i, data) for i, func, data in tasks}

        if A.Task_YesNoMenu_HandleInput in funcs or (
                any(f in A.YESNO_TASKS for f in funcs) and self.emu.u8(A.sYesNoWindowId) != 0xFF):
            return Menu("yesno", self.last_message or "Yes or no?", ["YES", "NO"], self._small_cursor(),
                        cancel_with_b=False)

        if A.Task_MultichoiceMenu_HandleInput in funcs:
            _, data = funcs[A.Task_MultichoiceMenu_HandleInput]
            mc_id = struct.unpack_from("<h", data, 7 * 2)[0]
            list_ptr, count = struct.unpack("<IB", self.emu.read(A.sMultichoiceLists + mc_id * 8, 5))
            labels = [self._text(self.emu.u32(list_ptr + i * 8)) for i in range(min(count, 12))]
            return Menu("multichoice", self.last_message or "Choose one:", labels, self._small_cursor(),
                        cancel_with_b=False)

        if A.Task_FieldItemContextMenuHandleInput in funcs:
            ptr = self.emu.u32(A.sContextMenuItemsPtr)
            n = self.emu.u8(A.sContextMenuNumItems)
            ids = list(self.emu.read(ptr, n)) if ptr and n <= 8 else []
            return Menu("bag_context", "What to do with this item?",
                        self._menu_actions(A.sItemMenuContextActions, ids), self._small_cursor())

        if A.Task_TMCaseContextMenu_HandleInput in funcs:
            return Menu("tm_context", "What to do with this move disc?",
                        self._menu_actions(A.sTMCaseMenuActions, [0, 1, 2]), self._small_cursor())

        if A.Task_HandleSelectionMenuInput in funcs:
            base = self.emu.u32(A.sPartyMenuInternal)
            raw = self.emu.read(base + 0x0F, 9)
            n = min(raw[8], 8)
            mon = self._party_slot_name()
            return Menu("party_action", f"What to do with {mon}?",
                        self._menu_actions(A.sCursorOptions, list(raw[:n])), self._small_cursor())

        if A.Task_BuyHowManyDialogueHandleInput in funcs:
            _, data = funcs[A.Task_BuyHowManyDialogueHandleInput]
            count = struct.unpack_from("<h", data, 1 * 2)[0]
            return Menu("quantity", "How many do you want to buy?",
                        ["Buy 1", "Buy 2", "Buy 3", "Buy 5", "Buy 10"], 0, data={"count": count})

        if A.Task_ShopMenu in funcs:
            return Menu("shop", "The shop clerk is waiting.",
                        self._menu_actions(A.sShopMenuActions_BuySellQuit, [0, 1, 2]), self._small_cursor(),
                        cancel_with_b=False)

        if A.Task_InputHandler_SelectOrForgetMove in funcs:
            return self._forget_move_menu()

        if A.Task_StartMenuHandleInput in funcs:
            n = min(self.emu.u8(A.sNumStartMenuItems), 9)
            order = list(self.emu.read(A.sStartMenuOrder, n))
            labels = self._menu_actions(A.sStartMenuActionTable, order)
            return Menu("start", "The main menu is open.", labels, self.emu.u8(A.sStartMenuCursorPos),
                        data={"order": order})

        lst = self._list_menu(tasks, funcs)
        if lst:
            return lst

        if A.Task_HandleChooseMonInput in funcs:
            return self._party_choose_menu()
        return None

    def _party_slot_name(self) -> str:
        slot = self.emu.u8(A.gPartyMenu_slotId)
        party = self.game.party()
        return party[slot].nickname if 0 <= slot < len(party) else "this Pokémon"

    def _party_choose_menu(self) -> Menu:
        party = self.game.party()
        labels = [m.summary() + ("; moves: " + ", ".join(mv.name for mv in m.moves) if m.moves else "")
                  for m in party]
        slot = self.emu.u8(A.gPartyMenu_slotId)
        return Menu("party_choose", "Choose a Pokémon.", labels, slot if slot < len(party) else 0)

    def _forget_move_menu(self) -> Menu:
        idx = self.emu.u8(A.sLastViewedMonIndex)
        party = self.game.party()
        mon = party[idx] if 0 <= idx < len(party) else None
        new_move = ""
        m = re.search(r"learn (?:the move )?([A-Z0-9][A-Z0-9 \-']+?)[.!?]", self.last_message)
        if m:
            new_move = m.group(1).strip()
        labels = [f"Forget {mv.name} ({mv.type_name}, {mv.pp} PP)" for mv in (mon.moves if mon else [])]
        labels.append(f"Don't learn {new_move or 'the new move'} (keep all current moves)")
        title = f"{mon.nickname if mon else 'Your Pokémon'} wants to learn {new_move or 'a new move'} " \
                "but already knows 4 moves. Pick one to forget."
        return Menu("forget_move", title, labels, self.emu.u8(A.sMoveSelectionCursorPos), cancel_with_b=False)

    def _list_menu(self, tasks, funcs) -> Menu | None:
        list_ids = [i for i, func, _ in tasks if func == A.ListMenuDummyTask]
        if not list_ids:
            return None
        task_id, title, kind = list_ids[-1], "Choose from the list:", "list"
        for owner, data_index, owner_title in ((A.Task_BagMenu_HandleInput, 0, "bag"),
                                              (A.Task_TMCaseHandleListInput, 0, "tm"),
                                              (A.Task_BuyMenu, 7, "shop")):
            if owner in funcs:
                cand = struct.unpack_from("<h", funcs[owner][1], data_index * 2)[0]
                if cand in list_ids:
                    task_id, kind = cand, owner_title
                break
        data = self.emu.read(A.gTasks + task_id * A.TASK_SIZE + 8, 32)
        items_ptr, = struct.unpack_from("<I", data, 0)
        total, = struct.unpack_from("<H", data, 0x0C)
        cursor, above = struct.unpack_from("<HH", data, 0x18)
        total = min(total, 120)
        raw = self.emu.read(items_ptr, total * 8) if items_ptr else b""
        labels, indices = [], []
        for i in range(total):
            label_ptr, index = struct.unpack_from("<Ii", raw, i * 8)
            label = self._text(label_ptr) or f"entry {i + 1}"
            if kind == "shop" and 0 < index < A.NUM_ITEMS:
                price = self.emu.u16(A.gItems + index * 44 + A.gItems_PRICE_OFFSET)
                label += f" (₽{price})"
            labels.append(label)
            indices.append(index)
        menu = Menu(kind if kind != "list" else "list", title, labels, cursor + above,
                    data={"task_id": task_id, "kind": kind})
        if kind == "bag":
            pocket = self.emu.u16(A.gBagMenuState + 6)
            menu.title = f"Your Bag is open on the {BAG_POCKETS[pocket] if pocket < 3 else '?'} pocket."
            menu.data["pocket"] = pocket
            menu.data["pocket_options_from"] = len(menu.options)
            for p, name in enumerate(BAG_POCKETS):
                if p != pocket:
                    menu.options.append(f"Switch to the {name} pocket")
        elif kind == "tm":
            menu.title = "Your TM Case (move discs) is open."
        elif kind == "shop":
            menu.title = f"The shop's items. You have ₽{self.game.state().money}."
        return menu

    # ------------------------------------------------------------------ acting
    def _nav_small(self, target: int, read_cursor) -> bool:
        for _ in range(12):
            cur = read_cursor()
            if cur == target:
                return True
            self.emu.press("DOWN" if cur < target else "UP", hold=2, wait=6)
        return read_cursor() == target

    def choose(self, menu: Menu, index: int) -> str:
        """Carry out option `index` of menu.all_options(). Returns a short description."""
        opts = menu.all_options()
        index = max(0, min(index, len(opts) - 1))
        label = opts[index]
        if label == BACK:
            self.emu.press("B", hold=2, wait=20)
            return "backed out"

        k = menu.kind
        if k == "yesno":
            # YES = A, NO = B works for every yes/no box in the game.
            self.emu.press("A" if index == 0 else "B", hold=2, wait=20)
            return label
        if k in ("multichoice", "bag_context", "tm_context", "party_action", "shop", "start", "forget_move"):
            read = {"start": lambda: self.emu.u8(A.sStartMenuCursorPos),
                    "forget_move": lambda: self.emu.u8(A.sMoveSelectionCursorPos)}.get(k, self._small_cursor)
            if not self._nav_small(index, read):
                return f"couldn't move the cursor to {label}"   # never select the wrong thing
            self.emu.press("A", hold=2, wait=30 if k in ("start", "forget_move") else 20)
            return label
        if k == "quantity":
            want = [1, 2, 3, 5, 10][index]
            have = menu.data.get("count", 1)
            for _ in range(abs(want - have)):
                self.emu.press("UP" if want > have else "DOWN", hold=2, wait=4)
            self.emu.press("A", hold=2, wait=20)
            return label
        if k == "party_choose":
            for _ in range(10):
                slot = self.emu.u8(A.gPartyMenu_slotId)
                if slot == index:
                    break
                self.emu.press("DOWN" if slot < index or slot > 5 else "UP", hold=2, wait=6)
            else:
                return f"couldn't move the cursor to {label}"
            self.emu.press("A", hold=2, wait=20)
            return label
        if k in ("list", "bag", "tm", "shop"):
            pocket_from = menu.data.get("pocket_options_from")
            if pocket_from is not None and index >= pocket_from and index < len(menu.options):
                target = BAG_POCKETS.index(label.replace("Switch to the ", "").replace(" pocket", ""))
                for _ in range(4):
                    if self.emu.u16(A.gBagMenuState + 6) == target:
                        break
                    cur = self.emu.u16(A.gBagMenuState + 6)
                    self.emu.press("RIGHT" if target > cur else "LEFT", hold=2, wait=24)
                return label
            task_id = menu.data["task_id"]
            base = A.gTasks + task_id * A.TASK_SIZE + 8

            def cur():
                c, a = struct.unpack("<HH", self.emu.read(base + 0x18, 4))
                return c + a
            for _ in range(130):
                c = cur()
                if c == index:
                    break
                self.emu.press("DOWN" if c < index else "UP", hold=2, wait=3)
            else:
                return f"couldn't move the cursor to {label}"
            self.emu.press("A", hold=2, wait=20)
            return label
        self.emu.press("A", hold=2, wait=20)
        return label
