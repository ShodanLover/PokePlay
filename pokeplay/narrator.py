"""Speaks the AI's lines out loud (text-to-speech) on a background thread.

Engines:
  windows - the voice built into Windows (no install needed)
  piper   - Piper, a free local neural voice that sounds much better (pip install piper-tts)
  none    - don't speak, just show text on the overlay
"""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import tempfile
import array
import threading
import time
import wave


SPELLED_OUT = {"HP", "PP", "TM", "HM", "OK", "TV", "PC", "NES", "AI", "KO"}     # capitals that really are letters


def pronounceable(text: str) -> str:
    """Respell words the voice gets wrong. Only what she says changes; subtitles keep the real spelling."""
    text = re.sub(r"\bpok[eé]\s*-?mon", "Pokemon", text, flags=re.I)         # "Pokémon" comes out as "PAH-kay-mun"
    text = re.sub(r"\bpok[eé]\s*-?dex", "Poh-kay-decks", text, flags=re.I)
    text = re.sub(r"\bpok[eé]\s*-?(balls?|mart|cent(?:er|re)|flute)\b", r"Pohkay \1", text, flags=re.I)
    text = re.sub(r"\bpoké\b", "Pohkay", text, flags=re.I)                   # plain "poke" is left as a normal word
    # The game writes names in capitals, and the voice spells those out: "OAK" came out as "Oh-aye-kay".
    return re.sub(r"\b[A-Z]{2,}\b", lambda m: m.group() if m.group() in SPELLED_OUT else m.group().capitalize(), text)


class Narrator:
    def __init__(self, engine: str = "windows", piper_model: str = "", rate: int = 0,
                 max_queue: int = 3, on_speak=None, on_done=None, gender: str = "female", volume: int = 100,
                 voice_name: str = "", piper_exe: str = "piper/piper.exe", kokoro_voice: str = "af_heart",
                 speed: float = 1.0):
        self.engine = engine
        self.piper_model = piper_model
        self.rate = rate
        self.on_speak = on_speak      # callback(text) when a line starts playing
        self.on_done = on_done        # callback() when it finishes (clears subtitles)
        self.gender = gender
        self.volume = max(0, min(100, int(volume)))
        self.voice_name = voice_name
        self.piper_exe = piper_exe
        self.kokoro_voice = kokoro_voice
        self.speed = speed
        self._kokoro = None
        self._subtitle = ""
        self.last_spoke = time.time()
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
                self.last_spoke = time.time()
                self._subtitle = text           # shown when the audio starts, not while it's being generated
                print(f"[voice] {text}")
                text = pronounceable(text)
                if self.engine == "windows":
                    self._show_subtitle()
                    self._speak_windows(text)
                elif self.engine == "piper":
                    self._speak_piper(text)
                elif self.engine == "kokoro":
                    self._speak_kokoro(text)
                else:
                    self._show_subtitle()
                    time.sleep(min(6.0, 0.06 * len(text)))   # give viewers time to read it
            except Exception as e:  # noqa: BLE001
                print(f"[voice] error: {e}")
            finally:
                self.last_spoke = time.time()
                if self.on_done and self._q.empty():
                    try:
                        self.on_done()
                    except Exception:  # noqa: BLE001
                        pass
                self._busy.clear()

    def _show_subtitle(self) -> None:
        self.last_spoke = time.time()
        if self.on_speak:
            self.on_speak(self._subtitle)

    def _speak_windows(self, text: str) -> None:
        if sys.platform != "win32":
            time.sleep(min(6.0, 0.06 * len(text)))
            return
        if self.voice_name:
            pick = f"try {{ $s.SelectVoice('{self.voice_name.replace(chr(39), '')}') }} catch {{}}; "
        else:
            hint = "Male" if self.gender.lower() == "male" else "Female"
            pick = f"try {{ $s.SelectVoiceByHints('{hint}') }} catch {{}}; "
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {int(self.rate)}; $s.Volume = {self.volume}; "
            + pick
            + "$s.Speak([Console]::In.ReadToEnd())"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], input=text.encode("utf-8"),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)

    def _speak_kokoro(self, text: str) -> None:
        if self._kokoro is None:
            from kokoro_onnx import Kokoro          # installed by: python -m pokeplay --get-voice kokoro
            from .voices import KOKORO_MODEL, KOKORO_VOICES
            self._kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
        lang = "en-gb" if self.kokoro_voice.startswith("b") else "en-us"
        samples, rate = self._kokoro.create(text, voice=self.kokoro_voice, speed=self.speed, lang=lang)
        import numpy as np                      # comes with kokoro-onnx
        pcm = (np.clip(samples * (self.volume / 100.0), -1.0, 1.0) * 32767).astype("<i2")
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(pcm.tobytes())
            self._show_subtitle()
            _play_wav(path)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def _speak_piper(self, text: str) -> None:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            if os.path.exists(self.piper_exe):
                # Piper's standalone program: no Python packages needed.
                subprocess.run([self.piper_exe, "--model", self.piper_model, "--output_file", path],
                               input=text.encode("utf-8"), capture_output=True, check=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                self._synthesize_with_module(text, path)
            _scale_volume(path, self.volume)
            self._show_subtitle()
            _play_wav(path)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def _synthesize_with_module(self, text: str, path: str) -> None:
        if self._piper_voice is None:
            from piper import PiperVoice  # pip install piper-tts
            if not self.piper_model or not os.path.exists(self.piper_model):
                raise RuntimeError(f"Piper voice model not found: {self.piper_model!r}")
            self._piper_voice = PiperVoice.load(self.piper_model)
        with wave.open(path, "wb") as wav:
            if hasattr(self._piper_voice, "synthesize_wav"):
                self._piper_voice.synthesize_wav(text, wav)
            else:
                self._piper_voice.synthesize(text, wav)


def _scale_volume(path: str, volume: int) -> None:
    """Make a 16-bit WAV file quieter (volume 0-100)."""
    if volume >= 100:
        return
    with wave.open(path, "rb") as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())
    if params.sampwidth != 2:
        return
    samples = array.array("h", frames)
    if sys.byteorder == "big":
        samples.byteswap()
    factor = volume / 100.0
    for i in range(len(samples)):
        samples[i] = int(samples[i] * factor)
    if sys.byteorder == "big":
        samples.byteswap()
    with wave.open(path, "wb") as w:
        w.setparams(params)
        w.writeframes(samples.tobytes())


def _play_wav(path: str) -> None:
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
    elif sys.platform == "darwin":
        subprocess.run(["afplay", path], check=False)
    else:
        subprocess.run(["aplay", "-q", path], check=False)
