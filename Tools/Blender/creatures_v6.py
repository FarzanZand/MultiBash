"""
MultiBash creatures v6: enemies built like the v6 heroes (sculpted lofted meshes, baked pixel-art shading, skinned to
a small armature) instead of mashed primitives.

  blender -b --factory-startup -P Tools/Blender/creatures_v6.py -- Yeti [--preview] [--out=path] [--cam=x,y,z,tx,ty,tz[,lens]]

Every creature defines its own bones (same names the game's ProceduralRig drives: Body, Head, ArmL/R, ForeArmL/R,
LegL/R, ShinL/R) and which bones each body area may be weighted to. Output: Assets/_Game/Art/Models/Creatures/<Name>.fbx
and Assets/_Game/Art/Textures/Characters/T_Char_<Name>.png (material M_Char_<Name>).
"""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import generate_models as gm  # noqa: E402
import characters as ch  # noqa: E402
import heroes_v6 as hv  # noqa: E402
from heroes_v6 import Atlas, Builder, pack, ell, egg  # noqa: E402

OUT_MODELS = os.path.join(gm.ROOT, "Assets", "_Game", "Art", "Models", "Creatures")

# extra ramps (dark -> light, 6 tones)
EXTRA_RAMPS = [
    ("fur",    ("#26304a", "#46567a", "#7a8cb2", "#b2c2dc", "#dfe8f4", "#ffffff")),
    ("frost",  ("#0a1838", "#163064", "#28549a", "#427ec8", "#70acea", "#b8e0ff")),
    ("ice",    ("#0c3048", "#185e80", "#2e94b8", "#5ccae2", "#a6eef8", "#ffffff")),
    ("horn",   ("#261c12", "#463624", "#6e5a3c", "#9a845e", "#c6b28a", "#efe2c2")),
    ("wolf",   ("#12141a", "#262a34", "#3e4452", "#5e6676", "#868f9e", "#b4bcc8")),
    ("snow",   ("#44547a", "#7284a8", "#a2b4d0", "#cad8e8", "#ebf2fa", "#ffffff")),
    ("coal",   ("#020203", "#08080b", "#111116", "#1c1c24", "#2a2a34", "#3c3c48")),
    ("ember",  ("#3a0604", "#7a1206", "#c42a0a", "#f05a18", "#ff9a3a", "#ffe08a")),
]
for k, v in EXTRA_RAMPS:
    if k not in hv.RAMP_ID:
        hv.RAMP_LIST.append((k, v))
        hv.RAMP_ID[k] = len(hv.RAMP_LIST) - 1
        hv.RAMP_NAME.append(k)
        hv.RAMPS[k] = np.array([hv.hexc(c) for c in v], dtype=np.float32)


# ----------------------------------------------------------------------------- geometry helpers

def _basis(d):
    d = np.array(d, dtype=float)
    d /= max(1e-9, np.linalg.norm(d))
    up = np.array([0.0, -1.0, 0.0]) if abs(d[2]) > 0.9 else np.array([0.0, 0.0, 1.0])
    u = np.cross(up, d); u /= max(1e-9, np.linalg.norm(u))
    v = np.cross(d, u)
    return u, v


def tube(B, rect, pts, radii, bone=None, n=10, cap_a=True, cap_b=True, squash=1.0, jag=0.0, mirror=False):
    """Tube along a 3D path with rings perpendicular to the path (horns, limbs, tails, claws).
    radii: per point, a float or (rx, ry). squash flattens the rings along the second axis. jag: zig-zag on the last ring."""
    bi = B._bone(bone)
    P = [np.array(p, dtype=float) for p in pts]
    if mirror:
        P = [np.array([-p[0], p[1], p[2]]) for p in P]
    rings = []
    for k, p in enumerate(P):
        d = (P[min(k + 1, len(P) - 1)] - P[max(k - 1, 0)])
        u, v = _basis(d)
        r = radii[k]
        rx, ry = (r, r * squash) if not isinstance(r, tuple) else r
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            jj = (jag if (k == len(P) - 1 and i % 2 == 0) else 0.0)
            q = p + u * math.cos(a) * rx + v * math.sin(a) * ry + (P[-1] - P[-2]) / max(1e-6, np.linalg.norm(P[-1] - P[-2])) * jj
            vt = B.bm.verts.new(tuple(q))
            vt[B.bones] = bi
            ring.append(vt)
        rings.append(ring)
    seg = [np.linalg.norm(P[i + 1] - P[i]) for i in range(len(P) - 1)]
    tot = sum(seg) or 1.0
    vs = [0.04]
    for s in seg:
        vs.append(vs[-1] + 0.92 * s / tot)
    for r in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            quad = [rings[r][i], rings[r][j], rings[r + 1][j], rings[r + 1][i]]
            uvs = [(i / n, vs[r]), ((i + 1) / n, vs[r]), ((i + 1) / n, vs[r + 1]), (i / n, vs[r + 1])]
            if mirror:
                quad.reverse(); uvs.reverse()
            f = B.bm.faces.new(quad)
            for loop, (uu, vv) in zip(f.loops, uvs):
                loop[B.uv].uv = rect.uv(uu, vv)
    for ring, vcap, do in ((rings[0], 0.01, cap_a), (rings[-1], 0.99, cap_b)):
        if not do:
            continue
        c = sum((v.co for v in ring), ring[0].co * 0) / len(ring)
        cv = B.bm.verts.new(c)
        cv[B.bones] = bi
        for i in range(n):
            j = (i + 1) % n
            tri = [cv, ring[j], ring[i]] if vcap < 0.5 else [cv, ring[i], ring[j]]
            if mirror:
                tri.reverse()
            try:
                f = B.bm.faces.new(tri)
            except ValueError:
                continue
            for loop in f.loops:
                loop[B.uv].uv = rect.uv((i + 0.5) / n, vcap)


def shag(rx, ry_b, ry_f, n=16, jag=0.06, every=2, phase=0, cy=0.0):
    """Egg ring whose points alternately drop by `jag` (shaggy fur hem)."""
    return [(x, y + cy, -(jag if (i + phase) % every == 0 else 0.0)) for i, (x, y) in enumerate(egg(rx, ry_b, ry_f, n))]


def streaks(rect, ramp, n, v0=0.1, v1=0.95, dark=1, light=4, seed=0):
    """Fur: short scattered strokes that shift the LIT tone (so shading still reads), plus darker tuft tips."""
    rng = np.random.default_rng(seed + rect.x * 7 + rect.y * 13)
    A = rect.a
    count = int(rect.w * rect.h * 0.05 * (n / 10.0))
    for _ in range(count):
        x = rect.x + int(rng.integers(0, rect.w))
        y0 = rect.y + int(rng.uniform(v0, v1) * rect.h)
        ln = int(rng.integers(2, 4))
        delta = 0.85 if rng.random() < 0.55 else -0.95
        for k in range(ln):
            y = y0 + k
            if rect.y <= y < rect.y + rect.h and 0 <= x < A.size:
                A.bias[y, x] += delta * (1.0 if k < ln - 1 else 0.6)


# ----------------------------------------------------------------------------- skeleton per creature

def use_bones(bones, allowed):
    ch.BONES.clear()
    ch.BONES.update(bones)
    ch.allowed = allowed


# ============================================================================= YETI (~2.3 m, hunched)

YETI_BONES = {
    "Root": ((0, 0, 0), (0, 0, 0.3), None),
    "Body": ((0, 0.02, 1.0), (0, -0.08, 1.9), "Root"),
    "Head": ((0, -0.24, 1.86), (0, -0.3, 2.24), "Body"),
    "ArmL": ((0.5, -0.04, 1.74), (0.64, -0.12, 1.26), "Body"), "ForeArmL": ((0.64, -0.12, 1.26), (0.68, -0.22, 0.42), "ArmL"),
    "ArmR": ((-0.5, -0.04, 1.74), (-0.64, -0.12, 1.26), "Body"), "ForeArmR": ((-0.64, -0.12, 1.26), (-0.68, -0.22, 0.42), "ArmR"),
    "LegL": ((0.24, 0.02, 1.0), (0.27, -0.02, 0.55), "Root"), "ShinL": ((0.27, -0.02, 0.55), (0.27, -0.04, 0.05), "LegL"),
    "LegR": ((-0.24, 0.02, 1.0), (-0.27, -0.02, 0.55), "Root"), "ShinR": ((-0.27, -0.02, 0.55), (-0.27, -0.04, 0.05), "LegR"),
}


def yeti_allowed(name, p):
    x, y, z = p
    if name == "Root":
        return False
    if name == "Head":
        return z > 1.84 and y < -0.05
    if name in ("ArmL", "ForeArmL"):
        return x > 0.42
    if name in ("ArmR", "ForeArmR"):
        return x < -0.42
    if name in ("LegL", "ShinL"):
        return x > 0.0 and z < 1.0
    if name in ("LegR", "ShinR"):
        return x < 0.0 and z < 1.0
    return z > 0.85


