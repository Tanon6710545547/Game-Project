"""
item.py - Item class: effects, pickup, rarity tiers
"""
import random
from src.constants import RARITY_WEIGHTS


ITEM_DEFINITIONS = {
    # name: (type, effect_value, rarity, description)
    "Small Potion":      ("potion",  30,  "common",    "Restores 30 HP"),
    "Large Potion":      ("potion",  70,  "uncommon",  "Restores 70 HP"),
    "Elixir":            ("potion",  150, "rare",      "Fully restores HP"),
    "Rusty Sword":       ("weapon",  5,   "common",    "+5 Attack"),
    "Iron Sword":        ("weapon",  12,  "uncommon",  "+12 Attack"),
    "Flame Blade":       ("weapon",  25,  "rare",      "+25 Attack, chance to burn"),
    "Void Blade":        ("weapon",  45,  "legendary", "+45 Attack, lifesteal"),
    "Leather Armor":     ("armor",   4,   "common",    "+4 Defense"),
    "Chain Mail":        ("armor",   10,  "uncommon",  "+10 Defense"),
    "Dragon Scale":      ("armor",   22,  "rare",      "+22 Defense"),
    "Speed Tonic":       ("buff",    0,   "uncommon",  "+20% Move Speed (floor)"),
    "Strength Brew":     ("buff",    8,   "uncommon",  "+8 Attack (floor)"),
    "Gold Bag":          ("gold",    25,  "common",    "+25 Gold"),
    "Treasure Chest":    ("gold",    75,  "rare",      "+75 Gold"),
}


def weighted_rarity_choice():
    rarities = list(RARITY_WEIGHTS.keys())
    weights  = list(RARITY_WEIGHTS.values())
    return random.choices(rarities, weights=weights, k=1)[0]


def random_item_by_rarity(rarity=None):
    if rarity is None:
        rarity = weighted_rarity_choice()
    pool = [k for k, v in ITEM_DEFINITIONS.items() if v[2] == rarity]
    if not pool:
        pool = [k for k, v in ITEM_DEFINITIONS.items() if v[2] == "common"]
    name = random.choice(pool)
    return Item(name)


class Item:
    """Represents a collectible item with type, effect, and rarity."""

    def __init__(self, name: str):
        if name not in ITEM_DEFINITIONS:
            name = "Small Potion"
        defn = ITEM_DEFINITIONS[name]
        self.name         = name
        self.type         = defn[0]   # potion / weapon / armor / buff / gold
        self.effect_value = defn[1]
        self.rarity       = defn[2]
        self.description  = defn[3]
        # World position (set when dropped on floor)
        self.x = 0
        self.y = 0
        self.collected = False

    # ------------------------------------------------------------------
    def apply(self, player, curse_type: str = "none"):
        """Apply item effect to player. Returns feedback string."""
        if self.type == "potion":
            if curse_type == "no_potions":
                return f"{self.name} fizzled! (Cursed floor)"
            heal = self.effect_value
            player.hp = min(player.max_hp, player.hp + heal)
            player.stat_tracker.record("items_collected",
                                       item_type=self.type, floor=player.current_floor,
                                       value=1)
            return f"Healed {heal} HP"

        elif self.type == "weapon":
            player.attack += self.effect_value
            player.stat_tracker.record("items_collected",
                                       item_type=self.type, floor=player.current_floor,
                                       value=1)
            return f"Attack +{self.effect_value}"

        elif self.type == "armor":
            player.defense += self.effect_value
            player.stat_tracker.record("items_collected",
                                       item_type=self.type, floor=player.current_floor,
                                       value=1)
            return f"Defense +{self.effect_value}"

        elif self.type == "buff":
            player.temp_buffs.append((self.name, self.effect_value))
            player.stat_tracker.record("items_collected",
                                       item_type=self.type, floor=player.current_floor,
                                       value=1)
            return f"Buff: {self.description}"

        elif self.type == "gold":
            player.gold += self.effect_value
            player.stat_tracker.record("items_collected",
                                       item_type=self.type, floor=player.current_floor,
                                       value=1)
            return f"+{self.effect_value} Gold"

        return "Nothing happened."

    def describe(self) -> str:
        return f"[{self.rarity.upper()}] {self.name}: {self.description}"

    def __repr__(self):
        return f"Item({self.name}, {self.type}, {self.rarity})"
