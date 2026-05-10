"""
enemy.py - Enemy and Boss classes with BFS pathfinding
"""
from __future__ import annotations
import pygame
import random
import math
from collections import deque
from src.constants import (
    ENEMY_BASE_HP, ENEMY_BASE_ATK, ENEMY_BASE_SPEED,
    ENEMY_EXP_BASE, ENEMY_AGGRO_RADIUS,
    BOSS_HP_MULT, BOSS_ATK_MULT,
    TILE_SIZE, RED, ORANGE, PURPLE, WHITE, GREEN
)
from src.item import random_item_by_rarity
from src.sprite_loader import make_all_anims, SpriteAnim


ENEMY_TYPES = {
    # dmg_ratio: ATK = max_hp * dmg_ratio (so damage scales with HP)
    "armored_orc":      {"color": (80,  140, 80),  "hp_mult": 1.8, "speed_mult": 0.9, "exp_mult": 1.5, "dmg_ratio": 0.14},
    "armored_skeleton": {"color": (220, 220, 200), "hp_mult": 1.2, "speed_mult": 1.0, "exp_mult": 1.1, "dmg_ratio": 0.17},
    "werebear":         {"color": (140, 100, 60),  "hp_mult": 2.0, "speed_mult": 0.8, "exp_mult": 1.6, "dmg_ratio": 0.15},
}

_SPRITE_CHAR: dict[str, str] = {
    "armored_orc":      "Armored Orc",
    "armored_skeleton": "Armored Skeleton",
    "werebear":         "Werebear",
}


def _draw_slime(surface, x, y, color, elite):
    # Shadow
    sh = pygame.Surface((34, 7), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 50), (0, 0, 34, 7))
    surface.blit(sh, (x - 17, y + 12))
    # Body blob
    hi = tuple(min(255, c + 70) for c in color)
    dk = tuple(max(0, c - 40) for c in color)
    pygame.draw.ellipse(surface, dk,  (x - 18, y - 6,  36, 24))
    pygame.draw.ellipse(surface, color,(x - 17, y - 8,  34, 22))
    # Shine
    pygame.draw.ellipse(surface, hi,  (x - 10, y - 7,  12,  7))
    # Eyes
    for ex, ey in ((x - 7, y - 2), (x + 7, y - 2)):
        pygame.draw.circle(surface, WHITE, (ex, ey), 5)
        pygame.draw.circle(surface, (30, 30, 30), (ex + 1, ey + 1), 3)
        pygame.draw.circle(surface, WHITE, (ex - 1, ey - 1), 1)
    # Smile
    if not elite:
        for sx2 in range(-4, 5, 2):
            pygame.draw.circle(surface, dk, (x + sx2, y + 6), 1)
    else:
        # Elite: angry brows
        pygame.draw.line(surface, (20, 20, 20), (x - 11, y - 8), (x - 4, y - 5), 2)
        pygame.draw.line(surface, (20, 20, 20), (x + 11, y - 8), (x + 4, y - 5), 2)


def _draw_goblin(surface, x, y, elite):
    skin = (90, 160, 60) if not elite else (50, 110, 30)
    dk   = (50, 100, 30) if not elite else (25, 65, 10)
    # Shadow
    sh = pygame.Surface((28, 6), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 50), (0, 0, 28, 6))
    surface.blit(sh, (x - 14, y + 16))
    # Legs
    pygame.draw.rect(surface, (55, 35, 15), (x - 8, y + 7, 6, 10), border_radius=1)
    pygame.draw.rect(surface, (55, 35, 15), (x + 2, y + 7, 6, 10), border_radius=1)
    # Body
    pygame.draw.rect(surface, skin, (x - 9, y - 6, 18, 15), border_radius=3)
    pygame.draw.rect(surface, dk,   (x - 7, y - 4, 14, 9),  border_radius=2)  # loincloth hint
    # Club
    pygame.draw.line(surface, (100, 70, 30), (x + 9, y - 2), (x + 18, y - 12), 3)
    pygame.draw.circle(surface, (80, 50, 20), (x + 18, y - 12), 5)
    pygame.draw.circle(surface, (60, 35, 10), (x + 18, y - 12), 5, 2)
    # Arms
    pygame.draw.rect(surface, skin, (x - 13, y - 5, 6, 10), border_radius=2)
    pygame.draw.rect(surface, skin, (x + 7,  y - 5, 6, 10), border_radius=2)
    # Head
    pygame.draw.circle(surface, skin, (x, y - 15), 10)
    # Ears (pointy)
    pygame.draw.polygon(surface, skin, [(x - 10, y - 20), (x - 17, y - 28), (x - 5, y - 18)])
    pygame.draw.polygon(surface, skin, [(x + 10, y - 20), (x + 17, y - 28), (x + 5, y - 18)])
    # Eyes
    ec = RED if elite else (220, 50, 50)
    pygame.draw.circle(surface, ec, (x - 4, y - 16), 3)
    pygame.draw.circle(surface, ec, (x + 4, y - 16), 3)
    pygame.draw.circle(surface, (10, 10, 10), (x - 4, y - 16), 1)
    pygame.draw.circle(surface, (10, 10, 10), (x + 4, y - 16), 1)
    # Angry brows
    pygame.draw.line(surface, (20, 20, 20), (x - 8, y - 20), (x - 1, y - 18), 2)
    pygame.draw.line(surface, (20, 20, 20), (x + 8, y - 20), (x + 1, y - 18), 2)


