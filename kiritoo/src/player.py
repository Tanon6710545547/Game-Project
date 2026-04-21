"""
player.py - Player class: movement, combat, inventory, skills
"""
from __future__ import annotations
import pygame
import math
import random
from src.sprite_loader import make_all_anims, SpriteAnim
from src.constants import (
    PLAYER_START_HP, PLAYER_START_ATK, PLAYER_START_DEF,
    PLAYER_SPEED, PLAYER_INVINCIBLE_MS,
    TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    WHITE, YELLOW, GREEN, RED,
    STAMINA_MAX, STAMINA_REGEN_PER_SEC, ATTACK_STAMINA_COST,
    FIREBALL_STAMINA_COST, FIREBALL_SPEED, FIREBALL_DMG_MULT,
    AREA_STAMINA_COST, AREA_RADIUS, AREA_DMG_MULT, AREA_DURATION_MS,
)

# ─── Fireball impact explosion duration ───────────────────────────────────────
_IMPACT_DURATION = 900   # ms the explosion plays after fireball hits


def _draw_glow_circle(surface: pygame.Surface, color: tuple, cx: int, cy: int,
                      radius: int, alpha: int):
    if radius <= 0 or alpha <= 0:
        return
    s = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, min(255, alpha)), (radius + 1, radius + 1), radius)
    surface.blit(s, (cx - radius - 1, cy - radius - 1))


def _draw_glow_ring(surface: pygame.Surface, color: tuple, cx: int, cy: int,
                    radius: int, width: int, alpha: int):
    if radius <= 0 or alpha <= 0:
        return
    pad = width + 6
    s = pygame.Surface((radius * 2 + pad * 2, radius * 2 + pad * 2), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, min(255, alpha)), (radius + pad, radius + pad), radius, width)
    surface.blit(s, (cx - radius - pad, cy - radius - pad))


