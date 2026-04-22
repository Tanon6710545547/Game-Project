"""
visualize.py - Kiritoo Data Analysis Dashboard

Reads stats.csv from data/ and renders 6 visualisations covering
Distribution, Time-series, and Proportion graph categories.

Usage
-----
    python visualize.py                 # interactive window
    python visualize.py --save          # save charts to data/charts/
    python visualize.py --save --nogui  # save only, no window
    python visualize.py --summary       # print row counts and exit

Requires: pandas, matplotlib
    pip install pandas matplotlib
"""
from __future__ import annotations

import argparse
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(_HERE, "data")
STATS_CSV = os.path.join(DATA_DIR, "stats.csv")
CHART_DIR = os.path.join(DATA_DIR, "charts")

# ── Colour palette ────────────────────────────────────────────────────────────
BG        = "#0e0c18"
PANEL     = "#16132a"
BORDER    = "#2e2850"
FG        = "#dcdaf0"
MUTED     = "#7a779a"

C_PURPLE  = "#9060d8"
C_GOLD    = "#f0c040"
C_CYAN    = "#38c8d8"
C_GREEN   = "#50d070"
C_RED     = "#d44060"
C_ORANGE  = "#e08040"
C_BLUE    = "#4888d8"
C_PINK    = "#d060a8"

ITEM_COLORS = {
    "potion": C_GREEN,
    "weapon": C_RED,
    "armor":  C_BLUE,
    "buff":   C_GOLD,
    "gold":   C_ORANGE,
}
CURSE_COLORS = {
    "none":         MUTED,
    "fast_enemies": C_RED,
    "darkness":     C_PURPLE,
    "no_potions":   C_ORANGE,
    "fragile":      C_PINK,
    "poor_loot":    C_CYAN,
}
SESSION_PALETTE = [C_PURPLE, C_CYAN, C_GREEN, C_GOLD, C_RED]


# ── Theme ─────────────────────────────────────────────────────────────────────
def apply_theme() -> None:
    plt.rcParams.update({
        "figure.facecolor":  BG,
        "axes.facecolor":    PANEL,
        "axes.edgecolor":    BORDER,
        "axes.labelcolor":   MUTED,
        "axes.titlecolor":   FG,
        "axes.titlesize":    11,
        "axes.titleweight":  "bold",
        "axes.titlepad":     9,
        "xtick.color":       MUTED,
        "ytick.color":       MUTED,
        "xtick.labelsize":   8,
        "ytick.labelsize":   8,
        "text.color":        FG,
        "grid.color":        BORDER,
        "grid.linestyle":    "--",
        "grid.alpha":        0.45,
        "font.family":       "DejaVu Sans",
        "font.size":         9,
        "legend.facecolor":  PANEL,
        "legend.edgecolor":  BORDER,
        "legend.labelcolor": FG,
        "legend.fontsize":   8,
    })


