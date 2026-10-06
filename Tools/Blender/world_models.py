"""
MultiBash world pass 2: landmarks, interactables and the Frostfall Peaks set + its enemies.

Builds on the helpers in generate_models.py (palette UVs, part/group/root_with, joints for the procedural rig).

Run headless (all, or only the named models after --):
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools/Blender/world_models.py -- Keep Windmill
"""
import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_models as gm  # noqa: E402

part, group, root_with, soft, skin, rock_chunk, eye, bone = gm.part, gm.group, gm.root_with, gm.soft, gm.skin, gm.rock_chunk, gm.eye, gm.bone
JOINTS = gm.JOINTS


def r2(x, y, deg):
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def ring_parts(n, radius, z, size, color, kind="cube", skip=0.0, jitter=0.0, seed=0, verts=6):
    random.seed(seed)
    out = []
    for i in range(n):
        if random.random() < skip:
            continue
        a = i / n * 360
        x, y = r2(radius, 0, a)
        h = size[2] * (1 + random.uniform(-jitter, jitter))
        out.append(part(kind, (x, y, z + h / 2), (size[0], size[1], h), color, rot=(0, 0, a), verts=verts))
    return out


def tube(points, color, subdiv=1, smooth=True):
    return skin(points, color, subdiv=subdiv, smooth=smooth)


# ============================================================================ HAUNTED KEEP

