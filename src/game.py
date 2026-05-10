"""
game.py - Main Game class: state management, main loop, rendering
"""
from __future__ import annotations
import math
import random
import pygame
import time
from src.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE,
    STATE_MENU, STATE_NAME_ENTRY, STATE_PLAYING, STATE_MERCHANT,
    STATE_GAME_OVER, STATE_LEADERBOARD, STATE_PAUSED, STATE_BOSS_CUTSCENE,
    HP_SAMPLE_INTERVAL_MS,
    DARK_BG, WHITE, YELLOW, GOLD_COLOR, RED, GREEN, GRAY
)
import numpy as np
from src.player        import Player
from src.floor         import Floor
from src.merchant      import Merchant
from src.combo_system  import ComboSystem
from src.stat_tracker  import StatTracker
from src.leaderboard   import Leaderboard
from src.hud           import HUD
try:
    from src.sounds import play_boss_death, play_boss_summon
except Exception:
    def play_boss_death(): pass
    def play_boss_summon(): pass


class Game:
    """
    Top-level class: owns the game loop, state machine, and all subsystems.
    """

    def __init__(self):
        self.screen  = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        pygame.display.set_icon(self._make_game_icon())
        self.clock   = pygame.time.Clock()

        self.leaderboard = Leaderboard()
        self.state       = STATE_MENU

        self.font_title  = pygame.font.SysFont("monospace", 52, bold=True)
        self.font_xl     = pygame.font.SysFont("monospace", 70, bold=True)
        self.font_card   = pygame.font.SysFont("monospace", 32, bold=True)
        self.font_big    = pygame.font.SysFont("monospace", 26, bold=True)
        self.font_med    = pygame.font.SysFont("monospace", 18)
        self.font_sm     = pygame.font.SysFont("monospace", 14)
        # Thai-capable font for "ตา" unit label
        self.font_th     = pygame.font.SysFont(
            "thonburi,tahoma,arial unicode ms,arial,helvetica", 13)

        # Menu particle system
        self._menu_stars = [
            {"x": random.uniform(0, SCREEN_WIDTH),
             "y": random.uniform(0, SCREEN_HEIGHT),
             "speed": random.uniform(0.2, 0.9),
             "size": random.randint(1, 3),
             "alpha": random.randint(80, 255),
             "twinkle": random.uniform(0, math.pi * 2)}
            for _ in range(70)
        ]
        self._menu_orbs = [
            {"ox": random.randint(-200, 200),
             "oy": random.randint(-60, 80),
             "r": random.randint(10, 26),
             "color": random.choice([
                 (160, 80, 255), (80, 160, 255), (255, 100, 60),
                 (60, 220, 160), (255, 200, 60), (200, 80, 200)]),
             "phase": random.uniform(0, math.pi * 2),
             "phase2": random.uniform(0, math.pi * 2),
             "speed": random.uniform(0.4, 1.0)}
            for _ in range(7)
        ]
        # Pre-render button icons
        self._icon_play = self._make_icon_sword(22)
        self._icon_lb   = self._make_icon_trophy(22)
        self._icon_quit = self._make_icon_door(22)
        self._icon_back = self._make_icon_back(22)

        # Player name input state
        self._player_name  = "Hero"
        self._name_input   = ""

        # Pickup effect animations and leaderboard scroll
        self._pickup_anims: list = []   # [{"start_ms", "color", "duration"}]
        self._death_particles: list = []  # [{"x","y","start_ms","color"}]
        self._lb_scroll  = 0

        self._reset_game()
        self._hp_sample_timer   = 0
        self._merchant: Merchant | None = None
        self._feedback_msg: str = ""
        self._feedback_expire   = 0
        self._show_stats_overlay  = False
        self._stats_tab           = 0     # 0 = SESSION, 1 = ALL SESSIONS
        self._selected_hist_idx: int | None = None  # row selected in ALL SESSIONS tab
        self._table_scroll        = 0     # scroll offset for ALL SESSIONS table
        self._last_session_stats: dict = {}  # cached before log is cleared on session end

    # ------------------------------------------------------------------
    def _reset_game(self):
        self.stat_tracker   = StatTracker()
        self.combo_system   = ComboSystem()
        self.player         = Player(self.stat_tracker, self.combo_system)
        self.current_floor_num = 1
        self.floor          = Floor(self.current_floor_num, self.stat_tracker,
                                    self.player.attack)
        self.player.x, self.player.y = self.floor.player_spawn_pos
        self.floor.apply_curse(self.player)
        self.hud            = HUD()
        self._won              = False
        self._pickup_anims     = []
        self._death_particles  = []
        self._shake_end        = 0
        self._shake_amp        = 0
        self._boss_flash_end   = 0
        self._color_drain_end  = 0   # screen desaturates during this window
        self._slowmo_end       = 0   # time-scale reduced during this window
        self._show_stats       = False
        self._play_time_ms     = 0   # ms spent in STATE_PLAYING only

    # ------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)
            # Apply slow-motion scale after boss death
            _now_r = pygame.time.get_ticks()
            if _now_r < getattr(self, "_slowmo_end", 0):
                frac = max(0.15, (_now_r - (_now_r - (self._slowmo_end - _now_r))) / 1800)
                dt   = int(dt * 0.18)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self._handle_event(event)

            self._update(dt)
            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------
    # EVENT HANDLING
    # ------------------------------------------------------------------
    def _handle_event(self, event: pygame.event.Event):
        # Stats overlay intercepts all input while open
        if self._show_stats_overlay:
            # ── Panel geometry (mirrors _draw_stats_overlay) ──────────
            _ow, _oh = 940, 640
            _ox  = (SCREEN_WIDTH  - _ow) // 2   # 10
            _oy  = (SCREEN_HEIGHT - _oh) // 2   # 40
            _lx  = _ox + 14
            _lw  = 548
            _row_h   = 18
            _cy_l    = _oy + 198
            _tr_y0   = _cy_l + 26 + 16          # top of first data row
            _tph     = _oy + _oh - 18 - _cy_l
            _max_rows = max(0, (_tph - 40) // _row_h)
            _n_e     = len(self.leaderboard.entries)
            _max_scroll = max(0, _n_e - _max_rows)

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._show_stats_overlay = False
            elif event.type == pygame.MOUSEWHEEL and self._stats_tab == 1:
                self._table_scroll = max(
                    0, min(_max_scroll, self._table_scroll - event.y)
                )
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                _tab_w  = (_ow - 32) // 2
                _close_x = pygame.Rect(_ox + _ow - 42, _oy + 10, 30, 30)
                _tab0_r  = pygame.Rect(_lx,              _oy + 158, _tab_w, 34)
                _tab1_r  = pygame.Rect(_lx + _tab_w + 4, _oy + 158, _tab_w, 34)
                mx, my = event.pos
                if _close_x.collidepoint(mx, my):
                    self._show_stats_overlay = False
                elif _tab0_r.collidepoint(mx, my):
                    self._stats_tab = 0
                elif _tab1_r.collidepoint(mx, my):
                    self._stats_tab = 1
                    # Auto-scroll so the current session is visible
                    _sid2 = getattr(self, "_last_summary", {}).get("session_id", "")
                    _cur_i = next(
                        (i for i, e in enumerate(self.leaderboard.entries)
                         if e.get("session_id", "") == _sid2),
                        None
                    )
                    if _cur_i is not None:
                        _target = max(0, _cur_i - _max_rows // 2)
                        self._table_scroll = max(0, min(_max_scroll, _target))
                elif self._stats_tab == 1:
                    # Row click in ALL SESSIONS table
                    if _lx <= mx <= _lx + _lw and my >= _tr_y0:
                        screen_row = (my - _tr_y0) // _row_h
                        abs_idx    = screen_row + self._table_scroll
                        if 0 <= abs_idx < _n_e:
                            self._selected_hist_idx = (
                                None if self._selected_hist_idx == abs_idx else abs_idx
                            )
            return
        if self.state == STATE_MENU:
            self._menu_event(event)
        elif self.state == STATE_NAME_ENTRY:
            self._name_entry_event(event)
        elif self.state == STATE_PLAYING:
            self._playing_event(event)
        elif self.state == STATE_MERCHANT:
            self._merchant_event(event)
        elif self.state == STATE_GAME_OVER:
            self._gameover_event(event)
        elif self.state == STATE_LEADERBOARD:
            self._leaderboard_event(event)
        elif self.state == STATE_PAUSED:
            self._paused_event(event)
        elif self.state == STATE_BOSS_CUTSCENE:
            self._boss_cutscene_event(event)

    def _menu_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                self._name_input = ""
                self.change_state(STATE_NAME_ENTRY)
            elif event.key == pygame.K_l:
                self._lb_scroll = 0
                self.change_state(STATE_LEADERBOARD)
            elif event.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            play_rect  = pygame.Rect(SCREEN_WIDTH//2 - 130, 252, 260, 54)
            lb_rect    = pygame.Rect(SCREEN_WIDTH//2 - 130, 316, 260, 54)
            stats_rect = pygame.Rect(SCREEN_WIDTH//2 - 130, 380, 260, 54)
            quit_rect  = pygame.Rect(SCREEN_WIDTH//2 - 130, 444, 260, 54)
            if play_rect.collidepoint(mx, my):
                self._name_input = ""
                self.change_state(STATE_NAME_ENTRY)
            elif lb_rect.collidepoint(mx, my):
                self._lb_scroll = 0
                self.change_state(STATE_LEADERBOARD)
            elif stats_rect.collidepoint(mx, my):
                self._show_stats_overlay = True
            elif quit_rect.collidepoint(mx, my):
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _name_entry_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                self._player_name = self._name_input.strip() or "Hero"
                self._reset_game()
                self.change_state(STATE_PLAYING)
            elif event.key == pygame.K_ESCAPE:
                self.change_state(STATE_MENU)
            elif event.key == pygame.K_BACKSPACE:
                self._name_input = self._name_input[:-1]
            else:
                if event.unicode and event.unicode.isprintable() and len(self._name_input) < 14:
                    self._name_input += event.unicode

    def _playing_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.change_state(STATE_PAUSED)
            if event.key == pygame.K_TAB:
                self._show_stats_overlay = not self._show_stats_overlay
            if event.key in (pygame.K_SPACE, pygame.K_z, pygame.K_j):
                self.player.start_attack(pygame.time.get_ticks())
            if event.key == pygame.K_e:
                self.player.try_break_wall(self.floor)
            if event.key == pygame.K_v:
                self.player.use_fireball()
            if event.key == pygame.K_b:
                self.player.use_area_attack(pygame.time.get_ticks())
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._PAUSE_BTN.collidepoint(*event.pos):
                self.change_state(STATE_PAUSED)

    def _merchant_event(self, event):
        if self._merchant:
            result = self._merchant.handle_event(event, self.player)
            if result:
                if result == "leave":
                    self.next_floor()
                else:
                    self._show_feedback(result)

    def _gameover_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._name_input = ""
                self.change_state(STATE_NAME_ENTRY)
            elif event.key == pygame.K_m:
                self.change_state(STATE_MENU)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            retry_rect = pygame.Rect(SCREEN_WIDTH//2 - 120, 506, 240, 48)
            menu_rect  = pygame.Rect(SCREEN_WIDTH//2 - 120, 560, 240, 48)
            stats_rect = pygame.Rect(SCREEN_WIDTH//2 - 120, 614, 240, 48)
            if retry_rect.collidepoint(mx, my):
                self._name_input = ""
                self.change_state(STATE_NAME_ENTRY)
            elif menu_rect.collidepoint(mx, my):
                self.change_state(STATE_MENU)
            elif stats_rect.collidepoint(mx, my):
                self._show_stats_overlay = True

    def _leaderboard_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_m):
            self.change_state(STATE_MENU)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            back_rect = pygame.Rect(SCREEN_WIDTH//2 - 80, SCREEN_HEIGHT - 70, 160, 44)
            if back_rect.collidepoint(*event.pos):
                self.change_state(STATE_MENU)
        if event.type == pygame.MOUSEWHEEL:
            _VISIBLE = 18
            max_scroll = max(0, len(self.leaderboard.entries) - _VISIBLE)
            self._lb_scroll = max(0, min(max_scroll, self._lb_scroll - event.y))

    def _paused_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.change_state(STATE_PLAYING)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            resume_rect = pygame.Rect(SCREEN_WIDTH//2 - 90, 296, 180, 48)
            menu_rect   = pygame.Rect(SCREEN_WIDTH//2 - 90, 356, 180, 48)
            stats_rect  = pygame.Rect(SCREEN_WIDTH//2 - 90, 416, 180, 48)
            if resume_rect.collidepoint(*event.pos):
                self.change_state(STATE_PLAYING)
            elif menu_rect.collidepoint(*event.pos):
                self._end_session()
                self.change_state(STATE_MENU)
            elif stats_rect.collidepoint(*event.pos):
                self._show_stats_overlay = True

    def _boss_cutscene_event(self, event):
        skip = False
        if event.type == pygame.KEYDOWN:
            skip = True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            skip = True
        if skip:
            self.change_state(STATE_PLAYING)

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    def _update(self, dt: float):
        if self.state == STATE_PLAYING and not self._show_stats_overlay:
            self._play_time_ms += dt
        if self._show_stats_overlay:
            return   # freeze all game logic while stats panel is open
        if self.state == STATE_MENU:
            for s in self._menu_stars:
                s["y"] -= s["speed"]
                s["twinkle"] += 0.05
                if s["y"] < -4:
                    s["y"] = SCREEN_HEIGHT + 4
                    s["x"] = random.uniform(0, SCREEN_WIDTH)
            for o in self._menu_orbs:
                o["phase"]  += o["speed"] * dt / 800.0
                o["phase2"] += o["speed"] * dt / 1200.0
            return
        if self.state == STATE_BOSS_CUTSCENE:
            elapsed = pygame.time.get_ticks() - getattr(self, "_cutscene_start_ms", 0)
            if elapsed >= 5000:
                self.change_state(STATE_PLAYING)
            return
        if self.state in (STATE_NAME_ENTRY, STATE_GAME_OVER,
                          STATE_LEADERBOARD, STATE_PAUSED, STATE_MERCHANT):
            return
        if self.state != STATE_PLAYING:
            return

        now  = pygame.time.get_ticks()
        keys = pygame.key.get_pressed()

        # Player movement
        self.player.handle_input(keys, self.floor.wall_rects, dt)
        self.player.update(now, dt)
        self.player.current_floor = self.current_floor_num

        # HP sampling
        if now - self._hp_sample_timer >= HP_SAMPLE_INTERVAL_MS:
            self._hp_sample_timer = now
            self.stat_tracker.record("player_hp_over_time",
                                     floor=self.current_floor_num,
                                     hp=self.player.hp, max_hp=self.player.max_hp)

        # Enemy AI + combat
        for enemy in self.floor.enemies:
            if not enemy.alive:
                continue
            enemy.choose_action(self.player,
                                 self.floor.walls_set,
                                 len(self.floor.tiles[0]),
                                 len(self.floor.tiles),
                                 self.floor.curse_type, now)
            enemy.try_attack(self.player, now, self.floor.curse_type)

            # Player attacks enemy
            if (self.player.attacking and self.player.attack_rect and
                    self.player.attack_rect.colliderect(enemy.rect)):
                dmg = enemy.take_damage(self.player.attack)
                if not enemy.alive:
                    drops = enemy.on_death(self.player, self.combo_system,
                                           self.stat_tracker,
                                           self.current_floor_num,
                                           self.floor.curse_type)
                    for item in drops:
                        item.x = int(enemy.x)
                        item.y = int(enemy.y)
                        self.floor.items.append(item)
                    self._death_particles.append(
                        {"x": enemy.x, "y": enemy.y, "start_ms": now,
                         "color": enemy.color}
                    )
                    # Boss death — spectacular effect
                    if hasattr(enemy, "phase"):
                        self._shake_end      = now + 3000
                        self._shake_amp      = 22
                        self._boss_flash_end = now + 700
                        self._color_drain_end = now + 2200
                        self._slowmo_end     = now + 1800
                        play_boss_death()
                        # Wave 1: instant central burst (100 particles)
                        for _bp in range(100):
                            _ang  = random.uniform(0, math.pi * 2)
                            _dist = random.uniform(0, 220)
                            self._death_particles.append({
                                "x": enemy.x + math.cos(_ang) * _dist * 0.3,
                                "y": enemy.y + math.sin(_ang) * _dist * 0.3,
                                "start_ms": now + random.randint(0, 300),
                                "color": random.choice([
                                    (255, 80, 20), (255, 200, 60),
                                    (200, 60, 255), (255, 255, 180),
                                    (60, 200, 255), (255, 30, 30),
                                ]),
                            })
                        # Wave 2: delayed second burst
                        for _bp in range(60):
                            _ang  = random.uniform(0, math.pi * 2)
                            _dist = random.uniform(50, 260)
                            self._death_particles.append({
                                "x": enemy.x + math.cos(_ang) * _dist * 0.5,
                                "y": enemy.y + math.sin(_ang) * _dist * 0.5,
                                "start_ms": now + random.randint(400, 900),
                                "color": random.choice([
                                    (255, 120, 40), (255, 240, 80),
                                    (220, 80, 255), (80, 255, 200),
                                ]),
                            })

        # Collect boss minion spawns (guarded)
        try:
            new_spawns = []
            for enemy in self.floor.enemies:
                if hasattr(enemy, "pending_spawns") and enemy.pending_spawns:
                    new_spawns.extend(enemy.pending_spawns)
                    enemy.pending_spawns.clear()
            self.floor.enemies.extend(new_spawns)
        except Exception:
            pass

        # Remove dead enemies
        self.floor.enemies = [e for e in self.floor.enemies if e.alive]

        # --- Fireballs ---
        for fb in self.player.fireballs:
            fb.update(self.floor.wall_rects)
            if not fb.active:
                continue
            for enemy in self.floor.enemies:
                if enemy.alive and fb.get_rect().colliderect(enemy.rect):
                    enemy.take_damage(fb.damage)
                    fb.active = False
                    if not enemy.alive:
                        drops = enemy.on_death(self.player, self.combo_system,
                                               self.stat_tracker,
                                               self.current_floor_num,
                                               self.floor.curse_type)
                        for item in drops:
                            item.x = int(enemy.x); item.y = int(enemy.y)
                            self.floor.items.append(item)
                        self._death_particles.append(
                            {"x": enemy.x, "y": enemy.y, "start_ms": now,
                             "color": enemy.color}
                        )
                    break
        self.player.fireballs = [fb for fb in self.player.fireballs if not fb.is_done()]

        # --- Area attack ---
        if self.player.area_effect and not self.player._area_applied:
            self.player._area_applied = True
            ax, ay, _ = self.player.area_effect
            area_dmg = int(self.player.attack * 1.5)
            for enemy in self.floor.enemies:
                if enemy.alive and math.hypot(enemy.x - ax, enemy.y - ay) < 160:
                    enemy.take_damage(area_dmg)
                    if not enemy.alive:
                        drops = enemy.on_death(self.player, self.combo_system,
                                               self.stat_tracker,
                                               self.current_floor_num,
                                               self.floor.curse_type)
                        for item in drops:
                            item.x = int(enemy.x); item.y = int(enemy.y)
                            self.floor.items.append(item)
                        self._death_particles.append(
                            {"x": enemy.x, "y": enemy.y, "start_ms": now,
                             "color": enemy.color}
                        )
        if self.player.area_effect and now - self.player.area_effect[2] > 700:
            self.player.area_effect = None

        # Item pickup
        for item in self.floor.items:
            if not item.collected:
                ir = pygame.Rect(item.x - 12, item.y - 12, 24, 24)
                if ir.colliderect(self.player.rect):
                    msg = self.player.use_item(item, self.floor.curse_type)
                    item.collected = True
                    self._show_feedback(msg)
                    _pcol = None
                    if item.type == "potion" and self.floor.curse_type != "no_potions":
                        _pcol = (50, 220, 80)    # green
                    elif item.type == "armor":
                        _pcol = (60, 130, 255)   # blue
                    elif item.type == "weapon":
                        _pcol = (220, 50, 50)    # red
                    if _pcol:
                        self._pickup_anims.append(
                            {"start_ms": now, "color": _pcol, "duration": 750}
                        )

        # Exit check
        self.floor.update_exit()
        if (self.floor.exit_open and
                self.floor.exit_rect and
                self.floor.exit_rect.colliderect(self.player.rect)):
            self._advance_floor()

        # Expire finished pickup/death effects
        self._pickup_anims    = [e for e in self._pickup_anims
                                  if now - e["start_ms"] < e["duration"]]
        self._death_particles = [e for e in self._death_particles
                                  if now - e["start_ms"] < 850]

        # Death check
        if self.player.is_dead():
            self._end_session()
            self.change_state(STATE_GAME_OVER)

    # ------------------------------------------------------------------
    def _advance_floor(self):
        if self.current_floor_num >= 20:
            self._won = True
            self._end_session()
            self.change_state(STATE_GAME_OVER)
            return

        self.current_floor_num += 1
        self.stat_tracker.record("floor_reached",
                                  floor=self.current_floor_num, value=self.current_floor_num)

        new_floor = Floor(self.current_floor_num, self.stat_tracker, self.player.attack)
        if new_floor.is_merchant:
            self._merchant = Merchant(self.current_floor_num, self.stat_tracker)
            self.floor = new_floor
            self.change_state(STATE_MERCHANT)
        else:
            self.floor = new_floor
            self.player.x, self.player.y = self.floor.player_spawn_pos
            self.player.wall_breaks = 3
            self.floor.apply_curse(self.player)
            self.combo_system.reset()
            if new_floor.is_boss:
                self._cutscene_start_ms = pygame.time.get_ticks()
                self.change_state(STATE_BOSS_CUTSCENE)

    def next_floor(self):
        """Called after leaving merchant."""
        self.current_floor_num += 1
        self.floor = Floor(self.current_floor_num, self.stat_tracker, self.player.attack)
        self.player.x, self.player.y = self.floor.player_spawn_pos
        self.player.wall_breaks = 3
        self.floor.apply_curse(self.player)
        self.combo_system.reset()
        if self.floor.is_boss:
            self._cutscene_start_ms = pygame.time.get_ticks()
            self.change_state(STATE_BOSS_CUTSCENE)
        else:
            self.change_state(STATE_PLAYING)

    # ------------------------------------------------------------------
    def _end_session(self):
        # Cache stats NOW — export_csv() clears the log, so this must come first
        self._last_session_stats = self._get_session_stats()
        summary = self.stat_tracker.generate_summary(
            self.current_floor_num, self.player.kills)
        summary["player_name"] = self._player_name
        self.stat_tracker.record("session_duration",
                                  value=summary["duration_sec"],
                                  duration_sec=summary["duration_sec"])
        self.stat_tracker.export_csv()
        self.leaderboard.add_entry(summary)
        self._last_summary = summary

    # ------------------------------------------------------------------
    def change_state(self, new_state: str):
        self._show_stats_overlay = False
        self.state = new_state

    def _show_feedback(self, msg: str, duration_ms: int = 2000):
        self._feedback_msg    = msg
        self._feedback_expire = pygame.time.get_ticks() + duration_ms

    # ------------------------------------------------------------------
    # DRAW
    # ------------------------------------------------------------------
    def _draw(self):
        if self.state == STATE_MENU:
            self._draw_menu()
        elif self.state == STATE_NAME_ENTRY:
            self._draw_name_entry()
        elif self.state == STATE_PLAYING:
            self._draw_playing()
        elif self.state == STATE_MERCHANT:
            self._draw_merchant()
        elif self.state == STATE_GAME_OVER:
            self._draw_gameover()
        elif self.state == STATE_LEADERBOARD:
            self._draw_leaderboard()
        elif self.state == STATE_PAUSED:
            self._draw_paused()
        elif self.state == STATE_BOSS_CUTSCENE:
            self._draw_boss_cutscene()
        if self._show_stats_overlay:
            self._draw_stats_overlay()

    # ------------------------------------------------------------------
    @staticmethod
    def _draw_knight_art(surface: pygame.Surface, cx: int, by: int, t: float):
        """Draw an ornate armoured knight hero. cx=centre x, by=feet y."""

        # Ground glow halo
        for ri in range(60, 0, -10):
            ga = int(20 * (ri / 60) * (0.5 + 0.5 * math.sin(t * 1.3)))
            gs = pygame.Surface((ri * 4, ri), pygame.SRCALPHA)
            pygame.draw.ellipse(gs, (80, 120, 255, ga), (0, 0, ri * 4, ri))
            surface.blit(gs, (cx - ri * 2, by - ri // 2))

        # Floating rune orbits
        for ri2 in range(7):
            angle = t * 0.55 + ri2 * math.pi * 2 / 7
            orb_r = 92 + int(10 * math.sin(t * 1.1 + ri2 * 0.9))
            rx2   = cx + int(math.cos(angle) * orb_r)
            ry2   = (by - 145) + int(math.sin(angle) * orb_r * 0.38)
            ra2   = int(55 + 38 * math.sin(t * 2.1 + ri2 * 1.4))
            pal   = [(80,180,255),(100,255,180),(200,110,255),(255,200,70),
                     (90,220,255),(170,255,110),(255,155,75)]
            col_r2 = pal[ri2 % 7]
            rs2 = pygame.Surface((16, 16), pygame.SRCALPHA)
            pygame.draw.rect(rs2, (*col_r2, ra2), (2, 2, 12, 12), 1, border_radius=2)
            pygame.draw.line(rs2, (*col_r2, ra2), (8, 2),  (8, 14), 1)
            pygame.draw.line(rs2, (*col_r2, ra2), (2, 8), (14, 8),  1)
            surface.blit(rs2, (rx2 - 8, ry2 - 8))

        # ── Cape ──────────────────────────────────────────────────────
        sway = math.sin(t * 0.9) * 9
        cape_pts = [
            (cx - 20, by - 188),
            (cx + 20, by - 188),
            (cx + 46 + sway, by - 82),
            (cx + 38 + sway, by - 18),
            (cx +  8,        by -  8),
            (cx - 34 - sway, by - 32),
            (cx - 46 - sway, by - 105),
        ]
        pygame.draw.polygon(surface, (22, 9,  34), [(x+3, y+3) for x,y in cape_pts])
        pygame.draw.polygon(surface, (66, 22, 86), cape_pts)
        pygame.draw.polygon(surface, (94, 36, 114), cape_pts, 2)
        pygame.draw.line(surface, (86, 30, 106),
                         (cx - 12, by - 184), (cx - 30 - int(sway), by - 48), 1)

        # ── Legs ──────────────────────────────────────────────────────
        for lx_off, lw in [(-17, 15), (3, 15)]:
            lx = cx + lx_off
            pygame.draw.rect(surface, (44, 50, 66), (lx, by - 80, lw, 42), border_radius=3)
            pygame.draw.rect(surface, (62, 70, 88), (lx, by - 80, lw, 42), 1, border_radius=3)
            pygame.draw.rect(surface, (48, 54, 70), (lx - 1, by - 40, lw + 2, 24), border_radius=3)
            pygame.draw.rect(surface, (68, 76, 96), (lx - 1, by - 40, lw + 2, 24), 1, border_radius=3)
            kx, ky = lx + lw // 2, by - 52
            pygame.draw.ellipse(surface, (78, 86, 106), (kx - 9, ky - 7, 18, 13))
            pygame.draw.ellipse(surface, (110, 118, 142), (kx - 9, ky - 7, 18, 13), 1)
            pygame.draw.line(surface, (140, 150, 175), (kx - 5, ky - 2), (kx + 5, ky - 2), 1)

        # ── Boots ──────────────────────────────────────────────────────
        for bx_off, bw in [(-19, 21), (1, 21)]:
            bx2 = cx + bx_off
            pygame.draw.rect(surface, (34, 28, 22), (bx2, by - 22, bw, 22), border_radius=4)
            pygame.draw.rect(surface, (52, 44, 34), (bx2, by - 22, bw, 6))
            pygame.draw.rect(surface, (58, 50, 38), (bx2, by - 22, bw, 22), 1, border_radius=4)

        # ── Chest plate ───────────────────────────────────────────────
        chest_pts = [
            (cx - 25, by - 82), (cx + 25, by - 82),
            (cx + 21, by - 182), (cx - 21, by - 182),
        ]
        inner_pts = [
            (cx - 20, by - 84), (cx + 20, by - 84),
            (cx + 17, by - 178), (cx - 17, by - 178),
        ]
        pygame.draw.polygon(surface, (42, 48, 64), chest_pts)
        pygame.draw.polygon(surface, (56, 64, 80), inner_pts)
        for band_y in [by - 102, by - 122, by - 142, by - 162]:
            bww = max(6, 20 - abs(band_y - (by - 132)) // 4)
            pygame.draw.line(surface, (68, 76, 96),
                             (cx - bww, band_y), (cx + bww, band_y), 1)
        pygame.draw.polygon(surface, (80, 90, 112), chest_pts, 2)
        # Emblem (animated gold diamond)
        em_y = by - 130
        em_pulse = 0.8 + 0.2 * math.sin(t * 2.4)
        for em_r in [18, 12, 7]:
            eg = pygame.Surface((em_r * 2, em_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(eg, (255, 200, 50, int(70 * em_pulse * em_r / 18)),
                               (em_r, em_r), em_r)
            surface.blit(eg, (cx - em_r, em_y - em_r))
        dm_pts = [(cx, em_y-14), (cx+12, em_y), (cx, em_y+14), (cx-12, em_y)]
        pygame.draw.polygon(surface, (170, 132, 24), dm_pts)
        pygame.draw.polygon(surface, (235, 192, 48), dm_pts, 1)
        dm2 = [(cx, em_y-8), (cx+7, em_y), (cx, em_y+8), (cx-7, em_y)]
        pygame.draw.polygon(surface, (255, 220, 80), dm2)

        # ── Belt ──────────────────────────────────────────────────────
        pygame.draw.rect(surface, (70, 50, 20), (cx-27, by-86, 54, 10), border_radius=2)
        pygame.draw.rect(surface, (100, 72, 30), (cx-25, by-86, 50, 4))
        pygame.draw.rect(surface, (178, 138, 28), (cx-7, by-90, 14, 14), border_radius=2)
        pygame.draw.rect(surface, (228, 186, 52), (cx-5, by-88, 10, 10), border_radius=1)
        pygame.draw.circle(surface, (255, 230, 100), (cx, by-83), 2)

        # ── Pauldrons ─────────────────────────────────────────────────
        for px3, side in [(cx-30, -1), (cx+30, 1)]:
            pygame.draw.ellipse(surface, (58, 64, 82), (px3-17, by-200, 34, 24))
            pygame.draw.ellipse(surface, (80, 90, 112), (px3-17, by-200, 34, 24), 2)
            pygame.draw.ellipse(surface, (96, 108, 132), (px3-11, by-198, 20, 10))
            pygame.draw.ellipse(surface, (54, 60, 78), (px3-19, by-183, 38, 16))
            pygame.draw.ellipse(surface, (76, 84, 106), (px3-19, by-183, 38, 16), 1)

        # ── Arms ──────────────────────────────────────────────────────
        pygame.draw.rect(surface, (48, 54, 70), (cx-50, by-178, 19, 72), border_radius=4)
        pygame.draw.rect(surface, (66, 74, 94), (cx-50, by-178, 19, 72), 1, border_radius=4)
        pygame.draw.rect(surface, (48, 54, 70), (cx+31, by-178, 19, 56), border_radius=4)
        pygame.draw.rect(surface, (66, 74, 94), (cx+31, by-178, 19, 56), 1, border_radius=4)

        # ── Shield (left) ─────────────────────────────────────────────
        sh_cx2, sh_cy2 = cx - 60, by - 118
        sh_pts = [
            (sh_cx2,      sh_cy2 - 38), (sh_cx2 + 24, sh_cy2 - 28),
            (sh_cx2 + 24, sh_cy2 + 10), (sh_cx2,      sh_cy2 + 32),
            (sh_cx2 - 24, sh_cy2 + 10), (sh_cx2 - 24, sh_cy2 - 28),
        ]
        pygame.draw.polygon(surface, (40, 44, 60), sh_pts)
        pygame.draw.polygon(surface, (62, 68, 88), sh_pts, 2)
        pygame.draw.line(surface, (148, 38, 38),
                         (sh_cx2, sh_cy2 - 26), (sh_cx2, sh_cy2 + 22), 5)
        pygame.draw.line(surface, (148, 38, 38),
                         (sh_cx2 - 18, sh_cy2 - 2), (sh_cx2 + 18, sh_cy2 - 2), 5)
        pygame.draw.line(surface, (195, 62, 62),
                         (sh_cx2, sh_cy2 - 24), (sh_cx2, sh_cy2 + 20), 2)
        pygame.draw.line(surface, (195, 62, 62),
                         (sh_cx2 - 16, sh_cy2 - 2), (sh_cx2 + 16, sh_cy2 - 2), 2)
        pygame.draw.circle(surface, (80, 64, 22), (sh_cx2, sh_cy2 - 2), 7)
        pygame.draw.circle(surface, (128, 102, 42), (sh_cx2, sh_cy2 - 2), 5)
        pygame.draw.circle(surface, (175, 148, 62), (sh_cx2, sh_cy2 - 2), 2)
        pygame.draw.line(surface, (82, 92, 116),
                         (sh_cx2 - 20, sh_cy2 - 25), (sh_cx2 + 20, sh_cy2 - 25), 1)

        # ── Sword (raised upper-right) ────────────────────────────────
        sw_bx = cx + 48
        sw_by = by - 128
        sw_tx = cx + 100 + int(4 * math.sin(t * 1.3))
        sw_ty = by - 248 + int(3 * math.cos(t * 1.1))
        # Glow along blade
        steps = 14
        for si in range(steps):
            frac = si / steps
            gx4  = int(sw_bx + (sw_tx - sw_bx) * frac)
            gy4  = int(sw_by + (sw_ty - sw_by) * frac)
            gr5  = max(1, int(9 * (1 - frac * 0.6) * (0.6 + 0.4 * math.sin(t * 2.5 + si * 0.4))))
            gg   = pygame.Surface((gr5 * 2, gr5 * 2), pygame.SRCALPHA)
            pygame.draw.circle(gg, (100, 180, 255, int(34 * (1 - frac))), (gr5, gr5), gr5)
            surface.blit(gg, (gx4 - gr5, gy4 - gr5))
        pygame.draw.line(surface, (168, 198, 230), (sw_bx, sw_by), (sw_tx, sw_ty), 5)
        pygame.draw.line(surface, (210, 232, 255), (sw_bx, sw_by), (sw_tx, sw_ty), 3)
        pygame.draw.line(surface, (255, 255, 255), (sw_bx, sw_by), (sw_tx, sw_ty), 1)
        # Fuller groove
        dx5 = sw_tx - sw_bx; dy5 = sw_ty - sw_by
        ln5 = math.hypot(dx5, dy5)
        if ln5 > 0:
            nx5, ny5 = -dy5 / ln5, dx5 / ln5
            pygame.draw.line(surface, (135, 168, 202),
                             (sw_bx + int(nx5 * 2), sw_by + int(ny5 * 2)),
                             (sw_tx + int(nx5 * 2), sw_ty + int(ny5 * 2)), 1)
        # Guard
        gd_cx2, gd_cy2 = sw_bx - 6, sw_by + 4
        pygame.draw.line(surface, (165, 128, 22),
                         (gd_cx2-14, gd_cy2+8), (gd_cx2+14, gd_cy2-8), 6)
        pygame.draw.line(surface, (214, 172, 40),
                         (gd_cx2-11, gd_cy2+6), (gd_cx2+11, gd_cy2-6), 3)
        # Handle
        ha1x, ha1y = gd_cx2-8, gd_cy2+10
        ha2x, ha2y = gd_cx2-22, gd_cy2+26
        pygame.draw.line(surface, (96, 64, 24), (ha1x, ha1y), (ha2x, ha2y), 6)
        pygame.draw.line(surface, (136, 98, 42), (ha1x, ha1y), (ha2x, ha2y), 3)
        for hi in range(4):
            hf  = hi / 3
            hwx = int(ha1x + (ha2x - ha1x) * hf)
            hwy = int(ha1y + (ha2y - ha1y) * hf)
            pygame.draw.circle(surface, (158, 118, 48), (hwx, hwy), 2)
        pygame.draw.circle(surface, (148, 116, 38), (ha2x, ha2y + 3), 6)
        pygame.draw.circle(surface, (192, 158, 64), (ha2x, ha2y + 3), 4)
        pygame.draw.circle(surface, (238, 208, 98), (ha2x, ha2y + 3), 2)
        # Tip sparkle
        sp_a3 = int(200 + 50 * math.sin(t * 4.5))
        for sp_r3 in [12, 7, 3]:
            sps3 = pygame.Surface((sp_r3 * 2, sp_r3 * 2), pygame.SRCALPHA)
            pygame.draw.circle(sps3, (175, 220, 255, sp_a3 * sp_r3 // 12),
                               (sp_r3, sp_r3), sp_r3)
            surface.blit(sps3, (sw_tx - sp_r3, sw_ty - sp_r3))
        pygame.draw.circle(surface, (255, 255, 255), (sw_tx, sw_ty), 2)

        # ── Neck ──────────────────────────────────────────────────────
        pygame.draw.rect(surface, (50, 56, 72), (cx-9, by-202, 18, 24))

        # ── Helmet ────────────────────────────────────────────────────
        helm_cy2 = by - 234
        hw2, hh2 = 48, 65
        pygame.draw.ellipse(surface, (54, 62, 80),
                            (cx - hw2 // 2, helm_cy2 - hh2 // 2, hw2, hh2))
        pygame.draw.ellipse(surface, (72, 82, 104),
                            (cx - hw2 // 2 + 4, helm_cy2 - hh2 // 2 + 4,
                             hw2 - 8, hh2 // 2))
        pygame.draw.ellipse(surface, (86, 96, 122),
                            (cx - hw2 // 2, helm_cy2 - hh2 // 2, hw2, hh2), 2)
        pygame.draw.line(surface, (90, 100, 126),
                         (cx, helm_cy2 - hh2 // 2 + 1), (cx, helm_cy2 + hh2 // 2 - 6), 2)
        # Visor
        vis_y2 = helm_cy2 - 7
        pygame.draw.rect(surface, (16, 12, 26), (cx-17, vis_y2-4, 34, 11), border_radius=3)
        vis_a2 = int(155 + 82 * math.sin(t * 2.9))
        vs2 = pygame.Surface((32, 7), pygame.SRCALPHA)
        pygame.draw.rect(vs2, (78, 178, 255, vis_a2), (0, 0, 32, 7), border_radius=3)
        surface.blit(vs2, (cx - 16, vis_y2 - 1))
        for ex_off3 in [-8, 8]:
            ed2 = pygame.Surface((10, 6), pygame.SRCALPHA)
            pygame.draw.ellipse(ed2, (158, 228, 255, min(255, vis_a2 + 40)), (0, 0, 10, 6))
            surface.blit(ed2, (cx + ex_off3 - 5, vis_y2))
        # Cheek guards
        for ck_x, ck_w in [(cx - hw2 // 2, 13), (cx + hw2 // 2 - 13, 13)]:
            pygame.draw.rect(surface, (48, 54, 70), (ck_x, helm_cy2 + 3, ck_w, 22), border_radius=3)
            pygame.draw.rect(surface, (72, 80, 102), (ck_x, helm_cy2 + 3, ck_w, 22), 1, border_radius=3)
        # Crest / plume
        for pi3 in range(14):
            ph_frac = pi3 / 13
            py_cr   = helm_cy2 - hh2 // 2 - pi3 * 7
            px_cr   = cx + int(5 * math.sin(t * 1.6 + pi3 * 0.4))
            pcol    = (int(195 * (1 - ph_frac) + 130 * ph_frac),
                       int(36 + 18 * ph_frac),
                       int(36 * (1 - ph_frac) + 110 * ph_frac))
            p_alp   = int(210 - pi3 * 13)
            if p_alp > 0:
                ps3 = pygame.Surface((9, 9), pygame.SRCALPHA)
                pygame.draw.circle(ps3, (*pcol, p_alp), (4, 4), max(1, 4 - pi3 // 4))
                surface.blit(ps3, (px_cr - 4, py_cr - 4))

    # ------------------------------------------------------------------
    def _draw_menu(self):
        now_t = pygame.time.get_ticks() / 1000.0

        # Rich gradient background
        for row in range(SCREEN_HEIGHT):
            frac = row / SCREEN_HEIGHT
            r2 = int(6  + 10 * (1 - frac))
            g2 = int(4  +  6 * (1 - frac))
            b2 = int(18 + 20 * (1 - frac))
            pygame.draw.rect(self.screen, (r2, g2, b2), (0, row, SCREEN_WIDTH, 1))

        # ── Stars ──────────────────────────────────────────────────────
        star_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for s in self._menu_stars:
            alpha = int(s["alpha"] * (0.6 + 0.4 * math.sin(s["twinkle"])))
            alpha = max(0, min(255, alpha))
            pygame.draw.circle(star_surf, (255, 255, 255, alpha),
                               (int(s["x"]), int(s["y"])), s["size"])
        self.screen.blit(star_surf, (0, 0))

        # ── Floating orbs (near title) ─────────────────────────────────
        orb_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        title_cx2, title_cy2 = SCREEN_WIDTH // 2, 165
        for o in self._menu_orbs:
            ox = title_cx2 + o["ox"] + int(40 * math.sin(o["phase"]))
            oy = title_cy2 + o["oy"] + int(25 * math.cos(o["phase2"]))
            r  = o["r"]
            pulse = 0.7 + 0.3 * math.sin(o["phase"] * 1.5)
            pygame.draw.circle(orb_surf, (*o["color"], int(28 * pulse)), (ox, oy), r + 8)
            pygame.draw.circle(orb_surf, (*o["color"], int(75 * pulse)), (ox, oy), r)
            pygame.draw.circle(orb_surf, (255, 255, 255, int(50 * pulse)),
                               (ox - r // 3, oy - r // 3), max(2, r // 4))
        self.screen.blit(orb_surf, (0, 0))

        # ── Knight character art (right side) ─────────────────────────
        self._draw_knight_art(self.screen, 800, 565, now_t)

        # ── Left side decorative panel (crossed swords / runes) ────────
        lp_x, lp_y, lp_w, lp_h = 28, 240, 80, 250
        lp = pygame.Surface((lp_w, lp_h), pygame.SRCALPHA)
        lp.fill((8, 6, 18, 130))
        pygame.draw.rect(lp, (70, 52, 110, 100), (0, 0, lp_w, lp_h), 1, border_radius=8)
        self.screen.blit(lp, (lp_x, lp_y))
        # Vertical rune symbols
        rune_syms = ["✦", "◈", "⬡", "✧", "◇"]
        font_rune = pygame.font.SysFont("monospace", 18)
        for ri3, sym in enumerate(rune_syms):
            ra3 = int(80 + 50 * math.sin(now_t * 1.2 + ri3 * 0.8))
            rs3 = font_rune.render(sym, True, (100, 80, 180))
            rs3.set_alpha(ra3)
            self.screen.blit(rs3, (lp_x + lp_w // 2 - rs3.get_width() // 2,
                                   lp_y + 14 + ri3 * 46))
        # Vertical accent line
        pygame.draw.line(self.screen, (70, 52, 110),
                         (lp_x + lp_w - 8, lp_y + 10),
                         (lp_x + lp_w - 8, lp_y + lp_h - 10), 1)

        # ── Title with glow ────────────────────────────────────────────
        cx = SCREEN_WIDTH // 2
        glow_t2 = 0.6 + 0.4 * math.sin(now_t * 1.8)
        gc2 = (int(120 * glow_t2), int(80 * glow_t2), int(200 * glow_t2))
        glow_surf2 = self.font_title.render("KIRITOO", True, gc2)
        for dx2, dy2 in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,-2),(-2,2),(2,2)]:
            self.screen.blit(glow_surf2,
                             (cx - glow_surf2.get_width()//2 + dx2, 122 + dy2))
        r_c2 = int(160 + 40 * math.sin(now_t * 1.2))
        g_c2 = int(120 + 30 * math.sin(now_t * 0.9 + 1))
        title2 = self.font_title.render("KIRITOO", True, (r_c2, g_c2, 255))
        self.screen.blit(title2, (cx - title2.get_width()//2, 122))

        # Decorative line under title
        t_w2 = title2.get_width()
        lw2  = t_w2 + 40
        pygame.draw.line(self.screen, (65, 48, 110),
                         (cx - lw2 // 2, 185), (cx + lw2 // 2, 185), 1)
        pygame.draw.polygon(self.screen, (130, 100, 200),
                            [(cx-5, 182), (cx, 187), (cx+5, 182)])

        # Subtitle
        sub2 = self.font_med.render("Roguelike Tower-Climbing RPG", True, (130, 112, 192))
        self.screen.blit(sub2, (cx - sub2.get_width()//2, 196))

        # ── Buttons ────────────────────────────────────────────────────
        bx2 = cx - 130
        self._draw_button("Play",        bx2, 252, 260, 54, (55, 35, 115), icon=self._icon_play)
        self._draw_button("Leaderboard", bx2, 316, 260, 54, (36, 56, 78),  icon=self._icon_lb)
        self._draw_button("Stats",       bx2, 380, 260, 54, (28, 68, 68))
        self._draw_button("Quit",        bx2, 444, 260, 54, (76, 26, 38),  icon=self._icon_quit)

        # Guide button (hover to show)
        guide_rect = pygame.Rect(cx - 130, 508, 260, 30)
        guide_hov  = guide_rect.collidepoint(*pygame.mouse.get_pos())
        gb_col = (32, 58, 52) if guide_hov else (18, 34, 30)
        gb_brd = (60, 180, 140) if guide_hov else (38, 90, 72)
        pygame.draw.rect(self.screen, gb_col, guide_rect, border_radius=7)
        pygame.draw.rect(self.screen, gb_brd, guide_rect, 1, border_radius=7)
        gh = self.font_sm.render("? HOW TO PLAY", True,
                                  (90, 220, 170) if guide_hov else (55, 140, 110))
        self.screen.blit(gh, (cx - gh.get_width()//2, guide_rect.y + 8))

        # Guide panel (shown on hover)
        if guide_hov:
            gp_w, gp_h = 400, 390
            gp_x = cx - gp_w // 2
            gp_y = guide_rect.y - gp_h - 6
            gp = pygame.Surface((gp_w, gp_h), pygame.SRCALPHA)
            gp.fill((6, 18, 14, 240))
            pygame.draw.rect(gp, (60, 180, 130, 200), (0, 0, gp_w, gp_h), 1, border_radius=12)
            self.screen.blit(gp, (gp_x, gp_y))

            # Title
            gtitle = self.font_med.render("GAME GUIDE", True, (80, 240, 180))
            self.screen.blit(gtitle, (gp_x + gp_w//2 - gtitle.get_width()//2, gp_y + 10))
            pygame.draw.line(self.screen, (50, 150, 110),
                             (gp_x + 14, gp_y + 30), (gp_x + gp_w - 14, gp_y + 30), 1)

            guide_lines = [
                ("MOVEMENT",    None,          (90, 220, 170)),
                ("WASD  or  Arrow Keys",       None, (175, 215, 200)),
                ("",            None,          (0, 0, 0)),
                ("COMBAT",      None,          (90, 220, 170)),
                ("Space / Z / J",  "Attack",   (220, 195, 150)),
                ("V",           "Fireball  (30 ST cost)",  (255, 140, 60)),
                ("B",           "Area burst  (50 ST cost)",(80, 210, 255)),
                ("E",           "Break wall",  (190, 155, 90)),
                ("",            None,          (0, 0, 0)),
                ("EXPLORE",     None,          (90, 220, 170)),
                ("Kill enemies to open exit", None, (175, 215, 200)),
                ("Step on exit door to advance floor", None, (175, 215, 200)),
                ("Reach floor 20 and beat the boss to WIN!", None, (255, 230, 80)),
                ("",            None,          (0, 0, 0)),
                ("ITEMS  (dropped by enemies)", None, (90, 220, 170)),
                ("Potion  Weapon  Armor  Buff  Gold", None, (175, 215, 200)),
                ("Merchant shop every 5 floors", None, (255, 215, 0)),
                ("",            None,          (0, 0, 0)),
                ("STATS  &  UI",  None,        (90, 220, 170)),
                ("ESC",         "Pause menu",  (220, 195, 150)),
                ("TAB",         "Stats overlay (mid-game)", (220, 195, 150)),
            ]
            gl_y = gp_y + 36
            for key, desc, gcol in guide_lines:
                if not key:
                    gl_y += 4
                    continue
                if desc is None:
                    # Section header
                    gs2 = self.font_sm.render(key, True, gcol)
                    self.screen.blit(gs2, (gp_x + 14, gl_y))
                else:
                    ks2 = self.font_sm.render(key, True, (240, 210, 100))
                    self.screen.blit(ks2, (gp_x + 14, gl_y))
                    ds2 = self.font_sm.render(desc, True, gcol)
                    self.screen.blit(ds2, (gp_x + 160, gl_y))
                gl_y += 16

        # Bottom mist
        mist = pygame.Surface((SCREEN_WIDTH, 80), pygame.SRCALPHA)
        for mi in range(40):
            ma = int(12 * (1 - mi / 40))
            pygame.draw.rect(mist, (20, 16, 40, ma), (0, mi * 2, SCREEN_WIDTH, 2))
        self.screen.blit(mist, (0, SCREEN_HEIGHT - 80))
        hint3 = self.font_sm.render("WASD / Arrows to move   |   Space / Z to attack",
                                    True, (60, 54, 90))
        self.screen.blit(hint3, (cx - hint3.get_width()//2, SCREEN_HEIGHT - 36))

    # ------------------------------------------------------------------
    def _draw_playing(self):
        self.floor.draw(self.screen)

        # Death explosions — debris chunks, NOT rings (very different from pickup)
        _now = pygame.time.get_ticks()
        for dp in self._death_particles:
            _el  = _now - dp["start_ms"]
            _dur = 800
            if _el < 0 or _el >= _dur:
                continue
            _prg = _el / _dur
            _dx, _dy = int(dp["x"]), int(dp["y"])
            _dc  = dp["color"]
            # Instant bright white flash (first 15%)
            if _prg < 0.15:
                _fp  = _prg / 0.15
                _fr  = int(30 * (1 - _fp))
                _fa  = max(0, min(255, int(255 * (1 - _fp))))
                if _fr > 0:
                    _fls = pygame.Surface((_fr * 2 + 2, _fr * 2 + 2), pygame.SRCALPHA)
                    pygame.draw.circle(_fls, (255, 255, 200, _fa),
                                       (_fr + 1, _fr + 1), _fr)
                    self.screen.blit(_fls, (_dx - _fr - 1, _dy - _fr - 1))
            # Smoke cloud — dark expanding semi-transparent disk
            _sr = int(6 + 52 * _prg)
            _sa = max(0, min(255, int(80 * max(0, 1 - _prg * 1.4))))
            _ss = pygame.Surface((_sr * 2, _sr * 2), pygame.SRCALPHA)
            pygame.draw.circle(_ss, (30, 25, 20, _sa), (_sr, _sr), _sr)
            self.screen.blit(_ss, (_dx - _sr, _dy - _sr))
            # 12 debris chunks — small rotating rectangles flying outward
            _rng2 = random.Random(dp["start_ms"])
            for _pi in range(12):
                _ang  = _rng2.uniform(0, math.pi * 2)
                _spd  = _rng2.uniform(30, 80)
                _grav = _rng2.uniform(12, 30)  # gravity pulls down
                _bx   = _dx + int(math.cos(_ang) * _spd * _prg)
                _by   = _dy + int(math.sin(_ang) * _spd * _prg) + int(_grav * _prg * _prg)
                _ba   = int(255 * max(0, 1 - _prg * 1.2))
                _sw   = max(2, int(_rng2.randint(3, 7) * (1 - _prg * 0.6)))
                _sh   = max(2, int(_rng2.randint(2, 5) * (1 - _prg * 0.6)))
                # Mix between enemy color and dark
                _mix  = max(0.0, 1 - _prg * 1.5)
                _cc   = (int(_dc[0] * _mix + 20 * (1 - _mix)),
                         int(_dc[1] * _mix + 15 * (1 - _mix)),
                         int(_dc[2] * _mix + 10 * (1 - _mix)))
                _ds   = pygame.Surface((_sw + 2, _sh + 2), pygame.SRCALPHA)
                pygame.draw.rect(_ds, (*_cc, _ba), (0, 0, _sw, _sh), border_radius=1)
                self.screen.blit(_ds, (_bx - _sw // 2, _by - _sh // 2))

        self.player.draw(self.screen)

        # Pickup effects — follow player, colored by item type
        _px, _py = int(self.player.x), int(self.player.y)
        for pe in self._pickup_anims:
            _el  = _now - pe["start_ms"]
            _prg = _el / pe["duration"]
            _col = pe["color"]
            # Expanding ring
            _rr = int(14 + 50 * _prg)
            _ra = int(220 * max(0, 1 - _prg))
            _rs = pygame.Surface((_rr * 2 + 4, _rr * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(_rs, (*_col, _ra // 3), (_rr + 2, _rr + 2), _rr + 4, 6)
            pygame.draw.circle(_rs, (*_col, _ra),      (_rr + 2, _rr + 2), _rr, 3)
            self.screen.blit(_rs, (_px - _rr - 2, _py - _rr - 2))
            # 14 rising particles
            _rng3 = random.Random(pe["start_ms"])
            for _pi in range(14):
                _ang = _rng3.uniform(0, math.pi * 2)
                _spd = _rng3.uniform(18, 48)
                _bx  = _px + int(math.cos(_ang) * _spd * _prg)
                _by  = _py + int(math.sin(_ang) * _spd * _prg) - int(55 * _prg)
                _ba  = int(240 * max(0, 1 - _prg * 1.2))
                _sz  = max(1, int(4 * (1 - _prg)) + 1)
                _ps2 = pygame.Surface((_sz * 2 + 2, _sz * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(_ps2, (*_col, _ba), (_sz + 1, _sz + 1), _sz)
                self.screen.blit(_ps2, (_bx - _sz - 1, _by - _sz - 1))

        self.hud.draw(self.screen, self.player, self.floor, self.combo_system,
                      play_time_ms=self._play_time_ms)

        # Darkness curse (vignette)
        if self.floor.curse_type == "darkness":
            self._draw_vignette()

        # Stats table overlay (Tab key)
        if self._show_stats:
            self._draw_stats_table()

        # Pause button (top-right corner)
        self._draw_pause_button()

        # Feedback
        now = pygame.time.get_ticks()
        if self._feedback_msg and now < self._feedback_expire:
            surf = self.font_med.render(self._feedback_msg, True, YELLOW)
            self.screen.blit(surf, (SCREEN_WIDTH//2 - surf.get_width()//2, 50))

        # Boss death flash overlay
        if now < self._boss_flash_end:
            frac = (self._boss_flash_end - now) / 700.0
            fla = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            fla.fill((255, 255, 255, int(240 * frac)))
            self.screen.blit(fla, (0, 0))

        # Color drain (grayscale) — fades out over _color_drain_end window
        if now < self._color_drain_end:
            try:
                drain_frac = max(0.0, (self._color_drain_end - now) / 2200.0)
                arr = pygame.surfarray.pixels3d(self.screen)
                gray = (0.299 * arr[:,:,0] + 0.587 * arr[:,:,1]
                        + 0.114 * arr[:,:,2]).astype(np.uint8)
                for ch in range(3):
                    arr[:,:,ch] = (gray * drain_frac
                                   + arr[:,:,ch] * (1 - drain_frac)).astype(np.uint8)
                del arr   # release pixel lock
            except Exception:
                pass

        # Screen shake
        if now < self._shake_end:
            amp = int(self._shake_amp * max(0.0, (self._shake_end - now) / 3000.0))
            if amp > 0:
                ox = random.randint(-amp, amp)
                oy = random.randint(-amp, amp)
                snap = self.screen.copy()
                self.screen.fill((0, 0, 0))
                self.screen.blit(snap, (ox, oy))

    def _draw_vignette(self):
        play_h = SCREEN_HEIGHT - 96   # clip to HUD_Y — never overlap the panel
        vig = pygame.Surface((SCREEN_WIDTH, play_h), pygame.SRCALPHA)
        vig.fill((0, 0, 0, 180))
        cx = int(self.player.x)
        cy = int(min(self.player.y, play_h - 1))
        radius = 160
        for r in range(radius, 0, -8):
            alpha = int(180 * (1 - r / radius))
            pygame.draw.circle(vig, (0, 0, 0, max(0, 180 - alpha * 2)), (cx, cy), r)
        pygame.draw.circle(vig, (0, 0, 0, 0), (cx, cy), radius // 2)
        self.screen.blit(vig, (0, 0))

    # ------------------------------------------------------------------
    def _draw_stats_table(self):
        """Tab-toggled in-game stats overlay panel."""
        p   = self.player
        fl  = self.floor
        cx  = SCREEN_WIDTH // 2
        pw, ph = 420, 240
        px  = cx - pw // 2
        py  = 60

        # Panel background
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((6, 4, 18, 220))
        pygame.draw.rect(bg, (90, 68, 160, 220), (0, 0, pw, ph), 2, border_radius=12)
        pygame.draw.rect(bg, (55, 42, 100, 80),  (4, 4, pw - 8, ph - 8), 1, border_radius=10)
        self.screen.blit(bg, (px, py))

        fm = pygame.font.SysFont("monospace", 14, bold=True)
        fs = pygame.font.SysFont("monospace", 13)

        # Title row
        hdr = fm.render("PLAYER STATS", True, (180, 150, 255))
        self.screen.blit(hdr, (cx - hdr.get_width() // 2, py + 10))
        pygame.draw.line(self.screen, (75, 58, 120),
                         (px + 14, py + 28), (px + pw - 14, py + 28), 1)

        # Two-column table
        col_left  = px + 22
        col_right = px + pw // 2 + 10
        rows_l = [
            ("Level",   str(p.level),              (210, 185, 255)),
            ("HP",      f"{p.hp}/{p.max_hp}",      (80, 220, 100)),
            ("Stamina", f"{int(p.stamina)}/{p.max_stamina}", (70, 200, 140)),
            ("ATK",     str(p.attack),              (235, 180, 60)),
            ("DEF",     str(p.defense),             (80, 160, 240)),
            ("Gold",    str(p.gold),                (255, 215, 0)),
        ]
        rows_r = [
            ("Floor",   str(fl.floor_num),          (185, 160, 255)),
            ("Kills",   str(p.kills),               (220, 100, 100)),
            ("Enemies", str(sum(1 for e in fl.enemies if e.alive)), (255, 130, 50)),
            ("Items",   str(sum(1 for i in fl.items if not i.collected)), (120, 200, 255)),
            ("Curse",   fl.curse_type.replace("_", " ").title() if fl.curse_type != "none" else "None",
             (255, 185, 30) if fl.curse_type != "none" else (120, 110, 150)),
            ("Boss Fl", "Yes" if fl.is_boss else "No",
             (255, 80, 60) if fl.is_boss else (100, 100, 130)),
        ]
        for i, (lbl, val, col) in enumerate(rows_l):
            ry = py + 36 + i * 30
            # Row stripe
            if i % 2 == 0:
                stripe = pygame.Surface((pw // 2 - 16, 26), pygame.SRCALPHA)
                stripe.fill((255, 255, 255, 6))
                self.screen.blit(stripe, (col_left - 4, ry - 2))
            key_s = fs.render(lbl, True, (150, 135, 180))
            val_s = fm.render(val, True, col)
            self.screen.blit(key_s, (col_left, ry))
            self.screen.blit(val_s, (col_left + 90, ry))
        for i, (lbl, val, col) in enumerate(rows_r):
            ry = py + 36 + i * 30
            if i % 2 == 0:
                stripe = pygame.Surface((pw // 2 - 16, 26), pygame.SRCALPHA)
                stripe.fill((255, 255, 255, 6))
                self.screen.blit(stripe, (col_right - 4, ry - 2))
            key_s = fs.render(lbl, True, (150, 135, 180))
            val_s = fm.render(val, True, col)
            self.screen.blit(key_s, (col_right, ry))
            self.screen.blit(val_s, (col_right + 90, ry))

        pygame.draw.line(self.screen, (65, 50, 105),
                         (cx, py + 30), (cx, py + ph - 10), 1)

        hint = pygame.font.SysFont("monospace", 11).render(
            "[TAB] toggle stats", True, (80, 70, 110))
        self.screen.blit(hint, (px + pw - hint.get_width() - 8, py + ph - 16))

    # ------------------------------------------------------------------
    _PAUSE_BTN = pygame.Rect(SCREEN_WIDTH - 52, 8, 44, 28)

    def _draw_pause_button(self):
        r    = self._PAUSE_BTN
        hov  = r.collidepoint(*pygame.mouse.get_pos())
        bg_c = (70, 55, 110) if hov else (40, 32, 68)
        pygame.draw.rect(self.screen, bg_c, r, border_radius=6)
        pygame.draw.rect(self.screen, (120, 90, 200) if hov else (80, 62, 130),
                         r, 1, border_radius=6)
        # Two vertical bars (pause symbol)
        bx, by = r.x + 12, r.y + 8
        pygame.draw.rect(self.screen, (210, 190, 255), (bx, by, 5, 12), border_radius=2)
        pygame.draw.rect(self.screen, (210, 190, 255), (bx + 11, by, 5, 12), border_radius=2)

    # ------------------------------------------------------------------
    def _draw_merchant(self):
        if self._merchant:
            self._merchant.draw(self.screen, self.player)
            # Feedback
            now = pygame.time.get_ticks()
            if self._feedback_msg and now < self._feedback_expire:
                surf = self.font_med.render(self._feedback_msg, True, YELLOW)
                self.screen.blit(surf, (SCREEN_WIDTH//2 - surf.get_width()//2, 130))

    # ------------------------------------------------------------------
    def _draw_boss_cutscene(self):
        t       = pygame.time.get_ticks() / 1000.0
        elapsed = pygame.time.get_ticks() - getattr(self, "_cutscene_start_ms", 0)
        prog    = min(1.0, elapsed / 5000.0)   # 0→1 over 5 seconds
        cx      = SCREEN_WIDTH  // 2
        cy      = SCREEN_HEIGHT // 2
        floor_n = self.current_floor_num

        # ── Blood-red gradient background ──────────────────────────────
        for row in range(SCREEN_HEIGHT):
            frac = row / SCREEN_HEIGHT
            r = int(22 + 30 * (1 - frac))
            g = int(4  +  4 * (1 - frac))
            b = int(6  +  4 * (1 - frac))
            pygame.draw.rect(self.screen, (r, g, b), (0, row, SCREEN_WIDTH, 1))

        # ── Animated dark radial vignette ───────────────────────────────
        vig = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for ri in range(380, 0, -20):
            va = int(160 * (1 - ri / 380))
            pygame.draw.circle(vig, (0, 0, 0, va), (cx, cy), ri)
        pygame.draw.circle(vig, (0, 0, 0, 0), (cx, cy), 200)
        self.screen.blit(vig, (0, 0))

        # ── Red lightning bolts emanating from centre ───────────────────
        rng_bolt = random.Random(int(t * 12))
        bolt_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for _ in range(6):
            ang = rng_bolt.uniform(0, math.pi * 2)
            seg_x, seg_y = cx, cy
            for seg in range(rng_bolt.randint(4, 8)):
                nx = seg_x + int(math.cos(ang) * rng_bolt.randint(30, 80))
                ny = seg_y + int(math.sin(ang) * rng_bolt.randint(30, 80))
                ang += rng_bolt.uniform(-0.6, 0.6)
                ba  = int(rng_bolt.randint(60, 180))
                pygame.draw.line(bolt_surf, (255, 50, 30, ba), (seg_x, seg_y), (nx, ny), 2)
                seg_x, seg_y = nx, ny
        self.screen.blit(bolt_surf, (0, 0))

        # ── BOSS FLOOR label (fade in) ──────────────────────────────────
        fade_in = min(1.0, prog * 4)        # fully visible by 25%
        lbl_a   = int(255 * fade_in)

        font_xl2   = pygame.font.SysFont("monospace", 18, bold=True)
        floor_txt  = font_xl2.render(f"FLOOR  {floor_n}", True, (200, 80, 60))
        floor_txt.set_alpha(lbl_a)
        self.screen.blit(floor_txt,
                         (cx - floor_txt.get_width() // 2, cy - 130))

        # ── "BOSS ENCOUNTER" animated title ────────────────────────────
        font_boss = pygame.font.SysFont("monospace", 56, bold=True)
        pulse_t   = 0.85 + 0.15 * math.sin(t * 3.5)
        rc        = int(255 * pulse_t)
        boss_col  = (rc, int(40 * pulse_t), int(30 * pulse_t))
        # Glow behind text
        for gd in range(8, 0, -2):
            gs  = font_boss.render("BOSS ENCOUNTER", True, (100, 10, 10))
            gs.set_alpha(int(30 * (gd / 8) * fade_in))
            for dx2, dy2 in [(-gd, 0), (gd, 0), (0, -gd), (0, gd)]:
                self.screen.blit(gs, (cx - gs.get_width() // 2 + dx2, cy - 40 + dy2))
        title_s = font_boss.render("BOSS ENCOUNTER", True, boss_col)
        title_s.set_alpha(lbl_a)
        self.screen.blit(title_s, (cx - title_s.get_width() // 2, cy - 42))

        # Decorative lines flanking title
        tw = title_s.get_width()
        lw2 = tw + 80
        line_a = lbl_a
        line_surf = pygame.Surface((lw2, 4), pygame.SRCALPHA)
        for xi in range(lw2):
            frac2 = abs(xi / lw2 - 0.5) * 2   # 0 centre → 1 edge
            ca = int(line_a * (1 - frac2 * 0.7))
            pygame.draw.line(line_surf, (220, 50, 30, ca), (xi, 1), (xi, 3))
        self.screen.blit(line_surf, (cx - lw2 // 2, cy - 50))
        self.screen.blit(line_surf, (cx - lw2 // 2, cy + 20))

        # ── Boss name / flavour ─────────────────────────────────────────
        font_sub2  = pygame.font.SysFont("monospace", 20, bold=True)
        name_s  = font_sub2.render("The Orc Warlord", True, (230, 160, 50))
        name_s.set_alpha(lbl_a)
        self.screen.blit(name_s, (cx - name_s.get_width() // 2, cy + 34))

        font_flav = pygame.font.SysFont("monospace", 14)
        lines = [
            "A warlord draped in ancient armour rises from the shadows.",
            "His warcry shakes the very stones of the tower.",
            "Minions surge at his command — prepare yourself.",
        ]
        for li, line in enumerate(lines):
            fa2 = min(1.0, max(0.0, prog * 5 - 0.5 - li * 0.25))
            ls  = font_flav.render(line, True, (190, 140, 130))
            ls.set_alpha(int(255 * fa2))
            self.screen.blit(ls, (cx - ls.get_width() // 2, cy + 78 + li * 22))

        # ── "Press any key" prompt (blinks in last 50%) ─────────────────
        if prog > 0.4:
            blink_a = int(200 * abs(math.sin(t * 3.5)))
            skip_s  = font_flav.render("Press any key to begin the battle", True, (220, 200, 180))
            skip_s.set_alpha(blink_a)
            self.screen.blit(skip_s, (cx - skip_s.get_width() // 2, SCREEN_HEIGHT - 72))

        # ── Countdown bar at bottom ──────────────────────────────────────
        bar_w = int(SCREEN_WIDTH * 0.5 * (1 - prog))
        bar_x = cx - bar_w // 2
        bar_y = SCREEN_HEIGHT - 32
        pygame.draw.rect(self.screen, (60, 10, 10), (cx - SCREEN_WIDTH // 4, bar_y, SCREEN_WIDTH // 2, 8), border_radius=4)
        if bar_w > 0:
            pygame.draw.rect(self.screen, (220, 50, 30), (bar_x, bar_y, bar_w, 8), border_radius=4)

    # ------------------------------------------------------------------
    def _draw_name_entry(self):
        t  = pygame.time.get_ticks() / 1000.0
        cx = SCREEN_WIDTH // 2

        # Rich gradient background (top dark indigo → bottom deep navy)
        for row in range(SCREEN_HEIGHT):
            frac = row / SCREEN_HEIGHT
            r = int(8  + 10 * (1 - frac))
            g = int(6  +  6 * (1 - frac))
            b = int(22 + 22 * (1 - frac))
            pygame.draw.rect(self.screen, (r, g, b), (0, row, SCREEN_WIDTH, 1))

        # Stars
        star_s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for s in self._menu_stars:
            alpha = int(s["alpha"] * 0.55 * (0.6 + 0.4 * math.sin(s["twinkle"] + t)))
            alpha = max(0, min(255, alpha))
            pygame.draw.circle(star_s, (255, 255, 255, alpha),
                               (int(s["x"]), int(s["y"])), s["size"])
        self.screen.blit(star_s, (0, 0))

        # Ambient orb glow behind panel
        for ox2, oy2, gr, base_a, col in [
            (cx, 330, 260, 40, (80, 50, 200)),
            (cx - 180, 420, 140, 25, (50, 80, 200)),
            (cx + 200, 280, 120, 22, (120, 40, 180)),
        ]:
            glo = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            for ri in range(gr, 0, -16):
                ga = int(base_a * (ri / gr) * (0.6 + 0.4 * math.sin(t * 1.4 + ri * 0.02)))
                pygame.draw.circle(glo, (*col, max(0, ga)), (gr, gr), ri)
            self.screen.blit(glo, (ox2 - gr, oy2 - gr))

        pulse  = 0.7 + 0.3 * math.sin(t * 2.5)
        brd_c  = (int(80 + 60 * pulse), int(55 + 40 * pulse), int(190 + 55 * pulse))

        # Outer decorative frame (full-width scanline look)
        frame_margin = 48
        frame_rect   = pygame.Rect(frame_margin, 130, SCREEN_WIDTH - frame_margin * 2, 400)
        frame_s = pygame.Surface((frame_rect.w, frame_rect.h), pygame.SRCALPHA)
        frame_s.fill((6, 4, 18, 160))
        pygame.draw.rect(frame_s, (*brd_c, 90),  (0, 0, frame_rect.w, frame_rect.h), 1,
                         border_radius=18)
        pygame.draw.rect(frame_s, (*brd_c, 35),  (5, 5, frame_rect.w - 10, frame_rect.h - 10),
                         1, border_radius=14)
        self.screen.blit(frame_s, (frame_rect.x, frame_rect.y))

        # Corner bracket ornaments on outer frame
        for ox2, oy2, fx, fy in [
            (frame_rect.left  + 14, frame_rect.top    + 14,  1,  1),
            (frame_rect.right - 14, frame_rect.top    + 14, -1,  1),
            (frame_rect.left  + 14, frame_rect.bottom - 14,  1, -1),
            (frame_rect.right - 14, frame_rect.bottom - 14, -1, -1),
        ]:
            pygame.draw.lines(self.screen, brd_c, False,
                              [(ox2, oy2), (ox2 + fx * 22, oy2),
                               (ox2 + fx * 22, oy2 + fy * 4),
                               (ox2 + fx * 4,  oy2 + fy * 4),
                               (ox2 + fx * 4,  oy2 + fy * 22),
                               (ox2,           oy2 + fy * 22)], 1)
            # Tiny diamond at corner junction
            pygame.draw.polygon(self.screen, brd_c,
                                [(ox2 + fx * 4, oy2 + fy * 4 - 3 * fy),
                                 (ox2 + fx * 4 + 3 * fx, oy2 + fy * 4),
                                 (ox2 + fx * 4, oy2 + fy * 4 + 3 * fy),
                                 (ox2 + fx * 4 - 3 * fx, oy2 + fy * 4)])

        # Title with glow layers
        title_y = frame_rect.top + 26
        title = self.font_title.render("ENTER YOUR NAME", True, (170, 140, 255))
        title_w = title.get_width()
        for gd in range(6, 0, -2):
            gt = self.font_title.render("ENTER YOUR NAME", True,
                                        (int(60 * pulse), int(38 * pulse), int(150 * pulse)))
            gt.set_alpha(int(28 + 12 * math.sin(t * 2.2)))
            for dx2, dy2 in [(-gd, 0), (gd, 0), (0, -gd), (0, gd)]:
                self.screen.blit(gt, (cx - title_w // 2 + dx2, title_y + dy2))
        self.screen.blit(title, (cx - title_w // 2, title_y))

        # Decorative line under title with center diamond
        line_y = title_y + title.get_height() + 10
        lw = title_w + 60
        pygame.draw.line(self.screen, (55, 42, 100),
                         (cx - lw // 2, line_y), (cx + lw // 2, line_y), 1)
        pygame.draw.polygon(self.screen, brd_c,
                            [(cx - 5, line_y - 3), (cx, line_y + 3),
                             (cx + 5, line_y - 3)])

        # Subtitle hint
        sub = self.font_sm.render("Press Enter to confirm   ·   Esc to go back",
                                  True, (130, 110, 185))
        self.screen.blit(sub, (cx - sub.get_width() // 2, line_y + 12))

        # Input box — wider
        box_w, box_h = 480, 58
        bx = cx - box_w // 2
        by = line_y + 44

        # Box background
        pygame.draw.rect(self.screen, (12, 9, 30), (bx, by, box_w, box_h), border_radius=10)

        # Multi-layer animated glow border
        for bi in range(5, 0, -1):
            glow_a = int(70 * (bi / 5) * (0.6 + 0.4 * math.sin(t * 3)))
            gc = (int(brd_c[0] * bi / 5), int(brd_c[1] * bi / 5), int(brd_c[2] * bi / 5))
            gbs = pygame.Surface((box_w + bi * 2, box_h + bi * 2), pygame.SRCALPHA)
            pygame.draw.rect(gbs, (*gc, glow_a),
                             (0, 0, box_w + bi * 2, box_h + bi * 2), 1, border_radius=10 + bi)
            self.screen.blit(gbs, (bx - bi, by - bi))

        pygame.draw.rect(self.screen, brd_c, (bx, by, box_w, box_h), 2, border_radius=10)
        # Top shine inside box
        shine = pygame.Surface((box_w - 4, box_h // 3), pygame.SRCALPHA)
        shine.fill((255, 255, 255, 10))
        self.screen.blit(shine, (bx + 2, by + 2))

        # Typed text + cursor
        display  = self._name_input + ("|" if int(t * 2) % 2 == 0 else " ")
        inp_surf = self.font_big.render(display, True, WHITE)
        # Shadow
        shd = self.font_big.render(display, True, (0, 0, 0))
        shd.set_alpha(80)
        center_x = bx + box_w // 2 - inp_surf.get_width() // 2
        center_y = by + box_h // 2 - inp_surf.get_height() // 2
        self.screen.blit(shd,     (center_x + 1, center_y + 1))
        self.screen.blit(inp_surf, (center_x,     center_y))

        # Small label above box
        lbl = self.font_sm.render("Your Hero's Name", True, (100, 84, 155))
        self.screen.blit(lbl, (bx, by - 18))

    # ------------------------------------------------------------------
    def _draw_gameover(self):
        t   = pygame.time.get_ticks() / 1000.0
        won = getattr(self, "_won", False)
        cx  = SCREEN_WIDTH // 2

        # ══════════════════════════════════════════════════════════════
        if won:
            # ── YOU WIN background ────────────────────────────────────
            # Deep cosmic gradient: dark indigo top → rich amber bottom
            for row in range(SCREEN_HEIGHT):
                frac = row / SCREEN_HEIGHT
                r = int(12 + 44 * frac + 18 * (1 - frac))
                g = int(6  + 20 * frac +  8 * (1 - frac))
                b = int(38 - 24 * frac)
                pygame.draw.rect(self.screen, (r, g, b), (0, row, SCREEN_WIDTH, 1))

            # Rotating crepuscular light rays from top-center
            rays = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for i in range(20):
                ang = i * math.pi * 2 / 20 + t * 0.10
                length = 900
                dx1 = math.cos(ang - 0.05) * length
                dy1 = math.sin(ang - 0.05) * length
                dx2 = math.cos(ang + 0.05) * length
                dy2 = math.sin(ang + 0.05) * length
                alpha_ray = max(0, int(14 + 10 * math.sin(t * 1.6 + i * 0.9)))
                pygame.draw.polygon(rays, (255, 220, 90, alpha_ray),
                                    [(cx, -40), (cx + int(dx1), -40 + int(dy1)),
                                     (cx + int(dx2), -40 + int(dy2))])
            self.screen.blit(rays, (0, 0))

            # Deep golden glow orbs
            glow = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for gx2, gy2, gr, base_a in [
                (cx, 80,  310, 65), (180, 640, 240, 50),
                (780, 560, 210, 45), (cx, 380, 190, 40),
            ]:
                for ra in range(gr, 0, -18):
                    a = int(base_a * (ra / gr) * (0.72 + 0.28 * math.sin(t * 1.9 + ra * 0.035)))
                    pygame.draw.circle(glow, (255, 205, 50, max(0, a)), (gx2, gy2), ra)
            self.screen.blit(glow, (0, 0))

            # Rich confetti rain: rectangles + circles + lines
            conf_cols = [(255,70,70),(60,255,110),(80,150,255),(255,215,40),(200,70,255),(255,170,40)]
            rng = random.Random(55)
            cf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for i in range(160):
                spd   = rng.uniform(45, 135)
                fx    = rng.randint(0, SCREEN_WIDTH)
                fy    = int((rng.randint(0, SCREEN_HEIGHT) + t * spd) % SCREEN_HEIGHT)
                col   = rng.choice(conf_cols)
                alpha = max(0, min(255, int(170 + 70 * math.sin(t * 4.5 + i * 0.65))))
                shape = i % 3
                if shape == 0:
                    pygame.draw.rect(cf, (*col, alpha),
                                     (fx, fy, rng.randint(4, 11), rng.randint(2, 6)),
                                     border_radius=1)
                elif shape == 1:
                    pygame.draw.circle(cf, (*col, alpha), (fx, fy), rng.randint(2, 4))
                else:
                    ex2 = fx + rng.randint(-7, 7)
                    ey2 = fy + rng.randint(-7, 7)
                    pygame.draw.line(cf, (*col, alpha), (fx, fy), (ex2, ey2), 2)
            self.screen.blit(cf, (0, 0))

            # Gold sparkle stars with cross halos
            rng2 = random.Random(99)
            sp = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for i in range(90):
                sx = rng2.randint(0, SCREEN_WIDTH)
                sy = rng2.randint(0, SCREEN_HEIGHT)
                ph = rng2.uniform(0, math.pi * 2)
                a  = int(70 + 180 * abs(math.sin(t * 3.0 + ph)))
                sz = rng2.randint(1, 4)
                pygame.draw.circle(sp, (255, 245, 140, a), (sx, sy), sz)
                if sz >= 3:
                    pygame.draw.line(sp, (255, 245, 140, a // 2),
                                     (sx - sz * 2, sy), (sx + sz * 2, sy), 1)
                    pygame.draw.line(sp, (255, 245, 140, a // 2),
                                     (sx, sy - sz * 2), (sx, sy + sz * 2), 1)
            self.screen.blit(sp, (0, 0))

        else:
            # ── GAME OVER background ──────────────────────────────────
            # Near-black top → deep crimson bottom
            for row in range(SCREEN_HEIGHT):
                frac = row / SCREEN_HEIGHT
                r = int(10 + 60 * frac + 14 * (1 - frac))
                g = int(2  +  5 * frac)
                b = int(5  +  8 * frac)
                pygame.draw.rect(self.screen, (r, g, b), (0, row, SCREEN_WIDTH, 1))

            # Intense crimson glow blobs
            glow = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for gx2, gy2, gr, base_a in [
                (150, SCREEN_HEIGHT - 80, 340, 80), (820, 70, 280, 70),
                (cx,  SCREEN_HEIGHT - 60, 260, 70), (cx, 320, 260, 55),
            ]:
                for ra in range(gr, 0, -18):
                    a = int(base_a * (ra / gr) * (0.62 + 0.38 * math.sin(t * 0.95 + ra * 0.045)))
                    pygame.draw.circle(glow, (230, 20, 8, max(0, a)), (gx2, gy2), ra)
            self.screen.blit(glow, (0, 0))

            # Animated ground fire columns at bottom
            fire_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            rng_f = random.Random(11)
            for fi in range(26):
                base_x = int((fi / 26) * SCREEN_WIDTH)
                sway   = int(22 * math.sin(t * 2.8 + fi * 1.2))
                fh     = int(70 + 55 * math.sin(t * 3.2 + fi * 0.75))
                for layer in range(fh):
                    lp     = layer / fh
                    al     = int(150 * (1 - lp) * (0.55 + 0.45 * math.sin(t * 4.5 + fi)))
                    fw2    = max(1, int(20 * (1 - lp * 0.65)))
                    col_g2 = int(30 + 130 * (1 - lp))
                    pygame.draw.line(fire_surf, (255, col_g2, 8, max(0, al)),
                                     (base_x + sway - fw2 // 2, SCREEN_HEIGHT - layer),
                                     (base_x + sway + fw2 // 2, SCREEN_HEIGHT - layer), 1)
            self.screen.blit(fire_surf, (0, 0))

            # Rising ash/ember particles
            rng = random.Random(77)
            em = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for i in range(100):
                spd  = rng.uniform(25, 80)
                ex   = rng.randint(0, SCREEN_WIDTH)
                ey_b = rng.randint(0, SCREEN_HEIGHT)
                ey   = int((ey_b - t * spd) % SCREEN_HEIGHT)
                sway = int(14 * math.sin(t * 1.3 + i * 0.42))
                col_g = rng.randint(35, 145)
                alpha = max(0, min(255, int(85 + 155 * abs(math.sin(t * 1.9 + i * 0.42)))))
                pygame.draw.circle(em, (255, col_g, 8, alpha), (ex + sway, ey),
                                   rng.randint(1, 3))
            self.screen.blit(em, (0, 0))

            # Lightning cracks flashing across upper screen
            rng3 = random.Random(42)
            lc = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for i in range(6):
                ph = rng3.uniform(0, math.pi * 2)
                if abs(math.sin(t * 1.6 + ph)) > 0.72:
                    lx = rng3.randint(80, SCREEN_WIDTH - 80)
                    pts = [(lx, rng3.randint(20, 100))]
                    for _ in range(rng3.randint(4, 7)):
                        pts.append((pts[-1][0] + rng3.randint(-45, 45),
                                    pts[-1][1] + rng3.randint(30, 90)))
                    la = int(190 * abs(math.sin(t * 1.6 + ph)))
                    for s2 in range(len(pts) - 1):
                        pygame.draw.line(lc, (255, 55, 55, la), pts[s2], pts[s2 + 1], 2)
                        pygame.draw.line(lc, (255, 160, 160, la // 3), pts[s2], pts[s2 + 1], 5)
            self.screen.blit(lc, (0, 0))

        # ── Title (large, dramatic) ────────────────────────────────────
        title_str = "YOU WIN!" if won else "GAME OVER"
        if won:
            pulse = 0.82 + 0.18 * math.sin(t * 2.6)
            tc = (int(255 * pulse), int(215 * pulse), int(28 * pulse))
            gc = (110, 75, 0)
        else:
            shake = int(4 * math.sin(t * 22)) if t < 2.5 else 0
            tc    = (225, 18, 18)
            gc    = (110, 0, 0)

        # Multi-layer outer glow
        for r2 in range(12, 0, -3):
            gt = self.font_xl.render(title_str, True, gc)
            gt.set_alpha(max(0, int(28 + 12 * math.sin(t * 2.2))))
            for dx2, dy2 in [(-r2, 0), (r2, 0), (0, -r2), (0, r2),
                              (-r2, -r2), (r2, -r2), (-r2, r2), (r2, r2)]:
                ox = shake if not won else 0
                self.screen.blit(gt, (cx - gt.get_width() // 2 + dx2 + ox, 58 + dy2))
        title_surf = self.font_xl.render(title_str, True, tc)
        ox = shake if not won else 0
        self.screen.blit(title_surf, (cx - title_surf.get_width() // 2 + ox, 58))

        # ── Stats card ─────────────────────────────────────────────────
        summary = getattr(self, "_last_summary", {})
        pname   = summary.get("player_name", self._player_name)
        floor_v = summary.get("floor_reached", self.current_floor_num)
        kills_v = summary.get("kills", self.player.kills)
        combo_v = summary.get("max_combo", 0)
        dur     = summary.get("duration_sec", 0)
        sid     = summary.get("session_id", "")
        dur_str = self._fmt_time(dur)

        card_x, card_y, card_w, card_h = cx - 290, 158, 580, 136
        # Card background with animated edge glow
        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        card.fill((0, 0, 0, 125))
        if won:
            edge_a = int(180 + 60 * math.sin(t * 2.4))
            pygame.draw.rect(card, (255, 200, 50, edge_a),  (0, 0, card_w, card_h), 2,
                             border_radius=14)
            pygame.draw.rect(card, (255, 240, 120, edge_a // 3), (3, 3, card_w-6, card_h-6),
                             1, border_radius=12)
        else:
            pygame.draw.rect(card, (180, 20, 20, 160), (0, 0, card_w, card_h), 2,
                             border_radius=14)
        self.screen.blit(card, (card_x, card_y))

        # Corner ornaments for win screen
        if won:
            orn_col = (255, 215, 0)
            for ox2, oy2 in [(card_x + 12, card_y + 12), (card_x + card_w - 12, card_y + 12),
                             (card_x + 12, card_y + card_h - 12),
                             (card_x + card_w - 12, card_y + card_h - 12)]:
                for ang_d in range(0, 360, 45):
                    a_r = math.radians(ang_d + t * 30)
                    pygame.draw.line(self.screen, orn_col,
                                     (ox2, oy2),
                                     (ox2 + int(math.cos(a_r) * 7),
                                      oy2 + int(math.sin(a_r) * 7)), 1)

        # Player name — centered
        nm_s = self.font_med.render(f"Player: {pname}", True, (210, 185, 255))
        self.screen.blit(nm_s, (cx - nm_s.get_width() // 2, card_y + 14))

        # Two-column stats: right-align left col at cx-28, left-align right col at cx+28
        sep_s  = self.font_med.render("|", True, (110, 100, 140))
        sep_sx = cx - sep_s.get_width() // 2

        fl_s  = self.font_med.render(f"Floor {floor_v}", True, WHITE)
        kl_s  = self.font_med.render(f"Kills: {kills_v}", True, WHITE)
        self.screen.blit(fl_s,  (cx - 28 - fl_s.get_width(),  card_y + 48))
        self.screen.blit(sep_s, (sep_sx,                        card_y + 48))
        self.screen.blit(kl_s,  (cx + 28,                       card_y + 48))

        mc_s  = self.font_med.render(f"Max Combo: x{combo_v}", True, YELLOW)
        tm_s  = self.font_med.render(f"Time: {dur_str}",        True, YELLOW)
        self.screen.blit(mc_s,  (cx - 28 - mc_s.get_width(),   card_y + 82))
        self.screen.blit(sep_s, (sep_sx,                         card_y + 82))
        self.screen.blit(tm_s,  (cx + 28,                        card_y + 82))

        # ── Rankings panel ─────────────────────────────────────────────
        rk_y, rk_w, rk_h = 306, 620, 192
        rk_card = pygame.Surface((rk_w, rk_h), pygame.SRCALPHA)
        rk_card.fill((0, 0, 0, 110))
        if won:
            pygame.draw.rect(rk_card, (180, 148, 30, 140), (0, 0, rk_w, rk_h), 1,
                             border_radius=12)
        else:
            pygame.draw.rect(rk_card, (100, 90, 160, 140), (0, 0, rk_w, rk_h), 1,
                             border_radius=12)
        self.screen.blit(rk_card, (cx - rk_w // 2, rk_y))

        player_rank, total, ctx_entries, player_idx = \
            self.leaderboard.get_player_context(sid, n=2)
        RANK_COL = {1: (255, 215, 0), 2: (200, 200, 215), 3: (205, 127, 50)}

        if won:
            # Title row
            hdr = self.font_med.render("SPEED HALL OF FAME", True, GOLD_COLOR)
            self.screen.blit(hdr, (cx - hdr.get_width() // 2, rk_y + 8))
            pygame.draw.line(self.screen, (160, 130, 20),
                             (cx - rk_w // 2 + 14, rk_y + 30),
                             (cx + rk_w // 2 - 14, rk_y + 30), 1)
            # Top 3 speed entries
            top3 = self.leaderboard.get_speed_top3()
            for j, entry in enumerate(top3[:3]):
                d   = float(entry.get("duration_sec", 0))
                ts  = self._fmt_time(d)
                nm  = str(entry.get("player_name", "?"))[:12]
                col = RANK_COL.get(j + 1, WHITE)
                tag = "  <- YOU" if entry.get("session_id") == sid else ""
                medals = {0: "#1", 1: "#2", 2: "#3"}
                row_txt = f"{medals[j]}  {nm:<14} {ts}{tag}"
                # Highlight strip
                if entry.get("session_id") == sid:
                    hl = pygame.Surface((rk_w - 16, 24), pygame.SRCALPHA)
                    hl.fill((255, 220, 0, 30))
                    self.screen.blit(hl, (cx - rk_w // 2 + 8, rk_y + 36 + j * 32 - 2))
                row = self.font_med.render(row_txt, True, col)
                self.screen.blit(row, (cx - 215, rk_y + 36 + j * 32))
            pygame.draw.line(self.screen, (120, 100, 20),
                             (cx - rk_w // 2 + 14, rk_y + 140),
                             (cx + rk_w // 2 - 14, rk_y + 140), 1)
            rank_s = self.font_med.render(
                f"Your Rank: #{player_rank} of {total} players", True, WHITE)
            self.screen.blit(rank_s, (cx - rank_s.get_width() // 2, rk_y + 150))
        else:
            hdr = self.font_med.render(
                f"YOUR RANK:  #{player_rank} of {total} players", True, WHITE)
            self.screen.blit(hdr, (cx - hdr.get_width() // 2, rk_y + 8))
            pygame.draw.line(self.screen, (80, 70, 120),
                             (cx - rk_w // 2 + 14, rk_y + 32),
                             (cx + rk_w // 2 - 14, rk_y + 32), 1)
            for j, entry in enumerate(ctx_entries):
                d   = float(entry.get("duration_sec", 0))
                ts  = self._fmt_time(d)
                nm  = str(entry.get("player_name", "?"))[:12]
                fl  = entry.get("floor_reached", 0)
                rk  = entry.get("rank", "?")
                is_me = (entry.get("session_id") == sid)
                col = YELLOW if is_me else (WHITE if j < player_idx else GRAY)
                row_txt = f"{'>' if is_me else ' '} #{rk:<4} {nm:<13} Fl.{fl:<3} {ts}"
                if is_me:
                    hl = pygame.Surface((rk_w - 16, 22), pygame.SRCALPHA)
                    hl.fill((255, 220, 0, 30))
                    self.screen.blit(hl, (cx - rk_w // 2 + 8, rk_y + 38 + j * 28 - 2))
                row = self.font_sm.render(row_txt, True, col)
                self.screen.blit(row, (cx - 230, rk_y + 38 + j * 28))

        # ── Buttons ────────────────────────────────────────────────────
        self._draw_button("Retry",     cx - 120, 506, 240, 48, (65, 28, 85))
        self._draw_button("Main Menu", cx - 120, 560, 240, 48, (28, 48, 72))
        self._draw_button("Stats",     cx - 120, 614, 240, 48, (28, 68, 68))

    # ------------------------------------------------------------------
    def _draw_leaderboard(self):
        t  = pygame.time.get_ticks() / 1000.0
        cx = SCREEN_WIDTH // 2

        # Rich gradient background
        for row in range(SCREEN_HEIGHT):
            frac = row / SCREEN_HEIGHT
            r = int(8  + 12 * (1 - frac))
            g = int(5  +  6 * (1 - frac))
            b = int(22 + 22 * (1 - frac))
            pygame.draw.rect(self.screen, (r, g, b), (0, row, SCREEN_WIDTH, 1))

        # Subtle star field
        star_s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for s in self._menu_stars:
            a = int(s["alpha"] * 0.4 * (0.6 + 0.4 * math.sin(s["twinkle"] + t)))
            a = max(0, min(255, a))
            pygame.draw.circle(star_s, (255, 255, 255, a),
                               (int(s["x"]), int(s["y"])), max(1, s["size"] - 1))
        self.screen.blit(star_s, (0, 0))

        # Title with multi-layer glow
        pulse = 0.85 + 0.15 * math.sin(t * 1.6)
        tc    = (int(255 * pulse), int(210 * pulse), int(0))
        for r2 in range(8, 0, -3):
            gs = self.font_title.render("LEADERBOARD", True, (90, 62, 0))
            gs.set_alpha(int(30 + 12 * math.sin(t * 2)))
            for dx, dy in [(-r2, 0), (r2, 0), (0, -r2), (0, r2)]:
                self.screen.blit(gs, (cx - gs.get_width() // 2 + dx, 18 + dy))
        title = self.font_title.render("LEADERBOARD", True, tc)
        self.screen.blit(title, (cx - title.get_width() // 2, 18))

        # Decorative line under title
        lw = title.get_width() + 40
        pygame.draw.line(self.screen, (140, 110, 20),
                         (cx - lw // 2, 82), (cx + lw // 2, 82), 1)
        pygame.draw.polygon(self.screen, GOLD_COLOR,
                            [(cx - 6, 78), (cx, 84), (cx + 6, 78)])

        # Table card
        tx, ty, tw, th = 24, 90, SCREEN_WIDTH - 48, SCREEN_HEIGHT - 168
        card = pygame.Surface((tw, th), pygame.SRCALPHA)
        card.fill((10, 8, 26, 200))
        pygame.draw.rect(card, (68, 55, 115, 210), (0, 0, tw, th), 1, border_radius=14)
        pygame.draw.rect(card, (45, 36, 82,  100), (4, 4, tw - 8, th - 8), 1, border_radius=12)
        self.screen.blit(card, (tx, ty))

        # Column layout
        cols = [
            (tx + 14,  "#",      "rank"),
            (tx + 56,  "Name",   "player_name"),
            (tx + 248, "Floor",  "floor_reached"),
            (tx + 316, "Kills",  "kills"),
            (tx + 380, "Combo",  "max_combo"),
            (tx + 450, "Time",   "time_str"),
            (tx + 560, "Result", "result"),
        ]
        header_y = ty + 12
        for hcx, label, _ in cols:
            hs = self.font_sm.render(label, True, (175, 150, 255))
            self.screen.blit(hs, (hcx, header_y))
        pygame.draw.line(self.screen, (75, 60, 115),
                         (tx + 8, header_y + 20), (tx + tw - 8, header_y + 20), 1)

        RANK_COL = {1: (255, 215, 0), 2: (210, 210, 225), 3: (210, 135, 55)}
        MEDALS   = {1: "🥇", 2: "🥈", 3: "🥉"}
        _VISIBLE = 16
        all_entries = self.leaderboard.entries
        total       = len(all_entries)
        start       = self._lb_scroll
        entries     = all_entries[start:start + _VISIBLE]

        for i, e in enumerate(entries):
            abs_rank = start + i + 1
            dur = float(e.get("duration_sec", 0))
            ts  = self._fmt_time(dur)
            won_flag = str(e.get("won", "0"))
            vals = {
                "rank":          f"#{abs_rank}",
                "player_name":   str(e.get("player_name", "?"))[:14],
                "floor_reached": str(e.get("floor_reached", "?")),
                "kills":         str(e.get("kills", "?")),
                "max_combo":     f"x{e.get('max_combo', '?')}",
                "time_str":      ts,
                "result":        "WIN" if won_flag == "1" else "---",
            }
            row_color = RANK_COL.get(abs_rank, (165, 155, 190) if abs_rank <= 3 else (110, 102, 135))
            ry = header_y + 22 + i * 26

            # Alternating row tint
            if i % 2 == 0:
                row_tint = pygame.Surface((tw - 12, 24), pygame.SRCALPHA)
                row_tint.fill((255, 255, 255, 6))
                self.screen.blit(row_tint, (tx + 6, ry - 2))

            # Gold highlight strip for top 3
            if abs_rank <= 3:
                hl_a = {1: 60, 2: 40, 3: 28}[abs_rank]
                hl   = pygame.Surface((tw - 12, 24), pygame.SRCALPHA)
                hl.fill((255, 200, 0, hl_a))
                self.screen.blit(hl, (tx + 6, ry - 2))

            for hcx, _, key in cols:
                val_str = vals[key]
                col_use = row_color
                if key == "result" and val_str == "WIN":
                    col_use = (80, 220, 100)
                self.screen.blit(self.font_sm.render(val_str, True, col_use), (hcx, ry))

        if not all_entries:
            s = self.font_med.render("No runs yet — play the game first!", True, (100, 90, 140))
            self.screen.blit(s, (cx - s.get_width() // 2, 330))
        elif total > _VISIBLE:
            hint = self.font_sm.render(
                f"{start+1}–{min(start+_VISIBLE, total)} of {total}   ↑↓ scroll",
                True, (90, 80, 120))
            self.screen.blit(hint, (cx - hint.get_width() // 2, ty + th + 6))

        self._draw_button("Back", cx - 80, SCREEN_HEIGHT - 60, 160, 42,
                          (38, 32, 68), icon=self._icon_back)

    # ------------------------------------------------------------------
    def _draw_paused(self):
        self._draw_playing()
        t  = pygame.time.get_ticks() / 1000.0
        cx = SCREEN_WIDTH // 2

        # Dark blur overlay with radial fade-in from center
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        self.screen.blit(ov, (0, 0))

        # Decorative panel box
        pw, ph = 340, 300
        px, py = cx - pw // 2, 180
        panel  = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 8, 24, 210))
        pygame.draw.rect(panel, (90, 68, 160, 200), (0, 0, pw, ph), 2, border_radius=12)
        # Inner lighter border
        pygame.draw.rect(panel, (60, 46, 110, 100), (4, 4, pw - 8, ph - 8), 1, border_radius=10)
        self.screen.blit(panel, (px, py))

        # Decorative diamond top-center
        dcx = cx
        for dd in range(3, 0, -1):
            da = int(80 * math.sin(t * 2) * (dd / 3))
            pygame.draw.polygon(self.screen, (130, 100, 220, max(0, da)),
                                [(dcx, py - 8), (dcx + 8, py),
                                 (dcx, py + 8), (dcx - 8, py)])
        pygame.draw.polygon(self.screen, (150, 120, 240),
                            [(dcx, py - 8), (dcx + 8, py),
                             (dcx, py + 8), (dcx - 8, py)])

        # Title
        pulse = 0.9 + 0.1 * math.sin(t * 2.5)
        tc    = (int(200 * pulse), int(180 * pulse), int(255 * pulse))
        title = self.font_title.render("PAUSED", True, tc)
        # Glow
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            gs = self.font_title.render("PAUSED", True, (80, 55, 160))
            gs.set_alpha(60)
            self.screen.blit(gs, (cx - title.get_width() // 2 + dx, 214 + dy))
        self.screen.blit(title, (cx - title.get_width() // 2, 214))

        # Divider
        pygame.draw.line(self.screen, (80, 60, 130),
                         (px + 24, 278), (px + pw - 24, 278), 1)

        self._draw_button("Resume",    cx - 90, 296, 180, 48, (38, 58, 100))
        self._draw_button("Main Menu", cx - 90, 356, 180, 48, (58, 28, 58))
        self._draw_button("Stats",     cx - 90, 416, 180, 48, (28, 68, 68))

    # ------------------------------------------------------------------
    def _draw_button(self, text: str, x: int, y: int, w: int, h: int,
                     color=(50, 40, 80), icon: pygame.Surface | None = None):
        rect    = pygame.Rect(x, y, w, h)
        hovered = rect.collidepoint(*pygame.mouse.get_pos())
        t       = pygame.time.get_ticks() / 1000.0

        # Outer glow when hovered
        if hovered:
            for gd in range(6, 0, -2):
                glow_s = pygame.Surface((w + gd * 2, h + gd * 2), pygame.SRCALPHA)
                ga     = int(50 * (gd / 6) * (0.7 + 0.3 * math.sin(t * 4)))
                glow_c = tuple(min(255, c + 80) for c in color)
                pygame.draw.rect(glow_s, (*glow_c, ga),
                                 (0, 0, w + gd * 2, h + gd * 2), border_radius=10)
                self.screen.blit(glow_s, (x - gd, y - gd))

        # Background
        bg = tuple(min(255, c + 40) for c in color) if hovered else color
        pygame.draw.rect(self.screen, bg, rect, border_radius=8)

        # Top shine strip
        shine = pygame.Surface((w, h // 2), pygame.SRCALPHA)
        shine.fill((255, 255, 255, 18 if not hovered else 30))
        self.screen.blit(shine, (x, y))

        # Border — brighter on hover
        brd_c = (160, 130, 220) if hovered else (100, 80, 155)
        pygame.draw.rect(self.screen, brd_c, rect, 2, border_radius=8)
        # Inner highlight line at top
        pygame.draw.line(self.screen, (*brd_c[:3], 80) if hovered else (80, 65, 120),
                         (x + 6, y + 3), (x + w - 6, y + 3), 1)

        surf = self.font_med.render(text, True, WHITE)
        # Text shadow
        shd = self.font_med.render(text, True, (0, 0, 0))
        shd.set_alpha(100)
        if icon:
            total_w = icon.get_width() + 8 + surf.get_width()
            start_x = rect.centerx - total_w // 2
            self.screen.blit(icon, (start_x,
                                    rect.centery - icon.get_height() // 2))
            self.screen.blit(shd,  (start_x + icon.get_width() + 9,
                                    rect.centery - surf.get_height() // 2 + 1))
            self.screen.blit(surf, (start_x + icon.get_width() + 8,
                                    rect.centery - surf.get_height() // 2))
        else:
            self.screen.blit(shd,  (rect.centerx - surf.get_width() // 2 + 1,
                                    rect.centery - surf.get_height() // 2 + 1))
            self.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                    rect.centery - surf.get_height() // 2))

    # ------------------------------------------------------------------
    # SESSION STATS HELPERS
    # ------------------------------------------------------------------
    @staticmethod
    def _fmt_time(seconds: float) -> str:
        s = max(0, int(seconds))
        return f"{s // 60}:{s % 60:02d}"

    def _get_hist_stats(self) -> dict:
        """Aggregate historical stats from in-memory leaderboard (fast, no CSV read)."""
        entries = self.leaderboard.entries
        n = len(entries)
        if n == 0:
            return {
                "total_sessions": 0, "wins": 0, "win_rate": 0.0,
                "best_floor": 0, "best_kills": 0, "best_combo": 0,
                "best_time_sec": None, "avg_kills": 0.0, "avg_floor": 0.0,
                "avg_time_sec": 0.0, "floor_dist": {},
            }
        wins = [e for e in entries if int(e.get("floor_reached", 0)) >= 20]
        avg_kills    = sum(int(e.get("kills", 0)) for e in entries) / n
        avg_floor    = sum(int(e.get("floor_reached", 0)) for e in entries) / n
        avg_time_sec = sum(float(e.get("duration_sec", 0)) for e in entries) / n
        best_floor   = max(int(e.get("floor_reached", 0)) for e in entries)
        best_kills   = max(int(e.get("kills", 0)) for e in entries)
        best_combo   = max(int(e.get("max_combo", 0)) for e in entries)
        best_time_sec = (min(float(e.get("duration_sec", 9999)) for e in wins)
                         if wins else None)
        win_rate   = round(len(wins) / n * 100, 1)
        floor_dist: dict[int, int] = {}
        for e in entries:
            f = max(1, min(20, int(e.get("floor_reached", 1))))
            floor_dist[f] = floor_dist.get(f, 0) + 1
        return {
            "total_sessions": n,
            "wins":           len(wins),
            "win_rate":       win_rate,
            "best_floor":     best_floor,
            "best_kills":     best_kills,
            "best_combo":     best_combo,
            "best_time_sec":  best_time_sec,
            "avg_kills":      round(avg_kills, 1),
            "avg_floor":      round(avg_floor, 1),
            "avg_time_sec":   avg_time_sec,
            "floor_dist":     floor_dist,
        }

    def _get_session_stats(self) -> dict:
        log = self.stat_tracker.log
        play_sec = self._play_time_ms / 1000.0

        kills_by_type: dict[str, int] = {}
        total_kills = 0
        for r in log:
            if r["event_type"] == "enemies_defeated":
                et = r.get("enemy_type") or "unknown"
                kills_by_type[et] = kills_by_type.get(et, 0) + 1
                total_kills += 1

        combos = [int(r["combo_count"]) for r in log
                  if r.get("combo_count") not in ("", None)]
        max_combo = max(combos, default=0)

        items_by_type: dict[str, int] = {}
        for r in log:
            if r["event_type"] == "items_collected":
                it = r.get("item_type") or "unknown"
                items_by_type[it] = items_by_type.get(it, 0) + 1

        hp_timeline: list[tuple[float, int, int]] = []
        for r in log:
            if r["event_type"] == "player_hp_over_time":
                try:
                    hp_timeline.append((float(r["timestamp"]),
                                        int(r["hp"]),
                                        int(r["max_hp"] or 100)))
                except (ValueError, TypeError):
                    pass

        gold_spent = 0
        for r in log:
            try:
                if r.get("gold_spent") not in ("", None):
                    gold_spent += int(r["gold_spent"])
            except (ValueError, TypeError):
                pass

        curses: list[str] = []
        for r in log:
            if r["event_type"] == "floor_curse_types":
                ct = r.get("curse_type", "none")
                if ct and ct != "none":
                    curses.append(ct)

        return {
            "play_sec":      play_sec,
            "floor_reached": self.current_floor_num,
            "total_kills":   total_kills,
            "kills_by_type": kills_by_type,
            "max_combo":     max_combo,
            "items_by_type": items_by_type,
            "hp_timeline":   hp_timeline,
            "gold_spent":    gold_spent,
            "curses":        curses,
        }

    # ── internal drawing primitives used only by _draw_stats_overlay ─
    @staticmethod
    def _donut_slice(surface, cx, cy, r_out, r_in, a0, a1, color):
        """Polygon-based donut slice: clockwise from a0→a1 (a0>a1 means CW in our coords)."""
        steps = max(14, int(abs(a1 - a0) * r_out / 4))
        angles = [a0 + (a1 - a0) * i / steps for i in range(steps + 1)]
        outer = [(cx + r_out * math.cos(a), cy - r_out * math.sin(a)) for a in angles]
        inner = [(cx + r_in  * math.cos(a), cy - r_in  * math.sin(a)) for a in angles]
        pts   = [(int(x), int(y)) for x, y in outer + inner[::-1]]
        if len(pts) >= 3:
            pygame.draw.polygon(surface, color, pts)

    @staticmethod
    def _panel(surface, x, y, w, h, bg=(18, 14, 38), border=(65, 50, 110)):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((*bg, 195))
        pygame.draw.rect(s, (*border, 180), (0, 0, w, h), 1, border_radius=8)
        surface.blit(s, (x, y))

    def _draw_stats_overlay(self):   # noqa: C901
        cx = SCREEN_WIDTH // 2
        t  = pygame.time.get_ticks() / 1000.0
        mx_m, my_m = pygame.mouse.get_pos()

        # Full-screen dim with vignette
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 195))
        self.screen.blit(dim, (0, 0))

        # ── Panel 940×640 ─────────────────────────────────────────────
        pw, ph = 940, 640
        px = (SCREEN_WIDTH  - pw) // 2   # 10
        py = (SCREEN_HEIGHT - ph) // 2   # 40

        # ── Gradient panel background ──────────────────────────────────
        panel_s = pygame.Surface((pw, ph), pygame.SRCALPHA)
        for row in range(ph):
            frac = row / ph
            r2 = int(8  + 10 * (1 - frac))
            g2 = int(6  +  6 * (1 - frac))
            b2 = int(20 + 18 * (1 - frac))
            pygame.draw.rect(panel_s, (r2, g2, b2, 252), (0, row, pw, 1))
        # Header band — distinct dark-purple strip
        for row in range(64):
            frac = row / 64
            pygame.draw.rect(panel_s, (20, 14, 46, 252), (0, row, pw, 1))
        self.screen.blit(panel_s, (px, py))
        pygame.draw.rect(self.screen, (18, 12, 38), (px, py, pw, 64))

        # Animated glowing border
        glow_a = 0.75 + 0.25 * math.sin(t * 1.6)
        for gd in range(5, 0, -1):
            ga = int(70 * (1 - gd / 6) * glow_a)
            gc = (int(100 * glow_a), int(65 * glow_a), int(200 * glow_a))
            pygame.draw.rect(self.screen, (*gc, ga),
                             (px - gd, py - gd, pw + gd*2, ph + gd*2),
                             1, border_radius=16 + gd)
        pygame.draw.rect(self.screen, (100, 72, 185), (px, py, pw, ph), 2, border_radius=16)
        pygame.draw.rect(self.screen, (55, 42, 98, 140),
                         (px+4, py+4, pw-8, ph-8), 1, border_radius=13)

        # ── Data ──────────────────────────────────────────────────────
        # Use live stats while playing; use cached copy after session ends
        # (export_csv clears the log, so live read would return all zeros)
        stats = (self._get_session_stats()
                 if self.state == STATE_PLAYING
                 else (self._last_session_stats or self._get_session_stats()))
        hist       = self._get_hist_stats()
        play_sec   = stats["play_sec"]
        total_k    = stats["total_kills"]
        hp_data    = stats["hp_timeline"]
        pname      = getattr(self, "_last_summary", {}).get("player_name", self._player_name)
        summary    = getattr(self, "_last_summary", {})
        sid        = summary.get("session_id", "")
        p_rank, p_total, _, _ = self.leaderboard.get_player_context(sid)

        enemy_order = ["goblin","slime","skeleton","orc","wraith","armored_orc","werebear"]
        enemy_cols  = [(80,200,80),(100,220,140),(200,200,200),
                       (200,100,60),(160,80,220),(120,140,200),(200,140,60)]

        # ── Header band ───────────────────────────────────────────────
        # Diamond accent left
        pygame.draw.polygon(self.screen, (130, 95, 220),
                            [(px+14, py+32),(px+22, py+24),(px+30, py+32),(px+22, py+40)])
        pygame.draw.polygon(self.screen, (180, 145, 255),
                            [(px+14, py+32),(px+22, py+24),(px+30, py+32),(px+22, py+40)], 1)
        title_s = self.font_big.render("SESSION  STATISTICS", True, (200, 175, 255))
        self.screen.blit(title_s, (px + 36, py + 22))

        # Player name badge (center)
        badge_txt = f"  {pname[:14]}  "
        bs = self.font_med.render(badge_txt, True, (240, 220, 100))
        bw2 = bs.get_width() + 4
        badge_bg = pygame.Surface((bw2, 26), pygame.SRCALPHA)
        badge_bg.fill((60, 48, 12, 200))
        pygame.draw.rect(badge_bg, (200, 165, 40, 200), (0, 0, bw2, 26), 1, border_radius=13)
        self.screen.blit(badge_bg, (cx - bw2//2, py + 19))
        self.screen.blit(bs, (cx - bs.get_width()//2, py + 22))

        # Meta pills top-right
        pill_defs = [
            (f"{hist['total_sessions']} runs",  (48, 38, 82),  (155, 140, 200)),
            (f"Win {hist['win_rate']}%",
             (28, 72, 44) if hist["win_rate"] >= 20 else (72, 28, 38),
             (90, 220, 120) if hist["win_rate"] >= 20 else (220, 90, 90)),
            (f"Best Fl.{hist['best_floor']}",   (38, 55, 100), (100, 160, 255)),
        ]
        pill_x = px + pw - 52
        for ptxt, pcol, ptc in reversed(pill_defs):
            ps2  = self.font_sm.render(ptxt, True, ptc)
            pw3  = ps2.get_width() + 20
            pill_x -= pw3 + 6
            pb2 = pygame.Surface((pw3, 24), pygame.SRCALPHA)
            pb2.fill((*pcol, 220))
            pygame.draw.rect(pb2, (*ptc, 120), (0, 0, pw3, 24), 1, border_radius=12)
            self.screen.blit(pb2, (pill_x, py + 20))
            self.screen.blit(ps2, (pill_x + 10, py + 23))

        # Rank badge (if ranked)
        if p_rank > 0:
            rk_txt = f"#{p_rank}"
            rk_col = (255, 215, 0) if p_rank <= 3 else (180, 160, 220)
            rk_bg  = (70, 52, 12) if p_rank <= 3 else (38, 30, 65)
            rks    = self.font_med.render(rk_txt, True, rk_col)
            rkw    = rks.get_width() + 18
            rkb    = pygame.Surface((rkw, 26), pygame.SRCALPHA)
            rkb.fill((*rk_bg, 220))
            pygame.draw.rect(rkb, (*rk_col, 160), (0, 0, rkw, 26), 1, border_radius=13)
            self.screen.blit(rkb, (pill_x - rkw - 8, py + 19))
            self.screen.blit(rks, (pill_x - rkw - 8 + 9, py + 22))

        # Close button
        close_rect = pygame.Rect(px + pw - 42, py + 17, 30, 30)
        close_hov  = close_rect.collidepoint(mx_m, my_m)
        pygame.draw.rect(self.screen, (200, 48, 48) if close_hov else (100, 38, 78),
                         close_rect, border_radius=8)
        pygame.draw.rect(self.screen, (240, 140, 140) if close_hov else (155, 85, 120),
                         close_rect, 1, border_radius=8)
        xs = self.font_med.render("X", True, WHITE)
        self.screen.blit(xs, (close_rect.centerx - xs.get_width()//2,
                               close_rect.centery - xs.get_height()//2))

        # Header bottom separator with gradient
        for gi in range(4):
            ga2 = 180 - gi * 40
            pygame.draw.line(self.screen, (88, 62, 165, ga2),
                             (px + 10, py + 64 + gi), (px + pw - 10, py + 64 + gi), 1)

        # ── Stat cards (5) ────────────────────────────────────────────
        card_defs = [
            ("FLOOR",      str(stats["floor_reached"]), (65, 108, 205),  (40, 70, 160)),
            ("KILLS",      str(total_k),                (210,  62,  62),  (140, 30, 30)),
            ("TIME",       self._fmt_time(play_sec),    (45, 190, 120),   (20, 120, 70)),
            ("MAX COMBO",  f"x{stats['max_combo']}",   (210, 158,  28),  (140, 100, 10)),
            ("GOLD SPENT", f"{stats['gold_spent']}g",  (230, 192,   0),  (150, 118,  0)),
        ]
        nc     = len(card_defs)
        gap_c  = 8
        cw_c   = (pw - 28 - gap_c * (nc - 1)) // nc
        ch_c   = 76
        cy0    = py + 70

        for i, (lbl, val, bc, dark_bc) in enumerate(card_defs):
            bx = px + 14 + i * (cw_c + gap_c)
            hover_c = pygame.Rect(bx, cy0, cw_c, ch_c).collidepoint(mx_m, my_m)
            # Card surface
            cb = pygame.Surface((cw_c, ch_c), pygame.SRCALPHA)
            for row in range(ch_c):
                a_frac = row / ch_c
                br  = int(dark_bc[0] + (bc[0] - dark_bc[0]) * 0.1 * (1 - a_frac))
                bg3 = int(dark_bc[1] + (bc[1] - dark_bc[1]) * 0.1 * (1 - a_frac))
                bb3 = int(dark_bc[2] + (bc[2] - dark_bc[2]) * 0.1 * (1 - a_frac))
                pygame.draw.rect(cb, (br, bg3, bb3, 235), (0, row, cw_c, 1))
            # Top accent band
            for row in range(5):
                aa = 255 - row * 30
                pygame.draw.rect(cb, (*bc, aa), (0, row, cw_c, 1))
            # Border
            brd_a = 200 + int(40 * math.sin(t * 2 + i)) if hover_c else 140
            pygame.draw.rect(cb, (*bc, brd_a), (0, 0, cw_c, ch_c), 1, border_radius=10)
            # Left accent bar
            pygame.draw.rect(cb, (*bc, 255), (0, 0, 4, ch_c), border_radius=2)
            # Top shine
            shine = pygame.Surface((cw_c, 22), pygame.SRCALPHA)
            shine.fill((255, 255, 255, 18 if not hover_c else 28))
            cb.blit(shine, (0, 0))
            self.screen.blit(cb, (bx, cy0))
            # Label
            ls2 = self.font_sm.render(lbl, True, bc)
            self.screen.blit(ls2, (bx + cw_c//2 - ls2.get_width()//2, cy0 + 9))
            # Value — 32pt fits within 76px card, fall back for wide strings
            vs2 = self.font_card.render(val, True, WHITE)
            if vs2.get_width() > cw_c - 12:
                vs2 = self.font_big.render(val, True, WHITE)
            if vs2.get_width() > cw_c - 12:
                vs2 = self.font_med.render(val, True, WHITE)
            # Vertically center value in card below the label
            v_y = cy0 + 28 + (ch_c - 28 - vs2.get_height()) // 2
            self.screen.blit(vs2, (bx + cw_c//2 - vs2.get_width()//2, v_y))

        # Separator with glow dot
        sep_y = py + 152
        pygame.draw.line(self.screen, (55, 42, 92), (px + 10, sep_y), (px + pw - 10, sep_y), 1)
        pygame.draw.circle(self.screen, (110, 82, 188), (cx, sep_y), 4)
        pygame.draw.circle(self.screen, (160, 130, 235), (cx, sep_y), 2)

        # ── Tab bar ───────────────────────────────────────────────────
        tab_y   = py + 158
        tab_h   = 34
        tab_w   = (pw - 32) // 2   # 454
        tab_rects = [
            pygame.Rect(px + 14,              tab_y, tab_w, tab_h),
            pygame.Rect(px + 14 + tab_w + 4,  tab_y, tab_w, tab_h),
        ]
        tab_labels = ["SESSION STATS", "ALL SESSIONS"]
        for t_i, (t_rect, t_lbl) in enumerate(zip(tab_rects, tab_labels)):
            active   = (self._stats_tab == t_i)
            tab_hov  = t_rect.collidepoint(mx_m, my_m)
            tb_bg    = (50, 40, 90) if active else ((30, 24, 52) if tab_hov else (18, 14, 36))
            tb_brd   = (140, 108, 215) if active else (65, 52, 100)
            tb_tc    = (230, 215, 255) if active else (110, 95, 148)
            pygame.draw.rect(self.screen, tb_bg, t_rect, border_radius=7)
            pygame.draw.rect(self.screen, tb_brd, t_rect, 1, border_radius=7)
            if active:
                # Bright underline for active tab
                pygame.draw.rect(self.screen, (145, 108, 240),
                                 (t_rect.x + 4, t_rect.y + tab_h - 4,
                                  t_rect.w - 8, 4), border_radius=3)
                # Top shine
                sh2 = pygame.Surface((t_rect.w - 8, 12), pygame.SRCALPHA)
                sh2.fill((255, 255, 255, 22))
                self.screen.blit(sh2, (t_rect.x + 4, t_rect.y + 2))
            tls = self.font_med.render(t_lbl, True, tb_tc)
            self.screen.blit(tls, (t_rect.centerx - tls.get_width()//2,
                                   t_rect.centery - tls.get_height()//2 - 2))

        # ── Column geometry ───────────────────────────────────────────
        lx     = px + 14
        lw     = 548
        rx     = px + 572
        rw     = pw - 572 - 14   # 354
        cy_l   = py + 198
        cy_r   = py + 198
        lbl_w  = 88
        bar_bw = lw - lbl_w - 80   # leaves ~80px right margin for count + pct text

        # helper: draw an all-time records panel
        def _draw_records_panel(ry):
            rph2 = 28 + 5 * 18
            self._panel(self.screen, rx, ry, rw, rph2, border=(55, 82, 55))
            self.screen.blit(
                self.font_sm.render("ALL-TIME RECORDS", True, (118, 205, 128)),
                (rx + 10, ry + 7))
            pygame.draw.line(self.screen, (55, 82, 55),
                             (rx + 10, ry + 22), (rx + rw - 10, ry + 22), 1)
            best_t = (self._fmt_time(hist["best_time_sec"])
                      if hist["best_time_sec"] else "--")
            rows_r = [
                ("Sessions",    str(hist["total_sessions"]),   (148, 130, 205)),
                ("Win Rate",    f"{hist['win_rate']}%",
                 (68, 215, 100) if hist["win_rate"] >= 20 else (215, 68, 68)),
                ("Best Floor",  str(hist["best_floor"]),       (65, 108, 205)),
                ("Best Kills",  str(hist["best_kills"]),       (198, 58, 58)),
                ("Fastest Win", best_t,                        (52, 178, 108)),
            ]
            rr_y = ry + 26
            for rname, rval, rcol in rows_r:
                self.screen.blit(
                    self.font_sm.render(rname, True, (130, 118, 172)),
                    (rx + 14, rr_y + 2))
                rv2 = self.font_sm.render(rval, True, rcol)
                self.screen.blit(rv2, (rx + rw - 14 - rv2.get_width(), rr_y + 2))
                pygame.draw.line(self.screen, (32, 26, 56),
                                 (rx + 10, rr_y + 16), (rx + rw - 10, rr_y + 16), 1)
                rr_y += 18
            return ry + rph2 + 8

        # helper: draw floor distribution bar chart
        def _draw_floor_dist(ry, height):
            if height < 50:
                return
            self._panel(self.screen, rx, ry, rw, height, border=(68, 56, 95))
            self.screen.blit(
                self.font_sm.render("FLOOR DISTRIBUTION", True, (148, 130, 205)),
                (rx + 10, ry + 7))
            pygame.draw.line(self.screen, (68, 56, 95),
                             (rx + 10, ry + 22), (rx + rw - 10, ry + 22), 1)
            fc_x = rx + 10
            fc_y = ry + 26
            fc_w = rw - 20
            fc_h = height - 36
            max_fd = max(hist["floor_dist"].values(), default=1) or 1
            step_w = fc_w / 20.0
            pygame.draw.rect(self.screen, (14, 10, 30),
                             (fc_x, fc_y, fc_w, fc_h), border_radius=4)
            for fl in range(1, 21):
                cnt2 = hist["floor_dist"].get(fl, 0)
                bx_f = fc_x + int((fl - 1) * step_w) + 1
                bw_f = max(2, int(step_w) - 1)
                bh_f = int(cnt2 / max_fd * (fc_h - 2))
                if fl == 20:
                    fc2 = GOLD_COLOR
                elif fl == 10:
                    fc2 = (220, 72, 72)
                elif fl % 5 == 0:
                    fc2 = (130, 72, 225)
                else:
                    frac_c = fl / 20
                    fc2 = (int(55 + 30 * frac_c), int(95 + 60 * frac_c),
                           int(195 - 40 * frac_c))
                if bh_f > 0:
                    pygame.draw.rect(self.screen, fc2,
                                     (bx_f, fc_y + fc_h - bh_f, bw_f, bh_f))
                    pygame.draw.rect(
                        self.screen,
                        (min(255, fc2[0]+50), min(255, fc2[1]+50), min(255, fc2[2]+50)),
                        (bx_f, fc_y + fc_h - bh_f, bw_f, 2))
                if fl % 5 == 0:
                    lbl_f = self.font_sm.render(str(fl), True, (90, 80, 115))
                    self.screen.blit(lbl_f,
                                     (bx_f + bw_f // 2 - lbl_f.get_width() // 2,
                                      fc_y + fc_h + 2))

        # ══════════════════════════════════════════════════════════════
        if self._stats_tab == 0:
            # ── TAB 0: SESSION ────────────────────────────────────────

            # LEFT A: Kills by enemy bar chart (Graph 1)
            kph = 28 + 7 * 20
            self._panel(self.screen, lx, cy_l, lw, kph, border=(68, 52, 112))
            self.screen.blit(
                self.font_sm.render("KILLS BY ENEMY TYPE", True, (158, 130, 218)),
                (lx + 10, cy_l + 7))
            pygame.draw.line(self.screen, (68, 52, 112),
                             (lx + 10, cy_l + 22), (lx + lw - 10, cy_l + 22), 1)
            max_k = max(stats["kills_by_type"].values(), default=1) or 1
            ky = cy_l + 26
            for etype, ecol in zip(enemy_order, enemy_cols):
                cnt   = stats["kills_by_type"].get(etype, 0)
                fw    = int(bar_bw * cnt / max_k)
                self.screen.blit(
                    self.font_sm.render(etype[:9], True, (155, 140, 192)),
                    (lx + 10, ky + 2))
                bx2 = lx + 10 + lbl_w
                pygame.draw.rect(self.screen, (22, 18, 42),
                                 (bx2, ky, bar_bw, 14), border_radius=3)
                if fw > 2:
                    pygame.draw.rect(self.screen, ecol, (bx2, ky, fw, 14), border_radius=3)
                    tip = pygame.Surface((min(12, fw), 14), pygame.SRCALPHA)
                    tip.fill((255, 255, 255, 30))
                    self.screen.blit(tip, (bx2 + fw - min(12, fw), ky))
                    sh = pygame.Surface((fw, 5), pygame.SRCALPHA)
                    sh.fill((255, 255, 255, 20))
                    self.screen.blit(sh, (bx2, ky))
                pct = int(cnt / total_k * 100) if total_k > 0 else 0
                cnt_col = (195, 185, 228) if cnt > 0 else (50, 46, 72)
                vs_cnt = self.font_sm.render(f"{cnt}", True, cnt_col)
                self.screen.blit(vs_cnt, (bx2 + bar_bw + 4, ky + 1))
                if cnt > 0 and total_k > 0:
                    vs_pct = self.font_sm.render(f"{pct}%", True, ecol[:3])
                    self.screen.blit(vs_pct,
                                     (bx2 + bar_bw + vs_cnt.get_width() + 7, ky + 1))
                ky += 20
            cy_l += kph + 8

            # LEFT B: Session vs Historical comparison
            cmp_rows = [
                ("Kills",  stats["total_kills"], hist["avg_kills"],    hist["best_kills"],
                 (198, 58, 58), True),
                ("Floor",  stats["floor_reached"], hist["avg_floor"],  hist["best_floor"],
                 (65, 108, 205), True),
                ("Combo",  stats["max_combo"], hist["best_combo"] * 0.7, hist["best_combo"],
                 (198, 150, 26), True),
                ("Time",   play_sec, hist["avg_time_sec"], None,
                 (52, 178, 108), False),
            ]
            cph = 28 + len(cmp_rows) * 20
            self._panel(self.screen, lx, cy_l, lw, cph, border=(75, 55, 100))
            self.screen.blit(
                self.font_sm.render("SESSION VS HISTORICAL AVERAGE",
                                    True, (168, 142, 225)),
                (lx + 10, cy_l + 7))
            pygame.draw.line(self.screen, (75, 55, 100),
                             (lx + 10, cy_l + 22), (lx + lw - 10, cy_l + 22), 1)
            cmp_bar_w = bar_bw - 110
            cy2 = cy_l + 26
            for cname, cur_v, avg_v, best_v, ccol, higher_better in cmp_rows:
                denom   = best_v if (best_v and best_v > 0) else max(avg_v * 1.5, cur_v, 1)
                fill_w2 = int(cmp_bar_w * min(cur_v, denom) / denom)
                avg_x   = int(cmp_bar_w * min(avg_v, denom) / denom)
                self.screen.blit(
                    self.font_sm.render(f"{cname:<7}", True, (148, 132, 185)),
                    (lx + 10, cy2 + 2))
                bx3 = lx + 10 + lbl_w
                pygame.draw.rect(self.screen, (22, 18, 42),
                                 (bx3, cy2, cmp_bar_w, 14), border_radius=3)
                if fill_w2 > 2:
                    pygame.draw.rect(self.screen, ccol,
                                     (bx3, cy2, fill_w2, 14), border_radius=3)
                    sh = pygame.Surface((fill_w2, 5), pygame.SRCALPHA)
                    sh.fill((255, 255, 255, 18))
                    self.screen.blit(sh, (bx3, cy2))
                if avg_x > 0:
                    pygame.draw.line(self.screen, (255, 255, 100),
                                     (bx3 + avg_x, cy2 - 1), (bx3 + avg_x, cy2 + 15), 2)
                above = (cur_v > avg_v) if higher_better else (cur_v < avg_v)
                arr  = "+" if above else "-"
                acol = (68, 215, 100) if above else (215, 68, 68)
                if cname == "Time":
                    txt = f"{self._fmt_time(cur_v)} ({arr}) {self._fmt_time(avg_v)}"
                else:
                    av  = round(avg_v) if avg_v >= 10 else round(avg_v, 1)
                    txt = f"{int(cur_v)} ({arr}) {av}"
                self.screen.blit(
                    self.font_sm.render(txt, True, acol),
                    (bx3 + cmp_bar_w + 6, cy2 + 1))
                cy2 += 20
            cy_l += cph + 8

            # LEFT C: Items collected bar chart
            item_order = ["potion", "weapon", "armor", "buff", "gold"]
            item_cols  = [
                (72, 188, 108), (108, 148, 228), (228, 172, 72),
                (188, 88, 208), (228, 192, 48),
            ]
            iph = 28 + len(item_order) * 20
            avail_l = (py + ph - 18) - cy_l
            if avail_l >= iph:
                self._panel(self.screen, lx, cy_l, lw, iph, border=(55, 80, 68))
                self.screen.blit(
                    self.font_sm.render("ITEMS COLLECTED", True, (118, 205, 148)),
                    (lx + 10, cy_l + 7))
                pygame.draw.line(self.screen, (55, 80, 68),
                                 (lx + 10, cy_l + 22), (lx + lw - 10, cy_l + 22), 1)
                max_i = max(
                    (stats["items_by_type"].get(it, 0) for it in item_order), default=1
                ) or 1
                iy = cy_l + 26
                for iname, icol in zip(item_order, item_cols):
                    cnt_i  = stats["items_by_type"].get(iname, 0)
                    fw_i   = int(bar_bw * cnt_i / max_i)
                    self.screen.blit(
                        self.font_sm.render(iname[:9].capitalize(), True, (138, 175, 155)),
                        (lx + 10, iy + 2))
                    bxi = lx + 10 + lbl_w
                    pygame.draw.rect(self.screen, (22, 18, 42),
                                     (bxi, iy, bar_bw, 14), border_radius=3)
                    if fw_i > 2:
                        pygame.draw.rect(self.screen, icol,
                                         (bxi, iy, fw_i, 14), border_radius=3)
                        shi = pygame.Surface((fw_i, 5), pygame.SRCALPHA)
                        shi.fill((255, 255, 255, 20))
                        self.screen.blit(shi, (bxi, iy))
                    self.screen.blit(
                        self.font_sm.render(str(cnt_i), True,
                                            (185, 215, 195) if cnt_i > 0 else (48, 44, 65)),
                        (bxi + bar_bw + 4, iy + 1))
                    iy += 20
                cy_l += iph + 8

            # RIGHT A: HP over time line chart (Graph 2)
            hph = 156
            self._panel(self.screen, rx, cy_r, rw, hph, border=(80, 40, 60))
            self.screen.blit(
                self.font_sm.render("HP OVER TIME", True, (215, 115, 125)),
                (rx + 10, cy_r + 7))
            pygame.draw.line(self.screen, (80, 40, 60),
                             (rx + 10, cy_r + 22), (rx + rw - 10, cy_r + 22), 1)
            chart_x = rx + 10
            chart_y = cy_r + 26
            chart_w = rw - 20
            chart_h = hph - 36
            pygame.draw.rect(self.screen, (14, 10, 30),
                             (chart_x, chart_y, chart_w, chart_h), border_radius=4)
            pygame.draw.rect(self.screen, (44, 32, 70),
                             (chart_x, chart_y, chart_w, chart_h), 1, border_radius=4)
            for frac_g in (0.25, 0.5, 0.75, 1.0):
                gy = chart_y + chart_h - 2 - int(frac_g * (chart_h - 4))
                pygame.draw.line(self.screen, (35, 28, 58),
                                 (chart_x + 1, gy), (chart_x + chart_w - 1, gy), 1)
            if len(hp_data) >= 2:
                t0v     = hp_data[0][0]
                trange  = max(hp_data[-1][0] - t0v, 1)
                max_hpv = max(h[2] for h in hp_data) or 1
                pts = [
                    (chart_x + 2 + int((ts3 - t0v) / trange * (chart_w - 4)),
                     chart_y + chart_h - 2 - int(hp3 / max_hpv * (chart_h - 4)))
                    for ts3, hp3, _ in hp_data
                ]
                for pass_a in (35, 22, 12):
                    fs = pygame.Surface((chart_w, chart_h), pygame.SRCALPHA)
                    local = [(p[0]-chart_x, p[1]-chart_y + pass_a//10) for p in pts]
                    poly  = [(local[0][0], chart_h-1)] + local + [(local[-1][0], chart_h-1)]
                    if len(poly) >= 3:
                        pygame.draw.polygon(fs, (220, 52, 52, pass_a), poly)
                    self.screen.blit(fs, (chart_x, chart_y))
                pygame.draw.lines(self.screen, (180, 45, 45), False, pts, 3)
                pygame.draw.lines(self.screen, (245, 82, 82), False, pts, 1)
                for pt in pts[::max(1, len(pts) // 10)]:
                    pygame.draw.circle(self.screen, (255, 110, 110), pt, 3)
                    pygame.draw.circle(self.screen, WHITE, pt, 1)
                pygame.draw.line(self.screen, (48, 188, 68),
                                 (chart_x+2, chart_y+2), (chart_x+chart_w-2, chart_y+2), 1)
                ts_lbl = self.font_sm.render("0:00", True, (65, 55, 82))
                te_lbl = self.font_sm.render(self._fmt_time(play_sec), True, (65, 55, 82))
                self.screen.blit(ts_lbl, (chart_x+2, chart_y+chart_h+2))
                self.screen.blit(te_lbl, (chart_x+chart_w-te_lbl.get_width()-2,
                                          chart_y+chart_h+2))
            elif len(hp_data) == 1:
                ts3, hp3, mhp3 = hp_data[0]
                fy = chart_y + chart_h - 2 - int(hp3 / max(mhp3, 1) * (chart_h - 4))
                pygame.draw.circle(self.screen, (245, 82, 82),
                                   (chart_x + chart_w // 2, fy), 5)
            else:
                nd = self.font_sm.render("No HP data yet", True, (65, 55, 82))
                self.screen.blit(nd, (chart_x + chart_w//2 - nd.get_width()//2,
                                      chart_y + chart_h//2 - nd.get_height()//2))
            cy_r += hph + 8

            # RIGHT B: All-time records
            cy_r = _draw_records_panel(cy_r)

            # RIGHT C: Floor distribution (fills remaining right space)
            avail_r = (py + ph - 18) - cy_r
            if avail_r >= 50:
                _draw_floor_dist(cy_r, avail_r)

        else:
            # ── TAB 1: ALL SESSIONS ───────────────────────────────────

            # LEFT: Past sessions table
            all_sess = self.leaderboard.entries
            row_h    = 18
            tph      = py + ph - 18 - cy_l
            max_rows = max(0, (tph - 40) // row_h)
            self._panel(self.screen, lx, cy_l, lw, tph, border=(58, 52, 100))
            self.screen.blit(
                self.font_sm.render("PAST SESSIONS", True, (168, 148, 228)),
                (lx + 10, cy_l + 7))
            tavg = self.font_sm.render(
                f"avg: Floor {hist['avg_floor']}  "
                f"{hist['avg_kills']}K  {self._fmt_time(hist['avg_time_sec'])}",
                True, (100, 115, 160))
            self.screen.blit(tavg, (lx + lw - tavg.get_width() - 10, cy_l + 7))
            pygame.draw.line(self.screen, (58, 52, 100),
                             (lx + 10, cy_l + 22), (lx + lw - 10, cy_l + 22), 1)

            tcols = [
                ("#",      52), ("NAME", 140), ("FLOOR", 52),
                ("KILLS",  50), ("COMBO", 52), ("TIME",  0),
            ]
            col_xs: list[int] = []
            cx_acc = lx + 10
            for _cn, _cw in tcols:
                col_xs.append(cx_acc)
                cx_acc += _cw if _cw else (lw - (cx_acc - lx) - 10)

            ch_y = cy_l + 26
            for i_c, (_cn, _) in enumerate(tcols):
                hs = self.font_sm.render(_cn, True, (108, 95, 148))
                self.screen.blit(hs, (col_xs[i_c], ch_y))
            pygame.draw.line(self.screen, (48, 42, 82),
                             (lx + 10, ch_y + 14), (lx + lw - 10, ch_y + 14), 1)

            scroll_off = max(0, min(self._table_scroll,
                                     max(0, len(all_sess) - max_rows)))
            tr_y  = ch_y + 16
            shown = 0
            for e in all_sess[scroll_off:]:
                if shown >= max_rows:
                    break
                abs_idx = shown + scroll_off
                is_cur  = (e.get("session_id", "") == sid)
                is_sel  = (abs_idx == self._selected_hist_idx)
                if is_sel:
                    hl = pygame.Surface((lw - 22, row_h - 1), pygame.SRCALPHA)
                    hl.fill((145, 108, 240, 55))
                    self.screen.blit(hl, (lx + 10, tr_y))
                elif is_cur:
                    hl = pygame.Surface((lw - 22, row_h - 1), pygame.SRCALPHA)
                    hl.fill((255, 220, 80, 30))
                    self.screen.blit(hl, (lx + 10, tr_y))
                elif shown % 2 == 0:
                    st = pygame.Surface((lw - 22, row_h - 1), pygame.SRCALPHA)
                    st.fill((255, 255, 255, 5))
                    self.screen.blit(st, (lx + 10, tr_y))
                bc  = (255, 220, 80) if is_cur else (165, 152, 200)
                d   = float(e.get("duration_sec", 0))
                row_vals = [
                    (f"#{e.get('rank','?')}", bc),
                    (str(e.get("player_name", "?"))[:13], bc),
                    (str(e.get("floor_reached","?")),
                     (140, 200, 255) if is_cur else (100, 160, 255)),
                    (str(e.get("kills","?")),
                     (255, 140, 140) if is_cur else (220, 100, 100)),
                    (f"x{e.get('max_combo','?')}",
                     (255, 220, 80) if is_cur else (220, 185, 60)),
                    (self._fmt_time(d),
                     (120, 240, 160) if is_cur else (90, 200, 140)),
                ]
                for i_c, (val_str, vcol) in enumerate(row_vals):
                    vs = self.font_sm.render(val_str, True, vcol)
                    self.screen.blit(vs, (col_xs[i_c], tr_y + 2))
                pygame.draw.line(self.screen, (32, 28, 58),
                                 (lx + 10, tr_y + row_h - 1),
                                 (lx + lw - 10, tr_y + row_h - 1), 1)
                tr_y  += row_h
                shown += 1
            if not all_sess:
                nd = self.font_sm.render("No sessions yet — play to populate.",
                                         True, (65, 58, 92))
                self.screen.blit(nd, (lx + lw//2 - nd.get_width()//2,
                                      cy_l + tph // 2))
            # Scrollbar
            if len(all_sess) > max_rows:
                sb_x    = lx + lw - 8
                sb_area = tph - 42
                sb_y0   = cy_l + 40
                thumb_h = max(16, sb_area * max_rows // len(all_sess))
                thumb_y = (sb_y0 + int((sb_area - thumb_h) * scroll_off
                            / max(1, len(all_sess) - max_rows)))
                pygame.draw.rect(self.screen, (30, 24, 55),
                                 (sb_x, sb_y0, 5, sb_area), border_radius=3)
                pygame.draw.rect(self.screen, (110, 90, 175),
                                 (sb_x, thumb_y, 5, thumb_h), border_radius=3)

            # RIGHT: All-time records + comparison (if row selected) or floor dist
            cy_r = _draw_records_panel(cy_r)
            sel_idx = self._selected_hist_idx
            all_e   = self.leaderboard.entries
            if sel_idx is not None and 0 <= sel_idx < len(all_e):
                e_sel     = all_e[sel_idx]
                sel_floor = int(e_sel.get("floor_reached", 0))
                sel_kills = int(e_sel.get("kills", 0))
                sel_combo = int(e_sel.get("max_combo", 0))
                sel_time  = float(e_sel.get("duration_sec", 0))
                sel_name  = str(e_sel.get("player_name", "?"))[:11]
                sel_rank  = e_sel.get("rank", "?")
                cmp_lbl_w = 52
                cmp_bar_w_s = rw - cmp_lbl_w - 24 - 96   # ~182px bar, ~96px text
                cph_s = 28 + 4 * 20   # 108
                avail_s = py + ph - 18 - cy_r
                cph_s = min(cph_s, avail_s)
                self._panel(self.screen, rx, cy_r, rw, cph_s, border=(75, 55, 110))
                hdr = self.font_sm.render(f"#{sel_rank} {sel_name} VS AVG",
                                          True, (175, 148, 235))
                self.screen.blit(hdr, (rx + 10, cy_r + 7))
                pygame.draw.line(self.screen, (75, 55, 110),
                                 (rx + 10, cy_r + 22), (rx + rw - 10, cy_r + 22), 1)
                cmp_rows_s = [
                    ("Floor", sel_floor, hist["avg_floor"],
                     hist["best_floor"], (65, 108, 205), True),
                    ("Kills", sel_kills, hist["avg_kills"],
                     hist["best_kills"], (198, 58, 58), True),
                    ("Combo", sel_combo, hist["best_combo"] * 0.7,
                     hist["best_combo"], (198, 150, 26), True),
                    ("Time",  sel_time,  hist["avg_time_sec"],
                     None, (52, 178, 108), False),
                ]
                cy_s = cy_r + 26
                for cname_s, cur_vs, avg_vs, best_vs, ccol_s, hb_s in cmp_rows_s:
                    denom_s = (best_vs if (best_vs and best_vs > 0)
                               else max(avg_vs * 1.5, cur_vs, 1))
                    fill_ws = int(cmp_bar_w_s * min(cur_vs, denom_s) / denom_s)
                    avg_xs  = int(cmp_bar_w_s * min(avg_vs, denom_s) / denom_s)
                    self.screen.blit(
                        self.font_sm.render(cname_s, True, (148, 132, 185)),
                        (rx + 10, cy_s + 2))
                    bxs = rx + 10 + cmp_lbl_w
                    pygame.draw.rect(self.screen, (22, 18, 42),
                                     (bxs, cy_s, cmp_bar_w_s, 14), border_radius=3)
                    if fill_ws > 2:
                        pygame.draw.rect(self.screen, ccol_s,
                                         (bxs, cy_s, fill_ws, 14), border_radius=3)
                        sh_s = pygame.Surface((fill_ws, 5), pygame.SRCALPHA)
                        sh_s.fill((255, 255, 255, 18))
                        self.screen.blit(sh_s, (bxs, cy_s))
                    if avg_xs > 0:
                        pygame.draw.line(self.screen, (255, 255, 100),
                                         (bxs + avg_xs, cy_s - 1),
                                         (bxs + avg_xs, cy_s + 15), 2)
                    above_s = (cur_vs > avg_vs) if hb_s else (cur_vs < avg_vs)
                    arr_s   = "+" if above_s else "-"
                    acol_s  = (68, 215, 100) if above_s else (215, 68, 68)
                    if cname_s == "Time":
                        txt_s = (f"{self._fmt_time(cur_vs)} ({arr_s}) "
                                 f"{self._fmt_time(avg_vs)}")
                    else:
                        av_s  = round(avg_vs) if avg_vs >= 10 else round(avg_vs, 1)
                        txt_s = f"{int(cur_vs)} ({arr_s}) {av_s}"
                    self.screen.blit(
                        self.font_sm.render(txt_s, True, acol_s),
                        (bxs + cmp_bar_w_s + 6, cy_s + 1))
                    cy_s += 20
                cy_r += cph_s + 8
                avail_fd2 = py + ph - 18 - cy_r
                if avail_fd2 >= 50:
                    _draw_floor_dist(cy_r, avail_fd2)
            else:
                _draw_floor_dist(cy_r, py + ph - 18 - cy_r)

        # ══ BOTTOM RANK STRIP (both tabs) ════════════════════════════
        strip_y = py + ph - 18
        strip_bg = pygame.Surface((pw - 8, 16), pygame.SRCALPHA)
        strip_bg.fill((14, 10, 34, 220))
        self.screen.blit(strip_bg, (px + 4, strip_y))
        pygame.draw.line(self.screen, (65, 50, 110),
                         (px + 10, strip_y), (px + pw - 10, strip_y), 1)
        if self._stats_tab == 1:
            cmp_hint = ("click row to compare" if self._selected_hist_idx is None
                        else f"comparing #{self._selected_hist_idx + 1} — click again to clear")
            rank_txt = (f"RANK #{p_rank} / {p_total}   |   "
                        f"{hist['total_sessions']} total runs   |   "
                        f"{cmp_hint}   |   [TAB] switch   [ESC] close")
        elif p_rank > 0:
            rank_txt = (f"RANK #{p_rank} / {p_total}   |   "
                        f"Best combo x{hist['best_combo']}   |   "
                        f"{sum(hist['floor_dist'].values())} total runs   |   "
                        f"[TAB] switch   [ESC] close")
        else:
            rank_txt = (f"Sessions: {hist['total_sessions']}   |   "
                        f"Win rate: {hist['win_rate']}%   |   "
                        f"[TAB] switch tab   [ESC] close")
        rs = self.font_sm.render(rank_txt, True, (115, 100, 162))
        self.screen.blit(rs, (cx - rs.get_width()//2, strip_y + 2))

    # ------------------------------------------------------------------
    # ICON / ANIMATION HELPERS
    # ------------------------------------------------------------------
    @staticmethod
    def _make_game_icon() -> pygame.Surface:
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        # Purple circle background
        pygame.draw.circle(surf, (80, 40, 160), (32, 32), 30)
        pygame.draw.circle(surf, (140, 100, 255), (32, 32), 30, 3)
        # Sword blade (diagonal, top-right to bottom-left)
        pygame.draw.line(surf, (220, 220, 255), (46, 10), (14, 50), 5)
        pygame.draw.line(surf, (255, 255, 255), (46, 10), (44, 14), 3)
        # Guard (crossguard)
        pygame.draw.line(surf, (200, 170, 60), (28, 28), (40, 20), 4)
        pygame.draw.line(surf, (200, 170, 60), (22, 34), (30, 26), 4)
        # Handle
        pygame.draw.line(surf, (140, 90, 40), (14, 50), (10, 56), 4)
        # Star accent
        pygame.draw.circle(surf, (255, 230, 80), (50, 14), 4)
        return surf

    @staticmethod
    def _make_icon_sword(size: int = 22) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        # Blade diagonal
        pygame.draw.line(surf, (200, 210, 255), (size - 4, 4), (5, size - 5), 3)
        # Guard
        mid = size // 2
        pygame.draw.line(surf, (200, 170, 60),
                         (mid - 5, mid + 4), (mid + 5, mid - 4), 3)
        # Handle
        pygame.draw.line(surf, (140, 90, 40), (4, size - 4), (6, size - 7), 3)
        return surf

    @staticmethod
    def _make_icon_trophy(size: int = 22) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        gold = (255, 215, 0)
        # Cup sides
        pygame.draw.line(surf, gold, (4, 4), (4, size // 2), 3)
        pygame.draw.line(surf, gold, (size - 4, 4), (size - 4, size // 2), 3)
        # Cup bottom arc (approximate with rect + circle)
        pygame.draw.rect(surf, gold, (4, 4, size - 8, 3))
        pygame.draw.ellipse(surf, gold,
                            (4, size // 2 - 4, size - 8, 8), 3)
        # Stem
        pygame.draw.line(surf, gold, (size // 2, size // 2 + 2),
                         (size // 2, size - 6), 2)
        # Base
        pygame.draw.rect(surf, gold, (4, size - 6, size - 8, 3),
                         border_radius=1)
        # Handles
        pygame.draw.arc(surf, gold,
                        pygame.Rect(0, 5, 7, 7), -math.pi / 3, math.pi / 3, 2)
        pygame.draw.arc(surf, gold,
                        pygame.Rect(size - 7, 5, 7, 7),
                        math.pi - math.pi / 3, math.pi + math.pi / 3, 2)
        return surf

    @staticmethod
    def _make_icon_back(size: int = 22) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        m = size // 2
        # Left-pointing arrow
        pygame.draw.polygon(surf, (180, 200, 255),
                            [(m - 4, m - 5), (m - 4, m + 5), (4, m)])
        pygame.draw.line(surf, (180, 200, 255), (m - 4, m), (size - 4, m), 3)
        return surf

    @staticmethod
    def _make_icon_door(size: int = 22) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        m = size // 2
        p = 4  # padding from edge
        # Bold X with rounded ends
        pygame.draw.line(surf, (255, 70, 70), (p, p), (size - p, size - p), 4)
        pygame.draw.line(surf, (255, 70, 70), (size - p, p), (p, size - p), 4)
        # Bright center dot
        pygame.draw.circle(surf, (255, 130, 130), (m, m), 3)
        return surf
