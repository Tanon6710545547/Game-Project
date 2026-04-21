"""
hud.py - Heads-Up Display renderer  (ornate redesign)
"""
from __future__ import annotations
import math
import os
import pygame
from src.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE, COLS, ROWS,
    WHITE, RED, GREEN, YELLOW, ORANGE, PURPLE, GOLD_COLOR, DARK_GRAY, GRAY,
    COMBO_MAX,
    FIREBALL_STAMINA_COST, AREA_STAMINA_COST, ATTACK_STAMINA_COST,
)

HUD_H   = 96
HUD_Y   = SCREEN_HEIGHT - HUD_H
BAR_W   = 168
BAR_H   = 16

# ── Palette ───────────────────────────────────────────────────────────────────
_C_PANEL    = (10,  8,  20)
_C_BORDER   = (72, 58, 110)
_C_ACCENT   = (110, 80, 200)
_C_DIVIDER  = (55, 46, 88)
_C_HP_EMPTY = (100, 18, 18)
_C_HP_FILL  = (55,  215, 80)
_C_HP_LOW   = (220, 50,  30)
_C_ST_EMPTY = (14,  58,  18)
_C_ST_FILL  = (50,  220, 125)
_C_EX_EMPTY = (16,  18,  80)
_C_EX_FILL  = (70,  115, 245)

_STAMINA_ICON: pygame.Surface | None = None

def _load_stamina_icon():
    global _STAMINA_ICON
    if _STAMINA_ICON is not None:
        return
    path = os.path.join(os.path.dirname(__file__), "stamina.png")
    try:
        img = pygame.image.load(path).convert_alpha()
        _STAMINA_ICON = pygame.transform.smoothscale(img, (13, 13))
    except Exception:
        _STAMINA_ICON = None


# ── Small icon helpers ────────────────────────────────────────────────────────
def _draw_coin_icon(surface, x, y, size=16):
    cx2, cy2, r = x + size // 2, y + size // 2, size // 2 - 1
    pygame.draw.circle(surface, (140, 100, 8),  (cx2, cy2), r)
    pygame.draw.circle(surface, (220, 175, 28), (cx2 - 1, cy2 - 1), r - 1)
    pygame.draw.circle(surface, (255, 225, 90), (cx2 - 2, cy2 - 2), max(1, r - 3))

