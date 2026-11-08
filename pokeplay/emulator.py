"""Talks to mGBA through the Lua bridge (lua/pokeplay_bridge.lua)."""

from __future__ import annotations

import socket
import struct
import time


class EmulatorError(RuntimeError):
    pass


class Emulator:
    def __init__(self, host: str = "127.0.0.1", port: int = 8888, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""

    # ---- connection -------------------------------------------------
    def connect(self, retry_seconds: float = 60.0) -> None:
        deadline = time.time() + retry_seconds
        while True:
            try:
                self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                self._buf = b""
                self.command("PING")
                return
            except OSError:
                if time.time() > deadline:
                    raise EmulatorError(
                        f"Could not connect to mGBA on {self.host}:{self.port}. "
                        "Is mGBA running with lua/pokeplay_bridge.lua loaded?"
                    )
                time.sleep(1.0)

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def command(self, line: str) -> str:
        if self._sock is None:
            raise EmulatorError("not connected")
        self._sock.sendall(line.encode("ascii") + b"\n")
        while b"\n" not in self._buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise EmulatorError("mGBA closed the connection")
            self._buf += chunk
        raw, self._buf = self._buf.split(b"\n", 1)
        text = raw.decode("ascii", "replace").strip()
        if text.startswith("ERR"):
            raise EmulatorError(f"{line!r} -> {text}")
        return text[3:] if text.startswith("OK ") else ""

    # ---- memory -----------------------------------------------------
    def read(self, addr: int, length: int) -> bytes:
        if length <= 0:
            return b""
        out = bytearray()
        # Keep each request a reasonable size.
        while length > 0:
            n = min(length, 0x8000)
            out += bytes.fromhex(self.command(f"READ {addr:08x} {n}"))
            addr += n
            length -= n
        return bytes(out)

    def u8(self, addr: int) -> int:
        return self.read(addr, 1)[0]

    def u16(self, addr: int) -> int:
        return struct.unpack("<H", self.read(addr, 2))[0]

    def u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read(addr, 4))[0]

    # ---- input ------------------------------------------------------
    def press(self, keys: str | list[str], hold: int = 6, wait: int = 6) -> None:
        """Hold the keys for `hold` frames, then release and wait `wait` frames.
        Returns once that has happened in the emulator (60 frames = 1 second)."""
        if isinstance(keys, (list, tuple)):
            keys = "+".join(keys) if keys else "NONE"
        self.command(f"PRESS {keys.upper()} {int(hold)} {int(wait)}")

    def wait_frames(self, frames: int) -> None:
        self.press("NONE", 0, frames)

    # ---- misc -------------------------------------------------------
    def info(self) -> str:
        return self.command("INFO")

    def frame(self) -> int:
        return int(self.command("FRAME"))

    def screenshot(self, path: str) -> None:
        self.command(f"SCREENSHOT {path}")

    def save_state(self, slot: int) -> None:
        self.command(f"SAVESTATE {slot}")
