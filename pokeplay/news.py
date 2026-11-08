"""Real headlines for her to remark on now and then. She says these live, so the worst topics are kept out."""

from __future__ import annotations

import random
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

REFRESH_SECONDS = 1800
MAX_FEED_BYTES = 2_000_000
MAX_HEADLINE_LENGTH = 140

MAX_HEADLINES = 40          # how many she has to pick from at a time
MIN_WORDS = 4               # shorter "headlines" are things like "Watch the Trailer"

# Politics is welcome. These stay out because she says this live: violence, crime, sexual content, death and illness.
# Over-filtering is fine: there are always more headlines.
UNSUITABLE = re.compile(
    r"\b(?:kill|murder|dead|death|dies?\b|died|dying|wars?\b|warfare|attack|assault|abus|rape|sex|shoot|shot|stab|terror"
    r"|bomb|massacre|genocide|suicid|cancer|disease|virus|illness|\bill\b|crash|blaze|flood|earthquake|hostage|prison"
    r"|jail|court|trial|accus|arrest|charged|guilty|convict|barrister|solicitor|police|crime|criminal|racis|hate|nazi"
    r"|gun|weapon|drug|overdose|tribute|mourn|funeral|tragedy|tragic|injur|sued?\b|lawsuit|alleg|harass|grief|naked"
    r"|nude|porn|victim|missing|russell brand)", re.I)


def parse_headlines(xml_bytes: bytes) -> list[str]:
    """Pull the suitable headlines out of an RSS feed."""
    out = []
    for item in ET.fromstring(xml_bytes).iter("item"):
        title = " ".join((item.findtext("title") or "").split())
        if len(title.split()) >= MIN_WORDS and len(title) <= MAX_HEADLINE_LENGTH and not UNSUITABLE.search(title):
            out.append(title)
    return out


class Headlines:
    def __init__(self, feeds: list[str]):
        self.feeds = feeds
        self._lock = threading.Lock()
        self._unused: list[str] = []
        self._seen: set[str] = set()

    def add(self, titles: list[str]) -> None:
        """Top the pool up to MAX_HEADLINES with stories she hasn't had yet."""
        with self._lock:
            for title in titles:
                if title not in self._seen and len(self._unused) < MAX_HEADLINES:
                    self._seen.add(title)
                    self._unused.append(title)

    def take(self) -> str:
        """A random headline she hasn't used, or "" if there are none."""
        with self._lock:
            return self._unused.pop(random.randrange(len(self._unused))) if self._unused else ""

    def refresh(self) -> None:
        titles: list[str] = []
        for url in self.feeds:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "PokePlay"})
                with urllib.request.urlopen(request, timeout=15) as response:
                    titles += parse_headlines(response.read(MAX_FEED_BYTES))
            except Exception as e:  # noqa: BLE001 - news is a nice extra and must never stop the stream
                print(f"[news] couldn't read {url}: {e}")
        random.shuffle(titles)              # so the pool is a mix of every feed
        self.add(titles)

    def _run(self) -> None:
        while True:
            self.refresh()
            time.sleep(REFRESH_SECONDS)

    def start(self) -> None:
        if self.feeds:
            threading.Thread(target=self._run, daemon=True).start()