def _draw_skeleton(surface, x, y, elite):
    bone = (220, 215, 200) if not elite else (180, 175, 255)
    drk  = (140, 130, 115) if not elite else (100, 95, 180)
    # Shadow
    sh = pygame.Surface((26, 6), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 50), (0, 0, 26, 6))
    surface.blit(sh, (x - 13, y + 16))
    # Leg bones
    pygame.draw.rect(surface, bone, (x - 8, y + 5, 5, 14), border_radius=2)
    pygame.draw.rect(surface, bone, (x + 3, y + 5, 5, 14), border_radius=2)
    pygame.draw.circle(surface, bone, (x - 5, y + 5),  4)
    pygame.draw.circle(surface, bone, (x + 5, y + 5),  4)
    pygame.draw.circle(surface, bone, (x - 5, y + 18), 4)
    pygame.draw.circle(surface, bone, (x + 5, y + 18), 4)
    # Ribcage
    pygame.draw.rect(surface, bone, (x - 9, y - 7, 18, 14), border_radius=2)
    for ry in range(y - 4, y + 6, 4):
        pygame.draw.line(surface, drk, (x - 7, ry), (x + 7, ry), 1)
    # Arm bones
    for side in (-1, 1):
        ax = x + side * 12
        pygame.draw.line(surface, bone, (x + side * 9, y - 4), (ax, y + 4), 3)
        pygame.draw.circle(surface, bone, (ax, y + 4), 4)
    # Skull
    pygame.draw.circle(surface, bone, (x, y - 16), 10)
    pygame.draw.rect(surface, bone, (x - 8, y - 14, 16, 6))  # jaw
    # Eye sockets
    pygame.draw.circle(surface, (10, 10, 10), (x - 4, y - 18), 4)
    pygame.draw.circle(surface, (10, 10, 10), (x + 4, y - 18), 4)
    if elite:
        pygame.draw.circle(surface, (130, 100, 255), (x - 4, y - 18), 2)
        pygame.draw.circle(surface, (130, 100, 255), (x + 4, y - 18), 2)
    # Teeth
    for tx2 in (x - 5, x - 2, x + 1, x + 4):
        pygame.draw.rect(surface, bone, (tx2, y - 10, 2, 4))


def _draw_orc(surface, x, y, elite):
    skin = (60, 130, 55) if not elite else (30, 85, 30)
    dk   = (35, 90, 30) if not elite else (15, 55, 15)
    arm  = (55, 120, 50) if not elite else (25, 75, 25)
    # Shadow
    sh = pygame.Surface((36, 8), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 55), (0, 0, 36, 8))
    surface.blit(sh, (x - 18, y + 16))
    # Thick legs
    pygame.draw.rect(surface, dk, (x - 11, y + 6, 9, 14), border_radius=2)
    pygame.draw.rect(surface, dk, (x + 2,  y + 6, 9, 14), border_radius=2)
    # Large body
    pygame.draw.rect(surface, skin, (x - 14, y - 8, 28, 16), border_radius=4)
    # Chest armor
    pygame.draw.rect(surface, (40, 65, 40), (x - 10, y - 6, 20, 12), border_radius=3)
    pygame.draw.line(surface, (30, 50, 30), (x, y - 6), (x, y + 6), 2)
    # Thick arms
    pygame.draw.rect(surface, arm, (x - 20, y - 7, 8, 14), border_radius=3)
    pygame.draw.rect(surface, arm, (x + 12, y - 7, 8, 14), border_radius=3)
    # Big head
    pygame.draw.circle(surface, skin, (x, y - 17), 12)
    # Tusks
    pygame.draw.rect(surface, (230, 225, 210), (x - 8, y - 9, 4, 7),  border_radius=1)
    pygame.draw.rect(surface, (230, 225, 210), (x + 4, y - 9, 4, 7),  border_radius=1)
    # Eyes
    ec = (255, 60, 40) if elite else (220, 50, 30)
    pygame.draw.circle(surface, ec, (x - 5, y - 19), 4)
    pygame.draw.circle(surface, ec, (x + 5, y - 19), 4)
    pygame.draw.circle(surface, (10, 10, 10), (x - 5, y - 19), 2)
    pygame.draw.circle(surface, (10, 10, 10), (x + 5, y - 19), 2)
    # Angry brows
    pygame.draw.line(surface, (20, 20, 20), (x - 10, y - 24), (x - 2, y - 21), 3)
    pygame.draw.line(surface, (20, 20, 20), (x + 10, y - 24), (x + 2, y - 21), 3)


