"""
MultiBash hero generator v4: one skinned character per hero with a baked painted-style texture.

  blender -b --factory-startup -P Tools/Blender/characters.py -- Knight Ranger Mage Alchemist [--preview]

Pipeline per hero:
  1. Body: one continuous mesh grown from a joint graph (Skin modifier + subdivision) - no floating parts.
  2. Clothing/armor: fitted shells grown from subsets of the same graph (slightly larger radii) so they hug the body,
     plus rigid accessories (helmets, pauldrons, belts...) tagged with the bone they ride on.
  3. Armature: Root > Body > Head / ArmL > ForeArmL / ArmR > ForeArmR, Root > LegL > ShinL / LegR > ShinR
     (same names the game's ProceduralRig animates). Weights: smooth distance-to-bone blending with anatomy rules.
  4. Texture: everything is unwrapped to one atlas and baked (Cycles) from the palette colors with ambient occlusion,
     cavity darkening, edge highlights and a soft top light -> T_Char_<Name>.png. Alpha carries the glow mask
     (PixelLit: alpha 0 = flat, ~0.125 = emissive).
  5. Export: Assets/_Game/Art/Models/Characters/<Name>.fbx with material M_Char_<Name>.
"""
import bpy
import bmesh
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import generate_models as gm  # noqa: E402

part, soft, _finish = gm.part, gm.soft, gm._finish
ROOT = gm.ROOT
OUT_MODELS = os.path.join(ROOT, "Assets", "_Game", "Art", "Models", "Characters")
OUT_TEX = os.path.join(ROOT, "Assets", "_Game", "Art", "Textures", "Characters")
PALETTE_PNG = os.path.join(ROOT, "Assets", "_Game", "Art", "Textures", "T_Palette.png")
TEX_SIZE = 512

# ----------------------------------------------------------------------------- joint graph (Z up, facing -Y, ~1.9 m)

G = {
    "P": ((0, 0, 0.95), (0.16, 0.11)), "W": ((0, 0, 1.12), (0.13, 0.095)), "C": ((0, -0.01, 1.33), (0.2, 0.13)),
    "U": ((0, 0, 1.46), (0.215, 0.125)), "N": ((0, 0, 1.56), (0.065, 0.065)), "NT": ((0, 0.005, 1.66), (0.055, 0.055)),
}
for _s, _k in ((1, "L"), (-1, "R")):
    G.update({
        "S" + _k: ((0.16 * _s, 0, 1.5), (0.07, 0.07)), "D" + _k: ((0.24 * _s, 0, 1.46), (0.08, 0.076)),
        "M" + _k: ((0.275 * _s, 0, 1.36), (0.072, 0.07)), "E" + _k: ((0.3 * _s, 0.005, 1.25), (0.056, 0.056)),
        "F" + _k: ((0.312 * _s, -0.01, 1.14), (0.064, 0.06)), "X" + _k: ((0.32 * _s, -0.012, 0.99), (0.04, 0.04)),
        "H" + _k: ((0.322 * _s, -0.02, 0.91), (0.042, 0.058)), "HT" + _k: ((0.322 * _s, -0.025, 0.85), (0.034, 0.045)),
        "I" + _k: ((0.1 * _s, 0, 0.9), (0.11, 0.11)), "T" + _k: ((0.105 * _s, -0.01, 0.74), (0.096, 0.096)),
        "K" + _k: ((0.105 * _s, -0.01, 0.53), (0.07, 0.072)), "Q" + _k: ((0.105 * _s, 0.014, 0.38), (0.078, 0.078)),
        "A" + _k: ((0.105 * _s, 0, 0.11), (0.048, 0.052)), "FT" + _k: ((0.105 * _s, -0.045, 0.055), (0.062, 0.05)),
        "TO" + _k: ((0.105 * _s, -0.15, 0.04), (0.05, 0.032)),
    })
EDGES = [("P", "W"), ("W", "C"), ("C", "U"), ("U", "N"), ("N", "NT")]
for _k in ("L", "R"):
    EDGES += [("U", "S" + _k), ("S" + _k, "D" + _k), ("D" + _k, "M" + _k), ("M" + _k, "E" + _k), ("E" + _k, "F" + _k),
              ("F" + _k, "X" + _k), ("X" + _k, "H" + _k), ("H" + _k, "HT" + _k),
              ("P", "I" + _k), ("I" + _k, "T" + _k), ("T" + _k, "K" + _k), ("K" + _k, "Q" + _k), ("Q" + _k, "A" + _k),
              ("A" + _k, "FT" + _k), ("FT" + _k, "TO" + _k)]

BONES = {   # name: (head, tail, parent)
    "Root": ((0, 0, 0), (0, 0, 0.3), None),
    "Body": ((0, 0, 0.95), (0, 0, 1.6), "Root"),
    "Head": ((0, 0, 1.62), (0, 0, 1.97), "Body"),
    "ArmL": ((0.17, 0, 1.5), (0.31, 0.005, 1.15), "Body"), "ForeArmL": ((0.31, 0.005, 1.15), (0.335, -0.025, 0.72), "ArmL"),
    "ArmR": ((-0.17, 0, 1.5), (-0.31, 0.005, 1.15), "Body"), "ForeArmR": ((-0.31, 0.005, 1.15), (-0.335, -0.025, 0.72), "ArmR"),
    "LegL": ((0.1, 0, 0.95), (0.105, -0.01, 0.53), "Root"), "ShinL": ((0.105, -0.01, 0.53), (0.105, -0.06, 0.05), "LegL"),
    "LegR": ((-0.1, 0, 0.95), (-0.105, -0.01, 0.53), "Root"), "ShinR": ((-0.105, -0.01, 0.53), (-0.105, -0.06, 0.05), "LegR"),
}

PIECES = []   # (object, bone or None)


