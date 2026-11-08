"""Runs lua/pokeplay_bridge.lua in a real Lua 5.4 interpreter with mGBA's API mocked.

Needs `pip install lupa`; skipped otherwise.
"""

from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa")
from lupa import lua54  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "lua" / "pokeplay_bridge.lua"

MOCK = r"""
mock = { keys = 0, frame = 0, mem = {}, logs = {}, sent = "", inbox = {} }

console = {
  log = function(self, s) table.insert(mock.logs, s) end,
  error = function(self, s) table.insert(mock.logs, "ERROR " .. s) end,
}

emu = {
  getGameCode = function(self) return "AGB-BPRE" end,
  getGameTitle = function(self) return "POKEMON FIRE" end,
  currentFrame = function(self) return mock.frame end,
  readRange = function(self, addr, len)
    local t = {}
    for i = 0, len - 1 do t[#t + 1] = string.char(mock.mem[addr + i] or 0) end
    return table.concat(t)
  end,
  addKeys = function(self, m) mock.keys = mock.keys | m end,
  clearKeys = function(self, m) mock.keys = mock.keys & ~m end,
  screenshot = function(self, p) end,
  saveStateSlot = function(self, s) mock.saved = s end,
  loadStateSlot = function(self, s) end,
}

local frameCbs = {}
callbacks = { add = function(self, name, fn) if name == "frame" then table.insert(frameCbs, fn) end end }
function mock.runFrame()
  mock.frame = mock.frame + 1
  for _, fn in ipairs(frameCbs) do fn() end
end

local clientSock = {
  handlers = {},
  receive = function(self, n)
    if #mock.inbox == 0 then return nil, socket.ERRORS.AGAIN end
    return table.remove(mock.inbox, 1)
  end,
  send = function(self, s) mock.sent = mock.sent .. s; return #s end,
  add = function(self, ev, fn) self.handlers[ev] = fn end,
  close = function(self) end,
}
local serverSock = {
  handlers = {},
  listen = function(self) return true end,
  accept = function(self) return clientSock end,
  add = function(self, ev, fn) self.handlers[ev] = fn end,
  close = function(self) end,
}
socket = {
  ERRORS = { AGAIN = "again", ADDRESS_IN_USE = "inuse" },
  bind = function(host, port) return serverSock end,
}
function mock.connect() serverSock.handlers.received() end
function mock.send(line)
  table.insert(mock.inbox, line)
  clientSock.handlers.received()
end
function mock.takeOutput() local s = mock.sent; mock.sent = ""; return s end
"""


@pytest.fixture()
def lua():
    rt = lua54.LuaRuntime()
    rt.execute(MOCK)
    rt.execute(SCRIPT.read_text())
    rt.eval("mock.connect()")
    return rt


def send(lua, line):
    lua.globals().mock.send(line)
    return lua.globals().mock.takeOutput()


def test_ping_info(lua):
    assert send(lua, "PING\n") == "OK PONG\n"
    assert send(lua, "INFO\n") == "OK AGB-BPRE POKEMON FIRE\n"


def test_read_hex(lua):
    lua.execute("mock.mem[0x02000000] = 0xAB; mock.mem[0x02000001] = 0x01")
    assert send(lua, "READ 02000000 3\n") == "OK ab0100\n"


def test_split_lines(lua):
    m = lua.globals().mock
    m.send("PI")
    assert m.takeOutput() == ""
    m.send("NG\nPING\n")
    assert m.takeOutput() == "OK PONG\nOK PONG\n"


def test_press_timing(lua):
    m = lua.globals().mock
    assert send(lua, "PRESS A+UP 3 2\n") == ""          # reply only after frames pass
    m.runFrame()
    assert m["keys"] == (1 << 0) | (1 << 6)
    m.runFrame()
    m.runFrame()
    assert m["keys"] == 0                                    # released after 3 frames
    assert m.takeOutput() == ""
    m.runFrame()
    m.runFrame()
    assert m.takeOutput() == "OK\n"


def test_errors(lua):
    assert send(lua, "PRESS Z 1 1\n").startswith("ERR unknown key")
    assert send(lua, "NOPE\n").startswith("ERR unknown command")
