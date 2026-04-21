"""
combo_system.py - Combo Kill Multiplier tracking
"""
import time
from src.constants import COMBO_WINDOW_MS, COMBO_MAX


class ComboSystem:
    """
    Tracks consecutive kills within a time window and computes
    a multiplier for gold / EXP rewards.
    """

    def __init__(self):
        self.combo_count    = 0
        self.last_kill_time = 0   # ms (pygame.time.get_ticks())
        self.multiplier     = 1.0
        self._history: list[int] = []   # combo counts recorded per reset (for stats)

    # ------------------------------------------------------------------
    def register_kill(self, current_time_ms: int):
        """Called on every enemy kill. Returns current multiplier."""
        if current_time_ms - self.last_kill_time <= COMBO_WINDOW_MS:
            self.combo_count = min(self.combo_count + 1, COMBO_MAX)
        else:
            # Chain broke — save old count before reset
            if self.combo_count > 0:
                self._history.append(self.combo_count)
            self.combo_count = 1

        self.last_kill_time = current_time_ms
        self.multiplier = 1.0 + (self.combo_count * 0.2)   # +20% per combo
        return self.multiplier

    def check_expiry(self, current_time_ms: int):
        """Call every frame to detect if combo window expired."""
        if self.combo_count > 0 and (current_time_ms - self.last_kill_time > COMBO_WINDOW_MS):
            self._history.append(self.combo_count)
            self.reset()

    def reset(self):
        """Hard reset (floor change or death)."""
        if self.combo_count > 0:
            self._history.append(self.combo_count)
        self.combo_count    = 0
        self.last_kill_time = 0
        self.multiplier     = 1.0

    def get_bonus(self) -> float:
        """Returns multiplier to apply to gold/EXP."""
        return self.multiplier

    def pop_history(self) -> list[int]:
        """Return recorded combos and clear history (used by StatTracker)."""
        h = self._history[:]
        self._history.clear()
        return h

    def __repr__(self):
        return f"ComboSystem(count={self.combo_count}, x{self.multiplier:.1f})"
