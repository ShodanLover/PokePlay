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
    temperature: float = 0.7
    context_tokens: int = 4096
    streamer_name: str = "PokePlay AI"


@dataclass
class VoiceConfig:
    engine: str = "windows"     # windows | piper | none
    piper_model: str = ""
    rate: int = 1
    wait_for_voice: bool = True


@dataclass
class OverlayConfig:
    port: int = 8765


@dataclass
class CommentaryConfig:
    enabled: bool = True
    min_seconds_between: float = 8


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
    data = tomllib.loads(path.read_text(encoding="utf-8"))
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
