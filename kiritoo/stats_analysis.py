"""
stats_analysis.py - Generate all required statistics graphs from collected CSV data

Graphs produced (no repeated type):
  1. Line graph     - Floor Reached across sessions (progression trend)
  2. Bar chart      - Enemies Defeated per session
  3. Histogram      - Combo Count frequency distribution
  4. Bar chart      - Items Collected by type
  5. Line graph     - Player HP over time (per floor)
  6. Pie chart      - Floor Curse Types proportion

Run: python stats_analysis.py
"""

import os
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from collections import defaultdict, Counter

DATA_DIR   = "data"
STATS_CSV  = os.path.join(DATA_DIR, "stats.csv")
OUT_DIR    = "data"


# -----------------------------------------------------------------------
def load_stats(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"[stats_analysis] No data file found at {path}. Play the game first!")
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def save_fig(fig, name: str):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"  Saved: {path}")
    plt.close(fig)


# -----------------------------------------------------------------------
def plot_floor_reached(rows: list[dict]):
    """Line graph: floor reached per session (progression trend)."""
    sessions: dict[str, int] = {}
    for r in rows:
        if r["event_type"] == "floor_reached":
            sid   = r["session_id"]
            floor = int(r.get("floor", 0) or 0)
            sessions[sid] = max(sessions.get(sid, 0), floor)

    if not sessions:
        print("  [floor_reached] no data")
        return

    sids   = list(sessions.keys())
    floors = [sessions[s] for s in sids]
    x      = list(range(1, len(sids) + 1))

    fig, ax = plt.subplots(figsize=(10, 4), facecolor="#12101e")
    ax.set_facecolor("#1a1830")
    ax.plot(x, floors, marker="o", color="#a070ff", linewidth=2, markersize=5)
    ax.fill_between(x, floors, alpha=0.15, color="#a070ff")
    ax.set_xlabel("Session #", color="white")
    ax.set_ylabel("Floor Reached", color="white")
    ax.set_title("Progression Trend: Floor Reached per Session", color="white", fontsize=14)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    fig.tight_layout()
    save_fig(fig, "graph_floor_reached.png")


# -----------------------------------------------------------------------
def plot_enemies_defeated(rows: list[dict]):
    """Bar chart: total kills per session."""
    sessions: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["event_type"] == "enemies_defeated":
            sessions[r["session_id"]] += 1

    if not sessions:
        print("  [enemies_defeated] no data")
        return

    sids   = list(sessions.keys())
    counts = [sessions[s] for s in sids]
    x      = list(range(len(sids)))

    fig, ax = plt.subplots(figsize=(10, 4), facecolor="#12101e")
    ax.set_facecolor("#1a1830")
    bars = ax.bar(x, counts, color="#e06060", width=0.7, edgecolor="#333")
    ax.set_xticks(x)
    ax.set_xticklabels([s[:6] for s in sids], rotation=45, ha="right", color="white", fontsize=9)
    ax.set_ylabel("Kill Count", color="white")
    ax.set_xlabel("Session", color="white")
    ax.set_title("Enemies Defeated per Session", color="white", fontsize=14)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    fig.tight_layout()
    save_fig(fig, "graph_enemies_defeated.png")


# -----------------------------------------------------------------------
def plot_combo_histogram(rows: list[dict]):
    """Histogram: combo count frequency distribution."""
    combos = []
    for r in rows:
        if r["event_type"] == "combo_count":
            try:
                combos.append(int(r["combo_count"]))
            except (ValueError, KeyError):
                pass

    if not combos:
        print("  [combo_count] no data")
        return

    fig, ax = plt.subplots(figsize=(8, 4), facecolor="#12101e")
    ax.set_facecolor("#1a1830")
    ax.hist(combos, bins=range(1, max(combos)+2), color="#60c060",
            edgecolor="#1a1830", align="left")
    ax.set_xlabel("Combo Count", color="white")
    ax.set_ylabel("Frequency", color="white")
    ax.set_title("Combo Kill Frequency Distribution", color="white", fontsize=14)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    fig.tight_layout()
    save_fig(fig, "graph_combo_histogram.png")


