# Pokémon AI (Syntax Error 26)

An immersive 3D Pokémon adventure built with Godot 4 and powered by an autonomous Python AI and LLM bridge server. Features companion bonding dialogue, tactical combat decision-making, wild habitat encounters, interactive quests, and a complete day/night cycle.

---

## Quick Start & Installation Guide

> **🎉 Everything is Bundled in the Release!**
> When you download your operating system's package from **[Releases](https://github.com/Chakshan-Arora/PokemonAI/releases)**, `server.py`, all backend AI models, and 1-click launchers are **already included inside the same zip**! You do not need to clone the repository or download source code separately.

---

### Step 1: Download the Release for Your Computer

Go to **[Releases](https://github.com/Chakshan-Arora/PokemonAI/releases)** and download your platform's package:

| Download Package | Included Contents | Launch Method |
| :--- | :--- | :--- |
| **`PokemonAI_Windows.zip`** | `PokemonAI.exe`<br>`Play_PokemonAI.bat`<br>`run_server.bat`<br>`server.py` + `src/` | **Option A (1-Click):** Double-click `Play_PokemonAI.bat`<br>*(Starts server + game together)*<br><br>**Option B:** Double-click `run_server.bat`, then double-click `PokemonAI.exe` |
| **`PokemonAI_macOS.zip`** | `PokémonAI.app`<br>`run_server.sh`<br>`server.py` + `src/` | 1. Open Terminal in folder and run `./run_server.sh`<br>2. Double-click `PokémonAI.app` |
| **`PokemonAI_Linux.zip`** | `PokemonAI.x86_64`<br>`run_server.sh`<br>`server.py` + `src/` | 1. Run `./run_server.sh`<br>2. Run `./PokemonAI.x86_64` |
| **`PokemonAI_Server.zip`** *(272 KB)* | `server.py`<br>`src/`<br>`run_server.bat`<br>`run_server.sh` | Standalone server package for headless hosts, VPS, or running backend separately |

---

### Step 2: Install Requirements for `server.py`

Make sure **Python 3.9 or higher** is installed. In the extracted folder:

#### Windows (Command Prompt / PowerShell):
```cmd
pip install -r requirements.txt
```

#### macOS / Linux (Terminal):
```bash
pip install -r requirements.txt
```

> **Zero-Dependency Note:** `server.py` includes a pure standard-library fallback. Even if `pip install` is skipped, the server and offline autonomous AI will still start and run!

---

### Step 3: Run the Server & Play!

#### Windows:
Double-click **`Play_PokemonAI.bat`** (or run `run_server.bat`, then launch `PokemonAI.exe`).

#### macOS / Linux:
In terminal:
```bash
# Terminal 1: Start server
./run_server.sh

# Terminal 2: Launch game
# macOS: open PokémonAI.app
# Linux: ./PokemonAI.x86_64
```

---

### (Optional) Cloud LLM API Keys
The game runs offline by default using the built-in autonomous heuristic model. If you want to connect live cloud LLM reasoning (Gemini or OpenAI), create a `.env` file in the folder:
```env
# Google Gemini (Recommended for low latency)
GEMINI_API_KEY=your_gemini_api_key_here
POKEMON_AI_PROVIDER=gemini
POKEMON_AI_MODEL=gemini-2.5-flash

# Or OpenAI
# OPENAI_API_KEY=your_openai_api_key_here
# POKEMON_AI_PROVIDER=openai
# POKEMON_AI_MODEL=gpt-4o-mini
```

---

## In-Game Controls

| Action | Keyboard / Mouse |
| :--- | :--- |
| **Movement** | `W`, `A`, `S`, `D` / Arrow Keys |
| **Camera Rotation** | Right Mouse Button + Drag / Mouse Movement |
| **Interact / Talk** | `E` or `Space` (near NPCs, signs, items) |
| **Companion Chat** | Click the Companion dialogue button on the HUD |
| **Open Menu / Inventory** | `Tab` / `ESC` |
| **Battle Actions** | Mouse Click on Fight, Items, Switch, or Run |

---

## Key Features

- **Autonomous Companion AI**: Your partner Pokémon learns your personality, dynamically tracks affection and trust, and participates in real-time conversations.
- **Intelligent Battle Engine**: Turn-based combat with type advantages, critical hits, status effects, and tactical AI opponents.
- **Dynamic 3D World**: Diverse habitats (Meadows, Forests, Mountains, Ruins) with day/night lighting cycles and time-based Pokémon spawns.
- **Authoritative Save System**: Atomic game state serialization to keep your team, inventory, currency, and quest progression safe.
- **Zero-Dependency Resilience**: Automatic offline fallback keeps all features functioning smoothly even without an active internet connection.

---

## Running Automated Tests

To run the full suite of 810 unit and integration tests:

```bash
pytest
```
Expected output:
```text
============================= 810 passed in 2.15s ==============================
```

---

## Project Structure

```text
PokemonAI/
├── server.py                 # REST API bridge for LLM companion & combat decisions
├── run_server.bat            # Windows 1-click server launcher
├── run_server.sh             # macOS/Linux 1-click server launcher
├── requirements.txt          # Python dependencies
├── export_backend_data.py    # Synchronizes Python models with Godot JSON schemas
│
├── Godot/syntax-error-26/    # Godot 4 3D Game Project
│   ├── scenes/               # World, Battle, UI, and Starter Choice scenes
│   ├── scripts/              # GDScript game systems and LLMClient autoload
│   ├── assets/               # 3D models, textures, battle backgrounds, and audio
│   └── project.godot         # Godot project configuration & export presets
│
├── src/                      # Authoritative Python game logic
│   ├── ai/                   # Companion dialogue, battle decision providers, & perception
│   ├── models/               # Pokémon, Battle, Inventory, Quests, & SaveManager
│   └── data/                 # Species, attacks, habitats, items, & type chart
│
├── tests/                    # 810 automated pytest suites
└── build/                    # Exported distribution binaries (Windows, macOS, Linux)
```
