"""Reads Twitch chat so she can talk back. Read-only and anonymous. Chat must never influence her game decisions."""

from __future__ import annotations

import collections
import random
import re
import socket
import threading
import time

from .brain import NOT_FOR_STREAM
from .news import UNSUITABLE

MAX_LENGTH = 200
LINK = re.compile(r"https?://|www\.|\.(?:com|net|org|gg|tv)\b", re.I)
LINE = re.compile(r"^:(\w+)!\S+ PRIVMSG #\S+ :(.*)$")


def worth_reading(user: str, text: str) -> bool:
    """She says these things out loud, so the worst never reach her."""
    if not text or len(text) > MAX_LENGTH or text.startswith("!") or LINK.search(text):
        return False
    return not (UNSUITABLE.search(text) or NOT_FOR_STREAM.search(text) or NOT_FOR_STREAM.search(user))


class ChatListener:
    def __init__(self, channel: str):
        self.channel = channel
        self._inbox: collections.deque[tuple[str, str]] = collections.deque(maxlen=20)
        self._lock = threading.Lock()

    def handle_line(self, line: str) -> None:
        match = LINE.match(line.strip())
        if not match:
            return
        user, text = match.group(1), match.group(2).strip()
        print(f"[chat] received from {user}: {text}")
        if worth_reading(user, text):
            with self._lock:
                self._inbox.append((user, text))
        else:
            print("[chat] (filtered out)")

    def take(self) -> tuple[str, str] | None:
        """The newest message she hasn't answered, or None."""
        with self._lock:
            return self._inbox.pop() if self._inbox else None

    def _run(self) -> None:
        while True:
            try:
                with socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=330) as sock:
                    sock.sendall(f"NICK justinfan{random.randint(10000, 89999)}\r\nJOIN #{self.channel}\r\n".encode())
                    buffer = b""
                    while True:
                        data = sock.recv(4096)
                        if not data:
                            break
                        buffer += data
                        *lines, buffer = buffer.split(b"\r\n")
                        for raw in lines:
                            line = raw.decode("utf-8", "replace")
                            if line.startswith("PING"):
                                sock.sendall(line.replace("PING", "PONG").encode() + b"\r\n")
                            else:
                                self.handle_line(line)
            except OSError as e:            # a nice extra: it must never affect the stream
                print(f"[chat] reconnecting: {e}")
            time.sleep(15)

    def start(self) -> None:
        if self.channel:
            threading.Thread(target=self._run, daemon=True).start()