def _draw_wraith(surface, x, y, elite):
    col  = (130, 60, 210) if not elite else (180, 80, 255)
    glow = (170, 100, 240) if not elite else (220, 140, 255)
    # Wispy tail (fading rects)
    for i, (ox, oy, ow, oh, al) in enumerate([
        (0, 4, 18, 14, 120), (-3, 10, 12, 10, 80), (2, 16, 8, 8, 50)
    ]):
        ts = pygame.Surface((ow, oh), pygame.SRCALPHA)
        pygame.draw.ellipse(ts, col + (al,), (0, 0, ow, oh))
        surface.blit(ts, (x - ow // 2 + ox, y + oy))
    # Robe body
    rs = pygame.Surface((30, 22), pygame.SRCALPHA)
    pygame.draw.ellipse(rs, col + (200,), (0, 0, 30, 22))
    surface.blit(rs, (x - 15, y - 10))
    # Outer glow ring
    gs = pygame.Surface((38, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(gs, glow + (60,), (0, 0, 38, 30))
    surface.blit(gs, (x - 19, y - 14))
    # Glowing eyes
    for ex, ey in ((x - 6, y - 10), (x + 6, y - 10)):
        pygame.draw.circle(surface, (255, 240, 80), (ex, ey), 5)
        pygame.draw.circle(surface, (10,  10,  10), (ex, ey), 2)
        gs2 = pygame.Surface((14, 14), pygame.SRCALPHA)
        pygame.draw.circle(gs2, (255, 240, 80, 80), (7, 7), 6)
        surface.blit(gs2, (ex - 7, ey - 7))
    # Claws (wispy hands)
    for side in (-1, 1):
        hx, hy = x + side * 16, y - 2
        pygame.draw.line(surface, glow, (x + side * 12, y - 4), (hx, hy), 2)
        for ci in range(3):
            ang_off = (ci - 1) * 6
            pygame.draw.line(surface, glow,
                             (hx, hy), (hx + side * 4, hy - 5 + ang_off), 1)


_DMG_FONT: object = None

def _get_dmg_font():
    global _DMG_FONT
    if _DMG_FONT is None:
        _DMG_FONT = pygame.font.SysFont("monospace", 15, bold=True)
    return _DMG_FONT


def _bfs_next_step(grid_w, grid_h, walls_set, sx, sy, tx, ty):
    """BFS on tile grid. Returns (dx, dy) direction toward target, or (0,0)."""
    if (sx, sy) == (tx, ty):
        return 0, 0
    queue   = deque()
    visited = {(sx, sy): None}
    queue.append((sx, sy))
    while queue:
        cx, cy = queue.popleft()
        for nx, ny in [(cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)]:
            if (nx, ny) in visited:
                continue
            if nx < 0 or ny < 0 or nx >= grid_w or ny >= grid_h:
                continue
            if (nx, ny) in walls_set:
                continue
            visited[(nx, ny)] = (cx, cy)
            if (nx, ny) == (tx, ty):
                # Trace back
                step = (nx, ny)
                while visited[step] != (sx, sy):
                    step = visited[step]
                return step[0] - sx, step[1] - sy
            queue.append((nx, ny))
    return 0, 0


class Enemy:
    """Base enemy class with BFS pathfinding."""

    SIZE = TILE_SIZE - 8

    def __init__(self, x: int, y: int, floor_num: int, enemy_type: str = None,
                 player_atk: int = 15):
        if enemy_type is None:
            enemy_type = random.choice(list(ENEMY_TYPES.keys()))
        self.enemy_type = enemy_type
        defn = ENEMY_TYPES[enemy_type]

        floor_scale  = 1.0 + (floor_num - 1) * 0.12
        # HP scales with both floor and player's current ATK (so killing is never trivial)
        atk_factor   = (max(15, player_atk) / 15.0) ** 0.50
        self.floor_num  = floor_num
        self.max_hp     = int(ENEMY_BASE_HP * defn["hp_mult"] * floor_scale * atk_factor)
        self.hp         = self.max_hp
        # ATK derived from own max_hp so tankier monsters hit harder
        self.attack     = max(5, int(self.max_hp * defn["dmg_ratio"]))
        self.speed      = ENEMY_BASE_SPEED * defn["speed_mult"]
        self.exp_reward = int(ENEMY_EXP_BASE * defn["exp_mult"] * floor_scale)
        self.color      = defn["color"]

        self.x = float(x)
        self.y = float(y)
        self.w = self.SIZE
        self.h = self.SIZE

        self.alive        = True
        self.aggro        = False
        self.attack_cd    = 0         # ms cooldown
        self.attack_rate  = 800       # ms between attacks
        self.attack_pattern = "chase" # could extend to "ranged", "patrol"

        # BFS path refresh
        self._path_timer = 0
        self._path_dir   = (0, 0)

        # Hit feedback
        self._hit_flash  = 0      # ms remaining white flash
        self._dmg_pops: list[tuple] = []   # (x, y, text, start_ms)

        # Sprite animation
        char = _SPRITE_CHAR.get(self.enemy_type)
        self._anims: dict[str, SpriteAnim] = make_all_anims(char, 124) if char else {}
        self._anim_state  = "idle"
        self._flip        = False
        self._last_draw_t = pygame.time.get_ticks()

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - self.w//2, int(self.y) - self.h//2, self.w, self.h)

    # ------------------------------------------------------------------
    def choose_action(self, player, walls_set, grid_w, grid_h,
                      curse_type: str, current_time_ms: int):
        dist = math.hypot(player.x - self.x, player.y - self.y)
        speed_mult = 2.0 if curse_type == "fast_enemies" else 1.0

        if dist < ENEMY_AGGRO_RADIUS:
            self.aggro = True

        if not self.aggro:
            return

        # BFS refresh every 400ms
        if current_time_ms - self._path_timer > 400:
            tx = int(player.x) // TILE_SIZE
            ty = int(player.y) // TILE_SIZE
            sx = int(self.x)   // TILE_SIZE
            sy = int(self.y)   // TILE_SIZE
            self._path_dir = _bfs_next_step(grid_w, grid_h, walls_set, sx, sy, tx, ty)
            self._path_timer = current_time_ms

        _ox, _oy = self.x, self.y
        dx, dy = self._path_dir
        if dx != 0 or dy != 0:
            length = math.hypot(dx, dy) or 1
            move_speed = self.speed * speed_mult * 2.5
            new_x = self.x + (dx / length) * move_speed
            new_y = self.y + (dy / length) * move_speed
            if not self._hits_wall(new_x, self.y, walls_set):
                self.x = new_x
            if not self._hits_wall(self.x, new_y, walls_set):
                self.y = new_y

        # Animation state based on movement
        _moved = abs(self.x - _ox) > 0.1 or abs(self.y - _oy) > 0.1
        if _moved:
            if self.x > _ox + 0.1:
                self._flip = False
            elif self.x < _ox - 0.1:
                self._flip = True
        if self._anim_state not in ("attack", "hurt"):
            self._anim_state = "walk" if _moved else "idle"
        elif self._anims.get(self._anim_state) and self._anims[self._anim_state].done:
            self._anim_state = "walk" if _moved else "idle"

    def _hits_wall(self, cx, cy, walls_set) -> bool:
        hw, hh = self.w // 2, self.h // 2
        l, r = int(cx) - hw, int(cx) + hw - 1
        t, b = int(cy) - hh, int(cy) + hh - 1
        for tc in range(l // TILE_SIZE, r // TILE_SIZE + 1):
            for tr in range(t // TILE_SIZE, b // TILE_SIZE + 1):
                if (tc, tr) in walls_set:
                    return True
        return False

    # ------------------------------------------------------------------
    def try_attack(self, player, current_time_ms: int, curse_type: str):
        if current_time_ms - self.attack_cd < self.attack_rate:
            return 0
        if self.rect.inflate(8, 8).colliderect(player.rect):
            self.attack_cd   = current_time_ms
            self._anim_state = "attack"
            if "attack" in self._anims:
                self._anims["attack"].reset()
            return player.take_damage(self.attack, curse_type)
        return 0

    # ------------------------------------------------------------------
    def take_damage(self, amount: int) -> int:
        actual = max(1, amount)
        self.hp -= actual
        self._hit_flash = 180
        if self._anim_state != "attack":
            self._anim_state = "hurt"
            if "hurt" in self._anims:
                self._anims["hurt"].reset()
        self._dmg_pops.append(
            (self.x, float(self.y - self.h // 2), str(actual), pygame.time.get_ticks())
        )
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
        return actual

    # ------------------------------------------------------------------
    def drop_loot(self, floor_num: int, curse_type: str) -> list:
        """Return list of Item objects dropped on death."""
        drops = []
        drop_chance = 0.3 if curse_type == "poor_loot" else 0.6
        if random.random() < drop_chance:
            drops.append(random_item_by_rarity())
        return drops

    # ------------------------------------------------------------------
    def on_death(self, player, combo_system, stat_tracker, floor_num: int,
                 curse_type: str) -> list:
        """Handle death: give EXP/gold, record stats, return drops."""
        now = pygame.time.get_ticks()
        multiplier = combo_system.register_kill(now)
        exp_gain  = int(self.exp_reward  * multiplier)
        gold_gain = int(self.exp_reward // 5 * multiplier)

        player.gain_exp(exp_gain)
        player.gold += gold_gain
        player.kills += 1

        stat_tracker.record("enemies_defeated",
                            floor=floor_num, enemy_type=self.enemy_type,
                            value=1)
        stat_tracker.record("combo_count",
                            floor=floor_num,
                            combo_count=combo_system.combo_count,
                            value=combo_system.combo_count)

        return self.drop_loot(floor_num, curse_type)

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        x, y = int(self.x), int(self.y)
        elite = self.floor_num >= 10

        # Advance animation
        now = pygame.time.get_ticks()
        dt_ms = now - self._last_draw_t
        self._last_draw_t = now
        if self._anim_state in self._anims:
            self._anims[self._anim_state].update(dt_ms)

        # Draw sprite frame (with shadow) or fallback
        frame = self._anims[self._anim_state].current(flip=self._flip) if self._anim_state in self._anims else None
        if frame:
            fw, fh = frame.get_size()
            sh = pygame.Surface((fw // 2 + 10, 9), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 50), (0, 0, sh.get_width(), 9))
            surface.blit(sh, (x - sh.get_width() // 2, y + int(fh * 0.10)))
            surface.blit(frame, (x - fw // 2, y - fh // 2))
        else:
            if self.enemy_type == "slime":
                _draw_slime(surface, x, y, self.color, elite)
            elif self.enemy_type == "goblin":
                _draw_goblin(surface, x, y, elite)
            elif self.enemy_type == "skeleton":
                _draw_skeleton(surface, x, y, elite)
            elif self.enemy_type == "orc":
                _draw_orc(surface, x, y, elite)
            elif self.enemy_type == "wraith":
                _draw_wraith(surface, x, y, elite)
            else:
                pygame.draw.rect(surface, self.color, self.rect, border_radius=4)

        # Elite aura glow (no hard border — just soft pulsing halo)
        if elite:
            t_ms  = pygame.time.get_ticks()
            pulse = 0.55 + 0.45 * math.sin(t_ms / 220.0)
            # Multi-layer glow: large soft outer + tighter inner
            for rw, rh, base_a in [(88, 96, 45), (70, 78, 70), (56, 64, 55)]:
                gs = pygame.Surface((rw + 14, rh + 14), pygame.SRCALPHA)
                a  = int(base_a * pulse)
                pygame.draw.ellipse(gs, (255, 200, 0, max(0, a)), (0, 0, rw + 14, rh + 14))
                surface.blit(gs, (x - (rw + 14) // 2, (y - 4) - (rh + 14) // 2))

        # HP bar (positioned above sprite, not hitbox)
        bw = self.w
        filled = int(bw * self.hp / self.max_hp)
        by = y - 38
        pygame.draw.rect(surface, (120, 0, 0),   (x - bw // 2, by, bw, 4))
        pygame.draw.rect(surface, (220, 60, 60),  (x - bw // 2, by, filled, 4))

        # Advance hit flash timer (keep for timing logic, no visual)
        if self._hit_flash > 0:
            self._hit_flash = max(0, self._hit_flash - 16)

        # Floating damage numbers
        now = pygame.time.get_ticks()
        font = _get_dmg_font()
        i = 0
        while i < len(self._dmg_pops):
            px, py, txt, t0 = self._dmg_pops[i]
            elapsed = now - t0
            if elapsed > 900:
                self._dmg_pops.pop(i)
                continue
            progress = elapsed / 900
            fy    = int(py - 28 * progress)
            alpha = max(0, 255 - int(255 * progress * 1.2))
            ds = font.render(txt, True, (255, 230, 60))
            ds.set_alpha(alpha)
            surface.blit(ds, (int(px) - ds.get_width() // 2, fy))
            i += 1


# ======================================================================
class Boss(Enemy):
    """Multi-phase boss — extends Enemy with phase transitions and special attacks."""

    def __init__(self, x: int, y: int, floor_num: int, player_atk: int = 15):
        super().__init__(x, y, floor_num, "armored_orc", player_atk)
        # Override stats — boss HP also scales with player ATK
        atk_factor  = (max(15, player_atk) / 15.0) ** 0.50
        self.max_hp = int(ENEMY_BASE_HP * BOSS_HP_MULT * (1 + (floor_num-1)*0.15) * atk_factor)
        self.hp     = self.max_hp
        # Boss ATK scales with floor only (not HP) — high HP is the challenge
        self.attack = max(15, int(ENEMY_BASE_ATK * BOSS_ATK_MULT * (1 + (floor_num-1)*0.10)))
        self.exp_reward *= 5
        self.color      = (180, 30, 180)
        self.w          = TILE_SIZE + 16
        self.h          = TILE_SIZE + 16
        # Override sprite — Orc rider (boss), scaled larger
        self._anims = make_all_anims("Orc rider", 152)
        self._vfx: list = []   # [(type, x, y, start_ms), ...]

        self.phase             = 1
        self.enrage_timer      = 0
        self.special_attacks   = ["slam"]
        self.special_cd        = 0
        self.special_rate      = 3000  # ms

        self._summon_cd        = 0
        self._summon_rate      = 9000  # ms between summon waves
        self.pending_spawns:   list    = []

        self.attack_rate = 600   # faster

    # ------------------------------------------------------------------
    def phase_transition(self):
        """Transition to phase 2 at 50% HP."""
        self.phase      = 2
        self.speed     *= 1.4
        self.attack     = int(self.attack * 1.3)
        self.attack_rate = 400
        self.color      = (220, 60, 30)

    # ------------------------------------------------------------------
    def try_attack(self, player, current_time_ms: int, curse_type: str) -> int:
        if current_time_ms - self.attack_cd < self.attack_rate:
            return 0
        if self.rect.inflate(14, 14).colliderect(player.rect):
            self.attack_cd   = current_time_ms
            self._anim_state = "attack"
            if "attack" in self._anims:
                self._anims["attack"].reset()
            self._vfx.append(("slash", self.x, self.y, current_time_ms))
            return player.take_damage(self.attack, curse_type)
        return 0

    # ------------------------------------------------------------------
    def special_attack(self, player, current_time_ms: int) -> int:
        """Slam shockwave attack with VFX. Returns damage dealt."""
        if current_time_ms - self.special_cd < self.special_rate:
            return 0
        self.special_cd = current_time_ms
        dist = math.hypot(player.x - self.x, player.y - self.y)
        vtype = "slam_p2" if self.phase == 2 else "slam"
        self._vfx.append((vtype, self.x, self.y, current_time_ms))
        if dist < 140:
            return player.take_damage(int(self.attack * 1.8))
        return 0

    # ------------------------------------------------------------------
    def try_summon(self, walls_set, grid_w: int, grid_h: int,
                   current_time_ms: int):
        """Spawn a wave of minions around the boss. Fully guarded against errors."""
        try:
            if current_time_ms - self._summon_cd < self._summon_rate:
                return
            if not walls_set or grid_w <= 0 or grid_h <= 0:
                return
            self._summon_cd = current_time_ms
            count = 3 if self.phase == 2 else 2
            spawned = 0
            for _ in range(count):
                for _attempt in range(30):
                    ox = int(self.x) + random.randint(-3, 3) * TILE_SIZE
                    oy = int(self.y) + random.randint(-3, 3) * TILE_SIZE
                    tx = ox // TILE_SIZE
                    ty = oy // TILE_SIZE
                    if (tx, ty) not in walls_set and 0 < tx < grid_w - 1 and 0 < ty < grid_h - 1:
                        try:
                            minion = Enemy(ox, oy, self.floor_num, player_atk=max(1, self.attack // 2))
                            minion.aggro = True
                            self.pending_spawns.append(minion)
                            spawned += 1
                        except Exception:
                            pass
                        break
            if spawned > 0:
                self._vfx.append(("summon_burst", self.x, self.y, current_time_ms))
        except Exception:
            pass   # summon failure is non-fatal

    # ------------------------------------------------------------------
    def choose_action(self, player, walls_set, grid_w, grid_h,
                      curse_type: str, current_time_ms: int):
        # Phase check
        if self.phase == 1 and self.hp < self.max_hp * 0.5:
            self.phase_transition()
        self.special_attack(player, current_time_ms)
        self.try_summon(walls_set, grid_w, grid_h, current_time_ms)
        super().choose_action(player, walls_set, grid_w, grid_h,
                              curse_type, current_time_ms)

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        x, y = int(self.x), int(self.y)
        p2 = (self.phase == 2)

        # Advance animation
        now = pygame.time.get_ticks()
        dt_ms = now - self._last_draw_t
        self._last_draw_t = now
        if self._anim_state in self._anims:
            self._anims[self._anim_state].update(dt_ms)

        # ── Slam VFX (renders under sprite) ───────────────────────────
        now_v = pygame.time.get_ticks()
        alive_vfx = []
        for vtype, vx, vy, vt in self._vfx:
            dur = 800 if "summon" in vtype else 650 if "slam" in vtype else 320
            elapsed = now_v - vt
            if elapsed >= dur:
                continue
            alive_vfx.append((vtype, vx, vy, vt))
            prog = elapsed / dur

            if "slam" in vtype:
                fire = (vtype == "slam_p2")
                ring_col  = (255, 110, 20) if fire else (160, 200, 255)
                inner_col = (255, 210, 80) if fire else (220, 240, 255)
                for ri in range(3):
                    rp = max(0.0, prog - ri * 0.18)
                    if rp <= 0:
                        continue
                    rad = int(16 + 150 * rp)
                    alpha = int(220 * (1 - rp))
                    rs = pygame.Surface((rad * 2 + 14, rad * 2 + 14), pygame.SRCALPHA)
                    pygame.draw.circle(rs, (*ring_col, alpha),
                                       (rad + 7, rad + 7), rad, max(1, 4 - ri))
                    pygame.draw.circle(rs, (*inner_col, alpha // 2),
                                       (rad + 7, rad + 7), max(1, rad - 5), 3)
                    surface.blit(rs, (int(vx) - rad - 7, int(vy) - rad - 7))
                if prog < 0.38:
                    spark_col = (255, 210, 60) if fire else (190, 225, 255)
                    for si in range(10):
                        ang_s = si * math.pi * 2 / 10 + prog * 3
                        dist_s = int(12 + 110 * prog)
                        sx2 = int(vx + math.cos(ang_s) * dist_s)
                        sy2 = int(vy + math.sin(ang_s) * dist_s)
                        sa = int(255 * (1 - prog / 0.38))
                        sps = pygame.Surface((10, 10), pygame.SRCALPHA)
                        pygame.draw.circle(sps, (*spark_col, sa), (5, 5), 3)
                        surface.blit(sps, (sx2 - 5, sy2 - 5))

            elif vtype == "summon_burst":
                # Purple portal ring expanding outward
                ring_col  = (180, 60, 255)
                inner_col = (220, 140, 255)
                for ri in range(3):
                    rp = max(0.0, prog - ri * 0.15)
                    if rp <= 0:
                        continue
                    rad = int(10 + 120 * rp)
                    alpha = int(200 * (1 - rp))
                    rs = pygame.Surface((rad * 2 + 14, rad * 2 + 14), pygame.SRCALPHA)
                    pygame.draw.circle(rs, (*ring_col, alpha),
                                       (rad + 7, rad + 7), rad, max(1, 4 - ri))
                    pygame.draw.circle(rs, (*inner_col, alpha // 2),
                                       (rad + 7, rad + 7), max(1, rad - 5), 2)
                    surface.blit(rs, (int(vx) - rad - 7, int(vy) - rad - 7))
                # Rune sparks
                if prog < 0.5:
                    for si in range(8):
                        ang_s = si * math.pi * 2 / 8 + prog * 4
                        dist_s = int(15 + 80 * prog)
                        sx2 = int(vx + math.cos(ang_s) * dist_s)
                        sy2 = int(vy + math.sin(ang_s) * dist_s)
                        sa = int(240 * (1 - prog / 0.5))
                        sps = pygame.Surface((10, 10), pygame.SRCALPHA)
                        pygame.draw.circle(sps, (200, 100, 255, sa), (5, 5), 3)
                        surface.blit(sps, (sx2 - 5, sy2 - 5))

        self._vfx = alive_vfx

        # Orc rider sprite frame
        frame = self._anims[self._anim_state].current(flip=self._flip) if self._anim_state in self._anims else None
        if frame:
            fw, fh = frame.get_size()
            sh = pygame.Surface((fw // 2 + 16, 13), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 60), (0, 0, sh.get_width(), 13))
            surface.blit(sh, (x - sh.get_width() // 2, y + int(fh * 0.10)))
            surface.blit(frame, (x - fw // 2, y - fh // 2))
        else:
            col = (220, 60, 30) if p2 else (180, 30, 180)
            pygame.draw.rect(surface, col, self.rect, border_radius=5)

        # ── Slash VFX (renders over sprite) ───────────────────────────
        for vtype, vx, vy, vt in self._vfx:
            if vtype != "slash":
                continue
            elapsed = now_v - vt
            prog = elapsed / 320
            alpha_s = int(230 * max(0, 1 - prog ** 0.7))
            flip_d = -1 if self._flip else 1
            eff_r = 120
            eff = pygame.Surface((eff_r * 2 + 4, eff_r * 2 + 4), pygame.SRCALPHA)
            for i in range(7):
                base_a = math.pi * 0.22 * flip_d
                ang_i  = base_a + (i - 3) * 0.20
                length = int(55 + 60 * prog)
                sr = 24
                lx1 = eff_r + 2 + int(math.cos(ang_i) * sr)
                ly1 = eff_r + 2 + int(math.sin(ang_i) * sr)
                lx2 = eff_r + 2 + int(math.cos(ang_i) * (sr + length))
                ly2 = eff_r + 2 + int(math.sin(ang_i) * (sr + length))
                center_dist = abs(i - 3)
                a = max(0, int(alpha_s * (1 - center_dist / 4.0)))
                col2 = (255, 255, 200) if center_dist < 1.5 else (255, 190, 70)
                thick = 3 if center_dist < 1.5 else 2
                pygame.draw.line(eff, (*col2, a), (lx1, ly1), (lx2, ly2), thick)
            surface.blit(eff, (int(vx) - eff_r - 2, int(vy) - eff_r - 2))

        # Phase 2 lava aura overlay
        if p2:
            for i in range(6):
                ang = i * 60 + now * 0.05
                ax = x + int(math.cos(math.radians(ang)) * 42)
                ay = y + int(math.sin(math.radians(ang)) * 42)
                gs = pygame.Surface((14, 14), pygame.SRCALPHA)
                pulse_a = int(80 + 60 * math.sin(now / 200.0 + i))
                pygame.draw.circle(gs, (255, 120, 20, max(0, min(255, pulse_a))), (7, 7), 7)
                surface.blit(gs, (ax - 7, ay - 7))

        # Advance hit flash timer (keep for timing logic, no visual)
        if self._hit_flash > 0:
            self._hit_flash = max(0, self._hit_flash - 16)

        # HP bar (positioned above sprite)
        bw = self.w
        filled = int(bw * self.hp / self.max_hp)
        by = y - 56
        pygame.draw.rect(surface, (80, 0, 0),    (x - bw // 2, by, bw, 6))
        hcol = (255, 80, 20) if p2 else (220, 60, 220)
        pygame.draw.rect(surface, hcol, (x - bw // 2, by, filled, 6))

        # Floating damage numbers
        font = _get_dmg_font()
        i = 0
        while i < len(self._dmg_pops):
            px, py, txt, t0 = self._dmg_pops[i]
            elapsed = now - t0
            if elapsed > 900:
                self._dmg_pops.pop(i); continue
            progress = elapsed / 900
            fy = int(py - 36 * progress)
            alpha = max(0, 255 - int(255 * progress * 1.2))
            ds = font.render(txt, True, (255, 100, 30))
            ds.set_alpha(alpha)
            surface.blit(ds, (int(px) - ds.get_width() // 2, fy))
            i += 1
