"""Voice helpers: list Windows voices, download free Piper voices, update config.toml.

    python -m pokeplay --list-voices          show every voice you can use
    python -m pokeplay --get-voice amy        download a Piper voice and switch to it
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en"
PIPER_EXE_ZIP = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
KOKORO_FILES = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_MODEL = "voices/kokoro-v1.0.onnx"
KOKORO_VOICES = "voices/voices-v1.0.bin"

# Kokoro: much more natural free voices. name -> description
KOKORO_SPEAKERS = {
    "af_heart": "American, warm and expressive (best overall)",
    "af_bella": "American, lively",
    "af_nicole": "American, soft and close (ASMR-ish)",
    "af_sarah": "American, clear and friendly",
    "af_sky": "American, light",
    "af_nova": "American, bright",
    "af_jessica": "American, casual",
    "af_river": "American, relaxed",
    "af_aoede": "American, smooth",
    "af_kore": "American, steady",
    "af_alloy": "American, neutral",
    "bf_emma": "British, warm",
    "bf_isabella": "British, polished",
    "bf_alice": "British, crisp",
    "bf_lily": "British, gentle",
}

# Free Piper voices (female, English). Short name -> (folder path, file stem, description)
PIPER_VOICES = {
    "amy":     ("en_US/amy/medium", "en_US-amy-medium", "American, warm and clear"),
    "lessac":  ("en_US/lessac/high", "en_US-lessac-high", "American, expressive (high quality)"),
    "kristin": ("en_US/kristin/medium", "en_US-kristin-medium", "American, bright"),
    "hfc":     ("en_US/hfc_female/medium", "en_US-hfc_female-medium", "American, casual"),
    "ljspeech": ("en_US/ljspeech/high", "en_US-ljspeech-high", "American, calm (high quality)"),
    "jenny":   ("en_GB/jenny_dioco/medium", "en_GB-jenny_dioco-medium", "British, friendly"),
    "cori":    ("en_GB/cori/high", "en_GB-cori-high", "British, crisp (high quality)"),
    "alba":    ("en_GB/alba/medium", "en_GB-alba-medium", "Scottish"),
}


def windows_voices() -> list[str]:
    if sys.platform != "win32":
        return []
    script = ("Add-Type -AssemblyName System.Speech; "
              "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | "
              "ForEach-Object { $_.VoiceInfo.Name + ' | ' + $_.VoiceInfo.Gender + ' | ' + $_.VoiceInfo.Culture }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def list_voices() -> int:
    print("Windows voices (engine = \"windows\", set voice_name to the name):")
    voices = windows_voices()
    for v in voices:
        print("   ", v)
    if not voices:
        print("    (none found, or not on Windows)")
    print("\nKokoro voices (most natural, recommended). Preview:  python -m pokeplay --test-voice kokoro:af_heart")
    print("                                             Use one:  python -m pokeplay --get-voice kokoro:af_heart")
    for name, desc in KOKORO_SPEAKERS.items():
        print(f"    kokoro:{name:12s} {desc}")
    print("\nPiper voices (smaller, more robotic). Install one with:  python -m pokeplay --get-voice NAME")
    for name, (_, stem, desc) in PIPER_VOICES.items():
        installed = " [installed]" if (Path("voices") / f"{stem}.onnx").exists() else ""
        print(f"    {name:9s} {desc}{installed}")
    return 0


def _download(url: str, dest: Path) -> None:
    print(f"  downloading {dest.name} ...")
    with urllib.request.urlopen(url, timeout=120) as resp:
        dest.write_bytes(resp.read())


def ensure_piper_exe(folder: str = "piper") -> Path | None:
    """Piper's standalone Windows program (no Python packages needed)."""
    exe = Path(folder) / "piper.exe"
    if exe.exists() or sys.platform != "win32":
        return exe if exe.exists() else None
    print("Getting the Piper voice program (one time, ~20 MB)...")
    with urllib.request.urlopen(PIPER_EXE_ZIP, timeout=300) as resp:
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(".")          # the zip contains a "piper/" folder
    return exe if exe.exists() else None


