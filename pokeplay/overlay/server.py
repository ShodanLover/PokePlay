"""Tiny local web server for the OBS overlay (add http://127.0.0.1:8765 as a Browser Source)."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML_PATH = Path(__file__).with_name("overlay.html")
SUBTITLES_PATH = Path(__file__).with_name("subtitles.html")
AVATAR_PATH = Path(__file__).with_name("avatar.html")
AVATAR_JS_PATH = Path(__file__).with_name("avatar.js")
AVATAR_3D_PATH = Path(__file__).with_name("avatar3d.js")
THREE_PATH = Path(__file__).with_name("three.min.js")


class OverlayState:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict = {"say": "", "thought": "", "goal": "", "mood": "", "stats": {}, "location": "", "badges": 0,
                            "money": 0, "party": [], "log": [], "mode": "", "action": "",
                            "subtitle": "", "streamer": "", "feed": [], "catch_up": None, "boss": None}

    def update(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)

    def log(self, line: str, keep: int = 8) -> None:
        with self._lock:
            self._data["log"] = (self._data["log"] + [line])[-keep:]

    def feed(self, line: str, keep: int = 4) -> None:
        """The newest things she's really done, for viewers."""
        with self._lock:
            if line and (not self._data["feed"] or self._data["feed"][-1]["text"] != line):
                self._data["feed"] = (self._data["feed"] + [{"time": time.strftime("%H:%M"), "text": line}])[-keep:]

    def snapshot(self) -> bytes:
        with self._lock:
            return json.dumps(self._data).encode()


def start_overlay(state: OverlayState, port: int = 8765) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.startswith("/state.json"):
                body, ctype = state.snapshot(), "application/json"
            elif self.path.startswith("/avatar3d.js"):
                body, ctype = AVATAR_3D_PATH.read_bytes(), "application/javascript; charset=utf-8"
            elif self.path.startswith("/three.min.js"):
                body, ctype = THREE_PATH.read_bytes(), "application/javascript; charset=utf-8"
            elif self.path.startswith("/avatar.js"):
                body, ctype = AVATAR_JS_PATH.read_bytes(), "application/javascript; charset=utf-8"
            elif self.path.startswith("/avatar"):
                body, ctype = AVATAR_PATH.read_bytes(), "text/html; charset=utf-8"
            elif self.path.startswith("/subtitles"):
                body, ctype = SUBTITLES_PATH.read_bytes(), "text/html; charset=utf-8"
            elif self.path in ("/", "/index.html"):
                body, ctype = HTML_PATH.read_bytes(), "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep the console quiet
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
