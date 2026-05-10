# Project Description

## 1. Project Overview

- **Project Name:** Kiritoo
- **Brief Description:**

  Kiritoo is a roguelike tower-climbing RPG built with Python and Pygame. The player fights through 20 procedurally generated floors, each with randomized enemy placements, floor curse modifiers, and item drops. Every floor is different — the game uses BFS pathfinding for enemy AI, a kill-combo multiplier system, and a merchant shop every 5 floors. A multi-phase final boss waits at floor 20.

  The game also functions as a data collection system. Every gameplay event (kills, HP snapshots, items collected, gold spent, combos, curse types) is recorded to a CSV file in real time. Players can open an in-game stats overlay (TAB) to view live bar charts, a session leaderboard, and comparisons against historical averages. A separate script (`stats_analysis.py`) generates full matplotlib visualizations from the session history.

- **Problem Statement:**

  Many roguelike games offer no feedback on how a player actually performs across runs. Kiritoo solves this by embedding a full statistics pipeline directly into the game — recording every meaningful event and making it immediately visible through charts and a persistent leaderboard, so players can identify their patterns and improve.

- **Target Users:**

  Players who enjoy roguelike games and want to track their performance over multiple runs. Also suitable as a demonstration of data collection integrated into a Python game project.

- **Key Features:**
  - Procedural floor generation with randomized tiles, enemies, and items
  - BFS pathfinding for enemy navigation around walls
  - Floor curse system (8 different modifiers per floor)
  - Kill-combo multiplier that boosts gold rewards
  - Multi-phase boss at floor 20
  - Merchant shop every 5 floors with tiered rarity items
  - In-game TAB stats overlay with live charts and session leaderboard
  - All sessions saved to CSV — persistent across playthroughs
  - Animated sprite system (idle, walk, attack, hurt)
  - External `stats_analysis.py` for full matplotlib data visualization

- **Screenshots:**

  *(Add gameplay and visualization screenshots here — place image files in `screenshots/gameplay/` and `screenshots/visualization/` and embed them below)*

  ```
  ![Gameplay](screenshots/gameplay/gameplay_01.png)
  ![Stats Overlay](screenshots/gameplay/stats_overlay.png)
  ![Data Visualization](screenshots/visualization/overview.png)
  ```

- **Proposal:** [Project Proposal PDF](proposal.pdf)

- **YouTube Presentation:** *(Add your YouTube link here)*

  The video includes:
  1. A short intro and demonstration of the game and statistics features
  2. An explanation of the class design and its usage
  3. An explanation of the statistics collection and data visualization

---

## 2. Concept

### 2.1 Background

Kiritoo was created as a Programming II year project to demonstrate object-oriented programming applied to a complete game system. The inspiration came from classic roguelikes like Enter the Gungeon and Hades — games where procedural generation and permadeath create a different experience every run.

The key motivation was to build something that goes beyond a simple game loop: by integrating a statistics tracker from the beginning, the project becomes both a playable game and a data pipeline. The problem it highlights is that most games do not show players why they fail — Kiritoo addresses this by recording and visualizing every decision point in the run.

### 2.2 Objectives

- Build a complete, playable roguelike RPG with at least 10 OOP classes
- Implement procedural floor generation with meaningful variation each run
- Record at least 8 distinct gameplay data features per session
- Display data in-game (overlay) and externally (matplotlib graphs)
- Maintain a persistent cross-session leaderboard saved to CSV
- Demonstrate inheritance, composition, and aggregation in the class design

---

## 3. UML Class Diagram

The class diagram shows all 10 classes with attributes, methods, visibility markers, type annotations, and relationship types.

**Relationships:**
- **Composition ◆──▶** : Game owns Player, Floor, StatTracker, Leaderboard, ComboSystem, HUD (lifetime tied to Game)
- **Aggregation ◇──▶** : Floor spawns Enemies (0..*) and contains Items (0..*); Merchant sells Items (0..*)
- **Dependency ╌╌▶** : Game creates Merchant; Player and Merchant record to StatTracker
- **Inheritance ──▷** : Boss extends Enemy (Boss is a specialised Enemy with extra phases)