def yeti():
    use_bones(YETI_BONES, yeti_allowed)
    A = Atlas()
    R = pack(A, [("torso", 64, 34), ("mantle", 64, 14), ("head", 40, 22), ("muzzle", 24, 10), ("horn", 12, 16),
                 ("upper", 24, 16), ("fore", 24, 18), ("cuff", 32, 8), ("hand", 16, 10), ("claw", 8, 6),
                 ("thigh", 24, 12), ("shin", 24, 12), ("legcuff", 32, 6), ("foot", 16, 10), ("shard", 8, 12), ("fang", 4, 4)])
    B = Builder()

    # ---- hunched torso: huge shoulders and hump, barrel chest, narrow hips
    T = [(2.0, 0.03, (0.2, 0.17, 0.1)), (1.92, 0.0, (0.42, 0.3, 0.17)), (1.78, -0.05, (0.58, 0.34, 0.28)),
         (1.58, -0.07, (0.56, 0.32, 0.34)), (1.34, -0.05, (0.47, 0.3, 0.36)), (1.12, 0.0, (0.38, 0.26, 0.3)),
         (0.95, 0.02, (0.3, 0.22, 0.22))]
    B.loft(R["torso"], [(0, cy, z, egg(rx, yb, yf, 16, {7: 1.04, 9: 1.04})) for z, cy, (rx, yb, yf) in T])
    # shaggy mantle over the shoulders (fur hangs down over the chest and back)
    B.loft(R["mantle"], [(0, 0.0, 1.97, egg(0.3, 0.26, 0.14, 16)), (0, -0.04, 1.86, egg(0.56, 0.36, 0.27, 16)),
                         (0, -0.06, 1.72, egg(0.63, 0.38, 0.35, 16)),
                         (0, -0.06, 1.5, shag(0.63, 0.38, 0.39, 20, jag=0.16))], cap_bot=False)
    # belly fur hem around the hips
    B.loft(R["mantle"], [(0, 0.0, 1.12, egg(0.395, 0.275, 0.315, 16)), (0, 0.02, 0.98, egg(0.35, 0.26, 0.27, 16)),
                         (0, 0.02, 0.84, shag(0.34, 0.26, 0.27, 20, jag=0.13, phase=1))], cap_top=False, cap_bot=False)

    # ---- head sunk forward between the shoulders, heavy brow, blue muzzle, curled horns
    Hd = [(2.22, (0.07, 0.06, 0.06), {}), (2.17, (0.17, 0.15, 0.14), {}), (2.09, (0.215, 0.18, 0.18), {6: 1.1, 7: 1.14, 8: 1.12, 9: 1.14, 10: 1.1}),
          (2.02, (0.22, 0.18, 0.17), {7: 0.9, 9: 0.9}), (1.95, (0.2, 0.16, 0.19), {}), (1.88, (0.15, 0.12, 0.15), {})]
    B.loft(R["head"], [(0, -0.33, z - 0.06, egg(rx * 1.08, yb, yf, 16, bl)) for z, (rx, yb, yf), bl in Hd], bone="Head")
    B.loft(R["muzzle"], [(0, -0.48, 1.98, egg(0.11, 0.05, 0.05, 12)), (0, -0.52, 1.93, egg(0.16, 0.08, 0.11, 12)),
                         (0, -0.51, 1.86, egg(0.15, 0.08, 0.1, 12)), (0, -0.47, 1.81, egg(0.1, 0.06, 0.06, 12))], bone="Head")
    for s in (1, -1):
        tube(B, R["horn"], [(0.17, -0.3, 2.06), (0.3, -0.26, 2.16), (0.41, -0.3, 2.2), (0.47, -0.4, 2.13), (0.44, -0.48, 2.03)],
             [0.055, 0.05, 0.042, 0.03, 0.008], bone="Head", n=8, mirror=s < 0)
        tube(B, R["fang"], [(0.07, -0.6, 1.84), (0.075, -0.62, 1.93)], [0.022, 0.004], bone="Head", n=6, mirror=s < 0)

    # ---- long arms reaching past the knees: fur sleeves, blue mitts with ice claws
    for s in (1, -1):
        m = s < 0
        tube(B, R["upper"], [(0.44, -0.03, 1.72), (0.57, -0.08, 1.5), (0.64, -0.12, 1.26)], [0.17, 0.18, 0.16], n=12, mirror=m)
        tube(B, R["fore"], [(0.64, -0.12, 1.28), (0.67, -0.17, 0.95), (0.68, -0.21, 0.66)], [0.15, 0.17, 0.18], n=12, mirror=m,
             bone=hv.side("ForeArm", s), cap_b=False)
        tube(B, R["cuff"], [(0.68, -0.2, 0.74), (0.68, -0.21, 0.6)], [0.21, 0.22], n=14, mirror=m, bone=hv.side("ForeArm", s),
             cap_a=False, cap_b=False, jag=0.1)
        tube(B, R["hand"], [(0.68, -0.21, 0.64), (0.69, -0.24, 0.5), (0.69, -0.27, 0.4)], [0.12, (0.14, 0.11), (0.1, 0.08)], n=10,
             mirror=m, bone=hv.side("ForeArm", s))
        for k in range(3):
            x = 0.64 + 0.045 * k
            tube(B, R["claw"], [(x, -0.33, 0.42), (x, -0.4, 0.36), (x + 0.005, -0.42, 0.28)], [0.026, 0.02, 0.004], n=6, mirror=m,
                 bone=hv.side("ForeArm", s))
        # ---- short thick legs with fur cuffs and big blue feet
        tube(B, R["thigh"], [(0.24, 0.02, 1.0), (0.27, -0.02, 0.78), (0.27, -0.02, 0.55)], [0.2, 0.2, 0.17], n=12, mirror=m)
        tube(B, R["shin"], [(0.27, -0.02, 0.58), (0.27, -0.01, 0.34), (0.27, -0.03, 0.14)], [0.16, 0.17, 0.15], n=12, mirror=m,
             bone=hv.side("Shin", s))
        tube(B, R["legcuff"], [(0.27, -0.03, 0.24), (0.27, -0.03, 0.12)], [0.19, 0.19], n=12, mirror=m, bone=hv.side("Shin", s),
             cap_a=False, cap_b=False, jag=0.09)
        tube(B, R["foot"], [(0.27, 0.06, 0.07), (0.27, -0.1, 0.06), (0.27, -0.26, 0.05)], [(0.13, 0.07), (0.15, 0.07), (0.12, 0.05)], n=10,
             mirror=m, bone=hv.side("Shin", s))
    # ice shards growing out of the hump
    for (x, y, z, lx, ly, lz, r) in ((0.0, 0.2, 1.95, 0.0, 0.2, 0.22, 0.06), (0.16, 0.22, 1.88, 0.1, 0.16, 0.16, 0.05),
                                     (-0.16, 0.22, 1.88, -0.1, 0.16, 0.16, 0.05), (0.08, 0.3, 1.74, 0.04, 0.2, 0.08, 0.04),
                                     (-0.08, 0.3, 1.74, -0.04, 0.2, 0.08, 0.04)):
        tube(B, R["shard"], [(x, y, z), (x + lx * 0.6, y + ly * 0.6, z + lz * 0.6), (x + lx, y + ly, z + lz)], [r, r * 0.7, 0.004], n=5, bone="Body")

    # ---- paint
    for k in ("torso", "upper", "fore", "thigh", "shin"):
        R[k].fill("fur", -0.2)
    for k in ("mantle", "cuff", "legcuff"):
        R[k].fill("fur", 0.1)
    R["head"].fill("fur", 0.0)
    R["muzzle"].fill("frost", 0.8); R["hand"].fill("frost", -0.2); R["foot"].fill("frost", -0.3)
    R["horn"].fill("horn"); R["claw"].fill("ice", 0.4); R["fang"].fill("cloth", 0.6)
    R["shard"].fill("ice", 0.5); R["shard"].glow(0, 0, 1, 1)
    streaks(R["torso"], "fur", 12, 0.1, 0.95, dark=2, light=4)
    streaks(R["mantle"], "fur", 9, 0.05, 1.0, dark=2, light=5)
    for k, n in (("upper", 9), ("fore", 9), ("thigh", 9), ("shin", 9), ("cuff", 12), ("legcuff", 12)):
        streaks(R[k], "fur", n, 0.05, 1.0, dark=2, light=5)
    # pale blue chest skin showing through the fur (ragged edge)
    t = R["torso"]
    for (u0, u1, v0, v1, tone) in ((0.43, 0.57, 0.42, 0.8, 3), (0.41, 0.59, 0.48, 0.74, 3), (0.45, 0.55, 0.46, 0.78, 4)):
        t.box(u0, v0, u1, v1, "frost", tone)
    # face: blue mask, deep brow, glowing eyes, wide dark mouth inside the muzzle
    h = R["head"]
    h.box(0.37, 0.42, 0.63, 1.0, "frost", 3)
    h.box(0.4, 0.5, 0.6, 1.0, "frost", 4)
    h.hline(0.4, "fur", 2, 0.35, 0.65, thick=2)
    for u in (0.44, 0.56):
        h.box(u - 0.04, 0.48, u + 0.04, 0.64, "frost", 0)               # sockets
        h.box(u - 0.02, 0.52, u + 0.02, 0.6, "ice", 5)
        h.glow(u - 0.02, 0.52, u + 0.02, 0.6)
    mz = R["muzzle"]
    mz.box(0.36, 0.55, 0.64, 0.8, "black", 0)                            # open mouth
    mz.hline(0.55, "frost", 1, 0.34, 0.66)
    mz.box(0.46, 0.18, 0.54, 0.3, "frost", 1)                            # nose
    for k in range(4):
        R["horn"].hline(0.2 + k * 0.2, "horn", 1)                       # horn ridges
    return B, A


CREATURES = {"Yeti": yeti}


# ============================================================================= shared bits

HUMAN_BONES = {
    "Root": ((0, 0, 0), (0, 0, 0.3), None),
    "Body": ((0, 0, 0.95), (0, 0, 1.6), "Root"),
    "Head": ((0, 0, 1.62), (0, 0, 1.97), "Body"),
    "ArmL": ((0.17, 0, 1.5), (0.31, 0.005, 1.15), "Body"), "ForeArmL": ((0.31, 0.005, 1.15), (0.335, -0.025, 0.72), "ArmL"),
    "ArmR": ((-0.17, 0, 1.5), (-0.31, 0.005, 1.15), "Body"), "ForeArmR": ((-0.31, 0.005, 1.15), (-0.335, -0.025, 0.72), "ArmR"),
    "LegL": ((0.1, 0, 0.95), (0.105, -0.01, 0.53), "Root"), "ShinL": ((0.105, -0.01, 0.53), (0.105, -0.06, 0.05), "LegL"),
    "LegR": ((-0.1, 0, 0.95), (-0.105, -0.01, 0.53), "Root"), "ShinR": ((-0.105, -0.01, 0.53), (-0.105, -0.06, 0.05), "LegR"),
}


def human_allowed(name, p):
    x, y, z = p
    if name == "Root":
        return False
    if name == "Head":
        return z > 1.6
    if name in ("ArmL", "ForeArmL"):
        return x > 0.15 and z > 0.6
    if name in ("ArmR", "ForeArmR"):
        return x < -0.15 and z > 0.6
    if name in ("LegL", "ShinL"):
        return x > -0.02 and z < 0.98
    if name in ("LegR", "ShinR"):
        return x < 0.02 and z < 0.98
    return True


for k, v in [("bone",    ("#2a2216", "#56483a", "#8a7a60", "#bdb092", "#e4dabe", "#fff9e8")),
             ("rust",    ("#1e0c06", "#40200e", "#6a381c", "#965630", "#c2804e", "#e6ac7c")),
             ("batfur",  ("#100a1a", "#221238", "#3a1e5c", "#583084", "#7a4cac", "#a478d4")),
             ("batwing", ("#280c22", "#4c1840", "#782a60", "#a24480", "#c668a2", "#e6a0ca")),
             ("slime",   ("#0c2a0a", "#1c5414", "#36861e", "#5cb82c", "#94e256", "#dcffa6"))]:
    if k not in hv.RAMP_ID:
        hv.RAMP_LIST.append((k, v)); hv.RAMP_ID[k] = len(hv.RAMP_LIST) - 1; hv.RAMP_NAME.append(k)
        hv.RAMPS[k] = np.array([hv.hexc(c) for c in v], dtype=np.float32)