# ── Helpers ───────────────────────────────────────────────────────────────────
def _load() -> pd.DataFrame:
    """Load stats CSV with numeric coercion."""
    if not os.path.exists(STATS_CSV):
        print(f"[visualize] stats.csv not found at {STATS_CSV}")
        print("  Play the game first to generate data.")
        sys.exit(0)
    df = pd.read_csv(STATS_CSV, dtype=str)
    for col in ("floor", "value", "hp", "max_hp",
                "gold_spent", "duration_sec", "combo_count"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _style(ax, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
    if title:   ax.set_title(title)
    if xlabel:  ax.set_xlabel(xlabel, labelpad=6)
    if ylabel:  ax.set_ylabel(ylabel, labelpad=6)
    ax.grid(True, alpha=0.35)
    for sp in ax.spines.values():
        sp.set_color(BORDER)


def _no_data(ax, msg: str = "No data yet — play the game first") -> None:
    ax.text(0.5, 0.5, msg, transform=ax.transAxes,
            ha="center", va="center", color=MUTED, fontsize=10, style="italic")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def _annotate(ax, text: str) -> None:
    """Small info box in top-left of axes."""
    ax.text(0.02, 0.97, text, transform=ax.transAxes,
            ha="left", va="top", color=MUTED, fontsize=8,
            bbox=dict(facecolor=PANEL, edgecolor=BORDER,
                      boxstyle="round,pad=0.4", alpha=0.88))


# ── Chart 1 — Line graph: Floor Reached per Session ──────────────────────────
def chart_floor_reached(ax, df: pd.DataFrame) -> None:
    sub = (df[df["event_type"] == "floor_reached"]
           .groupby("session_id")["floor"].max()
           .reset_index(name="max_floor"))
    _style(ax, "Floor Reached per Session", "Session #", "Floor")
    if sub.empty:
        _no_data(ax); return

    x = range(1, len(sub) + 1)
    y = sub["max_floor"].tolist()

    ax.plot(x, y, color=C_PURPLE, linewidth=2, marker="o",
            markersize=4, markerfacecolor=C_GOLD, zorder=3)
    ax.fill_between(x, y, alpha=0.12, color=C_PURPLE)

    # Rolling average (window=5) when enough data
    if len(y) >= 5:
        s = pd.Series(y).rolling(5, center=True).mean()
        ax.plot(x, s, color=C_GOLD, linewidth=1.4,
                linestyle="--", label="5-session avg")
        ax.legend(loc="upper left")

    best = max(y)
    best_x = y.index(best) + 1
    ax.annotate(f"Best: {best}", xy=(best_x, best),
                xytext=(best_x + max(1, len(y)//10), best),
                color=C_GOLD, fontsize=8,
                arrowprops=dict(arrowstyle="->", color=C_GOLD, lw=1.1))
    _annotate(ax, f"{len(y)} sessions  ·  avg floor {sum(y)/len(y):.1f}")
    ax.set_xticks(list(x)[::max(1, len(x)//10)])


# ── Chart 2 — Bar chart: Enemies Defeated per Session ────────────────────────
def chart_enemies_defeated(ax, df: pd.DataFrame) -> None:
    sub = (df[df["event_type"] == "enemies_defeated"]
           .groupby("session_id")
           .size()
           .reset_index(name="kills")
           .sort_values("kills", ascending=True))
    _style(ax, "Enemies Defeated per Session", "Kill Count", "")
    if sub.empty:
        _no_data(ax); return

    # Colour bars by quartile
    q25, q75 = sub["kills"].quantile(0.25), sub["kills"].quantile(0.75)
    colors = [C_RED if v >= q75 else (C_ORANGE if v >= q25 else C_BLUE)
              for v in sub["kills"]]
    y_pos = range(len(sub))
    ax.barh(list(y_pos), sub["kills"].tolist(),
            color=colors, edgecolor=BG, height=0.75)
    ax.set_yticks([])
    mean_k = sub["kills"].mean()
    ax.axvline(mean_k, color=C_GOLD, linewidth=1.5, linestyle="--")
    ax.text(mean_k + sub["kills"].max() * 0.01, len(sub) * 0.97,
            f"avg {mean_k:.0f}", color=C_GOLD, fontsize=8, va="top")
    _annotate(ax, f"{len(sub)} sessions  ·  total {sub['kills'].sum():.0f} kills")


# ── Chart 3 — Histogram: Combo Count Distribution ────────────────────────────
def chart_combo_histogram(ax, df: pd.DataFrame) -> None:
    sub = df[(df["event_type"] == "combo_count") & df["combo_count"].notna()]
    _style(ax, "Combo Kill Distribution", "Combo Count", "Frequency")
    if sub.empty:
        _no_data(ax); return

    combos = sub["combo_count"].dropna().astype(int)
    max_c  = int(combos.max())
    bins   = list(range(1, max_c + 2))
    _, _, patches = ax.hist(combos, bins=bins, color=C_GREEN,
                            edgecolor=BG, align="left", alpha=0.9)

    # Colour higher combos more brightly
    for i, patch in enumerate(patches):
        t = min(1.0, i / max(1, max_c - 1))
        patch.set_facecolor(
            (int(80 + 175 * (1 - t)) / 255,
             int(208 + 47 * t) / 255,
             int(112 - 50 * t) / 255))

    mean_c  = combos.mean()
    median_c = combos.median()
    ax.axvline(mean_c,   color=C_GOLD,   linewidth=1.5, linestyle="--",
               label=f"mean {mean_c:.1f}")
    ax.axvline(median_c, color=C_CYAN,   linewidth=1.2, linestyle=":",
               label=f"median {median_c:.0f}")
    ax.legend(loc="upper right")
    _annotate(ax, f"{len(combos):,} kills recorded  ·  max combo ×{max_c}")


# ── Chart 4 — Bar chart: Items Collected by Type ─────────────────────────────
def chart_items_collected(ax, df: pd.DataFrame) -> None:
    sub = df[(df["event_type"] == "items_collected") & df["item_type"].notna()]
    _style(ax, "Items Collected by Type", "Item Type", "Count")
    if sub.empty:
        _no_data(ax); return

    counts = sub["item_type"].value_counts().sort_values(ascending=False)
    colors = [ITEM_COLORS.get(t, MUTED) for t in counts.index]
    bars = ax.bar(counts.index, counts.values,
                  color=colors, edgecolor=BG, width=0.65)

    # Value labels on bars
    for bar, v in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + counts.max() * 0.01,
                str(int(v)), ha="center", va="bottom", color=FG, fontsize=9,
                fontweight="bold")

    ax.set_ylim(0, counts.max() * 1.14)
    ax.tick_params(axis="x", rotation=20)
    _annotate(ax, f"{counts.sum():,} items total  ·  {len(counts)} types")


# ── Chart 5 — Line graph: Player HP per Floor ────────────────────────────────
def chart_hp_over_floors(ax, df: pd.DataFrame) -> None:
    sub = df[(df["event_type"] == "player_hp_over_time") &
             df["floor"].notna() & df["hp"].notna() & df["max_hp"].notna()]
    _style(ax, "Player HP Drain per Floor", "Floor Number", "HP Remaining")
    if sub.empty:
        _no_data(ax); return

    sub = sub.copy()
    sub["hp_ratio"] = sub["hp"] / sub["max_hp"].replace(0, pd.NA)

    # Aggregate: mean ± std per floor
    grp = sub.groupby("floor")["hp_ratio"].agg(["mean", "std", "count"]).reset_index()
    grp = grp[grp["count"] >= 2].sort_values("floor")
    if grp.empty:
        _no_data(ax, "Not enough samples per floor yet"); return

    floors = grp["floor"].tolist()
    means  = grp["mean"].tolist()
    stds   = grp["std"].fillna(0).tolist()
    upper  = [min(1.0, m + s) for m, s in zip(means, stds)]
    lower  = [max(0.0, m - s) for m, s in zip(means, stds)]

    ax.fill_between(floors, lower, upper, alpha=0.18, color=C_CYAN)
    ax.plot(floors, means, color=C_CYAN, linewidth=2, marker=".", markersize=4)

    # Top-5 individual sessions overlaid lightly
    sess_floors = sub.groupby("session_id")["floor"].max().nlargest(5).index
    for i, sid in enumerate(sess_floors):
        s = sub[sub["session_id"] == sid].groupby("floor")["hp_ratio"].mean()
        ax.plot(s.index, s.values,
                color=SESSION_PALETTE[i % len(SESSION_PALETTE)],
                linewidth=0.9, alpha=0.45)

    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{int(v*100)}%"))
    _annotate(ax, f"{sub['session_id'].nunique()} sessions  ·  shaded = ±1 std")


# ── Chart 6 — Donut: Floor Curse Proportions ─────────────────────────────────
def chart_curse_types(ax, df: pd.DataFrame) -> None:
    sub = df[(df["event_type"] == "floor_curse_types") & df["curse_type"].notna()]
    _style(ax, "Floor Curse Types")
    if sub.empty:
        _no_data(ax); return

    counts = sub["curse_type"].value_counts()
    colors = [CURSE_COLORS.get(k, MUTED) for k in counts.index]
    labels = [k.replace("_", " ").title() for k in counts.index]

    wedges, _, autotexts = ax.pie(
        counts.values,
        labels=labels,
        colors=colors,
        autopct="%1.0f%%",
        startangle=110,
        textprops={"color": FG, "fontsize": 8},
        wedgeprops={"edgecolor": BG, "linewidth": 1.8, "width": 0.42},
        pctdistance=0.80,
    )
    for at in autotexts:
        at.set_fontweight("bold")
        at.set_color(BG)
        at.set_fontsize(8)

    # Donut centre: total floors
    total = counts.sum()
    ax.text(0,  0.08, f"{total:,}", ha="center", va="center",
            color=C_GOLD, fontsize=20, fontweight="bold")
    ax.text(0, -0.12, "floors", ha="center", va="center",
            color=MUTED, fontsize=9)

    # Most common curse below
    top = counts.index[0].replace("_", " ").title()
    pct = counts.values[0] / total * 100
    ax.text(0.5, -0.07, f"Most common: {top} ({pct:.0f}%)",
            transform=ax.transAxes, ha="center", va="top",
            color=MUTED, fontsize=8)


# ── Dashboard builder ─────────────────────────────────────────────────────────
_CHARTS = [
    ("floor_reached",    chart_floor_reached),
    ("enemies_defeated", chart_enemies_defeated),
    ("combo_histogram",  chart_combo_histogram),
    ("items_collected",  chart_items_collected),
    ("hp_over_floors",   chart_hp_over_floors),
    ("curse_types",      chart_curse_types),
]


def build_dashboard(df: pd.DataFrame) -> plt.Figure:
    fig = plt.figure(figsize=(17, 10))
    fig.suptitle("KIRITOO  —  Data Analysis Dashboard",
                 color=C_GOLD, fontsize=15, fontweight="bold", y=0.995)

    gs = gridspec.GridSpec(2, 3, figure=fig,
                           hspace=0.52, wspace=0.38,
                           left=0.055, right=0.975,
                           top=0.935, bottom=0.07)
    axes = [fig.add_subplot(gs[r, c]) for r in range(2) for c in range(3)]

    for ax, (name, fn) in zip(axes, _CHARTS):
        try:
            fn(ax, df)
        except Exception as exc:
            print(f"  [!] {name}: {exc}")
            _no_data(ax, f"Error rendering chart\n{exc}")

    return fig


# ── Save helpers ──────────────────────────────────────────────────────────────
def save_dashboard(df: pd.DataFrame) -> str:
    os.makedirs(CHART_DIR, exist_ok=True)
    fig = build_dashboard(df)
    path = os.path.join(CHART_DIR, "dashboard.png")
    fig.savefig(path, dpi=120, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


def save_individual(df: pd.DataFrame) -> None:
    os.makedirs(CHART_DIR, exist_ok=True)
    for name, fn in _CHARTS:
        fig, ax = plt.subplots(figsize=(8, 5))
        try:
            fn(ax, df)
            fig.tight_layout()
            path = os.path.join(CHART_DIR, f"{name}.png")
            fig.savefig(path, dpi=120, facecolor=BG, bbox_inches="tight")
            print(f"  Saved: {path}")
        except Exception as exc:
            print(f"  [!] {name}: {exc}")
        finally:
            plt.close(fig)


# ── Summary ───────────────────────────────────────────────────────────────────
def print_summary(df: pd.DataFrame) -> None:
    print()
    print("=" * 52)
    print("  KIRITOO  —  DATA SUMMARY")
    print("=" * 52)
    print(f"  Total records : {len(df):,}")
    print(f"  Sessions      : {df['session_id'].nunique()}")
    print()
    for et in df["event_type"].dropna().unique():
        n = (df["event_type"] == et).sum()
        print(f"  {et:<28s}  {n:>6,} rows")
    print("=" * 52)


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kiritoo data analysis dashboard")
    parser.add_argument("--save",    action="store_true",
                        help=f"Save charts to {CHART_DIR}/")
    parser.add_argument("--nogui",  action="store_true",
                        help="Skip interactive window (use with --save)")
    parser.add_argument("--summary", action="store_true",
                        help="Print data summary only")
    args = parser.parse_args()

    apply_theme()

    print("Loading data...")
    df = _load()
    print_summary(df)

    if args.summary:
        return

    if args.save:
        print("\nSaving individual charts...")
        save_individual(df)
        print("\nSaving dashboard...")
        save_dashboard(df)

    if not args.nogui:
        print("\nOpening dashboard...  (close the window to exit)")
        build_dashboard(df)
        plt.show()


if __name__ == "__main__":
    main()