**Submission:** [uml.pdf](uml.pdf) *(also viewable as `uml.png`)*

To regenerate the diagram:
```sh
python3 generate_uml.py
```

---

## 4. Object-Oriented Programming Implementation

| Class | File | Description |
|-------|------|-------------|
| **Game** | `src/game.py` | Main game loop and state machine (8 states: menu, playing, paused, merchant, game-over, leaderboard, boss cutscene, name entry). Owns all major subsystems. |
| **Player** | `src/player.py` | Handles movement, stamina, combat, skill use, and item application. Tracks HP, attack, defense, gold, and kills. |
| **Enemy** | `src/enemy.py` | Base enemy class with BFS pathfinding, attack logic, death handling, and loot dropping. Supports multiple enemy types. |
| **Boss** | `src/enemy.py` | Extends Enemy. Adds multi-phase behavior, special attacks, summon mechanics, and phase transition logic. |
| **Floor** | `src/floor.py` | Procedurally generates tile layouts, spawns enemies and items, applies floor curse modifiers, and manages exit unlocking. |
| **Item** | `src/item.py` | Represents collectible items with rarity tiers (common/rare/epic). Applies stat effects when picked up. |
| **Merchant** | `src/merchant.py` | Manages the shop floor — stocks tiered items, handles purchase/restock transactions, and records gold events to StatTracker. |
| **ComboSystem** | `src/combo_system.py` | Tracks kill-chain combos with a 2-second expiry window. Returns a multiplier bonus used to scale gold drops. |
| **StatTracker** | `src/stat_tracker.py` | Records all gameplay events (kills, HP, items, gold, curses, combos, duration) as structured dicts and exports to CSV. |
| **Leaderboard** | `src/leaderboard.py` | Loads, saves, and ranks all session records from `data/leaderboard.csv`. Provides context around a given session. |

---

## 5. Statistical Data

### 5.1 Data Recording Method

Data is recorded using the `StatTracker` class. Each significant gameplay event calls `stat_tracker.record(event_type, **kwargs)`, which appends a structured dict (including session ID, floor number, and timestamp) to an in-memory log list. At the end of each session, `export_csv()` writes all records to `data/stats.csv` in append mode — so all historical sessions accumulate in one file. The leaderboard summary is written separately to `data/leaderboard.csv`.

The in-game stats overlay (TAB key) reads the live log in real time. External analysis is done by `stats_analysis.py`, which reads the CSV and generates matplotlib charts.

### 5.2 Data Features

| # | Event Type | Fields Recorded | Purpose |
|---|-----------|-----------------|---------|
| 1 | `floor_reached` | session_id, floor_num | Track progression per session |
| 2 | `enemy_killed` | enemy_type, floor_num, combo_at_kill | Analyze combat patterns and kill distribution |
| 3 | `combo_count` | combo_count, floor_num | Measure aggressive vs passive playstyle |
| 4 | `item_collected` | item_name, item_type, rarity, floor_num | Identify popular items and collection rate |
| 5 | `gold_spent` | amount, item_name, floor_num | Track economy — spending habits at merchant |
| 6 | `hp_snapshot` | hp, max_hp, floor_num | Measure HP drain over floors |
| 7 | `curse_applied` | curse_type, floor_num | Show curse frequency distribution |
| 8 | `session_duration` | duration_seconds, floor_reached, kills | Measure play length and overall performance |

---

## 6. Changed Proposed Features

The following features were added beyond the original proposal:

- **Animated sprites** — character sheets with frame-by-frame animation (idle, walk, attack, hurt) were added using `sprite_loader.py` and `SpriteAnim`
- **In-game TAB stats overlay** — the proposal only mentioned an external visualization script; the live in-game overlay with scrollable leaderboard and comparison panels was added as an extra feature
- **Sound manager** (`sounds.py`) — background music and sound effects were added
- **Combo system** — the kill-chain multiplier was not in the original proposal but significantly improves gameplay feel and data richness

