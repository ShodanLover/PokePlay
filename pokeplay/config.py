"""Loads config.toml (see config.example.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class EmulatorConfig:
    host: str = "127.0.0.1"
    port: int = 8888
    autosave_minutes: float = 10
    autosave_slot: int = 9


@dataclass
class BrainConfig:
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:4b"
    temperature: float = 0.75
    context_tokens: int = 4096
    streamer_name: str = ""     # leave empty: the AI picks its own name on first launch
    max_seconds_between_thoughts: float = 7   # she stops waiting for her voice so she keeps moving
    # The only thing decided for her; she invents the rest of herself.
    persona_hint: str = "a female AI streamer with a dry, offbeat sense of humor who gets a little unhinged when things go wrong"
    speaking_style: str = ""   # how she talks, in your own words (empty = the built-in style)
    memory_file: str = "memory.json"
    persona_file: str = "persona.json"


@dataclass
class VoiceConfig:
    engine: str = "windows"     # windows | piper | none
    piper_model: str = ""
    rate: int = 1
    gender: str = "female"      # Windows voice: female | male
    volume: int = 85            # her voice volume, 0-100
    voice_name: str = ""        # a specific Windows voice (see: python -m pokeplay --list-voices)
    piper_exe: str = "piper/piper.exe"
    kokoro_voice: str = "af_heart"   # see: python -m pokeplay --list-voices
    speed: float = 1.0               # Kokoro speaking speed (0.8 slower - 1.2 faster)
    wait_for_voice: bool = True


@dataclass
class OverlayConfig:
    port: int = 8765
    twitch_channel: str = ""    # shows this channel's chat on the overlay (display only; never reaches the AI)


@dataclass
class CommentaryConfig:
    enabled: bool = True
    min_seconds_between: float = 8
    max_silence_seconds: float = 12   # if she's been quiet this long, she thinks out loud


@dataclass
class Config:
    emulator: EmulatorConfig = field(default_factory=EmulatorConfig)
    brain: BrainConfig = field(default_factory=BrainConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    commentary: CommentaryConfig = field(default_factory=CommentaryConfig)


def load_config(path: str | Path) -> Config:
    cfg = Config()
    path = Path(path)
    if not path.exists():
        print(f"No {path} found, using defaults (copy config.example.toml to config.toml to customize).")
        return cfg
    # "utf-8-sig" also accepts the invisible marker (BOM) that Notepad/PowerShell often add.
    text = path.read_text(encoding="utf-8-sig")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(
            f"\nThere's a problem in {path}: {e}\n"
            "Easiest fix: delete config.toml and run start.bat again (it makes a fresh copy).\n"
        ) from None
    for section in fields(cfg):
        values = data.get(section.name, {})
        target = getattr(cfg, section.name)
        known = {f.name for f in fields(target)}
        for k, v in values.items():
            if k not in known:
                print(f"Warning: unknown setting [{section.name}] {k}")
                continue
            setattr(target, k, v)
    return cfg