def add(obj, bone=None):
    if isinstance(obj, list):
        for o in obj:
            add(o, bone)
        return obj
    PIECES.append((obj, bone))
    return obj


def sides(keys):
    """'S*' -> ['SL','SR'] expansion helper."""
    out = []
    for k in keys:
        if k.endswith("*"):
            out += [k[:-1] + "L", k[:-1] + "R"]
        else:
            out.append(k)
    return out


def shell(keys, color, mult=1.0, add_r=0.0, sub=1, override=None, bone=None):
    """Organic tube network through a subset of the joint graph (fitted shell when mult > 1)."""
    keys = sides(keys)
    override = override or {}
    idx = {k: i for i, k in enumerate(keys)}
    edges = [(idx[a], idx[b]) for a, b in EDGES if a in idx and b in idx]
    pts = []
    for k in keys:
        pos, r = G[k]
        r = override.get(k, (r[0] * mult + add_r, r[1] * mult + add_r))
        pts.append((pos, r))
    me = bpy.data.meshes.new("shell")
    me.from_pydata([p for p, _ in pts], edges, [])
    o = bpy.data.objects.new("shell", me)
    bpy.context.scene.collection.objects.link(o)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    m = o.modifiers.new("Skin", "SKIN")
    m.use_smooth_shade = True
    m.branch_smoothing = 0.6
    # one root per connected component
    parent = list(range(len(pts)))

    def find(a):
        while parent[a] != a:
            a = parent[a]
        return a
    for a, b in edges:
        parent[find(a)] = find(b)
    roots = set()
    for i, (_, r) in enumerate(pts):
        sv = me.skin_vertices[0].data[i]
        sv.radius = r
        c = find(i)
        sv.use_root = c not in roots
        roots.add(c)
    if sub:
        s = o.modifiers.new("Sub", "SUBSURF")
        s.levels = sub
        s.render_levels = sub
    for mod in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    _finish(o, (1, 1, 1), color)
    for p in o.data.polygons:
        p.use_smooth = True
    return add(o, bone)


def flare(z_top, z_bot, r_top, r_bot, color, y_scale=0.78, verts=16, bone="Body", y=0.0):
    """Fitted flared skirt/robe/coat from z_top down to z_bot."""
    o = soft("cone", (0, y, (z_top + z_bot) / 2), (r_bot * 2, r_bot * 2 * y_scale, z_top - z_bot), color, verts=verts,
             r2=0.5 * r_top / r_bot)
    return add(o, bone)


def ring(z, rx, ry, color, h=0.04, bone="Body", y=0.0, x=0.0, verts=14):
    return add(soft("cyl", (x, y, z), (rx * 2, ry * 2, h), color, verts=verts), bone)


