# PokePlay

An AI that plays **Pokémon FireRed** live on Twitch and thinks out loud while she plays.
She picks her own name and personality, names her own character, rival and Pokémon, and
everything she says is generated live. Nothing is scripted except a few safety rules.
It runs **completely free** on your own PC: no paid AI services and no subscriptions.

```
┌────────────┐  memory + buttons  ┌───────────────────┐  words  ┌────────────┐
│ mGBA        │ ◀────────────────▶ │ PokePlay (Python) │ ──────▶ │ Voice (TTS) │──┐
│ + Lua bridge│                    │  ├ game mechanics │         └────────────┘  │
└────────────┘                     │  └ AI brain ◀──▶ Ollama (local AI model)    ▼
      │                            └───────────────────┘ ──▶ overlay page ──▶  OBS ──▶ Twitch
      └───────────────────────────── game window ─────────────────────────────▶
```

## How it works

- **mGBA** runs the game. A small Lua script (`lua/pokeplay_bridge.lua`) lets PokePlay read the
  game's memory and press buttons.
- **She plays as a true first-timer.** The AI is told she has never seen Pokémon. She gets **no
  walkthrough and no game knowledge**: doors and paths are unknown until she goes through them, people
  are just "a person" until she talks to them, and in battle she sees only what the screen shows (move
  names, types, PP, the opponent's HP bar). She learns matchups by noticing "It's super effective!".
- **She makes every decision**: where to go, who to talk to, which move to use, when to run, who to send
  out when a Pokémon faints, and what to name her character, her rival and her Pokémon.
- **Code only does the mechanics**: walking a route once she has chosen where to go, working the menus
  for the move she picked, and pressing A through text.
- **She remembers.** `memory.json` holds her journal (written by her), things she has noticed, places
  she has been, where doors lead, what people told her, her current goal, her mood and run stats. It
  survives restarts, so a months-long run builds on itself. She condenses her own journal when it gets long.
- **She is her own person.** On first launch she invents her name, personality and catchphrase
  (`persona.json`). The only thing decided for her is "a female AI with a chaotic, slightly unhinged,
  dramatic personality" (you can change `persona_hint` in `config.toml`). The only fixed rules are
  safety rules: family-friendly, within Twitch guidelines, no hate or harassment.
- **Subtitles:** everything she says is shown word-for-word. The AI writes her words and the voice
  reads them, so captions are free and exact.
- An **overlay** shows her thoughts, her own goal and mood, her team, recent events, and run stats
  (day, hours, steps, places found, battles won and lost).

**One honest limit:** the AI model learned from the internet, so somewhere inside it does know
Pokémon. She's told to ignore that and only trust what she learns on stream, but a small model will
occasionally "just know" something.

The ROM's own data (Pokémon names, moves, type chart) is read from **your ROM** while it runs.
No game data is stored in this repo.

---

## Setup (Windows)

> **Shortcut:** download this repo (green **Code** button → **Download ZIP**), unzip it, and double-click
> **`setup.bat`**. It installs Python, mGBA, Ollama and OBS, downloads the AI model, and creates your
> `config.toml`. Then skip to step 4 below. The manual steps are here if anything goes wrong.

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

You don't need to name her: she chooses her own name the first time she starts.

### 4. Set up mGBA

1. Open mGBA and load your FireRed ROM (**File → Load ROM**).
2. **Important:** go to **Tools → Settings → Emulation** (or **Interface** on some versions) and **untick
   "Pause when inactive"**. Otherwise the game freezes when you click on OBS.
3. Leave the game on the **title screen**. She plays from the very beginning, including Oak's speech,
   and types her own player name, rival name and Pokémon nicknames on the in-game keyboard.
   (If you already have a save file, she'll press CONTINUE.)
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

You can also just double-click **`start.bat`**. She says hello and starts playing. Press **Ctrl+C** in the window to stop her.

### Leaving her running while you're away

Use **`run_forever.bat`** instead of `start.bat`. It restarts her automatically if anything crashes.
Also:
- She keeps the PC awake while running, writes everything to `logs/`, and every 10 minutes saves
  a backup save state (slot 9) plus her memory.
- If Ollama hiccups, she waits and retries instead of acting randomly.
- **Windows Update** can restart your PC overnight. Go to Settings → Windows Update and either pause
  updates or set **Active hours** to cover when she streams.
- In **OBS → Settings → Advanced**, make sure **Automatically Reconnect** is on. Twitch ends a single
  broadcast after 48 hours; OBS reconnects and starts a new one.
- Make Ollama and OBS start with Windows if you want her to survive a reboot.
- **If mGBA itself crashes**, the bridge script has to be loaded again, and current mGBA releases (0.10)
  can't do that automatically. The newer mGBA **development builds** (mgba.io → Downloads →
  Development builds) have an **autorun scripts** option under Tools → Scripting. If you use one, add
  `pokeplay_bridge.lua` there. mGBA crashes are rare; the Python side, which is more likely to hiccup,
  restarts by itself.
- **Back up `memory.json` and `persona.json`** now and then. They are her whole history.

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
   - **Browser** source → URL `http://127.0.0.1:8765/subtitles`, Width **1920**, Height **1080**, placed on
     top of everything. These are her live subtitles.
   - **Browser** source → URL `http://127.0.0.1:8765/avatar`, Width **1920**, Height **1080**. This is her
     animated pixel-art avatar in the bottom-right corner (blinks, talks, grins, glitches).
   - **Audio**: OBS's **Desktop Audio** picks up both the game and her voice. To make her louder than
     the game, see "Balancing her voice and the game" below.

   Make sure all the Browser sources are **above** the mGBA window in the Sources list (the top of the
   list is drawn on top). If one doesn't show, right-click it → **Refresh**.

### Balancing her voice and the game

Turn the **game** down rather than her up:
1. While mGBA and PokePlay are running, right-click the **speaker icon** in the Windows taskbar →
   **Open volume mixer**.
2. Set **mGBA** to about **25-35%**. Leave **Windows PowerShell** (her Windows voice) or **Python**
   (her Piper voice) at **100%**.

OBS's Desktop Audio records these per-app levels, so viewers hear the same balance you do. Her voice
volume itself is `volume` under `[voice]` in `config.toml` (0-100).
5. Hit **Start Streaming**.

### Better voice (optional, still free)

The default Windows voice works but sounds robotic. **Piper** sounds much more natural:

```bash
pip install piper-tts
```

Download a voice (both the `.onnx` and `.onnx.json` files) from
huggingface.co/rhasspy/piper-voices. Female English voices include `en/en_US/amy/medium`,
`en/en_US/lessac/medium` and `en/en_GB/jenny_dioco/medium`. Put them in a `voices` folder, then in `config.toml`:

```toml
[voice]
engine = "piper"
piper_model = "voices/en_US-amy-medium.onnx"
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

**Works:** starting a new game, typing her own names, walking anywhere on a map, doors, stairs, map
exits, ledges, talking to people (including across shop counters), walking in tall grass, choosing her
own moves in battle, running away, choosing who to send out, learning matchups from battle messages,
reading dialogue, setting her own goals, long-term memory, narration, subtitles, stats, and the overlay.

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
  battle.py                 battle menus; she picks, it presses; learns from battle messages
  memory.py                 her long-term memory (journal, places, people, lessons, stats)
  brain.py                  local AI via Ollama: decisions + commentary
  narrator.py               text-to-speech (Windows voice or Piper)
  naming.py                 types names on the in-game keyboard
  overlay/                  OBS overlay + subtitles web pages
  agent.py                  main loop
tests/                      run with: pip install pytest lupa && python -m pytest
```

## Credits

Memory layouts and addresses come from the [pret/pokefirered](https://github.com/pret/pokefirered)
decompilation project. Pokémon is © Nintendo / Game Freak / Creatures. This project contains no
game data. You need your own legally obtained ROM.