# -----------------------------------------------------------------------
def plot_items_collected(rows: list[dict]):
    """Bar chart: item type frequency."""
    type_counts: Counter = Counter()
    for r in rows:
        if r["event_type"] == "items_collected" and r.get("item_type"):
            type_counts[r["item_type"]] += 1

    if not type_counts:
        print("  [items_collected] no data")
        return

    labels = list(type_counts.keys())
    counts = [type_counts[k] for k in labels]
    colors = ["#a0a0ff","#ffd060","#60e060","#ff8060","#80d0ff"]

    fig, ax = plt.subplots(figsize=(7, 4), facecolor="#12101e")
    ax.set_facecolor("#1a1830")
    ax.bar(labels, counts, color=colors[:len(labels)], edgecolor="#333")
    ax.set_ylabel("Count", color="white")
    ax.set_xlabel("Item Type", color="white")
    ax.set_title("Items Collected by Type", color="white", fontsize=14)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    fig.tight_layout()
    save_fig(fig, "graph_items_collected.png")


# -----------------------------------------------------------------------
def plot_hp_over_floors(rows: list[dict]):
    """Line graph: average HP remaining per floor number."""
    floor_hp: dict[int, list[int]] = defaultdict(list)
    for r in rows:
        if r["event_type"] == "player_hp_over_time":
            try:
                floor_hp[int(r["floor"])].append(int(r["hp"]))
            except (ValueError, KeyError):
                pass

    if not floor_hp:
        print("  [player_hp_over_time] no data")
        return

    floors  = sorted(floor_hp.keys())
    avg_hp  = [sum(floor_hp[f]) / len(floor_hp[f]) for f in floors]

    fig, ax = plt.subplots(figsize=(10, 4), facecolor="#12101e")
    ax.set_facecolor("#1a1830")
    ax.plot(floors, avg_hp, marker=".", color="#60c0ff", linewidth=2)
    ax.fill_between(floors, avg_hp, alpha=0.15, color="#60c0ff")
    ax.set_xlabel("Floor Number", color="white")
    ax.set_ylabel("Avg HP Remaining", color="white")
    ax.set_title("Player HP Drain Pattern per Floor", color="white", fontsize=14)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    fig.tight_layout()
    save_fig(fig, "graph_hp_over_floors.png")


# -----------------------------------------------------------------------
def plot_curse_types(rows: list[dict]):
    """Pie chart: proportion of floor curse types."""
    curse_counts: Counter = Counter()
    for r in rows:
        if r["event_type"] == "floor_curse_types" and r.get("curse_type"):
            curse_counts[r["curse_type"]] += 1

    if not curse_counts:
        print("  [floor_curse_types] no data")
        return

    labels = list(curse_counts.keys())
    sizes  = [curse_counts[k] for k in labels]
    colors = ["#7060a0","#e06060","#60a0e0","#e0a030","#60c080","#c060c0"]

    fig, ax = plt.subplots(figsize=(7, 5), facecolor="#12101e")
    ax.set_facecolor("#12101e")
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.0f%%",
        colors=colors[:len(labels)], startangle=140,
        textprops={"color": "white"},
        wedgeprops={"edgecolor": "#333", "linewidth": 1.2}
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(10)
    ax.set_title("Floor Curse Types Encountered", color="white", fontsize=14)
    fig.tight_layout()
    save_fig(fig, "graph_curse_types.png")


# -----------------------------------------------------------------------
def plot_session_duration(rows: list[dict]):
    """Histogram: session duration spread."""
    durations = []
    for r in rows:
        if r["event_type"] == "session_duration":
            try:
                durations.append(float(r["duration_sec"]))
            except (ValueError, KeyError):
                pass

    if not durations:
        print("  [session_duration] no data")
        return

    fig, ax = plt.subplots(figsize=(8, 4), facecolor="#12101e")
    ax.set_facecolor("#1a1830")
    ax.hist([d/60 for d in durations], bins=10, color="#f0a040", edgecolor="#1a1830")
    ax.set_xlabel("Session Duration (minutes)", color="white")
    ax.set_ylabel("Frequency", color="white")
    ax.set_title("Session Duration Distribution", color="white", fontsize=14)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    fig.tight_layout()
    save_fig(fig, "graph_session_duration.png")


# -----------------------------------------------------------------------
def generate_all():
    print("=== Kiritoo Stats Analysis ===")
    rows = load_stats(STATS_CSV)
    if not rows:
        return
    print(f"Loaded {len(rows)} records from {STATS_CSV}\n")

    plot_floor_reached(rows)
    plot_enemies_defeated(rows)
    plot_combo_histogram(rows)
    plot_items_collected(rows)
    plot_hp_over_floors(rows)
    plot_curse_types(rows)
    plot_session_duration(rows)

    print("\nAll graphs saved to data/")


if __name__ == "__main__":
    generate_all()
