"""
floor.py - Floor generation, layout, curse system  (full visual overhaul)
"""
from __future__ import annotations
import math
import os
import pygame
import random
from collections import deque
from src.constants import (
    TILE_SIZE, COLS, ROWS,
    CURSES, CURSE_WEIGHTS,
    SCREEN_WIDTH, SCREEN_HEIGHT,
    FLOOR_COLOR, WALL_COLOR, DARK_BG,
    MERCHANT_FLOOR_INTERVAL,
)
from src.enemy import Enemy, Boss
from src.item import Item, random_item_by_rarity

_ITEM_IMAGES: dict = {}

def _load_item_images():
    if _ITEM_IMAGES:
        return
    _src = os.path.dirname(__file__)
    for item_type, filename in [
        ("potion", "heal.png"),
        ("weapon", "sword.png"),
        ("armor",  "shield.png"),
        ("gold",   "gold-coins-.png"),
        ("buff",   "gacha.png"),
    ]:
        path = os.path.join(_src, filename)
        try:
            img = pygame.image.load(path).convert_alpha()
            _ITEM_IMAGES[item_type] = pygame.transform.smoothscale(img, (18, 18))
        except Exception:
            _ITEM_IMAGES[item_type] = None


# ── Visual themes ──────────────────────────────────────────────────────────────
_THEMES = {
    "dungeon": dict(
        bg=(12,10,20), floor=(52,47,68), floor_alt=(58,53,75),
        floor_moss=(40,55,46), floor_crack=(46,42,62),
        wall=(24,21,36), wall_top=(42,38,58), wall_bot=(13,11,22),
        wall_side=(32,29,46), grout=(15,13,25),
        pillar=(32,28,48), pillar_top=(50,46,68),
        torch_col=(255,152,38), torch_inner=(255,255,200),
        vine_col=(36,122,46), vine_leaf=(50,152,60),
        crystal_col=(80,172,255), rune_col=(70,108,220),
        chain_col=(74,72,84),
    ),
    "deep": dict(
        bg=(8,6,20), floor=(42,38,62), floor_alt=(48,44,70),
        floor_moss=(34,48,44), floor_crack=(38,34,58),
        wall=(19,17,33), wall_top=(34,30,52), wall_bot=(9,7,17),
        wall_side=(26,24,43), grout=(11,9,21),
        pillar=(27,23,44), pillar_top=(44,40,64),
        torch_col=(158,78,255), torch_inner=(220,180,255),
        vine_col=(26,104,52), vine_leaf=(38,128,62),
        crystal_col=(128,72,255), rune_col=(98,78,218),
        chain_col=(64,62,76),
    ),
    "abyss": dict(
        bg=(5,3,16), floor=(34,28,54), floor_alt=(40,34,62),
        floor_moss=(26,36,40), floor_crack=(30,25,50),
        wall=(15,12,28), wall_top=(28,24,46), wall_bot=(7,5,14),
        wall_side=(22,19,37), grout=(9,7,18),
        pillar=(22,18,38), pillar_top=(36,30,56),
        torch_col=(255,52,52), torch_inner=(255,200,180),
        vine_col=(18,84,42), vine_leaf=(26,106,52),
        crystal_col=(188,68,255), rune_col=(168,52,208),
        chain_col=(54,52,66),
    ),
    "boss": dict(
        bg=(8,3,3), floor=(40,24,24), floor_alt=(46,30,30),
        floor_moss=(34,20,20), floor_crack=(36,22,22),
        wall=(20,12,12), wall_top=(36,22,22), wall_bot=(9,5,5),
        wall_side=(28,17,17), grout=(12,7,7),
        pillar=(28,17,17), pillar_top=(44,27,27),
        torch_col=(255,34,14), torch_inner=(255,200,160),
        vine_col=(68,24,24), vine_leaf=(86,34,34),
        crystal_col=(255,48,48), rune_col=(198,24,24),
        chain_col=(60,44,44),
    ),
}

_RARITY_COL = {
    "common":    (140,140,145),
    "uncommon":  (55,198,70),
    "rare":      (64,114,248),
    "legendary": (255,188,14),
}
_RARITY_GLOW = {
    "common": 22, "uncommon": 44, "rare": 72, "legendary": 115,
}


