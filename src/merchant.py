"""
merchant.py - Merchant Floor: rotating shop, gold-based upgrades  (ornate redesign)
"""
from __future__ import annotations
import math
import pygame
import random
from src.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    DARK_BG, WHITE, YELLOW, GOLD_COLOR, GRAY, BLACK, GREEN, RED
)
from src.item import Item, ITEM_DEFINITIONS, random_item_by_rarity


# ── Colour palette ─────────────────────────────────────────────────────────────
_C_BG      = (8,   6,  20)
_C_PANEL   = (14, 11, 30)
_C_BORDER  = (88, 65, 145)
_C_ACCENT  = (130, 95, 210)
_C_DIVIDER = (55,  42, 95)

_RARITY_COL = {
    "common":    (140, 140, 145),
    "uncommon":  (55,  195, 70),
    "rare":      (65,  115, 245),
    "legendary": (255, 185, 15),
}
_RARITY_GLOW = {
    "common":    (100, 100, 105),
    "uncommon":  (40,  150, 55),
    "rare":      (50,   90, 200),
    "legendary": (220, 155, 10),
}


class Merchant:
    """Safe shop floor every 5 floors. Player buys items with gold."""

    SLOT_W   = 216
    SLOT_H   = 152
    COLS     = 3
    PADDING  = 28

    RESTOCK_LIMIT = 3

    def __init__(self, floor_num: int, stat_tracker=None):
        self.floor_num    = floor_num
        self.stat_tracker = stat_tracker
        self.inventory: list[dict] = []
        self.sold:       list[bool] = []
        self.restock_count = 0
        self.restock()
        self.done = False

        # Particle pool for background ambience
        rng = random.Random(floor_num * 17 + 3)
        self._particles = [
            {
                "x":     rng.uniform(0, SCREEN_WIDTH),
                "y":     rng.uniform(0, SCREEN_HEIGHT),
                "vy":    rng.uniform(-0.4, -1.2),
                "vx":    rng.uniform(-0.3, 0.3),
                "r":     rng.randint(1, 3),
                "phase": rng.uniform(0, math.pi * 2),
                "col":   rng.choice([(180, 140, 255), (255, 210, 80), (100, 200, 255)]),
            }
            for _ in range(55)
        ]

    # ------------------------------------------------------------------
    def restock(self):
        self.inventory.clear()
        self.sold.clear()
        count = random.randint(3, 5)
        for _ in range(count):
            rarity = random.choices(
                ["common", "uncommon", "rare", "legendary"],
                weights=[40, 35, 20, 5], k=1)[0]
            item = random_item_by_rarity(rarity)
            self.inventory.append({"item": item, "cost": self._price(item)})
            self.sold.append(False)

    def _price(self, item: Item) -> int:
        base = {"common": 40, "uncommon": 90, "rare": 200, "legendary": 500}
        return int(base.get(item.rarity, 60) * (1 + (self.floor_num // 5) * 0.15))

    # ------------------------------------------------------------------
    def try_buy(self, index: int, player) -> str:
        if index < 0 or index >= len(self.inventory):
            return "Invalid selection."
        if self.sold[index]:
            return "Already sold!"
        entry = self.inventory[index]
        cost  = entry["cost"]
        item  = entry["item"]
        if player.gold < cost:
            return f"Not enough gold! (Need {cost})"
        player.gold -= cost
        self.sold[index] = True
        if self.stat_tracker:
            self.stat_tracker.record("gold_spent", floor=self.floor_num,
                                     gold_spent=cost, value=cost)
        msg = player.use_item(item)
        return f"Bought {item.name}! {msg}"

    # ------------------------------------------------------------------
    RESTOCK_COST = 50

    def try_restock(self, player) -> str:
        if self.restock_count >= self.RESTOCK_LIMIT:
            return f"Restock limit reached ({self.RESTOCK_LIMIT}x per shop)."
        if player.gold < self.RESTOCK_COST:
            return f"Not enough gold! (Need {self.RESTOCK_COST})"
        player.gold -= self.RESTOCK_COST
        self.restock()
        self.restock_count += 1
        remaining = self.RESTOCK_LIMIT - self.restock_count
        return f"Shop restocked! ({remaining} use{'s' if remaining != 1 else ''} left)"

    def handle_event(self, event: pygame.event.Event, player) -> str | None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            leave_rect   = pygame.Rect(SCREEN_WIDTH // 2 - 88, SCREEN_HEIGHT - 76,  176, 48)
            restock_rect = pygame.Rect(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT - 138, 240, 54)
            if leave_rect.collidepoint(mx, my):
                self.done = True
                return "leave"
            if restock_rect.collidepoint(mx, my):
                return self.try_restock(player)
            start_x = (SCREEN_WIDTH - (self.SLOT_W * self.COLS + self.PADDING * (self.COLS - 1))) // 2
            start_y = 186
            for i, entry in enumerate(self.inventory):
                col = i % self.COLS
                row = i // self.COLS
                sx  = start_x + col * (self.SLOT_W + self.PADDING)
                sy  = start_y + row * (self.SLOT_H + self.PADDING)
                if pygame.Rect(sx, sy, self.SLOT_W, self.SLOT_H).collidepoint(mx, my):
                    return self.try_buy(i, player)
        return None

    # ------------------------------------------------------------------
    @staticmethod
    def _draw_type_icon(surface, x, y, item_type, size=22):
        cx, cy = x + size // 2, y + size // 2
        if item_type == "potion":
            pygame.draw.rect(surface, (28, 200, 80),  (cx - 2, y + 3,  4,  size - 6))
            pygame.draw.rect(surface, (28, 200, 80),  (x + 3,  cy - 2, size - 6, 4))
            pygame.draw.rect(surface, (90, 255, 140), (cx - 1, y + 4,  2,  size - 8))
        elif item_type == "weapon":
            pygame.draw.line(surface, (210, 220, 240), (x + 3, y + size - 4), (x + size - 3, y + 3), 3)
            pygame.draw.line(surface, GOLD_COLOR, (cx - 5, cy + 2), (cx + 5, cy - 2), 2)
            pygame.draw.line(surface, (160, 120, 70), (x + 2, y + size - 3), (x + 5, y + size), 3)
        elif item_type == "armor":
            pts = [(cx, y + 2), (x + size - 2, y + 6),
                   (x + size - 2, cy + 2), (cx, y + size - 2),
                   (x + 2, cy + 2), (x + 2, y + 6)]
            pygame.draw.polygon(surface, (55, 105, 200), pts)
            pygame.draw.polygon(surface, (120, 175, 255), pts, 2)
        elif item_type == "buff":
            pts = [(cx + 4, y + 2), (cx - 3, cy), (cx + 2, cy), (cx - 4, y + size - 2)]
            pygame.draw.lines(surface, (255, 225, 55), False, pts, 2)
        elif item_type == "gold":
            pygame.draw.circle(surface, (185, 148, 18), (cx, cy), size // 2 - 1)
            pygame.draw.circle(surface, (255, 210, 55), (cx - 1, cy - 1), size // 2 - 3)
            pygame.draw.circle(surface, (255, 245, 140), (cx - 2, cy - 2), max(1, size // 2 - 5))

    @staticmethod
    def _draw_sword_icon(surface, x, y, size=24, flip=False):
        x1, x2 = (x + size, x) if flip else (x, x + size)
        cy = y + size // 2
        pygame.draw.line(surface, (200, 215, 235), (x1, cy + size // 4),
                         (x2, cy - size // 4), 3)
        gx = x1 + (x2 - x1) // 3
        pygame.draw.line(surface, GOLD_COLOR, (gx - 6, cy + 2), (gx + 6, cy - 2), 3)
        pygame.draw.line(surface, (145, 105, 65), (x1, cy + size // 4),
                         (x1 - (4 if not flip else -4), cy + size // 4 + 5), 4)

    # ------------------------------------------------------------------
    @staticmethod
    def _draw_merchant_npc(surface: pygame.Surface, cx: int, cy: int, t: float):
        """Draw a robed merchant NPC with staff and floating coin."""
        # Ground shadow
        sh = pygame.Surface((58, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 55), (0, 0, 58, 14))
        surface.blit(sh, (cx - 29, cy - 6))

        # Staff (left side, behind body)
        sx, sy_top = cx - 34, cy - 148
        bob = int(4 * math.sin(t * 1.3))
        pygame.draw.line(surface, (88, 66, 38), (sx + 2, cy - 8), (sx + 3, sy_top + bob + 8), 5)
        pygame.draw.line(surface, (120, 94, 56), (sx + 1, cy - 8), (sx + 1, sy_top + bob + 8), 2)
        # Staff orb glow
        for gr in range(16, 0, -4):
            ga = int(44 * (gr / 16) * (0.55 + 0.45 * math.sin(t * 2.4 + gr * 0.3)))
            gs = pygame.Surface((gr * 2 + 2, gr * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (90, 160, 255, ga), (gr + 1, gr + 1), gr)
            surface.blit(gs, (sx - gr + 2, sy_top + bob - gr))
        pygame.draw.circle(surface, (55, 110, 220), (sx + 2, sy_top + bob), 8)
        pygame.draw.circle(surface, (160, 210, 255), (sx, sy_top + bob - 2), 4)
        pygame.draw.circle(surface, (220, 240, 255), (sx - 1, sy_top + bob - 3), 2)

        # Robe body (wide tapered shape)
        body_pts = [
            (cx - 30, cy), (cx + 30, cy),
            (cx + 20, cy - 72), (cx - 20, cy - 72),
        ]
        pygame.draw.polygon(surface, (44, 30, 74), body_pts)
        pygame.draw.polygon(surface, (66, 48, 102), body_pts, 2)
        # Robe fold lines
        for fx, fy0, fy1 in [(-12, cy - 70, cy - 4), (10, cy - 70, cy - 4)]:
            rs = pygame.Surface((2, abs(fy1 - fy0)), pygame.SRCALPHA)
            rs.fill((60, 44, 90, 60))
            surface.blit(rs, (cx + fx, min(fy0, fy1)))

        # Belt
        by = cy - 46
        pygame.draw.rect(surface, (140, 110, 18), (cx - 22, by, 44, 8), border_radius=2)
        pygame.draw.rect(surface, (200, 162, 30), (cx - 19, by + 1, 38, 3))
        # Belt buckle
        pygame.draw.rect(surface, (190, 148, 24), (cx - 6, by - 2, 12, 12), border_radius=2)
        pygame.draw.rect(surface, (255, 210, 55), (cx - 4, by, 8, 7), border_radius=1)
        pygame.draw.circle(surface, (255, 240, 120), (cx, by + 3), 2)

        # Sleeves / hands
        for hx_off, flip in [(-26, -1), (26, 1)]:
            hx = cx + hx_off
            hy = cy - 34
            sl = pygame.Surface((20, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(sl, (54, 36, 84, 220), (0, 0, 20, 14))
            surface.blit(sl, (hx - 10, hy - 7))
            # Hand nub
            pygame.draw.circle(surface, (195, 168, 138), (hx + flip * 4, hy + 2), 5)
            pygame.draw.circle(surface, (215, 188, 158), (hx + flip * 3, hy + 1), 3)

        # Hood body (trapezoid over head)
        hood_pts = [
            (cx - 22, cy - 70), (cx + 22, cy - 70),
            (cx + 15, cy - 96), (cx - 15, cy - 96),
        ]
        pygame.draw.polygon(surface, (34, 22, 60), hood_pts)
        pygame.draw.polygon(surface, (56, 40, 88), hood_pts, 1)

        # Hood tip (animated sway)
        tip_sway = int(5 * math.sin(t * 1.5))
        tip_pts = [
            (cx - 12, cy - 94), (cx + 12, cy - 94),
            (cx + 6 + tip_sway, cy - 120), (cx - 2 + tip_sway, cy - 125),
        ]
        pygame.draw.polygon(surface, (34, 22, 60), tip_pts)
        pygame.draw.polygon(surface, (56, 40, 88), tip_pts, 1)

        # Face shadow inside hood
        face_s = pygame.Surface((32, 26), pygame.SRCALPHA)
        pygame.draw.ellipse(face_s, (14, 9, 24, 210), (0, 0, 32, 26))
        surface.blit(face_s, (cx - 16, cy - 96))

        # Glowing eyes
        eye_pulse = int(160 + 80 * math.sin(t * 2.8))
        for ex_off in [-7, 7]:
            ex, ey = cx + ex_off, cy - 84
            eg = pygame.Surface((12, 12), pygame.SRCALPHA)
            pygame.draw.circle(eg, (255, 200, 55, eye_pulse // 3), (6, 6), 6)
            surface.blit(eg, (ex - 6, ey - 6))
            pygame.draw.circle(surface, (255, 220, 70), (ex, ey), 2)

        # Floating coin in right hand
        coin_x = cx + 38 + int(5 * math.sin(t * 2.0))
        coin_y = cy - 42 + int(4 * math.cos(t * 1.7))
        coin_a = int(160 + 70 * math.sin(t * 3.2))
        cg = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(cg, (255, 210, 30, coin_a // 3), (12, 12), 12)
        surface.blit(cg, (coin_x - 12, coin_y - 12))
        pygame.draw.circle(surface, (168, 130, 14), (coin_x, coin_y), 8)
        pygame.draw.circle(surface, (245, 200, 48), (coin_x - 1, coin_y - 1), 6)
        pygame.draw.circle(surface, (255, 238, 130), (coin_x - 2, coin_y - 2), 3)

        # Cloak hem detail at bottom
        for hi in range(5):
            hx2 = cx - 28 + hi * 14
            hs = pygame.Surface((16, 8), pygame.SRCALPHA)
            pygame.draw.ellipse(hs, (56, 40, 88, 140), (0, 0, 16, 8))
            surface.blit(hs, (hx2, cy - 8))

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, player):
        now = pygame.time.get_ticks()
        t   = now / 1000.0
        cx  = SCREEN_WIDTH  // 2

        # ── Background gradient ───────────────────────────────────────────
        for row in range(SCREEN_HEIGHT):
            frac = row / SCREEN_HEIGHT
            r = int(8  + 10 * (1 - frac))
            g = int(6  +  6 * (1 - frac))
            b = int(22 + 18 * (1 - frac))
            pygame.draw.rect(surface, (r, g, b), (0, row, SCREEN_WIDTH, 1))

        # ── Ambient floating particles ────────────────────────────────────
        part_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for p in self._particles:
            p["x"] = (p["x"] + p["vx"]) % SCREEN_WIDTH
            p["y"] = (p["y"] + p["vy"]) % SCREEN_HEIGHT
            a = int(60 + 50 * abs(math.sin(t * 1.2 + p["phase"])))
            pygame.draw.circle(part_surf, (*p["col"], a),
                               (int(p["x"]), int(p["y"])), p["r"])
        surface.blit(part_surf, (0, 0))

        # ── Side decorative columns ───────────────────────────────────────
        for col_x in [30, SCREEN_WIDTH - 30]:
            for seg_y in range(50, SCREEN_HEIGHT - 50, 40):
                seg_a = int(40 + 20 * math.sin(t * 1.5 + seg_y * 0.04))
                seg_s = pygame.Surface((8, 28), pygame.SRCALPHA)
                seg_s.fill((*_C_BORDER, seg_a))
                pygame.draw.rect(seg_s, (*_C_ACCENT, seg_a + 20), (0, 0, 8, 28), 1, border_radius=2)
                surface.blit(seg_s, (col_x - 4, seg_y))
            pygame.draw.line(surface, (*_C_DIVIDER, 80),
                             (col_x, 50), (col_x, SCREEN_HEIGHT - 50), 1)

        # ── Merchant NPC character (right side) ──────────────────────────
        npc_x = SCREEN_WIDTH - 88
        npc_y = 530
        # Soft backdrop glow behind character
        bg_glow = pygame.Surface((110, 160), pygame.SRCALPHA)
        for gr in range(55, 0, -8):
            ga = int(18 * (gr / 55))
            pygame.draw.ellipse(bg_glow, (90, 60, 160, ga),
                                (55 - gr, 80 - gr, gr * 2, gr * 2))
        surface.blit(bg_glow, (npc_x - 55, npc_y - 130))
        self._draw_merchant_npc(surface, npc_x, npc_y, t)

        # ── Title banner ──────────────────────────────────────────────────
        font_big = pygame.font.SysFont("monospace", 36, bold=True)
        font_med = pygame.font.SysFont("monospace", 17)
        font_sm  = pygame.font.SysFont("monospace", 13)

        # Title glow
        pulse = 0.78 + 0.22 * math.sin(t * 2.0)
        tc    = (int(255 * pulse), int(210 * pulse), int(10 * pulse))
        for gd in range(6, 0, -2):
            gs = font_big.render("MERCHANT", True, (100, 68, 5))
            gs.set_alpha(int(25 + 10 * math.sin(t * 2.5)))
            for dx, dy in [(-gd, 0), (gd, 0), (0, -gd), (0, gd)]:
                surface.blit(gs, (cx - gs.get_width() // 2 + dx, 28 + dy))
        title = font_big.render("MERCHANT", True, tc)
        tw2   = title.get_width()
        self._draw_sword_icon(surface, cx - tw2 // 2 - 42, 30, size=28, flip=False)
        surface.blit(title, (cx - tw2 // 2, 28))
        self._draw_sword_icon(surface, cx + tw2 // 2 + 14, 30, size=28, flip=True)

        # Decorative line under title
        lw = tw2 + 100
        pygame.draw.line(surface, (120, 90, 10), (cx - lw // 2, 76), (cx + lw // 2, 76), 1)
        pygame.draw.polygon(surface, GOLD_COLOR, [(cx - 5, 72), (cx, 78), (cx + 5, 72)])

        # Gold display with coin and panel
        gold_pw = 200
        gold_px = cx - gold_pw // 2
        gp = pygame.Surface((gold_pw, 30), pygame.SRCALPHA)
        gp.fill((20, 16, 42, 180))
        pygame.draw.rect(gp, (*_C_BORDER, 160), (0, 0, gold_pw, 30), 1, border_radius=6)
        surface.blit(gp, (gold_px, 86))
        # Coin icon
        cix = gold_px + 10
        pygame.draw.circle(surface, (150, 115, 12), (cix + 8, 101), 7)
        pygame.draw.circle(surface, (225, 180, 28), (cix + 7, 100), 6)
        pygame.draw.circle(surface, (255, 230, 100), (cix + 6, 99), 3)
        gold_s = font_med.render(f"{player.gold} Gold", True, GOLD_COLOR)
        surface.blit(gold_s, (gold_px + gold_pw // 2 - gold_s.get_width() // 2, 90))

        # ── Item grid ─────────────────────────────────────────────────────
        start_x = (SCREEN_WIDTH - (self.SLOT_W * self.COLS + self.PADDING * (self.COLS - 1))) // 2
        start_y = 186
        mx2, my2 = pygame.mouse.get_pos()

        for i, entry in enumerate(self.inventory):
            col = i % self.COLS
            row = i // self.COLS
            sx  = start_x + col * (self.SLOT_W + self.PADDING)
            sy  = start_y + row * (self.SLOT_H + self.PADDING)
            rect = pygame.Rect(sx, sy, self.SLOT_W, self.SLOT_H)
            item = entry["item"]
            rc   = _RARITY_COL.get(item.rarity, GRAY)
            rg   = _RARITY_GLOW.get(item.rarity, GRAY)
            hov  = rect.collidepoint(mx2, my2) and not self.sold[i]

            # Hover glow
            if hov:
                for gd in range(8, 0, -2):
                    gls = pygame.Surface((self.SLOT_W + gd * 2, self.SLOT_H + gd * 2), pygame.SRCALPHA)
                    ga  = int(40 * (gd / 8) * (0.7 + 0.3 * math.sin(t * 4)))
                    pygame.draw.rect(gls, (*rg, ga),
                                     (0, 0, self.SLOT_W + gd * 2, self.SLOT_H + gd * 2),
                                     border_radius=12 + gd)
                    surface.blit(gls, (sx - gd, sy - gd))

            # Card background
            if self.sold[i]:
                bg_c = (18, 16, 28)
            elif hov:
                bg_c = (42, 36, 68)
            else:
                bg_c = (26, 22, 46)

            card_s = pygame.Surface((self.SLOT_W, self.SLOT_H), pygame.SRCALPHA)
            card_s.fill((*bg_c, 230))

            # Rarity border (glowing on hover/legendary)
            brd_w  = 2
            brd_a  = int(200 + 40 * math.sin(t * 3)) if item.rarity == "legendary" else 180
            if hov:
                brd_w = 3
            pygame.draw.rect(card_s, (*rc, brd_a), (0, 0, self.SLOT_W, self.SLOT_H),
                             brd_w, border_radius=10)
            # Inner subtle line
            pygame.draw.rect(card_s, (*rc, 50),    (3, 3, self.SLOT_W - 6, self.SLOT_H - 6),
                             1, border_radius=8)
            # Top shine
            shine_s = pygame.Surface((self.SLOT_W, self.SLOT_H // 3), pygame.SRCALPHA)
            shine_s.fill((255, 255, 255, 8 if not hov else 15))
            card_s.blit(shine_s, (0, 0))

            surface.blit(card_s, (sx, sy))

            if self.sold[i]:
                # SOLD stamp
                sold_bg = pygame.Surface((80, 30), pygame.SRCALPHA)
                sold_bg.fill((0, 0, 0, 120))
                pygame.draw.rect(sold_bg, (100, 80, 80, 180), (0, 0, 80, 30), 1, border_radius=4)
                surface.blit(sold_bg, (rect.centerx - 40, rect.centery - 15))
                sold_t = font_med.render("SOLD", True, (160, 120, 120))
                surface.blit(sold_t, (rect.centerx - sold_t.get_width() // 2,
                                      rect.centery - sold_t.get_height() // 2))
                continue

            # Type icon in top-right
            self._draw_type_icon(surface, rect.x + rect.w - 30, rect.y + 7, item.type, size=22)

            # Rarity tag
            rar_s  = font_sm.render(f"[{item.rarity.upper()}]", True, rc)
            surface.blit(rar_s, (rect.x + 10, rect.y + 10))

            # Item name (bold-ish via double render)
            name_c = (255, 255, 255) if hov else (220, 215, 240)
            nm_s   = font_med.render(item.name, True, (0, 0, 0))
            nm_s.set_alpha(100)
            surface.blit(nm_s, (rect.x + 11, rect.y + 34))
            nm_s2  = font_med.render(item.name, True, name_c)
            surface.blit(nm_s2, (rect.x + 10, rect.y + 33))

            # Description (wrapped to 30 chars, 2 lines max)
            desc = item.description
            lines = []
            while len(desc) > 0:
                lines.append(desc[:30])
                desc = desc[30:]
                if len(lines) >= 2:
                    break
            for li, line in enumerate(lines):
                ds = font_sm.render(line, True, (165, 158, 192))
                surface.blit(ds, (rect.x + 10, rect.y + 56 + li * 16))

            # Divider
            pygame.draw.line(surface, (*rc, 60),
                             (rect.x + 8, rect.y + self.SLOT_H - 36),
                             (rect.x + self.SLOT_W - 8, rect.y + self.SLOT_H - 36), 1)

            # Price
            can_afford = player.gold >= entry["cost"]
            cost_c     = (70, 225, 100) if can_afford else (220, 65, 65)
            cost_s     = font_med.render(f"{entry['cost']} G", True, cost_c)
            surface.blit(cost_s, (rect.x + 10, rect.y + self.SLOT_H - 28))
            if not can_afford:
                lock_s = font_sm.render("✗ insufficient", True, (180, 55, 55))
                surface.blit(lock_s, (rect.x + 70, rect.y + self.SLOT_H - 27))

            # Legendary spinning sparkles around card
            if item.rarity == "legendary":
                for sp_i in range(6):
                    sp_a = t * 1.8 + sp_i * math.pi * 2 / 6
                    sp_r = int(self.SLOT_W // 2 + 12)
                    sp_x = rect.centerx + int(math.cos(sp_a) * sp_r)
                    sp_y = rect.centery + int(math.sin(sp_a) * sp_r * 0.4)
                    al   = int(140 + 80 * math.sin(t * 3 + sp_i))
                    ss2  = pygame.Surface((5, 5), pygame.SRCALPHA)
                    pygame.draw.circle(ss2, (255, 225, 70, al), (2, 2), 2)
                    surface.blit(ss2, (sp_x - 2, sp_y - 2))

        # ── Restock button (wider 2-line layout, no icon overlap) ──────────
        RBW, RBH   = 240, 54
        restock_rect = pygame.Rect(cx - RBW // 2, SCREEN_HEIGHT - 138, RBW, RBH)
        rhov        = restock_rect.collidepoint(*pygame.mouse.get_pos())
        uses_left   = max(0, self.RESTOCK_LIMIT - self.restock_count)
        exhausted   = (uses_left == 0)
        can_restock = (player.gold >= self.RESTOCK_COST) and not exhausted

        # Hover glow
        if rhov and can_restock:
            for gd in range(8, 0, -2):
                gls3 = pygame.Surface((RBW + gd * 2, RBH + gd * 2), pygame.SRCALPHA)
                ga3  = int(38 * (gd / 8))
                pygame.draw.rect(gls3, (40, 160, 80, ga3),
                                 (0, 0, RBW + gd * 2, RBH + gd * 2), border_radius=12 + gd)
                surface.blit(gls3, (restock_rect.x - gd, restock_rect.y - gd))

        rb_bg = (38, 88, 52) if (rhov and can_restock) else \
                (24, 56, 34) if can_restock else (38, 28, 30)
        pygame.draw.rect(surface, rb_bg, restock_rect, border_radius=10)
        # Top-shine strip
        rshine = pygame.Surface((RBW, RBH // 2), pygame.SRCALPHA)
        rshine.fill((255, 255, 255, 14 if rhov and can_restock else 7))
        surface.blit(rshine, (restock_rect.x, restock_rect.y))
        rb_border = (80, 210, 100) if (rhov and can_restock) else \
                    (42, 130, 64) if can_restock else (70, 48, 55)
        pygame.draw.rect(surface, rb_border, restock_rect, 2, border_radius=10)

        # Line 1: main label — centred in upper half of button
        rc_main  = WHITE if can_restock else (130, 95, 95)
        line1    = font_med.render(f"Restock  {self.RESTOCK_COST} G", True, rc_main)
        surface.blit(line1, (restock_rect.centerx - line1.get_width() // 2,
                             restock_rect.y + 8))
        # Line 2: uses remaining — centred in lower half
        if exhausted:
            cnt_col   = (170, 60, 60)
            cnt_label = "No uses remaining"
        else:
            cnt_col   = (100, 190, 120)
            cnt_label = f"({uses_left} of {self.RESTOCK_LIMIT} uses left)"
        line2 = font_sm.render(cnt_label, True, cnt_col)
        surface.blit(line2, (restock_rect.centerx - line2.get_width() // 2,
                             restock_rect.y + RBH - font_sm.get_height() - 7))

        # ── Leave button ───────────────────────────────────────────────────
        leave_rect = pygame.Rect(cx - 88, SCREEN_HEIGHT - 76, 176, 48)
        lhov = leave_rect.collidepoint(*pygame.mouse.get_pos())
        # Glow on hover
        if lhov:
            for gd in range(6, 0, -2):
                gls2 = pygame.Surface((176 + gd * 2, 48 + gd * 2), pygame.SRCALPHA)
                ga2  = int(45 * (gd / 6))
                pygame.draw.rect(gls2, (100, 70, 170, ga2),
                                 (0, 0, 176 + gd * 2, 48 + gd * 2), border_radius=10 + gd)
                surface.blit(gls2, (cx - 88 - gd, SCREEN_HEIGHT - 76 - gd))

        lb_bg  = (75, 54, 120) if lhov else (52, 36, 90)
        pygame.draw.rect(surface, lb_bg, leave_rect, border_radius=10)
        shine2 = pygame.Surface((176, 24), pygame.SRCALPHA)
        shine2.fill((255, 255, 255, 12 if not lhov else 22))
        surface.blit(shine2, (cx - 88, SCREEN_HEIGHT - 76))
        pygame.draw.rect(surface, GOLD_COLOR if lhov else _C_BORDER, leave_rect, 2, border_radius=10)
        lv_s = font_med.render("Leave Shop", True, WHITE)
        surface.blit(lv_s, (leave_rect.centerx - lv_s.get_width() // 2,
                             leave_rect.centery - lv_s.get_height() // 2))
