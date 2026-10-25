# Pokémon AI (Syntax Error 26)

An immersive 3D Pokémon adventure built with Godot 4 and powered by an autonomous Python AI and LLM bridge server. Features companion bonding dialogue, tactical combat decision-making, wild habitat encounters, interactive quests, and a complete day/night cycle.

---

## How to Install & Play

Getting the game up and running takes just 4 simple steps:

```
[ 1. Download Files ] ──► [ 2. pip install ] ──► [ 3. Run server.py ] ──► [ 4. Launch Game ]
```

---

### Step 1: Download the Required Files

You need two things: the **code repository** (which contains `server.py` and the backend AI systems) and the **game release** built for your operating system.

1. **Download the Repository Code:**
   - Click the green **Code** button at the top of this GitHub page ➔ **Download ZIP** (or [click here to download ZIP](https://github.com/Chakshan-Arora/PokemonAI/archive/refs/heads/main.zip)).
   - Extract the downloaded zip file into a folder on your computer.

2. **Download Your System's Release:**
   - Head over to the **[Releases](https://github.com/Chakshan-Arora/PokemonAI/releases)** page.
   - Download the file corresponding to your operating system:
     - **Windows:** `PokemonAI_Windows.exe` (or `PokemonAI_Windows.zip`)
     - **macOS:** `PokemonAI_Mac.app.zip` (or `PokemonAI_macOS.zip`)
     - **Linux:** `PokemonAI_Linux` (or `PokemonAI_Linux.zip`)

---

### Step 2: Install Python Requirements

Make sure you have **Python 3.9 or higher** installed on your computer.

Open your terminal (Terminal on macOS/Linux or Command Prompt / PowerShell on Windows), navigate into the extracted repository directory, and run:

```bash
pip install -r requirements.txt
```

> **Note:** If you use virtual environments, you can optionally create and activate one before running the command (`python -m venv venv`).

---

### Step 3: Run `server.py`

In the same repository directory, start the Pokémon AI bridge server:

#### **Windows:**
```cmd
python server.py
```
*(Alternatively, you can just double-click `run_server.bat`)*

#### **macOS / Linux:**
```bash
python3 server.py
```
*(Alternatively, run `./run_server.sh`)*

You will see the confirmation message:
```text
============================================================
 Syntax Error 26 — Pokémon AI & LLM Bridge Server
 Target: http://127.0.0.1:8008
============================================================
[OK] LLM Bridge Server Ready and Listening on http://127.0.0.1:8008!
```

> **Important:** Keep this terminal window open while playing so the game can communicate with the AI companion and battle engine.

---

### Step 4: Launch the Game Release

Now, locate the release file you downloaded in **Step 1** and run it:

- **Windows:** Double-click `PokemonAI_Windows.exe`.
  *(If Windows SmartScreen appears, click **More info** ➔ **Run anyway**)*.
- **macOS:** Unzip `PokemonAI_Mac.app.zip` and double-click `PokémonAI.app`.
  *(If Gatekeeper warns about an unidentified developer, right-click `PokémonAI.app` ➔ **Open**, or run `xattr -cr PokémonAI.app` in Terminal)*.
- **Linux:** Open a terminal where `PokemonAI_Linux` is located and run:
  ```bash
  chmod +x PokemonAI_Linux
  ./PokemonAI_Linux
  ```

Once launched, the game will automatically detect `http://127.0.0.1:8008` and display the **Backend Online** status indicator on your HUD!

---

## (Optional) Live Cloud AI Keys

The game runs 100% offline out-of-the-box using built-in autonomous heuristic AI. If you want your partner Pokémon to use live cloud LLM reasoning (Gemini or OpenAI), create a file named `.env` in the repository directory:

```env
# Google Gemini (Recommended for low-latency dialogue)
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

| Action | Controls |
| :--- | :--- |
| **Move Trainer** | `W`, `A`, `S`, `D` or Arrow Keys |
| **Rotate Camera** | Hold Right Mouse Button & Drag / Mouse Look |
| **Interact / Talk / Collect** | `E` or `Space` |
| **Talk to Companion Pokémon** | Click the **Companion Dialogue** bubble on the HUD |
| **Inventory & Team Menu** | `Tab` or `ESC` |
| **Battle Choices** | Click **Fight**, **Bag**, **Pokémon**, or **Run** buttons |

---

## Key Features

- **Autonomous Companion AI**: Your partner Pokémon learns your personality, dynamically tracks affection and trust, and participates in real-time conversations.
- **Intelligent Battle Engine**: Turn-based combat with type advantages, critical hits, status effects, and tactical AI opponents.
- **Dynamic 3D World**: Diverse habitats (Meadows, Forests, Mountains, Ruins) with day/night lighting cycles and time-based Pokémon spawns.
- **Authoritative Save System**: Atomic game state serialization to keep your team, inventory, currency, and quest progression safe.
- **Zero-Dependency Resilience**: Automatic offline fallback keeps all features functioning smoothly even without an active internet connection.

---

## Running Unit Tests

To verify the game systems and backend algorithms:

```bash
pytest
```
```text
============================= 810 passed in 2.15s ==============================
```
