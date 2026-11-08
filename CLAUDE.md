# PokePlay: context for Claude

This file is read automatically at the start of every Claude Code session in this folder. It holds
everything decided and built so far, so a new session can pick up right where the last one left off.
**Keep it up to date** when decisions change or major work is done.

## What this project is

An AI streamer that plays **Pokémon FireRed** live on **Twitch**, fully autonomously, and thinks out
loud with a voice, subtitles and an animated avatar. The owner wants to watch an AI play the entire
game, start to finish, **as a true first-timer**, no matter how long it takes (months is fine).

## The owner's decisions (follow these)

- **Cost: $0.** Everything runs locally and free: Ollama local model, Kokoro voice, mGBA, OBS.
  No paid APIs.
- **Fully autonomous.** It runs unattended while the owner is away. No human input during play.
- **No Twitch chat hints.** Chat must not influence the game. (Chat moderation is the owner's job.)
- **First-timer mode.** She gets **no game knowledge**: no walkthrough, no destination names until
  visited, no type chart. She learns only from what she sees and is told on stream (her journal).
- **Nothing scripted except safety rules.** All speech is generated live. The only fixed rules are
  safety: family-friendly, Twitch guidelines, no hate or harassment.
- **She names herself when she makes her character.** The name she types on the game's player naming
  screen becomes her name (`persona.json`, not in git), replacing the one she invented on first launch
  (currently **PikaPunch**). Only a new game reaches that screen. `streamer_name` in `config.toml` must stay
  empty, or it overrides her choice. New self-chosen names are blocked if they're Pokémon-derived.
- **Personality:** offbeat, dry humor, gets a little unhinged when things go wrong, but **not cringe**.
  No "I'm so chaotic!", no asterisk actions, no exclamation spam, no forced catchphrases (the catchphrase
  only goes in the stream greeting). Style rules are in `brain.py` (`DEFAULT_STYLE`), and the
  `speaking_style` config overrides them.
- **Voice:** Kokoro **`af_heart`** (installed via `python -m pokeplay --get-voice kokoro:af_heart`).
  Voice volume ~80-85; the game volume is turned down in the Windows volume mixer.
- **She must be able to finish the whole game:** full menu control (bag, TM case, catching, shops,
  HMs, move forgetting) was built for this.
- **Explain things in plain language** with exact step-by-step commands. The owner is not a programmer.

## Owner's setup

- Windows, project at **`D:\PokePlay`** (cloned from github.com/ShodanLover/PokePlay, branch `main`).
- GPU: **GTX 1660 (6 GB VRAM)**, so the model is **`qwen3:4b`** via Ollama. Bigger models won't fit
  alongside OBS.
- **Python 3.14** (`python` on PATH). kokoro-onnx was installed with `--ignore-requires-python`
  (it's labeled <3.14 but works).
- ROM: FireRed US, game code **BPRE**; addresses assume **v1.0** (the bot warns if it's v1.1).
- mGBA 0.10.x; the bridge script `lua/pokeplay_bridge.lua` is loaded manually via
  Tools → Scripting → File → Load script (0.10 can't autoload; dev builds have "autorun scripts").
- Run with **`run_forever.bat`** (auto-restarts) or `start.bat`. Logs go to `logs/pokeplay-DATE.log`.

## Current status

- All code is written and pushed. **42 tests pass** (`python -m pytest`; needs `pip install pytest lupa`).
- **Never verified against the real game yet.** All memory addresses come from the pret/pokefirered
  decompilation, and the logic is tested with simulated memory. The first real runs showed she walks,
  talks, names things and explores. The menus (Bag, TM Case, catching, shops, move forgetting) are
  the least proven and the most timing-sensitive.
- **OBS:** PokePlay has its own OBS scene collection and profile, both named **PokePlay**, so the owner's
  separate `Christmas 24-7` YouTube stream stays untouched. Don't add PokePlay changes to the Christmas files.
  Twitch sign-in on the PokePlay profile is done by the owner.

## OBS setup (target layout)

- Settings: Stream → Twitch (Connect Account). Output → Simple, **NVIDIA NVENC H.264**, 4500 Kbps.
  Video → 1920x1080, 30 FPS. Advanced → **Automatically Reconnect** on.
- Sources, top to bottom (top is drawn on top):
  1. **Avatar**: Browser, `http://127.0.0.1:8765/avatar`, 1920x1080
  2. **Subtitles**: Browser, `http://127.0.0.1:8765/subtitles`, 1920x1080
  3. **Info Panel**: Browser, `http://127.0.0.1:8765`, 1920x1080
  4. **Game**: Window Capture of mGBA, Capture Method "Windows 10 (1903 and up)" if it's black,
     Scale Filtering → Point, large on the left (the info panel occupies the right ~600 px; the avatar sits
     bottom-right; subtitles are bottom-center).
- The browser sources only show content while the bot is running (its overlay server is on port 8765).
  Right-click → Refresh if one is blank.
- Audio: Desktop Audio captures everything. Volume mixer: mGBA ~25-35%, Python (Kokoro voice) 100%.
- OBS stores scenes in `%APPDATA%\obs-studio\basic\scenes\*.json` and profiles in
  `%APPDATA%\obs-studio\basic\profiles\`. Close OBS before editing those files.

## How it works (code map)

```
lua/pokeplay_bridge.lua   mGBA script: TCP server on 127.0.0.1:8888 (READ, PRESS, SAVESTATE...)
pokeplay/
  emulator.py             client for the Lua bridge
  addresses.py            FireRed v1.0 RAM/ROM addresses + struct offsets (from the decomp)
  game.py                 reads party, map grid, NPCs, warps, bag, battle state; ROM data tables
  pathfinding.py          BFS over the map grid (walls, ledges, water, NPCs)
  overworld.py            builds her action options (doors, exits, people, grass, water, boulders,
                          START menu) with first-timer labels; walks/executes them
  battle.py               battle menus: she picks Fight/move, Bag, Switch, Run; learns matchups
                          from "super effective" messages; answers battle yes/no questions
  menus.py                generic menu reader: list menus (bag/TM case/shop) via ListMenu tasks,
                          box menus (start, USE/GIVE/TOSS, party actions, multichoice, yes/no)
                          via gTasks + sMenu; never presses A if the cursor can't be confirmed
  naming.py               types names on the in-game keyboard
  memory.py               memory.json: journal, lessons, places, door links, people, goal, mood, stats
  brain.py                Ollama client: decisions, comments, reflection, journal condensing,
                          persona creation, naming; FIRST_TIMER + SAFETY + DEFAULT_STYLE prompts;
                          clean_spoken() strips "Name:" labels; repeat filter
  narrator.py             TTS on a background thread: windows | piper | kokoro | none
  voices.py               --list-voices / --get-voice / --test-voice helpers (Kokoro + Piper)
  overlay/                local web server (port 8765): overlay.html, subtitles.html, avatar.html
                          + avatar.js (original pixel-art girl: pink hair, headset, blinks/talks/glitches)
  agent.py                main loop: mode detection -> menu turn / battle / dialog / overworld turn;
                          commentary thread incl. idle "thinking out loud" after max_silence_seconds
```

Files that are personal and NOT in git: `config.toml`, `persona.json`, `memory.json`, `voices/`,
`piper/`, `logs/`. Back up `persona.json` and `memory.json`, since they are her identity and history.

Useful commands:
- `python -m pokeplay --inspect`: prints what the bot sees (connect test; needs mGBA + bridge running)
- `python -m pokeplay --test-voice`: hear her current voice
- `python -m pokeplay --list-voices`

## Known limits / ideas not done yet

- The small model sometimes "knows" Pokémon facts (it learned them from the internet); that's accepted.
- Puzzle areas (spin tiles, teleporters, boulder puzzles) rely on her experimenting.
- Possible next steps: tune from real logs (especially menus and timing); "previously on" recap at
  stream start; an OBS scene collection file to import; FireRed v1.1 / LeafGreen address sets.

## Working on this repo

- Commit to `main` and push when the owner asks or when a change is done and tested
  (`git pull` first). Run `python -m pytest` and `python -m pyflakes pokeplay tests` before committing.
- The owner pulls updates with `git pull` in `D:\PokePlay`.