def _draw_warn_icon(surface, x, y, size=14):
    pts = [(x + size // 2, y + 1), (x + 1, y + size - 1), (x + size - 1, y + size - 1)]
    pygame.draw.polygon(surface, (190, 130, 0), pts)
    pygame.draw.polygon(surface, (255, 200, 40), pts, 1)
    mx = x + size // 2
    pygame.draw.line(surface, (20, 10, 0), (mx, y + 4), (mx, y + size - 6), 2)
    pygame.draw.circle(surface, (20, 10, 0), (mx, y + size - 3), 1)

def _draw_arrow_up(surface, x, y, size=14, color=(60, 240, 120)):
    mid = x + size // 2
    pygame.draw.polygon(surface, color,
                        [(mid, y), (x, y + size // 2), (x + size, y + size // 2)])
    pygame.draw.rect(surface, color, (mid - 2, y + size // 2, 4, size // 2))

def _draw_skull_icon(surface, x, y, size=14, color=(180, 60, 60)):
    cx2, cy2 = x + size // 2, y + size // 2 - 1
    pygame.draw.circle(surface, color, (cx2, cy2), size // 2 - 1)
    # Eyes
    pygame.draw.circle(surface, (20, 10, 10), (cx2 - 3, cy2 - 1), 2)
    pygame.draw.circle(surface, (20, 10, 10), (cx2 + 3, cy2 - 1), 2)
    # Teeth
    pygame.draw.rect(surface, (20, 10, 10), (cx2 - 4, cy2 + 3, 3, 3))
    pygame.draw.rect(surface, (20, 10, 10), (cx2 + 1, cy2 + 3, 3, 3))

def _draw_sword_mini(surface, x, y, size=13, color=(200, 210, 230)):
    pygame.draw.line(surface, color, (x + 2, y + size - 2), (x + size - 2, y + 2), 2)
    pygame.draw.line(surface, GOLD_COLOR, (x + size // 2 - 3, y + size // 2 + 1),
                     (x + size // 2 + 3, y + size // 2 - 1), 2)

def _draw_shield_mini(surface, x, y, size=13, color=(70, 120, 210)):
    cx2 = x + size // 2
    cy2 = y + size // 2
    pts = [(cx2, y + 1), (x + size - 1, y + 4),
           (x + size - 1, cy2 + 1), (cx2, y + size - 1),
           (x + 1, cy2 + 1), (x + 1, y + 4)]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (130, 175, 255), pts, 1)


# ── Corner ornament ───────────────────────────────────────────────────────────
def _draw_corner(surface, x, y, flip_x=False, flip_y=False, color=(90, 70, 140)):
    sx = -1 if flip_x else 1
    sy = -1 if flip_y else 1
    pts = [
        (x, y),
        (x + sx * 18, y),
        (x + sx * 18, y + sy * 3),
        (x + sx * 3,  y + sy * 3),
        (x + sx * 3,  y + sy * 18),
        (x,           y + sy * 18),
    ]
    pygame.draw.lines(surface, color, False, pts, 2)
    pygame.draw.circle(surface, color, (x + sx * 6, y + sy * 6), 2)


class HUD:
    """Renders all on-screen UI elements during gameplay."""

    def __init__(self):
        self.font_big  = pygame.font.SysFont("monospace", 20, bold=True)
        self.font_med  = pygame.font.SysFont("monospace", 15, bold=True)
        self.font_sm   = pygame.font.SysFont("monospace", 13)
        self.font_xs   = pygame.font.SysFont("monospace", 11)
        _load_stamina_icon()

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, player, floor, combo_system):
        now = pygame.time.get_ticks()
        t   = now / 1000.0

        # ── Panel background ──────────────────────────────────────────────
        panel = pygame.Surface((SCREEN_WIDTH, HUD_H), pygame.SRCALPHA)
        panel.fill((*_C_PANEL, 245))
        surface.blit(panel, (0, HUD_Y))

        # Top border line with glow
        pygame.draw.line(surface, _C_ACCENT,  (0, HUD_Y), (SCREEN_WIDTH, HUD_Y), 1)
        pygame.draw.line(surface, _C_BORDER,  (0, HUD_Y + 1), (SCREEN_WIDTH, HUD_Y + 1), 1)

        # Decorative top edge: diamond ornaments
        for dx in range(60, SCREEN_WIDTH - 60, 120):
            da = 0.5 * math.sin(t * 1.4 + dx * 0.01)
            pulse_c = (
                int(90 + 30 * da),
                int(68 + 20 * da),
                int(150 + 40 * da),
            )
            pygame.draw.polygon(surface, pulse_c,
                                [(dx, HUD_Y), (dx + 5, HUD_Y + 5),
                                 (dx + 10, HUD_Y), (dx + 5, HUD_Y - 5)])

        # Corner ornaments
        _draw_corner(surface, 4, HUD_Y + 4, color=_C_ACCENT)
        _draw_corner(surface, SCREEN_WIDTH - 4, HUD_Y + 4, flip_x=True, color=_C_ACCENT)
        _draw_corner(surface, 4, HUD_Y + HUD_H - 4, flip_y=True, color=_C_DIVIDER)
        _draw_corner(surface, SCREEN_WIDTH - 4, HUD_Y + HUD_H - 4,
                     flip_x=True, flip_y=True, color=_C_DIVIDER)

        # ── Section dividers ──────────────────────────────────────────────
        for dvx in [200, 380, 660, 860]:
            pygame.draw.line(surface, _C_DIVIDER,
                             (dvx, HUD_Y + 6), (dvx, HUD_Y + HUD_H - 6), 1)

        # ── Section 1: HP / ST / EXP bars (x=26) ─────────────────────────
        bx = 26
        hp_pct = max(0.0, min(1.0, player.hp / player.max_hp)) if player.max_hp > 0 else 0
        hp_col = _C_HP_LOW if hp_pct < 0.25 else _C_HP_FILL
        if hp_pct < 0.25:
            # Pulse fill color when low
            pulse = abs(math.sin(t * 4))
            hp_col = (int(200 + 55 * pulse), int(30 + 20 * pulse), int(20 + 10 * pulse))

        self._draw_bar(surface, bx, HUD_Y + 7,  player.hp, player.max_hp,
                       _C_HP_EMPTY, hp_col,    "HP",  (255, 205, 205), t=t, bar_id=0)
        self._draw_bar(surface, bx, HUD_Y + 31, player.stamina, player.max_stamina,
                       _C_ST_EMPTY, _C_ST_FILL, "ST", (195, 255, 218), t=t, bar_id=1,
                       icon=_STAMINA_ICON)
        self._draw_bar(surface, bx, HUD_Y + 55, player.exp, player.exp_to_next,
                       _C_EX_EMPTY, _C_EX_FILL, "XP", (175, 210, 255), t=t, bar_id=2)

        # ── Section 2: Stats (x=212) ──────────────────────────────────────
        sx = 212
        lv_surf = self.font_med.render(f"Lv.{player.level}", True, (210, 185, 255))
        surface.blit(lv_surf, (sx, HUD_Y + 6))

        # ATK with sword icon
        _draw_sword_mini(surface, sx, HUD_Y + 27, size=13)
        atk_s = self.font_xs.render(f"{player.attack}", True, (235, 195, 80))
        surface.blit(atk_s, (sx + 16, HUD_Y + 28))

        # DEF with shield icon
        _draw_shield_mini(surface, sx, HUD_Y + 46, size=13)
        def_s = self.font_xs.render(f"{player.defense}", True, (100, 195, 240))
        surface.blit(def_s, (sx + 16, HUD_Y + 47))

        # Gold with coin icon
        _draw_coin_icon(surface, sx, HUD_Y + 68, size=16)
        gld_s = self.font_med.render(f"{player.gold}", True, GOLD_COLOR)
        surface.blit(gld_s, (sx + 20, HUD_Y + 67))

        # ── Section 3: Skills (x=392) ─────────────────────────────────────
        skills = [
            ("[V]", "Fireball",  FIREBALL_STAMINA_COST, (255, 120, 30),  (80, 30, 10)),
            ("[B]", "Area",      AREA_STAMINA_COST,     (80,  210, 255), (10, 40, 70)),
            ("[E]", "Wall",      0,                     (190, 145, 80),  (50, 35, 12),
             f"x{getattr(player, 'wall_breaks', 0)}"),
        ]
        for sk_i, sk in enumerate(skills):
            key_lbl, name, cost, col, dark_col = sk[0], sk[1], sk[2], sk[3], sk[4]
            extra = sk[5] if len(sk) > 5 else ""
            avail = (player.stamina >= cost) if cost > 0 else True
            skx   = 392
            sky   = HUD_Y + 5 + sk_i * 28

            # Skill panel background
            panel_col = dark_col if avail else (18, 15, 25)
            brd_col   = col      if avail else (55, 48, 70)
            sk_rect   = pygame.Rect(skx, sky, 260, 22)
            sk_surf   = pygame.Surface((260, 22), pygame.SRCALPHA)
            sk_surf.fill((*panel_col, 180))
            pygame.draw.rect(sk_surf, (*brd_col, 200), (0, 0, 260, 22), 1, border_radius=3)
            surface.blit(sk_surf, (skx, sky))

            # Key label box
            key_box = pygame.Rect(skx + 2, sky + 2, 28, 18)
            key_bg  = (*col, 200) if avail else (40, 35, 55, 200)
            kbs = pygame.Surface((28, 18), pygame.SRCALPHA)
            kbs.fill(key_bg)
            surface.blit(kbs, (skx + 2, sky + 2))
            ks = self.font_xs.render(key_lbl, True, (240, 240, 240) if avail else (120, 110, 130))
            surface.blit(ks, (skx + 3, sky + 4))

            # Name
            name_col = col if avail else (100, 90, 110)
            ns = self.font_xs.render(name, True, name_col)
            surface.blit(ns, (skx + 34, sky + 4))

            # Cost / extra
            if cost > 0:
                cost_str = f"{cost}ST"
                cost_col = (180, 220, 140) if avail else (160, 60, 60)
                cs = self.font_xs.render(cost_str, True, cost_col)
                surface.blit(cs, (skx + 180, sky + 4))
            elif extra:
                xs = self.font_xs.render(extra, True, col if avail else GRAY)
                surface.blit(xs, (skx + 180, sky + 4))

            # Unavailable X mark
            if not avail and cost > 0:
                xs = self.font_xs.render("✗", True, (200, 60, 60))
                surface.blit(xs, (skx + 244, sky + 4))

        # ── Section 4: Floor / Kills / Curse (x=672) ────────────────────
        rx = 672
        fl_str  = f"FLOOR {floor.floor_num}"
        fl_surf = self.font_med.render(fl_str, True, (185, 165, 255))
        fls_w   = fl_surf.get_width()
        surface.blit(fl_surf, (rx, HUD_Y + 6))
        pygame.draw.line(surface, _C_DIVIDER, (rx, HUD_Y + 24), (rx + fls_w + 4, HUD_Y + 24), 1)

        _draw_skull_icon(surface, rx, HUD_Y + 30, size=13)
        kl_s = self.font_sm.render(f" Kills: {player.kills}", True, (140, 130, 160))
        surface.blit(kl_s, (rx + 15, HUD_Y + 30))

        # Boss / merchant label
        if floor.is_boss:
            boss_s = self.font_xs.render("BOSS FLOOR", True, (255, 80, 60))
            surface.blit(boss_s, (rx, HUD_Y + 48))
        elif floor.is_merchant:
            merch_s = self.font_xs.render("MERCHANT", True, GOLD_COLOR)
            surface.blit(merch_s, (rx, HUD_Y + 48))

        # Curse indicator — below floor info
        if floor.curse_type != "none":
            cl = floor.curse_type.replace("_", " ").title()
            pulse_o = int(200 + 40 * math.sin(t * 2.8))
            _draw_warn_icon(surface, rx, HUD_Y + 66, size=13)
            ct = self.font_xs.render(f" {cl}", True, (255, pulse_o, 20))
            surface.blit(ct, (rx + 15, HUD_Y + 67))

        # ── Section 5: Minimap (x=872) ────────────────────────────────────
        self._draw_minimap(surface, floor, player, 875, HUD_Y + 6, 78, 82)

        # ── Exit hint (top of screen) ─────────────────────────────────────
        if floor.exit_open:
            pulse = 0.7 + 0.3 * math.sin(t * 3)
            ec = (int(60 * pulse), int(240 * pulse), int(120 * pulse))
            hint = self.font_sm.render(" Exit Open — reach the door!", True, ec)
            hx = SCREEN_WIDTH // 2 - hint.get_width() // 2
            _draw_arrow_up(surface, hx - 2, 8, size=14, color=ec)
            surface.blit(hint, (hx + 14, 8))

        # ── Combo ─────────────────────────────────────────────────────────
        if combo_system.combo_count > 0:
            self._draw_combo(surface, combo_system.combo_count,
                             combo_system.multiplier, t)

        # ── Player messages ───────────────────────────────────────────────
        self._draw_messages(surface, player)

    # ------------------------------------------------------------------
    def _draw_bar(self, surface, x, y, val, max_val,
                  empty_color, fill_color, label, text_color,
                  t=0.0, bar_id=0, icon=None):
        pct    = max(0.0, min(1.0, val / max_val)) if max_val > 0 else 0.0
        filled = int(BAR_W * pct)

        # Background (empty)
        pygame.draw.rect(surface, empty_color, (x, y, BAR_W, BAR_H), border_radius=5)

        # Fill
        if filled > 0:
            pygame.draw.rect(surface, fill_color, (x, y, filled, BAR_H), border_radius=5)
            # Top shine strip
            shine_h = max(1, BAR_H // 3)
            sc = tuple(min(255, c + 55) for c in fill_color)
            sh = pygame.Surface((filled, shine_h), pygame.SRCALPHA)
            sh.fill((*sc, 80))
            surface.blit(sh, (x, y))
            # Animated shimmer sweep
            shim_x = int((x + BAR_W * ((t * 0.6 + bar_id * 0.33) % 1.0)) % BAR_W)
            if shim_x < filled:
                sw = min(20, filled - shim_x)
                if sw > 0:
                    shim_s = pygame.Surface((sw, BAR_H), pygame.SRCALPHA)
                    for si in range(sw):
                        a = int(60 * math.sin(si / sw * math.pi))
                        pygame.draw.line(shim_s, (255, 255, 255, a), (si, 0), (si, BAR_H))
                    surface.blit(shim_s, (x + shim_x, y))

        # Border
        pygame.draw.rect(surface, _C_BORDER, (x, y, BAR_W, BAR_H), 1, border_radius=5)

        # Label + value inside bar
        txt  = f"{label} {int(val)}/{int(max_val)}"
        shd  = self.font_xs.render(txt, True, (0, 0, 0))
        lx   = x + (BAR_W - shd.get_width()) // 2
        ly   = y + (BAR_H - shd.get_height()) // 2
        surface.blit(shd,  (lx + 1, ly + 1))
        lbl2 = self.font_xs.render(txt, True, text_color)
        surface.blit(lbl2, (lx, ly))

        if icon:
            surface.blit(icon, (x + BAR_W + 4, y + 1))

    # ------------------------------------------------------------------
    def _draw_minimap(self, surface, floor, player, mx, my, mw, mh):
        """Tiny tile minimap in HUD bottom-right."""
        # Background panel
        mm_bg = pygame.Surface((mw, mh), pygame.SRCALPHA)
        mm_bg.fill((6, 4, 16, 210))
        pygame.draw.rect(mm_bg, (*_C_BORDER, 180), (0, 0, mw, mh), 1, border_radius=3)
        surface.blit(mm_bg, (mx, my))

        tile_w = mw / COLS
        tile_h = mh / ROWS

        for r in range(ROWS):
            for c in range(COLS):
                tx = int(mx + c * tile_w)
                ty = int(my + r * tile_h)
                tw = max(1, int(tile_w) - 1)
                th = max(1, int(tile_h) - 1)
                if floor.tiles[r][c] == 1:
                    col = (30, 26, 48)
                else:
                    col = (65, 58, 90)
                pygame.draw.rect(surface, col, (tx, ty, tw, th))

        # Exit dot
        if floor.exit_rect:
            ec2 = floor.exit_rect.left // TILE_SIZE
            er2 = floor.exit_rect.top  // TILE_SIZE
            edx = int(mx + ec2 * tile_w + tile_w / 2)
            edy = int(my + er2 * tile_h + tile_h / 2)
            col = (50, 255, 140) if floor.exit_open else (70, 65, 100)
            pygame.draw.circle(surface, col, (edx, edy), max(2, int(tile_w)))

        # Enemy dots
        for enemy in floor.enemies:
            if enemy.alive:
                emc = int(enemy.x / TILE_SIZE)
                emr = int(enemy.y / TILE_SIZE)
                edx2 = int(mx + emc * tile_w + tile_w / 2)
                edy2 = int(my + emr * tile_h + tile_h / 2)
                pygame.draw.circle(surface, (255, 70, 70), (edx2, edy2), max(1, int(tile_w * 0.8)))

        # Item dots
        for item in floor.items:
            if not item.collected:
                ic = int(item.x / TILE_SIZE)
                ir = int(item.y / TILE_SIZE)
                idx2 = int(mx + ic * tile_w + tile_w / 2)
                idy2 = int(my + ir * tile_h + tile_h / 2)
                pygame.draw.circle(surface, GOLD_COLOR, (idx2, idy2), 1)

        # Player dot (bright)
        pc  = int(player.x / TILE_SIZE)
        pr  = int(player.y / TILE_SIZE)
        pdx = int(mx + pc * tile_w + tile_w / 2)
        pdy = int(my + pr * tile_h + tile_h / 2)
        pygame.draw.circle(surface, (100, 200, 255), (pdx, pdy), max(2, int(tile_w)))
        pygame.draw.circle(surface, WHITE,           (pdx, pdy), 1)

        # Label
        lbl = self.font_xs.render("MAP", True, (88, 72, 130))
        surface.blit(lbl, (mx + mw // 2 - lbl.get_width() // 2, my + mh + 1))

    # ------------------------------------------------------------------
    def _draw_combo(self, surface, count: int, mult: float, t: float):
        thresholds = [
            (0,  (180, 180, 180)),
            (2,  (80,  230, 90)),
            (4,  (70,  190, 255)),
            (6,  (230, 170, 20)),
            (8,  (255, 90,  90)),
            (10, (255, 60,  200)),
        ]
        col = thresholds[0][1]
        for threshold, c in thresholds:
            if count >= threshold:
                col = c

        scale  = 1.0 + 0.06 * math.sin(t * 8)
        cx     = SCREEN_WIDTH // 2
        cy     = HUD_Y - 34

        # Glow behind text
        glow_r = int(50 + 12 * math.sin(t * 4))
        gs = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*col, int(30 + 15 * math.sin(t * 3))),
                           (glow_r, glow_r), glow_r)
        surface.blit(gs, (cx - glow_r, cy - glow_r + 8))

        # Afterimage shadow offsets
        for shx, shy, sa in [(-2, 1, 60), (2, 1, 60), (0, -1, 80)]:
            sh_surf = self.font_big.render(f"×{count}  ×{mult:.1f}", True, col)
            sh_surf = pygame.transform.scale(sh_surf,
                       (int(sh_surf.get_width() * scale),
                        int(sh_surf.get_height() * scale)))
            sh_surf.set_alpha(sa)
            surface.blit(sh_surf, (cx - sh_surf.get_width() // 2 + shx,
                                   cy - sh_surf.get_height() // 2 + shy))

        # Main text
        txt_surf = self.font_big.render(f"×{count}  ×{mult:.1f}", True, col)
        txt_surf = pygame.transform.scale(txt_surf,
                   (int(txt_surf.get_width() * scale),
                    int(txt_surf.get_height() * scale)))
        surface.blit(txt_surf, (cx - txt_surf.get_width() // 2,
                                cy - txt_surf.get_height() // 2))

    # ------------------------------------------------------------------
    def _draw_messages(self, surface, player):
        now = pygame.time.get_ticks()
        y   = HUD_Y - 64
        for text, expire in reversed(player.messages[-4:]):
            alpha = max(0, min(255, int((expire - now) / 2500 * 255 * 2)))
            surf  = self.font_sm.render(text, True, WHITE)
            surf.set_alpha(alpha)
            surface.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, y))
            y -= 22
