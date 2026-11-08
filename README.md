# PokePlay

An AI that plays **Pokémon FireRed** live on Twitch and talks through what it's doing.
It runs **completely free** on your own PC: no paid AI services and no subscriptions.

```
┌────────────┐  memory + buttons  ┌───────────────────┐  words  ┌────────────┐
│ mGBA        │ ◀────────────────▶ │ PokePlay (Python) │ ──────▶ │ Voice (TTS) │──┐
│ + Lua bridge│                    │  ├ autopilot      │         └────────────┘  │
└────────────┘                     │  └ AI brain ◀──▶ Ollama (local AI model)    ▼
      │                            └───────────────────┘ ──▶ overlay page ──▶  OBS ──▶ Twitch
      └───────────────────────────── game window ─────────────────────────────▶
```

## How it works

- **mGBA** runs the game. A small Lua script (`lua/pokeplay_bridge.lua`) lets PokePlay read the
  game's memory and press buttons.
- PokePlay **reads the game's memory directly**: map, position, walls, doors, NPCs, your team's HP and
  moves, items, badges and story progress. Nothing is guessed from screenshots, so a small AI model
  can play.
- **The autopilot (plain code) does the hard parts:** walking, pathfinding around walls and ledges,
  picking the strongest move in battle (using real type matchups), switching when a Pokémon faints,
  and clicking through dialogue.
- **The AI brain** is a free local model run by Ollama. In the overworld it chooses what to do next from
  a list (*"Go through the door to Professor Oak's Lab"*, *"Talk to the person at (5,3)"*,
  *"Train in the tall grass"*…) and says one line out loud explaining why. It also reacts to battles,
  level-ups and evolutions.
- A built-in **walkthrough** works out the current goal from the game's story flags, so the AI always
  knows what it's working toward.
- An **overlay page** shows the AI's thoughts, goal, team HP bars and recent events, ready for OBS.

The ROM's own data (Pokémon names, moves, type chart) is read from **your ROM** while it runs.
No game data is stored in this repo.

---

## Setup (Windows)

You need: a **Pokémon FireRed (US) ROM dumped from your own cartridge**, and about 5 GB of disk space.

### 1. Install the software (all free)

| Program | Where | Notes |
|---|---|---|
| **Python 3.12** | python.org/downloads | During install, tick **"Add python.exe to PATH"** |
| **mGBA 0.10 or newer** | mgba.io/downloads.html | The emulator |
| **Ollama** | ollama.com/download | Runs the AI model on your graphics card |
| **OBS Studio** | obsproject.com | Streaming software |
| **Git** (optional) | git-scm.com | To download/update this project. You can also use GitHub's "Download ZIP" |

### 2. Download the AI model

Open **Command Prompt** and run:

```bash
ollama pull qwen3:4b
```

This is about 2.5 GB. It fits comfortably on a 6 GB card like your **GTX 1660** with room left for OBS.

### 3. Get PokePlay

```bash
git clone https://github.com/ShodanLover/PokePlay.git
```

```bash
cd PokePlay
```

```bash
copy config.example.toml config.toml
```

Open `config.toml` in Notepad and change `streamer_name` to whatever you want the AI to be called.

### 4. Set up mGBA

1. Open mGBA and load your FireRed ROM (**File → Load ROM**).
2. **Important:** go to **Tools → Settings → Emulation** (or **Interface** on some versions) and **untick
   "Pause when inactive"**. Otherwise the game freezes when you click on OBS.
3. **Play the opening yourself** up to the point where you're standing in your bedroom: Oak's speech
   and naming yourself and your rival. Then save in-game (START → SAVE). The bot takes over from there.
4. Load the bridge: **Tools → Scripting…**, then in that window **File → Load script…** and pick
   `lua/pokeplay_bridge.lua` from the PokePlay folder.
   The scripting window should say: `PokePlay bridge listening on 127.0.0.1:8888`.

> You have to load the script again each time you restart mGBA.

### 5. Test the connection

With the game running and the script loaded:

```bash
python -m pokeplay --inspect
```

You should see your location, your team and a little ASCII map of the area. If that works,
everything is wired up correctly.

### 6. Start the AI

```bash
python -m pokeplay
```

You can also just double-click **`start.bat`**. The AI says hello and starts playing. Press **Ctrl+C** in the window to stop it.
It also makes an mGBA save state in slot 9 every 10 minutes, as a backup.

### 7. Set up OBS for Twitch