def head(skin_c, dark, brows=None, face=True):
    """Shaped head (cranium + cheekbones + jaw) with a face. Rides on the Head bone."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=0.5, location=(0, 0, 1.775))
    o = bpy.context.active_object
    for v in o.data.vertices:
        x, y, z = v.co
        if z < -0.05:                       # narrow the jaw, push the chin forward
            t = min(1.0, (-z - 0.05) / 0.45)
            v.co.x *= 1 - 0.32 * t
            v.co.y = y * (1 - 0.15 * t) - 0.06 * t
        if y < -0.3:                        # flatter face plane
            v.co.y = -0.3 + (y + 0.3) * 0.5
    _finish(o, (0.235, 0.26, 0.3), skin_c)
    for p in o.data.polygons:
        p.use_smooth = True
    add(o, "Head")
    if not face:
        return
    for s in (-1, 1):
        add([soft("ico", (0.05 * s, -0.122, 1.793), (0.032, 0.02, 0.036), "black", sub=2),     # eyes
             soft("ico", (0.058 * s, -0.135, 1.802), (0.01, 0.006, 0.01), "white", sub=1),      # glints
             soft("cube", (0.055 * s, -0.124, 1.823), (0.06, 0.02, 0.016), brows or dark, rot=(0, -10 * s, 0)),   # brows
             soft("ico", (0.118 * s, 0.0, 1.775), (0.035, 0.05, 0.07), skin_c, sub=2)], "Head")         # ears
    add([soft("cone", (0, -0.14, 1.758), (0.04, 0.05, 0.065), dark, verts=6, rot=(-75, 0, 0)),          # nose
         soft("cube", (0, -0.128, 1.705), (0.055, 0.012, 0.012), dark)], "Head")                        # mouth


# ----------------------------------------------------------------------------- heroes

def knight():
    body = shell(["P", "W", "C", "U", "N", "NT", "S*", "D*", "M*", "E*", "F*", "X*", "H*", "HT*",
                  "I*", "T*", "K*", "Q*", "A*", "FT*", "TO*"], "steel_edge")                         # mail underlayer
    shell(["P", "W", "C", "U", "S*", "D*"], "steel", mult=1.12)                                       # cuirass
    shell(["I*", "T*", "K*"], "steel", mult=1.1)                                                      # cuisses
    shell(["K*", "Q*", "A*"], "steel_light", mult=1.12)                                               # greaves
    shell(["A*", "FT*", "TO*"], "steel_edge", mult=1.18)                                              # sabatons
    shell(["E*", "F*", "X*"], "steel", mult=1.12)                                                     # vambraces
    shell(["X*", "H*", "HT*"], "steel_edge", mult=1.18)                                               # gauntlets
    # breastplate ridge, gold straps, gorget
    add([part("ico", (0, -0.065, 1.36), (0.44, 0.24, 0.36), "steel_light", sub=1),
         part("cube", (0, -0.18, 1.37), (0.025, 0.03, 0.28), "steel"),
         part("cube", (0, -0.176, 1.37), (0.026, 0.03, 0.4), "gold_trim", rot=(0, 34, 0)),
         part("cube", (0, -0.176, 1.37), (0.026, 0.03, 0.4), "gold_trim", rot=(0, -34, 0)),
         part("cyl", (0, 0, 1.59), (0.27, 0.23, 0.08), "steel_edge", verts=8),
         part("cyl", (0, 0, 1.625), (0.22, 0.19, 0.04), "steel", verts=8)], "Body")
    # faulds and tabard
    for z, w, c in ((0.98, 0.42, "steel_edge"), (0.99, 0.4, "steel"), (0.9, 0.46, "steel_edge"), (0.91, 0.44, "steel_light")):
        add(part("cone", (0, 0, z), (w, w * 0.74, 0.09), c, verts=10, r2=0.44), "Body")
    add([part("cube", (0, -0.163, 0.8), (0.23, 0.02, 0.35), "steel_edge"),
         part("cube", (0, -0.17, 0.8), (0.2, 0.02, 0.32), "cloth_white"),
         part("cube", (0, -0.182, 0.83), (0.035, 0.012, 0.18), "black"),
         part("cube", (0, -0.182, 0.86), (0.12, 0.012, 0.035), "black"),
         ring(1.06, 0.17, 0.12, "gold_trim", h=0.06)], "Body")
    for s, arm, fore in ((1, "ArmL", "ForeArmL"), (-1, "ArmR", "ForeArmR")):
        add(part("ico", (0.25 * s, 0, 1.54), (0.25, 0.25, 0.2), "steel", sub=1), arm)                 # pauldron dome
        for k in range(3):
            z = 1.49 - k * 0.065
            add([part("cone", (0.275 * s, 0, z), (0.27 - k * 0.02, 0.25 - k * 0.02, 0.07), "steel_edge", verts=8, r2=0.42),
                 part("cone", (0.275 * s, 0, z + 0.012), (0.255 - k * 0.02, 0.235 - k * 0.02, 0.06),
                      "steel_light" if k == 0 else "steel", verts=8, r2=0.42)], arm)
        add(part("cyl", (0.275 * s, 0, 1.375), (0.2, 0.19, 0.02), "gold_trim", verts=8), arm)
        add([part("ico", (0.3 * s, 0.04, 1.25), (0.12, 0.1, 0.12), "steel_light", sub=1),             # couter
             part("cone", (0.32 * s, -0.012, 1.0), (0.14, 0.14, 0.12), "steel", verts=8, r2=0.33, rot=(180, 0, 0)),
             part("cyl", (0.32 * s, -0.012, 1.06), (0.145, 0.145, 0.02), "gold_trim", verts=8)], fore)
        leg, shin = ("LegL", "ShinL") if s > 0 else ("LegR", "ShinR")
        add([part("ico", (0.105 * s, -0.075, 0.53), (0.13, 0.09, 0.13), "steel_light", sub=1),       # knee cop
             part("cone", (0.105 * s, -0.11, 0.53), (0.1, 0.05, 0.1), "steel", verts=4, rot=(90, 0, 0))], shin)
    # bucket helm
    add([part("cyl", (0, 0, 1.79), (0.29, 0.31, 0.36), "steel", verts=8),
         part("cyl", (0, 0, 1.98), (0.27, 0.29, 0.03), "steel_light", verts=8),
         part("cyl", (0, 0, 1.63), (0.31, 0.33, 0.04), "steel_edge", verts=8),
         part("cyl", (0, 0, 1.89), (0.3, 0.32, 0.02), "steel", verts=8),
         part("cube", (0, -0.155, 1.78), (0.03, 0.03, 0.32), "steel"),
         part("cube", (-0.058, -0.152, 1.83), (0.07, 0.02, 0.04), "black"),
         part("cube", (0.058, -0.152, 1.83), (0.07, 0.02, 0.04), "black")], "Head")
    for x in (-0.05, 0.05):
        for z in (1.71, 1.68):
            add(part("cube", (x, -0.152, z), (0.015, 0.02, 0.015), "black"), "Head")
    return body


def ranger():
    shell(["N", "NT", "M*", "E*", "F*", "X*", "H*", "HT*"], "skin")              # exposed skin only
    shell(["P", "W", "C", "U", "N", "S*", "D*", "M*"], "ranger_green", mult=1.09,
          override={"MR": (0.085, 0.083), "ML": (0.085, 0.083)})                                       # tunic with short sleeves
    shell(["I*", "T*", "K*", "Q*"], "cloth_white", mult=1.06)                                          # leggings
    shell(["Q*", "A*", "FT*", "TO*"], "leather", mult=1.16, override={"QL": (0.095, 0.095), "QR": (0.095, 0.095)})   # tall boots
    shell(["F*", "X*"], "leather", mult=1.22)                                                          # bracers
    flare(1.1, 0.7, 0.16, 0.22, "ranger_green", y_scale=0.8)                                           # tunic skirt
    add([soft("cone", (0, -0.005, 0.715), (0.45, 0.36, 0.03), "green_dark", verts=16, r2=0.48),
         ring(1.06, 0.155, 0.115, "leather_dark", h=0.06),
         part("cube", (0, -0.125, 1.06), (0.07, 0.02, 0.06), "gold_trim"),
         soft("cone", (0, -0.12, 1.5), (0.15, 0.05, 0.12), "green_dark", verts=3, rot=(180, 0, 0)),     # V collar
         part("cube", (0, -0.14, 1.32), (0.035, 0.02, 0.48), "leather_dark", rot=(0, 35, 0)),          # strap
         soft("cyl", (0.1, 0.16, 1.38), (0.11, 0.11, 0.5), "leather", rot=(-12, 0, -22), verts=8),     # quiver
         soft("cyl", (0.03, 0.2, 1.62), (0.12, 0.12, 0.02), "leather_dark", rot=(-12, 0, -22), verts=8)], "Body")
    for i, (dx, c) in enumerate(((0.0, "cloth_red"), (0.06, "cloth_red"), (0.12, "white"))):
        add(soft("cone", (0.03 + dx, 0.2 + i * 0.005, 1.69), (0.05, 0.03, 0.15), c, rot=(-12, 0, -22), verts=3), "Body")
    for s in (-1, 1):
        shin = "ShinL" if s > 0 else "ShinR"
        add(soft("cone", (0.105 * s, 0.012, 0.4), (0.21, 0.21, 0.06), "leather_light", verts=12, r2=0.42), shin)   # boot fold
        fore = "ForeArmL" if s > 0 else "ForeArmR"
        add([ring(1.13, 0.085, 0.08, "leather_dark", h=0.015, bone=fore, x=0.312 * s, y=-0.01),
             ring(1.0, 0.06, 0.06, "leather_dark", h=0.015, bone=fore, x=0.32 * s, y=-0.012)], fore)
    head("skin", "skin_dark", brows="hair_blonde")
    add([soft("ico", (0, 0.03, 1.81), (0.265, 0.275, 0.27), "hair_blonde", sub=2),
         soft("cone", (0, 0.07, 1.66), (0.26, 0.16, 0.24), "hair_blonde", verts=8, r2=0.3, rot=(180, 0, 0)),
         soft("cone", (-0.07, -0.11, 1.86), (0.1, 0.05, 0.1), "hair_blonde", verts=4, rot=(-120, 0, 25)),
         soft("cone", (0.05, -0.115, 1.865), (0.1, 0.05, 0.09), "hair_blonde", verts=4, rot=(-120, 0, -20)),
         soft("cone", (0, 0.02, 1.9), (0.28, 0.3, 0.2), "ranger_green", verts=10, r2=0.18, rot=(-10, 0, 0)),
         soft("cyl", (0, 0.0, 1.84), (0.285, 0.305, 0.02), "green_dark", verts=10),
         soft("cone", (0, 0.15, 1.98), (0.1, 0.1, 0.24), "ranger_green", verts=6, rot=(-75, 0, 0)),
         soft("cone", (0.11, 0.06, 1.99), (0.03, 0.02, 0.22), "cloth_red", verts=3, rot=(-40, 25, 0))], "Head")


def mage():
    """Red-robed hooded sage with a long white beard (red robe, deliberately not a wide-brim witch)."""
    shell(["N", "NT", "X*", "H*", "HT*"], "skin")
    shell(["P", "W", "C", "U", "N", "S*", "D*", "M*", "E*", "F*"], "mage_red", mult=1.1)               # robe top + sleeves
    shell(["I*", "T*", "K*", "Q*", "A*"], "mage_red_dark", mult=1.08)                                   # under-robe legs
    shell(["A*", "FT*", "TO*"], "leather_dark", mult=1.15)                                             # slippers
    flare(1.12, 0.1, 0.165, 0.3, "mage_red", y_scale=0.8, verts=18)                                    # long robe
    add([soft("cone", (0, 0.0, 0.1), (0.62, 0.5, 0.05), "gold_trim", verts=18, r2=0.49),
         part("cube", (0, -0.215, 0.58), (0.13, 0.02, 0.9), "mage_red_dark"),                         # front panel
         part("cube", (-0.07, -0.22, 0.58), (0.012, 0.012, 0.9), "gold_trim"),
         part("cube", (0.07, -0.22, 0.58), (0.012, 0.012, 0.9), "gold_trim"),
         ring(1.07, 0.16, 0.12, "gold_trim", h=0.08),
         soft("cone", (0.1, -0.13, 0.92), (0.07, 0.03, 0.28), "gold_trim", verts=4, rot=(0, 10, 0)),
         soft("cone", (0, 0.0, 1.5), (0.52, 0.4, 0.16), "mage_red_dark", verts=12, r2=0.38),           # mantle
         soft("cone", (0, 0.0, 1.43), (0.53, 0.41, 0.02), "gold_trim", verts=12, r2=0.49),
         part("cube", (-0.09, -0.14, 1.25), (0.07, 0.02, 0.4), "cloth_white"),                        # stole
         part("cube", (0.09, -0.14, 1.25), (0.07, 0.02, 0.4), "cloth_white"),
         part("cube", (-0.09, -0.152, 1.15), (0.04, 0.01, 0.04), "rune_blue"),
         part("cube", (0.09, -0.152, 1.15), (0.04, 0.01, 0.04), "rune_blue"),
         soft("ico", (0, -0.15, 1.36), (0.06, 0.03, 0.08), "lightning", sub=1)], "Body")
    for s in (-1, 1):
        fore = "ForeArmL" if s > 0 else "ForeArmR"
        add([soft("cone", (0.315 * s, -0.01, 1.08), (0.2, 0.2, 0.22), "mage_red", verts=14, r2=0.3, rot=(180, 0, 0)),
             soft("cone", (0.315 * s, -0.01, 0.97), (0.21, 0.21, 0.03), "gold_trim", verts=14, r2=0.48)], fore)
    head("skin", "skin_dark", brows="cloth_white")
    add([soft("cone", (0, -0.12, 1.58), (0.2, 0.1, 0.36), "cloth_white", verts=10, rot=(172, 0, 0)),     # long beard
         soft("cone", (0, -0.13, 1.69), (0.18, 0.06, 0.08), "cloth_white", verts=8, rot=(180, 0, 0)),     # moustache
         soft("ico", (0, 0.075, 1.83), (0.34, 0.32, 0.36), "mage_red", sub=2),                         # hood
         soft("torus", (0, -0.075, 1.8), (0.3, 0.32, 0.4), "mage_red_dark", verts=16, rot=(90, 0, 0)),
         soft("cone", (0, 0.17, 1.88), (0.14, 0.14, 0.3), "mage_red", verts=6, rot=(-100, 0, 0)),
         soft("cyl", (0, -0.12, 1.96), (0.2, 0.03, 0.02), "gold_trim", verts=8)], "Head")


def alchemist():
    shell(["N", "NT"], "skin")
    shell(["P", "W", "C", "U", "N", "S*", "D*", "M*", "E*", "F*"], "cloth_white", mult=1.08)            # shirt
    shell(["P", "I*", "T*", "K*", "Q*", "A*"], "leather", mult=1.08)                                   # trousers
    shell(["Q*", "A*", "FT*", "TO*"], "leather_dark", mult=1.18, override={"QL": (0.098, 0.098), "QR": (0.098, 0.098)})   # boots
    shell(["F*", "X*", "H*", "HT*"], "leather_dark", mult=1.14)                                        # gloves
    add([soft("cone", (0, 0.0, 1.43), (0.5, 0.4, 0.3), "alch_orange", verts=14, r2=0.36),               # poncho
         soft("cone", (0, 0.0, 1.285), (0.51, 0.41, 0.03), "alch_dark", verts=14, r2=0.49),
         soft("cone", (0, 0.0, 1.6), (0.3, 0.26, 0.1), "alch_dark", verts=10, r2=0.4),                 # rolled hood
         ring(1.06, 0.165, 0.12, "leather", h=0.06),
         part("cube", (0, -0.13, 1.06), (0.07, 0.02, 0.06), "gold_trim"),
         soft("cube", (0, 0.18, 1.28), (0.3, 0.14, 0.34), "leather"),                                  # backpack
         soft("cube", (0, 0.26, 1.18), (0.28, 0.04, 0.1), "leather_dark"),
         soft("cyl", (-0.08, 0.19, 1.52), (0.07, 0.07, 0.15), "poison", verts=8),
         soft("cyl", (0.08, 0.19, 1.52), (0.07, 0.07, 0.15), "gem_blue", verts=8),
         soft("cyl", (-0.17, -0.08, 1.0), (0.08, 0.08, 0.12), "gem_red", verts=8),
         soft("cyl", (0.17, -0.08, 1.0), (0.08, 0.08, 0.12), "poison", verts=8),
         soft("cube", (0.2, 0.02, 0.97), (0.08, 0.14, 0.12), "leather"),
         soft("cube", (-0.2, 0.04, 0.97), (0.07, 0.12, 0.1), "leather_light")], "Body")
    for s in (-1, 1):
        shin = "ShinL" if s > 0 else "ShinR"
        add(soft("cone", (0.105 * s, 0.012, 0.4), (0.21, 0.21, 0.06), "leather_light", verts=12, r2=0.42), shin)
    head("skin", "skin_dark", brows="hair_brown")
    add([soft("ico", (0, 0.03, 1.82), (0.27, 0.28, 0.26), "hair_brown", sub=2),
         soft("cone", (-0.06, -0.105, 1.89), (0.11, 0.06, 0.11), "hair_brown", verts=4, rot=(-120, 0, 25)),
         soft("cone", (0.06, -0.11, 1.9), (0.1, 0.06, 0.1), "hair_brown", verts=4, rot=(-120, 0, -25)),
         soft("cyl", (0, 0, 1.86), (0.27, 0.29, 0.03), "leather", verts=12),
         soft("cyl", (-0.055, -0.13, 1.87), (0.085, 0.085, 0.04), "gold", rot=(90, 0, 0), verts=10),
         soft("cyl", (0.055, -0.13, 1.87), (0.085, 0.085, 0.04), "gold", rot=(90, 0, 0), verts=10),
         soft("cyl", (-0.055, -0.152, 1.87), (0.06, 0.06, 0.01), "glass", rot=(90, 0, 0), verts=10),
         soft("cyl", (0.055, -0.152, 1.87), (0.06, 0.06, 0.01), "glass", rot=(90, 0, 0), verts=10),
         soft("cone", (0, -0.1, 1.64), (0.22, 0.12, 0.07), "alch_dark", verts=10, r2=0.4)], "Head")      # scarf


HEROES = {"Knight": knight, "Ranger": ranger, "Mage": mage, "Alchemist": alchemist}

# ----------------------------------------------------------------------------- rig + weights


def seg_dist(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    L = sum(c * c for c in ab) or 1e-9
    t = max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / L))
    q = [a[i] + ab[i] * t for i in range(3)]
    return math.dist(p, q), t


def allowed(name, p):
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
    return True   # Body


def weigh(obj):
    """Smooth distance-based skin weights (two closest allowed bones, inverse-power blend)."""
    for b in BONES:
        if b != "Root" and b not in obj.vertex_groups:
            obj.vertex_groups.new(name=b)
    mw = obj.matrix_world
    for v in obj.data.vertices:
        p = tuple(mw @ v.co)
        cands = []
        for b, (h, t, _) in BONES.items():
            if not allowed(b, p):
                continue
            d, _ = seg_dist(p, h, t)
            cands.append((d, b))
        if not cands:
            cands = [(0.0, "Body")]
        cands.sort()
        best = cands[:2]
        ws = [1.0 / (d + 0.015) ** 5 for d, _ in best]
        tot = sum(ws)
        for (d, b), w in zip(best, ws):
            if w / tot > 0.02:
                obj.vertex_groups[b].add([v.index], w / tot, "REPLACE")


def rigid(obj, bone):
    for b in BONES:
        if b != "Root" and b not in obj.vertex_groups:
            obj.vertex_groups.new(name=b)
    obj.vertex_groups[bone].add([v.index for v in obj.data.vertices], 1.0, "REPLACE")


def armature():
    arm = bpy.data.armatures.new("Rig")
    o = bpy.data.objects.new("Rig", arm)
    bpy.context.scene.collection.objects.link(o)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    for name, (h, t, par) in BONES.items():
        b = arm.edit_bones.new(name)
        b.head, b.tail = h, t
        b.roll = 0
        eb[name] = b
    for name, (_, _, par) in BONES.items():
        if par:
            eb[name].parent = eb[par]
            eb[name].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    return o

# ----------------------------------------------------------------------------- painted bake


def bake_material(name, img):
    """Bake shader: palette color x AO x cavity + edge highlight + soft top light -> emission. Target image node active."""
    mat = bpy.data.materials.new("BAKE_" + name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    uv = N("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    pal = N("ShaderNodeTexImage"); pal.image = bpy.data.images.load(PALETTE_PNG, check_existing=True); pal.interpolation = "Closest"
    nt.links.new(uv.outputs["UV"], pal.inputs["Vector"])
    ao = N("ShaderNodeAmbientOcclusion"); ao.samples = 24; ao.inputs["Distance"].default_value = 0.12
    aomix = N("ShaderNodeMapRange"); aomix.inputs["To Min"].default_value = 0.5; aomix.inputs["To Max"].default_value = 1.0
    nt.links.new(ao.outputs["AO"], aomix.inputs["Value"])
    geo = N("ShaderNodeNewGeometry")
    edge = N("ShaderNodeMapRange")       # convex edges -> highlight
    edge.inputs["From Min"].default_value = 0.58; edge.inputs["From Max"].default_value = 0.72
    nt.links.new(geo.outputs["Pointiness"], edge.inputs["Value"])
    cav = N("ShaderNodeMapRange")        # concave creases -> darker
    cav.inputs["From Min"].default_value = 0.47; cav.inputs["From Max"].default_value = 0.4
    cav.inputs["To Min"].default_value = 1.0; cav.inputs["To Max"].default_value = 0.7
    nt.links.new(geo.outputs["Pointiness"], cav.inputs["Value"])
    sep = N("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Normal"], sep.inputs["Vector"])
    top = N("ShaderNodeMapRange")        # painted key light from above
    top.inputs["From Min"].default_value = -1; top.inputs["From Max"].default_value = 1
    top.inputs["To Min"].default_value = 0.82; top.inputs["To Max"].default_value = 1.12
    nt.links.new(sep.outputs["Z"], top.inputs["Value"])
    m1 = N("ShaderNodeMix"); m1.data_type = "RGBA"; m1.blend_type = "MULTIPLY"; m1.inputs["Factor"].default_value = 1
    nt.links.new(pal.outputs["Color"], m1.inputs["A"]); nt.links.new(aomix.outputs["Result"], m1.inputs["B"])
    m2 = N("ShaderNodeMix"); m2.data_type = "RGBA"; m2.blend_type = "MULTIPLY"; m2.inputs["Factor"].default_value = 1
    nt.links.new(m1.outputs["Result"], m2.inputs["A"]); nt.links.new(cav.outputs["Result"], m2.inputs["B"])
    m3 = N("ShaderNodeMix"); m3.data_type = "RGBA"; m3.blend_type = "MULTIPLY"; m3.inputs["Factor"].default_value = 1
    nt.links.new(m2.outputs["Result"], m3.inputs["A"]); nt.links.new(top.outputs["Result"], m3.inputs["B"])
    hl = N("ShaderNodeMath"); hl.operation = "MULTIPLY"; hl.inputs[1].default_value = 0.14
    nt.links.new(edge.outputs["Result"], hl.inputs[0])
    m4 = N("ShaderNodeMix"); m4.data_type = "RGBA"; m4.blend_type = "ADD"
    m4.inputs["B"].default_value = (1, 0.97, 0.9, 1)
    nt.links.new(hl.outputs["Value"], m4.inputs["Factor"]); nt.links.new(m3.outputs["Result"], m4.inputs["A"])
    em = N("ShaderNodeEmission"); nt.links.new(m4.outputs["Result"], em.inputs["Color"])
    out = N("ShaderNodeOutputMaterial"); nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    target = N("ShaderNodeTexImage"); target.image = img
    nt.nodes.active = target
    # glow mask material output (palette alpha in the glow band) - second bake pass swaps this in
    glow = N("ShaderNodeMapRange"); glow.name = "GLOW"
    glow.inputs["From Min"].default_value = 0.06; glow.inputs["From Max"].default_value = 0.07
    nt.links.new(pal.outputs["Alpha"], glow.inputs["Value"])
    gl2 = N("ShaderNodeMapRange"); gl2.name = "GLOW2"
    gl2.inputs["From Min"].default_value = 0.19; gl2.inputs["From Max"].default_value = 0.18
    nt.links.new(pal.outputs["Alpha"], gl2.inputs["Value"])
    gm_ = N("ShaderNodeMath"); gm_.operation = "MULTIPLY"; gm_.name = "GLOWMASK"
    nt.links.new(glow.outputs["Result"], gm_.inputs[0]); nt.links.new(gl2.outputs["Result"], gm_.inputs[1])
    return mat, nt, em, out, gm_


def bake(obj, name):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.render.bake.margin = 6
    img = bpy.data.images.new("T_Char_" + name, TEX_SIZE, TEX_SIZE, alpha=True)
    glow = bpy.data.images.new("G_" + name, TEX_SIZE, TEX_SIZE, alpha=False)
    mat, nt, em, out, gmask = bake_material(name, img)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.data.uv_layers.active = obj.data.uv_layers["BakeUV"]
    bpy.ops.object.bake(type="EMIT")
    # glow mask pass
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image == img:
            n.image = glow
            nt.nodes.active = n
    nt.links.new(gmask.outputs["Value"], em.inputs["Strength"])
    em.inputs["Color"].default_value = (1, 1, 1, 1)
    for l in list(nt.links):
        if l.to_node == em and l.to_socket.name == "Color":
            nt.links.remove(l)
    bpy.ops.object.bake(type="EMIT")
    px = np.array(img.pixels[:]).reshape(-1, 4)
    g = np.array(glow.pixels[:]).reshape(-1, 4)[:, 0]
    px[:, 3] = np.where(g > 0.5, 32.0 / 255.0, 0.0)
    img.pixels[:] = px.ravel()
    os.makedirs(OUT_TEX, exist_ok=True)
    img.filepath_raw = os.path.join(OUT_TEX, f"T_Char_{name}.png")
    img.file_format = "PNG"
    img.alpha_mode = "STRAIGHT"
    img.save()
    print("baked", img.filepath_raw)
    return img



# ----------------------------------------------------------------------------- pixel-art painter (v5)
# Bakes three low-res data maps (palette color, world normal, ambient occlusion) and paints the final texture in
# numpy like a pixel artist would: per-material 5-tone hue-shifted ramps, light quantized into bands with ordered
# dithering, 1-texel dark outlines where materials meet, sparse painterly grain. Alpha = glow mask.

PIX = 128
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) / 16.0 - 0.47
LIGHT = np.array([-0.35, -0.55, 0.76])
LIGHT /= np.linalg.norm(LIGHT)


def _emit_bake(obj, nt, em, color_socket, img):
    for l in list(nt.links):
        if l.to_node == em and l.to_socket.name == "Color":
            nt.links.remove(l)
    nt.links.new(color_socket, em.inputs["Color"])
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.name == "TARGET":
            n.image = img
            nt.nodes.active = n
    bpy.ops.object.bake(type="EMIT")
    return np.array(img.pixels[:], dtype=np.float32).reshape(PIX, PIX, 4)


def _ramp(rgb):
    """5 tones for one material: 0 deep shadow (cool, darker) .. 4 highlight (warm, lighter)."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    tones = []
    for k, (dv, dh, ds) in enumerate(((0.42, -0.06, 0.18), (0.68, -0.03, 0.1), (1.0, 0.0, 0.0), (1.22, 0.025, -0.1), (1.45, 0.05, -0.22))):
        hh = (h + (dh if s > 0.08 else 0)) % 1.0
        ss = min(1, max(0, s + ds * (1 if s > 0.08 else 0)))
        vv = min(1, max(0.03, v * dv + (0.06 if k == 4 else 0)))
        tones.append(colorsys.hsv_to_rgb(hh, ss, vv))
    return np.array(tones, dtype=np.float32)


