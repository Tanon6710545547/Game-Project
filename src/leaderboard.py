"""
leaderboard.py - Persist top-10 sessions across playthroughs
"""
import csv
import os
from src.constants import LEADERBOARD_CSV, LEADERBOARD_SIZE, DATA_DIR

FIELDS = ["rank", "session_id", "player_name", "floor_reached", "kills",
          "max_combo", "duration_sec"]


class Leaderboard:
    """Maintains a persistent top-10 leaderboard stored as CSV."""

    def __init__(self):
        self.entries: list[dict] = []
        os.makedirs(DATA_DIR, exist_ok=True)
        self.load()

    # ------------------------------------------------------------------
    def load(self):
        if not os.path.exists(LEADERBOARD_CSV):
            self.entries = []
            return
        with open(LEADERBOARD_CSV, newline="") as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader]
        self.entries = []
        for e in rows:
            for k in ("floor_reached", "kills", "max_combo"):
                try:
                    e[k] = int(e[k])
                except (ValueError, KeyError):
                    e[k] = 0
            try:
                e["duration_sec"] = float(e["duration_sec"])
            except (ValueError, KeyError):
                e["duration_sec"] = 0.0
            # Clamp floor to max 20; drop legacy entries exceeding it
            e["floor_reached"] = min(20, e["floor_reached"])
            # Back-fill player_name for old CSV rows that lacked it
            if not e.get("player_name"):
                e["player_name"] = e.get("session_id", "?")[:6]
            self.entries.append(e)
        # Re-sort and re-rank: floor desc, then time asc (faster = better rank)
        self.entries.sort(key=lambda x: (-int(x["floor_reached"]), float(x.get("duration_sec", 99999))))
        for i, e in enumerate(self.entries, 1):
            e["rank"] = i
        self.save()

    def save(self):
        with open(LEADERBOARD_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.entries)

    # ------------------------------------------------------------------
    def add_entry(self, session: dict):
        """Insert session, re-sort by floor_reached desc, keep top-10."""
        entry = {
            "rank":          0,
            "session_id":    session.get("session_id", "?"),
            "player_name":   session.get("player_name", "?")[:14],
            "floor_reached": min(20, int(session.get("floor_reached", 0))),
            "kills":         int(session.get("kills", 0)),
            "max_combo":     int(session.get("max_combo", 0)),
            "duration_sec":  float(session.get("duration_sec", 0)),
        }
        self.entries.append(entry)
        self.entries.sort(key=lambda x: (-int(x["floor_reached"]), float(x.get("duration_sec", 99999))))
        for i, e in enumerate(self.entries, 1):
            e["rank"] = i
        self.save()

    def display_top10(self) -> list[dict]:
        return self.entries

    def get_speed_top3(self) -> list[dict]:
        """Top 3 floor-20 completions sorted by fastest time."""
        winners = [e for e in self.entries if int(e.get("floor_reached", 0)) >= 20]
        return winners[:3]  # already sorted fastest first

    def get_player_context(self, session_id: str, n: int = 2):
        """Returns (rank, total, context_entries, player_idx_in_context)."""
        for i, e in enumerate(self.entries):
            if e.get("session_id") == session_id:
                total = len(self.entries)
                lo    = max(0, i - n)
                hi    = min(total, i + n + 1)
                return i + 1, total, self.entries[lo:hi], i - lo
        return 0, len(self.entries), [], 0
