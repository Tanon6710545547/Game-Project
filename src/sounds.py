"""
sounds.py - Procedurally synthesized sound effects using numpy + pygame.sndarray.
No external audio files required. All sounds generated at runtime.
"""
from __future__ import annotations
import math
import pygame
import numpy as np

_SAMPLE_RATE  = 44100
_CHANNELS     = 2          # stereo
_SOUNDS: dict = {}         # cache

def _make_stereo(mono: np.ndarray) -> np.ndarray:
    stereo = np.stack([mono, mono], axis=1)
    return np.ascontiguousarray(stereo)

def _norm(arr: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(arr))
    if peak > 0:
        arr = arr / peak
    return arr

# ── Waveform building blocks ───────────────────────────────────────────────────

def _sine(freq: float, duration: float, amp: float = 1.0) -> np.ndarray:
    n = int(_SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    return (amp * np.sin(2 * math.pi * freq * t)).astype(np.float32)

def _noise(duration: float, amp: float = 1.0) -> np.ndarray:
    n = int(_SAMPLE_RATE * duration)
    return (amp * (np.random.random(n).astype(np.float32) * 2 - 1))

def _envelope(arr: np.ndarray, attack: float = 0.01, decay: float = 0.1,
              sustain: float = 0.7, release: float = 0.2) -> np.ndarray:
    n   = len(arr)
    env = np.ones(n, dtype=np.float32)
    a   = max(1, int(n * attack))
    d   = max(1, int(n * decay))
    r   = max(1, int(n * release))
    s   = max(0, n - a - d - r)
    env[:a]      = np.linspace(0, 1, a)
    env[a:a+d]   = np.linspace(1, sustain, d)
    env[a+d:a+d+s] = sustain
    env[a+d+s:]  = np.linspace(sustain, 0, r)
    return arr * env

def _exp_decay(arr: np.ndarray, tau: float = 0.3) -> np.ndarray:
    n   = len(arr)
    t   = np.linspace(0, len(arr) / _SAMPLE_RATE, n)
    return arr * np.exp(-t / tau).astype(np.float32)

# ── Boss death sound (dramatic climax) ────────────────────────────────────────

def _build_boss_death() -> pygame.Sound:
    dur = 3.0
    n   = int(_SAMPLE_RATE * dur)

    # Layer 1: deep sub-bass thud (80 Hz sine, exponential decay)
    bass = _sine(80,  dur, 1.0)
    bass = _exp_decay(bass, 0.25)

    # Layer 2: mid-range impact roar (160 Hz with slight freq drop)
    t    = np.linspace(0, dur, n)
    freq = 160 * np.exp(-t * 1.5)       # pitch drops over time
    phase = np.cumsum(2 * math.pi * freq / _SAMPLE_RATE)
    roar = (np.sin(phase) * 0.7).astype(np.float32)
    roar = _exp_decay(roar, 0.4)

    # Layer 3: white noise rumble burst
    noise = _noise(dur, 0.5)
    noise = _exp_decay(noise, 0.18)

    # Layer 4: high triumphant ring (1200 Hz harmonic, long tail)
    ring = _sine(1200, dur, 0.3)
    ring += _sine(2400, dur, 0.15)
    ring += _sine(600,  dur, 0.2)
    ring = _envelope(ring, attack=0.005, decay=0.05, sustain=0.5, release=0.7)

    # Layer 5: metallic zing sweep (freq rising)
    freq2 = 300 + 1400 * np.linspace(0, 1, n) ** 0.4
    phase2 = np.cumsum(2 * math.pi * freq2 / _SAMPLE_RATE)
    zing = (np.sin(phase2) * 0.4).astype(np.float32)
    zing_env = np.zeros(n, dtype=np.float32)
    zing_env[:int(n * 0.05)] = np.linspace(0, 1, int(n * 0.05))
    zing_env[int(n * 0.05):int(n * 0.45)] = np.linspace(1, 0, int(n * 0.40))
    zing *= zing_env

    combined = _norm(bass + roar + noise + ring + zing)
    # Convert to int16
    samples  = (combined * 28000).astype(np.int16)
    stereo   = _make_stereo(samples)
    sound    = pygame.sndarray.make_sound(stereo)
    return sound

def _build_boss_summon() -> pygame.Sound:
    dur = 1.2
    n   = int(_SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n)

    # Descending shriek (1500 → 400 Hz)
    freq = 1500 * np.exp(-t * 1.8)
    phase = np.cumsum(2 * math.pi * freq / _SAMPLE_RATE)
    shriek = (np.sin(phase) * 0.6 + np.sin(phase * 2) * 0.3).astype(np.float32)
    shriek = _envelope(shriek, attack=0.01, decay=0.05, sustain=0.7, release=0.3)

    noise = _noise(dur, 0.25)
    noise = _exp_decay(noise, 0.15)

    combined = _norm(shriek + noise)
    samples  = (combined * 22000).astype(np.int16)
    stereo   = _make_stereo(samples)
    return pygame.sndarray.make_sound(stereo)

def _build_ui_confirm() -> pygame.Sound:
    dur = 0.18
    s   = _sine(880, dur, 1.0) + _sine(1320, dur, 0.5)
    s   = _envelope(s, attack=0.02, decay=0.05, sustain=0.6, release=0.25)
    samples = (_norm(s) * 16000).astype(np.int16)
    return pygame.sndarray.make_sound(_make_stereo(samples))

# ── Public API ─────────────────────────────────────────────────────────────────

def _get(name: str) -> pygame.Sound | None:
    """Return a cached Sound, building it on first call. Returns None on error."""
    if name in _SOUNDS:
        return _SOUNDS[name]
    try:
        builders = {
            "boss_death":   _build_boss_death,
            "boss_summon":  _build_boss_summon,
            "ui_confirm":   _build_ui_confirm,
        }
        if name not in builders:
            return None
        sound = builders[name]()
        _SOUNDS[name] = sound
        return sound
    except Exception:
        _SOUNDS[name] = None   # cache the failure so we don't retry
        return None

def play_boss_death() -> None:
    s = _get("boss_death")
    if s:
        try:
            s.set_volume(0.85)
            s.play()
        except Exception:
            pass

def play_boss_summon() -> None:
    s = _get("boss_summon")
    if s:
        try:
            s.set_volume(0.55)
            s.play()
        except Exception:
            pass

def play_ui_confirm() -> None:
    s = _get("ui_confirm")
    if s:
        try:
            s.set_volume(0.4)
            s.play()
        except Exception:
            pass