def lerp3(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def long_bone(B, rect, a, b, r, bone, n=8, mirror=False):
    """Bone shaft with knobbed ends."""
    tube(B, rect, [a, lerp3(a, b, 0.12), lerp3(a, b, 0.5), lerp3(a, b, 0.88), b], [r * 1.7, r * 1.1, r, r * 1.1, r * 1.6],
         bone=bone, n=n, mirror=mirror)


def vz(z, z0, z1):
    """v on a loft rect for height z (loft from z0 at the top to z1 at the bottom)."""
    return 0.04 + 0.92 * (z0 - z) / (z0 - z1)


# ============================================================================= SKELETON (+ archer)

SKULL = [(1.99, (0.06, 0.06, 0.06)), (1.96, (0.14, 0.14, 0.13)), (1.91, (0.178, 0.17, 0.165)), (1.84, (0.188, 0.178, 0.18)),
         (1.78, (0.182, 0.17, 0.19)), (1.73, (0.165, 0.15, 0.185)), (1.69, (0.125, 0.11, 0.15)), (1.665, (0.07, 0.06, 0.09))]


def skeleton(archer=False):
    use_bones(HUMAN_BONES, human_allowed)
    A = Atlas()
    R = pack(A, [("skull", 48, 30), ("jaw", 24, 10), ("rib", 16, 6), ("spine", 8, 24), ("pelvis", 32, 12), ("limb", 12, 16),
                 ("hand", 8, 8), ("foot", 12, 8), ("blade", 8, 20), ("grip", 8, 8), ("hood", 48, 24), ("cape", 40, 26), ("bow", 6, 30),
                 ("quiver", 12, 16)])
    B = Builder()
    z0, z1 = SKULL[0][0], SKULL[-1][0]
    B.loft(R["skull"], [(0, 0.0, z, egg(rx, yb, yf, 16, {6: 1.06, 10: 1.06} if 1.8 > z > 1.72 else {})) for z, (rx, yb, yf) in SKULL], bone="Head")
    B.loft(R["jaw"], [(0, -0.05, 1.685, egg(0.12, 0.05, 0.12, 12)), (0, -0.06, 1.645, egg(0.11, 0.045, 0.11, 12)),
                      (0, -0.055, 1.615, egg(0.07, 0.03, 0.07, 12))], bone="Head")
    # spine with vertebra bumps, rib cage, sternum, collarbones, pelvis
    sp = [(0, 0.07, 0.98 + i * 0.065) for i in range(11)]
    tube(B, R["spine"], sp, [0.032 if i % 2 == 0 else 0.022 for i in range(11)], bone="Body", n=8)
    for k, (z, w) in enumerate(((1.47, 0.165), (1.4, 0.178), (1.33, 0.172), (1.26, 0.158), (1.2, 0.135))):
        for s in (1, -1):
            tube(B, R["rib"], [(0.02, 0.07, z), (w * 0.7, 0.085, z + 0.005), (w, 0.0, z - 0.015), (w * 0.78, -0.1, z - 0.04), (0.035, -0.125, z - 0.06)],
                 [0.016, 0.017, 0.017, 0.016, 0.014], bone="Body", n=6, mirror=s < 0)
    tube(B, R["spine"], [(0, -0.128, 1.48), (0, -0.135, 1.35), (0, -0.13, 1.21)], [0.022, 0.026, 0.016], bone="Body", n=6)
    for s in (1, -1):
        tube(B, R["limb"], [(0.02, -0.11, 1.53), (0.11, -0.05, 1.545), (0.2, 0.0, 1.52)], [0.016, 0.018, 0.022], bone="Body", n=6, mirror=s < 0)
    B.loft(R["pelvis"], [(0, 0.02, 1.04, egg(0.16, 0.085, 0.07, 12)), (0, 0.02, 0.98, egg(0.135, 0.075, 0.08, 12)),
                         (0, 0.02, 0.92, egg(0.07, 0.05, 0.05, 12))], bone="Body")
    for s in (1, -1):
        m = s < 0
        arm, fore, legb, shin = hv.side("Arm", s), hv.side("ForeArm", s), hv.side("Leg", s), hv.side("Shin", s)
        long_bone(B, R["limb"], (0.2, 0.0, 1.52), (0.27, 0.0, 1.2), 0.021, arm, mirror=m)
        long_bone(B, R["limb"], (0.27, 0.0, 1.2), (0.3, -0.03, 0.93), 0.017, fore, mirror=m)
        long_bone(B, R["limb"], (0.285, 0.018, 1.19), (0.315, -0.012, 0.94), 0.011, fore, n=6, mirror=m)
        tube(B, R["hand"], [(0.305, -0.03, 0.93), (0.31, -0.04, 0.87)], [(0.035, 0.022), (0.03, 0.018)], bone=fore, n=8, mirror=m)
        for k in range(3):
            tube(B, R["hand"], [(0.29 + 0.018 * k, -0.045, 0.87), (0.29 + 0.018 * k, -0.06, 0.82), (0.29 + 0.018 * k, -0.05, 0.79)],
                 [0.009, 0.008, 0.005], bone=fore, n=5, mirror=m)
        long_bone(B, R["limb"], (0.09, 0.01, 0.95), (0.1, -0.01, 0.55), 0.025, legb, mirror=m)
        tube(B, R["limb"], [(0.1, -0.045, 0.58), (0.1, -0.055, 0.53), (0.1, -0.045, 0.49)], [0.022, 0.034, 0.02], bone=shin, n=8, mirror=m)
        long_bone(B, R["limb"], (0.1, -0.01, 0.53), (0.1, 0.0, 0.1), 0.021, shin, mirror=m)
        long_bone(B, R["limb"], (0.125, 0.012, 0.5), (0.12, 0.01, 0.12), 0.011, shin, n=6, mirror=m)
        tube(B, R["foot"], [(0.1, 0.035, 0.06), (0.1, -0.05, 0.04), (0.1, -0.14, 0.025)], [(0.04, 0.03), (0.045, 0.022), (0.035, 0.012)],
             bone=shin, n=8, mirror=m)
    if not archer:
        # rusty short sword in the right hand
        tube(B, R["grip"], [(-0.305, 0.02, 0.86), (-0.305, -0.05, 0.86)], [0.016, 0.016], bone="ForeArmR", n=6)
        tube(B, R["grip"], [(-0.305, -0.06, 0.8), (-0.305, -0.06, 0.92)], [(0.012, 0.016), (0.012, 0.016)], bone="ForeArmR", n=6)
        tube(B, R["blade"], [(-0.305, -0.06, 0.86), (-0.305, -0.3, 0.86), (-0.305, -0.5, 0.86), (-0.305, -0.58, 0.86)],
             [(0.007, 0.038), (0.007, 0.036), (0.006, 0.03), (0.003, 0.004)], bone="ForeArmR", n=6)
    else:
        # hood + tattered cape + bow + quiver
        def hood_ring(z, grow, open_front=-0.06):
            i = min(range(len(SKULL)), key=lambda k: abs(SKULL[k][0] - z))
            rx, yb, yf = SKULL[i][1]
            return [(x, max(y, open_front)) for x, y in egg(rx * grow, yb * grow, yf * grow, 16)]
        B.loft(R["hood"], [(0, 0.0, 2.03, hood_ring(1.99, 1.4)), (0, 0.0, 1.97, hood_ring(1.94, 1.18)), (0, 0.0, 1.86, hood_ring(1.84, 1.16)),
                           (0, 0.01, 1.74, hood_ring(1.76, 1.17, -0.03)), (0, 0.03, 1.6, [(x * 1.25, y * 0.9) for x, y in hood_ring(1.7, 1.25, 0.0)]),
                           (0, 0.04, 1.5, [(x * 1.4, y + 0.02) for x, y in hood_ring(1.7, 1.3, 0.02)])], cap_bot=False, bone="Head")
        jag = [0.0, -0.07, 0.0, -0.05, 0.0, -0.08, 0.0, -0.04]
        B.loft(R["cape"], [(0, 0.1, 1.52, ell(0.2, 0.05, 8)), (0, 0.14, 1.2, ell(0.22, 0.05, 8)),
                           (0, 0.17, 0.85, [(x, y, jag[i]) for i, (x, y) in enumerate(ell(0.22, 0.04, 8))])], cap_top=False, bone="Body")
        tube(B, R["bow"], [(0.33, -0.05, 1.28), (0.34, -0.15, 1.1), (0.345, -0.18, 0.9), (0.34, -0.15, 0.7), (0.33, -0.05, 0.52)],
             [0.012, 0.016, 0.02, 0.016, 0.012], bone="ForeArmL", n=6)
        tube(B, R["grip"], [(0.33, -0.05, 1.27), (0.33, -0.04, 0.9), (0.33, -0.05, 0.53)], [0.003, 0.003, 0.003], bone="ForeArmL", n=4)
        tube(B, R["quiver"], [(0.08, 0.12, 1.5), (-0.1, 0.13, 1.1)], [0.05, 0.045], bone="Body", n=8)
        for k in range(3):
            tube(B, R["blade"], [(0.08 + 0.02 * k, 0.12, 1.5), (0.1 + 0.02 * k, 0.11, 1.6)], [0.008, 0.002], bone="Body", n=4)

    # ---- paint
    for k in ("skull", "jaw", "rib", "spine", "pelvis", "limb", "hand", "foot"):
        R[k].fill("bone", 0.1)
    R["jaw"].fill("bone", -0.2)
    sk = R["skull"]
    ve = vz(1.795, z0, z1)
    for u in (0.4, 0.6):                                                    # plain round eye holes: dark, no glow
        sk.box(u - 0.022, ve - 0.12, u + 0.022, ve + 0.12, "black", 0)    # rounded: narrow tall core...
        sk.box(u - 0.036, ve - 0.07, u + 0.036, ve + 0.07, "black", 0)    # ...plus a wider middle
    vn = vz(1.74, z0, z1)
    sk.box(0.48, vn - 0.04, 0.52, vn + 0.06, "black", 0)                   # nasal cavity
    vt = vz(1.695, z0, z1)
    for j in range(8):                                                       # upper teeth
        u = 0.42 + j * 0.02
        sk.box(u, vt - 0.03, u + 0.015, vt + 0.07, "bone", 5 if j % 2 else 4)
    sk.hline(min(0.96, vt + 0.08), "black", 0, 0.41, 0.59)
    jw = R["jaw"]
    for j in range(8):
        jw.box(0.42 + j * 0.02, 0.0, 0.435 + j * 0.02, 0.35, "bone", 5 if j % 2 else 4)
    sk.vline(0.33, "bone", 2, 0.05, 0.5)                                    # cranial seams / cracks
    sk.dot(0.66, 0.2, "bone", 2); sk.dot(0.67, 0.22, "bone", 2); sk.dot(0.68, 0.25, "bone", 2)
    R["blade"].fill("rust", 0.3); R["blade"].hline(0.4, "rust", 1); R["blade"].vline(0.5, "steel", 4, 0.0, 0.9)
    R["grip"].fill("leather", -0.3)
    R["hood"].fill("red", -0.6); R["cape"].fill("red", -0.9)
    for u in (0.2, 0.4, 0.6, 0.8):
        R["cape"].vline(u, "red", 1, 0.2, 0.9)
    R["hood"].hline(0.9, "wine", 1)
    R["bow"].fill("leather", 0.2); R["quiver"].fill("leather", -0.4)
    R["quiver"].hline(0.15, "gold", 3); R["quiver"].hline(0.85, "gold", 3)
    return B, A


# ============================================================================= SLIMES (green / magma / frost / treasure)

SLIME_BONES = {"Root": ((0, 0, 0), (0, 0, 0.1), None), "Body": ((0, 0, 0.05), (0, 0, 0.8), "Root")}


def slime(kind="slime"):
    use_bones(SLIME_BONES, lambda n, p: n == "Body")
    A = Atlas()
    R = pack(A, [("body", 72, 40), ("eye", 16, 12), ("drip", 12, 8), ("crown", 32, 8), ("coin", 8, 8), ("gem", 8, 8), ("crust", 16, 8)])
    B = Builder()
    D = [(0.86, (0.1, 0.1, 0.1)), (0.8, (0.26, 0.25, 0.25)), (0.7, (0.38, 0.36, 0.37)), (0.55, (0.47, 0.45, 0.46)), (0.38, (0.52, 0.5, 0.52)),
         (0.22, (0.55, 0.53, 0.56)), (0.1, (0.56, 0.55, 0.58)), (0.03, (0.52, 0.5, 0.54)), (0.0, (0.46, 0.44, 0.48))]
    B.loft(R["body"], [(0, 0, z, egg(rx, yb, yf, 20)) for z, (rx, yb, yf) in D], bone="Body")
    for s in (1, -1):   # big googly eyes bulging from the front
        B.loft(R["eye"], [(0.16, -0.4, 0.66, egg(0.035, 0.03, 0.03, 10)), (0.16, -0.43, 0.6, egg(0.09, 0.06, 0.07, 10)),
                          (0.16, -0.44, 0.52, egg(0.1, 0.07, 0.08, 10)), (0.16, -0.43, 0.45, egg(0.075, 0.05, 0.06, 10)),
                          (0.16, -0.41, 0.41, egg(0.03, 0.03, 0.03, 10))], bone="Body", mirror=s < 0)
    for (x, y, l) in ((0.42, -0.25, 0.07), (-0.36, -0.32, 0.09), (0.12, -0.53, 0.06), (-0.5, 0.15, 0.08)):
        tube(B, R["drip"], [(x, y, 0.16), (x * 1.05, y * 1.05, 0.08), (x * 1.06, y * 1.06, 0.0)], [0.06, 0.05, 0.035], bone="Body", n=8)
    def surf(a_deg, z, out=1.0):
        """Point on the slime's skin at angle a (0 = front) and height z."""
        for k in range(len(D) - 1):
            if D[k][0] >= z >= D[k + 1][0]:
                f = (D[k][0] - z) / (D[k][0] - D[k + 1][0])
                rx = D[k][1][0] + (D[k + 1][1][0] - D[k][1][0]) * f
                break
        else:
            rx = D[-1][1][0]
        a = math.radians(a_deg)
        return (math.sin(a) * rx * out, -math.cos(a) * rx * out, z)
    if kind == "treasure":
        jag = [(x, y, 0.07 if i % 2 == 0 else 0.0) for i, (x, y) in enumerate(ell(0.17, 0.16, 12))]
        B.loft(R["crown"], [(0, 0.0, 0.95, jag), (0, 0.0, 0.86, ell(0.16, 0.15, 12))], cap_top=False, bone="Body")
        B.loft(R["gem"], [(0, -0.16, 0.93, ell(0.01, 0.01, 6)), (0, -0.175, 0.9, ell(0.03, 0.02, 6)), (0, -0.165, 0.87, ell(0.01, 0.01, 6))], bone="Body")
        for (ang, z) in ((60, 0.62), (-70, 0.68), (160, 0.7), (-140, 0.55), (110, 0.4), (-100, 0.32), (20, 0.78)):
            p0, p1 = surf(ang, z, 0.96), surf(ang, z, 1.04)
            tube(B, R["coin"], [p0, p1], [0.06, 0.06], bone="Body", n=10)
    if kind == "magma":
        for (ang, z, r) in ((150, 0.72, 0.13), (-120, 0.66, 0.12), (60, 0.62, 0.1), (-60, 0.7, 0.1), (180, 0.45, 0.14), (100, 0.35, 0.12),
                            (-150, 0.3, 0.12), (30, 0.8, 0.09)):
            p0, p1 = surf(ang, z, 0.94), surf(ang, z, 1.05)
            tube(B, R["crust"], [p0, p1], [(r, r * 0.8), (r * 0.75, r * 0.6)], bone="Body", n=7)

    pal = {"slime": "slime", "magma": "ember", "frost": "ice", "treasure": "gold"}[kind]
    b = R["body"]
    b.fill(pal, {"slime": 0.2, "magma": -0.9, "frost": -0.7, "treasure": -0.5}[kind])
    b.fill(pal, -0.6, v0=0.82)                                             # darker, denser base
    b.box(0.3, 0.12, 0.42, 0.26, pal, 5); b.box(0.32, 0.18, 0.37, 0.24, "cloth", 5)    # glossy highlight
    b.dot(0.45, 0.3, "cloth", 5)
    vm = vz(0.33, 0.86, 0.0)
    b.hline(vm, pal, 0, 0.44, 0.56, thick=1)                                # smile
    b.dot(0.43, vm - 0.04, pal, 0); b.dot(0.57, vm - 0.04, pal, 0)
    for j in range(14):                                                      # bubbles inside the jelly
        u, v = (j * 0.37) % 1.0, 0.25 + (j * 0.23) % 0.5
        b.dot(u, v, pal, 4 if j % 2 else 1)
    e = R["eye"]
    e.fill("cloth", 0.6)
    e.box(0.4, 0.3, 0.6, 0.75, "black", 0); e.dot(0.47, 0.38, "cloth", 5)
    R["drip"].fill(pal, -0.2)
    R["crown"].fill("gold", 0.4); R["gem"].fill("red", 0.8); R["gem"].glow(0, 0, 1, 1); R["coin"].fill("gold", 0.6)
    R["crust"].fill("coal", 0.4)
    if kind == "magma":
        for j in range(30):                                                  # glowing cracks between the crust
            u, v = (j * 0.61) % 1.0, 0.1 + (j * 0.29) % 0.75
            b.box(u, v, u + 0.02, v + 0.05, "ember", 5); b.glow(u, v, u + 0.02, v + 0.05)
    if kind == "frost":
        for j in range(18):
            u, v = (j * 0.43) % 1.0, 0.1 + (j * 0.31) % 0.7
            b.dot(u, v, "cloth", 5)
    return B, A


# ============================================================================= BAT (+ frost bat)

BAT_BONES = {
    "Root": ((0, 0, -0.3), (0, 0, -0.1), None),
    "Body": ((0, 0, -0.18), (0, 0, 0.12), "Root"),
    "Head": ((0, -0.02, 0.1), (0, -0.04, 0.42), "Body"),
    "WingL": ((0.12, 0.02, 0.1), (0.7, 0.02, 0.15), "Body"),
    "WingR": ((-0.12, 0.02, 0.1), (-0.7, 0.02, 0.15), "Body"),
}


def bat_allowed(n, p):
    x, y, z = p
    if n == "Root":
        return False
    if n == "WingL":
        return x > 0.13
    if n == "WingR":
        return x < -0.13
    if n == "Head":
        return z > 0.1 and abs(x) < 0.15
    return abs(x) < 0.16


def bat(frost=False):
    use_bones(BAT_BONES, bat_allowed)
    A = Atlas()
    R = pack(A, [("body", 40, 20), ("head", 32, 18), ("ear", 12, 12), ("wing", 48, 26), ("finger", 8, 12), ("foot", 8, 8), ("fang", 4, 4)])
    B = Builder()
    B.loft(R["body"], [(0, 0.01, 0.13, egg(0.08, 0.07, 0.07, 12)), (0, 0.01, 0.06, egg(0.15, 0.13, 0.13, 12)), (0, 0.01, -0.06, egg(0.17, 0.15, 0.15, 12)),
                       (0, 0.02, -0.17, egg(0.12, 0.11, 0.1, 12)), (0, 0.02, -0.23, egg(0.04, 0.04, 0.04, 12))], bone="Body")
    B.loft(R["head"], [(0, -0.03, 0.36, egg(0.06, 0.05, 0.05, 12)), (0, -0.03, 0.31, egg(0.13, 0.11, 0.11, 12)),
                       (0, -0.04, 0.22, egg(0.15, 0.12, 0.14, 12, {5: 1.05, 6: 1.08, 7: 1.08})), (0, -0.04, 0.13, egg(0.1, 0.08, 0.11, 12)),
                       (0, -0.04, 0.09, egg(0.05, 0.04, 0.05, 12))], bone="Head")
    B.loft(R["head"], [(0, -0.15, 0.22, egg(0.03, 0.02, 0.02, 8)), (0, -0.18, 0.19, egg(0.05, 0.03, 0.04, 8)), (0, -0.17, 0.15, egg(0.03, 0.02, 0.03, 8))], bone="Head")
    for s in (1, -1):
        m = s < 0
        tube(B, R["ear"], [(0.08, -0.02, 0.32), (0.12, -0.01, 0.42), (0.14, 0.0, 0.5)], [(0.05, 0.02), (0.04, 0.015), (0.005, 0.004)], bone="Head", n=6, mirror=m)
        tube(B, R["fang"], [(0.03, -0.18, 0.15), (0.032, -0.185, 0.11)], [0.01, 0.002], bone="Head", n=4, mirror=m)
        tube(B, R["foot"], [(0.05, 0.02, -0.2), (0.055, 0.0, -0.28), (0.06, -0.03, -0.3)], [0.02, 0.014, 0.006], bone="Body", n=5, mirror=m)
        # wing: membrane plate with scalloped trailing edge, finger bones on top
        outline = [(0.12, 0.17), (0.3, 0.28), (0.5, 0.33), (0.76, 0.24), (0.7, 0.08), (0.62, -0.02), (0.56, 0.06), (0.48, -0.12),
                   (0.4, -0.02), (0.3, -0.16), (0.22, -0.04), (0.14, -0.12), (0.12, -0.02)]
        if m:
            outline = [(-x, z) for x, z in reversed(outline)]
        wing = hv.side("Wing", s)
        B.plate(R["wing"], outline, 0.02, thick=0.012, bone=wing)
        for tip in ((0.76, 0.24), (0.62, -0.02), (0.48, -0.12), (0.3, -0.16)):
            tube(B, R["finger"], [(0.13, 0.012, 0.14), (0.4, 0.012, 0.25 if tip[1] > 0.1 else 0.15), (tip[0], 0.012, tip[1])],
                 [0.018, 0.012, 0.005], bone=wing, n=5, mirror=m)
    fur, mem = ("frost", "ice") if frost else ("batfur", "batwing")
    R["body"].fill(fur, 0.2); R["head"].fill(fur, 0.3); R["ear"].fill(mem, -0.3); R["foot"].fill(fur, -0.6)
    R["wing"].fill(mem, -0.2); R["finger"].fill(fur, -0.2); R["fang"].fill("cloth", 0.6)
    streaks(R["body"], fur, 10); streaks(R["head"], fur, 6)
    h = R["head"]
    for u in (0.4, 0.6):
        h.box(u - 0.04, 0.42, u + 0.04, 0.6, "black", 0)
        h.box(u - 0.025, 0.46, u + 0.02, 0.56, "ice" if frost else "ember", 5)
        h.glow(u - 0.025, 0.46, u + 0.02, 0.56)
    w = R["wing"]
    for u in (0.25, 0.5, 0.75):
        w.vline(u, mem, 1, 0.1, 0.95)
    return B, A


CREATURES.update({
    "Skeleton": skeleton, "SkeletonArcher": lambda: skeleton(archer=True),
    "Slime": lambda: slime("slime"), "MagmaSlime": lambda: slime("magma"), "FrostSlime": lambda: slime("frost"),
    "TreasureSlime": lambda: slime("treasure"),
    "Bat": bat, "FrostBat": lambda: bat(frost=True),
})



# ============================================================================= batch 2: wolf, snowman, ghoul, wraith, golem, brute, shroom, imp

for k, v in [("ghoul",    ("#121810", "#283222", "#435238", "#637752", "#8a9e72", "#b8c89c")),
             ("spirit",   ("#2a0a4a", "#4a1a7a", "#7a34b0", "#a860e0", "#d29cff", "#f2e0ff")),
             ("wraith",   ("#08050f", "#170e2a", "#281a44", "#3e2c62", "#5a4684", "#8070ae")),
             ("stone",    ("#16181e", "#2e323c", "#4c525e", "#6e7684", "#969eac", "#c4cad4")),
             ("obsidian", ("#05030a", "#100a1a", "#1e162e", "#30244a", "#48386a", "#6e5c9a")),
             ("imp",      ("#220404", "#480a08", "#7a160e", "#ac2a18", "#d84e2a", "#f68a54")),
             ("cap",      ("#2c0606", "#5c0e0c", "#94181a", "#c82a26", "#ea5446", "#ff9a84"))]:
    if k not in hv.RAMP_ID:
        hv.RAMP_LIST.append((k, v)); hv.RAMP_ID[k] = len(hv.RAMP_LIST) - 1; hv.RAMP_NAME.append(k)
        hv.RAMPS[k] = np.array([hv.hexc(c) for c in v], dtype=np.float32)


def rock_ring(rx, ry_b, ry_f, n=8, seed=0, jit=0.12):
    """Faceted stone cross-section (few corners, jittered) -> cut-stone look."""
    rng = np.random.default_rng(seed)
    pts = []
    for i in range(n):
        a = math.pi + 2 * math.pi * i / n
        c = -math.cos(a)
        m = 1.0 + rng.uniform(-jit, jit)
        pts.append((math.sin(a) * rx * m, c * (ry_b if c > 0 else ry_f) * m))
    return pts


def boulder(B, rect, cx, cy, z_top, z_bot, rx, ry, seed, bone=None, n=8, mirror=False):
    """Chunky faceted boulder lofted from 4 rings."""
    zs = [z_top, z_top - (z_top - z_bot) * 0.22, z_bot + (z_top - z_bot) * 0.22, z_bot]
    sc = [0.55, 1.0, 1.0, 0.6]
    secs = []
    for k, (z, f) in enumerate(zip(zs, sc)):
        secs.append((cx if not mirror else -cx, cy, z, rock_ring(rx * f, ry * f, ry * f, n, seed + k)))
    B.loft(rect, secs, bone=bone)


# ---------------------------------------------------------------------------- ICE WOLF (quadruped)

WOLF_BONES = {
    "Root": ((0, 0, 0), (0, 0, 0.3), None),
    "Body": ((0, 0.35, 0.68), (0, -0.35, 0.72), "Root"),
    "Head": ((0, -0.42, 0.96), (0, -0.8, 0.94), "Body"),
    "ArmL": ((0.13, -0.3, 0.7), (0.14, -0.34, 0.4), "Body"), "ForeArmL": ((0.14, -0.34, 0.4), (0.14, -0.36, 0.0), "ArmL"),
    "ArmR": ((-0.13, -0.3, 0.7), (-0.14, -0.34, 0.4), "Body"), "ForeArmR": ((-0.14, -0.34, 0.4), (-0.14, -0.36, 0.0), "ArmR"),
    "LegL": ((0.14, 0.3, 0.72), (0.15, 0.42, 0.42), "Root"), "ShinL": ((0.15, 0.42, 0.42), (0.15, 0.36, 0.0), "LegL"),
    "LegR": ((-0.14, 0.3, 0.72), (-0.15, 0.42, 0.42), "Root"), "ShinR": ((-0.15, 0.42, 0.42), (-0.15, 0.36, 0.0), "LegR"),
}


def ice_wolf():
    use_bones(WOLF_BONES, lambda n, p: n == "Body")
    A = Atlas()
    R = pack(A, [("torso", 56, 28), ("neck", 32, 14), ("mane", 48, 12), ("head", 32, 16), ("muzzle", 24, 10), ("jaw", 16, 8), ("ear", 8, 10),
                 ("leg", 16, 16), ("low", 16, 16), ("paw", 12, 8), ("tail", 24, 14), ("shard", 8, 10), ("tooth", 4, 4)])
    B = Builder()
    # body: deep chest, tucked belly, narrower hips (ring centres drop at the chest)
    tube(B, R["torso"], [(0, 0.46, 0.7), (0, 0.32, 0.7), (0, 0.12, 0.7), (0, -0.08, 0.66), (0, -0.26, 0.64), (0, -0.38, 0.7)],
         [(0.12, 0.13), (0.15, 0.15), (0.15, 0.14), (0.17, 0.19), (0.19, 0.23), (0.15, 0.19)], bone="Body", n=12)
    tube(B, R["neck"], [(0, -0.3, 0.76), (0, -0.4, 0.86), (0, -0.47, 0.95)], [(0.14, 0.16), (0.12, 0.13), (0.11, 0.11)], bone="Body", n=10, cap_a=False)
    tube(B, R["mane"], [(0, -0.16, 0.78), (0, -0.32, 0.84), (0, -0.44, 0.9)], [(0.2, 0.24), (0.19, 0.23), (0.15, 0.17)],
         bone="Body", n=14, cap_a=False, cap_b=False, jag=0.09)
    # head: compact skull, tapering muzzle, open jaw
    tube(B, R["head"], [(0, -0.42, 1.0), (0, -0.5, 1.02), (0, -0.58, 0.99)], [(0.1, 0.09), (0.12, 0.11), (0.1, 0.09)], bone="Head", n=10)
    tube(B, R["muzzle"], [(0, -0.57, 0.97), (0, -0.67, 0.94), (0, -0.76, 0.92), (0, -0.8, 0.915)], [(0.075, 0.07), (0.06, 0.055), (0.045, 0.04), (0.02, 0.02)],
         bone="Head", n=10)
    tube(B, R["jaw"], [(0, -0.56, 0.9), (0, -0.66, 0.87), (0, -0.74, 0.86)], [(0.06, 0.03), (0.045, 0.025), (0.025, 0.012)], bone="Head", n=8)
    for s in (1, -1):
        m = s < 0
        tube(B, R["ear"], [(0.06, -0.47, 1.06), (0.075, -0.465, 1.14), (0.085, -0.46, 1.22)], [(0.05, 0.022), (0.035, 0.016), (0.004, 0.003)],
             bone="Head", n=6, mirror=m)
        tube(B, R["tooth"], [(0.03, -0.73, 0.9), (0.031, -0.735, 0.86)], [0.011, 0.002], bone="Head", n=4, mirror=m)
        arm, fore, legb, shin = hv.side("Arm", s), hv.side("ForeArm", s), hv.side("Leg", s), hv.side("Shin", s)
        tube(B, R["leg"], [(0.11, -0.28, 0.68), (0.12, -0.31, 0.5), (0.12, -0.32, 0.36)], [0.075, 0.06, 0.045], bone=arm, n=8, mirror=m)
        tube(B, R["low"], [(0.12, -0.32, 0.38), (0.12, -0.32, 0.2), (0.12, -0.31, 0.06)], [0.045, 0.038, 0.036], bone=fore, n=8, mirror=m)
        tube(B, R["paw"], [(0.12, -0.28, 0.04), (0.12, -0.35, 0.035), (0.12, -0.41, 0.03)], [(0.045, 0.035), (0.05, 0.03), (0.035, 0.018)],
             bone=fore, n=8, mirror=m)
        tube(B, R["leg"], [(0.11, 0.3, 0.72), (0.13, 0.36, 0.55), (0.13, 0.42, 0.4)], [0.105, 0.08, 0.05], bone=legb, n=8, mirror=m)
        tube(B, R["low"], [(0.13, 0.42, 0.42), (0.13, 0.38, 0.22), (0.13, 0.35, 0.06)], [0.045, 0.038, 0.036], bone=shin, n=8, mirror=m)
        tube(B, R["paw"], [(0.13, 0.38, 0.04), (0.13, 0.31, 0.035), (0.13, 0.25, 0.03)], [(0.045, 0.035), (0.05, 0.03), (0.035, 0.018)],
             bone=shin, n=8, mirror=m)
    tube(B, R["tail"], [(0, 0.44, 0.74), (0, 0.56, 0.68), (0, 0.63, 0.54), (0, 0.65, 0.4), (0, 0.64, 0.32)],
         [0.05, 0.085, 0.09, 0.065, 0.01], bone="Body", n=10)
    for k in range(4):                                                        # ice crystals along the spine
        y = -0.12 + k * 0.15
        tube(B, R["shard"], [(0, y, 0.82 - k * 0.01), (0, y + 0.03, 0.92 - k * 0.02), (0, y + 0.06, 0.99 - k * 0.03)], [0.04, 0.028, 0.003],
             bone="Body", n=5)
    R["torso"].fill("wolf", -0.1); R["neck"].fill("wolf", 0.0); R["leg"].fill("wolf", 0.1); R["paw"].fill("fur", -0.2)
    R["tail"].fill("wolf", -0.2); R["mane"].fill("fur", 0.0); R["head"].fill("wolf", 0.2); R["muzzle"].fill("fur", 0.0); R["jaw"].fill("fur", -0.2)
    R["ear"].fill("wolf", -0.6)
    R["shard"].fill("ice", 0.6); R["shard"].glow(0, 0, 1, 1); R["tooth"].fill("cloth", 0.8)
    t = R["torso"]
    t.fill("wolf", -0.9, u0=0.38, u1=0.62)                                      # dark saddle along the back
    t.fill("fur", 0.1, u0=0.0, u1=0.14); t.fill("fur", 0.1, u0=0.86, u1=1.0)   # pale belly
    R["low"].fill("wolf", 0.1); R["low"].fill("fur", -0.1, v0=0.55)               # white socks
    streaks(t, "wolf", 10); streaks(R["mane"], "fur", 10); streaks(R["tail"], "wolf", 8); streaks(R["neck"], "wolf", 6)
    h = R["head"]
    for u in (0.32, 0.68):                                                       # glowing ice eyes
        h.box(u - 0.035, 0.32, u + 0.035, 0.48, "black", 0)
        h.box(u - 0.02, 0.35, u + 0.02, 0.45, "ice", 5); h.glow(u - 0.02, 0.35, u + 0.02, 0.45)
    mz = R["muzzle"]
    mz.box(0.4, 0.82, 0.6, 1.0, "coal", 1)                                       # nose
    R["jaw"].fill("red", -0.6, u0=0.3, u1=0.7)                                   # mouth inside
    return B, A


# ---------------------------------------------------------------------------- GRUMPY SNOWMAN

SNOW_BONES = {
    "Root": ((0, 0, 0), (0, 0, 0.2), None),
    "Body": ((0, 0, 0.3), (0, 0, 1.2), "Root"),
    "Head": ((0, 0, 1.2), (0, 0, 1.75), "Body"),
    "ArmL": ((0.28, 0, 1.0), (0.62, -0.05, 1.18), "Body"),
    "ArmR": ((-0.28, 0, 1.0), (-0.62, -0.05, 1.18), "Body"),
}


def snowman():
    use_bones(SNOW_BONES, lambda n, p: n == "Body")
    A = Atlas()
    R = pack(A, [("base", 56, 26), ("mid", 48, 20), ("head", 40, 18), ("scarf", 40, 8), ("tail", 12, 12), ("nose", 8, 8),
                 ("coal", 8, 8), ("hat", 32, 16), ("twig", 8, 12)])
    B = Builder()
    def ball(rect, zc, r, squash=0.92, bone="Body", n=16):
        ks = [0.98, 0.86, 0.6, 0.3, 0.0, -0.3, -0.6, -0.86, -0.98]
        B.loft(rect, [(0, 0, zc + r * squash * k, egg(r * math.sqrt(max(0.02, 1 - k * k)), r * math.sqrt(max(0.02, 1 - k * k)),
                                                       r * math.sqrt(max(0.02, 1 - k * k)), n)) for k in ks], bone=bone)
    ball(R["base"], 0.4, 0.44)
    ball(R["mid"], 0.98, 0.33)
    ball(R["head"], 1.46, 0.25, bone="Head")
    B.loft(R["scarf"], [(0, 0, 1.28, egg(0.27, 0.27, 0.27, 16)), (0, 0, 1.2, egg(0.29, 0.29, 0.29, 16))], cap_top=False, cap_bot=False, bone="Body")
    tube(B, R["tail"], [(0.12, -0.24, 1.22), (0.16, -0.3, 1.05), (0.18, -0.3, 0.88)], [(0.07, 0.02), (0.07, 0.02), (0.07, 0.02)], bone="Body", n=6, jag=0.03)
    tube(B, R["nose"], [(0, -0.22, 1.47), (0, -0.36, 1.45), (0, -0.46, 1.43)], [0.045, 0.03, 0.004], bone="Head", n=8)
    for s in (1, -1):
        m = s < 0
        for (x, y, z) in ((0.09, -0.225, 1.53),):
            tube(B, R["coal"], [(x, y + 0.02, z), (x, y - 0.02, z)], [0.03, 0.03], bone="Head", n=6, mirror=m)
        tube(B, R["coal"], [(0.035, -0.24, 1.565), (0.14, -0.215, 1.615)], [(0.012, 0.02), (0.012, 0.02)], bone="Head", n=4, mirror=m)  # angry brows
        arm = hv.side("Arm", s)
        tube(B, R["twig"], [(0.28, 0.0, 1.0), (0.45, -0.02, 1.08), (0.62, -0.05, 1.18)], [0.025, 0.02, 0.012], bone=arm, n=5, mirror=m)
        tube(B, R["twig"], [(0.5, -0.03, 1.1), (0.56, -0.06, 1.24)], [0.012, 0.004], bone=arm, n=4, mirror=m)
        tube(B, R["twig"], [(0.6, -0.05, 1.17), (0.7, -0.08, 1.2)], [0.01, 0.003], bone=arm, n=4, mirror=m)
    for z in (1.08, 0.94, 0.64):                                                 # coal buttons
        r_ = 0.33 if z > 0.8 else 0.44
        zc = 0.98 if z > 0.8 else 0.4
        y = -math.sqrt(max(0.0, r_ * r_ - ((z - zc) / 0.92) ** 2))
        tube(B, R["coal"], [(0, y + 0.02, z), (0, y - 0.03, z)], [0.035, 0.035], bone="Body", n=6)
    B.loft(R["hat"], [(0, 0.02, 1.98, egg(0.14, 0.14, 0.14, 12)), (0, 0.02, 1.76, egg(0.15, 0.15, 0.15, 12)),
                      (0, 0.02, 1.72, egg(0.25, 0.25, 0.25, 12)), (0, 0.02, 1.69, egg(0.25, 0.25, 0.25, 12))], bone="Head")
    R["base"].fill("snow", 0.2); R["mid"].fill("snow", 0.3); R["head"].fill("snow", 0.4)
    for k in ("base", "mid", "head"):
        streaks(R[k], "snow", 5)
    R["scarf"].fill("red", -0.1); R["tail"].fill("red", -0.3)
    R["scarf"].hline(0.5, "red", 1); R["tail"].hline(0.8, "red", 1)
    R["nose"].fill("orange", 0.4); R["coal"].fill("coal", 0.2); R["twig"].fill("leather", -0.5)
    R["hat"].fill("coal", 0.6); R["hat"].hline(0.62, "red", 3, thick=2)
    h = R["head"]
    h.box(0.47, 0.62, 0.53, 0.66, "coal", 1)                                     # grumpy mouth
    for u in (0.42, 0.58):
        h.box(u - 0.015, 0.36, u + 0.015, 0.42, "ember", 4); h.glow(u - 0.015, 0.36, u + 0.015, 0.42)
    return B, A


# ---------------------------------------------------------------------------- GHOUL (hunched, long arms)

GHOUL_BONES = {
    "Root": ((0, 0, 0), (0, 0, 0.3), None),
    "Body": ((0, 0.04, 0.9), (0, -0.12, 1.42), "Root"),
    "Head": ((0, -0.16, 1.42), (0, -0.26, 1.72), "Body"),
    "ArmL": ((0.22, -0.08, 1.38), (0.28, -0.14, 1.08), "Body"), "ForeArmL": ((0.28, -0.14, 1.08), (0.32, -0.24, 0.62), "ArmL"),
    "ArmR": ((-0.22, -0.08, 1.38), (-0.28, -0.14, 1.08), "Body"), "ForeArmR": ((-0.28, -0.14, 1.08), (-0.32, -0.24, 0.62), "ArmR"),
    "LegL": ((0.1, 0.04, 0.9), (0.12, -0.06, 0.5), "Root"), "ShinL": ((0.12, -0.06, 0.5), (0.12, 0.04, 0.04), "LegL"),
    "LegR": ((-0.1, 0.04, 0.9), (-0.12, -0.06, 0.5), "Root"), "ShinR": ((-0.12, -0.06, 0.5), (-0.12, 0.04, 0.04), "LegR"),
}


def ghoul():
    use_bones(GHOUL_BONES, lambda n, p: n == "Body")
    A = Atlas()
    R = pack(A, [("torso", 48, 28), ("head", 40, 22), ("jaw", 20, 8), ("ear", 8, 10), ("upper", 12, 14), ("fore", 12, 16),
                 ("hand", 12, 8), ("claw", 4, 6), ("thigh", 12, 14), ("shin", 12, 14), ("foot", 12, 8), ("cloth", 40, 14), ("rope", 32, 4), ("tooth", 4, 4)])
    B = Builder()
    T = [(1.5, -0.12, (0.13, 0.1, 0.08)), (1.44, -0.1, (0.24, 0.15, 0.1)), (1.32, -0.07, (0.25, 0.17, 0.13)),
         (1.18, -0.03, (0.2, 0.14, 0.12)), (1.04, 0.0, (0.15, 0.11, 0.1)), (0.92, 0.03, (0.16, 0.11, 0.1))]
    B.loft(R["torso"], [(0, cy, z, egg(rx, yb, yf, 14)) for z, cy, (rx, yb, yf) in T], bone="Body")
    B.loft(R["cloth"], [(0, 0.03, 1.0, egg(0.17, 0.12, 0.11, 14)), (0, 0.03, 0.86, egg(0.2, 0.15, 0.14, 14)),
                        (0, 0.02, 0.68, shag(0.22, 0.16, 0.16, 14, jag=0.09))], cap_top=False, cap_bot=False, bone="Body")
    B.loft(R["rope"], [(0, 0.03, 1.0, egg(0.172, 0.122, 0.112, 14)), (0, 0.03, 0.97, egg(0.172, 0.122, 0.112, 14))], cap_top=False, cap_bot=False, bone="Body")
    Hd = [(1.74, (0.06, 0.06, 0.05)), (1.71, (0.12, 0.12, 0.1)), (1.65, (0.14, 0.13, 0.13)), (1.58, (0.13, 0.11, 0.15)),
          (1.52, (0.1, 0.08, 0.14)), (1.48, (0.06, 0.05, 0.1))]
    B.loft(R["head"], [(0, -0.2, z, egg(rx, yb, yf, 14, {6: 1.06, 8: 1.05} if z > 1.62 else {})) for z, (rx, yb, yf) in Hd], bone="Head")
    B.loft(R["jaw"], [(0, -0.28, 1.53, egg(0.09, 0.05, 0.08, 10)), (0, -0.29, 1.47, egg(0.07, 0.04, 0.07, 10)), (0, -0.28, 1.44, egg(0.03, 0.02, 0.03, 10))], bone="Head")
    for s in (1, -1):
        m = s < 0
        arm, fore, legb, shin = hv.side("Arm", s), hv.side("ForeArm", s), hv.side("Leg", s), hv.side("Shin", s)
        tube(B, R["ear"], [(0.12, -0.18, 1.64), (0.2, -0.16, 1.7), (0.27, -0.14, 1.76)], [(0.04, 0.015), (0.025, 0.01), (0.003, 0.003)], bone="Head", n=5, mirror=m)
        for k in range(2):
            tube(B, R["tooth"], [(0.03 + 0.03 * k, -0.33, 1.5), (0.03 + 0.03 * k, -0.34, 1.54)], [0.008, 0.002], bone="Head", n=4, mirror=m)
        tube(B, R["upper"], [(0.2, -0.08, 1.4), (0.25, -0.11, 1.22), (0.28, -0.14, 1.08)], [0.06, 0.05, 0.045], bone=arm, n=8, mirror=m)
        tube(B, R["fore"], [(0.28, -0.14, 1.1), (0.3, -0.19, 0.85), (0.32, -0.24, 0.66)], [0.045, 0.04, 0.035], bone=fore, n=8, mirror=m)
        tube(B, R["hand"], [(0.32, -0.24, 0.67), (0.33, -0.27, 0.6), (0.33, -0.28, 0.56)], [(0.05, 0.03), (0.06, 0.03), (0.05, 0.025)], bone=fore, n=8, mirror=m)
        for k in range(3):
            x = 0.3 + 0.025 * k
            tube(B, R["claw"], [(x, -0.29, 0.56), (x, -0.33, 0.48), (x + 0.005, -0.31, 0.42)], [0.012, 0.009, 0.002], bone=fore, n=5, mirror=m)
        tube(B, R["thigh"], [(0.1, 0.04, 0.92), (0.12, -0.04, 0.7), (0.12, -0.06, 0.5)], [0.065, 0.055, 0.045], bone=legb, n=8, mirror=m)
        tube(B, R["shin"], [(0.12, -0.06, 0.52), (0.12, 0.0, 0.28), (0.12, 0.04, 0.07)], [0.045, 0.04, 0.035], bone=shin, n=8, mirror=m)
        tube(B, R["foot"], [(0.12, 0.06, 0.05), (0.12, -0.06, 0.03), (0.12, -0.16, 0.02)], [(0.045, 0.03), (0.055, 0.025), (0.04, 0.012)], bone=shin, n=8, mirror=m)
    for k in ("torso", "head", "jaw", "ear", "upper", "fore", "hand", "thigh", "shin", "foot"):
        R[k].fill("ghoul", 0.1)
    R["claw"].fill("bone", 0.3); R["tooth"].fill("bone", 0.6); R["cloth"].fill("leather", -0.7); R["rope"].fill("tan", 0.2)
    for u in (0.15, 0.4, 0.6, 0.85):
        R["cloth"].vline(u, "leather", 1, 0.2, 1.0)
    t = R["torso"]
    for v in (0.35, 0.45, 0.55, 0.65):                                           # ribs showing through the skin
        t.hline(v, "ghoul", 4, 0.38, 0.62); t.hline(v + 0.04, "ghoul", 1, 0.38, 0.62)
    t.vline(0.5, "ghoul", 1, 0.3, 0.75)
    h = R["head"]
    for u in (0.42, 0.58):
        h.box(u - 0.05, 0.42, u + 0.05, 0.6, "black", 0)
        h.box(u - 0.025, 0.46, u + 0.025, 0.56, "gold", 5); h.glow(u - 0.025, 0.46, u + 0.025, 0.56)
    h.box(0.47, 0.7, 0.53, 0.78, "ghoul", 0)
    R["jaw"].hline(0.15, "black", 0, 0.35, 0.65, thick=2)
    streaks(R["torso"], "ghoul", 4); streaks(R["head"], "ghoul", 3)
    return B, A


# ---------------------------------------------------------------------------- WRAITH (floating shroud)

WRAITH_BONES = {
    "Root": ((0, 0, 0), (0, 0, 0.2), None),
    "Body": ((0, 0, 0.2), (0, 0, 1.25), "Root"),
    "Head": ((0, -0.02, 1.2), (0, -0.06, 1.62), "Body"),
    "ArmL": ((0.24, -0.02, 1.15), (0.4, -0.14, 0.92), "Body"), "ForeArmL": ((0.4, -0.14, 0.92), (0.44, -0.3, 0.74), "ArmL"),
    "ArmR": ((-0.24, -0.02, 1.15), (-0.4, -0.14, 0.92), "Body"), "ForeArmR": ((-0.4, -0.14, 0.92), (-0.44, -0.3, 0.74), "ArmR"),
}


def wraith():
    use_bones(WRAITH_BONES, lambda n, p: n == "Body")
    A = Atlas()
    R = pack(A, [("robe", 64, 34), ("hood", 48, 24), ("face", 24, 14), ("sleeve", 24, 20), ("hand", 8, 8), ("trim", 48, 6), ("rune", 8, 8)])
    B = Builder()
    rings = []
    for k, (z, w, d) in enumerate(((1.2, 0.18, 0.15), (1.05, 0.26, 0.2), (0.8, 0.3, 0.24), (0.55, 0.33, 0.27), (0.32, 0.35, 0.29), (0.12, 0.38, 0.31))):
        prof = egg(w, d, d, 16) if k < 5 else [(x, y, (0.0 if i % 3 else 0.14) + (0.06 if i % 2 else 0.0)) for i, (x, y) in enumerate(egg(w, d, d, 16))]
        rings.append((0, 0.02, z, prof))
    B.loft(R["robe"], rings, cap_bot=False, bone="Body")
    B.loft(R["trim"], [(0, 0.02, 1.08, egg(0.27, 0.21, 0.21, 16)), (0, 0.02, 1.02, egg(0.28, 0.22, 0.22, 16))], cap_top=False, cap_bot=False, bone="Body")
    # hood: open at the front, a deep dark face inside
    def hood(z, rx, ry, open_y):
        return [(x, max(y, open_y)) for x, y in egg(rx, ry, ry, 16)]
    B.loft(R["hood"], [(0, 0.06, 1.68, hood(1.68, 0.07, 0.06, -0.2)), (0, 0.02, 1.62, hood(1.62, 0.17, 0.17, -0.15)),
                       (0, 0.0, 1.52, hood(1.52, 0.22, 0.21, -0.17)), (0, 0.0, 1.38, hood(1.38, 0.23, 0.22, -0.17)),
                       (0, 0.0, 1.24, hood(1.24, 0.24, 0.22, -0.15))], cap_bot=False, bone="Head")
    tube(B, R["face"], [(0, 0.12, 1.66), (0, 0.24, 1.6), (0, 0.32, 1.48)], [0.05, 0.035, 0.005], bone="Head", n=6)  # drooping hood tip
    for s in (1, -1):
        m = s < 0
        arm, fore = hv.side("Arm", s), hv.side("ForeArm", s)
        tube(B, R["sleeve"], [(0.2, -0.02, 1.18), (0.32, -0.08, 1.04), (0.4, -0.14, 0.92)], [0.07, 0.08, 0.09], bone=arm, n=10, mirror=m)
        tube(B, R["sleeve"], [(0.4, -0.14, 0.94), (0.43, -0.22, 0.82), (0.45, -0.28, 0.72)], [0.09, 0.11, 0.13], bone=fore, n=10, mirror=m,
             cap_b=False, jag=0.06)
        for k in range(3):
            x = 0.42 + 0.025 * k
            tube(B, R["hand"], [(x, -0.27, 0.76), (x, -0.33, 0.68), (x + 0.01, -0.34, 0.6)], [0.012, 0.009, 0.003], bone=fore, n=5, mirror=m)
    R["robe"].fill("wraith", -0.1); R["hood"].fill("wraith", 0.1); R["sleeve"].fill("wraith", 0.0)
    R["face"].fill("black", -1.0); R["hand"].fill("bone", 0.0)
    R["trim"].fill("spirit", 0.5); R["trim"].glow(0, 0, 1, 1)
    rb = R["robe"]
    for u in (0.1, 0.25, 0.4, 0.6, 0.75, 0.9):
        rb.vline(u, "wraith", 1, 0.15, 1.0); rb.vline(u + 0.02, "wraith", 4, 0.3, 0.9)
    rb.hline(0.9, "spirit", 3, thick=2); rb.glow(0.0, 0.9, 1.0, 0.96)
    R["sleeve"].hline(0.9, "spirit", 3); R["sleeve"].glow(0, 0.88, 1, 0.94)
    R["face"].fill("wraith", 0.0)
    hd = R["hood"]
    hd.box(0.36, 0.22, 0.64, 1.0, "black", 0)                                  # the void inside the hood
    hd.box(0.33, 0.3, 0.67, 1.0, "black", 1)
    hd.box(0.36, 0.22, 0.64, 1.0, "black", 0)
    for u in (0.44, 0.56):
        hd.box(u - 0.025, 0.42, u + 0.025, 0.55, "spirit", 5); hd.glow(u - 0.025, 0.42, u + 0.025, 0.55)
    return B, A


# ---------------------------------------------------------------------------- GOLEM / OBSIDIAN BRUTE (cut stone)

def golem(obsidian=False):
    use_bones(HUMAN_BONES, human_allowed)
    A = Atlas()
    R = pack(A, [("chest", 40, 24), ("belly", 32, 14), ("hips", 32, 12), ("head", 24, 14), ("shoulder", 24, 14), ("upper", 20, 14),
                 ("fore", 20, 14), ("fist", 24, 14), ("thigh", 20, 14), ("shin", 20, 14), ("foot", 20, 10), ("core", 12, 12), ("spike", 8, 10)])
    B = Builder()
    rock = "obsidian" if obsidian else "stone"
    sd = 11 if obsidian else 1
    boulder(B, R["chest"], 0, 0.0, 1.66, 1.18, 0.46, 0.3, sd, bone="Body", n=9)
    boulder(B, R["belly"], 0, 0.02, 1.24, 0.98, 0.3, 0.22, sd + 5, bone="Body")
    boulder(B, R["hips"], 0, 0.02, 1.02, 0.84, 0.27, 0.2, sd + 9, bone="Body")
    boulder(B, R["head"], 0, -0.06, 1.88, 1.66, 0.17, 0.16, sd + 13, bone="Head", n=7)
    boulder(B, R["core"], 0, -0.26, 1.5, 1.32, 0.09, 0.05, sd + 17, bone="Body", n=6)
    for s in (1, -1):
        m = s < 0
        arm, fore, legb, shin = hv.side("Arm", s), hv.side("ForeArm", s), hv.side("Leg", s), hv.side("Shin", s)
        boulder(B, R["shoulder"], 0.44, 0.0, 1.74, 1.46, 0.2, 0.2, sd + 20 + s, bone=arm, mirror=m)
        boulder(B, R["upper"], 0.5, -0.02, 1.48, 1.22, 0.15, 0.15, sd + 24 + s, bone=arm, mirror=m)
        boulder(B, R["fore"], 0.54, -0.05, 1.22, 0.92, 0.16, 0.16, sd + 28 + s, bone=fore, mirror=m)
        boulder(B, R["fist"], 0.56, -0.08, 0.94, 0.66, 0.2, 0.19, sd + 32 + s, bone=fore, n=8, mirror=m)
        boulder(B, R["thigh"], 0.17, 0.0, 0.92, 0.56, 0.15, 0.16, sd + 36 + s, bone=legb, mirror=m)
        boulder(B, R["shin"], 0.17, -0.01, 0.56, 0.16, 0.14, 0.15, sd + 40 + s, bone=shin, mirror=m)
        boulder(B, R["foot"], 0.17, -0.07, 0.17, 0.0, 0.17, 0.21, sd + 44 + s, bone=shin, mirror=m)
        if obsidian:
            for k in range(3):
                tube(B, R["spike"], [(0.36 + 0.07 * k, 0.04 * k, 1.68), (0.4 + 0.09 * k, 0.05 + 0.04 * k, 1.84 - 0.03 * k), (0.42 + 0.1 * k, 0.06 + 0.04 * k, 1.95 - 0.06 * k)],
                     [0.06, 0.04, 0.004], bone=arm, n=5, mirror=m)
    for k in ("chest", "belly", "hips", "head", "shoulder", "upper", "fore", "fist", "thigh", "shin", "foot"):
        R[k].fill(rock, 0.2 if not obsidian else 0.5)
    R["spike"].fill("obsidian", 0.8)
    glow = "ember" if obsidian else "gem"
    R["core"].fill(glow, 1.0); R["core"].glow(0, 0, 1, 1)
    h = R["head"]
    for u in (0.4, 0.6):
        h.box(u - 0.05, 0.45, u + 0.05, 0.6, glow, 5); h.glow(u - 0.05, 0.45, u + 0.05, 0.6)
    h.hline(0.38, rock, 0, 0.3, 0.7)
    if not obsidian:
        for k in ("shoulder", "chest", "head"):
            R[k].fill("green", -0.2, v0=0.0, v1=0.3)                            # moss on top
            for j in range(6):
                R[k].dot((j * 0.37) % 1, 0.32 + (j % 3) * 0.04, "green", 2)
    else:
        for k, n in (("chest", 6), ("belly", 3), ("fore", 2), ("fist", 3), ("thigh", 2), ("shin", 2), ("shoulder", 2)):
            r_ = R[k]
            for j in range(n):                                                  # glowing magma veins
                u = (j * 0.31 + 0.1) % 1.0
                r_.vline(u, "ember", 4, 0.2, 0.8); r_.glow(u, 0.2, u + 1.0 / r_.w, 0.8)
    for k in ("chest", "fist", "shoulder", "shin"):                             # chips and cracks
        for j in range(5):
            R[k].dot((j * 0.53) % 1, 0.3 + (j * 0.17) % 0.6, rock, 0)
    return B, A


# ---------------------------------------------------------------------------- BOMB SHROOM

SHROOM_BONES = {
    "Root": ((0, 0, 0), (0, 0, 0.2), None),
    "Body": ((0, 0, 0.3), (0, 0, 1.1), "Root"),
    "LegL": ((0.11, 0, 0.32), (0.12, -0.02, 0.0), "Root"), "ShinL": ((0.12, -0.02, 0.12), (0.12, -0.04, 0.0), "LegL"),
    "LegR": ((-0.11, 0, 0.32), (-0.12, -0.02, 0.0), "Root"), "ShinR": ((-0.12, -0.02, 0.12), (-0.12, -0.04, 0.0), "LegR"),
}


def bomb_shroom():
    use_bones(SHROOM_BONES, lambda n, p: n == "Body")
    A = Atlas()
    R = pack(A, [("cap", 64, 30), ("under", 48, 8), ("stem", 40, 22), ("leg", 8, 10), ("foot", 12, 8), ("fuse", 8, 12), ("spark", 8, 8)])
    B = Builder()
    B.loft(R["cap"], [(0, 0, 1.1, egg(0.12, 0.12, 0.12, 18)), (0, 0, 1.05, egg(0.33, 0.33, 0.33, 18)), (0, 0, 0.95, egg(0.47, 0.46, 0.46, 18)),
                      (0, 0, 0.84, egg(0.53, 0.52, 0.52, 18)), (0, 0, 0.76, egg(0.52, 0.5, 0.5, 18))], cap_bot=False, bone="Body")
    B.loft(R["under"], [(0, 0, 0.76, egg(0.52, 0.5, 0.5, 18)), (0, 0, 0.73, egg(0.36, 0.35, 0.35, 18)), (0, 0, 0.72, egg(0.18, 0.18, 0.18, 18))],
           cap_top=False, bone="Body")
    B.loft(R["stem"], [(0, 0, 0.76, egg(0.2, 0.2, 0.2, 14)), (0, 0, 0.6, egg(0.25, 0.24, 0.26, 14)), (0, 0, 0.42, egg(0.27, 0.25, 0.28, 14)),
                       (0, 0, 0.3, egg(0.24, 0.22, 0.24, 14)), (0, 0, 0.24, egg(0.16, 0.15, 0.16, 14))], bone="Body")
    tube(B, R["fuse"], [(0, 0.0, 1.08), (0.02, 0.02, 1.2), (0.07, 0.0, 1.28), (0.1, -0.03, 1.3)], [0.025, 0.022, 0.02, 0.018], bone="Body", n=6)
    B.loft(R["spark"], [(0.1, -0.03, 1.36, ell(0.01, 0.01, 6)), (0.1, -0.03, 1.32, ell(0.05, 0.05, 6)), (0.1, -0.03, 1.28, ell(0.01, 0.01, 6))], bone="Body")
    for s in (1, -1):
        m = s < 0
        legb, shin = hv.side("Leg", s), hv.side("Shin", s)
        tube(B, R["leg"], [(0.11, 0.0, 0.28), (0.12, -0.01, 0.12)], [0.045, 0.04], bone=legb, n=8, mirror=m)
        tube(B, R["foot"], [(0.12, 0.03, 0.06), (0.12, -0.05, 0.04), (0.12, -0.12, 0.03)], [(0.06, 0.05), (0.065, 0.04), (0.045, 0.02)],
             bone=shin, n=8, mirror=m)
    c = R["cap"]
    c.fill("cap", 0.2)
    for (u, v, r_) in ((0.5, 0.45, 0.05), (0.32, 0.6, 0.04), (0.68, 0.62, 0.04), (0.15, 0.4, 0.05), (0.85, 0.42, 0.05), (0.05, 0.7, 0.03),
                       (0.95, 0.72, 0.03), (0.42, 0.22, 0.035), (0.6, 0.25, 0.03), (0.25, 0.85, 0.03), (0.75, 0.86, 0.03)):
        c.box(u - r_, v - r_ * 1.4, u + r_, v + r_ * 1.4, "cloth", 4)            # white spots
        c.box(u - r_ * 0.6, v - r_, u + r_ * 0.6, v + r_, "cloth", 5)
    R["under"].fill("tan", 0.4)
    for u in [i / 18 for i in range(18)]:
        R["under"].vline(u, "tan", 2)                                             # gills
    st = R["stem"]
    st.fill("cloth", 0.0)
    for u in (0.42, 0.58):                                                        # angry face
        st.box(u - 0.035, 0.32, u + 0.035, 0.45, "black", 0)
        st.box(u - 0.015, 0.36, u + 0.015, 0.42, "ember", 5); st.glow(u - 0.015, 0.36, u + 0.015, 0.42)
    st.box(0.36, 0.26, 0.47, 0.3, "black", 0); st.box(0.53, 0.26, 0.64, 0.3, "black", 0)   # angry brows
    st.box(0.43, 0.58, 0.57, 0.66, "black", 0)                                    # gritted mouth
    st.hline(0.62, "cloth", 4, 0.44, 0.56)
    R["leg"].fill("cloth", -0.4); R["foot"].fill("leather", -0.3)
    R["fuse"].fill("tan", -0.2); R["spark"].fill("ember", 1.0); R["spark"].glow(0, 0, 1, 1)
    return B, A


# ---------------------------------------------------------------------------- FIRE IMP (flyer)

IMP_BONES = {
    "Root": ((0, 0, -0.35), (0, 0, -0.2), None),
    "Body": ((0, 0, -0.25), (0, 0, 0.2), "Root"),
    "Head": ((0, -0.03, 0.18), (0, -0.05, 0.55), "Body"),
    "ArmL": ((0.15, 0, 0.12), (0.26, -0.08, -0.05), "Body"), "ArmR": ((-0.15, 0, 0.12), (-0.26, -0.08, -0.05), "Body"),
    "WingL": ((0.1, 0.1, 0.12), (0.62, 0.14, 0.24), "Body"), "WingR": ((-0.1, 0.1, 0.12), (-0.62, 0.14, 0.24), "Body"),
}


def fire_imp():
    use_bones(IMP_BONES, lambda n, p: n == "Body")
    A = Atlas()
    R = pack(A, [("body", 40, 20), ("head", 36, 20), ("horn", 8, 10), ("arm", 12, 12), ("leg", 12, 12), ("tail", 24, 8), ("wing", 44, 24),
                 ("finger", 8, 10), ("flame", 12, 12), ("tooth", 4, 4)])
    B = Builder()
    B.loft(R["body"], [(0, 0.01, 0.16, egg(0.08, 0.07, 0.07, 12)), (0, 0.01, 0.1, egg(0.14, 0.11, 0.12, 12)), (0, 0.0, -0.04, egg(0.16, 0.12, 0.16, 12)),
                       (0, 0.01, -0.15, egg(0.13, 0.1, 0.12, 12)), (0, 0.02, -0.21, egg(0.06, 0.05, 0.05, 12))], bone="Body")
    B.loft(R["head"], [(0, -0.03, 0.47, egg(0.07, 0.07, 0.06, 12)), (0, -0.03, 0.42, egg(0.14, 0.13, 0.13, 12)),
                       (0, -0.04, 0.32, egg(0.16, 0.13, 0.15, 12, {6: 1.06, 10: 1.06})), (0, -0.04, 0.23, egg(0.12, 0.09, 0.13, 12)),
                       (0, -0.03, 0.18, egg(0.06, 0.05, 0.07, 12))], bone="Head")
    for s in (1, -1):
        m = s < 0
        tube(B, R["horn"], [(0.08, -0.02, 0.43), (0.13, 0.0, 0.52), (0.14, 0.04, 0.6), (0.12, 0.08, 0.64)], [0.035, 0.026, 0.015, 0.003], bone="Head", n=6, mirror=m)
        tube(B, R["tooth"], [(0.04, -0.17, 0.26), (0.042, -0.175, 0.22)], [0.01, 0.002], bone="Head", n=4, mirror=m)
        tube(B, R["arm"], [(0.14, 0.0, 0.1), (0.21, -0.05, 0.02), (0.25, -0.1, -0.06)], [0.035, 0.03, 0.028], bone=hv.side("Arm", s), n=6, mirror=m)
        tube(B, R["finger"], [(0.25, -0.1, -0.06), (0.27, -0.14, -0.09), (0.27, -0.17, -0.08)], [0.03, 0.02, 0.005], bone=hv.side("Arm", s), n=5, mirror=m)
        tube(B, R["leg"], [(0.07, 0.02, -0.17), (0.09, -0.03, -0.27), (0.09, 0.02, -0.36), (0.09, -0.04, -0.4)], [0.04, 0.032, 0.025, 0.01], bone="Body", n=6, mirror=m)
        outline = [(0.1, 0.24), (0.3, 0.38), (0.5, 0.44), (0.66, 0.34), (0.58, 0.2), (0.5, 0.26), (0.42, 0.1), (0.32, 0.18), (0.22, 0.02), (0.12, 0.08)]
        if m:
            outline = [(-x, z) for x, z in reversed(outline)]
        wing = hv.side("Wing", s)
        B.plate(R["wing"], outline, 0.1, thick=0.012, bone=wing)
        for tip in ((0.66, 0.34), (0.42, 0.1), (0.22, 0.02)):
            tube(B, R["finger"], [(0.1, 0.092, 0.2), (tip[0], 0.092, tip[1])], [0.014, 0.004], bone=wing, n=5, mirror=m)
    tube(B, R["tail"], [(0, 0.1, -0.12), (0, 0.24, -0.2), (0, 0.34, -0.12), (0, 0.4, 0.0)], [0.03, 0.025, 0.02, 0.012], bone="Body", n=6)
    B.loft(R["tooth"], [(0, 0.42, 0.06, ell(0.005, 0.005, 4)), (0, 0.41, 0.02, ell(0.04, 0.02, 4)), (0, 0.4, -0.02, ell(0.005, 0.005, 4))], bone="Body")
    # a fireball cupped in its right hand
    B.loft(R["flame"], [(-0.28, -0.2, 0.08, ell(0.01, 0.01, 8)), (-0.28, -0.2, 0.02, ell(0.07, 0.07, 8)), (-0.28, -0.2, -0.05, ell(0.08, 0.08, 8)),
                        (-0.28, -0.2, -0.1, ell(0.04, 0.04, 8))], bone="ArmR")
    for k in ("body", "head", "arm", "leg", "tail"):
        R[k].fill("imp", 0.2)
    R["body"].fill("orange", -0.3, u0=0.38, u1=0.62)                              # warm belly
    R["horn"].fill("coal", 0.6); R["finger"].fill("coal", 0.4); R["wing"].fill("wine", 0.0); R["tooth"].fill("cloth", 0.7)
    for u in (0.25, 0.5, 0.75):
        R["wing"].vline(u, "wine", 1)
    R["flame"].fill("ember", 1.2); R["flame"].glow(0, 0, 1, 1)
    h = R["head"]
    for u in (0.41, 0.59):
        h.box(u - 0.04, 0.4, u + 0.04, 0.55, "gold", 5); h.glow(u - 0.04, 0.4, u + 0.04, 0.55)
        h.box(u - 0.01, 0.43, u + 0.01, 0.53, "black", 0)
    h.box(0.4, 0.66, 0.6, 0.72, "black", 0)                                        # wicked grin
    h.hline(0.66, "cloth", 4, 0.42, 0.58)
    return B, A


CREATURES.update({
    "IceWolf": ice_wolf, "Snowman": snowman, "Ghoul": ghoul, "Wraith": wraith, "Golem": golem,
    "ObsidianBrute": lambda: golem(obsidian=True), "BombShroom": bomb_shroom, "FireImp": fire_imp,
})

# ----------------------------------------------------------------------------- build / export / preview

def build(name, preview=False):
    gm.reset()
    B, A = CREATURES[name]()
    mesh = B.finish(name)
    maps = hv.bake_maps(mesh, hv.TEX)
    img = hv.write_texture(hv.compose(A, maps), name)
    mesh.data.materials.clear()
    mat = bpy.data.materials.new("M_Char_" + name)
    if preview:
        mat.use_nodes = True
        tn = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = img
        img.colorspace_settings.name = "sRGB"
        img.alpha_mode = "NONE"
        tn.interpolation = "Closest"
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Roughness"].default_value = 0.9
        mat.node_tree.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    mesh.data.materials.append(mat)
    rig = ch.armature()
    mesh.parent = rig
    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    return mesh, rig


def export(name):
    old = ch.OUT_MODELS
    ch.OUT_MODELS = OUT_MODELS
    try:
        ch.export(name)
    finally:
        ch.OUT_MODELS = old


def preview(name):
    import render_previews as rp
    build(name, preview=True)
    bpy.context.scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
    rp.setup_render(1200, 1200, transparent=False)
    cam = next((a[6:] for a in sys.argv if a.startswith("--cam=")), None)
    if cam:
        v = [float(x) for x in cam.split(",")]
        rp.camera(tuple(v[0:3]), tuple(v[3:6]), lens=v[6] if len(v) > 6 else 50)
    else:
        rp.camera((1.6, -5.2, 2.0), (0, 0, 1.15), lens=50)
    out = next((a[6:] for a in sys.argv if a.startswith("--out=")), None)
    bpy.context.scene.render.filepath = out or os.path.join(gm.ROOT, "Tools", "Blender", "creature.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = [a for a in args if a in CREATURES] or list(CREATURES)
    if "--preview" in args:
        preview(names[0])
    else:
        for n in names:
            build(n)
            export(n)
