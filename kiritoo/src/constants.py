"""
constants.py - Game-wide constants and configuration
"""

# Screen
SCREEN_WIDTH  = 960
SCREEN_HEIGHT = 720
FPS = 60
TITLE = "Kiritoo"

# Tile
TILE_SIZE = 48
COLS = SCREEN_WIDTH  // TILE_SIZE   # 20
ROWS = (SCREEN_HEIGHT - 80) // TILE_SIZE  # ~13 (leaving room for HUD)

# Colors
BLACK       = (0,   0,   0)
WHITE       = (255, 255, 255)
GRAY        = (100, 100, 100)
DARK_GRAY   = (40,  40,  40)
RED         = (220, 50,  50)
GREEN       = (50,  200, 80)
BLUE        = (60,  120, 220)
YELLOW      = (240, 200, 40)
ORANGE      = (240, 130, 30)
PURPLE      = (150, 60,  220)
CYAN        = (40,  200, 220)
GOLD_COLOR  = (255, 215, 0)
DARK_BG     = (18,  18,  28)
FLOOR_COLOR = (55,  50,  70)
WALL_COLOR  = (25,  22,  38)

# Game States
STATE_MENU        = "menu"
STATE_NAME_ENTRY  = "name_entry"
STATE_PLAYING     = "playing"
STATE_MERCHANT    = "merchant"
STATE_GAME_OVER   = "game_over"
STATE_LEADERBOARD = "leaderboard"
STATE_PAUSED      = "paused"

# Player
PLAYER_START_HP     = 100
PLAYER_START_ATK    = 15
PLAYER_START_DEF    = 5
PLAYER_SPEED        = 3
PLAYER_INVINCIBLE_MS = 600  # ms of invincibility after hit

# Enemy  (harder: +67% HP, +75% ATK, -33% speed)
ENEMY_BASE_HP    = 50
ENEMY_BASE_ATK   = 14
ENEMY_BASE_SPEED = 1.0
ENEMY_EXP_BASE   = 20
ENEMY_AGGRO_RADIUS = 250  # pixels

# Boss  (tougher: bigger HP/ATK pool)
BOSS_HP_MULT  = 12
BOSS_ATK_MULT = 3.5

# Items
ITEM_TYPES = ["potion", "weapon", "armor", "buff", "gold"]
RARITY_WEIGHTS = {"common": 60, "uncommon": 25, "rare": 12, "legendary": 3}

# Combo
COMBO_WINDOW_MS = 3000   # ms window to chain kills
COMBO_MAX       = 10

# Merchant
MERCHANT_FLOOR_INTERVAL = 5

# Floor Curses
CURSES = [
    "none",
    "fast_enemies",   # enemies 2x speed
    "no_potions",     # potions disabled
    "darkness",       # reduced visibility
    "fragile",        # player takes double damage
    "poor_loot",      # item drops halved
]
CURSE_WEIGHTS = [30, 15, 15, 15, 15, 10]

# Stamina
STAMINA_MAX          = 100
STAMINA_REGEN_PER_SEC = 18   # per second passive regen
ATTACK_STAMINA_COST  = 8

# Skills
FIREBALL_STAMINA_COST = 30
FIREBALL_SPEED        = 9    # px per frame
FIREBALL_DMG_MULT     = 2.5
AREA_STAMINA_COST     = 50
AREA_RADIUS           = 160
AREA_DMG_MULT         = 1.5
AREA_DURATION_MS      = 700

# Stats sampling
HP_SAMPLE_INTERVAL_MS = 2000

# Leaderboard
LEADERBOARD_SIZE = 10

# CSV paths
DATA_DIR            = "data"
STATS_CSV           = "data/stats.csv"
LEADERBOARD_CSV     = "data/leaderboard.csv"