def keep():
    """The ruined keep: a huge broken castle block with corner turrets, lit windows, a gate and banners. Landmark (~17m)."""
    random.seed(101)
    W, H = 9.0, 11.0
    ps = [part("cube", (0, 0, H / 2), (W, W, H), "brick"),
          part("cube", (0, 0, 0.6), (W + 1.0, W + 1.0, 1.2), "brick_dark"),
          part("cube", (0, 0, H * 0.5), (W + 0.3, W + 0.3, 0.35), "brick_dark"),
          part("cube", (0, 0, H - 0.2), (W + 0.4, W + 0.4, 0.4), "brick_dark")]
    # broken upper storey: four wall slabs of different height (one corner collapsed)
    tops = [3.4, 2.2, 3.0, 0.6]
    for s in range(4):
        h = tops[s]
        x, y = r2(0, W / 2 - 0.4, s * 90)
        ps.append(part("cube", (x, y, H + h / 2), (W, 0.8, h) if s % 2 == 0 else (0.8, W, h), "brick"))
        for k in range(5):
            if random.random() < 0.3:
                continue
            t = -W / 2 + 0.9 + k * (W - 1.8) / 4
            cx, cy = r2(t, W / 2 - 0.4, s * 90)
            ch = random.uniform(0.6, 1.0)
            ps.append(part("cube", (cx, cy, H + h + ch / 2), (0.9, 0.9, ch), "brick"))
    # rubble where the corner fell
    for i in range(7):
        ps.append(part("cube", (random.uniform(-6, -3), random.uniform(3, 6.5), random.uniform(0.2, 0.6)),
                       (random.uniform(0.6, 1.4),) * 2 + (random.uniform(0.4, 0.9),), "brick_dark", rot=(random.uniform(-20, 20), 0, random.uniform(0, 90))))
    # corner turrets
    for s, (cx, cy) in enumerate(((W / 2, W / 2), (-W / 2, W / 2), (-W / 2, -W / 2), (W / 2, -W / 2))):
        th = H + (4.5 if s != 1 else 1.0)
        ps.append(part("cyl", (cx, cy, th / 2), (2.6, 2.6, th), "brick", verts=10))
        ps.append(part("cyl", (cx, cy, th - 0.3), (3.0, 3.0, 0.5), "brick_dark", verts=10))
        if s in (0, 2):
            ps.append(part("cone", (cx, cy, th + 1.6), (3.2, 3.2, 3.2), "roof", verts=10))
            ps.append(part("cube", (cx, cy, th + 3.7), (0.06, 0.06, 1.2), "dark_iron"))
            ps.append(part("cube", (cx + 0.35, cy, th + 4.0), (0.7, 0.04, 0.4), "banner_red"))
        else:
            for k in range(6):
                a = k * 60
                x, y = r2(1.15, 0, a)
                ps.append(part("cube", (cx + x, cy + y, th + 0.4), (0.6, 0.5, 0.8), "brick", rot=(0, 0, a)))
        sx, sy = (1 if cx > 0 else -1), (1 if cy > 0 else -1)
        for z in (4.0, 8.5):
            ps.append(part("cube", (cx + sx * 0.93, cy + sy * 0.93, z), (0.35, 0.12, 0.8), "lantern_glow", rot=(0, 0, 45 * sx * sy)))
    # front face (-Y): gate, glowing windows, banners, ivy
    f = -W / 2 - 0.05
    ps += [part("cube", (0, f, 1.9), (2.6, 0.3, 3.4), "black"),
           part("cyl", (0, f, 3.55), (2.6, 0.3, 2.6), "black", rot=(90, 0, 0), verts=12),
           part("cube", (-1.25, f - 0.6, 1.8), (1.2, 0.12, 3.2), "wood_dark", rot=(0, 0, -35)),
           part("cube", (0, f - 0.05, 5.2), (3.6, 0.25, 0.4), "brick_dark")]
    for x in (-3, 3):
        ps.append(part("cube", (x, f - 0.08, 7.6), (0.7, 0.1, 1.3), "lantern_glow"))
        ps.append(part("cube", (x, f - 0.06, 7.6), (0.95, 0.06, 1.55), "brick_dark"))
        ps.append(part("cube", (x * 0.62, f - 0.12, 7.0), (1.0, 0.05, 3.6), "banner_red"))
        ps.append(part("cube", (x * 0.62, f - 0.14, 7.9), (0.4, 0.03, 0.4), "gold"))
    for z in (4.0, 8.0):
        for x in (-2.2, 2.2):
            ps.append(part("cube", (W / 2 + 0.06, x, z), (0.1, 0.5, 1.0), "lantern_glow" if random.random() < 0.6 else "black"))
            ps.append(part("cube", (-W / 2 - 0.06, x, z), (0.1, 0.5, 1.0), "black"))
    for i in range(14):
        s = random.randint(0, 3)
        t = random.uniform(-W / 2 + 1, W / 2 - 1)
        z = random.uniform(1.2, H - 1.5)
        x, y = r2(t, -W / 2 - 0.04, s * 90)
        ps.append(part("cube", (x, y, z), (random.uniform(0.8, 1.8), 0.08, random.uniform(1.2, 3.2)), "ivy", rot=(0, 0, s * 90)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def mausoleum():
    """Stone crypt with columns, a pediment, a glowing purple doorway and an angel on top."""
    ps = [part("cube", (0, 0, 0.2), (6.2, 7.2, 0.4), "stone_dark"),
          part("cube", (0, -0.2, 0.55), (5.6, 6.6, 0.3), "stone_light"),
          part("cube", (0, 0.6, 2.4), (4.6, 4.6, 3.4), "stone"),
          part("cube", (0, -0.4, 4.25), (5.4, 6.4, 0.4), "stone_light"),
          part("cyl", (0, -0.4, 4.95), (5.4, 1.4, 6.4), "stone", rot=(90, 0, 0), verts=3),
          part("cube", (0, -1.74, 2.0), (1.6, 0.12, 2.5), "witch_purple"),
          part("cube", (0, -1.78, 2.0), (1.1, 0.06, 2.0), "purple_glow"),
          part("cube", (0, -1.8, 3.4), (2.0, 0.3, 0.3), "stone_dark"),
          part("cube", (0, -3.3, 0.85), (1.8, 0.6, 0.3), "stone_light"),
          part("cube", (0, -3.7, 0.55), (2.0, 0.6, 0.3), "stone_light")]
    for x in (-2.2, -1.1, 1.1, 2.2):
        ps.append(part("cyl", (x, -2.9, 2.4), (0.5, 0.5, 3.4), "stone_light", verts=8))
        ps.append(part("cube", (x, -2.9, 0.85), (0.7, 0.7, 0.3), "stone"))
        ps.append(part("cube", (x, -2.9, 3.95), (0.7, 0.7, 0.2), "stone"))
    # angel statue on top
    ps += [part("cone", (0, -0.4, 6.4), (0.9, 0.7, 1.6), "stone_light", verts=8, r2=0.3),
           part("ico", (0, -0.4, 7.4), (0.45, 0.45, 0.5), "stone_light", sub=1),
           part("cube", (-0.6, -0.1, 6.9), (0.9, 0.12, 1.3), "stone", rot=(0, 25, 20)),
           part("cube", (0.6, -0.1, 6.9), (0.9, 0.12, 1.3), "stone", rot=(0, -25, -20)),
           part("torus", (0, -0.4, 7.8), (0.5, 0.5, 0.5), "moonstone", verts=10)]
    # urns with candles and moss
    for x in (-2.6, 2.6):
        ps.append(part("cyl", (x, -3.3, 0.75), (0.4, 0.4, 0.5), "stone_dark", verts=8))
        ps.append(part("cube", (x, -3.3, 1.1), (0.08, 0.08, 0.2), "candle"))
    ps.append(part("cube", (1.6, 1.5, 4.5), (2.0, 2.8, 0.1), "moss", rot=(0, 0, 0)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def windmill():
    """Stone windmill with a thatched cap and a separate 'Blades' part the game spins."""
    ps = [part("cone", (0, 0, 3.0), (4.4, 4.4, 6.0), "stone_light", verts=10, r2=0.36),
          part("cyl", (0, 0, 0.25), (4.8, 4.8, 0.5), "stone_dark", verts=10),
          part("cyl", (0, 0, 6.6), (3.4, 3.4, 1.4), "wood", verts=10),
          part("cone", (0, 0, 8.3), (3.9, 3.9, 2.4), "thatch", verts=10),
          part("cube", (0, -2.0, 1.2), (1.1, 0.4, 2.0), "wood_dark"),
          part("cube", (0, -2.05, 2.35), (1.3, 0.3, 0.2), "wood"),
          part("cube", (1.2, -1.45, 4.0), (0.5, 0.2, 0.7), "lantern_glow", rot=(0, 0, 40)),
          part("cube", (-1.0, -1.1, 6.6), (0.5, 0.2, 0.6), "lantern_glow", rot=(0, 0, -30)),
          part("cyl", (0, -1.9, 6.8), (0.5, 0.5, 1.4), "wood_dark", rot=(90, 0, 0), verts=8)]
    for i in range(6):   # sacks and a cart by the door
        a = random.uniform(-60, 60)
        x, y = r2(0, -3.0, a)
        ps.append(part("ico", (x, y, 0.4), (0.7, 0.6, 0.8), "rope", sub=1))
    tower = group("Mesh", ps, (0, 0, 0))
    hub = (0, -2.7, 6.8)
    bl = [part("cyl", hub, (0.8, 0.8, 0.6), "wood_dark", rot=(90, 0, 0), verts=8)]
    for k in range(4):
        a = k * 90 + 20
        for d, w in ((2.6, 0.22),):
            x, z = r2(0, d, a)
            bl.append(part("cube", (hub[0] + x, hub[1] - 0.15, hub[2] + z), (w, 0.12, 5.2), "wood", rot=(0, -a, 0)))
            sx, sz = r2(0.55, 3.0, a)
            bl.append(part("cube", (hub[0] + sx, hub[1] - 0.2, hub[2] + sz), (0.9, 0.05, 3.6), "cloth_white", rot=(0, -a, 0)))
    blades = group("Blades", bl, hub)
    root = gm.empty("Root", (0, 0, 0))
    gm.parent(tower, root)
    gm.parent(blades, root)


def bridge():
    """Wooden footbridge over the brook (walkable deck)."""
    ps = []
    n = 9
    for i in range(n):
        t = i / (n - 1) * 2 - 1
        z = 0.75 * (1 - t * t) + 0.25
        ps.append(part("cube", (0, t * 4.0, z), (2.6, 0.9, 0.18), "wood" if i % 2 else "wood_light", rot=(math.degrees(math.atan(-1.5 * t * 0.5)) * 0.6, 0, 0)))
    for x in (-1.3, 1.3):
        for i in range(5):
            t = i / 4 * 2 - 1
            z = 0.75 * (1 - t * t) + 0.25
            ps.append(part("cube", (x, t * 4.0, z + 0.5), (0.16, 0.16, 1.1), "wood_dark"))
        for i in range(4):
            t0, t1 = i / 4 * 2 - 1, (i + 1) / 4 * 2 - 1
            z0, z1 = 0.75 * (1 - t0 * t0) + 1.0, 0.75 * (1 - t1 * t1) + 1.0
            ln = math.hypot((t1 - t0) * 4, z1 - z0)
            ps.append(part("cube", (x, (t0 + t1) * 2, (z0 + z1) / 2), (0.1, ln, 0.1), "wood_dark",
                           rot=(math.degrees(math.atan2(z1 - z0, (t1 - t0) * 4)), 0, 0)))
    ps.append(part("cube", (1.3, -4.0, 1.75), (0.22, 0.22, 0.3), "lantern_glow"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def hanging_tree():
    """Giant gnarled dead tree hung with glowing lanterns (graveyard landmark, ~11m)."""
    random.seed(55)
    ps = [tube([((0, 0, -0.5), (1.5, 1.4)), ((0.3, 0.2, 2.0), (1.0, 0.95)), ((-0.2, 0.1, 4.5), (0.8, 0.75)), ((0.4, -0.2, 6.5), (0.6, 0.55))], "bark")]
    for k in range(5):   # roots
        a = k * 72 + random.uniform(-15, 15)
        x, y = r2(2.4, 0, a)
        ps.append(tube([((0, 0, 0.6), (0.6, 0.5)), ((x * 0.6, y * 0.6, 0.3), (0.4, 0.35)), ((x, y, -0.2), (0.2, 0.2))], "bark"))
    tips = []
    for k in range(6):
        a = k * 60 + random.uniform(-20, 20)
        z0 = random.uniform(4.0, 6.0)
        L = random.uniform(3.5, 5.5)
        x1, y1 = r2(L * 0.5, 0, a)
        x2, y2 = r2(L, 0, a + random.uniform(-25, 25))
        ps.append(tube([((0, 0, z0), (0.45, 0.4)), ((x1, y1, z0 + 1.5), (0.28, 0.26)), ((x2, y2, z0 + 1.2 + random.uniform(-0.5, 1.5)), (0.1, 0.1))], "wood_dark"))
        tips.append((x1 * 1.2, y1 * 1.2, z0 + 1.5))
    for (x, y, z) in tips:
        ln = random.uniform(1.0, 2.0)
        ps.append(part("cube", (x, y, z - ln / 2), (0.04, 0.04, ln), "rope"))
        ps.append(part("cube", (x, y, z - ln - 0.25), (0.42, 0.42, 0.5), "dark_iron"))
        ps.append(part("cube", (x, y, z - ln - 0.25), (0.32, 0.44, 0.36), "lantern_glow"))
        ps.append(part("cone", (x, y, z - ln + 0.08), (0.5, 0.5, 0.2), "dark_iron", verts=4, rot=(0, 0, 45)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def bounce_shroom():
    """Bouncy giant mushroom (jump pad): wide low cap with white spots."""
    random.seed(8)
    ps = [part("cyl", (0, 0, 0.35), (1.0, 1.0, 0.7), "mushroom_stem", verts=10),
          soft("ico", (0, 0, 0.8), (3.0, 3.0, 0.9), "mushroom_red", sub=2),
          soft("cyl", (0, 0, 0.55), (2.7, 2.7, 0.15), "mushroom_stem", verts=14)]
    for k in range(9):
        a = k * 40 + random.uniform(-10, 10)
        d = random.uniform(0.4, 1.15)
        x, y = r2(d, 0, a)
        z = 0.8 + 0.42 * math.sqrt(max(0, 1 - (d / 1.5) ** 2))
        ps.append(soft("ico", (x, y, z), (0.36, 0.36, 0.1), "cloth_white", sub=1))
    for k in range(4):
        a = k * 90 + 30
        x, y = r2(1.7, 0, a)
        ps.append(soft("ico", (x, y, 0.15), (0.4, 0.4, 0.3), "mushroom_stem", sub=1))
    root_with([group("Mesh", ps, (0, 0, 0))])


def knight_statue():
    """Huge kneeling stone knight, hands on a sword planted in the plinth (~7m)."""
    ps = [part("cube", (0, 0, 0.6), (4.2, 4.2, 1.2), "stone_dark"),
          part("cube", (0, 0, 1.35), (3.6, 3.6, 0.3), "stone"),
          # kneeling legs
          part("cube", (-0.7, 0.4, 2.0), (0.9, 2.2, 0.9), "stone_light"),
          part("cube", (0.7, -0.3, 2.3), (0.9, 1.0, 1.6), "stone_light"),
          part("cube", (0.7, -0.9, 1.7), (0.9, 1.2, 0.5), "stone_light"),
          # torso, belt, shoulders
          part("cube", (0, 0.4, 3.6), (2.0, 1.2, 2.2), "stone_light"),
          part("cube", (0, 0.4, 2.55), (2.1, 1.25, 0.3), "stone_dark"),
          soft("ico", (-1.25, 0.4, 4.5), (1.0, 1.1, 0.8), "stone", sub=1),
          soft("ico", (1.25, 0.4, 4.5), (1.0, 1.1, 0.8), "stone", sub=1),
          # helmet head bowed
          part("cube", (0, 0.1, 5.2), (0.9, 1.0, 1.1), "stone_light", rot=(15, 0, 0)),
          part("cube", (0, -0.42, 5.2), (0.7, 0.05, 0.12), "black", rot=(15, 0, 0)),
          part("cone", (0, 0.3, 5.95), (0.2, 0.9, 0.6), "stone", verts=4),
          # arms down to the hilt
          part("cube", (-0.85, -0.3, 3.9), (0.6, 1.6, 0.6), "stone_light", rot=(-40, 0, 10)),
          part("cube", (0.85, -0.3, 3.9), (0.6, 1.6, 0.6), "stone_light", rot=(-40, 0, -10)),
          part("cube", (0, -1.05, 3.4), (0.8, 0.6, 0.6), "stone"),
          # sword
          part("cube", (0, -1.05, 4.2), (0.25, 0.25, 1.0), "stone_dark"),
          part("cube", (0, -1.05, 3.65), (1.8, 0.3, 0.25), "stone_dark"),
          part("cube", (0, -1.05, 2.2), (0.5, 0.14, 2.8), "steel"),
          part("ico", (0, -1.05, 4.8), (0.35, 0.35, 0.35), "rune_blue", sub=1),
          part("cube", (1.0, 0.8, 4.1), (1.6, 0.1, 1.6), "moss", rot=(0, 0, 20)),
          part("cube", (-1.6, -1.6, 1.25), (1.4, 1.0, 0.12), "moss")]
    root_with([group("Mesh", ps, (0, 0, 0))])


def well():
    ps = [part("cyl", (0, 0, 0.5), (2.0, 2.0, 1.0), "stone", verts=10),
          part("cyl", (0, 0, 1.0), (2.2, 2.2, 0.15), "stone_dark", verts=10),
          part("cyl", (0, 0, 0.95), (1.5, 1.5, 0.12), "water", verts=10),
          part("cube", (-0.95, 0, 1.6), (0.18, 0.18, 2.0), "wood_dark"),
          part("cube", (0.95, 0, 1.6), (0.18, 0.18, 2.0), "wood_dark"),
          part("cyl", (0, 0, 2.2), (0.15, 0.15, 2.0), "wood", rot=(0, 90, 0), verts=6),
          part("cyl", (0, 0, 2.85), (1.2, 2.6, 1.0), "roof", rot=(0, 90, 0), verts=3),
          part("cube", (0, 0, 1.5), (0.04, 0.04, 1.3), "rope"),
          part("cyl", (0, 0, 1.25), (0.3, 0.3, 0.35), "wood", verts=6)]
    root_with([group("Mesh", ps, (0, 0, 0))])


# ---- breakables (the game swaps them for debris when smashed)

def pumpkin():
    random.seed(3)
    ps = []
    for k in range(7):
        x, y = r2(0.18, 0, k * 51)
        ps.append(soft("ico", (x, y, 0.36), (0.42, 0.42, 0.62), "pumpkin" if k % 2 else "pumpkin_dark", sub=2))
    ps += [part("cyl", (0, 0, 0.72), (0.1, 0.1, 0.22), "leaf_dark", verts=5, rot=(10, 0, 0)),
           part("cube", (-0.12, -0.38, 0.45), (0.12, 0.05, 0.1), "candle", rot=(0, 20, 0)),
           part("cube", (0.12, -0.38, 0.45), (0.12, 0.05, 0.1), "candle", rot=(0, -20, 0)),
           part("cube", (0, -0.39, 0.28), (0.3, 0.05, 0.07), "candle")]
    root_with([group("Mesh", ps, (0, 0, 0))])


def supply_crate():
    """Wooden supply crate with iron corner bands and a stencilled lid (breakable)."""
    ps = [part("cube", (0, 0, 0.42), (0.84, 0.84, 0.84), "crate"),
          part("cube", (0, 0, 0.86), (0.88, 0.88, 0.06), "wood_dark")]
    for x in (-1, 1):
        for y in (-1, 1):
            ps.append(part("cube", (0.41 * x, 0.41 * y, 0.42), (0.1, 0.1, 0.86), "dark_iron"))
    for s_ in (-1, 1):
        ps.append(part("cube", (0, 0.425 * s_, 0.42), (0.7, 0.03, 0.1), "wood_dark", rot=(0, 45, 0)))
        ps.append(part("cube", (0.425 * s_, 0, 0.42), (0.03, 0.7, 0.1), "wood_dark", rot=(45, 0, 0)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def grain_sack():
    """Tied burlap sack slumped on the ground (breakable)."""
    ps = [soft("ico", (0, 0, 0.32), (0.72, 0.62, 0.66), "rope", sub=2),
          soft("ico", (0.04, 0.02, 0.62), (0.32, 0.3, 0.26), "rope", sub=2),
          part("cyl", (0.05, 0.02, 0.76), (0.14, 0.14, 0.08), "leather_dark", verts=8),
          soft("cone", (0.06, 0.02, 0.86), (0.2, 0.18, 0.16), "rope", verts=7, r2=0.4)]
    root_with([group("Mesh", ps, (0, 0, 0))])


def urn(body="clay", dark="clay_dark", glow=None):
    def fn():
        ps = [soft("ico", (0, 0, 0.45), (0.75, 0.75, 0.75), body, sub=2),
              part("cyl", (0, 0, 0.88), (0.36, 0.36, 0.2), dark, verts=10),
              part("cyl", (0, 0, 0.99), (0.5, 0.5, 0.08), body, verts=10),
              part("cyl", (0, 0, 0.06), (0.45, 0.45, 0.12), dark, verts=10),
              part("cyl", (0, 0, 0.52), (0.78, 0.78, 0.07), dark, verts=12)]
        if glow:
            ps.append(part("cube", (0, -0.36, 0.42), (0.06, 0.05, 0.36), glow, rot=(0, 25, 0)))
            ps.append(part("cube", (0.3, -0.2, 0.3), (0.05, 0.05, 0.28), glow, rot=(0, -30, 60)))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def barrel():
    ps = [part("cyl", (0, 0, 0.5), (0.85, 0.85, 1.0), "wood", verts=10),
          part("cyl", (0, 0, 0.5), (0.95, 0.95, 0.5), "wood_light", verts=10),
          part("cyl", (0, 0, 0.15), (0.88, 0.88, 0.07), "dark_iron", verts=10),
          part("cyl", (0, 0, 0.85), (0.88, 0.88, 0.07), "dark_iron", verts=10),
          part("cyl", (0, 0, 1.0), (0.7, 0.7, 0.04), "wood_dark", verts=10)]
    root_with([group("Mesh", ps, (0, 0, 0))])


def ice_crate():
    ps = [part("cube", (0, 0, 0.45), (0.9, 0.9, 0.9), "ice"),
          part("cube", (0, 0, 0.45), (0.6, 0.6, 0.6), "gold"),
          part("cube", (0, 0, 0.92), (0.75, 0.75, 0.08), "snow"),
          part("cube", (0.3, -0.46, 0.6), (0.2, 0.03, 0.3), "ice_glow")]
    root_with([group("Mesh", ps, (0, 0, 0))])


# ============================================================================ MOLTEN CALDERA

def dragon_skull():
    """A colossal dragon skull half sunk in the basalt; magma glows in the sockets (~14m long)."""
    ps = [soft("ico", (0, 0.5, 2.4), (5.6, 6.0, 4.0), "bone_old", sub=2),          # cranium
          soft("ico", (0, -4.2, 1.9), (3.8, 6.4, 2.4), "bone_old", sub=2),         # long snout
          soft("ico", (0, -8.0, 1.6), (2.8, 3.2, 1.8), "bone_old", sub=2),         # snout tip
          soft("ico", (0, -9.2, 2.1), (1.4, 1.2, 1.0), "bone_shadow", sub=1),
          soft("ico", (0, 2.6, 3.8), (4.6, 3.6, 1.6), "bone_shadow", sub=2),       # back crest
          soft("ico", (0, -1.6, 3.9), (4.4, 2.0, 0.7), "bone_shadow", sub=1)]      # brow ridge
    for x in (-1, 1):
        ps.append(soft("ico", (1.75 * x, -1.9, 3.15), (1.9, 1.1, 0.95), "black", sub=2, rot=(0, -18 * x, 25 * x)))   # angular sockets
        ps.append(soft("ico", (1.8 * x, -2.25, 3.1), (0.9, 0.4, 0.45), "magma", sub=1, rot=(0, -18 * x, 25 * x)))
        ps.append(soft("ico", (0.65 * x, -9.6, 2.3), (0.55, 0.4, 0.35), "black", sub=1))                             # nostrils
        # horns sweep back along the crest
        ps.append(tube([((1.9 * x, 1.0, 3.8), (0.95, 0.95)), ((2.6 * x, 4.4, 4.6), (0.7, 0.7)), ((2.5 * x, 7.8, 4.9), (0.42, 0.42)),
                        ((2.0 * x, 10.4, 4.2), (0.1, 0.1))], "yeti_horn"))
        ps.append(tube([((2.6 * x, 1.6, 2.4), (0.55, 0.55)), ((3.8 * x, 3.8, 2.6), (0.35, 0.35)), ((4.2 * x, 5.8, 2.0), (0.08, 0.08))], "yeti_horn"))
        for k in range(3):   # cheek spikes
            ps.append(part("cone", (2.5 * x, -0.5 - k * 1.3, 1.6), (0.35, 0.35, 1.0), "bone", verts=5, rot=(0, 70 * x, 0)))
        for k in range(7):   # fangs
            ps.append(part("cone", ((1.35 - 0.06 * k) * x, -3.2 - k * 0.85, 0.8), (0.34, 0.34, 1.1 if k == 1 else 0.8), "bone", verts=5, rot=(180, 0, 0)))
    ps.append(soft("ico", (0, -5.2, 0.15), (3.2, 7.2, 0.9), "bone_shadow", sub=2))   # lower jaw in the ground
    ps.append(part("cyl", (0, -2.4, 0.05), (5.6, 5.6, 0.2), "magma", verts=10))       # magma pooling under the skull
    root_with([group("Mesh", ps, (0, 0, 0))])


def dragon_ribcage():
    """Spine and arching ribs you can run through (~18m long)."""
    ps = []
    for i in range(10):
        y = -9 + i * 2.0
        z = 6.2 - 0.05 * (y ** 2) * 0.35
        ps.append(soft("ico", (0, y, z), (1.1, 1.3, 1.0), "bone_old", sub=1))
        ps.append(part("cone", (0, y, z + 0.9), (0.4, 0.8, 1.2), "bone", verts=4))
    for i in range(6):
        y = -6 + i * 2.4
        z = 6.2 - 0.05 * (y ** 2) * 0.35
        s = 1.0 - abs(y) / 14
        for x in (-1, 1):
            ps.append(tube([((0.5 * x, y, z - 0.2), (0.45, 0.45)), ((2.6 * x * s, y + 0.2, z + 0.25), (0.4, 0.4)),
                            ((4.4 * x * s, y + 0.5, z - 1.2), (0.36, 0.36)), ((5.0 * x * s, y + 0.7, z * 0.42), (0.32, 0.32)),
                            ((4.2 * x * s, y + 0.9, 0.4), (0.24, 0.24)), ((3.4 * x * s, y + 1.0, -0.4), (0.12, 0.12))], "bone_old"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def dragon_claw():
    """Giant claw bones curling out of the ground."""
    random.seed(13)
    ps = [soft("ico", (0, 0, 0.3), (4.4, 3.6, 1.6), "bone_shadow", sub=1)]
    for k in range(4):
        a = -50 + k * 33
        x, y = r2(0, -1.0, a)
        ps.append(tube([((x * 0.8, y * 0.8, 0.6), (0.7, 0.7)), ((x * 2.2, y * 2.2, 3.6), (0.55, 0.55)), ((x * 3.6, y * 3.6, 5.0), (0.32, 0.32)),
                        ((x * 4.8, y * 4.8, 4.6), (0.1, 0.1))], "bone_old"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def dwarf_forge():
    """Abandoned dwarven forge: furnace with a glowing mouth, chimney, anvil, hammer and quench trough."""
    ps = [part("cube", (0, 0, 1.6), (4.0, 3.2, 3.2), "basalt"),
          part("cube", (0, 0, 0.2), (4.6, 3.8, 0.4), "basalt_dark"),
          part("cube", (0, 0, 3.3), (4.4, 3.6, 0.3), "dark_iron"),
          part("cyl", (0, -1.62, 1.4), (1.8, 0.2, 1.8), "magma", rot=(90, 0, 0), verts=8),
          part("cyl", (0, -1.65, 1.4), (1.1, 0.2, 1.1), "magma_core", rot=(90, 0, 0), verts=8),
          part("cyl", (0, -1.6, 1.4), (2.2, 0.25, 2.2), "dark_iron", rot=(90, 0, 0), verts=8),
          part("cone", (1.0, 0.6, 5.2), (1.6, 1.6, 3.6), "basalt_dark", verts=6, r2=0.5),
          part("cyl", (1.0, 0.6, 7.1), (0.9, 0.9, 0.3), "ember", verts=6),
          # anvil
          part("cube", (-2.8, -2.4, 0.4), (0.8, 0.6, 0.8), "basalt_dark"),
          part("cube", (-2.8, -2.4, 0.95), (1.6, 0.7, 0.35), "dark_iron"),
          part("cone", (-1.75, -2.4, 0.95), (0.7, 0.5, 0.35), "dark_iron", verts=4, rot=(0, 90, 0)),
          # hammer leaning on the anvil
          part("cube", (-3.3, -2.0, 1.1), (0.12, 0.12, 1.6), "wood", rot=(0, 30, 0)),
          part("cube", (-3.7, -2.0, 1.75), (0.6, 0.35, 0.35), "iron", rot=(0, 30, 0)),
          # quench trough
          part("cube", (2.6, -2.2, 0.4), (1.6, 0.9, 0.8), "dark_iron"),
          part("cube", (2.6, -2.2, 0.75), (1.4, 0.7, 0.1), "water"),
          part("cube", (-2.0, 1.8, 0.5), (1.2, 1.0, 1.0), "crate"),
          part("ico", (-2.0, 1.8, 1.2), (0.6, 0.6, 0.5), "magma_core", sub=1)]
    root_with([group("Mesh", ps, (0, 0, 0))])


def giant_hammer():
    """A titan's warhammer driven into the rock, glowing rune bands (~8m)."""
    ps = [part("cube", (0, 0, 1.4), (3.6, 2.2, 2.4), "dark_iron", rot=(0, 8, 0)),
          part("cube", (0, 0, 1.4), (3.8, 2.4, 0.4), "rust", rot=(0, 8, 0)),
          part("cube", (0, -1.14, 1.4), (2.0, 0.05, 0.25), "magma_core", rot=(0, 8, 0)),
          part("cyl", (0.4, 0, 5.2), (0.6, 0.6, 5.6), "wood_dark", rot=(0, 8, 0), verts=8),
          part("cyl", (0.65, 0, 6.8), (0.75, 0.75, 0.3), "gold_dark", rot=(0, 8, 0), verts=8),
          part("cyl", (0.75, 0, 7.6), (0.75, 0.75, 0.3), "gold_dark", rot=(0, 8, 0), verts=8),
          part("ico", (0.85, 0, 8.3), (0.9, 0.9, 0.9), "magma", sub=1)]
    for k in range(6):
        a = k * 60
        x, y = r2(2.6, 0, a)
        ps.append(rock_chunk((x, y, 0.2), (1.4, 1.2, 0.8), "volcano_rock", 300 + k))
        ps.append(part("cube", (x * 0.7, y * 0.7, 0.05), (0.14, 1.4, 0.06), "magma", rot=(0, 0, a + 90)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def crystal_cluster(main="crystal_pink", seed=5):
    def fn():
        random.seed(seed)
        ps = [part("cyl", (0, 0, 0.15), (2.2, 2.0, 0.3), "obsidian", verts=7)]
        for k in range(7):
            a = random.uniform(0, 360)
            d = random.uniform(0, 0.7) if k else 0
            h = random.uniform(1.0, 2.0) if k else 3.0
            x, y = r2(d, 0, a)
            tilt = random.uniform(10, 30) if k else 4
            ps.append(part("cyl", (x, y, h / 2), (0.5, 0.5, h), main if k % 3 != 2 else "obsidian", verts=6, rot=(0, tilt, a)))
            tx, ty = r2(d + math.sin(math.radians(tilt)) * h / 2, 0, a)
            ps.append(part("cone", (x + (tx - x) * 0.0, y, h), (0.5, 0.5, 0.5), main, verts=6, rot=(0, tilt, a)))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def steam_vent():
    """Geyser vent (jump pad): cracked rock cone with a glowing throat."""
    ps = [part("cone", (0, 0, 0.3), (2.6, 2.6, 0.6), "volcano_rock", verts=9, r2=0.62),
          part("cyl", (0, 0, 0.6), (1.5, 1.5, 0.04), "sulfur", verts=9),
          part("cyl", (0, 0, 0.62), (1.0, 1.0, 0.04), "magma", verts=9),
          part("cyl", (0, 0, 0.64), (0.55, 0.55, 0.04), "magma_core", verts=9)]
    for k in range(5):
        a = k * 72 + 20
        x, y = r2(1.25, 0, a)
        ps.append(rock_chunk((x, y, 0.5), (0.6, 0.5, 0.5), "basalt", 40 + k))
    root_with([group("Mesh", ps, (0, 0, 0))])


def lava_fall():
    """Cascade of glowing lava down a basalt cliff (backdrop at the arena edge)."""
    random.seed(9)
    ps = [rock_chunk((0, 1.5, 4.0), (9.0, 4.0, 9.0), "basalt_dark", 61),
          rock_chunk((-3.5, 0.8, 2.0), (4.0, 3.0, 4.5), "basalt", 62),
          rock_chunk((3.6, 0.6, 2.4), (4.0, 3.0, 5.0), "basalt", 63)]
    for k in range(4):
        x = -0.9 + k * 0.6
        ps.append(part("cube", (x, -0.45, 4.0), (0.55, 0.3, 8.0), "magma" if k % 2 else "magma_core"))
    root_with([group("Mesh", ps, (0, 0, 0))])


# ============================================================================ FROSTFALL PEAKS

def snow_pine(seed, tiers=4):
    def fn():
        random.seed(seed)
        ps = [part("cyl", (0, 0, 0.9), (0.4, 0.4, 1.8), "bark", verts=6)]
        h = 1.4
        for i in range(tiers):
            r = 2.8 - i * 0.55
            ps.append(part("cone", (0, 0, h), (r, r, 1.7), "pine" if i % 2 else "pine_dark", verts=7, rot=(0, 0, random.uniform(0, 50))))
            ps.append(part("cone", (0, 0, h + 0.38), (r * 0.78, r * 0.78, 1.0), "snow", verts=7, r2=0.0, rot=(0, 0, random.uniform(0, 50))))
            h += 1.05
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def ice_spire(seed=21):
    def fn():
        random.seed(seed)
        ps = [part("cyl", (0, 0, 0.2), (2.0, 1.8, 0.4), "snow", verts=7)]
        for k in range(6):
            a = random.uniform(0, 360)
            d = random.uniform(0.2, 0.8) if k else 0
            h = random.uniform(1.6, 3.2) if k else 5.2
            x, y = r2(d, 0, a)
            tilt = random.uniform(8, 26) if k else 3
            c = "ice" if k % 2 else "ice_dark"
            ps.append(part("cone", (x, y, h / 2), (0.9 if k else 1.3, 0.9 if k else 1.3, h), c, verts=5, rot=(0, tilt, a)))
        ps.append(part("cone", (0.1, -0.15, 2.2), (0.35, 0.2, 3.0), "ice_glow", verts=4))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def snow_rock(seed, scale):
    def fn():
        o = rock_chunk((0, 0, 0.3 * scale[2]), scale, "stone_blue", seed)
        cap = gm.part("ico", (0.05 * scale[0], 0, 0.62 * scale[2]), (scale[0] * 0.8, scale[1] * 0.75, scale[2] * 0.3), "snow", sub=1)
        root_with([group("Mesh", [o, cap], (0, 0, 0))])
    return fn


def frozen_titan():
    """A giant frozen warrior, horned helm and great axe, legs locked in blocks of ice (~15m)."""
    random.seed(7)
    S = "stone_blue"
    ps = [part("cube", (0, 0, 0.5), (7.0, 7.0, 1.0), "stone_dark"),
          # legs
          part("cube", (-1.1, 0, 3.2), (1.6, 1.8, 4.6), S),
          part("cube", (1.1, 0, 3.2), (1.6, 1.8, 4.6), S),
          # kilt and belt
          part("cone", (0, 0, 5.4), (4.2, 3.2, 2.2), "fur_grey", verts=8, r2=0.7),
          part("cube", (0, 0, 6.4), (3.6, 2.4, 0.6), "dark_iron"),
          part("cube", (0, -1.22, 6.4), (0.8, 0.1, 0.5), "gold"),
          # chest
          part("cube", (0, 0, 8.4), (4.0, 2.4, 3.6), S),
          soft("ico", (0, 0.1, 10.2), (5.4, 3.0, 1.6), "fur_white", sub=2),
          soft("ico", (-2.4, 0, 10.0), (1.8, 2.0, 1.6), "stone", sub=1),
          soft("ico", (2.4, 0, 10.0), (1.8, 2.0, 1.6), "stone", sub=1),
          # head and helm
          part("cube", (0, -0.1, 11.6), (1.6, 1.6, 1.8), S),
          part("cube", (0, -0.92, 11.4), (1.2, 0.1, 0.2), "ice_glow"),
          tube([((0, -0.2, 12.8), (1.1, 1.1)), ((0, -0.1, 13.2), (0.8, 0.8))], "iron"),
          tube([((-0.9, 0, 12.8), (0.4, 0.4)), ((-2.0, 0, 13.6), (0.3, 0.3)), ((-2.3, 0, 14.8), (0.06, 0.06))], "yeti_horn"),
          tube([((0.9, 0, 12.8), (0.4, 0.4)), ((2.0, 0, 13.6), (0.3, 0.3)), ((2.3, 0, 14.8), (0.06, 0.06))], "yeti_horn"),
          part("cone", (0, -0.6, 10.4), (1.4, 0.9, 1.6), "fur_white", verts=6, rot=(180, 0, 0)),   # beard
          # arms gripping the axe in front
          part("cube", (-2.6, -0.6, 8.2), (1.2, 1.2, 3.4), S, rot=(-25, 0, 10)),
          part("cube", (2.6, -0.6, 8.2), (1.2, 1.2, 3.4), S, rot=(-25, 0, -10)),
          part("cube", (0, -2.0, 6.8), (2.4, 1.1, 1.0), S),
          # great axe, head buried in the ice
          part("cyl", (0, -2.0, 5.2), (0.4, 0.4, 7.0), "wood_dark", verts=6),
          part("cube", (0, -2.0, 2.0), (3.0, 0.3, 1.6), "iron"),
          part("cube", (0, -2.0, 2.0), (3.2, 0.2, 0.3), "steel_light")]
    # ice blocks up to the knees and around the base
    for k in range(9):
        a = k * 40 + random.uniform(-10, 10)
        x, y = r2(random.uniform(1.5, 3.2), 0, a)
        h = random.uniform(1.6, 3.6)
        ps.append(part("cube", (x, y, 1.0 + h / 2), (random.uniform(1.4, 2.2), random.uniform(1.4, 2.2), h), "ice" if k % 3 else "ice_dark",
                       rot=(random.uniform(-6, 6), random.uniform(-6, 6), a)))
    ps.append(part("cube", (0.9, -1.0, 4.0), (1.0, 0.1, 2.0), "ice_glow", rot=(0, 0, 20)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def rune_monolith(seed=3):
    def fn():
        random.seed(seed)
        h = random.uniform(3.6, 4.6)
        ps = [part("cube", (0, 0, h / 2), (1.3, 0.8, h), "stone_dark", rot=(random.uniform(-4, 4), random.uniform(-4, 4), 0)),
              part("cube", (0, 0, h + 0.05), (1.4, 0.9, 0.3), "snow"),
              part("cube", (0, 0, 0.15), (1.9, 1.4, 0.3), "snow")]
        for k in range(4):
            ps.append(part("cube", (random.uniform(-0.3, 0.3), -0.42, 0.8 + k * 0.8), (random.uniform(0.25, 0.5), 0.05, 0.12), "aurora_green" if seed % 2 else "ice_glow"))
            ps.append(part("cube", (random.uniform(-0.3, 0.3), -0.42, 1.1 + k * 0.8), (0.08, 0.05, 0.4), "aurora_green" if seed % 2 else "ice_glow"))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def longhouse():
    """Snow-buried viking longhouse ruin with crossed dragon-head gable beams."""
    L = 10.0
    ps = [part("cube", (0, 0, 1.1), (5.0, L, 2.2), "wood"),
          part("cube", (0, 0, 0.15), (5.4, L + 0.4, 0.3), "stone_blue"),
          part("cube", (0, -L / 2 - 0.02, 1.0), (1.4, 0.1, 1.8), "black"),
          part("cube", (1.4, -L / 2 - 0.03, 1.4), (0.6, 0.06, 0.5), "lantern_glow")]
    for side in (-1, 1):   # A-frame roof with snow on top
        ps.append(part("cube", (side * 1.55, 0, 3.1), (0.25, L + 0.6, 4.4), "thatch", rot=(0, -52 * side, 0)))
        ps.append(part("cube", (side * 1.62, 0, 3.2), (0.18, L + 0.6, 4.3), "snow", rot=(0, -52 * side, 0)))
    for y in (-L / 2 - 0.3, L / 2 + 0.3):   # crossed gable beams with carved heads
        for side in (-1, 1):
            ps.append(part("cube", (side * 0.55, y, 5.2), (0.22, 0.22, 2.0), "wood_dark", rot=(0, -40 * side, 0)))
            ps.append(part("cube", (side * 1.15, y, 6.0), (0.3, 0.3, 0.5), "wood_dark", rot=(0, -60 * side, 0)))
    for i in range(3):
        ps.append(part("cube", (2.6, -3 + i * 3, 0.9), (0.2, 0.9, 1.6), "wood_dark"))   # shields along the wall
        ps.append(part("cyl", (2.72, -3 + i * 3, 1.2), (0.9, 0.9, 0.08), "banner_red" if i % 2 else "banner_blue", rot=(0, 90, 0), verts=10))
    for k in range(6):
        ps.append(soft("ico", (random.uniform(-3, 3), random.uniform(-L / 2, L / 2), 0.2), (2.0, 2.0, 0.8), "snow", sub=1))
    root_with([group("Mesh", ps, (0, 0, 0))])


def tent():
    ps = [part("cyl", (0, 0, 1.0), (2.6, 3.0, 2.0), "leather_light", rot=(90, 0, 0), verts=3),
          part("cube", (0, -1.52, 0.6), (0.7, 0.05, 1.1), "leather_dark"),
          part("cube", (0, 0, 2.1), (0.12, 3.4, 0.12), "wood_dark"),
          part("cube", (0, 0.4, 1.95), (1.0, 2.0, 0.08), "snow")]
    for y in (-1.6, 1.6):
        ps.append(part("cube", (0, y, 1.1), (0.1, 0.1, 2.3), "wood_dark"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def campfire():
    ps = []
    for k in range(8):
        x, y = r2(0.7, 0, k * 45)
        ps.append(rock_chunk((x, y, 0.15), (0.35, 0.35, 0.3), "stone_blue", 70 + k))
    for k in range(4):
        ps.append(part("cyl", (0, 0, 0.25), (0.14, 0.14, 1.1), "wood_dark", rot=(0, 70, k * 45), verts=6))
    ps += [part("cone", (0, 0, 0.55), (0.6, 0.6, 0.8), "fire", verts=5),
           part("cone", (0, 0, 0.5), (0.35, 0.35, 0.6), "fire_core", verts=5)]
    root_with([group("Mesh", ps, (0, 0, 0))])


def igloo():
    ps = [soft("ico", (0, 0, 0), (4.6, 4.6, 4.0), "snow", sub=2),
          part("cyl", (0, -2.2, 0.75), (1.6, 1.6, 1.6), "snow", rot=(90, 0, 0), verts=10),
          part("cyl", (0, -3.0, 0.75), (1.0, 0.1, 1.0), "black", rot=(90, 0, 0), verts=10),
          part("cube", (0, -2.2, 0.1), (1.6, 1.6, 0.2), "snow")]
    for z in (0.6, 1.2, 1.7):   # block seams
        r = math.sqrt(max(0.1, 2.3 ** 2 - z ** 2))
        ps.append(part("cyl", (0, 0, z), (r * 2 + 0.06, r * 2 + 0.06, 0.04), "snow_shadow", verts=14))
    ps.append(part("cube", (0.6, -3.05, 1.0), (0.3, 0.05, 0.3), "lantern_glow"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def frozen_waterfall():
    """A waterfall frozen solid down a blue cliff (edge backdrop, ~12m)."""
    random.seed(17)
    ps = [rock_chunk((0, 2.0, 5.0), (12.0, 5.0, 11.0), "stone_blue", 81),
          rock_chunk((-5, 1.0, 2.4), (5.0, 4.0, 5.0), "stone_dark", 82),
          rock_chunk((5.2, 1.0, 2.8), (5.0, 4.0, 6.0), "stone_dark", 83),
          part("ico", (0, 1.5, 10.4), (10.0, 4.0, 1.6), "snow", sub=1)]
    for k in range(9):
        x = -2.4 + k * 0.6
        h = random.uniform(6.0, 9.5)
        ps.append(part("cone", (x, -0.4 + random.uniform(-0.2, 0.2), 10.0 - h / 2), (0.9, 0.6, h), "ice" if k % 2 else "ice_glow", verts=5, rot=(180, 0, 0)))
    ps.append(part("cyl", (0, -1.6, 0.1), (6.4, 3.4, 0.2), "ice", verts=12))
    root_with([group("Mesh", ps, (0, 0, 0))])


def frost_mountain(seed, w, h):
    def fn():
        random.seed(seed)
        ps = []
        for i in range(5):
            x = random.uniform(-w * 0.35, w * 0.35)
            y = random.uniform(-w * 0.15, w * 0.15)
            ph = h * random.uniform(0.55, 1.0)
            pw = w * random.uniform(0.35, 0.6)
            bpy.ops.mesh.primitive_cone_add(vertices=7, radius1=0.5, radius2=0.04, depth=1, location=(x, y, ph / 2),
                                            rotation=(0, 0, math.radians(random.uniform(0, 60))))
            o = bpy.context.active_object
            for v in o.data.vertices:
                if v.co.z > -0.45:
                    v.co.x += random.uniform(-0.08, 0.08)
                    v.co.y += random.uniform(-0.08, 0.08)
            ps.append(gm._finish(o, (pw, pw * 0.8, ph), "stone_blue" if i % 2 else "frost_blue"))
            ps.append(part("cone", (x, y, ph * 0.74), (pw * 0.36, pw * 0.3, ph * 0.54), "snow", verts=7, r2=0.02))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def ice_geyser():
    """Frost geyser (jump pad): ring of ice shards around a glowing vent."""
    ps = [part("cyl", (0, 0, 0.12), (2.6, 2.6, 0.24), "snow", verts=10),
          part("cyl", (0, 0, 0.26), (1.4, 1.4, 0.06), "ice_dark", verts=10),
          part("cyl", (0, 0, 0.3), (0.8, 0.8, 0.06), "ice_glow", verts=10)]
    for k in range(7):
        a = k * 51
        x, y = r2(1.1, 0, a)
        ps.append(part("cone", (x, y, 0.5), (0.35, 0.3, 1.0), "ice", verts=4, rot=(0, 25, a)))
    root_with([group("Mesh", ps, (0, 0, 0))])


# ============================================================================ FROST ENEMIES

def ice_wolf():
    """Fast frost wolf. Quadruped: front legs are ArmL/ArmR, hind legs LegL/LegR (the rig's trot)."""
    HZ = 0.62
    body = [soft("ico", (0, -0.12, HZ + 0.05), (0.5, 1.0, 0.48), "wolf_grey", sub=2),
            soft("ico", (0, -0.38, HZ + 0.12), (0.56, 0.6, 0.52), "fur_white", sub=2),        # shaggy chest ruff
            soft("ico", (0, 0.32, HZ + 0.02), (0.42, 0.5, 0.4), "wolf_grey", sub=2),
            soft("ico", (0, 0.0, HZ + 0.28), (0.3, 0.9, 0.12), "wolf_dark", sub=1),           # dark back stripe
            tube([((0, 0.55, HZ + 0.1), (0.1, 0.1)), ((0, 0.85, HZ + 0.22), (0.12, 0.12)), ((0, 1.1, HZ + 0.12), (0.06, 0.06))], "fur_white")]
    for k in range(4):   # ice crystals along the spine
        body.append(part("cone", (0, -0.25 + k * 0.18, HZ + 0.32), (0.08, 0.1, 0.2 - k * 0.03), "ice_glow", verts=4, rot=(-20, 0, 0)))
    Body = group("Body", body, (0, 0, HZ))
    head = [soft("ico", (0, -0.62, HZ + 0.24), (0.32, 0.36, 0.3), "wolf_grey", sub=2),
            soft("ico", (0, -0.84, HZ + 0.16), (0.18, 0.3, 0.16), "fur_grey", sub=2),          # snout
            soft("ico", (0, -0.99, HZ + 0.19), (0.07, 0.05, 0.05), "black", sub=1),
            soft("ico", (-0.08, -0.76, HZ + 0.3), (0.06, 0.03, 0.04), "ice_glow", sub=1),
            soft("ico", (0.08, -0.76, HZ + 0.3), (0.06, 0.03, 0.04), "ice_glow", sub=1),
            part("cone", (-0.1, -0.56, HZ + 0.44), (0.1, 0.06, 0.16), "wolf_dark", verts=4),
            part("cone", (0.1, -0.56, HZ + 0.44), (0.1, 0.06, 0.16), "wolf_dark", verts=4),
            part("cone", (-0.05, -0.95, HZ + 0.07), (0.03, 0.03, 0.06), "white", verts=4, rot=(180, 0, 0)),
            part("cone", (0.05, -0.95, HZ + 0.07), (0.03, 0.03, 0.06), "white", verts=4, rot=(180, 0, 0))]
    JOINTS.append(group("Head", head, (0, -0.5, HZ + 0.15)))

    def front(side):
        x = 0.14 * side
        return group("ArmR" if side < 0 else "ArmL", [tube([((x, -0.4, HZ), (0.08, 0.08)), ((x, -0.44, 0.28), (0.055, 0.055)), ((x, -0.46, 0.05), (0.05, 0.05))], "wolf_grey"),
                                                       soft("ico", (x, -0.5, 0.04), (0.11, 0.15, 0.07), "fur_grey", sub=1)], (x, -0.4, HZ))

    def hind(side):
        x = 0.15 * side
        return group("LegR" if side < 0 else "LegL", [tube([((x, 0.32, HZ), (0.1, 0.1)), ((x, 0.4, 0.32), (0.06, 0.06)), ((x, 0.36, 0.05), (0.05, 0.05))], "wolf_grey"),
                                                       soft("ico", (x, 0.32, 0.04), (0.11, 0.15, 0.07), "fur_grey", sub=1)], (x, 0.32, HZ))

    root_with([Body, front(-1), front(1), hind(-1), hind(1)] + JOINTS)


def yeti():
    """Hulking white yeti with curled horns, blue face and icy claws (also the Yeti King boss)."""
    H = gm.HIP_Z
    body = [soft("ico", (0, 0.02, 1.32), (1.0, 0.75, 0.95), "fur_white", sub=2),
            soft("ico", (0, -0.05, 0.98), (0.8, 0.62, 0.55), "fur_white", sub=2),
            soft("ico", (0, -0.3, 1.25), (0.62, 0.3, 0.55), "fur_grey", sub=2),                  # belly
            soft("ico", (0, 0.12, 1.66), (0.9, 0.6, 0.4), "fur_white", sub=2)]                   # hunched shoulders
    for k in range(5):
        a = k * 72
        x, y = r2(0.42, 0, a)
        body.append(part("cone", (x, y, 0.72), (0.18, 0.18, 0.3), "fur_white", verts=4, rot=(180, 0, 0)))   # shaggy hem
    Body = group("Body", body, (0, 0, H))
    head = [soft("ico", (0, -0.14, 1.88), (0.5, 0.48, 0.48), "fur_white", sub=2),
            soft("ico", (0, -0.34, 1.84), (0.34, 0.16, 0.3), "frost_blue", sub=2),               # face
            soft("ico", (-0.08, -0.42, 1.9), (0.07, 0.03, 0.05), "ice_glow", sub=1),
            soft("ico", (0.08, -0.42, 1.9), (0.07, 0.03, 0.05), "ice_glow", sub=1),
            part("cube", (0, -0.43, 1.77), (0.16, 0.03, 0.04), "black"),
            part("cone", (-0.06, -0.44, 1.75), (0.04, 0.03, 0.07), "white", verts=4),
            part("cone", (0.06, -0.44, 1.75), (0.04, 0.03, 0.07), "white", verts=4)]
    for x in (-1, 1):
        head.append(tube([((0.2 * x, -0.05, 2.02), (0.07, 0.07)), ((0.36 * x, 0.04, 2.14), (0.055, 0.055)), ((0.42 * x, -0.08, 2.0), (0.035, 0.035)),
                          ((0.34 * x, -0.14, 1.95), (0.015, 0.015))], "yeti_horn"))
    JOINTS.append(group("Head", head, (0, -0.05, gm.NECK_Z + 0.05)))

    def arm(side):
        x = 0.52 * side
        upper = group("ArmR" if side < 0 else "ArmL", [soft("ico", (x, 0, 1.4), (0.36, 0.36, 0.5), "fur_white", sub=2)], (x, 0, gm.SHOULDER_Z))
        fore = [soft("ico", (x * 1.06, -0.04, 1.02), (0.34, 0.34, 0.5), "fur_white", sub=2),
                soft("ico", (x * 1.08, -0.06, 0.74), (0.3, 0.3, 0.24), "frost_blue", sub=2)]
        for k in range(3):
            fore.append(part("cone", (x * 1.08 + 0.07 * (k - 1), -0.16, 0.62), (0.05, 0.05, 0.16), "ice", verts=4, rot=(200, 0, 0)))
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", fore, (x, 0, gm.ELBOW_Z)))
        return upper

    def leg(side):
        x = 0.2 * side
        thigh = group("LegR" if side < 0 else "LegL", [soft("ico", (x, 0, 0.72), (0.34, 0.36, 0.48), "fur_white", sub=2)], (x, 0, H))
        shin = group("ShinR" if side < 0 else "ShinL", [soft("ico", (x, 0, 0.32), (0.3, 0.32, 0.44), "fur_white", sub=2),
                                                         soft("ico", (x, -0.08, 0.07), (0.32, 0.44, 0.16), "frost_blue", sub=2)], (x, 0, gm.KNEE_Z))
        JOINTS.append(shin)
        return thigh

    root_with([Body, arm(-1), arm(1), leg(-1), leg(1)] + JOINTS)


def grumpy_snowman():
    """Evil snowman that waddles in and explodes into ice shards. Coal eyes glow red, twig arms."""
    body = [soft("ico", (0, 0, 0.42), (0.86, 0.86, 0.8), "snow", sub=2),
            soft("ico", (0, 0, 0.98), (0.64, 0.64, 0.6), "snow", sub=2),
            soft("ico", (0, 0, 0.75), (0.7, 0.7, 0.14), "snow_shadow", sub=2)]
    for z in (0.95, 1.1, 0.6):
        body.append(soft("ico", (0, -0.32 if z > 0.7 else -0.42, z), (0.07, 0.05, 0.07), "coal", sub=1))
    body.append(soft("cyl", (0, 0, 1.24), (0.5, 0.5, 0.12), "banner_red", verts=10))   # scarf
    body.append(part("cube", (0.18, -0.25, 1.1), (0.12, 0.06, 0.34), "banner_red", rot=(0, 15, 0)))
    Body = group("Body", body, (0, 0, 0.4))
    head = [soft("ico", (0, 0, 1.48), (0.48, 0.48, 0.46), "snow", sub=2),
            soft("ico", (-0.09, -0.21, 1.53), (0.07, 0.04, 0.07), "eye_red", sub=1),
            soft("ico", (0.09, -0.21, 1.53), (0.07, 0.04, 0.07), "eye_red", sub=1),
            part("cube", (-0.09, -0.22, 1.6), (0.12, 0.03, 0.03), "coal", rot=(0, -25, 0)),
            part("cube", (0.09, -0.22, 1.6), (0.12, 0.03, 0.03), "coal", rot=(0, 25, 0)),
            part("cone", (0, -0.36, 1.46), (0.08, 0.08, 0.3), "carrot", verts=6, rot=(90, 0, 0)),
            part("cube", (0, -0.21, 1.37), (0.16, 0.03, 0.03), "coal"),
            part("cyl", (0, 0, 1.72), (0.36, 0.36, 0.06), "coal", verts=10),
            part("cyl", (0, 0, 1.86), (0.24, 0.24, 0.26), "coal", verts=10)]
    JOINTS.append(group("Head", head, (0, 0, 1.25)))
    arms = []
    for side in (-1, 1):
        x = 0.28 * side
        a = [part("cyl", (x * 1.6, 0, 1.04), (0.04, 0.04, 0.5), "wood_dark", rot=(0, 70 * side, 0), verts=4),
             part("cyl", (x * 2.2, -0.02, 1.16), (0.03, 0.03, 0.2), "wood_dark", rot=(0, 20 * side, 0), verts=4)]
        arms.append(group("ArmR" if side < 0 else "ArmL", a, (x, 0, 1.0)))
    root_with([Body] + arms + JOINTS)


def recolored(fn, mapping):
    """Build an existing model with some palette colours swapped (variants that need a real hue change)."""
    def run():
        orig = gm.uv_for
        gm.uv_for = lambda c: orig(mapping.get(c, c))
        try:
            fn()
        finally:
            gm.uv_for = orig
    return run


MODELS = [
    # haunted keep
    ("Environment", "Keep", keep),
    ("Environment", "Mausoleum", mausoleum),
    ("Environment", "Windmill", windmill),
    ("Environment", "Bridge", bridge),
    ("Environment", "HangingTree", hanging_tree),
    ("Environment", "BounceShroom", bounce_shroom),
    ("Environment", "KnightStatue", knight_statue),
    ("Environment", "Well", well),
    ("Environment", "SupplyCrate", supply_crate),
    ("Environment", "GrainSack", grain_sack),
    ("Environment", "Urn", urn()),
    ("Environment", "Barrel", barrel),
    # molten caldera
    ("Environment", "DragonSkull", dragon_skull),
    ("Environment", "DragonRibcage", dragon_ribcage),
    ("Environment", "DragonClaw", dragon_claw),
    ("Environment", "DwarfForge", dwarf_forge),
    ("Environment", "GiantHammer", giant_hammer),
    ("Environment", "CrystalCluster", crystal_cluster()),
    ("Environment", "SteamVent", steam_vent),
    ("Environment", "LavaFall", lava_fall),
    ("Environment", "MagmaUrn", urn("basalt", "basalt_dark", "magma")),
    # frostfall peaks
    ("Environment", "SnowPineA", snow_pine(1, 4)),
    ("Environment", "SnowPineB", snow_pine(2, 5)),
    ("Environment", "IceSpireA", ice_spire(21)),
    ("Environment", "IceSpireB", ice_spire(22)),
    ("Environment", "SnowRockA", snow_rock(31, (1.8, 1.4, 1.2))),
    ("Environment", "SnowRockB", snow_rock(32, (3.0, 2.4, 1.8))),
    ("Environment", "FrozenTitan", frozen_titan),
    ("Environment", "RuneMonolithA", rune_monolith(3)),
    ("Environment", "RuneMonolithB", rune_monolith(4)),
    ("Environment", "Longhouse", longhouse),
    ("Environment", "Tent", tent),
    ("Environment", "Campfire", campfire),
    ("Environment", "Igloo", igloo),
    ("Environment", "FrozenWaterfall", frozen_waterfall),
    ("Environment", "FrostMountainA", frost_mountain(5, 80, 48)),
    ("Environment", "FrostMountainB", frost_mountain(6, 110, 64)),
    ("Environment", "IceGeyser", ice_geyser),
    ("Environment", "IceCrate", ice_crate),
    ("Environment", "FrozenUrn", urn("ice", "ice_dark", "ice_glow")),
    # enemies
    ("Enemies", "IceWolf", ice_wolf),
    ("Enemies", "Yeti", yeti),
    ("Enemies", "Snowman", grumpy_snowman),
    ("Enemies", "FrostSlime", recolored(gm.slime, {"slime_green": "ice", "slime_dark": "ice_dark", "slime_core": "ice_glow"})),
    ("Enemies", "FrostBat", recolored(gm.bat, {"mage_dark": "frost_blue", "mage_purple": "ice", "heart_red": "ice_glow", "eye_red": "ice_glow"})),
]

SMOOTH = {"Snowman", "FrostSlime", "FrostBat"}

if __name__ == "__main__":
    only = None
    if "--" in sys.argv:
        only = set(sys.argv[sys.argv.index("--") + 1:])
    for cat, name, fn in MODELS:
        if only and name not in only:
            continue
        JOINTS.clear()
        gm.reset()
        fn()
        if name in SMOOTH:
            gm._smooth_all()
        gm.export(cat, name)
    print("DONE")