class Fireball:
    """A spectacular projectile fired by the player."""
    RADIUS = 14

    def __init__(self, x: float, y: float, dx: int, dy: int, damage: int):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.damage = damage
        self.active = True
        self._trail: list[tuple] = []
        self._smoke: list[dict] = []
        # Impact explosion state
        self._impacting = False
        self._impact_ms = 0
        self._impact_x = 0
        self._impact_y = 0
        # Pre-bake random debris for the explosion
        rng = random.Random(id(self) & 0xFFFF)
        self._debris = [
            {
                "angle": rng.uniform(0, math.pi * 2),
                "speed": rng.uniform(0.9, 2.4),
                "size":  rng.randint(3, 7),
                "col":   rng.choice([(255,200,50),(255,130,20),(255,60,10),(220,220,255)]),
            }
            for _ in range(18)
        ]
        self._sparks = [
            {
                "angle": i * math.pi * 2 / 24 + rng.uniform(-0.12, 0.12),
                "len":   rng.randint(16, 38),
                "col":   rng.choice([(255,240,100),(255,180,40),(255,100,20)]),
            }
            for i in range(24)
        ]

    # ------------------------------------------------------------------
    def _trigger_impact(self):
        self._impacting = True
        self._impact_ms = pygame.time.get_ticks()
        self._impact_x  = int(self.x)
        self._impact_y  = int(self.y)
        self.active = False   # no longer moves; explosion takes over

    # ------------------------------------------------------------------
    def update(self, wall_rects: list):
        if self._impacting:
            return   # explosion ticks in draw()
        if not self.active:
            return

        # Smoke particles trail
        sx = self.x + random.uniform(-4, 4)
        sy = self.y + random.uniform(-4, 4)
        self._smoke.append({"x": sx, "y": sy, "r": random.randint(5, 11),
                            "a": random.randint(60, 110), "born": pygame.time.get_ticks()})
        self._smoke = [p for p in self._smoke if pygame.time.get_ticks() - p["born"] < 320]

        self._trail.append((int(self.x), int(self.y)))
        if len(self._trail) > 14:
            self._trail.pop(0)

        self.x += self.dx * FIREBALL_SPEED
        self.y += self.dy * FIREBALL_SPEED

        if not (0 < self.x < SCREEN_WIDTH and 0 < self.y < SCREEN_HEIGHT - 96):
            self._trigger_impact()
            return

        fr = pygame.Rect(int(self.x) - self.RADIUS, int(self.y) - self.RADIUS,
                         self.RADIUS * 2, self.RADIUS * 2)
        if any(fr.colliderect(w) for w in wall_rects):
            self._trigger_impact()

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - self.RADIUS, int(self.y) - self.RADIUS,
                           self.RADIUS * 2, self.RADIUS * 2)

    def is_done(self) -> bool:
        """True once both flying and explosion are finished."""
        if not self.active and not self._impacting:
            return True
        if self._impacting:
            return pygame.time.get_ticks() - self._impact_ms > _IMPACT_DURATION
        return False

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface):
        # ── Explosion phase ──────────────────────────────────────────
        if self._impacting:
            elapsed = pygame.time.get_ticks() - self._impact_ms
            if elapsed > _IMPACT_DURATION:
                return
            ep = elapsed / _IMPACT_DURATION   # 0 → 1
            ix, iy = self._impact_x, self._impact_y

            # Outer mega-glow bloom (fades throughout)
            bloom_r = int(85 * (1 - ep * 0.4))
            bloom_a = int(160 * (1 - ep))
            _draw_glow_circle(surface, (255, 140, 20), ix, iy, bloom_r, bloom_a)

            # Inner white flash (first 25%)
            if ep < 0.25:
                fp = ep / 0.25
                _draw_glow_circle(surface, (255, 255, 220), ix, iy,
                                  int(55 * (1 - fp)), int(255 * (1 - fp)))

            # 3 expanding shockwave rings
            ring_data = [
                (0.00, (255, 255, 200), 5),
                (0.05, (255, 160, 30),  4),
                (0.12, (200, 80, 10),   3),
            ]
            max_ring = 120
            for delay, rcol, thick in ring_data:
                rp = max(0.0, ep - delay)
                if rp <= 0:
                    continue
                rad = int(max_ring * min(1.0, rp * 1.2))
                ra  = int(255 * max(0, 1 - rp * 1.4))
                _draw_glow_ring(surface, rcol, ix, iy, rad, thick, ra)
                # Outer halo of each ring
                _draw_glow_ring(surface, rcol, ix, iy, rad + 7, thick + 4, ra // 3)

            # Radial spark lines (first 60%)
            if ep < 0.60:
                sp_fade = 1 - ep / 0.60
                for sp in self._sparks:
                    dist = int(max_ring * min(1.0, ep * 1.8) * 0.85)
                    sa   = int(255 * sp_fade)
                    ex2  = ix + int(math.cos(sp["angle"]) * dist)
                    ey2  = iy + int(math.sin(sp["angle"]) * dist)
                    sx2  = ix + int(math.cos(sp["angle"]) * max(0, dist - sp["len"]))
                    sy2  = iy + int(math.sin(sp["angle"]) * max(0, dist - sp["len"]))
                    lw   = max(1, int(3 * sp_fade))
                    ls = pygame.Surface((abs(ex2 - sx2) + lw * 2 + 2,
                                         abs(ey2 - sy2) + lw * 2 + 2), pygame.SRCALPHA)
                    ox = min(sx2, ex2) - lw
                    oy = min(sy2, ey2) - lw
                    pygame.draw.line(ls, (*sp["col"], sa),
                                     (sx2 - ox, sy2 - oy), (ex2 - ox, ey2 - oy), lw)
                    surface.blit(ls, (ox, oy))

            # Debris chunks flying outward
            for db in self._debris:
                dist = int(max_ring * 0.9 * min(1.0, ep * 1.5))
                da   = int(255 * max(0, 1 - ep * 1.6))
                dbx  = ix + int(math.cos(db["angle"]) * dist)
                dby  = iy + int(math.sin(db["angle"]) * dist)
                dbr  = max(1, int(db["size"] * (1 - ep * 0.7)))
                _draw_glow_circle(surface, db["col"], dbx, dby, dbr, da)

            # Hot core embers
            core_r = max(1, int(18 * (1 - ep * 2)))
            if core_r > 0:
                _draw_glow_circle(surface, (255, 255, 180), ix, iy, core_r,
                                  int(200 * (1 - ep * 2)))
            return

        # ── Flying phase ─────────────────────────────────────────────
        if not self.active:
            return

        ix, iy = int(self.x), int(self.y)
        now = pygame.time.get_ticks()

        # Smoke trail (oldest first, lightest)
        for p in self._smoke:
            age   = (now - p["born"]) / 320
            alpha = int(p["a"] * (1 - age))
            r     = int(p["r"] * (1 + age * 0.5))
            _draw_glow_circle(surface, (90, 70, 60), int(p["x"]), int(p["y"]), r, alpha)

        # Fire trail (bright, colored)
        trail_n = len(self._trail)
        for i, (tx, ty) in enumerate(self._trail):
            frac = (i + 1) / max(1, trail_n)
            a    = int(180 * frac)
            r    = max(2, int(self.RADIUS * frac * 0.85))
            col  = (255, int(80 + 120 * frac), int(10 + 30 * frac))
            _draw_glow_circle(surface, col, tx, ty, r, a)

        # Outer glow layers (purple → red → orange → yellow → white core)
        t = now * 0.001
        flicker = 1.0 + 0.08 * math.sin(t * 18.7)
        layers = [
            (50, (160,  40, 200), 55),   # purple outer haze
            (38, (255,  40,  10), 90),   # red
            (28, (255, 120,  20), 140),  # orange
            (18, (255, 210,  50), 200),  # yellow
            ( 9, (255, 255, 200), 255),  # white core
        ]
        for base_r, col, alpha in layers:
            r = max(1, int(base_r * flicker))
            _draw_glow_circle(surface, col, ix, iy, r, alpha)

        # Sharp bright center dot
        pygame.draw.circle(surface, (255, 255, 255), (ix, iy), 4)

        # Rotating sparkle ring (4 bright dots orbiting the orb)
        orbit_r = self.RADIUS + 8
        for ki in range(4):
            angle = t * 5.5 + ki * math.pi / 2
            kx = ix + int(math.cos(angle) * orbit_r)
            ky = iy + int(math.sin(angle) * orbit_r)
            _draw_glow_circle(surface, (255, 240, 140), kx, ky, 3, 200)


# ──────────────────────────────────────────────────────────────────────────────

class Player:
    """Handles player movement, combat, inventory, and EXP/leveling."""

    def __init__(self, stat_tracker, combo_system):
        # Stats
        self.max_hp   = PLAYER_START_HP
        self.hp       = PLAYER_START_HP
        self.attack   = PLAYER_START_ATK
        self.defense  = PLAYER_START_DEF
        self.speed    = PLAYER_SPEED
        self.gold     = 0
        self.exp      = 0
        self.level    = 1
        self.exp_to_next = 100

        # Position (pixel)
        self.x = SCREEN_WIDTH  // 2
        self.y = (SCREEN_HEIGHT - 80) // 2
        self.w = TILE_SIZE - 14
        self.h = TILE_SIZE - 14

        # Combat state
        self.invincible_timer = 0
        self.current_floor    = 1
        self.kills            = 0
        self.temp_buffs: list[tuple] = []
        self.facing = "down"

        # Attack animation
        self.attacking        = False
        self.attack_timer     = 0
        self.attack_duration  = 200   # ms
        self.attack_rect      = None

        # References
        self.stat_tracker = stat_tracker
        self.combo_system = combo_system

        # Wall-break charges (reset each floor)
        self.wall_breaks = 3

        # Stamina
        self.max_stamina = float(STAMINA_MAX)
        self.stamina     = float(STAMINA_MAX)

        # Skills
        self.fireballs:  list[Fireball] = []
        self.area_effect: tuple | None  = None   # (x, y, start_ms)
        self._area_applied = True
        # Pre-baked area-attack decoration data (stable per activation)
        self._area_cracks:  list[dict] = []
        self._area_debris:  list[dict] = []
        self._area_bolts:   list[dict] = []

        # Feedback messages
        self.messages: list[tuple] = []   # (text, expire_time_ms)

        # Sprite animation (Knight Templar)
        self._anims      = make_all_anims("Knight Templar", 128)
        self._anim_state = "idle"
        self._flip       = False
        self._moving     = False

    # ------------------------------------------------------------------
    # rect helper
    @property
    def rect(self):
        return pygame.Rect(self.x - self.w // 2, self.y - self.h // 2, self.w, self.h)

    # ------------------------------------------------------------------
    def handle_input(self, keys, walls: list[pygame.Rect], dt_ms: float):
        speed = self.speed * (dt_ms / 16)
        dx, dy = 0, 0

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= speed; self.facing = "up"
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += speed; self.facing = "down"
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= speed; self.facing = "left"
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += speed; self.facing = "right"

        self._moving = (dx != 0 or dy != 0)
        if dx < 0:
            self._flip = True
        elif dx > 0:
            self._flip = False

        # Collision
        new_rect = self.rect.move(dx, 0)
        if not any(new_rect.colliderect(w) for w in walls):
            self.x += dx
        new_rect = self.rect.move(0, dy)
        if not any(new_rect.colliderect(w) for w in walls):
            self.y += dy

        # Clamp inside play area
        margin = self.w // 2
        self.x = max(margin, min(SCREEN_WIDTH  - margin, self.x))
        self.y = max(margin, min(SCREEN_HEIGHT - 96 - margin, self.y))

    # ------------------------------------------------------------------
    def start_attack(self, current_time_ms: int):
        if not self.attacking:
            self.stamina = max(0.0, self.stamina - ATTACK_STAMINA_COST)
            self.attacking     = True
            self.attack_timer  = current_time_ms
            self._anim_state   = "attack"
            self._anims["attack"].reset()
            # Build attack hitbox in facing direction
            r = self.rect
            aw, ah = 40, 40
            if   self.facing == "up":    self.attack_rect = pygame.Rect(r.centerx - aw//2, r.top - ah,    aw, ah)
            elif self.facing == "down":  self.attack_rect = pygame.Rect(r.centerx - aw//2, r.bottom,       aw, ah)
            elif self.facing == "left":  self.attack_rect = pygame.Rect(r.left - aw,        r.centery - ah//2, aw, ah)
            elif self.facing == "right": self.attack_rect = pygame.Rect(r.right,             r.centery - ah//2, aw, ah)

    # ------------------------------------------------------------------
    def update(self, current_time_ms: int, dt_ms: float = 16.0):
        # Invincibility
        if self.invincible_timer > 0:
            self.invincible_timer = max(0, self.invincible_timer - dt_ms)

        # Attack expiry
        if self.attacking and current_time_ms - self.attack_timer >= self.attack_duration:
            self.attacking    = False
            self.attack_rect  = None

        # Stamina regen
        self.stamina = min(self.max_stamina,
                           self.stamina + STAMINA_REGEN_PER_SEC * dt_ms / 1000.0)

        # Combo expiry check
        self.combo_system.check_expiry(current_time_ms)

        # Message expiry
        self.messages = [(t, e) for t, e in self.messages if e > current_time_ms]

        # Animation state machine
        a = self._anims
        if self._anim_state == "attack" and a["attack"].done:
            self._anim_state = "walk" if self._moving else "idle"
        elif self._anim_state == "hurt" and a["hurt"].done:
            self._anim_state = "walk" if self._moving else "idle"
        elif self._anim_state not in ("attack", "hurt"):
            ns = "walk" if self._moving else "idle"
            if ns != self._anim_state:
                self._anim_state = ns
        a[self._anim_state].update(dt_ms)

    # ------------------------------------------------------------------
    def take_damage(self, amount: int, curse_type: str = "none"):
        if self.invincible_timer > 0:
            return 0
        if curse_type == "fragile":
            amount = amount * 2
        dmg = max(1, amount - self.defense)
        self.hp = max(0, self.hp - dmg)
        self.invincible_timer = PLAYER_INVINCIBLE_MS
        if self._anim_state != "attack":
            self._anim_state = "hurt"
            self._anims["hurt"].reset()
        return dmg

    # ------------------------------------------------------------------
    def use_item(self, item, curse_type: str = "none"):
        msg = item.apply(self, curse_type)
        self.add_message(msg)
        return msg

    # ------------------------------------------------------------------
    def gain_exp(self, amount: int):
        self.exp += amount
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.max_hp  += 20
            self.hp       = min(self.hp + 20, self.max_hp)
            self.attack  += 3
            self.defense += 1
            self.exp_to_next = int(self.exp_to_next * 1.4)
            self.add_message(f"LEVEL UP! Lv.{self.level}")

    # ------------------------------------------------------------------
    def add_message(self, text: str, duration_ms: int = 2500):
        expire = pygame.time.get_ticks() + duration_ms
        self.messages.append((text, expire))

    # ------------------------------------------------------------------
    def use_fireball(self) -> bool:
        if self.stamina < FIREBALL_STAMINA_COST:
            self.add_message("Not enough stamina! [V]", 1200)
            return False
        self.stamina -= FIREBALL_STAMINA_COST
        dirs = {"up": (0,-1), "down": (0,1), "left": (-1,0), "right": (1,0)}
        dx, dy = dirs.get(self.facing, (0, 1))
        dmg = int(self.attack * FIREBALL_DMG_MULT)
        self.fireballs.append(
            Fireball(self.x + dx * 22, self.y + dy * 22, dx, dy, dmg)
        )
        return True

    def use_area_attack(self, current_time_ms: int) -> bool:
        if self.stamina < AREA_STAMINA_COST:
            self.add_message("Not enough stamina! [B]", 1200)
            return False
        self.stamina -= AREA_STAMINA_COST
        self.area_effect   = (self.x, self.y, current_time_ms)
        self._area_applied = False
        # Pre-bake stable random elements for this activation
        rng = random.Random(current_time_ms & 0xFFFF)
        # Ground cracks: 12 radiating lines from center
        self._area_cracks = [
            {
                "angle":  rng.uniform(0, math.pi * 2),
                "length": rng.uniform(0.55, 1.05),   # fraction of AREA_RADIUS
                "segs":   rng.randint(3, 6),          # zigzag segments
                "col":    rng.choice([(255,160,40),(255,100,20),(200,80,10),(255,220,80)]),
            }
            for _ in range(12)
        ]
        # Debris chunks
        self._area_debris = [
            {
                "angle": rng.uniform(0, math.pi * 2),
                "speed": rng.uniform(0.7, 1.8),
                "size":  rng.randint(4, 9),
                "col":   rng.choice([(180,140,80),(140,110,60),(255,160,40),(200,200,220)]),
            }
            for _ in range(20)
        ]
        # Lightning bolt endpoints (inside the ring area)
        self._area_bolts = [
            {
                "a1": rng.uniform(0, math.pi * 2),
                "a2": rng.uniform(0, math.pi * 2),
                "r1": rng.uniform(0.3, 0.85),
                "r2": rng.uniform(0.3, 0.85),
                "segs": rng.randint(4, 8),
                "col": rng.choice([(180, 220, 255),(255,255,180),(200,180,255)]),
            }
            for _ in range(8)
        ]
        return True

    def try_break_wall(self, floor) -> bool:
        if self.wall_breaks <= 0:
            self.add_message("No wall breaks left!", 1500)
            return False
        offsets = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
        dc, dr = offsets.get(self.facing, (0, 0))
        from src.constants import TILE_SIZE
        col = int(self.x) // TILE_SIZE + dc
        row = int(self.y) // TILE_SIZE + dr
        if floor.remove_wall(col, row):
            self.wall_breaks -= 1
            self.add_message(f"Wall broken! ({self.wall_breaks} left)", 1500)
            return True
        self.add_message("No wall there.", 1000)
        return False

    def is_dead(self) -> bool:
        return self.hp <= 0

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface):
        now = pygame.time.get_ticks()
        if self.invincible_timer > 0 and (now // 80) % 2 == 0:
            return

        x, y = int(self.x), int(self.y)

        # Knight Templar sprite frame
        frame = self._anims[self._anim_state].current(flip=self._flip)
        if frame:
            fw, fh = frame.get_size()
            sh = pygame.Surface((fw // 2 + 10, 9), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 55), (0, 0, sh.get_width(), 9))
            surface.blit(sh, (x - sh.get_width() // 2, y + int(fh * 0.10)))
            surface.blit(frame, (x - fw // 2, y - fh // 2))
        else:
            sh = pygame.Surface((36, 9), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 55), (0, 0, 36, 9))
            surface.blit(sh, (x - 18, y + 38))
            pygame.draw.rect(surface, (65, 125, 215), (x - 15, y - 20, 30, 40), border_radius=4)

        # ── Area Attack: spectacular ──────────────────────────────────
        if self.area_effect is not None:
            ax, ay, at = self.area_effect
            elapsed = now - at
            if elapsed < AREA_DURATION_MS:
                prog = elapsed / AREA_DURATION_MS
                iax, iay = int(ax), int(ay)
                t_sec = now * 0.001

                # ── Screen-edge vignette flash (peak at prog≈0.12) ──
                peak_a = int(80 * max(0, 1 - abs(prog - 0.12) / 0.22))
                if peak_a > 0:
                    vig = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - 96), pygame.SRCALPHA)
                    for vr in range(5):
                        va = peak_a // (vr + 1)
                        if va > 0:
                            pygame.draw.rect(vig, (255, 200, 50, va),
                                             (vr, vr, SCREEN_WIDTH - vr * 2,
                                              SCREEN_HEIGHT - 96 - vr * 2), 4 - min(3, vr))
                    surface.blit(vig, (0, 0))

                # ── Energy pillar rising from player (first 30%) ────
                if prog < 0.30:
                    pp = prog / 0.30
                    pillar_h = int(260 * math.sin(pp * math.pi))
                    pillar_w = int(32 + 14 * math.sin(pp * math.pi))
                    pillar_a = int(220 * math.sin(pp * math.pi))
                    if pillar_h > 0:
                        ps = pygame.Surface((pillar_w + 40, pillar_h + 40), pygame.SRCALPHA)
                        # Outer glow
                        for pw in range(3):
                            pygame.draw.rect(ps,
                                (100, 160, 255, pillar_a // (pw + 3)),
                                (20 - pw * 6, 20 + pw * 4,
                                 pillar_w + pw * 12, pillar_h),
                                border_radius=pillar_w // 2 + pw * 3)
                        # Core beam
                        pygame.draw.rect(ps,
                            (200, 220, 255, pillar_a),
                            (20, 20, pillar_w, pillar_h),
                            border_radius=pillar_w // 2)
                        # Bright center stripe
                        pygame.draw.rect(ps,
                            (255, 255, 255, min(255, pillar_a + 40)),
                            (20 + pillar_w // 2 - 4, 20, 8, pillar_h),
                            border_radius=4)
                        surface.blit(ps, (iax - pillar_w // 2 - 20,
                                          iay - pillar_h - 20))
                    # Electric particles shooting upward along pillar
                    ep_rng = random.Random(int(prog * 60))
                    for _ in range(8):
                        ex = iax + ep_rng.randint(-pillar_w // 2, pillar_w // 2)
                        ey = iay - ep_rng.randint(0, max(1, pillar_h))
                        _draw_glow_circle(surface, (180, 220, 255),
                                          ex, ey, ep_rng.randint(2, 5),
                                          int(180 * (1 - pp)))

                # ── Ground cracks radiating from center ─────────────
                crack_fade_end = 0.85
                if prog < crack_fade_end:
                    crack_a = int(220 * max(0, 1 - prog / crack_fade_end))
                    for ck in self._area_cracks:
                        total_len = AREA_RADIUS * ck["length"]
                        # Cracks grow in from prog=0 to prog=0.18
                        visible = min(1.0, prog / 0.18)
                        draw_len = total_len * visible
                        if draw_len < 2:
                            continue
                        # Build zigzag points
                        segs = ck["segs"]
                        pts = [(iax, iay)]
                        for si in range(1, segs + 1):
                            frac = si / segs
                            cx = iax + int(math.cos(ck["angle"]) * draw_len * frac)
                            cy = iay + int(math.sin(ck["angle"]) * draw_len * frac)
                            # Perpendicular jitter decreases toward tip
                            jitter_mag = int(6 * (1 - frac) * visible)
                            perp = ck["angle"] + math.pi / 2
                            jitter = random.Random(si * 37 + int(ck["angle"] * 100)).randint(
                                -jitter_mag, jitter_mag)
                            cx += int(math.cos(perp) * jitter)
                            cy += int(math.sin(perp) * jitter)
                            pts.append((cx, cy))
                        if len(pts) >= 2:
                            cs = pygame.Surface(
                                (SCREEN_WIDTH, SCREEN_HEIGHT - 96), pygame.SRCALPHA)
                            pygame.draw.lines(cs, (*ck["col"], crack_a), False, pts, 2)
                            # Bright glow line
                            pygame.draw.lines(cs, (255, 255, 200, crack_a // 2),
                                              False, pts, 1)
                            surface.blit(cs, (0, 0))

                # ── Ground fill glow disk (fades by prog=0.45) ──────
                if prog < 0.50:
                    gr = int(AREA_RADIUS * min(1.0, prog * 1.35))
                    if gr > 0:
                        ga = int(55 * (1 - prog / 0.50))
                        _draw_glow_circle(surface, (200, 220, 255), iax, iay, gr, ga)

                # ── Central burst flash (first 25%) ─────────────────
                if prog < 0.25:
                    fp = prog / 0.25
                    flash_r = int(34 * (1 - fp))
                    fa = int(255 * (1 - fp))
                    _draw_glow_circle(surface, (255, 255, 220), iax, iay, flash_r, fa)
                    # Shockwave compression ring at ground
                    _draw_glow_ring(surface, (255, 255, 255), iax, iay,
                                    int(flash_r * 1.8), 3, fa // 2)

                # ── 6 staggered expanding shockwave rings ────────────
                ring_defs = [
                    (0.00, (140, 240, 255), 7),   # cyan leading
                    (0.06, (255, 250,  90), 6),   # yellow
                    (0.12, (255, 180,  30), 5),   # orange
                    (0.19, (255,  90,  20), 4),   # red-orange
                    (0.27, (220,  50, 200), 4),   # purple trailing
                    (0.36, (180,  40, 255), 3),   # violet tail
                ]
                for delay, rcol, thick in ring_defs:
                    rp = max(0.0, prog - delay)
                    if rp <= 0:
                        continue
                    rad = int(AREA_RADIUS * min(1.0, rp * 1.35))
                    ra  = int(250 * max(0, 1 - rp * 1.3))
                    _draw_glow_ring(surface, rcol, iax, iay, rad, thick, ra)
                    # Outer soft halo per ring
                    _draw_glow_ring(surface, rcol, iax, iay, rad + 8, thick + 5, ra // 4)

                # ── Lightning arcs inside the ring zone (0–70%) ─────
                if prog < 0.70:
                    bolt_fade = 1 - prog / 0.70
                    # Flicker: only draw every ~3 frames using time
                    bolt_frame = (now // 50) % 3
                    if bolt_frame < 2:
                        for bi, bolt in enumerate(self._area_bolts):
                            # Each bolt exists in a short time window
                            bolt_start = bi * 0.06
                            bolt_end   = bolt_start + 0.28
                            if not (bolt_start <= prog <= bolt_end):
                                continue
                            bfade = 1 - abs(prog - (bolt_start + bolt_end) * 0.5) / 0.14
                            ba = int(220 * bfade * bolt_fade)
                            x1 = iax + int(math.cos(bolt["a1"]) * AREA_RADIUS * bolt["r1"])
                            y1 = iay + int(math.sin(bolt["a1"]) * AREA_RADIUS * bolt["r1"])
                            x2 = iax + int(math.cos(bolt["a2"]) * AREA_RADIUS * bolt["r2"])
                            y2 = iay + int(math.sin(bolt["a2"]) * AREA_RADIUS * bolt["r2"])
                            # Zigzag lightning between p1 and p2
                            segs = bolt["segs"]
                            lpts = [(x1, y1)]
                            for lsi in range(1, segs):
                                frac = lsi / segs
                                lx = x1 + int((x2 - x1) * frac)
                                ly = y1 + int((y2 - y1) * frac)
                                perp = math.atan2(y2 - y1, x2 - x1) + math.pi / 2
                                jitter = random.Random(bi * 100 + lsi + now // 50).randint(-12, 12)
                                lx += int(math.cos(perp) * jitter)
                                ly += int(math.sin(perp) * jitter)
                                lpts.append((lx, ly))
                            lpts.append((x2, y2))
                            if len(lpts) >= 2 and ba > 0:
                                lbs = pygame.Surface(
                                    (SCREEN_WIDTH, SCREEN_HEIGHT - 96), pygame.SRCALPHA)
                                pygame.draw.lines(lbs, (*bolt["col"], ba), False, lpts, 2)
                                pygame.draw.lines(lbs, (255, 255, 255, ba // 3), False, lpts, 1)
                                surface.blit(lbs, (0, 0))

                # ── 24 radial sparks riding the leading ring ─────────
                if prog < 0.60:
                    sp_prog = prog / 0.60
                    rng_sp = random.Random(12345)
                    ring_rad = int(AREA_RADIUS * min(1.0, prog * 1.35))
                    for si in range(24):
                        base_a  = si * math.pi * 2 / 24 + rng_sp.uniform(-0.15, 0.15)
                        dist_sp = int(ring_rad * 0.92)
                        sx2 = iax + int(math.cos(base_a) * dist_sp)
                        sy2 = iay + int(math.sin(base_a) * dist_sp)
                        slen = max(2, int(14 * (1 - sp_prog)))
                        sa   = int(230 * (1 - sp_prog))
                        ex2  = sx2 + int(math.cos(base_a) * slen)
                        ey2  = sy2 + int(math.sin(base_a) * slen)
                        scol = (255, 240, 120) if si % 3 != 0 else (180, 230, 255)
                        _draw_glow_circle(surface, scol, sx2, sy2, 3, sa)

                # ── Debris chunks flying outward (0–80%) ────────────
                if prog < 0.80:
                    for db in self._area_debris:
                        dist = int(AREA_RADIUS * db["speed"] * min(1.0, prog * 1.6))
                        da   = int(255 * max(0, 1 - prog / 0.80))
                        dbx  = iax + int(math.cos(db["angle"]) * dist)
                        dby  = iay + int(math.sin(db["angle"]) * dist)
                        dbr  = max(1, int(db["size"] * (1 - prog * 0.6)))
                        _draw_glow_circle(surface, db["col"], dbx, dby, dbr, da)

        # ── Fireballs ────────────────────────────────────────────────
        for fb in self.fireballs:
            fb.draw(surface)

        # HP bar
        bar_w  = self.w
        filled = int(bar_w * self.hp / self.max_hp)
        bar_y  = y - 42
        pygame.draw.rect(surface, RED,   (x - bar_w // 2, bar_y, bar_w, 5))
        pygame.draw.rect(surface, GREEN, (x - bar_w // 2, bar_y, filled, 5))

    def _draw_slash(self, surface: pygame.Surface, progress: float):
        r = self.attack_rect
        alpha = int(240 * (1.0 - progress) ** 0.6)
        # Glow background
        glow = pygame.Surface((r.w + 6, r.h + 6), pygame.SRCALPHA)
        pygame.draw.rect(glow, (255, 215, 55, alpha // 3),
                         (0, 0, r.w + 6, r.h + 6), border_radius=6)
        surface.blit(glow, (r.left - 3, r.top - 3))
        # Slash lines
        ls = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        lc = (255, 250, 160, min(255, alpha + 40))
        if self.facing in ("up", "down"):
            for ox in (-9, 0, 9):
                cx = r.w // 2 + ox
                if self.facing == "down":
                    pygame.draw.line(ls, lc, (cx - 10, 2), (cx + 10, r.h - 2), 2)
                else:
                    pygame.draw.line(ls, lc, (cx - 10, r.h - 2), (cx + 10, 2), 2)
        else:
            for oy in (-9, 0, 9):
                cy = r.h // 2 + oy
                if self.facing == "right":
                    pygame.draw.line(ls, lc, (2, cy + 10), (r.w - 2, cy - 10), 2)
                else:
                    pygame.draw.line(ls, lc, (2, cy - 10), (r.w - 2, cy + 10), 2)
        surface.blit(ls, r.topleft)
        # Bright frame
        fr = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(fr, (255, 255, 200, alpha // 2),
                         (0, 0, r.w, r.h), 2, border_radius=3)
        surface.blit(fr, r.topleft)
