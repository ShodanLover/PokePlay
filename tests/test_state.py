"""Builds a fake FireRed memory image and checks the full state reader + option builder."""

import json
import struct
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from pokeplay import addresses as A
from pokeplay.brain import Brain
from pokeplay.overworld import Overworld

from test_core import build_mon, make_game

SB1, SB2 = 0x02025000, 0x02024A00
MAP_PTR, LAYOUT, TS1, TS2, ATTR1, ATTR2 = 0x02010000, 0x08400000, 0x08410000, 0x08410100, 0x08420000, 0x08430000
EVENTS, WARPS, CONNS, CONN_LIST = 0x08440000, 0x08440100, 0x08440200, 0x08440300
W, H = 6, 5


def build_world():
    g = make_game()
    e = g.emu
    w32 = lambda a, v: e.write(a, struct.pack("<I", v))
    w32(A.gMain_callback2, A.CB2_Overworld | 1)
    w32(A.gSaveBlock1Ptr, SB1)
    w32(A.gSaveBlock2Ptr, SB2)
    key = 0x11223344
    w32(SB2 + A.SB2_ENCRYPTION_KEY, key)
    e.write(SB1 + A.SB1_LOCATION, bytes([3, 0]))              # Pallet Town
    w32(SB1 + A.SB1_MONEY, 3000 ^ key)
    e.write(SB1 + A.SB1_FLAGS + A.FLAG_BADGE01_GET // 8, bytes([0b11]))   # 2 badges
    e.write(SB1 + A.SB1_BAG_ITEMS, struct.pack("<HH", 13, 5 ^ (key & 0xFFFF)))
    g.item_names = [f"ITEM{i}" for i in range(375)]
    # party
    e.write(A.gPlayerPartyCount, bytes([1]))
    e.write(A.gPlayerParty, build_mon(1234, 5678, 1, (33, 45, 0, 0), (35, 40, 0, 0), 7, 20, 24, "BULBA"))
    # player object (slot 0) at map (2,3) facing up; NPC (slot 1) at (4,1)
    e.write(A.gPlayerAvatar + 5, bytes([0]))
    obj = bytearray(0x24); obj[0] = 1; obj[2] = 1
    struct.pack_into("<hh", obj, 0x10, 2 + 7, 3 + 7); obj[0x18] = 2
    e.write(A.gObjectEvents, bytes(obj))
    npc = bytearray(0x24); npc[0] = 1; npc[8] = 5; npc[7] = 0
    struct.pack_into("<hh", npc, 0x10, 4 + 7, 1 + 7)
    e.write(A.gObjectEvents + 0x24, bytes(npc))
    # map grid: walls on the top row except a door at (1,0); grass at (4,4)
    xs, ys = W + 15, H + 14
    cells = [0] * (xs * ys)
    for y in range(H):
        for x in range(W):
            mt = 1
            col = 0
            if y == 0 and x != 1:
                col = 1
            if (x, y) == (4, 4):
                mt = 2
            cells[(y + 7) * xs + x + 7] = mt | (col << 10)
    e.write(A.VMap, struct.pack("<iiI", xs, ys, MAP_PTR))
    e.write(MAP_PTR, struct.pack(f"<{len(cells)}H", *cells))
    w32(A.gMapHeader, LAYOUT)
    e.write(LAYOUT + 0x10, struct.pack("<II", TS1, TS2))
    w32(TS1 + 0x14, ATTR1)
    w32(TS2 + 0x14, ATTR2)
    e.write(ATTR1, struct.pack("<3I", 0, 0, 0x02))            # metatile 2 = tall grass
    # events: one warp at the door (1,0) to Oak's lab (4.3)
    w32(A.gMapHeader + 4, EVENTS)
    e.write(EVENTS, bytes([0, 1, 0, 0]) + struct.pack("<IIII", 0, WARPS, 0, 0))
    e.write(WARPS, struct.pack("<hhBBBB", 1, 0, 0, 0, 3, 4))
    # connection: south to Route 1? (use 3.19 just as a number)
    w32(A.gMapHeader + 0xC, CONNS)
    e.write(CONNS, struct.pack("<iI", 1, CONN_LIST))
    e.write(CONN_LIST, bytes([1, 0, 0, 0]) + struct.pack("<I", 0) + bytes([3, 19, 0, 0]))
    return g


def test_full_state():
    g = build_world()
    s = g.state()
    assert s.mode == "overworld"
    assert s.map_name == "Pallet Town"
    assert (s.x, s.y, s.facing) == (2, 3, "up")
    assert s.money == 3000 and s.badges == 2
    assert s.items == [("ITEM13", 5)]
    assert s.party[0].nickname == "BULBA" and s.party[0].level == 7


def test_options():
    g = build_world()
    s = g.state()
    world = Overworld(g.emu, g)
    options, grid = world.build_options(s)
    kinds = {o.kind: o for o in options}
    assert grid.width == W and grid.height == H
    assert "Professor Oak's Lab" in kinds["warp"].label and kinds["warp"].target == (1, 0)
    assert kinds["exit"].direction == "down" and kinds["exit"].target[1] == H - 1
    assert kinds["talk"].npc.local_id == 5
    assert kinds["train"].target == (4, 4)


def test_brain_against_fake_ollama():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen["body"] = body
            if "format" in body:
                content = json.dumps({"thought": "The lab is where Oak is.", "say": "To the lab!", "choice": 2})
            else:
                content = "Wow, what a battle!"
            out = json.dumps({"message": {"role": "assistant", "content": content}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    brain = Brain(f"http://127.0.0.1:{srv.server_port}", "qwen3:4b", "Tester")
    d = brain.decide("CONTEXT", ["Go north", "Enter the lab", "Talk to mom"])
    assert d.choice == 1 and d.say == "To the lab!" and not d.fallback
    assert seen["body"]["think"] is False and seen["body"]["format"]["required"]
    assert brain.comment(["We won"], "CONTEXT") == "Wow, what a battle!"
    srv.shutdown()
