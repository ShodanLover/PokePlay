"""Speaks the AI's lines out loud (text-to-speech) on a background thread.

Engines:
  windows - the voice built into Windows (no install needed)
  piper   - Piper, a free local neural voice that sounds much better (pip install piper-tts)
  none    - don't speak, just show text on the overlay
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import wave


class Narrator:
    def __init__(self, engine: str = "windows", piper_model: str = "", rate: int = 0,
                 max_queue: int = 3, on_speak=None):
        self.engine = engine
        self.piper_model = piper_model
        self.rate = rate
        self.on_speak = on_speak      # callback(text) when a line starts playing
        self._q: queue.Queue[str] = queue.Queue()
        self._max_queue = max_queue
        self._busy = threading.Event()
        self._piper_voice = None
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text: str) -> None:
        text = " ".join(text.split())
        if not text:
            return
        # Drop stale lines if the voice is falling behind the game.
        while self._q.qsize() >= self._max_queue:
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._q.put(text)

    def is_speaking(self) -> bool:
        return self._busy.is_set() or not self._q.empty()

    def wait_until_quiet(self, timeout: float = 15.0) -> None:
        end = time.time() + timeout
        while self.is_speaking() and time.time() < end:
            time.sleep(0.1)

    # ------------------------------------------------------------------ worker
    def _run(self) -> None:
        while True:
            text = self._q.get()
            self._busy.set()
            try:
                if self.on_speak:
                    self.on_speak(text)
                print(f"[voice] {text}")
                if self.engine == "windows":
                    self._speak_windows(text)
                elif self.engine == "piper":
                    self._speak_piper(text)
                else:
                    time.sleep(min(6.0, 0.06 * len(text)))   # give viewers time to read it
            except Exception as e:  # noqa: BLE001
                print(f"[voice] error: {e}")
            finally:
                self._busy.clear()

    def _speak_windows(self, text: str) -> None:
        if sys.platform != "win32":
            time.sleep(min(6.0, 0.06 * len(text)))
            return
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {int(self.rate)}; "
            "$s.Speak([Console]::In.ReadToEnd())"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], input=text.encode("utf-8"),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)

    def _speak_piper(self, text: str) -> None:
        if self._piper_voice is None:
            from piper import PiperVoice  # pip install piper-tts
            if not self.piper_model or not os.path.exists(self.piper_model):
                raise RuntimeError(f"Piper voice model not found: {self.piper_model!r}")
            self._piper_voice = PiperVoice.load(self.piper_model)
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with wave.open(path, "wb") as wav:
                if hasattr(self._piper_voice, "synthesize_wav"):
                    self._piper_voice.synthesize_wav(text, wav)
                else:
                    self._piper_voice.synthesize(text, wav)
            _play_wav(path)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


def _play_wav(path: str) -> None:
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
    elif sys.platform == "darwin":
        subprocess.run(["afplay", path], check=False)
    else:
        subprocess.run(["aplay", "-q", path], check=False)