def set_config_values(path: str, section: str, values: dict) -> None:
    """Change settings in config.toml in place (keeps your other settings and comments)."""
    p = Path(path)
    if not p.exists():
        example = Path("config.example.toml")
        p.write_text(example.read_text(encoding="utf-8-sig") if example.exists() else "", encoding="utf-8")
    text = p.read_text(encoding="utf-8-sig")
    for key, value in values.items():
        rendered = f'"{value}"' if isinstance(value, str) else str(value).lower() if isinstance(value, bool) else str(value)
        sec = re.search(rf"^\[{re.escape(section)}\][^\[]*", text, flags=re.M)
        if sec is None:
            text += f"\n[{section}]\n{key} = {rendered}\n"
            continue
        block = sec.group(0)
        if re.search(rf"^{key}\s*=", block, flags=re.M):
            new_block = re.sub(rf"^{key}\s*=.*$", f"{key} = {rendered}", block, count=1, flags=re.M)
        else:
            new_block = block.rstrip("\n") + f"\n{key} = {rendered}\n\n"
        text = text.replace(block, new_block, 1)
    p.write_text(text, encoding="utf-8")


def install_kokoro() -> bool:
    """Install the Kokoro voice engine (Python package + ~350 MB of model files)."""
    import importlib.util
    if importlib.util.find_spec("kokoro_onnx") is None:
        print("Installing the Kokoro voice engine (one time)...")
        cmd = [sys.executable, "-m", "pip", "install", "kokoro-onnx"]
        if sys.version_info >= (3, 14):
            cmd.append("--ignore-requires-python")   # it works on 3.14; the package is just labeled conservatively
        if subprocess.run(cmd).returncode != 0:
            print("Couldn't install kokoro-onnx. Paste the error above to get help.")
            return False
    os.makedirs("voices", exist_ok=True)
    try:
        for path in (KOKORO_MODEL, KOKORO_VOICES):
            if not Path(path).exists():
                print("(this is a big download, about 350 MB total)" if path == KOKORO_MODEL else "", end="")
                _download(f"{KOKORO_FILES}/{Path(path).name}", Path(path))
    except OSError as e:
        print(f"Download failed: {e}")
        return False
    return True


def parse_kokoro(name: str) -> str | None:
    """'kokoro' or 'kokoro:af_bella' -> speaker name (or None if not a Kokoro voice)."""
    if not name.lower().startswith("kokoro"):
        return None
    speaker = name.split(":", 1)[1] if ":" in name else "af_heart"
    return speaker if speaker in KOKORO_SPEAKERS else ""


def download_voice(name: str) -> Path | None:
    """Make sure a Piper voice (and the Piper program) is on disk. Returns the model path."""
    name = name.lower()
    if name not in PIPER_VOICES:
        print(f"Unknown voice '{name}'. Choose one of: {', '.join(PIPER_VOICES)}")
        return None
    folder, stem, _desc = PIPER_VOICES[name]
    os.makedirs("voices", exist_ok=True)
    model = Path("voices") / f"{stem}.onnx"
    try:
        if not model.exists():
            _download(f"{BASE}/{folder}/{stem}.onnx?download=true", model)
        cfg = model.with_suffix(".onnx.json")
        if not cfg.exists():
            _download(f"{BASE}/{folder}/{stem}.onnx.json?download=true", cfg)
        ensure_piper_exe()
    except OSError as e:
        print(f"Download failed: {e}")
        return None
    return model


def get_voice(name: str, config_path: str = "config.toml") -> int:
    speaker = parse_kokoro(name)
    if speaker is not None:
        if not speaker:
            print(f"Unknown Kokoro voice. Choose one of: {', '.join(KOKORO_SPEAKERS)}")
            return 1
        if not install_kokoro():
            return 1
        set_config_values(config_path, "voice", {"engine": "kokoro", "kokoro_voice": speaker})
        print(f"Done! She now uses Kokoro '{speaker}' ({KOKORO_SPEAKERS[speaker]}). Restart PokePlay to hear it.")
        return 0
    model = download_voice(name)
    if model is None:
        return 1
    desc = PIPER_VOICES[name.lower()][2]
    set_config_values(config_path, "voice", {"engine": "piper", "piper_model": model.as_posix()})
    print(f"Done! She now uses the '{name}' voice ({desc}). Restart PokePlay to hear it.")
    return 0
