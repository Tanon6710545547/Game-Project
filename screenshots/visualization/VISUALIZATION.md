# Data Visualization

This folder contains screenshots of all data visualization components in Kiritoo.
Screenshots are taken from the in-game stats overlay (TAB key) and the external `stats_analysis.py` graphs.

---

## Overview — In-Game Stats Overlay

![Stats Overlay Overview](overview.png)

The in-game stats overlay (opened with TAB during or after a game) shows two tabs: **SESSION** (current run stats) and **ALL SESSIONS** (historical leaderboard). It is accessible at any time and updates live during gameplay. The SESSION tab shows bar charts for enemies defeated by type, items collected by type, HP over floors, and floor curse distribution. The ALL SESSIONS tab shows a scrollable ranked table of every past session with click-to-compare functionality.

---

## Component 1 — Enemies Defeated by Type (Bar Chart)

![Enemies Bar Chart](enemies_chart.png)

This bar chart shows how many enemies of each type the player defeated in the current session. Each enemy type (Armored Orc, Armored Skeleton, Werebear, Orc Rider) is shown as a separate bar with its kill count and percentage of total kills. This data is collected via `enemy_killed` events in `StatTracker` and helps identify which enemy type the player encounters most and defeats most efficiently.

---

## Component 2 — Items Collected by Type (Bar Chart)

![Items Bar Chart](items_chart.png)

This bar chart shows the number of items collected in the session, grouped by item type (heal, attack, defense, gold, gacha). It is useful for understanding what items the player prioritized during a run and whether their item strategy matched their playstyle (aggressive vs defensive).

---

## Component 3 — HP Over Floors (Line Graph)

![HP Line Graph](hp_chart.png)

This line graph shows the player's HP at the end of each floor. It makes it easy to see which floors caused the most damage and whether the player was recovering HP effectively through healing items. A downward trend in the late game often indicates increasing difficulty from curses and harder enemies.

---

## Component 4 — Floor Curse Distribution (Bar Chart)

![Curse Bar Chart](curse_chart.png)

This bar chart shows which floor curse types appeared during the session. Each curse (e.g., fast, dark, fragile, poison, mirror) is shown with its count. This data reveals whether curse RNG was favorable or punishing in a given run, and over many sessions shows which curses are most common.

---

## Component 5 — All Sessions Leaderboard (Table)

![Leaderboard Table](leaderboard_table.png)

The ALL SESSIONS tab shows a scrollable table of every session ever played, ranked by floor reached. Columns show rank, player name, floor reached, enemies killed, max combo, and session duration. Clicking a row highlights it and shows a side panel comparing that session's stats to the historical average. This table is sourced from `data/leaderboard.csv` via the `Leaderboard` class.

---

## Component 6 — External Graphs (`stats_analysis.py`)

![External Graphs Overview](external_graphs.png)

Running `python3 stats_analysis.py` generates a multi-panel matplotlib figure saved to `data/`. It includes:

- **Line graph** — floor reached across all sessions (progression trend)
- **Bar chart** — total enemies defeated by type across all sessions
- **Histogram** — combo count distribution (how often combos occur)
- **Bar chart** — items collected by type across all sessions
- **Line graph** — average HP per floor averaged across sessions
- **Pie chart** — floor curse type frequency across all sessions

These graphs provide a bird's-eye view of long-term play patterns that the in-game overlay cannot easily show.
