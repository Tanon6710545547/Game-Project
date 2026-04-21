# Kiritoo 🗡️
**Roguelike Tower-Climbing RPG** — Programming 2 Year Project

---

## Quick Start

```bash
pip install pygame matplotlib
python main.py
```

## Controls

| Key | Action |
|-----|--------|
| W/A/S/D or Arrow Keys | Move |
| Space / Z / J | Attack |
| ESC | Pause |
| L (in menu) | Leaderboard |

## Statistics Analysis

After playing several sessions, generate graphs:

```bash
python stats_analysis.py
```

Graphs are saved to `data/` as PNG files.

---

## Project Structure

```
kiritoo/
├── main.py                 # Entry point
├── stats_analysis.py       # Graph generation (matplotlib)
├── requirements.txt
├── data/
│   ├── stats.csv           # Auto-generated gameplay data
│   └── leaderboard.csv     # Top-10 runs
└── src/
    ├── constants.py        # All game constants
    ├── game.py             # Game class — main loop & state machine
    ├── player.py           # Player class
    ├── enemy.py            # Enemy + Boss classes (BFS pathfinding)
    ├── floor.py            # Floor class (procedural gen + curses)
    ├── item.py             # Item class (rarity tiers)
    ├── merchant.py         # Merchant class
    ├── combo_system.py     # ComboSystem class
    ├── stat_tracker.py     # StatTracker class
    ├── leaderboard.py      # Leaderboard class
    └── hud.py              # HUD renderer
```

## OOP Classes (10 total, minimum requirement: 5)

| Class | Responsibility |
|-------|---------------|
| `Game` | Main loop & state management |
| `Player` | Movement, combat, inventory |
| `Enemy` | AI behavior, BFS pathfinding, loot |
| `Boss` | Extends Enemy — multi-phase boss |
| `Item` | Item effects & pickup, rarity tiers |
| `Floor` | Procedural generation, curse system |
| `Merchant` | Shop floor, gold-based upgrades |
| `ComboSystem` | Kill combo multiplier tracking |
| `StatTracker` | Record & export stats to CSV |
| `Leaderboard` | Persist top-10 sessions |

## Features

- **Procedural floor generation** — random tile layouts each run
- **BFS Pathfinding** — enemies navigate around obstacles
- **Floor Curse System** — random modifiers (fast enemies, darkness, fragile, etc.)
- **Combo Kill Multiplier** — chain kills for bonus gold/EXP
- **Merchant Floor** — every 5 floors, safe shop with tiered items
- **Persistent Leaderboard** — top-10 sessions saved across playthroughs
- **Full Stats Collection** — 8 tracked features, 100+ records per session

## Stats Features Tracked

1. Floor Reached — progression trend
2. Enemies Defeated — combat efficiency
3. Combo Count — aggressive vs passive playstyle
4. Items Collected — item type frequency
5. Gold Spent at Merchant — economy analysis
6. Player HP Over Time — HP drain per floor
7. Floor Curse Types — which curses appear most
8. Session Duration — play length distribution