class Floor:
    """Generates a tile-based floor layout, populates enemies/items,
    and applies a random curse modifier."""

    def __init__(self, floor_num: int, stat_tracker=None, player_attack: int = 15):
        self.floor_num     = floor_num
        self.stat_tracker  = stat_tracker
        self.player_attack = player_attack
        self.curse_type    = self._pick_curse()
        self.is_boss       = (floor_num > 1 and floor_num % 10 == 0)
        self.is_merchant   = (floor_num > 1
                              and floor_num % MERCHANT_FLOOR_INTERVAL == 0
                              and not self.is_boss)

        self.tiles:      list[list[int]]   = []
        self.wall_rects: list[pygame.Rect] = []
        self.walls_set:  set[tuple]        = set()
        self.enemies:    list[Enemy]       = []
        self.items:      list[Item]        = []
        self.exit_rect:  pygame.Rect | None = None
        self.exit_open   = False

        self.generate()

        if self.stat_tracker:
            self.stat_tracker.record("floor_curse_types",
                                     floor=floor_num, curse_type=self.curse_type, value=1)

    # ── generation helpers ─────────────────────────────────────────────────────
    def _pick_curse(self) -> str:
        return random.choices(CURSES, weights=CURSE_WEIGHTS, k=1)[0]

    def generate(self):
        random.seed()
        self.tiles = [[0]*COLS for _ in range(ROWS)]

        for c in range(COLS):
            self.tiles[0][c] = 1
            self.tiles[ROWS-1][c] = 1
        for r in range(ROWS):
            self.tiles[r][0] = 1
            self.tiles[r][COLS-1] = 1

        num_obstacles = random.randint(8, 18)
        for _ in range(num_obstacles):
            r = random.randint(2, ROWS-3)
            c = random.randint(2, COLS-3)
            length = random.randint(1, 4)
            horizontal = random.random() > 0.5
            for i in range(length):
                tr = r + (0 if horizontal else i)
                tc = c + (i if horizontal else 0)
                if 1 <= tr < ROWS-1 and 1 <= tc < COLS-1:
                    self.tiles[tr][tc] = 1

        ex_col = COLS // 2
        ex_row = 1
        self.tiles[ex_row][ex_col] = 0
        self._ensure_connectivity()

        self.wall_rects = []
        self.walls_set  = set()
        for r in range(ROWS):
            for c in range(COLS):
                if self.tiles[r][c] == 1:
                    self.wall_rects.append(pygame.Rect(c*TILE_SIZE, r*TILE_SIZE,
                                                       TILE_SIZE, TILE_SIZE))
                    self.walls_set.add((c, r))

        self.exit_rect = pygame.Rect(ex_col*TILE_SIZE+4, ex_row*TILE_SIZE+4,
                                     TILE_SIZE-8, TILE_SIZE-8)
        self.player_spawn_pos = self._find_spawn_pos(TILE_SIZE-14)

        if not self.is_merchant:
            self._spawn_enemies()
        self._scatter_items()
        self._generate_decorations()

    # ── decoration generation ──────────────────────────────────────────────────
    def _generate_decorations(self):
        rng = random.Random(self.floor_num * 7919 + 42)

        if self.is_boss:          tk = "boss"
        elif self.floor_num >= 11: tk = "abyss"
        elif self.floor_num >= 6:  tk = "deep"
        else:                      tk = "dungeon"
        self._theme = _THEMES[tk]
        th = self._theme

        # Floor tile variants (deterministic per tile)
        self._fv: dict[tuple,str] = {}
        for r in range(ROWS):
            for c in range(COLS):
                if self.tiles[r][c] == 0:
                    h = (r*31 + c*17 + self.floor_num*7) % 100
                    if h < 5:   self._fv[(c,r)] = "cracked"
                    elif h < 10: self._fv[(c,r)] = "mossy"
                    elif h < 13: self._fv[(c,r)] = "inlay"
                    elif h < 16: self._fv[(c,r)] = "stained"
                    elif h < 18 and self.is_boss: self._fv[(c,r)] = "blood"
                    else:        self._fv[(c,r)] = "normal"

        # Pre-generate crack line data
        self._crack_data: dict[tuple,list] = {}
        for (c,r),v in self._fv.items():
            if v == "cracked":
                cr = random.Random(c*100+r+self.floor_num)
                lines = []
                for _ in range(cr.randint(2,4)):
                    x1,y1 = cr.randint(4,TILE_SIZE-4), cr.randint(4,TILE_SIZE-4)
                    pts = [(x1,y1)]
                    for _ in range(cr.randint(2,4)):
                        pts.append((pts[-1][0]+cr.randint(-10,10),
                                    pts[-1][1]+cr.randint(-10,10)))
                    lines.append(pts)
                self._crack_data[(c,r)] = lines

        # Pillars: isolated wall tiles with floor on 3+ cardinal sides
        self._pillars: set[tuple] = set()
        for r in range(1, ROWS-1):
            for c in range(1, COLS-1):
                if self.tiles[r][c] == 1:
                    nf = sum(1 for nc,nr in [(c-1,r),(c+1,r),(c,r-1),(c,r+1)]
                             if 0<=nc<COLS and 0<=nr<ROWS and self.tiles[nr][nc]==0)
                    if nf >= 3:
                        self._pillars.add((c,r))

        # Torches: wall with floor directly below, spaced apart
        tcands = [(c,r) for r in range(1,ROWS-2) for c in range(1,COLS-1)
                  if self.tiles[r][c]==1 and self.tiles[r+1][c]==0
                  and (c,r) not in self._pillars]
        rng.shuffle(tcands)
        self._torches: list[dict] = []
        for tc,tr in tcands:
            if len(self._torches) >= 9: break
            if all(abs(tc-e["c"])+abs(tr-e["r"]) > 3 for e in self._torches):
                self._torches.append({"c":tc,"r":tr,"phase":rng.uniform(0,math.pi*2)})

        # Vines: wall with floor below, not torch positions
        tp = {(e["c"],e["r"]) for e in self._torches}
        vcands = [(c,r) for r in range(1,ROWS-2) for c in range(1,COLS-1)
                  if self.tiles[r][c]==1 and self.tiles[r+1][c]==0
                  and (c,r) not in tp and (c,r) not in self._pillars]
        rng.shuffle(vcands)
        self._vines: list[dict] = []
        for vc,vr in vcands[:rng.randint(5,13)]:
            self._vines.append({
                "c":vc,"r":vr,
                "length":rng.randint(1,3),
                "strands":rng.randint(1,3),
                "phases":[rng.uniform(0,math.pi*2) for _ in range(3)],
                "offsets":[rng.randint(-10,10) for _ in range(3)],
            })

        # Floor tile pool
        fts = [(c,r) for r in range(2,ROWS-2) for c in range(2,COLS-2)
               if self.tiles[r][c]==0]
        rng.shuffle(fts)
        idx = 0

        self._floor_decos: list[dict] = []

        # Rugs (1–3)
        rug_cols = [(110,28,28),(28,55,110),(70,45,18),(55,28,80),(20,78,55)]
        for _ in range(rng.randint(1,3)):
            if idx >= len(fts): break
            c,r = fts[idx]; idx+=1
            self._floor_decos.append({"type":"rug","c":c,"r":r,
                                       "color":rng.choice(rug_cols)})

        # Puddles (2–4)
        for _ in range(rng.randint(2,4)):
            if idx >= len(fts): break
            c,r = fts[idx]; idx+=1
            self._floor_decos.append({
                "type":"puddle",
                "x":c*TILE_SIZE+TILE_SIZE//2,"y":r*TILE_SIZE+TILE_SIZE//2,
                "rx":rng.randint(10,20),"ry":rng.randint(5,10),
                "phase":rng.uniform(0,math.pi*2),
            })

        # Bones / skulls (5–10)
        for _ in range(rng.randint(5,10)):
            if idx >= len(fts): break
            c,r = fts[idx]; idx+=1
            self._floor_decos.append({
                "type":"bones",
                "x":c*TILE_SIZE+rng.randint(8,TILE_SIZE-8),
                "y":r*TILE_SIZE+rng.randint(8,TILE_SIZE-8),
                "angle":rng.uniform(0,math.pi),
                "variant":rng.randint(0,2),
                "scale":rng.uniform(0.7,1.2),
            })

        # Candles (3–6)
        for _ in range(rng.randint(3,6)):
            if idx >= len(fts): break
            c,r = fts[idx]; idx+=1
            self._floor_decos.append({
                "type":"candle",
                "x":c*TILE_SIZE+rng.randint(6,TILE_SIZE-6),
                "y":r*TILE_SIZE+rng.randint(6,TILE_SIZE-6),
                "phase":rng.uniform(0,math.pi*2),
            })

        # Cobwebs in floor-tile corners adjacent to two walls
        self._cobwebs: list[dict] = []
        for r in range(1,ROWS-1):
            for c in range(1,COLS-1):
                if self.tiles[r][c] == 0:
                    # NW corner
                    if (r>0 and c>0
                            and self.tiles[r-1][c]==1 and self.tiles[r][c-1]==1
                            and rng.random() < 0.28):
                        self._cobwebs.append({
                            "x":c*TILE_SIZE,"y":r*TILE_SIZE,
                            "flip_x":False,"size":rng.randint(18,32),
                            "phase":rng.uniform(0,math.pi*2),
                        })
                    # NE corner
                    elif (r>0 and c<COLS-1
                            and self.tiles[r-1][c]==1 and self.tiles[r][c+1]==1
                            and rng.random() < 0.28):
                        self._cobwebs.append({
                            "x":(c+1)*TILE_SIZE,"y":r*TILE_SIZE,
                            "flip_x":True,"size":rng.randint(18,32),
                            "phase":rng.uniform(0,math.pi*2),
                        })
        if len(self._cobwebs) > 12:
            rng.shuffle(self._cobwebs); self._cobwebs = self._cobwebs[:12]

        # Crystals embedded in walls (floor 6+)
        self._crystals: list[dict] = []
        if self.floor_num >= 6:
            wcands = [(c,r) for r in range(1,ROWS-1) for c in range(1,COLS-1)
                      if self.tiles[r][c]==1 and (c,r) not in self._pillars
                      and (c,r) not in tp]
            rng.shuffle(wcands)
            bc = th["crystal_col"]
            for cc,cr in wcands[:rng.randint(4,10)]:
                j = lambda v: max(0,min(255,v+rng.randint(-25,25)))
                self._crystals.append({
                    "c":cc,"r":cr,
                    "color":(j(bc[0]),j(bc[1]),j(bc[2])),
                    "size":rng.randint(4,9),
                    "phase":rng.uniform(0,math.pi*2),
                    "side":rng.choice(["top","left","right"]),
                })

        # Hanging chains (floor 3+)
        self._chains: list[dict] = []
        if self.floor_num >= 3:
            chcands = [(c,r) for r in range(1,ROWS-1) for c in range(1,COLS-1)
                       if self.tiles[r][c]==1 and r+1<ROWS and self.tiles[r+1][c]==0
                       and (c,r) not in tp and (c,r) not in self._pillars]
            rng.shuffle(chcands)
            for chc,chr_ in chcands[:rng.randint(2,5)]:
                self._chains.append({
                    "x":chc*TILE_SIZE+TILE_SIZE//2+rng.randint(-8,8),
                    "y":(chr_+1)*TILE_SIZE,
                    "length":rng.randint(14,36),
                    "links":rng.randint(4,8),
                    "sway":rng.uniform(0,math.pi*2),
                })

        # Rune circles on floor (floor 3+)
        self._runes: list[dict] = []
        if self.floor_num >= 3:
            rng.shuffle(fts)
            for rc,rr in fts[:rng.randint(1,3)]:
                self._runes.append({
                    "x":rc*TILE_SIZE+TILE_SIZE//2,
                    "y":rr*TILE_SIZE+TILE_SIZE//2,
                    "radius":rng.randint(18,30),
                    "phase":rng.uniform(0,math.pi*2),
                    "spokes":rng.randint(5,8),
                })

    # ── game-logic helpers (unchanged) ─────────────────────────────────────────
    def _ensure_connectivity(self):
        start_c, start_r = COLS//2, ROWS//2
        self.tiles[start_r][start_c] = 0
        def floor_reachable():
            visited = set(); q = deque([(start_c,start_r)]); visited.add((start_c,start_r))
            while q:
                cc,cr = q.popleft()
                for nc,nr in [(cc-1,cr),(cc+1,cr),(cc,cr-1),(cc,cr+1)]:
                    if 0<=nc<COLS and 0<=nr<ROWS and self.tiles[nr][nc]==0 and (nc,nr) not in visited:
                        visited.add((nc,nr)); q.append((nc,nr))
            return visited
        while True:
            reachable = floor_reachable(); target = None
            for r in range(1,ROWS-1):
                for c in range(1,COLS-1):
                    if self.tiles[r][c]==0 and (c,r) not in reachable:
                        target=(c,r); break
                if target: break
            if not target: break
            tc,tr = target; q=deque([(tc,tr)]); came_from={(tc,tr):None}; found=None
            while q and found is None:
                cc,cr = q.popleft()
                for nc,nr in [(cc-1,cr),(cc+1,cr),(cc,cr-1),(cc,cr+1)]:
                    if 0<=nc<COLS and 0<=nr<ROWS and (nc,nr) not in came_from:
                        came_from[(nc,nr)]=(cc,cr)
                        if (nc,nr) in reachable: found=(nc,nr); break
                        q.append((nc,nr))
            if not found: break
            step=found
            while step is not None:
                sc,sr=step
                if self.tiles[sr][sc]==1 and 1<=sc<COLS-1 and 1<=sr<ROWS-1:
                    self.tiles[sr][sc]=0
                step=came_from[step]

    def _spawn_enemies(self):
        num=min(self.floor_num+random.randint(2,5),12)
        if self.is_boss: num=1
        for _ in range(num):
            size=TILE_SIZE+16 if self.is_boss else TILE_SIZE-8
            pos=self._find_spawn_pos(size)
            if self.is_boss:
                self.enemies.append(Boss(pos[0],pos[1],self.floor_num,self.player_attack))
            else:
                self.enemies.append(Enemy(pos[0],pos[1],self.floor_num,player_atk=self.player_attack))

    def _scatter_items(self):
        num=random.randint(1,3)
        if self.curse_type=="poor_loot": num=max(0,num-1)
        used:set[tuple]=set()
        for _ in range(num):
            item=random_item_by_rarity()
            pos=self._find_spawn_pos(20,used)
            item.x,item.y=pos
            tc,tr=item.x//TILE_SIZE,item.y//TILE_SIZE
            for dr in range(-2,3):
                for dc in range(-2,3): used.add((tc+dc,tr+dr))
            self.items.append(item)

    def _find_spawn_pos(self,entity_size:int,exclude_tiles:set|None=None)->tuple[int,int]:
        hw=entity_size//2; exclude=exclude_tiles or set(); candidates=[]
        for r in range(1,ROWS-1):
            for c in range(1,COLS-1):
                if self.tiles[r][c]!=0 or (c,r) in exclude: continue
                px=c*TILE_SIZE+TILE_SIZE//2; py=r*TILE_SIZE+TILE_SIZE//2
                er=pygame.Rect(px-hw,py-hw,entity_size,entity_size)
                if not any(er.colliderect(wr) for wr in self.wall_rects):
                    candidates.append((px,py))
        if candidates: return random.choice(candidates)
        for r in range(1,ROWS-1):
            for c in range(1,COLS-1):
                if self.tiles[r][c]==0:
                    return c*TILE_SIZE+TILE_SIZE//2,r*TILE_SIZE+TILE_SIZE//2
        return COLS//2*TILE_SIZE+TILE_SIZE//2,ROWS//2*TILE_SIZE+TILE_SIZE//2

    def check_exit(self)->bool: return self.exit_open
    def update_exit(self):
        if not self.exit_open and all(not e.alive for e in self.enemies):
            self.exit_open=True
    def get_enemy(self,index:int)->Enemy|None:
        return self.enemies[index] if 0<=index<len(self.enemies) else None
    def remove_wall(self,col:int,row:int)->bool:
        if not(1<=col<COLS-1 and 1<=row<ROWS-1): return False
        if self.tiles[row][col]!=1: return False
        self.tiles[row][col]=0
        target=pygame.Rect(col*TILE_SIZE,row*TILE_SIZE,TILE_SIZE,TILE_SIZE)
        self.wall_rects=[r for r in self.wall_rects if r!=target]
        self.walls_set.discard((col,row))
        return True
    def apply_curse(self,player):
        if self.curse_type!="none":
            player.add_message(f"Floor Curse: {self.curse_type.replace('_',' ').title()}!",3500)

    # ══════════════════════════════════════════════════════════════════════════
    # DRAW
    # ══════════════════════════════════════════════════════════════════════════
    def draw(self, surface: pygame.Surface):
        now = pygame.time.get_ticks()
        t   = now / 1000.0
        th  = self._theme

        surface.fill(th["bg"])

        # ── 1. Floor tiles ────────────────────────────────────────────────────
        for r in range(ROWS):
            for c in range(COLS):
                if self.tiles[r][c] == 0:
                    self._draw_floor_tile(surface, c, r, th, t)

        # ── 2. Floor decorations (below walls & entities) ─────────────────────
        for deco in self._floor_decos:
            dt = deco["type"]
            if dt == "rug":    self._draw_rug(surface, deco, th)
            elif dt == "puddle": self._draw_puddle(surface, deco, t)
            elif dt == "bones":  self._draw_bones(surface, deco)

        # ── 3. Rune circles ───────────────────────────────────────────────────
        for rune in self._runes:
            self._draw_rune(surface, rune, t, th)

        # ── 4. Wall tiles ─────────────────────────────────────────────────────
        for r in range(ROWS):
            for c in range(COLS):
                if self.tiles[r][c] == 1:
                    self._draw_wall_tile(surface, c, r, th)

        # ── 5. Torch warm floor glow ──────────────────────────────────────────
        for torch in self._torches:
            self._draw_torch_glow(surface, torch, t, th)

        # ── 6. Vines ──────────────────────────────────────────────────────────
        for vine in self._vines:
            self._draw_vine(surface, vine, t, th)

        # ── 7. Crystals ───────────────────────────────────────────────────────
        for crystal in self._crystals:
            self._draw_crystal(surface, crystal, t)

        # ── 8. Chains ─────────────────────────────────────────────────────────
        for chain in self._chains:
            self._draw_chain(surface, chain, t, th)

        # ── 9. Torch flames ───────────────────────────────────────────────────
        for torch in self._torches:
            self._draw_torch_flame(surface, torch, t, th)

        # ── 10. Floor candles (drawn after torches so flames layer correctly) ─
        for deco in self._floor_decos:
            if deco["type"] == "candle":
                self._draw_candle(surface, deco, t, th)

        # ── 11. Cobwebs ───────────────────────────────────────────────────────
        for cw in self._cobwebs:
            self._draw_cobweb(surface, cw, t)

        # ── 12. Map edge vignette ─────────────────────────────────────────────
        pw, ph = COLS*TILE_SIZE, ROWS*TILE_SIZE
        vg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        for i in range(42):
            a = int(115*(1-i/42)**2)
            if a > 0:
                pygame.draw.rect(vg, (0,0,0,a), (i,i,pw-i*2,ph-i*2), 1)
        surface.blit(vg, (0, 0))

        # ── 13. Exit door ─────────────────────────────────────────────────────
        if self.exit_rect:
            ex = self.exit_rect.centerx
            ey = self.exit_rect.centery
            if self.exit_open:
                ps = TILE_SIZE+26
                portal = pygame.Surface((ps, ps), pygame.SRCALPHA)
                pcx = pcy = ps//2
                # Layered glow
                for gi in range(5):
                    gr = int(24-gi*3 + 4*math.sin(t*3+gi*0.7))
                    ga = int(38+16*math.sin(t*2.2+gi))
                    pygame.draw.circle(portal,(60,255,150,ga),(pcx,pcy),gr+gi*5+4,2)
                # Spinning dots
                for ri in range(3):
                    rr2 = 22-ri*5
                    rt  = t*(1.8+ri*0.7)
                    for dj in range(7):
                        da  = rt+dj*math.pi*2/7
                        dpx = int(math.cos(da)*rr2)
                        dpy = int(math.sin(da)*rr2)
                        sz  = max(1,3-ri)
                        pygame.draw.circle(portal,(100,255,175,int(200-ri*55)),
                                           (pcx+dpx,pcy+dpy),sz)
                # Bright core
                core_r = int(10+3*math.sin(t*4.5))
                pygame.draw.circle(portal,(150,255,210,200),(pcx,pcy),core_r)
                pygame.draw.circle(portal,(220,255,235,255),(pcx,pcy),max(1,core_r-4))
                surface.blit(portal,(ex-ps//2, ey-ps//2))
            else:
                dr = self.exit_rect
                pygame.draw.rect(surface,(42,38,58),dr,border_radius=4)
                for pk in range(3):
                    py2 = dr.top+5+pk*(dr.height//3)
                    pygame.draw.line(surface,(52,48,70),(dr.left+4,py2),(dr.right-4,py2),1)
                pygame.draw.rect(surface,(76,68,102),dr,2,border_radius=4)
                pygame.draw.circle(surface,(90,82,120),(ex,ey-2),5)
                pygame.draw.circle(surface,(112,102,152),(ex,ey-2),3)
                pygame.draw.rect(surface,(90,82,120),(ex-2,ey+2,4,6))

        # ── 14. Items as treasure chests ──────────────────────────────────────
        _load_item_images()
        for item in self.items:
            if not item.collected:
                self._draw_item(surface, item, t)

        # ── 15. Enemies ───────────────────────────────────────────────────────
        for enemy in self.enemies:
            enemy.draw(surface)

    # ══════════════════════════════════════════════════════════════════════════
    # TILE DRAW HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _draw_floor_tile(self, surface, c, r, th, t):
        rx, ry = c*TILE_SIZE, r*TILE_SIZE
        v = self._fv.get((c,r), "normal")

        if v == "mossy":
            bc = th["floor_moss"]
        elif v in ("cracked","stained","blood"):
            bc = th["floor_crack"]
        else:
            ck = 3 if (r+c)%2==0 else 0
            bc = (th["floor"][0]+ck, th["floor"][1]+ck, th["floor"][2]+ck)

        pygame.draw.rect(surface, bc, (rx,ry,TILE_SIZE,TILE_SIZE))

        if v == "cracked":
            for pts in self._crack_data.get((c,r),[]):
                if len(pts) >= 2:
                    apt = [(rx+x,ry+y) for x,y in pts]
                    pygame.draw.lines(surface,
                        (th["grout"][0]+6,th["grout"][1]+6,th["grout"][2]+6),
                        False, apt, 1)
        elif v == "mossy":
            mr = random.Random(c*200+r+self.floor_num)
            for _ in range(4):
                mx2 = rx+mr.randint(4,TILE_SIZE-5)
                my2 = ry+mr.randint(4,TILE_SIZE-5)
                ms = pygame.Surface((10,6),pygame.SRCALPHA)
                pygame.draw.ellipse(ms,(*th["vine_col"],110),(0,0,10,6))
                surface.blit(ms,(mx2-5,my2-3))
        elif v == "inlay":
            cx2,cy2 = rx+TILE_SIZE//2, ry+TILE_SIZE//2
            dm = TILE_SIZE//3
            il = pygame.Surface((TILE_SIZE,TILE_SIZE),pygame.SRCALPHA)
            pts = [(TILE_SIZE//2,TILE_SIZE//2-dm),(TILE_SIZE//2+dm,TILE_SIZE//2),
                   (TILE_SIZE//2,TILE_SIZE//2+dm),(TILE_SIZE//2-dm,TILE_SIZE//2)]
            tc2 = (th["floor_alt"][0]+12,th["floor_alt"][1]+12,th["floor_alt"][2]+12)
            pygame.draw.polygon(il,(*tc2,90),pts)
            pygame.draw.polygon(il,(200,180,150,35),pts,1)
            surface.blit(il,(rx,ry))
        elif v == "blood":
            br = random.Random(c*300+r)
            for _ in range(4):
                bx2 = rx+br.randint(4,TILE_SIZE-5)
                by2 = ry+br.randint(4,TILE_SIZE-5)
                bs = pygame.Surface((14,9),pygame.SRCALPHA)
                pygame.draw.ellipse(bs,(155,18,18,95),(0,0,14,9))
                surface.blit(bs,(bx2-7,by2-4))
        elif v == "stained":
            sr2 = random.Random(c*400+r+self.floor_num)
            sx2 = rx+sr2.randint(6,TILE_SIZE-10)
            sy2 = ry+sr2.randint(6,TILE_SIZE-10)
            ss2 = pygame.Surface((16,12),pygame.SRCALPHA)
            pygame.draw.ellipse(ss2,(0,0,0,55),(0,0,16,12))
            surface.blit(ss2,(sx2,sy2))

        # Corner dots
        gc = (th["grout"][0]+7, th["grout"][1]+7, th["grout"][2]+7)
        for dcx,dcy in [(2,2),(TILE_SIZE-3,2),(2,TILE_SIZE-3),(TILE_SIZE-3,TILE_SIZE-3)]:
            if 0 <= rx+dcx < surface.get_width() and 0 <= ry+dcy < surface.get_height():
                surface.set_at((rx+dcx,ry+dcy), gc)

        pygame.draw.rect(surface,
            (th["grout"][0]+4,th["grout"][1]+4,th["grout"][2]+4),
            (rx,ry,TILE_SIZE,TILE_SIZE), 1)

    def _draw_wall_tile(self, surface, c, r, th):
        rx, ry = c*TILE_SIZE, r*TILE_SIZE

        if (c,r) in self._pillars:
            # Stone pillar
            sh = pygame.Surface((TILE_SIZE,6),pygame.SRCALPHA)
            sh.fill((0,0,0,55))
            surface.blit(sh,(rx,ry+TILE_SIZE-4))
            cw2 = TILE_SIZE-14
            pygame.draw.rect(surface,th["pillar"],(rx+7,ry+6,cw2,TILE_SIZE-8),border_radius=3)
            # Left lit edge
            pygame.draw.rect(surface,th["pillar_top"],(rx+7,ry+6,3,TILE_SIZE-8))
            # Right shadow
            dc = tuple(max(0,v-8) for v in th["wall_bot"])
            pygame.draw.rect(surface,dc,(rx+7+cw2-3,ry+6,3,TILE_SIZE-8))
            # Top cap
            pygame.draw.rect(surface,th["pillar_top"],(rx+2,ry,TILE_SIZE-4,11),border_radius=2)
            pygame.draw.rect(surface,
                tuple(min(255,v+12) for v in th["pillar_top"]),
                (rx+4,ry,TILE_SIZE-8,4),border_radius=1)
            # Mid decorative band
            my = ry+TILE_SIZE//2
            pygame.draw.rect(surface,th["pillar_top"],(rx+5,my-3,TILE_SIZE-10,6),border_radius=1)
            # Bottom base
            pygame.draw.rect(surface,th["pillar_top"],(rx+2,ry+TILE_SIZE-10,TILE_SIZE-4,10),border_radius=2)
            pygame.draw.rect(surface,
                (th["wall_side"][0]+8,th["wall_side"][1]+8,th["wall_side"][2]+8),
                (rx,ry,TILE_SIZE,TILE_SIZE),1)
            return

        # Standard brick wall
        pygame.draw.rect(surface,th["wall"],(rx,ry,TILE_SIZE,TILE_SIZE))
        # Top highlight
        pygame.draw.rect(surface,th["wall_top"],(rx,ry,TILE_SIZE,4))
        # Left subtle edge
        pygame.draw.rect(surface,th["wall_side"],(rx,ry+4,2,TILE_SIZE-4))
        # Bottom shadow
        pygame.draw.rect(surface,th["wall_bot"],(rx,ry+TILE_SIZE-3,TILE_SIZE,3))
        # Right shadow
        pygame.draw.rect(surface,th["wall_bot"],(rx+TILE_SIZE-2,ry,2,TILE_SIZE))

        # Brick mortar
        g = th["grout"]
        mid = ry+TILE_SIZE//2
        pygame.draw.line(surface,g,(rx+2,mid),(rx+TILE_SIZE-2,mid),1)
        vo = (TILE_SIZE//2) if r%2==0 else 0
        vx = rx+vo
        if rx < vx < rx+TILE_SIZE:
            pygame.draw.line(surface,g,(vx,ry+2),(vx,mid-1),1)
        vx2 = rx+vo+TILE_SIZE//2
        if rx < vx2 < rx+TILE_SIZE:
            pygame.draw.line(surface,g,(vx2,mid+1),(vx2,ry+TILE_SIZE-2),1)

        pygame.draw.rect(surface,
            (th["wall_side"][0]+6,th["wall_side"][1]+6,th["wall_side"][2]+6),
            (rx,ry,TILE_SIZE,TILE_SIZE),1)

    # ══════════════════════════════════════════════════════════════════════════
    # DECORATION DRAW HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _draw_torch_glow(self, surface, torch, t, th):
        c, r = torch["c"], torch["r"]
        tc  = th["torch_col"]
        ph  = torch["phase"]
        gx  = c*TILE_SIZE+TILE_SIZE//2
        gy  = (r+1)*TILE_SIZE+TILE_SIZE//2
        fli = 0.8+0.2*math.sin(t*11+ph*2.3)
        br  = int(54+16*math.sin(t*3+ph))
        gw, gh = br*2, int(br*0.65)
        gs = pygame.Surface((gw,gh),pygame.SRCALPHA)
        for gr2 in range(br,0,-8):
            ga = int(26*fli*(gr2/br))
            grc = min(255,tc[0])
            ggc = int(tc[1]*0.65)
            gbc = int(tc[2]*0.35)
            pygame.draw.ellipse(gs,(grc,ggc,gbc,max(0,ga)),
                (int(gw//2-gr2), int(gh//2-gr2*gh//gw),
                 int(gr2*2),    int(gr2*gh*2//max(1,gw))))
        surface.blit(gs,(gx-gw//2, gy-gh//2))

    def _draw_torch_flame(self, surface, torch, t, th):
        c, r = torch["c"], torch["r"]
        tc  = th["torch_col"]
        ti  = th["torch_inner"]
        ph  = torch["phase"]
        x   = c*TILE_SIZE+TILE_SIZE//2
        y   = (r+1)*TILE_SIZE-6
        fli = math.sin(t*14+ph*3.1)

        # Bracket
        pygame.draw.rect(surface,(90,74,50),(x-6,y-6,12,6),border_radius=1)
        pygame.draw.rect(surface,(112,90,62),(x-4,y-10,8,5),border_radius=2)
        pygame.draw.ellipse(surface,(78,62,44),(x-4,y-6,8,5))
        pygame.draw.ellipse(surface,(100,80,55),(x-3,y-6,6,4))

        # Flame layers
        for fi in range(6,0,-1):
            fw = max(1,int((7-fi)*1.5+abs(fli)*2))
            fh = int(fi*3.8+abs(fli)*2)
            sw = int(fli*(fi*0.45))
            fy = y-8-fh//2-(6-fi)*2
            fx = x+sw
            frac = fi/6
            fr2 = int(tc[0]*frac+ti[0]*(1-frac))
            fg2 = int(tc[1]*frac+ti[1]*(1-frac))
            fb2 = int(tc[2]*frac+ti[2]*(1-frac))
            fa  = int(225*(fi/6))
            fs  = pygame.Surface((fw*2+4,fh+4),pygame.SRCALPHA)
            pts = [(fw+2,2),(fw*2+2,fh+2),(fw+2,fh*2//3+2),(2,fh+2)]
            pygame.draw.polygon(fs,(fr2,fg2,fb2,fa),pts)
            surface.blit(fs,(fx-fw-2,fy))

        # Bright core
        ca = int(240+12*math.sin(t*22+ph))
        cs = pygame.Surface((6,6),pygame.SRCALPHA)
        pygame.draw.circle(cs,(255,255,220,ca),(3,3),3)
        surface.blit(cs,(x-3,y-14))

        # Smoke wisps
        for wi in range(2):
            wp = ph+wi*1.6
            wx2 = x+int(3*math.sin(t*2.4+wp))
            wy2 = y-16-int((t*14+wp*9)%20)
            wa  = int(28+18*math.sin(t*2.1+wp))
            ws  = pygame.Surface((8,8),pygame.SRCALPHA)
            pygame.draw.circle(ws,(38,36,44,wa),(4,4),4)
            surface.blit(ws,(wx2-4,wy2-4))

    def _draw_vine(self, surface, vine, t, th):
        c, r = vine["c"], vine["r"]
        vc = th["vine_col"]
        lc = th["vine_leaf"]
        y_start = (r+1)*TILE_SIZE
        for si in range(vine["strands"]):
            ox = vine["offsets"][si%len(vine["offsets"])]
            ph = vine["phases"][si%len(vine["phases"])]
            xs = c*TILE_SIZE+TILE_SIZE//2+ox
            total = vine["length"]*TILE_SIZE//5+6
            px2, py2 = xs, y_start
            for sj in range(total):
                sw  = int(5*math.sin(t*1.1+ph+sj*0.55))
                sx2 = xs+sw
                sy2 = y_start+sj*5
                a   = max(0, 200-sj*(200//(total+1)))
                if a <= 0: break
                vs = pygame.Surface((5,5),pygame.SRCALPHA)
                pygame.draw.circle(vs,(*vc,a),(2,2),2)
                surface.blit(vs,(sx2-2,sy2-2))
                if sj > 0:
                    pygame.draw.line(surface,(*vc,min(a+18,200)),(px2,py2),(sx2,sy2),2)
                if sj > 1 and sj%3==0 and a > 55:
                    ls2 = 1 if sj%6<3 else -1
                    lx2 = sx2+ls2*8+int(2*math.sin(t*1.3+ph+sj))
                    ly2 = sy2-2
                    lav = min(175,a)
                    ls3 = pygame.Surface((14,9),pygame.SRCALPHA)
                    pygame.draw.ellipse(ls3,(*lc,lav),(0,0,14,9))
                    pygame.draw.line(ls3,(*vc,min(255,lav+40)),(0,4),(14,4),1)
                    surface.blit(ls3,(lx2-7,ly2-4))
                px2, py2 = sx2, sy2

    def _draw_crystal(self, surface, crystal, t):
        c, r = crystal["c"], crystal["r"]
        col  = crystal["color"]
        sz   = crystal["size"]
        ph   = crystal["phase"]
        side = crystal["side"]
        rx, ry = c*TILE_SIZE, r*TILE_SIZE
        if side == "top":   x,y = rx+TILE_SIZE//2, ry+5
        elif side == "left": x,y = rx+5, ry+TILE_SIZE//2
        else:                x,y = rx+TILE_SIZE-5, ry+TILE_SIZE//2

        gr = int(sz*2.5+4*math.sin(t*2+ph))
        ga = int(34+18*math.sin(t*2.5+ph))
        gs = pygame.Surface((gr*2,gr*2),pygame.SRCALPHA)
        pygame.draw.circle(gs,(*col,ga),(gr,gr),gr)
        surface.blit(gs,(x-gr,y-gr))

        pulse = 1+0.08*math.sin(t*2.5+ph)
        pts = []
        for i in range(6):
            a = i*math.pi*2/6-math.pi/6
            pts.append((x+int(math.cos(a)*sz*pulse), y+int(math.sin(a)*sz*pulse)))
        dc = tuple(max(0,v//2) for v in col)
        pygame.draw.polygon(surface,dc,pts)
        pygame.draw.polygon(surface,col,pts,1)
        if sz >= 5:
            in_pts = [(x+int(math.cos(i*math.pi*2/3-math.pi/6)*sz*0.5*pulse),
                       y+int(math.sin(i*math.pi*2/3-math.pi/6)*sz*0.5*pulse))
                      for i in range(3)]
            pygame.draw.polygon(surface,tuple(min(255,v+60) for v in col),in_pts,1)
        pygame.draw.circle(surface,(255,255,255),(x-sz//3,y-sz//3),max(1,sz//4))

    def _draw_chain(self, surface, chain, t, th):
        x, y = chain["x"], chain["y"]
        length = chain["length"]
        links  = chain["links"]
        sw     = int(3*math.sin(t*1.2+chain["sway"]))
        col    = th["chain_col"]
        dc     = tuple(max(0,v-14) for v in col)
        lh     = max(3, length//links)
        for li in range(links):
            lx = x+sw+(1 if li%2==0 else -1)*2
            ly = y+li*lh
            pygame.draw.ellipse(surface,col,(lx-3,ly,6,lh-1))
            pygame.draw.ellipse(surface,dc,(lx-3,ly,6,lh-1),1)
            pygame.draw.line(surface,tuple(min(255,v+22) for v in col),
                             (lx-1,ly+1),(lx-1,ly+lh-2),1)

    def _draw_cobweb(self, surface, cw, t):
        x, y   = cw["x"], cw["y"]
        sz     = cw["size"]
        flip_x = cw["flip_x"]
        sw     = 0.4*math.sin(t*0.8+cw["phase"])
        if not flip_x:
            a_start, a_end = 0.0, math.pi*0.5
        else:
            a_start, a_end = math.pi*0.5, math.pi
        n_rays, n_rings = 5, 4
        for i in range(n_rays):
            frac = i/(n_rays-1) if n_rays>1 else 0
            a = a_start+frac*(a_end-a_start)+sw*0.05
            pygame.draw.line(surface,(158,152,170,62),(x,y),
                             (x+int(math.cos(a)*sz), y+int(math.sin(a)*sz)),1)
        for ri in range(1,n_rings+1):
            rf = ri/(n_rings+1)
            rpts = []
            for i in range(n_rays):
                frac = i/(n_rays-1) if n_rays>1 else 0
                a = a_start+frac*(a_end-a_start)+sw*0.05*rf
                rpts.append((x+int(math.cos(a)*sz*rf), y+int(math.sin(a)*sz*rf)))
            if len(rpts) >= 2:
                pygame.draw.lines(surface,(158,152,170,48),False,rpts,1)

    def _draw_rune(self, surface, rune, t, th):
        x, y   = rune["x"], rune["y"]
        radius = rune["radius"]
        ph     = rune["phase"]
        spokes = rune["spokes"]
        col    = th["rune_col"]
        ba     = int(24+14*math.sin(t*1.5+ph))
        spin   = t*0.4+ph
        r2     = radius+2
        rs     = pygame.Surface((r2*2,r2*2),pygame.SRCALPHA)
        cx2=cy2=r2
        pygame.draw.circle(rs,(*col,ba),(cx2,cy2),radius,1)
        pygame.draw.circle(rs,(*col,ba//2),(cx2,cy2),radius*2//3,1)
        for i in range(spokes):
            a = spin+i*math.pi*2/spokes
            ex2 = cx2+int(math.cos(a)*radius)
            ey2 = cy2+int(math.sin(a)*radius)
            pygame.draw.line(rs,(*col,ba),(cx2,cy2),(ex2,ey2),1)
        for i in range(spokes):
            a = spin+math.pi/spokes+i*math.pi*2/spokes
            px2 = cx2+int(math.cos(a)*radius)
            py2 = cy2+int(math.sin(a)*radius)
            pygame.draw.circle(rs,(*col,ba),(px2,py2),2)
        surface.blit(rs,(x-r2,y-r2))

    def _draw_rug(self, surface, deco, th):
        c, r = deco["c"], deco["r"]
        col  = deco["color"]
        rx   = c*TILE_SIZE+4
        ry   = r*TILE_SIZE+4
        rw   = TILE_SIZE-8
        rh   = TILE_SIZE-8
        rs   = pygame.Surface((rw,rh),pygame.SRCALPHA)
        rs.fill((*col,115))
        bc2 = tuple(min(255,v+44) for v in col)
        pygame.draw.rect(rs,(*bc2,148),(0,0,rw,rh),2,border_radius=3)
        pygame.draw.rect(rs,(*bc2,76),(4,4,rw-8,rh-8),1,border_radius=2)
        if rw >= 32 and rh >= 32:
            dm = min(rw,rh)//3
            dcx,dcy = rw//2,rh//2
            pts = [(dcx,dcy-dm),(dcx+dm,dcy),(dcx,dcy+dm),(dcx-dm,dcy)]
            pygame.draw.polygon(rs,(*bc2,95),pts)
            pygame.draw.polygon(rs,(*bc2,148),pts,1)
        surface.blit(rs,(rx,ry))

    def _draw_puddle(self, surface, deco, t):
        x, y = deco["x"], deco["y"]
        rx2, ry2 = deco["rx"], deco["ry"]
        ph  = deco["phase"]
        rip = 0.8+0.2*math.sin(t*1.5+ph)
        ps  = pygame.Surface((rx2*2+4,ry2*2+4),pygame.SRCALPHA)
        pygame.draw.ellipse(ps,(11,13,25,142),(2,2,rx2*2,ry2*2))
        rfw = max(2,int(rx2*0.7))
        rfh = max(1,ry2//2)
        pygame.draw.ellipse(ps,(48,58,88,int(52*rip)),(rx2-rfw//2+2,4,rfw,rfh))
        pygame.draw.ellipse(ps,(58,68,98,28),(2,2,rx2*2,ry2*2),1)
        for ri in range(1,3):
            rf = ri/3
            ra = int(22*max(0,1-rf))
            ew = int(rx2*2*(1-rf*0.5))
            eh = int(ry2*2*(1-rf*0.5))
            if ew>0 and eh>0:
                pygame.draw.ellipse(ps,(52,62,98,ra),
                    (int(2+rx2*rf*0.5),int(2+ry2*rf*0.5),ew,eh),1)
        surface.blit(ps,(x-rx2-2,y-ry2-2))

    def _draw_bones(self, surface, deco):
        x, y    = deco["x"], deco["y"]
        angle   = deco["angle"]
        scale   = deco["scale"]
        variant = deco["variant"]
        bc2 = (192,188,180)
        bcs = (155,150,142)
        if variant == 0:
            L = int(14*scale)
            dx2 = int(math.cos(angle)*L); dy2 = int(math.sin(angle)*L)
            pygame.draw.line(surface,bcs,(x,y),(x+dx2,y+dy2),max(1,int(2*scale)))
            for ex3,ey3 in [(x,y),(x+dx2,y+dy2)]:
                pygame.draw.circle(surface,bc2,(ex3,ey3),max(2,int(3*scale)))
        elif variant == 1:
            for da in [angle,angle+math.pi*0.5]:
                L = int(12*scale)
                dx2 = int(math.cos(da)*L); dy2 = int(math.sin(da)*L)
                pygame.draw.line(surface,bcs,(x-dx2,y-dy2),(x+dx2,y+dy2),max(1,int(2*scale)))
                for ex3,ey3 in [(x-dx2,y-dy2),(x+dx2,y+dy2)]:
                    pygame.draw.circle(surface,bc2,(ex3,ey3),max(1,int(2*scale)))
        else:
            sr = max(4,int(6*scale))
            pygame.draw.circle(surface,bcs,(x,y),sr)
            pygame.draw.circle(surface,bc2,(x,y-1),sr-1)
            pygame.draw.circle(surface,(24,17,13),(x-2,y-1),max(1,sr//3))
            pygame.draw.circle(surface,(24,17,13),(x+2,y-1),max(1,sr//3))
            pygame.draw.rect(surface,bc2,(x-sr+2,y+sr-4,sr*2-4,max(1,sr//2)))
            for ti in range(3):
                tx2 = x-sr+3+ti*max(1,(sr*2-6)//2)
                pygame.draw.rect(surface,(24,17,13),(tx2,y+sr-4,max(1,(sr*2-6)//4),sr//3))

    def _draw_candle(self, surface, deco, t, th):
        x, y = deco["x"], deco["y"]
        ph   = deco["phase"]
        tc   = th["torch_col"]
        ti   = th["torch_inner"]
        fli  = math.sin(t*9+ph)
        # Wax puddle
        pd = pygame.Surface((10,6),pygame.SRCALPHA)
        pygame.draw.ellipse(pd,(226,218,204,118),(0,0,10,6))
        surface.blit(pd,(x-5,y+7))
        # Body
        pygame.draw.rect(surface,(228,220,206),(x-3,y-12,6,18),border_radius=1)
        pygame.draw.rect(surface,(205,198,185),(x+1,y-12,2,18),border_radius=1)
        pygame.draw.rect(surface,(215,208,195),(x-2,y-12,1,4))
        # Wick
        pygame.draw.line(surface,(54,37,17),(x,y-12),(x+int(fli*1.5),y-15),1)
        # Flame
        for fi in range(4,0,-1):
            fh = int(5+fi*1.5+abs(fli)*2)
            fw = max(1,4-fi+int(abs(fli)))
            sx2 = x+int(fli*(fi*0.4))
            fy  = y-13-fh+fi
            frac = fi/4
            fc_r = int(tc[0]*frac+ti[0]*(1-frac))
            fc_g = int(tc[1]*frac+ti[1]*(1-frac))
            fa   = int(188*(fi/4))
            fs   = pygame.Surface((fw*2+2,fh+2),pygame.SRCALPHA)
            pts2 = [(fw+1,1),(fw*2+1,fh+1),(fw+1,fh*2//3+1),(1,fh+1)]
            pygame.draw.polygon(fs,(fc_r,fc_g,0,fa),pts2)
            surface.blit(fs,(sx2-fw-1,fy))
        # Glow
        gl = int(14+5*abs(fli))
        gls = pygame.Surface((gl*2,int(gl*0.65)),pygame.SRCALPHA)
        ga  = int(17+7*abs(fli))
        pygame.draw.ellipse(gls,(*tc,ga),(0,0,gl*2,int(gl*0.65)))
        surface.blit(gls,(x-gl,y-16))

    def _draw_item(self, surface, item, t):
        bob = int(4 * math.sin(t * 2.5 + item.x * 0.03 + item.y * 0.02))
        ix  = item.x
        iy  = item.y + bob
        rc  = _RARITY_COL.get(item.rarity, (200, 200, 200))
        ga  = _RARITY_GLOW.get(item.rarity, 22)

        # Soft outer glow halo (rarity-coloured)
        gr = int(18 + 6 * math.sin(t * 2.0 + item.y * 0.04))
        glo = pygame.Surface((gr * 2 + 2, gr * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(glo, (*rc, ga), (gr + 1, gr + 1), gr)
        surface.blit(glo, (ix - gr - 1, iy - gr - 1))

        # Pulsing rarity ring
        ring_r = int(14 + 3 * math.sin(t * 2.2 + item.x * 0.05))
        ring_a = int(120 + 60 * math.sin(t * 2.2 + item.x * 0.05))
        rs = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(rs, (*rc, ring_a), (ring_r + 2, ring_r + 2), ring_r, 1)
        surface.blit(rs, (ix - ring_r - 2, iy - ring_r - 2))

        # Drop shadow on floor
        sh = pygame.Surface((22, 7), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 50), (0, 0, 22, 7))
        surface.blit(sh, (ix - 11, item.y + 12))

        # Item image centred on the drop point
        img = _ITEM_IMAGES.get(item.type)
        if img:
            surface.blit(img, (ix - 9, iy - 9))

        # Bright centre sparkle
        pulse_a = int(180 + 60 * math.sin(t * 3.5 + item.x * 0.1))
        sps = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(sps, (255, 255, 255, pulse_a), (3, 3), 2)
        surface.blit(sps, (ix - 3, iy - 3))

        # Legendary orbiting sparkles
        if item.rarity == "legendary":
            for sp_i in range(6):
                spa = t * 2.2 + sp_i * math.pi * 2 / 6
                spr = int(20 + 4 * math.sin(t * 3 + sp_i))
                spx = ix + int(math.cos(spa) * spr)
                spy = iy + int(math.sin(spa) * spr * 0.55)
                al  = int(140 + 80 * math.sin(t * 4 + sp_i))
                ss2 = pygame.Surface((6, 6), pygame.SRCALPHA)
                pygame.draw.circle(ss2, (255, 225, 70, al), (3, 3), 2)
                surface.blit(ss2, (spx - 3, spy - 3))