---

## 7. External Sources

**Reference Games (concept and code inspiration):**

1. **The Infinite Tower** — https://www.pygame.org/project/4283
   - *What was taken / adapted:* The core roguelike loop concept — a player fights enemies on each floor, collects gold, and tries to ascend as high as possible before dying. The floor-progression gate (kill all enemies → exit opens) was directly inspired by this game.
   - *What was changed:* Kiritoo adds procedural tile generation, a floor curse system, a combo multiplier, a merchant shop, animated sprites, a multi-phase boss, and a full data-tracking pipeline — none of which exist in The Infinite Tower.

2. **pgRPG - ECS Pygame Game Engine** — https://www.pygame.org/project/5674/8284
   - *What was taken / adapted:* Used as a structural reference for pygame game loop organisation, tile-based map rendering, and basic 2D player movement and collision handling.
   - *What was changed:* The ECS (Entity-Component-System) architecture was not adopted. All classes were written from scratch as plain OOP (Player, Enemy, Floor, etc.). BFS pathfinding, the state machine, and all game-specific logic are original work.

**What was added originally in Kiritoo (not from either source):**
- BFS pathfinding for enemy AI navigation around walls
- 8-type floor curse system applied randomly each floor
- Kill-combo multiplier with 2-second expiry window
- Multi-phase boss at floor 20 with special attacks and summoning
- Merchant shop every 5 floors with item rarity tiers (common / rare / epic)
- Animated sprite system (`SpriteAnim`, `sprite_loader.py`) with idle/walk/attack/hurt states
- In-game stats overlay (TAB) with live bar charts and scrollable leaderboard
- Full data pipeline: `StatTracker` → `data/stats.csv` → matplotlib visualization
- Persistent cross-session leaderboard saved to `data/leaderboard.csv`
- Procedural tile map generation (randomised layout each run)
- Stamina system for skill usage (V / B / E skills)
- Sound manager (`sounds.py`)
- Boss cutscene state and named-player entry screen

---

**Libraries:**

1. **Pygame** — game framework used for rendering, input, and sound.
   https://www.pygame.org [LGPL License]

2. **Matplotlib** — used for UML generation and data visualization charts.
   https://matplotlib.org [PSF/BSD License]

3. **NumPy** — used for vector math in UML diamond drawing.
   https://numpy.org [BSD License]

**Art / Sprites:**

4. **Character sprites** — all animated character sprite sheets (Knight Templar, Armored Orc, Armored Skeleton, Werebear, Orc Rider, Priest heal effect) used in `assets/Animetion/`.
   - Creator: zerie
   - Source: Tiny RPG Character Asset Pack v1.03 — https://zerie.itch.io/tiny-rpg-character-asset-pack
   - License: as specified on the itch.io page

5. **gacha.png** — gacha/gachapon icon used in the merchant shop UI.
   - Source: https://www.magnific.com/icon/gachapon_4228420

6. **gold-coins-.png** — gold coins icon used for gold pickups and UI.
   - Source: https://www.magnific.com/th/premium-vector/gold-coins-pile-treasure-money-game-asset-adventure-pirates-cartoon-style-shiny-money-heap_89878405.htm

7. **heal.png** — heal item icon used in the item system.
   - Source: https://pngtree.com/freepng/heal-game-icon_15702933.html

8. **shield.png** — shield/defense item icon used in the item system.
   - Source: https://th.pngtree.com/freepng/medieval-shield-cartoon-game-vector_12169687.html

9. **stamina.png** — stamina bar icon used in the HUD.
   - Source: Icon Pack: Halloween | Lineal color — https://www.flaticon.com/packs/halloween-8
   - License: Flaticon Free License (attribution required)

10. **sword.png** — sword/attack item icon used in the item system.
    - Source: https://th.pngtree.com/so/game-sword