def pixel_bake(obj, name):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 96
    sc.render.bake.margin = 2
    sc.render.bake.margin_type = "EXTEND"
    imgs = {k: bpy.data.images.new(f"{k}_{name}", PIX, PIX, alpha=True, float_buffer=True) for k in ("COL", "NRM", "AO", "GLW")}
    for im in imgs.values():
        im.colorspace_settings.name = "Non-Color"
    mat = bpy.data.materials.new("PIXBAKE_" + name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = nt.nodes.new
    uv = N("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    pal = N("ShaderNodeTexImage"); pal.image = bpy.data.images.load(PALETTE_PNG, check_existing=True)
    pal.interpolation = "Closest"
    pal.image.colorspace_settings.name = "Non-Color"     # keep raw sRGB palette values (painted directly)
    nt.links.new(uv.outputs["UV"], pal.inputs["Vector"])
    geo = N("ShaderNodeNewGeometry")
    nmap = N("ShaderNodeVectorMath"); nmap.operation = "MULTIPLY_ADD"
    nmap.inputs[1].default_value = (0.5, 0.5, 0.5); nmap.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(geo.outputs["Normal"], nmap.inputs[0])
    ao = N("ShaderNodeAmbientOcclusion"); ao.samples = 64; ao.inputs["Distance"].default_value = 0.1
    g1 = N("ShaderNodeMapRange"); g1.inputs["From Min"].default_value = 0.06; g1.inputs["From Max"].default_value = 0.07
    nt.links.new(pal.outputs["Alpha"], g1.inputs["Value"])
    g2 = N("ShaderNodeMapRange"); g2.inputs["From Min"].default_value = 0.19; g2.inputs["From Max"].default_value = 0.18
    nt.links.new(pal.outputs["Alpha"], g2.inputs["Value"])
    gm_ = N("ShaderNodeMath"); gm_.operation = "MULTIPLY"
    nt.links.new(g1.outputs["Result"], gm_.inputs[0]); nt.links.new(g2.outputs["Result"], gm_.inputs[1])
    em = N("ShaderNodeEmission")
    out = N("ShaderNodeOutputMaterial"); nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    tgt = N("ShaderNodeTexImage"); tgt.name = "TARGET"
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.data.uv_layers.active = obj.data.uv_layers["BakeUV"]

    col = _emit_bake(obj, nt, em, pal.outputs["Color"], imgs["COL"])
    nrm = _emit_bake(obj, nt, em, nmap.outputs["Vector"], imgs["NRM"])
    aom = _emit_bake(obj, nt, em, ao.outputs["Color"], imgs["AO"])
    glw = _emit_bake(obj, nt, em, gm_.outputs["Value"], imgs["GLW"])

    # covered texels: anything the bake wrote (margin included)
    valid = col[..., 3] > 0.5
    rgb = col[..., :3]
    # material id = exact palette color
    key = (np.round(rgb * 255).astype(np.int32) * np.array([65536, 256, 1])).sum(-1)
    key[~valid] = -1
    n = nrm[..., :3] * 2 - 1
    ndl = np.clip((n * LIGHT).sum(-1), -1, 1)
    occl = aom[..., 0]
    # denoise AO: 5x5 box blur restricted to covered texels (noisy AO would quantize into camo blotches)
    acc = np.zeros_like(occl); cnt = np.zeros_like(occl)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            acc += np.roll(np.roll(occl * valid, dy, 0), dx, 1)
            cnt += np.roll(np.roll(valid.astype(np.float32), dy, 0), dx, 1)
    occl = np.where(cnt > 0, acc / np.maximum(cnt, 1), occl)
    shade = 0.5 + 0.42 * ndl                     # wrap lighting
    shade = shade * (0.55 + 0.45 * occl)         # AO darkens creases
    yy, xx = np.mgrid[0:PIX, 0:PIX]
    rng = np.random.default_rng(abs(hash(name)) % 1000)
    level = shade * 4.0 + BAYER4[yy % 4, xx % 4] * 0.5 + (rng.random((PIX, PIX)) - 0.5) * 0.12
    level = np.clip(np.floor(level + 0.5), 0, 4).astype(np.int32)

    out_rgb = np.zeros((PIX, PIX, 3), dtype=np.float32)
    ramps = {}
    for k in np.unique(key[valid]):
        m = key == k
        c = rgb[m][0]
        ramps[k] = _ramp(tuple(float(x) for x in c))
        out_rgb[m] = ramps[k][level[m]]

    # 1-texel outlines where two materials meet (the darker side gets the line)
    lum = rgb @ np.array([0.3, 0.59, 0.11], dtype=np.float32)
    edge = np.zeros((PIX, PIX), dtype=bool)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nk = np.roll(np.roll(key, dy, 0), dx, 1)
        nl = np.roll(np.roll(lum, dy, 0), dx, 1)
        edge |= valid & (nk >= 0) & (nk != key) & (lum <= nl)
    # strong contrast -> near-black line; similar materials -> just one tone darker
    contrast = np.zeros((PIX, PIX), dtype=np.float32)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nk = np.roll(np.roll(key, dy, 0), dx, 1)
        nl = np.roll(np.roll(lum, dy, 0), dx, 1)
        contrast = np.maximum(contrast, np.where((nk >= 0) & (nk != key), np.abs(nl - lum), 0))
    for k, ramp in ramps.items():
        m = edge & (key == k)
        strong = m & (contrast > 0.25)
        soft_ = m & ~strong
        out_rgb[strong] = ramp[0] * 0.85
        out_rgb[soft_] = ramp[np.maximum(level[soft_] - 2, 0)]

    # glow cells stay bright and flat (emissive in PixelLit)
    g = glw[..., 0] > 0.5
    out_rgb[g] = rgb[g]
    alpha = np.where(g, 32.0 / 255.0, 0.0)
    final = np.concatenate([out_rgb, alpha[..., None]], -1)
    final[~valid] = 0

    img = bpy.data.images.new("T_Char_" + name, PIX, PIX, alpha=True)
    img.colorspace_settings.name = "Non-Color"   # values are already sRGB
    img.pixels[:] = final.ravel()
    os.makedirs(OUT_TEX, exist_ok=True)
    img.filepath_raw = os.path.join(OUT_TEX, f"T_Char_{name}.png")
    img.file_format = "PNG"
    img.alpha_mode = "STRAIGHT"
    img.save()
    print("painted", img.filepath_raw)
    return img

# ----------------------------------------------------------------------------- build


def build(name, preview=False, reset=True):
    if reset:
        gm.reset()
    gm.JOINTS.clear()
    PIECES.clear()
    HEROES[name]()
    for o, bone in PIECES:
        if bone:
            rigid(o, bone)
        else:
            weigh(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o, _ in PIECES:
        o.select_set(True)
    bpy.context.view_layer.objects.active = PIECES[0][0]
    bpy.ops.object.join()
    mesh = bpy.context.active_object
    mesh.name = "Skin"
    mesh.data.name = "Skin_" + name
    # atlas UVs for the bake (palette UVs stay in "UVMap" while baking)
    uv = mesh.data.uv_layers.new(name="BakeUV")
    mesh.data.uv_layers.active = uv
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.025, area_weight=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    pixel_bake(mesh, name)
    # final: single UV set + named material for Unity's remap
    mesh.data.uv_layers.remove(mesh.data.uv_layers["UVMap"])
    mesh.data.uv_layers["BakeUV"].name = "UVMap"
    mesh.data.materials.clear()
    mat = bpy.data.materials.new("M_Char_" + name)
    if preview:
        mat.use_nodes = True
        tn = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = bpy.data.images.get("T_Char_" + name)
        tn.interpolation = "Closest"
        tn.image.alpha_mode = "NONE"
        tn.image.colorspace_settings.name = "sRGB"
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        mat.node_tree.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    mesh.data.materials.append(mat)
    rig = armature()
    mesh.parent = rig
    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    return mesh, rig


def export(name):
    # Unity's "Bake Axis Conversion" turns -Y-facing Blender characters around: pre-rotate so they face the game's forward
    rig = bpy.data.objects.get("Rig")
    if rig is not None:
        bpy.ops.object.select_all(action="DESELECT")
        rig.rotation_euler.z = math.pi
        for o in [rig] + list(rig.children):
            o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    os.makedirs(OUT_MODELS, exist_ok=True)
    path = os.path.join(OUT_MODELS, name + ".fbx")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH", "ARMATURE"},
        apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        mesh_smooth_type="FACE", add_leaf_bones=False, armature_nodetype="NULL", primary_bone_axis="Y",
        secondary_bone_axis="X", use_armature_deform_only=True, bake_anim=False)
    print("exported", path)


def preview(names):
    """Render the finished heroes with their baked textures (Tools/Blender/heroes_v4.png)."""
    sys.argv = sys.argv  # noqa
    import render_previews as rp
    gm.reset()
    for i, n in enumerate(names):
        mesh, rig = build(n, preview=True, reset=False)
        rig.location.x += i * 1.3
    bpy.context.scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
    rp.setup_render(1600, 900, transparent=False)
    rp.camera((1.95 + 1.2, -6.5, 2.4), (1.95, 0, 1.15), lens=50)
    bpy.context.scene.render.filepath = os.path.join(ROOT, "Tools", "Blender", "heroes_v4.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = [a for a in args if a in HEROES] or list(HEROES)
    if "--preview" in args:
        preview(names)
    else:
        for n in names:
            build(n)
            export(n)
