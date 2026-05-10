"""
generate_uml.py  —  UML Class Diagram for Kiritoo  (Visual Paradigm style)
Run:  python3 generate_uml.py   →  saves uml.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Polygon as MPoly
import numpy as np

BG      = "#f4f6f9"
C_TITLE = "#1a1a2e"

# (header_color, body_color)
COLS = {
    "Game":         ("#2d6bbf", "#eef4fc"),
    "Player":       ("#2d6bbf", "#eef4fc"),
    "Floor":        ("#2d6bbf", "#eef4fc"),
    "Enemy":        ("#bf6b2d", "#fcf0e8"),
    "Boss":         ("#bf2d2d", "#fce8e8"),
    "Item":         ("#2d8c3a", "#e8fcea"),
    "Merchant":     ("#bf6b2d", "#fcf0e8"),
    "StatTracker":  ("#6b2dbf", "#f0e8fc"),
    "Leaderboard":  ("#6b2dbf", "#f0e8fc"),
    "ComboSystem":  ("#6b2dbf", "#f0e8fc"),
    "HUD":          ("#2d8cbf", "#e8f5fc"),
}

# ── Class data (proper UML: visibility + types + return types) ────────────────
CLASSES = [
    ("Game", [
        "- state : str",
        "- player : Player",
        "- floor : Floor",
        "- stat_tracker : StatTracker",
        "- leaderboard : Leaderboard",
        "- combo_system : ComboSystem",
        "- hud : HUD",
        "- current_floor_num : int",
    ], [
        "+ run() : void",
        "+ change_state(s : str) : void",
        "- _update(dt : float) : void",
        "- _handle_event(ev : Event) : void",
        "- _end_session() : void",
        "- _advance_floor() : void",
        "- _draw_stats_overlay() : void",
    ]),
    ("Player", [
        "+ hp : int",
        "+ max_hp : int",
        "+ attack : int",
        "+ defense : int",
        "+ gold : int",
        "+ kills : int",
        "- _stamina : float",
    ], [
        "+ handle_input(keys, walls, dt : float) : void",
        "+ use_item(item : Item, curse : str) : void",
        "+ take_damage(amount : int) : void",
        "+ is_dead() : bool",
        "+ draw(surface) : void",
    ]),
    ("Floor", [
        "+ floor_num : int",
        "- tiles : list",
        "+ enemies : list[Enemy]",
        "+ items : list[Item]",
        "+ curse_type : str",
        "+ is_boss : bool",
        "+ exit_open : bool",
    ], [
        "+ generate() : void",
        "+ apply_curse(player : Player) : void",
        "+ update_exit() : void",
        "- _spawn_enemies() : void",
        "- _scatter_items() : void",
        "+ draw(surface) : void",
    ]),
    ("Enemy", [
        "+ hp : int",
        "+ attack : int",
        "+ speed : float",
        "+ enemy_type : str",
        "+ alive : bool",
        "# _phase : int",
    ], [
        "+ choose_action(player : Player, walls) : void",
        "+ try_attack(player : Player, t : int) : void",
        "+ take_damage(amount : int) : int",
        "+ on_death(player : Player, combo) : void",
        "+ drop_loot(floor : Floor, curse : str) : void",
        "+ draw(surface) : void",
    ]),
    ("Boss", [
        "+ phase : int",
        "- special_cooldown : int",
    ], [
        "+ try_attack(player : Player, t : int, curse : str) : void",
        "+ special_attack(player : Player, t : int) : void",
        "+ try_summon(walls, floor : Floor) : void",
        "+ phase_transition() : void",
    ]),
    ("Item", [
        "+ name : str",
        "+ type : str",
        "+ rarity : str",
        "+ value : int",
        "+ collected : bool",
    ], [
        "+ apply(player : Player, curse : str) : void",
        "+ describe() : str",
    ]),
    ("Merchant", [
        "+ floor_num : int",
        "- stock : list[Item]",
        "- stat_tracker : StatTracker",
    ], [
        "+ try_buy(index : int, player : Player) : str",
        "+ try_restock(player : Player) : str",
        "+ restock() : void",
        "+ draw(surface, player : Player) : void",
    ]),
    ("StatTracker", [
        "- session_id : str",
        "- log : list[dict]",
    ], [
        "+ record(event_type : str, **kwargs) : void",
        "+ export_csv() : void",
        "+ generate_summary(floor : int, kills : int) : dict",
    ]),
    ("Leaderboard", [
        "- entries : list[dict]",
    ], [
        "+ load() : void",
        "+ save() : void",
        "+ add_entry(session : dict) : void",
        "+ display_top10() : list",
        "+ get_player_context(sid : str, n : int) : list",
    ]),
    ("ComboSystem", [
        "+ combo_count : int",
        "+ multiplier : float",
        "- last_kill_time : int",
    ], [
        "+ register_kill(time_ms : int) : void",
        "+ check_expiry(time_ms : int) : void",
        "+ reset() : void",
        "+ get_bonus() : float",
    ]),
    ("HUD", [
        "- font_sm : Font",
        "- font_big : Font",
    ], [
        "+ draw(surface, player : Player, floor : Floor) : void",
        "- _draw_combo(surface, combo : ComboSystem) : void",
        "- _draw_bars(surface, player : Player) : void",
    ]),
]

# ── Layout (x, y, w, h) ───────────────────────────────────────────────────────
COL = [0.03, 0.28, 0.54, 0.76]
W   = 0.22

LAYOUT = {
    "Game":         (COL[2], 0.60,  W, 0.36),
    "Player":       (COL[0], 0.64,  W, 0.32),
    "Floor":        (COL[1], 0.64,  W, 0.32),
    "Enemy":        (COL[0], 0.30,  W, 0.30),
    "Boss":         (COL[0], 0.02,  W, 0.25),
    "Item":         (COL[1], 0.40,  W, 0.20),
    "Merchant":     (COL[2], 0.35,  W, 0.21),
    "StatTracker":  (COL[3], 0.78,  W, 0.18),
    "Leaderboard":  (COL[3], 0.56,  W, 0.18),
    "ComboSystem":  (COL[3], 0.32,  W, 0.20),
    "HUD":          (COL[3], 0.09,  W, 0.19),
}

# ── Relations (from, to, label, style, card_from, card_to, arc_rad) ───────────
RELATIONS = [
    ("Game",     "Player",      "owns",       "compose",   "1",  "1",     0.00),
    ("Game",     "Floor",       "owns",       "compose",   "1",  "1",     0.06),
    ("Game",     "StatTracker", "owns",       "compose",   "1",  "1",     0.00),
    ("Game",     "Leaderboard", "owns",       "compose",   "1",  "1",     0.06),
    ("Game",     "ComboSystem", "owns",       "compose",   "1",  "1",     0.10),
    ("Game",     "HUD",         "owns",       "compose",   "1",  "1",     0.14),
    ("Game",     "Merchant",    "creates",    "depend",    "",   "0..1",  0.08),
    ("Floor",    "Enemy",       "spawns",     "aggregate", "1",  "0..*",  0.06),
    ("Floor",    "Item",        "contains",   "aggregate", "1",  "0..*",  0.00),
    ("Merchant", "Item",        "sells",      "aggregate", "1",  "0..*",  0.08),
    ("Player",   "StatTracker", "records to", "depend",    "",   "",      0.18),
    ("Merchant", "StatTracker", "records to", "depend",    "",   "",      0.00),
    ("Boss",     "Enemy",       "extends",    "inherit",   "",   "",      0.00),
]

# (color, lw, ls)
REL_STYLE = {
    "compose":   ("#2255aa", 1.6, "-"),
    "aggregate": ("#227744", 1.4, "-"),
    "depend":    ("#996622", 1.2, "--"),
    "inherit":   ("#aa2222", 1.8, "-"),
}

LINE_H = 0.0185
HDR_H  = 0.052
PAD    = 0.009


def box_edge(name, direction):
    x, y, w, h = LAYOUT[name]
    cx, cy = x + w / 2, y + h / 2
    if direction == "right":  return x + w, cy
    if direction == "left":   return x,     cy
    if direction == "top":    return cx,    y + h
    if direction == "bottom": return cx,    y
    return cx, cy


def get_endpoints(frm, to):
    fx0, fy0, fw, fh = LAYOUT[frm]
    tx0, ty0, tw, th = LAYOUT[to]
    fcx, fcy = fx0 + fw / 2, fy0 + fh / 2
    tcx, tcy = tx0 + tw / 2, ty0 + th / 2
    if abs(fcx - tcx) >= abs(fcy - tcy):
        if fcx < tcx:
            return box_edge(frm, "right"), box_edge(to, "left")
        else:
            return box_edge(frm, "left"),  box_edge(to, "right")
    else:
        if fcy < tcy:
            return box_edge(frm, "top"),    box_edge(to, "bottom")
        else:
            return box_edge(frm, "bottom"), box_edge(to, "top")


def draw_diamond(ax, x, y, tx, ty, filled, color, size=0.012):
    """Draw a UML diamond at (x, y) oriented toward (tx, ty)."""
    dx, dy = tx - x, ty - y
    n = max(np.hypot(dx, dy), 1e-9)
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    a, b = size, size * 0.52
    pts = [
        (x + ux * a,  y + uy * a),
        (x + px * b,  y + py * b),
        (x - ux * a,  y - uy * a),
        (x - px * b,  y - py * b),
    ]
    ax.add_patch(MPoly(pts, closed=True,
                       fc=color if filled else BG,
                       ec=color, lw=1.3, zorder=7))


def draw_relation(ax, frm, to, label, style, card_frm, card_to, rad):
    color, lw, ls = REL_STYLE[style]
    (fx, fy), (tx, ty) = get_endpoints(frm, to)

    # Offset line start past diamond tip
    if style in ("compose", "aggregate"):
        dx, dy = tx - fx, ty - fy
        n = max(np.hypot(dx, dy), 1e-9)
        fxl = fx + (dx / n) * 0.013
        fyl = fy + (dy / n) * 0.013
    else:
        fxl, fyl = fx, fy

    if style == "inherit":
        ax.annotate("", xy=(tx, ty), xytext=(fxl, fyl),
                    arrowprops=dict(
                        arrowstyle="-|>",
                        ec=color, fc=BG,
                        mutation_scale=14, lw=lw,
                        linestyle=ls,
                        connectionstyle=f"arc3,rad={rad}"),
                    zorder=5)
    else:
        ax.annotate("", xy=(tx, ty), xytext=(fxl, fyl),
                    arrowprops=dict(
                        arrowstyle="->",
                        color=color,
                        mutation_scale=11, lw=lw,
                        linestyle=ls,
                        connectionstyle=f"arc3,rad={rad}"),
                    zorder=5)

    if style in ("compose", "aggregate"):
        draw_diamond(ax, fx, fy, tx, ty, filled=(style == "compose"), color=color)

    # Relationship label
    mx, my = (fx + tx) / 2, (fy + ty) / 2
    ax.text(mx, my, label, ha="center", va="center",
            fontsize=5, color=color, style="italic",
            bbox=dict(boxstyle="round,pad=0.10", fc=BG, ec="none", alpha=0.9),
            zorder=8)

    # Cardinality labels
    if card_frm:
        ax.text(fx + (tx - fx) * 0.13, fy + (ty - fy) * 0.13,
                card_frm, ha="center", va="center",
                fontsize=5, color="#1a55aa", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.06", fc=BG, ec="none", alpha=0.9),
                zorder=8)
    if card_to:
        ax.text(fx + (tx - fx) * 0.87, fy + (ty - fy) * 0.87,
                card_to, ha="center", va="center",
                fontsize=5, color="#1a55aa", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.06", fc=BG, ec="none", alpha=0.9),
                zorder=8)


def draw_class_box(ax, name, attrs, methods):
    x, y, w, h = LAYOUT[name]
    hdr_col, body_col = COLS[name]

    # Subtle drop shadow
    ax.add_patch(FancyBboxPatch(
        (x + 0.004, y - 0.004), w, h,
        boxstyle="round,pad=0.006",
        fc="#cccccc", alpha=0.45, zorder=1, ec="none"))

    # Main box body (light tinted fill, colored border)
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.006",
        fc=body_col, ec=hdr_col, lw=1.6, zorder=2))

    # Header stripe (colored, covers top portion)
    ax.add_patch(FancyBboxPatch(
        (x + 0.001, y + h - HDR_H + 0.001), w - 0.002, HDR_H - 0.001,
        boxstyle="round,pad=0.004",
        fc=hdr_col, ec="none", zorder=3))

    # Class name (white, bold, no stereotype for clean VP look)
    ax.text(x + w / 2, y + h - HDR_H / 2,
            name,
            ha="center", va="center",
            fontsize=8.5, fontweight="bold", color="white", zorder=4)

    # Divider: header / attrs
    div1 = y + h - HDR_H - 0.002
    ax.plot([x + PAD, x + w - PAD], [div1, div1], color=hdr_col, lw=0.9, zorder=4)

    # Attributes
    cursor = div1 - 0.007
    for a in attrs:
        ax.text(x + PAD + 0.003, cursor, a,
                ha="left", va="top",
                fontsize=5.8, color="#2a2a2a", zorder=4)
        cursor -= LINE_H

    # Divider: attrs / methods
    div2 = cursor + LINE_H - 0.004
    ax.plot([x + PAD, x + w - PAD], [div2, div2],
            color="#aaaaaa", lw=0.7, ls="--", zorder=4)

    # Methods (slightly blue to differentiate)
    cursor = div2 - 0.006
    for m in methods:
        ax.text(x + PAD + 0.003, cursor, m,
                ha="left", va="top",
                fontsize=5.8, color="#1a2a6e", zorder=4)
        cursor -= LINE_H


# ── Figure ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(24, 15))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(-0.01, 1.01)
ax.set_ylim(-0.04, 1.04)
ax.axis("off")

# Relations first (behind boxes)
for frm, to, label, style, cf, ct, rad in RELATIONS:
    draw_relation(ax, frm, to, label, style, cf, ct, rad)

# Class boxes on top
cls_map = {name: (attrs, methods) for name, attrs, methods in CLASSES}
for name, (attrs, methods) in cls_map.items():
    draw_class_box(ax, name, attrs, methods)

# Title
ax.text(0.5, 1.012, "Kiritoo — UML Class Diagram",
        ha="center", va="bottom", fontsize=16, fontweight="bold",
        color=C_TITLE, transform=ax.transAxes)

# Legend
legend_items = [
    mpatches.Patch(color="#2255aa", label="Composition  ◆──▶  (Game owns, 1-to-1)"),
    mpatches.Patch(color="#227744", label="Aggregation  ◇──▶  (contains / spawns, 0..*)"),
    mpatches.Patch(color="#996622", label="Dependency   ╌╌▶   (creates / records to)"),
    mpatches.Patch(color="#aa2222", label="Inheritance  ──▷   (Boss extends Enemy)"),
]
leg = ax.legend(handles=legend_items, loc="lower right",
                fontsize=7.5, facecolor="white", edgecolor="#cccccc",
                labelcolor="#222222", framealpha=0.95, borderpad=0.9)

plt.tight_layout(pad=0.6)
plt.savefig("uml.png", dpi=160, bbox_inches="tight",
            facecolor=fig.get_facecolor())
plt.savefig("uml.pdf", bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Saved → uml.png  uml.pdf")
