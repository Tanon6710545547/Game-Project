# Kiritoo

## Project Description

- Project by: Tanon
- Game Genre: Roguelike, Action RPG

Kiritoo is a roguelike tower-climbing RPG built with Python and Pygame. Players fight their way through 20 procedurally generated floors, encountering progressively harder enemies, floor curses, and a multi-phase boss. Between floors, a merchant offers upgrades for gold. Every run is unique — floors, enemy placements, and item drops are randomized each time.

The game automatically records gameplay statistics (kills, HP, combos, items, gold spent) and saves them to CSV. An in-game stats overlay (TAB) shows live charts and a session leaderboard, and a separate visualization script produces matplotlib graphs for deeper analysis.

---

## Installation

To clone this project:

```sh
git clone https://github.com/<your-username>/Kiritoo.git
```

**Windows** — create and activate a virtual environment:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Mac** — create and activate a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Running Guide

After activating the virtual environment, run the game:

**Windows:**

```bat
python main.py
```

**Mac:**

```sh
python3 main.py
```

To generate the UML class diagram (saves `uml.png`):

```sh
python3 generate_uml.py
```

To generate data analysis graphs (saves PNGs to `data/`):

```sh
python3 stats_analysis.py
```

---

## Tutorial / Usage

| Key | Action |
|-----|--------|
| W / A / S / D or Arrow Keys | Move |
| Space / Z / J | Attack |
| V | Skill 1 |
| B | Skill 2 |
| E | Skill 3 |
| TAB | Open stats overlay |
| ESC | Pause |
| L (in menu) | View leaderboard |

**Gameplay loop:**
1. Enter your name at the start screen
2. Navigate each floor — find the exit (lights up when all enemies are dead)
3. Every 5 floors, visit the merchant to spend gold on upgrades
4. Floor 20 has the final boss — defeat it to win
5. After the run ends, press TAB to review your session stats and compare with past runs

---

## Game Features

- **Procedural floor generation** — random tile layouts, enemy spawn points, and item drops every run
- **BFS Pathfinding** — enemies navigate around walls to chase the player
- **Floor Curse System** — each floor applies a random modifier (fast enemies, darkness, fragile HP, poisoned gold, etc.)
- **Combo Kill Multiplier** — chain kills within 2 seconds for bonus gold; combo resets on expiry
- **Multi-phase Boss** — final boss at floor 20 with phase transitions and special attacks
- **Merchant Floor** — safe shop every 5 floors with tiered rarity items and a restock option
- **Animated Sprites** — frame-by-frame character animation (idle, walk, attack, hurt)
- **In-game Stats Overlay** — TAB shows live session charts (enemies, items, HP) and an all-sessions leaderboard
- **Persistent Leaderboard** — all session records saved to CSV and ranked by floor reached
- **Data Visualization** — run `stats_analysis.py` to generate matplotlib graphs from your play history

---

## Known Bugs

- None currently known. Please open a GitHub issue if you find one.

---

## Unfinished Works

- All planned features from the proposal have been implemented.
- Extra features added beyond the proposal: animated sprites, in-game TAB stats overlay, combo system, sound manager.

---

## External Sources

Acknowledge to:

**Reference games:**

1. **The Infinite Tower** — floor-climbing roguelike concept and floor-gate mechanic. https://www.pygame.org/project/4283
2. **pgRPG - ECS Pygame Game Engine** — pygame game loop and tile-map structure reference. https://www.pygame.org/project/5674/8284

**Libraries:**

3. **Pygame** — game framework. https://www.pygame.org [LGPL License]
2. **Matplotlib** — graphs and UML diagram. https://matplotlib.org [PSF/BSD License]
3. **NumPy** — vector math in UML generation. https://numpy.org [BSD License]
4. **Character sprites** — Tiny RPG Character Asset Pack v1.03 by zerie. https://zerie.itch.io/tiny-rpg-character-asset-pack
5. **gacha.png** — https://www.magnific.com/icon/gachapon_4228420
6. **gold-coins-.png** — https://www.magnific.com/th/premium-vector/gold-coins-pile-treasure-money-game-asset-adventure-pirates-cartoon-style-shiny-money-heap_89878405.htm
7. **heal.png** — https://pngtree.com/freepng/heal-game-icon_15702933.html
8. **shield.png** — https://th.pngtree.com/freepng/medieval-shield-cartoon-game-vector_12169687.html
9. **stamina.png** — Icon Pack: Halloween | Lineal color. https://www.flaticon.com/packs/halloween-8 [Flaticon Free License]
10. **sword.png** — https://th.pngtree.com/so/game-sword
11. **BFS pathfinding** — standard algorithm, implemented from scratch
