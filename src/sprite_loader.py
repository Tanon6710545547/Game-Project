"""
sprite_loader.py - Animated sprite system for RPG character sheets (100×100 frames).
All sheets are horizontal strips; each frame is FRAME_W × FRAME_H pixels.
"""
from __future__ import annotations
import os
import pygame
from src.constants import ASSETS_DIR

ANIM_DIR   = os.path.join(ASSETS_DIR, "Animetion")
FRAME_W    = 100
FRAME_H    = 100

# ── Frame cache: (path, scale) → list[Surface] ────────────────────────────
_CACHE: dict[tuple, list[pygame.Surface]] = {}


def load_frames(path: str, scale: int = 48) -> list[pygame.Surface]:
    key = (path, scale)
    if key in _CACHE:
        return _CACHE[key]
    try:
        sheet  = pygame.image.load(path).convert_alpha()
        n      = sheet.get_width() // FRAME_W
        frames = []
        for i in range(n):
            sub = sheet.subsurface((i * FRAME_W, 0, FRAME_W, FRAME_H))
            frames.append(pygame.transform.smoothscale(sub, (scale, scale)))
        _CACHE[key] = frames
        return frames
    except Exception:
        _CACHE[key] = []
        return []


def _sheet(char: str, fname: str) -> str:
    return os.path.join(ANIM_DIR, char, f"{char} with shadows", f"{char}-{fname}.png")


# ── Character animation config: state → (sheet_name, fps, loop) ────────────
_CFG: dict[str, dict[str, tuple]] = {
    "Knight Templar": {
        "idle":   ("Idle",     6.0, True),
        "walk":   ("Walk01",  10.0, True),
        "attack": ("Attack01",14.0, False),
        "hurt":   ("Hurt",    12.0, False),
    },
    "Armored Orc": {
        "idle":   ("Idle",    6.0, True),
        "walk":   ("Walk",   10.0, True),
        "attack": ("Attack01",14.0, False),
        "hurt":   ("Hurt",   12.0, False),
    },
    "Armored Skeleton": {
        "idle":   ("Idle",    6.0, True),
        "walk":   ("Walk",   10.0, True),
        "attack": ("Attack01",14.0, False),
        "hurt":   ("Hurt",   12.0, False),
    },
    "Werebear": {
        "idle":   ("Idle",    6.0, True),
        "walk":   ("Walk",   10.0, True),
        "attack": ("Attack01",14.0, False),
        "hurt":   ("Hurt",   12.0, False),
    },
    "Orc rider": {
        "idle":   ("Idle",    6.0, True),
        "walk":   ("Walk",   10.0, True),
        "attack": ("Attack01",14.0, False),
        "hurt":   ("Hurt",   12.0, False),
    },
}


class SpriteAnim:
    """Cycles through pre-loaded frames at a given FPS."""

    def __init__(self, frames: list[pygame.Surface], fps: float = 8.0,
                 loop: bool = True):
        self.frames  = frames
        self.fps     = fps
        self.loop    = loop
        self._idx    = 0
        self._t      = 0.0
        self.done    = False

    # ------------------------------------------------------------------
    def reset(self):
        self._idx  = 0
        self._t    = 0.0
        self.done  = False

    def update(self, dt_ms: float):
        if self.done or not self.frames:
            return
        self._t += dt_ms
        step = 1000.0 / max(1.0, self.fps)
        while self._t >= step:
            self._t -= step
            self._idx += 1
            if self._idx >= len(self.frames):
                if self.loop:
                    self._idx = 0
                else:
                    self._idx = len(self.frames) - 1
                    self.done = True
                    return

    def current(self, flip: bool = False) -> pygame.Surface | None:
        if not self.frames:
            return None
        f = self.frames[self._idx]
        return pygame.transform.flip(f, True, False) if flip else f

    @property
    def empty(self) -> bool:
        return not self.frames


# ── Factory ────────────────────────────────────────────────────────────────
def make_anim(char: str, state: str, scale: int = 48) -> SpriteAnim:
    cfg = _CFG.get(char, {}).get(state)
    if not cfg:
        return SpriteAnim([])
    fname, fps, loop = cfg
    frames = load_frames(_sheet(char, fname), scale)
    return SpriteAnim(frames, fps=fps, loop=loop)


def make_all_anims(char: str, scale: int = 48) -> dict[str, SpriteAnim]:
    return {state: make_anim(char, state, scale)
            for state in ("idle", "walk", "attack", "hurt")}


# ── Priest heal effect ─────────────────────────────────────────────────────
_HEAL_FRAMES: list[pygame.Surface] = []


def get_heal_frames(scale: int = 72) -> list[pygame.Surface]:
    global _HEAL_FRAMES
    if not _HEAL_FRAMES:
        path = os.path.join(ANIM_DIR, "Priest-Heal_Effect.png")
        _HEAL_FRAMES = load_frames(path, scale)
    return _HEAL_FRAMES


def make_heal_anim(scale: int = 72) -> SpriteAnim:
    return SpriteAnim(get_heal_frames(scale), fps=10.0, loop=False)
