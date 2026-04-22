"""
stat_tracker.py - Record and export gameplay statistics
Features tracked:
  floor_reached, enemies_defeated, combo_count, items_collected,
  gold_spent, player_hp_over_time, floor_curse_types, session_duration
"""
import csv
import os
import time
import uuid
from src.constants import STATS_CSV, DATA_DIR


STAT_FIELDS = [
    "session_id", "timestamp", "event_type",
    "floor", "value", "item_type", "curse_type",
    "enemy_type", "combo_count", "hp", "max_hp",
    "gold_spent", "duration_sec"
]


class StatTracker:
    """Collects gameplay events and exports them to CSV at session end."""

    def __init__(self):
        self.session_id  = str(uuid.uuid4())[:8]
        self.start_time  = time.time()
        self.log: list[dict] = []
        os.makedirs(DATA_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    def record(self, event_type: str, **kwargs):
        """Append one event record."""
        row = {f: "" for f in STAT_FIELDS}
        row["session_id"]  = self.session_id
        row["timestamp"]   = round(time.time(), 2)
        row["event_type"]  = event_type
        for k, v in kwargs.items():
            if k in row:
                row[k] = v
        self.log.append(row)

    # ------------------------------------------------------------------
    def export_csv(self):
        """Append all logged events to the shared stats CSV."""
        write_header = not os.path.exists(STATS_CSV) or os.path.getsize(STATS_CSV) == 0
        with open(STATS_CSV, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=STAT_FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerows(self.log)
        self.log.clear()

    # ------------------------------------------------------------------
    def generate_summary(self, floor_reached: int, kills: int) -> dict:
        """Return a summary dict for the leaderboard."""
        duration = round(time.time() - self.start_time, 1)
        combos   = [r["combo_count"] for r in self.log if r["combo_count"] not in ("", None)]
        max_combo = max((int(c) for c in combos), default=0)
        return {
            "session_id":    self.session_id,
            "floor_reached": floor_reached,
            "kills":         kills,
            "max_combo":     max_combo,
            "duration_sec":  duration,
        }
