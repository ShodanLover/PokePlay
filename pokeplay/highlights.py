"""A running shortlist of moments worth clipping, saved to logs/highlights-DATE.md with the time of day."""

from __future__ import annotations

import re
import time
from pathlib import Path

REACTION_SECONDS = 12       # what she says this soon after a big moment is probably worth watching
BIG_MOMENT = re.compile(r"you lost|caught it|changed form|fainted|badge|you named|new: .*(?:gym|city|town|cave|forest|tunnel)",
                        re.I)


class Highlights:
    def __init__(self, folder: Path | str):
        self.folder = Path(folder)
        self._last_big = 0.0

    def _write(self, tag: str, text: str) -> None:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            path = self.folder / f"highlights-{time.strftime('%Y-%m-%d')}.md"
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%H:%M:%S')}  [{tag}] {text}\n")
        except OSError as e:                # a nice extra: it must never affect the stream
            print(f"[highlights] couldn't write: {e}")

    def event(self, text: str) -> None:
        if BIG_MOMENT.search(text):
            self._last_big = time.time()
            self._write("BIG MOMENT", text)

    def badge(self, count: int) -> None:
        self._last_big = time.time()
        self._write("BIG MOMENT", f"She earned badge number {count}!")

    def spoken(self, text: str, running_joke: str = "", was_news: bool = False) -> None:
        if was_news:
            self._write("REAL-WORLD TAKE", text)
        elif running_joke and running_joke.split()[0].lower() in text.lower():
            self._write("RUNNING JOKE", text)
        elif time.time() - self._last_big <= REACTION_SECONDS:
            self._write("REACTION", text)