1. **Settings → Stream**: Service **Twitch**, then **Connect Account** (or paste your stream key).
2. **Settings → Output**: Encoder **NVIDIA NVENC H.264** (your GTX 1660 has a dedicated video chip for
   this, so streaming barely slows the AI). Bitrate around **4500 Kbps**.
3. **Settings → Video**: Base and Output **1920x1080**, 30 or 60 FPS.
4. Add sources to your scene:
   - **Window Capture** → the mGBA window. Make it big on the left (the GBA screen is 3:2). In mGBA, use
     **View → Frame size → 4x** and right-click the source in OBS → **Scale Filtering → Point**
     so the pixels stay sharp.
   - **Browser** source → URL `http://127.0.0.1:8765`, Width **1920**, Height **1080**. The panel
     sits on the right side.
   - **Audio**: OBS's **Desktop Audio** picks up both the game and the AI's voice automatically.
5. Hit **Start Streaming**.

### Better voice (optional, still free)

The default Windows voice works but sounds robotic. **Piper** sounds much more natural:

```bash
pip install piper-tts
```

Download a voice (both the `.onnx` and `.onnx.json` files) from
huggingface.co/rhasspy/piper-voices. For example `en/en_US/lessac/medium`, or `en_US-ryan-high` for
a more energetic voice. Put them in a `voices` folder, then in `config.toml`:

```toml
[voice]
engine = "piper"
piper_model = "voices/en_US-lessac-medium.onnx"
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Could not connect to mGBA` | Load `lua/pokeplay_bridge.lua` in **Tools → Scripting**, and make sure the game is running (not paused) |
| `game code is ...` error | PokePlay currently supports **FireRed US** only (game code BPRE) |
| Warning about **v1.1** | Some FireRed carts are revision 1.1. The memory addresses here are for v1.0, so battles or menus may misbehave. Tell us and we'll add v1.1 support |
| `Can't reach Ollama` | Start the Ollama app (it lives in the system tray) |
| `Model 'qwen3:4b' isn't downloaded` | Run `ollama pull qwen3:4b` |
| AI is slow to decide | Normal on a 6 GB card: expect a few seconds per decision. Set `wait_for_voice = false` to overlap talking and moving |
| Game freezes when OBS is focused | Untick **Pause when inactive** in mGBA settings |
| The bot is stuck in a loop | It tracks how often it picks each option and avoids repeats, but sometimes you'll need to help. Stop it (Ctrl+C), move a few steps yourself, and restart. Its progress lives in the game, so nothing is lost |

## What it can and can't do yet (v0.1)

**Works:** walking anywhere on a map, doors, stairs, map exits, ledges, talking to people (including across
shop counters), training in tall grass, wild and trainer battles with smart move choice, switching
when a Pokémon faints, running from bad wild battles, reading dialogue, story-aware goals for all 8 gyms,
narration, and the overlay.

**Not yet (planned):**
- Using menus on purpose: healing items, catching Pokémon, teaching HMs (Cut/Surf/Strength), and
  using HMs in the field. This is the next big step; the game needs Cut after the third gym.
- Shopping at Poké Marts.
- Choosing which move to forget when learning a new one. Right now it keeps its old moves.
- Puzzles (Rocket Hideout spinners, Silph Co. teleporters, boulder pushing).
- Twitch chat interaction (viewers giving hints or voting).
- FireRed v1.1 and LeafGreen.

## Project layout

```
lua/pokeplay_bridge.lua     mGBA script: memory reads + button presses over a local socket
pokeplay/
  emulator.py               talks to the Lua bridge
  addresses.py              FireRed memory addresses (from the pret/pokefirered decompilation)
  game.py                   reads party, map, NPCs, bag, battle state from memory
  pathfinding.py            BFS pathfinding (walls, ledges, water, NPCs)
  overworld.py              builds the action list and carries out actions
  battle.py                 battle autopilot (move scoring with type matchups)
  objectives.py             story-aware goals
  brain.py                  local AI via Ollama: decisions + commentary
  narrator.py               text-to-speech (Windows voice or Piper)
  overlay/                  OBS overlay web page
  agent.py                  main loop
tests/                      run with: pip install pytest lupa && python -m pytest
```

## Credits

Memory layouts and addresses come from the [pret/pokefirered](https://github.com/pret/pokefirered)
decompilation project. Pokémon is © Nintendo / Game Freak / Creatures. This project contains no
game data. You need your own legally obtained ROM.
